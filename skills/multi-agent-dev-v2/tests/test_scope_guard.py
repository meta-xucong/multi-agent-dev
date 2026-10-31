from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "hooks"))
import scope_guard  # noqa: E402


class ScopeGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "scope.sqlite3"
        self.session = "session-one"
        self.agent = "monitor-one"
        self.cwd = str(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def report(self, status: str, *, agent: str | None = None,
               session: str | None = None, **fields) -> dict:
        payload = {"hook_event_name": "SubagentStop", "session_id": session or self.session,
                   "agent_id": agent or self.agent, "cwd": self.cwd,
                   "last_assistant_message": scope_guard.PREFIX + json.dumps({"status": status, **fields})}
        return scope_guard.handle(payload, self.db)

    def pretool(self, tool: str, command: str, *, session: str | None = None) -> dict:
        return scope_guard.handle({"hook_event_name": "PreToolUse", "session_id": session or self.session,
                                   "tool_name": tool, "cwd": self.cwd,
                                   "tool_input": {"command": command}}, self.db)

    def stop(self, active: bool = False) -> dict:
        return scope_guard.handle({"hook_event_name": "Stop", "session_id": self.session,
                                   "stop_hook_active": active}, self.db)

    def register(self) -> None:
        self.assertIn("monitor-one", self.report("REGISTER")["systemMessage"])

    def violation(self, issue: str = "issue-1", paths: list[str] | None = None) -> None:
        self.report("VIOLATION", issue_id=issue, rule="no SHA", evidence="new call to digest",
                    paths=[str(self.root / "src" / "a.py")] if paths is None else paths)

    def allow(self, tool: str, command: str, issue_ids: list[str] | None = None) -> None:
        self.report("ALLOW", issue_ids=issue_ids or ["issue-1"], tool=tool, cwd=self.cwd,
                    tool_input={"command": command})

    def test_unregistered_and_other_sessions_are_unaffected(self) -> None:
        self.assertEqual(self.pretool("Bash", "python tests.py"), {})
        self.assertFalse(self.db.exists())
        self.register()
        self.violation()
        self.assertEqual(self.pretool("Bash", "python tests.py", session="other-session"), {})

    def test_pending_blocks_bash_and_affected_patch_but_allows_other_paths(self) -> None:
        self.register()
        self.violation()
        self.assertEqual(self.pretool("Bash", "python tests.py")["hookSpecificOutput"]["permissionDecision"], "deny")
        affected = "*** Begin Patch\n*** Update File: src/a.py\n*** End Patch"
        unrelated = "*** Begin Patch\n*** Update File: src/b.py\n*** End Patch"
        self.assertEqual(self.pretool("apply_patch", affected)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.pretool("apply_patch", unrelated), {})

    def test_pathless_violation_blocks_patches(self) -> None:
        self.register()
        self.violation(paths=[])
        patch = "*** Begin Patch\n*** Update File: src/b.py\n*** End Patch"
        self.assertEqual(self.pretool("apply_patch", patch)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_exact_read_and_correction_are_one_use_until_rechecked(self) -> None:
        self.register()
        self.violation()
        read = "Get-Content src/a.py"
        self.allow("Bash", read)
        self.assertEqual(self.pretool("Bash", "Get-Content src/b.py")["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.pretool("Bash", read), {})
        self.assertEqual(self.pretool("Bash", read)["hookSpecificOutput"]["permissionDecision"], "deny")
        correction = "*** Begin Patch\n*** Update File: src/a.py\n*** End Patch"
        self.allow("apply_patch", correction)
        self.assertEqual(self.pretool("apply_patch", correction), {})
        self.assertEqual(self.pretool("apply_patch", correction)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.stop()["decision"], "block")
        self.report("RESOLVED", issue_id="issue-1")
        self.assertEqual(self.pretool("Bash", "python tests.py"), {})
        self.assertEqual(self.stop(), {})

    def test_multiple_issues_are_preserved_and_new_finding_revokes_approval(self) -> None:
        self.register()
        self.violation()
        self.allow("Bash", "read a")
        self.violation("issue-2", [str(self.root / "src" / "b.py")])
        self.assertEqual(self.pretool("Bash", "read a")["hookSpecificOutput"]["permissionDecision"], "deny")
        self.report("RESOLVED", issue_id="issue-1")
        self.assertEqual(self.pretool("Bash", "python tests.py")["hookSpecificOutput"]["permissionDecision"], "deny")
        self.report("RESOLVED", issue_id="issue-2")
        self.assertEqual(self.pretool("Bash", "python tests.py"), {})

    def test_unrelated_agent_cannot_change_binding_or_resolve_issue(self) -> None:
        self.register()
        self.violation()
        self.assertEqual(self.report("REGISTER", agent="other-agent"), {})
        self.assertEqual(self.report("REGISTER", agent="other-agent", replace=True), {})
        self.report("RESOLVED", agent="other-agent", issue_id="issue-1")
        self.assertEqual(self.pretool("Bash", "python tests.py")["hookSpecificOutput"]["permissionDecision"], "deny")
        self.report("TRANSFER", agent_id="replacement")
        self.report("REGISTER", agent="replacement", replace=True)
        self.report("RESOLVED", agent="replacement", issue_id="issue-1")
        self.assertEqual(self.stop(), {})

    def test_distinct_finding_with_same_label_is_not_lost(self) -> None:
        self.register()
        self.violation()
        response = self.report("VIOLATION", issue_id="issue-1", rule="scope",
                               evidence="different extra behavior", paths=[str(self.root / "src" / "b.py")])
        self.assertIn("issue-1-2", response["systemMessage"])
        response = self.report("VIOLATION", issue_id="issue-1", rule="scope",
                               evidence="different extra behavior", paths=[str(self.root / "src" / "b.py")])
        self.assertIn("issue-1-2", response["systemMessage"])
        self.report("RESOLVED", issue_id="issue-1")
        self.assertEqual(self.pretool("Bash", "python tests.py")["hookSpecificOutput"]["permissionDecision"], "deny")
        self.report("RESOLVED", issue_id="issue-1-2")
        self.assertEqual(self.stop(), {})

    def test_missing_cwd_is_not_replaced_by_hook_working_directory(self) -> None:
        self.register()
        self.violation()
        payload = {"hook_event_name": "PreToolUse", "session_id": self.session,
                   "tool_name": "apply_patch", "tool_input": {"command": "*** Update File: src/a.py"}}
        self.assertIn("MADV2_SCOPE_CWD_UNKNOWN", scope_guard.handle(payload, self.db)["systemMessage"])

    def test_relative_finding_path_is_rejected_instead_of_guessing_worktree(self) -> None:
        self.register()
        response = self.report("VIOLATION", issue_id="issue-1", rule="scope",
                               evidence="change in another worktree", paths=["src/a.py"])
        self.assertIn("MADV2_SCOPE_PATH_UNKNOWN", response["systemMessage"])
        self.assertEqual(response["decision"], "block")
        self.assertEqual(self.stop(), {})

    @unittest.skipUnless(os.name == "nt", "Windows drive-relative behavior")
    def test_windows_rooted_path_without_drive_is_not_registered(self) -> None:
        self.register()
        response = self.report("VIOLATION", issue_id="issue-1", rule="scope",
                               evidence="change in another worktree", paths=["/project/src/a.py"])
        self.assertIn("MADV2_SCOPE_PATH_UNKNOWN", response["systemMessage"])
        self.assertEqual(self.stop(), {})

    def test_absolute_finding_path_targets_the_correct_worktree(self) -> None:
        self.register()
        target = self.root / "other-worktree" / "src" / "a.py"
        self.violation(paths=[str(target)])
        patch = f"*** Begin Patch\n*** Update File: {target}\n*** End Patch"
        self.assertEqual(self.pretool("apply_patch", patch)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_accepted_state_changes_emit_receipts(self) -> None:
        self.register()
        response = self.report("VIOLATION", issue_id="issue-1", rule="no SHA", evidence="new digest", paths=[])
        self.assertIn("MADV2_SCOPE_VIOLATION", response["systemMessage"])
        response = self.report("ALLOW", issue_ids=["issue-1"], tool="Bash", cwd=self.cwd,
                               tool_input={"command": "read"})
        self.assertIn("MADV2_SCOPE_ALLOW", response["systemMessage"])
        response = self.report("RESOLVED", issue_id="issue-1")
        self.assertIn("MADV2_SCOPE_RESOLVED", response["systemMessage"])

    def test_unrelated_or_incomplete_marker_does_not_create_issue(self) -> None:
        self.register()
        self.report("VIOLATION", issue_id="missing-evidence", rule="scope", paths=[])
        self.assertEqual(self.stop(), {})

    def test_stop_does_not_loop_after_continuation(self) -> None:
        self.register()
        self.violation()
        self.assertEqual(self.stop()["decision"], "block")
        self.assertFalse(self.stop(active=True)["continue"])
        self.assertEqual(self.pretool("Bash", "python tests.py")["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_command_hook_reads_stdin_and_emits_registration_receipt(self) -> None:
        payload = {"hook_event_name": "SubagentStop", "session_id": self.session,
                   "agent_id": self.agent, "cwd": self.cwd,
                   "last_assistant_message": scope_guard.PREFIX + '{"status":"REGISTER"}'}
        env = {**os.environ, "MADV2_SCOPE_GUARD_DB": str(self.db)}
        proc = subprocess.run([sys.executable, "-B", str(PACKAGE / "hooks" / "scope_guard.py")],
                              input=json.dumps(payload), text=True, capture_output=True, env=env, check=True)
        self.assertIn("monitor-one", json.loads(proc.stdout)["systemMessage"])

    def test_command_hook_protocol_across_separate_processes(self) -> None:
        env = {**os.environ, "MADV2_SCOPE_GUARD_DB": str(self.db)}

        def run(payload: dict) -> dict:
            proc = subprocess.run([sys.executable, "-B", str(PACKAGE / "hooks" / "scope_guard.py")],
                                  input=json.dumps(payload), text=True, capture_output=True, env=env, check=True)
            return json.loads(proc.stdout)

        def event(status: str, **fields) -> dict:
            return {"hook_event_name": "SubagentStop", "session_id": self.session,
                    "agent_id": self.agent, "cwd": self.cwd,
                    "last_assistant_message": scope_guard.PREFIX + json.dumps({"status": status, **fields})}

        read = {"hook_event_name": "PreToolUse", "session_id": self.session,
                "tool_name": "Bash", "cwd": self.cwd, "tool_input": {"command": "read source"}}
        run(event("REGISTER"))
        run(event("VIOLATION", issue_id="issue-1", rule="no SHA", evidence="new digest call",
                  paths=[str(self.root / "src" / "a.py")]))
        self.assertEqual(run(read)["hookSpecificOutput"]["permissionDecision"], "deny")
        run(event("ALLOW", issue_ids=["issue-1"], tool="Bash", cwd=self.cwd, tool_input=read["tool_input"]))
        self.assertEqual(run(read), {})
        self.assertEqual(run(read)["hookSpecificOutput"]["permissionDecision"], "deny")
        run(event("RESOLVED", issue_id="issue-1"))
        self.assertEqual(run(read), {})


if __name__ == "__main__":
    unittest.main()
