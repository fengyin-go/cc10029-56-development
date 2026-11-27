"""通用接口契约；模块字段由领域服务持有，不再为每个模块复制一份模型类。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    action: str
    remark: str | None = None


class GrantIssuePayload(BaseModel):
    """按评估报告发放证据授权凭证。"""
    eval_id: int
    record_id: int
    recipient: str
    issuer: str
    purpose: str | None = None


class EvidenceScopePayload(BaseModel):
    """持凭证读取档案或验票时的归属参数。"""
    eval_id: int
    record_id: int


class SupplementCompletePayload(BaseModel):
    """用替代凭证办结外评补件。"""
    new_grant_no: str
