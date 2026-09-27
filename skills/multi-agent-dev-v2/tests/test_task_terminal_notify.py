from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "hooks"))
sys.path.insert(0, str(PACKAGE / "scripts"))

import notify_serverchan as notifier  # noqa: E402
import task_terminal_notify as terminal_hook  # noqa: E402


class TerminalNotificationHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "state"
        self.session = "session-test-001"
        self.task_id = "local-only-task-9"
        self.active_path = self.state / "active" / f"{hashlib.sha256(self.session.encode()).hexdigest()}.json"
        self.task_hash = hashlib.sha256(self.task_id.encode()).hexdigest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def register(self) -> None:
        self.assertTrue(terminal_hook.register_active_session(self.session, self.task_id, self.state))

    def test_pretooluse_registers_only_exact_v2_registration_command(self) -> None:
        notifier_path = terminal_hook.NOTIFIER
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "session_id": self.session,
            "cwd": str(PACKAGE.parent),
            "tool_input": {
                "command": f'python -B "{notifier_path}" --register-active --task-id "{self.task_id}"'
            },
        }
        self.assertEqual(terminal_hook.handle(payload, self.state), {})
        self.assertTrue(self.active_path.exists())
        self.assertNotIn(self.task_id, self.active_path.read_text(encoding="utf-8"))
        unrelated = {**payload, "tool_input": {"command": f'python "{notifier_path}" --status stopped'}}
        terminal_hook.handle(unrelated, self.state)
        self.assertEqual(len(list((self.state / "active").glob("*.json"))), 1)

    def test_registration_rejects_text_shell_wrapper_compound_and_wrong_script(self) -> None:
        notifier_path = terminal_hook.NOTIFIER
        valid_suffix = f'--register-active --task-id "{self.task_id}"'
        commands = (
            f'echo "python {notifier_path} {valid_suffix}"',
            f'python -c "print(\\"{notifier_path} {valid_suffix}\\")"',
            f'cmd /c python "C:\\other\\notify_serverchan.py" {valid_suffix}',
            f'python "{notifier_path}" {valid_suffix}; echo done',
            f'python "{notifier_path}" {valid_suffix} --status stopped',
        )
        for command in commands:
            with self.subTest(command=command):
                payload = {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(PACKAGE.parent),
                    "tool_input": {"command": command},
                }
                self.assertEqual(terminal_hook.handle(payload, self.state), {})
        self.assertFalse(self.active_path.exists())

    def test_noncanonical_exec_tool_name_does_not_register(self) -> None:
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "exec_command",
            "session_id": self.session,
            "tool_input": {"command": f"python notify_serverchan.py --register-active --task-id {self.task_id}"},
        }
        self.assertEqual(terminal_hook.handle(payload, self.state), {})
        self.assertFalse(self.active_path.exists())

    def test_stop_without_pending_terminal_intent_is_noop(self) -> None:
        self.register()
        with patch.object(terminal_hook, "_run_notifier") as send:
            result = terminal_hook.handle(
                {"hook_event_name": "Stop", "session_id": self.session}, self.state
            )
        self.assertEqual(result, {"continue": True})
        send.assert_not_called()
        self.assertTrue(self.active_path.exists())

    def test_interrupt_sends_stopped_fallback_and_is_idempotent(self) -> None:
        self.register()
        with patch.object(terminal_hook, "_run_notifier", return_value=(True, "ok")) as send:
            result = terminal_hook.handle(
                {"hook_event_name": "Interrupt", "session_id": self.session}, self.state
            )
            again = terminal_hook.handle(
                {"hook_event_name": "SessionEnd", "session_id": self.session}, self.state
            )
        self.assertEqual(result, {})
        self.assertEqual(again, {})
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[0]["status"], "stopped")
        self.assertFalse(self.active_path.exists())

    def test_session_end_delivery_failure_exits_as_hook_failure_without_json_output(self) -> None:
        self.register()
        payload = {"hook_event_name": "SessionEnd", "session_id": self.session}
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            patch.object(terminal_hook, "STATE_ROOT", self.state),
            patch.object(terminal_hook, "_run_notifier", return_value=(False, "delivery_failed")),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            exit_code = terminal_hook.main()
        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("open delivery risk", stderr.getvalue())

    def test_stop_retries_persisted_intent_without_exposing_task_id(self) -> None:
        self.register()
        pending = notifier._pending_path(self.state, self.task_id, "done")
        notifier._write_pending(
            pending,
            {
                "status": "done",
                "title": "Done",
                "short": "Finished",
                "message": "Review is ready.",
                "verification": "17 tests passed",
                "project": ".",
            },
        )
        with patch.object(terminal_hook, "_run_notifier", return_value=(True, "ok")) as send:
            result = terminal_hook.handle(
                {"hook_event_name": "Stop", "session_id": self.session}, self.state
            )
        self.assertEqual(result, {"continue": True})
        item = send.call_args.args[0]
        self.assertEqual(item["status"], "done")
        self.assertEqual(item["verification"], "17 tests passed")
        self.assertNotIn(self.task_id, repr(item))
        self.assertFalse(pending.exists())
        self.assertFalse(self.active_path.exists())

    def test_stop_failure_blocks_once_then_surfaces_delivery_risk(self) -> None:
        self.register()
        pending = notifier._pending_path(self.state, self.task_id, "blocked")
        notifier._write_pending(
            pending,
            {
                "status": "blocked",
                "title": "Blocked",
                "short": "Review needed",
                "message": "Waiting for a decision.",
                "verification": "",
                "project": ".",
            },
        )
        with patch.object(terminal_hook, "_run_notifier", return_value=(False, "delivery_failed")):
            first = terminal_hook.handle(
                {"hook_event_name": "Stop", "session_id": self.session}, self.state
            )
            second = terminal_hook.handle(
                {"hook_event_name": "Stop", "session_id": self.session, "stop_hook_active": True}, self.state
            )
        self.assertEqual(first.get("decision"), "block")
        self.assertIn("delivery_failed", first["reason"])
        self.assertEqual(second.get("continue"), True)
        self.assertIn("open delivery risk", second["systemMessage"])
        self.assertTrue(pending.exists())

    def test_direct_success_receipt_prevents_interrupt_duplicate(self) -> None:
        self.register()
        receipt = notifier._receipt_path(self.state, self.task_id, "blocked")
        notifier._write_receipt(receipt, {"status": "blocked", "sent_at": 1})
        with patch.object(terminal_hook, "_run_notifier") as send:
            result = terminal_hook.handle(
                {"hook_event_name": "Interrupt", "session_id": self.session}, self.state
            )
        self.assertEqual(result, {})
        send.assert_not_called()
        self.assertFalse(self.active_path.exists())


if __name__ == "__main__":
    unittest.main()
