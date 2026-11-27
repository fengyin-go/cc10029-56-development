"""外评证据受控凭证接口。

独立于通用资源路由：授权发放、受控只读、验票受理、补件闭环和接收前体检
都有专属路径，路径前缀 /api/evidence 固定，需在资源动态路由之前注册。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    EvidenceScopePayload,
    GrantIssuePayload,
    SupplementCompletePayload,
)
from app.services.evidence_access import evidence_service
from app.services.external_eval import ExternalEvalService

router = APIRouter(prefix="/api/evidence", tags=["外评证据凭证"])


def _result(ok: bool, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": ok, "message": message}
    payload.update(extra)
    return payload


@router.post("/grants")
def issue_grant(payload: GrantIssuePayload) -> dict[str, Any]:
    """授权入口：按评估报告发放针对指定档案的只读凭证。"""
    entry, message = evidence_service.issue_grant(
        eval_id=payload.eval_id,
        record_id=payload.record_id,
        recipient=payload.recipient,
        issuer=payload.issuer,
        purpose=payload.purpose or "",
    )
    if entry is None:
        return _result(False, message)
    return _result(True, message, entry=entry)


@router.get("/grants")
def list_grants(
    eval_id: int | None = Query(default=None),
) -> dict[str, Any]:
    """凭证台账：已签收/已失效凭证均保留原编号可查。"""
    items = evidence_service.list_grants(eval_id=eval_id)
    return _result(True, f"共 {len(items)} 张授权凭证", items=items)


@router.get("/grants/{grant_no}")
def get_grant(grant_no: str) -> dict[str, Any]:
    """按原编号查凭证：发给谁、实际用了哪件档案、发放时点快照。"""
    grant = evidence_service.get_grant(grant_no)
    if grant is None:
        raise HTTPException(status_code=404, detail=f"凭证 {grant_no} 不存在")
    logs = evidence_service.list_access_logs(grant_no=grant_no)
    return _result(
        True, "凭证查询成功", entry=grant, access_logs=logs,
    )


@router.post("/grants/{grant_no}/read")
def read_record_evidence(grant_no: str, payload: EvidenceScopePayload) -> dict[str, Any]:
    """受控只读：外部收件人持凭证按报告/档案归属核对档案内容。"""
    view, message = evidence_service.read_record_evidence(
        grant_no=grant_no,
        eval_id=payload.eval_id,
        record_id=payload.record_id,
    )
    if view is None:
        return _result(False, message)
    return _result(True, message, entry=view)


@router.post("/grants/{grant_no}/tickets")
def accept_ticket(grant_no: str, payload: EvidenceScopePayload) -> dict[str, Any]:
    """材料验票：校验凭证与报告引用归属，通过后出具受理回执。"""
    ticket, message = evidence_service.accept_ticket(
        grant_no=grant_no,
        eval_id=payload.eval_id,
        record_id=payload.record_id,
    )
    if ticket is None:
        return _result(False, message)
    return _result(True, message, entry=ticket)


@router.get("/tickets")
def list_tickets(
    eval_id: int | None = Query(default=None),
) -> dict[str, Any]:
    """受理回执台账。"""
    items = evidence_service.list_tickets(eval_id=eval_id)
    return _result(True, f"共 {len(items)} 张受理回执", items=items)


@router.get("/supplements")
def list_supplements(
    eval_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    """外评补件待办：档案资格变化自动生成。"""
    items = evidence_service.list_supplements(eval_id=eval_id, status=status)
    return _result(True, f"共 {len(items)} 条补件记录", items=items)


@router.post("/supplements/{supplement_id}/complete")
def complete_supplement(
    supplement_id: int, payload: SupplementCompletePayload
) -> dict[str, Any]:
    """补件闭环：用替代档案的新凭证、新回执办结，旧授权不得跨报告沿用。"""
    entry, message = evidence_service.complete_supplement(
        supplement_id=supplement_id,
        new_grant_no=payload.new_grant_no,
    )
    if entry is None:
        return _result(False, message)
    return _result(True, message, entry=entry)


@router.get("/reports/{eval_id}/receive-check")
def receive_check(eval_id: int) -> dict[str, Any]:
    """接收报告入口前置体检：原授权能否完成已受理引用。"""
    diagnosis = ExternalEvalService().receive_diagnosis(eval_id)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail=f"评估报告 {eval_id} 不存在或已归档")
    return _result(True, diagnosis["提示"], diagnosis=diagnosis)
