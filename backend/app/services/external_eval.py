"""外部评估领域服务：评估报告登记、接收、转办，含跨模块关联学期目标和教学档案。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services.evidence_access import evidence_service


class ExternalEvalService(BaseModuleService):
    MODULE = "external_eval"
    ENTITY = "评估报告"
    OPERATION_TERM = "接收报告"
    LIST_FIELDS = ["评估机构", "评估指标", "评估结论", "出具日期", "接收部门", "整改要求", "有效期至", "备注说明"]
    REQUIRED_FIELDS = ["评估机构", "评估指标", "评估结论"]
    STATUS_ORDER = ["草稿", "待接收", "已接收", "已转办"]
    ACTION_RULES = {"接收报告": "已接收", "退回补充": "草稿", "转办整改": "已转办"}
    NEGATIVE_ACTIONS = []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含跨模块联动。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 接收报告：必须是待接收
        if action == "接收报告":
            if entry.get("status") not in ("待接收", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可接收"
            # 接收前凭证体检：档案注销与授权使用冲突时，先判断原授权能否
            # 完成已受理引用；被阻断则等待替代证明和新的授予。
            diagnosis = evidence_service.diagnose_receive(entry_id)
            if not diagnosis["可接收"]:
                return None, (
                    f"{self.ENTITY} {entry_id} 暂不可接收：{diagnosis['提示']}"
                )

        # 转办整改：必须先接收
        if action == "转办整改":
            if entry.get("status") != "已接收":
                return None, f"{self.ENTITY} {entry_id} 必须先接收报告，才能转办"

        result, message = super().run_action(entry_id, action)
        if action == "接收报告" and result is not None:
            # 签收外发凭证：回执转入已引用、凭证记录实际签收，历史编号保持可查。
            evidence_service.confirm_report_received(entry_id)
        return result, message

    def receive_diagnosis(self, entry_id: int) -> dict[str, Any] | None:
        """供路由调用的接收前凭证体检入口。"""
        if self.get_entry(entry_id) is None:
            return None
        return evidence_service.diagnose_receive(entry_id)