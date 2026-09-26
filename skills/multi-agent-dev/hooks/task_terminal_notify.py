#!/usr/bin/env python3
"""Enforce a ServerChan notification before a multi-agent task stops.

The hook is intentionally small and stateful only at the delivery boundary:
the final assistant message carries a short terminal marker, the hook sends
that marker through the bundled notifier, and a local receipt prevents
duplicates.  A pending record makes a later SessionEnd/Interrupt invocation
able to retry a failed delivery without retaining credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


MARKER_PREFIX = "MAD_TASK_TERMINAL_V1"
TERMINAL_STATUSES = frozenset({"done", "blocked", "stopped"})
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_TITLE = 160
MAX_SHORT = 240
MAX_MESSAGE = 4000
STATE_ROOT = Path.home() / ".codex" / "state" / "multi-agent-dev"
ACTIVE_DIR = STATE_ROOT / "active"
PENDING_DIR = STATE_ROOT / "pending"
RECEIPT_DIR = STATE_ROOT / "receipts"
NOTIFY_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "notify_serverchan.py"


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > limit:
        return None
    return value


def parse_terminal_marker(message: Any) -> dict[str, str] | None:
    """Parse the hidden terminal marker from the final assistant message."""

    if not isinstance(message, str):
        return None
    for raw_line in reversed(message.splitlines()):
        line = raw_line.strip()
        if line.startswith("<!--") and line.endswith("-->"):
            line = line[4:-3].strip()
        if not line.startswith(MARKER_PREFIX + " "):
            continue
        try:
            payload = json.loads(line[len(MARKER_PREFIX) :].strip())
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        required = {"task_id", "status", "title", "short", "message"}
        if set(payload) != required:
            return None
        task_id = payload.get("task_id")
        status = payload.get("status")
        if not isinstance(task_id, str) or SAFE_ID_RE.fullmatch(task_id) is None:
            return None
        if not isinstance(status, str) or status not in TERMINAL_STATUSES:
            return None
        title = _text(payload.get("title"), MAX_TITLE)
        short = _text(payload.get("short"), MAX_SHORT)
        summary = _text(payload.get("message"), MAX_MESSAGE)
        if title is None or short is None or summary is None:
            return None
        return {
            "task_id": task_id,
            "status": status,
            "title": title,
            "short": short,
            "message": summary,
        }
    return None


def _context_id(payload: dict[str, Any]) -> str:
    for field in ("session_id", "transcript_path", "cwd"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown-session"


def delivery_key(payload: dict[str, Any], task_id: str) -> str:
    raw = f"{_context_id(payload)}\0{task_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _path(directory: Path, key: str) -> Path:
    return directory / f"{key}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def register_active_session(payload: dict[str, Any], task_id: str) -> None:
    """Record that a marked Agent dispatch started a task (best effort)."""

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return
    key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    _write_json(
        _path(ACTIVE_DIR, key),
        {
            "session_id": session_id,
            "task_id": task_id,
            "cwd": payload.get("cwd") if isinstance(payload.get("cwd"), str) else ".",
            "started_at": int(time.time()),
        },
    )


def _active_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return _read_json(_path(ACTIVE_DIR, key))


def _pending_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip() or not PENDING_DIR.exists():
        return None
    for path in PENDING_DIR.glob("*.json"):
        record = _read_json(path)
        if record and record.get("session_id") == session_id:
            return record
    return None


def _fallback_marker(payload: dict[str, Any]) -> dict[str, str] | None:
    pending = _pending_record(payload)
    if pending:
        task_id = pending.get("task_id")
        status = pending.get("status")
        title = _text(pending.get("title"), MAX_TITLE)
        short = _text(pending.get("short"), MAX_SHORT)
        summary = _text(pending.get("message"), MAX_MESSAGE)
        if (
            isinstance(task_id, str)
            and SAFE_ID_RE.fullmatch(task_id) is not None
            and isinstance(status, str)
            and status in TERMINAL_STATUSES
            and title is not None
            and short is not None
            and summary is not None
        ):
            return {
                "task_id": task_id,
                "status": status,
                "title": title,
                "short": short,
                "message": summary,
            }
    active = _active_record(payload)
    if not active:
        return None
    task_id = active.get("task_id")
    if not isinstance(task_id, str) or SAFE_ID_RE.fullmatch(task_id) is None:
        return None
    return {
        "task_id": task_id,
        "status": "stopped",
        "title": "多 Agent 任务已停止，等待验收",
        "short": "Codex 多 Agent 任务需要人工查看",
        "message": "任务在会话中断或结束前未提交 done/blocked 终态，已按 stopped 通知。",
    }


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _run_notifier(marker: dict[str, str], payload: dict[str, Any]) -> tuple[bool, str]:
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else "."
    run_cwd = cwd if Path(cwd).is_dir() else None
    event = payload.get("hook_event_name")
    if event == "Stop":
        timeout, retries, delay = "10", "3", "2"
    else:
        # SessionEnd/Interrupt have a platform timeout of at most three seconds.
        timeout, retries, delay = "1", "1", "0"
    command = [
        sys.executable,
        str(NOTIFY_SCRIPT),
        "--project",
        cwd,
        "--status",
        marker["status"],
        "--title",
        marker["title"],
        "--short",
        marker["short"],
        "--message",
        marker["message"],
        "--timeout",
        timeout,
        "--retries",
        retries,
        "--retry-delay-seconds",
        delay,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=run_cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45 if event == "Stop" else 2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError) as error:
        return False, type(error).__name__
    if completed.returncode == 0:
        return True, "ok"
    return False, f"notifier_exit_{completed.returncode}"


def deliver(marker: dict[str, str], payload: dict[str, Any]) -> tuple[bool, str]:
    key = delivery_key(payload, marker["task_id"])
    receipt = _path(RECEIPT_DIR, key)
    pending = _path(PENDING_DIR, key)
    active = None
    session_id = payload.get("session_id")
    if isinstance(session_id, str) and session_id.strip():
        active = _path(ACTIVE_DIR, hashlib.sha256(session_id.encode("utf-8")).hexdigest())
    if receipt.exists():
        _remove(pending)
        _remove(active) if active else None
        return True, "already_sent"
    _write_json(
        pending,
        {
            "task_id": marker["task_id"],
            "status": marker["status"],
            "title": marker["title"],
            "short": marker["short"],
            "message": marker["message"],
            "session_id": payload.get("session_id"),
            "updated_at": int(time.time()),
        },
    )
    ok, detail = _run_notifier(marker, payload)
    if not ok:
        return False, detail
    _write_json(
        receipt,
        {
            "task_id": marker["task_id"],
            "status": marker["status"],
            "sent_at": int(time.time()),
        },
    )
    _remove(pending)
    _remove(active) if active else None
    return True, detail


def _result(*, event: str, success: bool, detail: str, retry_allowed: bool) -> dict[str, Any]:
    if success:
        return {"continue": True}
    if event == "Stop" and retry_allowed:
        return {
            "decision": "block",
            "reason": f"ServerChan notification failed ({detail}); retry the notification before ending the task.",
        }
    return {
        "continue": True,
        "systemMessage": f"ServerChan notification failed ({detail}); delivery is recorded as a blocking risk.",
    }


def _active_stop_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("hook_event_name") != "Stop":
        return None
    if _active_record(payload) is None and _pending_record(payload) is None:
        return None
    return {
        "decision": "block",
        "reason": (
            "This marked multi-agent task cannot end without a MAD_TASK_TERMINAL_V1 "
            "done/blocked/stopped marker in the final response."
        ),
    }


def handle(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"continue": True, "systemMessage": "ServerChan hook received invalid input."}
    event = payload.get("hook_event_name")
    if event not in {"Stop", "SessionEnd", "Interrupt"}:
        return {"continue": True}
    marker = parse_terminal_marker(payload.get("last_assistant_message"))
    if marker is None:
        active_stop = _active_stop_result(payload)
        if active_stop is not None:
            return active_stop
    if marker is None and event in {"SessionEnd", "Interrupt"}:
        marker = _fallback_marker(payload)
    if marker is None:
        return {"continue": True}
    ok, detail = deliver(marker, payload)
    retry_allowed = not bool(payload.get("stop_hook_active"))
    return _result(event=event, success=ok, detail=detail, retry_allowed=retry_allowed)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except (OSError, UnicodeError, json.JSONDecodeError):
        print(json.dumps({"continue": True, "systemMessage": "ServerChan hook input was invalid."}))
        return 0
    try:
        result = handle(payload)
    except Exception:
        event = payload.get("hook_event_name") if isinstance(payload, dict) else ""
        if event == "Stop" and not bool(payload.get("stop_hook_active")):
            result = {
                "decision": "block",
                "reason": "ServerChan notification hook failed; retry the notification before ending the task.",
            }
        else:
            result = {
                "continue": True,
                "systemMessage": "ServerChan notification hook failed; delivery is recorded as a blocking risk.",
            }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
