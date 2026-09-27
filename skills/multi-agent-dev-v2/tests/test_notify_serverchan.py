from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import notify_serverchan as notifier  # noqa: E402


class NotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = notifier.main(["--state-dir", str(self.state), *args])
        return result, stdout.getvalue(), stderr.getvalue()

    def test_done_requires_verification_and_does_not_send(self) -> None:
        with patch.object(notifier, "send_notification") as send:
            code, _, stderr = self.invoke("--task-id", "task-1", "--status", "done")
        self.assertEqual(code, 2)
        self.assertIn("done_requires_verification", stderr)
        send.assert_not_called()

    def test_dry_run_needs_no_secret_or_network_and_avoids_absolute_project_path(self) -> None:
        with patch.object(notifier, "load_sendkey", side_effect=AssertionError("must not read secret")), patch.object(
            notifier, "send_notification", side_effect=AssertionError("must not send")
        ):
            code, stdout, _ = self.invoke(
                "--task-id", "task-2", "--status", "done", "--verification", "tests passed",
                "--project", str(Path(self.temp.name) / "demo-project"), "--dry-run",
            )
        self.assertEqual(code, 0)
        message = json.loads(stdout)["desp"]
        self.assertIn("demo-project", message)
        self.assertNotIn(self.temp.name, message)

    def test_retries_then_writes_receipt_and_suppresses_duplicate(self) -> None:
        with patch.object(notifier, "load_sendkey", return_value="not-a-real-secret"), patch.object(
            notifier, "send_notification", side_effect=[False, True]
        ) as send, patch.object(notifier.time, "sleep"):
            code, stdout, _ = self.invoke(
                "--task-id", "task-3", "--status", "blocked", "--retries", "2", "--retry-delay-seconds", "0"
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["attempts"], 2)
        self.assertEqual(send.call_count, 2)
        with patch.object(notifier, "send_notification") as duplicate_send:
            code, stdout, _ = self.invoke("--task-id", "task-3", "--status", "blocked")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout)["already_sent"])
        duplicate_send.assert_not_called()
        receipt = notifier._receipt_path(self.state, "task-3", "blocked")
        self.assertNotIn("task-3", receipt.read_text(encoding="utf-8"))

    def test_task_id_is_optional_local_only_and_never_sent(self) -> None:
        with patch.object(notifier, "load_sendkey", return_value="not-a-real-secret"), patch.object(
            notifier, "send_notification", return_value=True
        ) as send:
            code, _, _ = self.invoke(
                "--status", "stopped", "--message", "Task ended without a routed agent ID."
            )
        self.assertEqual(code, 0)
        self.assertNotIn("task_id", send.call_args.args[3])
        self.assertFalse((self.state / "receipts").exists())

    def test_outbound_message_and_receipt_do_not_disclose_task_id(self) -> None:
        secret_local_id = "local-only-task-7"
        with patch.object(notifier, "load_sendkey", return_value="not-a-real-secret"), patch.object(
            notifier, "send_notification", return_value=True
        ) as send:
            code, _, _ = self.invoke(
                "--task-id", secret_local_id, "--status", "blocked", "--message", "Needs user review."
            )
        self.assertEqual(code, 0)
        outbound = "\n".join(str(value) for value in send.call_args.args)
        self.assertNotIn(secret_local_id, outbound)
        receipt = notifier._receipt_path(self.state, secret_local_id, "blocked")
        self.assertNotIn(secret_local_id, receipt.read_text(encoding="utf-8"))

    def test_failed_delivery_does_not_write_receipt_or_echo_secret(self) -> None:
        with patch.object(notifier, "load_sendkey", return_value="must-never-appear"), patch.object(
            notifier, "send_notification", return_value=False
        ), patch.object(notifier.time, "sleep"):
            code, _, stderr = self.invoke(
                "--task-id", "task-4", "--status", "stopped", "--retries", "1"
            )
        self.assertEqual(code, 1)
        self.assertNotIn("must-never-appear", stderr)
        receipt = notifier._receipt_path(self.state, "task-4", "stopped")
        self.assertFalse(receipt.exists())

    def test_rejects_unsafe_task_id(self) -> None:
        code, _, stderr = self.invoke("--task-id", "../bad", "--status", "stopped")
        self.assertEqual(code, 2)
        self.assertIn("invalid_task_id", stderr)

    def test_register_active_is_a_local_hook_request_and_needs_no_secret(self) -> None:
        with patch.object(notifier, "load_sendkey", side_effect=AssertionError("must not read secret")):
            code, stdout, _ = self.invoke("--task-id", "task-5", "--register-active")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout)["registration_requested"])
        self.assertFalse(self.state.exists())

    def test_missing_sendkey_keeps_local_pending_intent_for_stop_retry(self) -> None:
        with patch.object(notifier, "load_sendkey", return_value=""):
            code, _, stderr = self.invoke("--task-id", "task-6", "--status", "blocked")
        self.assertEqual(code, 2)
        self.assertIn("missing_sendkey", stderr)
        pending = notifier._pending_path(self.state, "task-6", "blocked")
        self.assertTrue(pending.exists())
        self.assertNotIn("task-6", pending.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
