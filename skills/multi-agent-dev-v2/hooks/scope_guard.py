#!/usr/bin/env python3
"""Optional Codex scope hook; effective only when installed and trusted."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


PREFIX = "MADV2_SCOPE_V1 "
STATE_PATH = Path(os.environ.get("MADV2_SCOPE_GUARD_DB") or
                  Path.home() / ".codex" / "state" / "multi-agent-dev-v2" / "scope-guard.sqlite3")
PATCH_HEADERS = ("*** Add File: ", "*** Update File: ", "*** Delete File: ", "*** Move to: ")


def _record(message: object) -> dict | None:
    if not isinstance(message, str) or not message.startswith(PREFIX):
        return None
    try:
        record = json.loads(message.splitlines()[0][len(PREFIX):])
    except (ValueError, IndexError):
        return None
    return record if isinstance(record, dict) else None


def _normalized_path(path: str, cwd: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.join(cwd, path)))


def _patch_paths(command: object, cwd: str) -> list[str]:
    if not isinstance(command, str):
        return []
    return [
        _normalized_path(line[len(header):], cwd)
        for line in command.splitlines()
        for header in PATCH_HEADERS
        if line.startswith(header) and line[len(header):]
    ]


def _touches_issue(command: object, cwd: str, issues: list[dict]) -> bool:
    paths = _patch_paths(command, cwd)
    if not paths or any(not issue["paths"] for issue in issues):
        return True
    for changed in paths:
        for issue in issues:
            for affected in issue["paths"]:
                affected = _normalized_path(affected, cwd)
                try:
                    if os.path.commonpath((changed, affected)) == affected:
                        return True
                except ValueError:
                    continue
    return False


def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                    "permissionDecision": "deny",
                                    "permissionDecisionReason": reason}}


def handle(payload: dict, state_path: Path = STATE_PATH) -> dict:
    """Handle one documented Codex Hook event using session-scoped state."""
    event = payload.get("hook_event_name")
    session = payload.get("session_id")
    if not isinstance(session, str) or not session:
        return {}
    record = _record(payload.get("last_assistant_message")) if event == "SubagentStop" else None
    if (event == "SubagentStop" and record is None
            and isinstance(payload.get("last_assistant_message"), str)
            and payload["last_assistant_message"].startswith(PREFIX)):
        return {"systemMessage": "MADV2_SCOPE_PROTOCOL_ERROR: Hook state was not updated."}
    is_register = record is not None and record.get("status") == "REGISTER"
    if not state_path.exists() and not is_register:
        return {}
    if is_register:
        state_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(state_path, timeout=2)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS sessions "
                   "(session_id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, "
                   "issues TEXT NOT NULL, approval TEXT, transfer_to TEXT)")
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT monitor_id, issues, approval, transfer_to FROM sessions WHERE session_id = ?",
                         (session,)).fetchone()
        monitor = row[0] if row else None
        issues = json.loads(row[1]) if row else []
        approval = json.loads(row[2]) if row and row[2] else None
        transfer_to = row[3] if row else None

        if event == "SubagentStop" and record:
            agent = payload.get("agent_id")
            if not isinstance(agent, str) or not agent:
                return {}
            status = record.get("status")
            if status == "REGISTER":
                if monitor and monitor != agent:
                    if record.get("replace") is not True or (issues and transfer_to != agent):
                        return {}
                db.execute("INSERT INTO sessions VALUES (?, ?, ?, NULL, NULL) "
                           "ON CONFLICT(session_id) DO UPDATE SET monitor_id=excluded.monitor_id, "
                           "approval=NULL, transfer_to=NULL",
                           (session, agent, json.dumps(issues, ensure_ascii=False)))
                return {"systemMessage": f"MADV2_SCOPE_REGISTERED session={session} agent={agent}"}
            if agent != monitor:
                return {}

            issue_id = record.get("issue_id")
            notices = []
            if status == "VIOLATION":
                paths = record.get("paths")
                if (not isinstance(issue_id, str) or not issue_id
                        or not isinstance(record.get("rule"), str) or not record["rule"]
                        or not isinstance(record.get("evidence"), str) or not record["evidence"]
                        or not isinstance(paths, list)):
                    return {}
                if not all(isinstance(p, str) and p and Path(p).is_absolute() for p in paths):
                    reason = "MADV2_SCOPE_PATH_UNKNOWN: issue was not registered; submit absolute paths."
                    if not payload.get("stop_hook_active"):
                        return {"decision": "block", "reason": reason, "systemMessage": reason}
                    return {"systemMessage": reason}
                finding = {"issue_id": issue_id, "source_id": issue_id, "rule": record["rule"],
                           "evidence": record["evidence"],
                           "paths": [os.path.normcase(os.path.normpath(p)) for p in paths]}
                same = next((issue for issue in issues
                             if issue.get("source_id", issue["issue_id"]) == issue_id
                             and issue["rule"] == finding["rule"]
                             and issue["evidence"] == finding["evidence"]
                             and issue["paths"] == finding["paths"]), None)
                if same:
                    finding = same
                elif any(issue["issue_id"] == issue_id for issue in issues):
                    suffix = 2
                    while any(issue["issue_id"] == f"{issue_id}-{suffix}" for issue in issues):
                        suffix += 1
                    finding["issue_id"] = f"{issue_id}-{suffix}"
                if finding["issue_id"] != issue_id:
                    notices.append(f"MADV2_SCOPE_REASSIGNED issue={finding['issue_id']}")
                if same is None:
                    issues.append(finding)
                approval = None
            elif status == "ALLOW":
                issue_ids = record.get("issue_ids")
                if (not issues or not isinstance(issue_ids, list)
                        or not all(isinstance(item, str) for item in issue_ids)
                        or sorted(issue_ids) != sorted(i["issue_id"] for i in issues)
                        or record.get("tool") not in ("Bash", "apply_patch")
                        or not isinstance(record.get("cwd"), str)
                        or not isinstance(record.get("tool_input"), dict)):
                    return {}
                approval = {"tool": record["tool"], "cwd": record["cwd"],
                            "tool_input": record["tool_input"]}
            elif status == "RESOLVED":
                if not any(issue["issue_id"] == issue_id for issue in issues):
                    return {}
                issues = [issue for issue in issues if issue["issue_id"] != issue_id]
                approval = None
            elif status == "TRANSFER":
                if not isinstance(record.get("agent_id"), str) or not record["agent_id"]:
                    return {}
                transfer_to = record["agent_id"]
                approval = None
            else:
                return {}
            db.execute("UPDATE sessions SET issues = ?, approval = ?, transfer_to = ? WHERE session_id = ?",
                       (json.dumps(issues, ensure_ascii=False),
                        json.dumps(approval, ensure_ascii=False) if approval else None, transfer_to, session))
            if status == "VIOLATION":
                issue_id = finding["issue_id"]
            notices.append(f"MADV2_SCOPE_{status} session={session} issue={issue_id or '-'}")
            return {"systemMessage": " ".join(notices)}

        if not issues:
            return {}
        if event == "PreToolUse":
            tool = payload.get("tool_name")
            tool_input = payload.get("tool_input")
            cwd = payload.get("cwd")
            if approval and approval == {"tool": tool, "cwd": cwd, "tool_input": tool_input}:
                db.execute("UPDATE sessions SET approval = NULL WHERE session_id = ?", (session,))
                return {}
            if tool == "Bash":
                return _deny("Scope violation unresolved; collect the monitor finding and approve an exact read or correction.")
            if tool == "apply_patch" and (not isinstance(cwd, str) or not cwd):
                return {"systemMessage": "MADV2_SCOPE_CWD_UNKNOWN: patch coverage is unverified."}
            if tool == "apply_patch" and _touches_issue(
                    tool_input.get("command") if isinstance(tool_input, dict) else None, cwd, issues):
                return _deny("Scope violation unresolved; collect the monitor finding and approve an exact read or correction.")
        if event == "Stop":
            reason = "Scope violation unresolved; correct it and obtain a monitor recheck before claiming completion."
            if payload.get("stop_hook_active"):
                return {"continue": False, "stopReason": reason, "systemMessage": reason}
            return {"decision": "block", "reason": reason}
    return {}


def main() -> None:
    payload = json.load(sys.stdin)
    json.dump(handle(payload), sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
