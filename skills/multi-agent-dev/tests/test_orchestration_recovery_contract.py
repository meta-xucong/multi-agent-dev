from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
REFERENCE = (ROOT / "references" / "adaptive-four-role-workflow.md").read_text(
    encoding="utf-8"
)
RECOVERY = (ROOT / "docs" / "stalled-orchestration-recovery-development.md").read_text(
    encoding="utf-8"
)
README = (ROOT / "README.md").read_text(encoding="utf-8")


class OrchestrationRecoveryContractTests(unittest.TestCase):
    def test_recovery_states_are_defined_and_referenced(self):
        for state in (
            "ORCH_HEALTHY",
            "ORCH_STALE_SUSPECTED",
            "ORCH_STATE_CONFLICT",
            "ORCH_STOP_REQUESTED",
            "ORCH_BLOCKED_NEEDS_USER",
        ):
            self.assertIn(state, RECOVERY)
        self.assertIn("ORCH_STALE_SUSPECTED", SKILL)
        self.assertIn("ORCH_STATE_CONFLICT", SKILL)
        self.assertIn("ORCH_STALE_SUSPECTED", REFERENCE)
        self.assertIn("ORCH_STATE_CONFLICT", REFERENCE)
        self.assertIn("ORCH_BLOCKED_NEEDS_USER", README)

    def test_idle_and_not_loaded_are_not_standalone_stop_evidence(self):
        caveat = "idle/notLoaded` 只是 UI/加载状态"
        self.assertIn(caveat, SKILL)
        self.assertIn(caveat, REFERENCE)
        self.assertIn("没有 `inProgress` 回合和进行中写入", RECOVERY)
        self.assertIn("读取失败或空结果直接进入 `ORCH_BLOCKED_NEEDS_USER`", SKILL)
        self.assertIn("读取失败、空结果或状态无法证明都直接进入 `ORCH_BLOCKED_NEEDS_USER`", RECOVERY)

    def test_stop_requested_requires_platform_acceptance(self):
        self.assertIn("已被平台接受/排队", RECOVERY)
        self.assertIn("未被接受时直接进入 `ORCH_BLOCKED_NEEDS_USER`", RECOVERY)
        self.assertIn("才记录 `ORCH_STOP_REQUESTED`", SKILL)
        self.assertIn("才进入 `ORCH_STOP_REQUESTED`", REFERENCE)

    def test_recovery_does_not_define_a_fixed_timeout(self):
        self.assertNotIn("30–60 秒", RECOVERY)
        self.assertIn("等待时长本身不是停止证据", RECOVERY)

    def test_monitoring_is_explicit_and_delivery_is_silent(self):
        for text in (SKILL, REFERENCE, RECOVERY, README):
            self.assertIn("MONITOR_MODE=DELIVERY_SILENT", text)
            self.assertIn("MONITOR_MODE=OBSERVE", text)
        self.assertIn("STATUS_REPORT_V1", SKILL)
        self.assertIn("STATUS_REPORT_V1", REFERENCE)
        self.assertIn("STATUS_REPORT_V1", RECOVERY)
        self.assertIn("不发送周期性心跳", SKILL)
        self.assertIn("不发送周期性心跳", README)

    def test_monitoring_requires_observable_activity_evidence(self):
        for text in (SKILL, REFERENCE, RECOVERY, README):
            self.assertIn("工具事件", text)
            self.assertIn("文件变化", text)
            self.assertIn("测试结果", text)
        self.assertIn("expected_until", SKILL)
        self.assertIn("last_progress_at", RECOVERY)

    def test_state_conflict_blocks_write_and_release(self):
        self.assertIn("来源冲突时进入 `ORCH_STATE_CONFLICT`", RECOVERY)
        self.assertIn("冲突未收敛前不得放行、替代写入", SKILL)
        self.assertIn("只允许一次无写入复核", RECOVERY)

    def test_reassignment_stays_blocked_until_old_writer_is_stopped(self):
        for text in (SKILL, REFERENCE):
            self.assertTrue("不得 fork" in text or "禁止 fork" in text)
        self.assertIn("阻止替代写入者、fork", RECOVERY)
        self.assertIn("只有主回合和旧写入者都被确认终止", RECOVERY)

    def test_close_failure_contract_oracle(self):
        def classify(status, read_ok=True, in_progress=False, writing=False):
            if not read_ok or in_progress or writing:
                return "BLOCKED"
            if status in {"inactive", "completed", "failed", "idle", "notLoaded"}:
                return "DUPLICATE_CLOSE"
            if status == "active":
                return "STOP_ONCE"
            return "BLOCKED"

        self.assertEqual(classify("completed"), "DUPLICATE_CLOSE")
        self.assertEqual(classify("notLoaded"), "DUPLICATE_CLOSE")
        self.assertEqual(classify("notLoaded", read_ok=False), "BLOCKED")
        self.assertEqual(classify("completed", in_progress=True), "BLOCKED")
        self.assertEqual(classify("completed", writing=True), "BLOCKED")
        self.assertEqual(classify("active"), "STOP_ONCE")
        self.assertEqual(classify("unknown"), "BLOCKED")

    def test_stop_request_acceptance_contract_oracle(self):
        def classify(accepted, rechecked, still_active):
            if not accepted:
                return "ORCH_BLOCKED_NEEDS_USER"
            if not rechecked:
                return "ORCH_STOP_REQUESTED"
            if still_active:
                return "ORCH_BLOCKED_NEEDS_USER"
            return "STOP_CONFIRMED"

        self.assertEqual(classify(False, False, False), "ORCH_BLOCKED_NEEDS_USER")
        self.assertEqual(classify(True, False, True), "ORCH_STOP_REQUESTED")
        self.assertEqual(classify(True, True, True), "ORCH_BLOCKED_NEEDS_USER")
        self.assertEqual(classify(True, True, False), "STOP_CONFIRMED")
        self.assertIn("已排队但尚未中断", RECOVERY)
        self.assertIn("复核仍活动才转为 `ORCH_BLOCKED_NEEDS_USER`", RECOVERY)


if __name__ == "__main__":
    unittest.main()
