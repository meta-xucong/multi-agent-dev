from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "hooks"))
import task_terminal_notify as notify  # noqa: E402


def marker(status: str = "done") -> str:
    return (
        '<!-- MAD_TASK_TERMINAL_V1 '
        + '{"task_id":"task-001","status":"'
        + status
        + '","title":"Task finished","short":"Review required",'
        + '"message":"Tests and audit completed."} -->'
    )


class TaskTerminalNotifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.old_dirs = (notify.ACTIVE_DIR, notify.PENDING_DIR, notify.RECEIPT_DIR)
        notify.ACTIVE_DIR = root / "active"
        notify.PENDING_DIR = root / "pending"
        notify.RECEIPT_DIR = root / "receipts"

    def tearDown(self) -> None:
        notify.ACTIVE_DIR, notify.PENDING_DIR, notify.RECEIPT_DIR = self.old_dirs
        self.temp.cleanup()

    def test_parse_hidden_terminal_marker(self) -> None:
        parsed = notify.parse_terminal_marker("final text\n" + marker("blocked"))
        self.assertEqual(parsed["task_id"], "task-001")
        self.assertEqual(parsed["status"], "blocked")

    def test_stop_without_marker_is_noop(self) -> None:
        result = notify.handle(
            {
                "hook_event_name": "Stop",
                "session_id": "session-001",
                "cwd": self.temp.name,
                "last_assistant_message": "ordinary response",
            }
        )
        self.assertEqual(result, {"continue": True})

    def test_active_task_cannot_stop_without_terminal_marker(self) -> None:
        payload = {
            "hook_event_name": "Stop",
            "session_id": "session-active",
            "cwd": self.temp.name,
            "last_assistant_message": "intermediate update",
        }
        notify.register_active_session(payload, "task-active")
        result = notify.handle(payload)
        self.assertEqual(result["decision"], "block")
        self.assertIn("MAD_TASK_TERMINAL_V1", result["reason"])

    def test_success_is_idempotent(self) -> None:
        payload = {
            "hook_event_name": "Stop",
            "session_id": "session-001",
            "cwd": self.temp.name,
            "last_assistant_message": marker(),
        }
        with patch.object(notify, "_run_notifier", return_value=(True, "ok")) as run:
            self.assertEqual(notify.handle(payload), {"continue": True})
            self.assertEqual(notify.handle(payload), {"continue": True})
        run.assert_called_once()
        self.assertEqual(len(list(notify.RECEIPT_DIR.glob("*.json"))), 1)

    def test_failure_blocks_once_then_reports_delivery_risk(self) -> None:
        payload = {
            "hook_event_name": "Stop",
            "session_id": "session-002",
            "cwd": self.temp.name,
            "last_assistant_message": marker(),
            "stop_hook_active": False,
        }
        with patch.object(notify, "_run_notifier", return_value=(False, "notifier_exit_1")):
            first = notify.handle(payload)
        self.assertEqual(first["decision"], "block")
        payload["stop_hook_active"] = True
        with patch.object(notify, "_run_notifier", return_value=(False, "notifier_exit_1")):
            second = notify.handle(payload)
        self.assertIn("systemMessage", second)
        self.assertEqual(len(list(notify.PENDING_DIR.glob("*.json"))), 1)

    def test_interrupt_uses_active_task_fallback(self) -> None:
        payload = {
            "hook_event_name": "Interrupt",
            "session_id": "session-003",
            "cwd": self.temp.name,
        }
        notify.register_active_session(payload, "task-003")
        with patch.object(notify, "_run_notifier", return_value=(True, "ok")) as run:
            result = notify.handle(payload)
        self.assertEqual(result, {"continue": True})
        run.assert_called_once()
        self.assertEqual(len(list(notify.RECEIPT_DIR.glob("*.json"))), 1)

    def test_session_end_retries_pending_terminal_marker(self) -> None:
        stop_payload = {
            "hook_event_name": "Stop",
            "session_id": "session-004",
            "cwd": self.temp.name,
            "last_assistant_message": marker(),
            "stop_hook_active": False,
        }
        with patch.object(notify, "_run_notifier", return_value=(False, "notifier_exit_1")):
            self.assertEqual(notify.handle(stop_payload)["decision"], "block")
        end_payload = {
            "hook_event_name": "SessionEnd",
            "session_id": "session-004",
            "cwd": self.temp.name,
        }
        with patch.object(notify, "_run_notifier", return_value=(True, "ok")) as run:
            self.assertEqual(notify.handle(end_payload), {"continue": True})
        run.assert_called_once()
        self.assertEqual(len(list(notify.RECEIPT_DIR.glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
