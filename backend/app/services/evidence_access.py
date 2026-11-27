"""外评证据受控凭证领域服务。

围绕「外部评估报告 ↔ 教学档案」发放只读授权凭证，核心约束：

1. 授权按评估报告发放，并绑定具体档案；读取权限同时受报告归属与档案归属限制，
   R-26 的凭证不能打开 R-25 的证据，外部收件人对档案只有只读权限。
2. 评审员凭凭证完成材料验票后取得受理回执，回执是接收报告时填写引用的凭据。
3. 档案资格变化（注销）会使在用凭证失效、阻断相关回执，并生成外评补件待办。
4. 注销后发放的新授权不得再引用该注销档案；已签收的历史凭证仍保留原编号、
   原收件人和实际使用的档案，补件不能跨报告沿用旧授权。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

# 三张领域表 + 一张只读访问审计表，均在内存仓库中按需创建。
GRANT_TABLE = "evidence_grant"
TICKET_TABLE = "evidence_ticket"
SUPPLEMENT_TABLE = "eval_supplement"
ACCESS_LOG_TABLE = "evidence_access_log"


def _rows(table: str) -> list[dict[str, Any]]:
    return store.rows(table)


def _next_serial(prefix: str, table: str) -> str:
    """生成带日期的稳定业务编号，历史凭证即使失效也保留原编号可查。"""
    today = date.today().strftime("%Y%m%d")
    seq = sum(1 for row in _rows(table) if str(row.get("id", 0))) + 1
    return f"{prefix}-{today}-{seq:03d}"


def _next_id(table: str) -> int:
    return max((int(row.get("id", 0)) for row in _rows(table)), default=0) + 1


class EvidenceAccessService:
    """外评证据授权、验票、补件与接收校验的统一领域入口。"""

    # ------------------------------------------------------------------ 发放
    def issue_grant(
        self,
        eval_id: int,
        record_id: int,
        recipient: str,
        issuer: str,
        purpose: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        """按评估报告发放针对某件档案的只读授权凭证。"""
        recipient = (recipient or "").strip()
        issuer = (issuer or "").strip()
        if not recipient:
            return None, "外部收件人不能为空"
        if not issuer:
            return None, "发放人不能为空"

        eval_entry = store.find("external_eval", eval_id)
        if eval_entry is None:
            return None, f"评估报告 {eval_id} 不存在，无法发放证据授权"
        record = store.find("teach_record", record_id)
        if record is None:
            return None, f"档案条目 {record_id} 不存在，无法发放证据授权"

        # 注销档案不具备对外提供证据的资格，此后不得再发放新授权。
        if record.get("status") == "已注销":
            return None, (
                f"档案条目 {record_id} 已注销，不能再对外发放授权，"
                "请改用替代档案重新申请"
            )
        if record.get("status") != "已归档":
            return None, (
                f"档案条目 {record_id} 当前状态为'{record.get('status')}'，"
                "须审核归档后才能对外发放证据授权"
            )

        # 同一报告、同一档案、同一收件人只保留一张有效凭证，避免授权泛滥。
        for row in _rows(GRANT_TABLE):
            if (
                row.get("评估报告ID") == eval_id
                and row.get("档案ID") == record_id
                and row.get("外部收件人") == recipient
                and row.get("状态") == "有效"
            ):
                return None, (
                    f"收件人{recipient}针对评估报告 {eval_id} / 档案 {record_id} "
                    f"已有有效凭证 {row['凭证编号']}，无需重复发放"
                )

        grant = {
            "id": _next_id(GRANT_TABLE),
            "凭证编号": _next_serial("GR", GRANT_TABLE),
            "评估报告ID": eval_id,
            "档案ID": record_id,
            "外部收件人": recipient,
            "发放人": issuer,
            "发放日期": date.today().isoformat(),
            "用途说明": purpose.strip(),
            "权限范围": "只读",
            "状态": "有效",
            "失效原因": "",
            "签收状态": "待使用",
            # 留存发放时点的档案快照，注销后仍可还原「实际用了哪件档案」。
            "档案快照": {
                "教师姓名": record.get("教师姓名"),
                "档案类型": record.get("档案类型"),
                "内容摘要": record.get("内容摘要"),
                "存档日期": record.get("存档日期"),
                "发放时状态": record.get("status"),
            },
        }
        _rows(GRANT_TABLE).append(grant)
        return grant, f"授权凭证 {grant['凭证编号']} 已发放，收件人对该档案只读"

    # ------------------------------------------------------------- 受控只读
    def read_record_evidence(
        self, grant_no: str, eval_id: int, record_id: int
    ) -> tuple[dict[str, Any] | None, str]:
        """外部收件人持凭证读取档案：三重归属校验通过才返回只读视图。"""
        grant = self._find_grant(grant_no)
        if grant is None:
            self._log_access(grant_no, eval_id, record_id, "", "拒绝：凭证不存在")
            return None, f"凭证 {grant_no} 不存在"

        common_ok, reason = self._check_scope(grant, eval_id, record_id)
        if not common_ok:
            self._log_access(
                grant_no, eval_id, record_id,
                str(grant.get("外部收件人", "")), f"拒绝：{reason}",
            )
            return None, reason

        record = store.find("teach_record", record_id)
        assert record is not None  # _check_scope 已保证档案存在
        # 注销后不允许再通过凭证读取实体档案，但历史凭证与快照仍可按编号查询。
        if record.get("status") == "已注销":
            self._log_access(
                grant_no, eval_id, record_id,
                str(grant.get("外部收件人", "")), "拒绝：档案已注销",
            )
            return None, (
                f"档案条目 {record_id} 已注销，凭证 {grant_no} 已失效，"
                "不能再读取该档案，请等待替代证明和新的授予"
            )

        view = {field: record.get(field) for field in [
            "id", "教师姓名", "档案类型", "内容摘要", "存档日期",
            "关联学期", "保管期限", "status",
        ]}
        view["只读提示"] = "外部收件人仅可核对，不可修改档案内容"
        self._log_access(
            grant_no, eval_id, record_id,
            str(grant.get("外部收件人", "")), "放行：只读核对",
        )
        return view, f"凭证 {grant_no} 校验通过，已返回档案 {record_id} 只读视图"

    def _check_scope(
        self, grant: dict[str, Any], eval_id: int, record_id: int
    ) -> tuple[bool, str]:
        """凭证有效性 + 报告归属 + 档案归属三重校验。"""
        if grant.get("状态") != "有效":
            reason = (
                f"凭证 {grant['凭证编号']} 已失效"
                + (f"（{grant.get('失效原因')}）" if grant.get("失效原因") else "")
            )
            if grant.get("失效原因"):
                reason += "，请等待替代证明和新的授予"
            return False, reason
        if grant.get("评估报告ID") != eval_id:
            # 同一评审人处理 R-25/R-26 两份报告时，凭证不可跨报告使用。
            return False, (
                f"凭证 {grant['凭证编号']} 归属评估报告 "
                f"{grant.get('评估报告ID')}，不能用于打开评估报告 {eval_id} 的证据"
            )
        if grant.get("档案ID") != record_id:
            return False, (
                f"凭证 {grant['凭证编号']} 未授权档案条目 {record_id}，"
                f"其授权范围仅限档案条目 {grant.get('档案ID')}"
            )
        if store.find("external_eval", eval_id) is None:
            return False, f"评估报告 {eval_id} 不存在"
        if store.find("teach_record", record_id) is None:
            return False, f"档案条目 {record_id} 不存在"
        return True, ""

    # ------------------------------------------------------------------ 验票
    def accept_ticket(
        self, grant_no: str, eval_id: int, record_id: int
    ) -> tuple[dict[str, Any] | None, str]:
        """评审员持凭证完成材料验票，通过后取得可填写引用的受理回执。"""
        grant = self._find_grant(grant_no)
        if grant is None:
            return None, f"凭证 {grant_no} 不存在"
        ok, reason = self._check_scope(grant, eval_id, record_id)
        if not ok:
            return None, reason
        record = store.find("teach_record", record_id)
        assert record is not None
        if record.get("status") == "已注销":
            return None, (
                f"档案条目 {record_id} 已注销，验票失败；请等待替代证明并申请新凭证"
            )

        # 一张凭证只出一张受理回执；已被注销阻断的回执不允许重复受理。
        for row in _rows(TICKET_TABLE):
            if row.get("凭证编号") == grant_no and row.get("状态") == "已受理":
                return None, (
                    f"凭证 {grant_no} 已完成验票，受理回执 {row['回执编号']} "
                    "仍可使用，无需重复验票"
                )

        ticket = {
            "id": _next_id(TICKET_TABLE),
            "回执编号": _next_serial("RC", TICKET_TABLE),
            "凭证编号": grant_no,
            "评估报告ID": eval_id,
            "档案ID": record_id,
            "外部收件人": grant.get("外部收件人"),
            "受理日期": date.today().isoformat(),
            "受理结论": "材料验票通过，可在评估报告中填写该档案引用",
            "状态": "已受理",
            "引用填写状态": "待填写引用",
            "阻断原因": "",
        }
        _rows(TICKET_TABLE).append(ticket)
        return ticket, f"受理回执 {ticket['回执编号']} 已出具，可填写档案引用"

    # ---------------------------------------------------------- 档案资格联动
    def handle_record_revoked(self, record_id: int) -> list[dict[str, Any]]:
        """档案注销时：失效在用凭证、阻断受理回执、生成外评补件待办。

        由 TeachRecordService 的「注销档案」动作调用；返回生成的补件列表。
        已签收的历史凭证不删除，只改状态并保留原编号与档案快照。
        """
        created_supplements: list[dict[str, Any]] = []
        affected_grants = [
            row for row in _rows(GRANT_TABLE)
            if row.get("档案ID") == record_id and row.get("状态") == "有效"
        ]
        for grant in affected_grants:
            grant["状态"] = "已失效"
            grant["失效原因"] = f"档案条目 {record_id} 已注销"
            grant["签收状态"] = "已冻结"

        for ticket in _rows(TICKET_TABLE):
            if ticket.get("档案ID") != record_id or ticket.get("状态") != "已受理":
                continue
            ticket["状态"] = "已阻断"
            ticket["阻断原因"] = f"凭证 {ticket['凭证编号']} 因档案注销失效"

            # 同一报告 + 同一档案 + 同一收件人只挂一个待办，重复注销不重复生成。
            exists = any(
                row.get("评估报告ID") == ticket["评估报告ID"]
                and row.get("档案ID") == record_id
                and row.get("外部收件人") == ticket["外部收件人"]
                and row.get("状态") == "待补件"
                for row in _rows(SUPPLEMENT_TABLE)
            )
            if exists:
                continue
            supplement = {
                "id": _next_id(SUPPLEMENT_TABLE),
                "补件编号": _next_serial("BC", SUPPLEMENT_TABLE),
                "评估报告ID": ticket["评估报告ID"],
                "档案ID": record_id,
                "来源凭证编号": ticket["凭证编号"],
                "来源回执编号": ticket["回执编号"],
                "外部收件人": ticket["外部收件人"],
                "触发原因": f"档案条目 {record_id} 注销，原引用失去有效凭证支撑",
                "生成日期": date.today().isoformat(),
                "状态": "待补件",
                "替代凭证编号": "",
                "替代回执编号": "",
                "完成日期": "",
                "备注说明": "",
            }
            _rows(SUPPLEMENT_TABLE).append(supplement)
            created_supplements.append(supplement)
        return created_supplements

    # ------------------------------------------------------------- 补件闭环
    def complete_supplement(
        self, supplement_id: int, new_grant_no: str
    ) -> tuple[dict[str, Any] | None, str]:
        """用替代档案的新凭证和新受理回执办结补件；旧授权不得跨报告沿用。"""
        supplement = store.find(SUPPLEMENT_TABLE, supplement_id)
        if supplement is None:
            return None, f"外评补件 {supplement_id} 不存在"
        if supplement.get("状态") == "已完成":
            return None, f"补件 {supplement['补件编号']} 已完成，无需重复办结"

        new_grant = self._find_grant(new_grant_no)
        if new_grant is None:
            return None, f"替代凭证 {new_grant_no} 不存在"
        if new_grant.get("状态") != "有效":
            return None, f"替代凭证 {new_grant_no} 不是有效凭证，不能用于补件"
        # 补件绑定原报告：新授予必须归属同一份评估报告，禁止跨报告沿用。
        if new_grant.get("评估报告ID") != supplement["评估报告ID"]:
            return None, (
                f"替代凭证 {new_grant_no} 归属报告 {new_grant.get('评估报告ID')}，"
                f"补件 {supplement['补件编号']} 属于报告 "
                f"{supplement['评估报告ID']}，补件不能跨报告沿用授权"
            )
        # 新授予必须指向另一件仍具资格的档案，不能再挂回已注销档案。
        if new_grant.get("档案ID") == supplement["档案ID"]:
            return None, (
                f"档案条目 {supplement['档案ID']} 已注销，"
                "替代凭证必须指向新的替代档案"
            )
        new_record = store.find("teach_record", int(new_grant["档案ID"]))
        if new_record is None or new_record.get("status") != "已归档":
            return None, "替代凭证指向的档案不存在或未处于已归档状态"

        new_ticket = next((
            row for row in _rows(TICKET_TABLE)
            if row.get("凭证编号") == new_grant_no
            and row.get("评估报告ID") == supplement["评估报告ID"]
            and row.get("状态") == "已受理"
        ), None)
        if new_ticket is None:
            return None, (
                f"替代凭证 {new_grant_no} 尚未完成材料验票，"
                "请先取得新的受理回执再办结补件"
            )

        supplement["状态"] = "已完成"
        supplement["替代凭证编号"] = new_grant_no
        supplement["替代回执编号"] = new_ticket["回执编号"]
        supplement["完成日期"] = date.today().isoformat()
        supplement["备注说明"] = (
            f"替代档案 {new_grant['档案ID']} 已验票，原注销档案引用完成替换"
        )
        return supplement, (
            f"补件 {supplement['补件编号']} 已办结，替代凭证 {new_grant_no}、"
            f"替代回执 {new_ticket['回执编号']}"
        )

    # ------------------------------------------------------------- 接收校验
    def diagnose_receive(self, eval_id: int) -> dict[str, Any]:
        """接收报告前的凭证体检：判断原授权能否支撑已受理的引用。"""
        tickets = [
            row for row in _rows(TICKET_TABLE)
            if row.get("评估报告ID") == eval_id
        ]
        pending_supplements = [
            row for row in _rows(SUPPLEMENT_TABLE)
            if row.get("评估报告ID") == eval_id and row.get("状态") == "待补件"
        ]
        # 已被补件闭环替换的阻断回执只作历史留存，不再阻挡接收。
        unresolved_receipts = {
            row.get("来源回执编号") for row in pending_supplements
        }
        blocked = [
            row for row in tickets
            if row.get("状态") == "已阻断"
            and row.get("回执编号") in unresolved_receipts
        ]
        accepted = [row for row in tickets if row.get("状态") == "已受理"]

        if not tickets:
            can_receive = True
            message = "该报告尚无凭证验票记录，按普通流程接收报告"
        elif blocked or pending_supplements:
            can_receive = False
            message = (
                "存在被档案注销阻断的受理回执/待办补件，原授权已无法完成已受理引用，"
                "须等待替代证明、取得新凭证与新受理回执并办结补件后再接收报告"
            )
        else:
            can_receive = True
            message = (
                f"全部 {len(accepted)} 张受理回执的凭证仍有效（或阻断引用已由补件替换），"
                "原授权可完成已受理引用，可以接收报告"
            )

        return {
            "评估报告ID": eval_id,
            "可接收": can_receive,
            "提示": message,
            "受理回执": [self._ticket_brief(row) for row in tickets],
            "阻断数": len(blocked),
            "待补件数": len(pending_supplements),
        }

    def confirm_report_received(self, eval_id: int) -> None:
        """报告完成接收：把本报告有效回执标记为已引用、对应凭证标记已签收。"""
        for ticket in _rows(TICKET_TABLE):
            if ticket.get("评估报告ID") == eval_id and ticket.get("状态") == "已受理":
                ticket["引用填写状态"] = "已引用"
        ticket_grant_nos = {
            row.get("凭证编号")
            for row in _rows(TICKET_TABLE)
            if row.get("评估报告ID") == eval_id
        }
        for grant in _rows(GRANT_TABLE):
            if grant.get("凭证编号") in ticket_grant_nos and grant.get("状态") == "有效":
                grant["签收状态"] = "已签收"

    # ------------------------------------------------------------------ 查询
    def list_grants(self, eval_id: int | None = None) -> list[dict[str, Any]]:
        rows = _rows(GRANT_TABLE)
        if eval_id is not None:
            rows = [row for row in rows if row.get("评估报告ID") == eval_id]
        return rows

    def list_tickets(self, eval_id: int | None = None) -> list[dict[str, Any]]:
        rows = _rows(TICKET_TABLE)
        if eval_id is not None:
            rows = [row for row in rows if row.get("评估报告ID") == eval_id]
        return rows

    def list_supplements(
        self, eval_id: int | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        rows = _rows(SUPPLEMENT_TABLE)
        if eval_id is not None:
            rows = [row for row in rows if row.get("评估报告ID") == eval_id]
        if status:
            rows = [row for row in rows if row.get("状态") == status]
        return rows

    def list_access_logs(self, grant_no: str | None = None) -> list[dict[str, Any]]:
        rows = _rows(ACCESS_LOG_TABLE)
        if grant_no:
            rows = [row for row in rows if row.get("凭证编号") == grant_no]
        return rows

    def get_grant(self, grant_no: str) -> dict[str, Any] | None:
        """按原编号查凭证：含发给谁、实际用了哪件档案及发放时点快照。"""
        return self._find_grant(grant_no)

    # ------------------------------------------------------------------ 辅助
    def _find_grant(self, grant_no: str) -> dict[str, Any] | None:
        return next((
            row for row in _rows(GRANT_TABLE)
            if row.get("凭证编号") == grant_no
        ), None)

    def _ticket_brief(self, ticket: dict[str, Any]) -> dict[str, Any]:
        return {
            "回执编号": ticket.get("回执编号"),
            "凭证编号": ticket.get("凭证编号"),
            "档案ID": ticket.get("档案ID"),
            "外部收件人": ticket.get("外部收件人"),
            "状态": ticket.get("状态"),
            "引用填写状态": ticket.get("引用填写状态"),
            "阻断原因": ticket.get("阻断原因", ""),
        }

    def _log_access(
        self, grant_no: str, eval_id: int, record_id: int,
        recipient: str, result: str,
    ) -> None:
        _rows(ACCESS_LOG_TABLE).append({
            "id": _next_id(ACCESS_LOG_TABLE),
            "凭证编号": grant_no,
            "评估报告ID": eval_id,
            "档案ID": record_id,
            "外部收件人": recipient,
            "读取时间": date.today().isoformat(),
            "读取结果": result,
        })


# 模块级单例，路由与其他领域服务共用同一份凭证状态。
evidence_service = EvidenceAccessService()
