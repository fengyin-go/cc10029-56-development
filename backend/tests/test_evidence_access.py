"""外评证据受控凭证业务测试。

覆盖故事主线：
- 按评估报告发放授权，读取权限受报告与档案双重归属限制，外部收件人只读；
- R-26 的凭证不能打开 R-25 的证据；
- 凭证验票出具受理回执；档案注销触发授权失效、回执阻断、外评补件待办；
- 接收报告前判断原授权能否完成已受理引用，冲突时等待替代证明与新授予；
- 注销后不得再对该档案发放新授权；历史凭证按原编号可追溯；
- 补件不能跨报告沿用旧授权。
"""
from __future__ import annotations

import pytest

from app.services.evidence_access import (
    ACCESS_LOG_TABLE,
    GRANT_TABLE,
    SUPPLEMENT_TABLE,
    TICKET_TABLE,
    evidence_service as svc,
)
from app.services.external_eval import ExternalEvalService
from app.services.teach_record import TeachRecordService
from app.store import store


def clear_evidence_tables():
    for table in (GRANT_TABLE, TICKET_TABLE, SUPPLEMENT_TABLE, ACCESS_LOG_TABLE):
        store.rows(table).clear()


def make_archived_record(teacher: str = "王老师") -> int:
    """登记一件档案并走完审核归档。"""
    rec_svc = TeachRecordService()
    record, _ = rec_svc.create_entry({
        "教师姓名": teacher,
        "档案类型": "课堂教学质量档案",
        "内容摘要": f"{teacher}的学期教学档案",
    })
    rec_svc.run_action(record["id"], "审核归档")
    assert store.find("teach_record", record["id"])["status"] == "已归档"
    return record["id"]


def make_report(org: str = "省评估院") -> int:
    eval_svc = ExternalEvalService()
    report, _ = eval_svc.create_entry({
        "评估机构": org,
        "评估指标": "专业建设质量",
        "评估结论": "通过",
    })
    return report["id"]


@pytest.fixture(autouse=True)
def reset_data():
    store.rows("teach_record").clear()
    store.rows("external_eval").clear()
    clear_evidence_tables()
    yield
    clear_evidence_tables()


class TestGrantIssuance:
    """授权入口：按评估报告发放、按档案资格限制。"""

    def test_grant_requires_archived_record(self):
        eval_id = make_report()
        rec_svc = TeachRecordService()
        record, _ = rec_svc.create_entry({
            "教师姓名": "李老师", "档案类型": "档案", "内容摘要": "草稿档案",
        })
        grant, msg = svc.issue_grant(eval_id, record["id"], "评审员张工", "资料员刘工")
        assert grant is None
        assert "审核归档" in msg

    def test_grant_issued_for_report_and_record_with_readonly_scope(self):
        eval_id = make_report()
        record_id = make_archived_record()
        grant, msg = svc.issue_grant(eval_id, record_id, "评审员张工", "资料员刘工", "核对R-26引用")
        assert grant is not None
        assert grant["权限范围"] == "只读"
        assert grant["状态"] == "有效"
        assert grant["评估报告ID"] == eval_id
        assert grant["档案ID"] == record_id
        assert grant["凭证编号"].startswith("GR-")
        assert "GR-" in msg
        # 发放时点留存档案快照
        assert grant["档案快照"]["发放时状态"] == "已归档"

    def test_duplicate_active_grant_rejected(self):
        eval_id = make_report()
        record_id = make_archived_record()
        svc.issue_grant(eval_id, record_id, "评审员张工", "资料员刘工")
        again, msg = svc.issue_grant(eval_id, record_id, "评审员张工", "资料员刘工")
        assert again is None
        assert "已有有效凭证" in msg

    def test_recipient_and_issuer_required(self):
        eval_id = make_report()
        record_id = make_archived_record()
        assert svc.issue_grant(eval_id, record_id, "", "资料员刘工")[0] is None
        assert svc.issue_grant(eval_id, record_id, "评审员张工", "  ")[0] is None

    def test_grant_requires_existing_report_and_record(self):
        record_id = make_archived_record()
        assert svc.issue_grant(999, record_id, "评审员张工", "资料员刘工")[0] is None
        eval_id = make_report()
        assert svc.issue_grant(eval_id, 999, "评审员张工", "资料员刘工")[0] is None


class TestScopedReadOnlyAccess:
    """受控读取：报告归属 + 档案归属 + 凭证有效性，外部收件人只读。"""

    def setup_method(self):
        self.eval_25 = make_report("评估中心A")  # R-25
        self.eval_26 = make_report("评估中心B")  # R-26
        self.record_a = make_archived_record("王老师")
        self.record_b = make_archived_record("赵老师")
        self.grant_26, _ = svc.issue_grant(
            self.eval_26, self.record_a, "评审员张工", "资料员刘工", "R-26验票")

    def test_valid_grant_returns_readonly_view(self):
        view, msg = svc.read_record_evidence(
            self.grant_26["凭证编号"], self.eval_26, self.record_a)
        assert view is not None
        assert view["id"] == self.record_a
        assert view["只读提示"]
        assert "只读" in msg
        # 只读视图不暴露写操作相关字段
        assert "录入人员" not in view

    def test_r26_grant_cannot_open_r25_evidence(self):
        """同一评审人处理两份报告：R-26 授权不能打开 R-25 的证据。"""
        view, msg = svc.read_record_evidence(
            self.grant_26["凭证编号"], self.eval_25, self.record_a)
        assert view is None
        assert "归属评估报告" in msg
        assert str(self.eval_25) in msg

    def test_grant_cannot_read_other_record(self):
        view, msg = svc.read_record_evidence(
            self.grant_26["凭证编号"], self.eval_26, self.record_b)
        assert view is None
        assert "未授权档案条目" in msg

    def test_unknown_grant_rejected_and_logged(self):
        view, msg = svc.read_record_evidence("GR-NONE", self.eval_26, self.record_a)
        assert view is None
        assert "不存在" in msg
        logs = svc.list_access_logs("GR-NONE")
        assert len(logs) == 1 and logs[0]["读取结果"].startswith("拒绝")

    def test_denied_access_writes_audit_log_but_allowed_does_too(self):
        svc.read_record_evidence(
            self.grant_26["凭证编号"], self.eval_25, self.record_a)  # 拒绝
        svc.read_record_evidence(
            self.grant_26["凭证编号"], self.eval_26, self.record_a)  # 放行
        logs = svc.list_access_logs(self.grant_26["凭证编号"])
        assert [log["读取结果"].startswith(("拒绝", "放行")) for log in logs]
        assert any("拒绝" in log["读取结果"] for log in logs)
        assert any("放行" in log["读取结果"] for log in logs)


class TestTicketAcceptance:
    """材料验票与受理回执。"""

    def setup_method(self):
        self.eval_id = make_report()
        self.record_id = make_archived_record()
        self.grant, _ = svc.issue_grant(
            self.eval_id, self.record_id, "评审员张工", "资料员刘工")

    def test_ticket_issued_after_scope_validation(self):
        ticket, msg = svc.accept_ticket(
            self.grant["凭证编号"], self.eval_id, self.record_id)
        assert ticket is not None
        assert ticket["回执编号"].startswith("RC-")
        assert ticket["状态"] == "已受理"
        assert ticket["引用填写状态"] == "待填写引用"
        assert "可填写" in msg

    def test_ticket_rejects_cross_report_usage(self):
        other_eval = make_report()
        ticket, msg = svc.accept_ticket(
            self.grant["凭证编号"], other_eval, self.record_id)
        assert ticket is None
        assert "归属评估报告" in msg

    def test_ticket_idempotent_per_grant(self):
        first, _ = svc.accept_ticket(
            self.grant["凭证编号"], self.eval_id, self.record_id)
        again, msg = svc.accept_ticket(
            self.grant["凭证编号"], self.eval_id, self.record_id)
        assert again is None
        assert first["回执编号"] in msg


class TestRevocationConflict:
    """授权使用与档案注销冲突的完整链路（R-26 主线）。"""

    def setup_method(self):
        self.eval_svc = ExternalEvalService()
        self.rec_svc = TeachRecordService()
        self.eval_id = make_report()
        self.record_id = make_archived_record()
        grant, _ = svc.issue_grant(
            self.eval_id, self.record_id, "评审员张工", "资料员刘工", "R-26")
        self.grant_no = grant["凭证编号"]
        self.ticket, _ = svc.accept_ticket(
            self.grant_no, self.eval_id, self.record_id)
        # 已取得可以填写引用的受理回执
        assert self.ticket["状态"] == "已受理"

    def test_revocation_invalidates_grant_blocks_ticket_and_creates_supplement(self):
        result, msg = self.rec_svc.run_action(self.record_id, "注销档案")
        assert result is not None and result["status"] == "已注销"
        assert "外评补件待办" in msg

        grant = svc.get_grant(self.grant_no)
        assert grant["状态"] == "已失效"
        assert "已注销" in grant["失效原因"]

        tickets = svc.list_tickets(self.eval_id)
        assert tickets[0]["状态"] == "已阻断"
        assert "注销" in tickets[0]["阻断原因"]

        supplements = svc.list_supplements(eval_id=self.eval_id, status="待补件")
        assert len(supplements) == 1
        todo = supplements[0]
        assert todo["来源凭证编号"] == self.grant_no
        assert todo["来源回执编号"] == self.ticket["回执编号"]
        assert todo["档案ID"] == self.record_id
        assert todo["外部收件人"] == "评审员张工"

    def test_revoked_grant_can_no_longer_read_evidence(self):
        self.rec_svc.run_action(self.record_id, "注销档案")
        view, msg = svc.read_record_evidence(
            self.grant_no, self.eval_id, self.record_id)
        assert view is None
        assert "已失效" in msg
        assert "替代证明" in msg

    def test_revoked_record_cannot_receive_new_grant(self):
        """此后发放的新授权不能再使用那件注销档案。"""
        self.rec_svc.run_action(self.record_id, "注销档案")
        new_grant, msg = svc.issue_grant(
            self.eval_id, self.record_id, "评审员张工", "资料员刘工")
        assert new_grant is None
        assert "已注销" in msg

    def test_receive_blocked_until_replacement_completes_supplement(self):
        """接收报告前先看原授权是否仍能完成已受理引用。"""
        # 注销前体检：原授权有效，可以接收
        diagnosis = svc.diagnose_receive(self.eval_id)
        assert diagnosis["可接收"] is True
        assert diagnosis["阻断数"] == 0

        self.rec_svc.run_action(self.record_id, "注销档案")

        # 冲突后体检：必须等待替代证明和新的授予
        diagnosis = svc.diagnose_receive(self.eval_id)
        assert diagnosis["可接收"] is False
        assert diagnosis["阻断数"] == 1
        assert diagnosis["待补件数"] == 1
        assert any(t["状态"] == "已阻断" for t in diagnosis["受理回执"])

        # 报告接收动作被拦截
        result, msg = self.eval_svc.run_action(self.eval_id, "接收报告")
        assert result is None
        assert "暂不可接收" in msg

        # 替代档案 → 新凭证 → 新验票回执 → 办结补件
        replacement_id = make_archived_record("替代档案教师")
        new_grant, _ = svc.issue_grant(
            self.eval_id, replacement_id, "评审员张工", "资料员刘工", "R-26替代证明")
        new_ticket, _ = svc.accept_ticket(
            new_grant["凭证编号"], self.eval_id, replacement_id)

        supplement = svc.list_supplements(eval_id=self.eval_id, status="待补件")[0]
        done, done_msg = svc.complete_supplement(
            supplement["id"], new_grant["凭证编号"])
        assert done is not None and done["状态"] == "已完成"
        assert done["替代回执编号"] == new_ticket["回执编号"]
        assert "已办结" in done_msg

        # 补件办结后体检放行，报告可接收，凭证与回执进入签收/已引用
        diagnosis = svc.diagnose_receive(self.eval_id)
        assert diagnosis["可接收"] is True
        received, _ = self.eval_svc.run_action(self.eval_id, "接收报告")
        assert received is not None and received["status"] == "已接收"
        assert svc.get_grant(new_grant["凭证编号"])["签收状态"] == "已签收"
        final_ticket = next(
            t for t in svc.list_tickets(self.eval_id)
            if t["凭证编号"] == new_grant["凭证编号"])
        assert final_ticket["引用填写状态"] == "已引用"

    def test_revocation_without_active_grants_is_quiet(self):
        plain_record = make_archived_record("无外评档案教师")
        result, msg = self.rec_svc.run_action(plain_record, "注销档案")
        assert result is not None
        assert "无关联外评凭证" in msg
        assert svc.list_supplements() == []

    def test_revocation_todo_not_duplicated_on_repeat_path(self):
        self.rec_svc.run_action(self.record_id, "注销档案")
        # 再次执行联动逻辑不应重复生成待办
        svc.handle_record_revoked(self.record_id)
        pending = svc.list_supplements(eval_id=self.eval_id, status="待补件")
        assert len(pending) == 1


class TestHistoricalTraceability:
    """已签收/已失效凭证仍可按原编号追溯收件人与实际档案。"""

    def test_signed_grant_keeps_original_number_recipient_and_record(self):
        eval_id = make_report()
        record_id = make_archived_record()
        grant, _ = svc.issue_grant(eval_id, record_id, "外评机构收件人陈工", "资料员刘工")
        svc.accept_ticket(grant["凭证编号"], eval_id, record_id)
        eval_svc = ExternalEvalService()
        eval_svc.run_action(eval_id, "接收报告")

        signed = svc.get_grant(grant["凭证编号"])
        assert signed is not None
        assert signed["凭证编号"] == grant["凭证编号"]
        assert signed["外部收件人"] == "外评机构收件人陈工"
        assert signed["档案ID"] == record_id
        assert signed["签收状态"] == "已签收"
        assert signed["档案快照"]["教师姓名"] == "王老师"

    def test_invalidated_grant_still_queryable_by_original_number(self):
        eval_id = make_report()
        record_id = make_archived_record()
        grant, _ = svc.issue_grant(eval_id, record_id, "外评机构收件人陈工", "资料员刘工")
        TeachRecordService().run_action(record_id, "注销档案")

        history = svc.get_grant(grant["凭证编号"])
        assert history["状态"] == "已失效"
        assert history["凭证编号"] == grant["凭证编号"]
        assert history["外部收件人"] == "外评机构收件人陈工"
        assert history["档案ID"] == record_id
        assert history["档案快照"]["发放时状态"] == "已归档"


class TestSupplementCrossReportGuard:
    """补件不能跨报告沿用旧授权。"""

    def setup_method(self):
        self.r25 = make_report("评估中心A")
        self.r26 = make_report("评估中心B")
        self.record_26 = make_archived_record("钱老师")
        self.record_25 = make_archived_record("孙老师")

    def test_supplement_rejects_grant_from_other_report(self):
        # R-26 档案注销生成补件
        grant_26, _ = svc.issue_grant(
            self.r26, self.record_26, "评审员张工", "资料员刘工")
        svc.accept_ticket(grant_26["凭证编号"], self.r26, self.record_26)
        TeachRecordService().run_action(self.record_26, "注销档案")
        todo = svc.list_supplements(eval_id=self.r26, status="待补件")[0]

        # R-25 的有效凭证不能拿来办结 R-26 的补件
        grant_25, _ = svc.issue_grant(
            self.r25, self.record_25, "评审员张工", "资料员刘工")
        svc.accept_ticket(grant_25["凭证编号"], self.r25, self.record_25)
        done, msg = svc.complete_supplement(todo["id"], grant_25["凭证编号"])
        assert done is None
        assert "跨报告" in msg

    def test_supplement_rejects_revoked_record_grant_and_missing_ticket(self):
        grant_26, _ = svc.issue_grant(
            self.r26, self.record_26, "评审员张工", "资料员刘工")
        svc.accept_ticket(grant_26["凭证编号"], self.r26, self.record_26)
        TeachRecordService().run_action(self.record_26, "注销档案")
        todo = svc.list_supplements(eval_id=self.r26, status="待补件")[0]

        # 同报告但指向替代档案、尚未验票的新凭证：缺受理回执
        replacement = make_archived_record("替代教师")
        new_grant, _ = svc.issue_grant(
            self.r26, replacement, "评审员张工", "资料员刘工")
        done, msg = svc.complete_supplement(todo["id"], new_grant["凭证编号"])
        assert done is None
        assert "验票" in msg

        # 完成验票后可办结
        svc.accept_ticket(new_grant["凭证编号"], self.r26, replacement)
        done, msg = svc.complete_supplement(todo["id"], new_grant["凭证编号"])
        assert done is not None and done["状态"] == "已完成"

        # 幂等：重复办结被拦截
        again, again_msg = svc.complete_supplement(todo["id"], new_grant["凭证编号"])
        assert again is None
        assert "已完成" in again_msg


class TestReceiveWithoutCredentials:
    """没有凭证链路的报告保持原有接收流程。"""

    def test_plain_report_can_still_be_received(self):
        eval_id = make_report()
        diagnosis = svc.diagnose_receive(eval_id)
        assert diagnosis["可接收"] is True
        result, _ = ExternalEvalService().run_action(eval_id, "接收报告")
        assert result is not None and result["status"] == "已接收"
