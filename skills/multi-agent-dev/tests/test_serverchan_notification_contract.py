from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
REFERENCE = (ROOT / "references" / "adaptive-four-role-workflow.md").read_text(
    encoding="utf-8"
)
NOTIFICATION_DOC = (ROOT / "docs" / "serverchan-completion-notification.md").read_text(
    encoding="utf-8"
)
SCRIPT = ROOT / "scripts" / "notify_serverchan.py"


class ServerChanNotificationContractTests(unittest.TestCase):
    def test_terminal_notification_is_scoped_and_documented(self):
        for text in (SKILL, README, REFERENCE, NOTIFICATION_DOC):
            self.assertIn("ServerChan", text)
            self.assertIn("SCT_SENDKEY", text)
            self.assertIn("serverchan_sendkey.txt", text)
        self.assertIn("done", NOTIFICATION_DOC)
        self.assertIn("blocked", NOTIFICATION_DOC)
        self.assertIn("stopped", NOTIFICATION_DOC)
        self.assertIn("监测/诊断任务不发送", SKILL)
        self.assertIn("默认重试 3 次", SKILL)
        self.assertIn("才可向用户报告该终态已完成", SKILL)

    def test_notification_script_preserves_retry_and_secret_contract(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("SCT_SENDKEY", source)
        self.assertIn("Path.home() / \".codex\" / \"secrets\"", source)
        self.assertIn("--retries", source)
        self.assertIn("--retry-delay-seconds", source)
        self.assertIn("--state-file", source)
        self.assertIn("if args.state_file else {}", source)
        self.assertIn("choices=[\"done\", \"blocked\", \"stopped\"]", source)
        self.assertNotIn("print(args.sendkey)", source)

    def test_dry_run_builds_message_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project",
                    directory,
                    "--status",
                    "done",
                    "--title",
                    "Test",
                    "--message",
                    "dry run",
                    "--sendkey",
                    "TEST_ONLY",
                    "--dry-run",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertIn("Status: `done`", payload["desp"])
        self.assertIn("dry run", payload["desp"])
        self.assertNotIn("TEST_ONLY", completed.stdout)

    def test_state_is_opt_in_and_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "objective": "explicit objective",
                        "current_phase": "testing",
                        "tests_run": [{"command": "test command"}],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project",
                    directory,
                    "--state-file",
                    str(state_path),
                    "--status",
                    "stopped",
                    "--message",
                    "explicit state",
                    "--sendkey",
                    "TEST_ONLY",
                    "--dry-run",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn("explicit objective", payload["desp"])
        self.assertIn("Current phase: `testing`", payload["desp"])
        self.assertIn("test command", payload["desp"])


if __name__ == "__main__":
    unittest.main()
