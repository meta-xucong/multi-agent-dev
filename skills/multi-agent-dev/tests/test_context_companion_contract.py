from __future__ import annotations

import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
DOC = (SKILL_ROOT / "docs" / "context-lean-companion-development.md").read_text(encoding="utf-8")
README = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
ROOT_README = (SKILL_ROOT.parent.parent / "README.md").read_text(encoding="utf-8")


class ContextCompanionContractTests(unittest.TestCase):
    def test_main_skill_routes_context_mode_conditionally(self) -> None:
        self.assertIn("CONTEXT_MODE", SKILL)
        self.assertIn("NOT_NEEDED", SKILL)
        self.assertIn("ARMED", SKILL)
        self.assertIn("ACTIVE", SKILL)
        self.assertIn("BLOCKED", SKILL)
        self.assertIn("context-lean 条件伴随能力开发文档", SKILL)
        self.assertIn("context-lean/SKILL.md", SKILL)
        self.assertIn("主控自动路由到上下文伴随流程", SKILL)

    def test_companion_contract_has_safe_compaction_and_recovery_gates(self) -> None:
        self.assertRegex(DOC, r"当前写入、测试和审计动作已到安全边界")
        self.assertRegex(DOC, r"恢复记录缺失、过期、与工作区不一致")
        self.assertIn("ORCH_STALE_SUSPECTED", DOC)
        self.assertIn("ORCH_STOP_REQUESTED", DOC)
        self.assertIn("ORCH_BLOCKED_NEEDS_USER", DOC)
        self.assertIn("不能凭压缩摘要直接继续写代码", DOC)

    def test_platform_fallback_and_recovery_order_are_explicit(self) -> None:
        self.assertIn("平台支持按 Skill 路由时", DOC)
        self.assertIn("不支持递归加载时，使用本文第 3～5 节的最小规则", DOC)
        self.assertLess(DOC.index("## 4. 压缩门禁"), DOC.index("## 5. 恢复门禁"))
        self.assertLess(DOC.index("先保存状态再压缩"), DOC.index("先完成恢复门禁，再允许写入"))

    def test_exit_matrix_covers_contract_paths_without_claiming_runtime_proof(self) -> None:
        for scenario in ("清晰小任务", "长任务/大读取", "需要压缩", "压缩后恢复", "Hook/命令不可用", "写入者停滞"):
            with self.subTest(scenario=scenario):
                self.assertIn(scenario, DOC)
        self.assertIn("契约测试覆盖“不启用、启用、不可用、恢复和停滞优先级”的规则存在性", DOC)
        self.assertIn("真实平台的递归 Skill、压缩命令和 Hook 生命周期仍需在目标环境单独验证", DOC)

    def test_companion_does_not_turn_platform_details_into_universal_rules(self) -> None:
        self.assertIn("不能把某个平台的上下文百分比、耗时、缓存行为或 Hook 输入输出推断为所有平台的事实", DOC)
        self.assertIn("不把 `context-lean` 的平台专属命令、Hook、阈值和性能数据变成通用硬规则", DOC)
        self.assertNotRegex(SKILL, r"90%")
        self.assertNotRegex(SKILL, r"208 秒")

    def test_state_record_remains_single_source_and_audit_is_preserved(self) -> None:
        for required in ("契约修订", "唯一写入者", "审计状态", "下一步", "版本标识"):
            with self.subTest(required=required):
                self.assertIn(required, DOC)
        self.assertIn("不强制另建第二套台账", DOC)
        self.assertIn("不得改变开发范围、公共契约、模型路由", SKILL)

    def test_readme_explains_single_skill_default_and_conditional_companion(self) -> None:
        self.assertIn("不需要每次手动同时调用两个 Skill", README)
        self.assertIn("按需伴随 `context-lean`", ROOT_README)
        self.assertIn("保持独立目录", ROOT_README)


if __name__ == "__main__":
    unittest.main()
