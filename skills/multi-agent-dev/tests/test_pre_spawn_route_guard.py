from __future__ import annotations

import json
import io
import subprocess
import sys
import unittest
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
HOOK = SKILL_ROOT / "hooks" / "pre_spawn_route_guard.py"
sys.path.insert(0, str(HOOK.parent))

import pre_spawn_route_guard as guard  # noqa: E402


def marker(
    role: str = "execute",
    gate: str = "ESCALATE_REQUIRED",
    stage: str = "CONTRACT_FROZEN",
    *,
    task_id: str = "task-001",
    contract_rev: str = "v1.3.1-route-guard",
) -> str:
    body = {
        "role": role,
        "complexity_gate": gate,
        "stage": stage,
        "task_id": task_id,
        "contract_rev": contract_rev,
    }
    return "MAD_ROUTE_V1 " + json.dumps(body, separators=(",", ":"))


def payload(
    *,
    tool_name: str = "spawn_agent",
    tool_input: dict[str, object] | None = None,
    tool_use_id: object = "toolu-001",
) -> dict[str, object]:
    return {
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "tool_input": tool_input if tool_input is not None else {"message": marker()},
    }


class RouteGuardPureTests(unittest.TestCase):
    def test_unmarked_spawn_is_exact_passthrough(self) -> None:
        original = payload(tool_input={"message": "ordinary task", "model": "custom", "extra": {"a": 1}})
        action, output, exit_code = guard.guard_payload(deepcopy(original))
        self.assertEqual((action, output, exit_code), ("passthrough", None, 0))
        self.assertEqual(original["tool_input"], {"message": "ordinary task", "model": "custom", "extra": {"a": 1}})

    def test_empty_message_is_passthrough(self) -> None:
        action, output, exit_code = guard.guard_payload(payload(tool_input={"message": "\n  \n"}))
        self.assertEqual((action, output, exit_code), ("passthrough", None, 0))

    def test_three_role_route_classes(self) -> None:
        cases = [
            ("think", "ESCALATE_REQUIRED", "PRE_CONTRACT", "gpt-5.6-sol", "max"),
            ("execute", "SIMPLE_PROVEN", "CONTRACT_FROZEN", "gpt-5.6-luna", "high"),
            ("execute", "ESCALATE_REQUIRED", "CONTRACT_FROZEN", "gpt-5.6-luna", "max"),
            ("audit", "SIMPLE_PROVEN", "VERSION_FROZEN", "gpt-5.6-luna", "high"),
            ("audit", "ESCALATE_REQUIRED", "VERSION_FROZEN", "gpt-5.6-luna", "max"),
        ]
        for role, gate, stage, expected_model, expected_effort in cases:
            with self.subTest(role=role, gate=gate):
                action, output, exit_code = guard.guard_payload(
                    payload(tool_input={"message": marker(role, gate, stage)})
                )
                self.assertEqual(action, "allow")
                self.assertEqual(exit_code, 0)
                assert output is not None
                updated = output["hookSpecificOutput"]["updatedInput"]
                self.assertEqual(updated["model"], expected_model)
                self.assertEqual(updated["reasoning_effort"], expected_effort)
                self.assertIn("MAD_ROUTE_RECEIPT", output["hookSpecificOutput"]["additionalContext"])

    def test_missing_wrong_and_xhigh_route_values_are_replaced(self) -> None:
        original = {
            "message": marker("execute", "SIMPLE_PROVEN", "CONTRACT_FROZEN") + "\nsecret task details",
            "model": "wrong-model",
            "reasoning_effort": "xhigh",
            "other": "preserve",
        }
        action, output, exit_code = guard.guard_payload(payload(tool_input=original))
        self.assertEqual((action, exit_code), ("allow", 0))
        assert output is not None
        updated = output["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "gpt-5.6-luna")
        self.assertEqual(updated["reasoning_effort"], "high")
        self.assertEqual(updated["other"], "preserve")
        receipt = output["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("secret task details", receipt)
        self.assertIn('"requested_model":"other"', receipt)
        self.assertIn('"requested_reasoning_effort":"xhigh"', receipt)
        self.assertIn('"enforced_model":"gpt-5.6-luna"', receipt)
        self.assertIn('"enforced_reasoning_effort":"high"', receipt)
        self.assertIn('"corrected":true', receipt)

    def test_correct_route_is_deterministic_and_idempotent(self) -> None:
        original = {
            "message": marker("execute", "ESCALATE_REQUIRED", "CONTRACT_FROZEN"),
            "model": "gpt-5.6-luna",
            "reasoning_effort": "max",
            "task_name": "madv1_execute_escalate_route_guard",
            "fork_turns": "none",
            "agent_type": "worker",
        }
        first = guard.guard_payload(payload(tool_input=original))
        second = guard.guard_payload(payload(tool_input=first[1]["hookSpecificOutput"]["updatedInput"]))  # type: ignore[index]
        self.assertEqual(first, second)
        assert first[1] is not None
        self.assertIn('"corrected":false', first[1]["hookSpecificOutput"]["additionalContext"])

    def test_all_supported_tool_names_share_the_same_guard(self) -> None:
        for tool_name in ("Agent", "spawn_agent", "multi_agent_v1__spawn_agent"):
            with self.subTest(tool_name=tool_name):
                action, output, exit_code = guard.guard_payload(payload(tool_name=tool_name))
                self.assertEqual((action, exit_code), ("allow", 0))
                assert output is not None
                self.assertEqual(output["hookSpecificOutput"]["updatedInput"]["reasoning_effort"], "max")

    def test_marker_json_and_field_errors_are_denied(self) -> None:
        messages = [
            "MAD_ROUTE_V1 not-json",
            "MAD_ROUTE_V1 {}",
            "MAD_ROUTE_V1 {\"role\":\"execute\",\"complexity_gate\":\"ESCALATE_REQUIRED\",\"stage\":\"CONTRACT_FROZEN\",\"task_id\":\"t\"}",
            marker("execute", "SIMPLE_PROVEN", "PRE_CONTRACT"),
            "MAD_ROUTE_V1 {\"role\":[],\"complexity_gate\":\"ESCALATE_REQUIRED\",\"stage\":\"CONTRACT_FROZEN\",\"task_id\":\"t\",\"contract_rev\":\"v1\"}",
        ]
        for message in messages:
            with self.subTest(message=message):
                action, output, exit_code = guard.guard_payload(payload(tool_input={"message": message}))
                self.assertEqual((action, exit_code), ("deny", 0))
                assert output is not None
                specific = output["hookSpecificOutput"]
                self.assertEqual(specific["permissionDecision"], "deny")
                self.assertNotIn(message, json.dumps(output))

    def test_agent_type_is_builtin_only_and_cannot_override_route(self) -> None:
        for agent_type in ("worker", "explorer", "default"):
            with self.subTest(agent_type=agent_type):
                action, output, exit_code = guard.guard_payload(
                    payload(tool_input={"message": marker(), "agent_type": agent_type, "model": "bad"})
                )
                self.assertEqual((action, exit_code), ("allow", 0))
                assert output is not None
                self.assertEqual(output["hookSpecificOutput"]["updatedInput"]["model"], "gpt-5.6-luna")
        action, output, exit_code = guard.guard_payload(
            payload(tool_input={"message": marker(), "agent_type": "custom", "model": "bad"})
        )
        self.assertEqual((action, exit_code), ("deny", 0))
        assert output is not None
        self.assertIn("MAD_ROUTE_AGENT_TYPE_UNSUPPORTED", json.dumps(output))

    def test_task_name_and_fork_compatibility(self) -> None:
        action, output, exit_code = guard.guard_payload(
            payload(
                tool_input={
                    "message": marker(),
                    "task_name": "madv1_execute_escalate_render_scene",
                    "agent_type": "default",
                }
            )
        )
        self.assertEqual((action, exit_code), ("allow", 0))
        assert output is not None
        updated = output["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["task_name"], "madv1_execute_escalate_render_scene")
        self.assertEqual(updated["fork_turns"], "none")

        for tool_input in (
            {"message": marker(), "task_name": "x", "fork_turns": "all"},
            {"message": marker(), "fork_turns": "all"},
            {"message": marker(), "fork_context": True},
            {"message": marker(), "fork_context": "true"},
            {"message": marker(), "fork_turns": 0},
            {"message": marker(), "fork_turns": "3"},
            {"message": marker(), "fork_turns": "none", "fork_context": False},
            {"message": marker(), "fork_turns": "all", "fork_context": False},
        ):
            with self.subTest(tool_input=tool_input):
                action, output, exit_code = guard.guard_payload(payload(tool_input=tool_input))
                self.assertEqual((action, exit_code), ("deny", 0))
                assert output is not None
                self.assertIn("MAD_ROUTE_ERROR", json.dumps(output))

        action, output, exit_code = guard.guard_payload(payload(tool_input={"message": marker(), "fork_context": False}))
        self.assertEqual((action, exit_code), ("allow", 0))
        assert output is not None
        self.assertNotIn("task_name", output["hookSpecificOutput"]["updatedInput"])

    def test_receipt_is_declassified(self) -> None:
        secret = "do-not-print-this-whole-message"
        tool_input = {"message": marker() + "\n" + secret, "prompt": secret}
        action, output, exit_code = guard.guard_payload(payload(tool_input=tool_input))
        self.assertEqual((action, exit_code), ("allow", 0))
        assert output is not None
        receipt = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("MAD_ROUTE_RECEIPT", receipt)
        self.assertNotIn(secret, receipt)
        self.assertNotIn("prompt", receipt)
        self.assertIn('"tool_use_id":"toolu-001"', receipt)

    def test_requested_classification_covers_omitted_and_invalid_type(self) -> None:
        action, output, exit_code = guard.guard_payload(
            payload(tool_input={"message": marker(), "model": None, "reasoning_effort": 3})
        )
        self.assertEqual((action, exit_code), ("allow", 0))
        assert output is not None
        receipt = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn('"requested_model":"invalid_type"', receipt)
        self.assertIn('"requested_reasoning_effort":"invalid_type"', receipt)
        self.assertIn('"corrected":true', receipt)

        action, output, exit_code = guard.guard_payload(payload(tool_input={"message": marker()}))
        self.assertEqual((action, exit_code), ("allow", 0))
        assert output is not None
        receipt = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn('"requested_model":"omitted"', receipt)
        self.assertIn('"requested_reasoning_effort":"omitted"', receipt)

    def test_tool_use_id_is_required_and_safe_for_marked_calls(self) -> None:
        for tool_use_id in (None, "", "/path", "bad id", "bad\nvalue", "x" * 129, 7):
            with self.subTest(tool_use_id=repr(tool_use_id)):
                action, output, exit_code = guard.guard_payload(
                    payload(tool_input={"message": marker()}, tool_use_id=tool_use_id)
                )
                self.assertEqual((action, exit_code), ("deny", 0))
                assert output is not None
                self.assertIn("MAD_ROUTE_TOOL_USE_ID_INVALID", json.dumps(output))

    def test_task_name_must_match_marker_and_madv1_requires_marker(self) -> None:
        for task_name in (
            "madv1_audit_escalate_name",
            "madv1_execute_simple_name",
            "madv1_execute_escalate_bad name",
            "madv1_execute_escalate_",
        ):
            with self.subTest(task_name=task_name):
                action, output, exit_code = guard.guard_payload(
                    payload(tool_input={"message": marker(), "task_name": task_name})
                )
                self.assertEqual((action, exit_code), ("deny", 0))
                assert output is not None

        action, output, exit_code = guard.guard_payload(
            payload(tool_input={"message": "ordinary", "task_name": "madv1_execute_escalate_name"})
        )
        self.assertEqual((action, exit_code), ("deny", 0))
        assert output is not None
        self.assertIn("MAD_ROUTE_MARKER_INVALID", json.dumps(output))

        action, output, exit_code = guard.guard_payload(
            payload(tool_input={"message": "ordinary", "task_name": "ordinary_task"})
        )
        self.assertEqual((action, output, exit_code), ("passthrough", None, 0))

    def test_unknown_marker_prefix_and_message_types_are_scoped(self) -> None:
        ordinary_inputs = (
            {"message": "MAD_ROUTE_V2 {\"role\":\"execute\"}", "task_name": "ordinary"},
            {"message": "MAD_ROUTE_V1X {\"role\":\"execute\"}", "task_name": "ordinary"},
            {"message": None, "task_name": "ordinary"},
            {"task_name": "ordinary"},
        )
        for tool_input in ordinary_inputs:
            with self.subTest(tool_input=tool_input):
                self.assertEqual(guard.guard_payload(payload(tool_input=tool_input)), ("passthrough", None, 0))

        for tool_input in (
            {"message": "MAD_ROUTE_V1X {\"role\":\"execute\"}", "task_name": "madv1_execute_escalate_name"},
            {"message": None, "task_name": "madv1_execute_escalate_name"},
            {"task_name": "madv1_execute_escalate_name"},
        ):
            with self.subTest(tool_input=tool_input):
                action, output, exit_code = guard.guard_payload(payload(tool_input=tool_input))
                self.assertEqual((action, exit_code), ("deny", 0))
                assert output is not None

    def test_contract_and_task_id_are_exact_safe_values(self) -> None:
        for contract_rev in ("v1.3-route-guard", "v1.3.1-route-guard ", "v1.3.1-route-guard/next"):
            with self.subTest(contract_rev=contract_rev):
                action, output, exit_code = guard.guard_payload(
                    payload(tool_input={"message": marker(contract_rev=contract_rev)})
                )
                self.assertEqual((action, exit_code), ("deny", 0))
                assert output is not None
        for task_id in ("../task", "bad id", "bad\nvalue", "x" * 129, ""):
            with self.subTest(task_id=repr(task_id)):
                action, output, exit_code = guard.guard_payload(
                    payload(tool_input={"message": marker(task_id=task_id)})
                )
                self.assertEqual((action, exit_code), ("deny", 0))
                assert output is not None

    def test_internal_guard_failure_is_stderr_only(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(guard, "guard_payload", side_effect=RuntimeError("secret path")):
            with patch.object(guard.sys, "stdin", io.StringIO("{}")):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = guard.main()
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "MAD_ROUTE_ERROR MAD_ROUTE_GUARD_FAILURE\n")


class RouteGuardCliTests(unittest.TestCase):
    def run_cli(self, raw: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(HOOK)],
            input=raw,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_unmarked_cli_has_empty_stdout(self) -> None:
        result = self.run_cli(json.dumps(payload(tool_input={"message": "ordinary"})))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_non_target_cli_has_empty_stdout(self) -> None:
        result = self.run_cli(json.dumps(payload(tool_name="unrelated_tool", tool_input={"message": marker()})))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_invalid_stdin_fail_closes_without_echo(self) -> None:
        raw = "not json with a secret"
        result = self.run_cli(raw)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "MAD_ROUTE_ERROR MAD_ROUTE_INPUT_INVALID\n")

    def test_target_missing_tool_input_fail_closes(self) -> None:
        result = self.run_cli(json.dumps({"tool_name": "spawn_agent"}))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "MAD_ROUTE_ERROR MAD_ROUTE_INPUT_INVALID\n")

    def test_valid_cli_output_is_json_and_updates_input(self) -> None:
        result = self.run_cli(json.dumps(payload(tool_input={"message": marker(), "reasoning_effort": "xhigh"})))
        self.assertEqual(result.returncode, 0)
        decoded = json.loads(result.stdout)
        specific = decoded["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "allow")
        self.assertEqual(specific["updatedInput"]["model"], "gpt-5.6-luna")
        self.assertEqual(specific["updatedInput"]["reasoning_effort"], "max")
        self.assertIn("MAD_ROUTE_RECEIPT", specific["additionalContext"])
        self.assertNotIn("permissionDecisionReason", specific)

    def test_marked_cli_without_tool_use_id_is_denied(self) -> None:
        value = payload(tool_input={"message": marker()}, tool_use_id=None)
        result = self.run_cli(json.dumps(value))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        decoded = json.loads(result.stdout)
        self.assertEqual(decoded["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("MAD_ROUTE_TOOL_USE_ID_INVALID", result.stdout)


if __name__ == "__main__":
    unittest.main()
