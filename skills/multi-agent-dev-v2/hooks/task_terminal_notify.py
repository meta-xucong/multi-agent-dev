#!/usr/bin/env python3
"""V2 lifecycle-notification hook; inactive unless manually registered and trusted."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TERMINAL = frozenset({"done", "blocked", "stopped"})
MAX_TEXT = 4000
STATE_ROOT = Path.home() / ".codex" / "state" / "multi-agent-dev-v2"
ACTIVE_DIR = STATE_ROOT / "active"
PENDING_DIR = STATE_ROOT / "pending"
HOOK_RECEIPT_DIR = STATE_ROOT / "hook-receipts"
NOTIFIER = Path(__file__).resolve().parents[1] / "scripts" / "notify_serverchan.py"
SHELL_CONTROL = re.compile(r"[;&|<>`\r\n]")
PYTHON_EXECUTABLES = frozenset({"python", "python3", "python.exe", "python3.exe", "py", "py.exe"})


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(value: Any, limit: int = MAX_TEXT) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and len(value) <= limit else None


def _path(directory: Path, key: str, suffix: str = ".json") -> Path:
    return directory / f"{key}{suffix}"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix="record-", suffix=".tmp", delete=False
        ) as temporary:
            temporary_name = temporary.name
            json.dump(value, temporary, ensure_ascii=False)
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _session(payload: dict[str, Any]) -> str | None:
    value = payload.get("session_id")
    if isinstance(value, str) and value.strip() and len(value) <= 512:
        return value.strip()
    return None


def register_active_session(session_id: str, task_id: str, state_root: Path = STATE_ROOT) -> bool:
    if not session_id or len(session_id) > 512 or SAFE_ID.fullmatch(task_id) is None:
        return False
    task_hash = _digest(task_id)
    _write_json(
        _path(state_root / "active", _digest(session_id)),
        {"task_hash": task_hash, "started_at": int(time.time())},
    )
    return True


def _unquote_token(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _is_notifier_path(value: str, cwd: str | None) -> bool:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = Path(cwd) / candidate if cwd else Path.cwd() / candidate
    try:
        return candidate.resolve() == NOTIFIER.resolve()
    except (OSError, RuntimeError):
        return False


def _registration_argv(command: str, cwd: str | None) -> str | None:
    if not command or SHELL_CONTROL.search(command):
        return None
    try:
        tokens = [_unquote_token(token) for token in shlex.split(command, posix=False)]
    except ValueError:
        return None
    if len(tokens) < 4:
        return None

    executable = tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if executable not in PYTHON_EXECUTABLES:
        return None
    index = 1
    while index < len(tokens) and tokens[index] in {"-3", "-B"}:
        index += 1
    if index >= len(tokens) or not _is_notifier_path(tokens[index], cwd):
        return None

    args = tokens[index + 1 :]
    register_count = 0
    task_id: str | None = None
    cursor = 0
    while cursor < len(args):
        value = args[cursor]
        if value == "--register-active":
            register_count += 1
            cursor += 1
        elif value == "--task-id" and cursor + 1 < len(args):
            if task_id is not None:
                return None
            task_id = args[cursor + 1]
            cursor += 2
        elif value.startswith("--task-id="):
            if task_id is not None:
                return None
            task_id = value.partition("=")[2]
            cursor += 1
        else:
            return None
    if register_count != 1 or task_id is None or SAFE_ID.fullmatch(task_id) is None:
        return None
    return task_id


def _registration_task_id(payload: dict[str, Any]) -> str | None:
    if payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        return None
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    return _registration_argv(tool_input["command"], cwd)


def _active_record(payload: dict[str, Any], state_root: Path) -> tuple[Path, dict[str, Any]] | None:
    session_id = _session(payload)
    if session_id is None:
        return None
    path = _path(state_root / "active", _digest(session_id))
    record = _read_json(path)
    if not record or not isinstance(record.get("task_hash"), str):
        return None
    if re.fullmatch(r"[a-f0-9]{64}", record["task_hash"]) is None:
        return None
    return path, record


def _pending_records(task_hash: str, state_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    directory = state_root / "pending" / task_hash
    if not directory.is_dir():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in directory.glob("*.json"):
        record = _read_json(path)
        if not record:
            continue
        status = record.get("status")
        title = _text(record.get("title"), 160)
        short = _text(record.get("short"), 240)
        message = _text(record.get("message"))
        verification = _text(record.get("verification"))
        project = _text(record.get("project"), 1024) or "."
        if (
            status in TERMINAL
            and title is not None
            and short is not None
            and message is not None
            and (status != "done" or verification is not None)
        ):
            records.append(
                (
                    path,
                    {
                        "status": status,
                        "title": title,
                        "short": short,
                        "message": message,
                        "verification": verification or "",
                        "project": project,
                    },
                )
            )
    return sorted(records, key=lambda pair: pair[0].stat().st_mtime, reverse=True)


def _already_delivered(task_hash: str, state_root: Path) -> bool:
    receipts = state_root / "receipts" / task_hash
    return receipts.is_dir() and any(receipts.glob("*.json"))


def _hook_receipt(payload: dict[str, Any], task_hash: str, status: str, state_root: Path) -> Path:
    session_id = _session(payload) or "unknown-session"
    key = _digest(f"{session_id}\0{task_hash}\0{status}")
    return _path(state_root / "hook-receipts", key)


def _fallback(task_hash: str, project: str = ".") -> dict[str, str]:
    return {
        "status": "stopped",
        "title": "多 Agent 任务已中断，等待检查",
        "short": "Codex 多 Agent 任务需要人工查看",
        "message": "任务在发送终态通知前被中断或会话结束，已按 stopped 状态补发提醒。",
        "verification": "",
        "project": project,
    }


def _run_notifier(item: dict[str, str], state_root: Path, event: str) -> tuple[bool, str]:
    if item["status"] == "done" and not item.get("verification", "").strip():
        return False, "done_verification_missing"
    short_event = event in {"Interrupt", "SessionEnd"}
    timeout = "1" if short_event else "10"
    command = [
        sys.executable,
        str(NOTIFIER),
        "--project",
        item["project"],
        "--status",
        item["status"],
        "--title",
        item["title"],
        "--short",
        item["short"],
        "--message",
        item["message"],
        "--timeout",
        timeout,
        "--retries",
        "1" if short_event else "3",
        "--retry-delay-seconds",
        "0" if short_event else "2",
        "--state-dir",
        str(state_root),
    ]
    if item.get("verification"):
        command.extend(["--verification", item["verification"]])
    try:
        completed = subprocess.run(
            command,
            cwd=item["project"] if Path(item["project"]).is_dir() else None,
            capture_output=True,
            text=True,
            timeout=2 if short_event else 45,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
        return False, type(exc).__name__
    return (True, "ok") if completed.returncode == 0 else (False, f"notifier_exit_{completed.returncode}")


def _cleanup(active_path: Path, pending_path: Path | None) -> None:
    _remove(active_path)
    if pending_path is not None:
        _remove(pending_path)


def _deliver_active(payload: dict[str, Any], event: str, state_root: Path) -> dict[str, Any]:
    active = _active_record(payload, state_root)
    if active is None:
        return {"continue": True} if event == "Stop" else {}
    active_path, active_record = active
    task_hash = active_record["task_hash"]
    if _already_delivered(task_hash, state_root):
        _cleanup(active_path, None)
        return {"continue": True} if event == "Stop" else {}

    pending = _pending_records(task_hash, state_root)
    if event == "Stop" and not pending:
        return {"continue": True}
    if pending:
        pending_path, item = pending[0]
    elif event in {"Interrupt", "SessionEnd"}:
        pending_path = None
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else "."
        item = _fallback(task_hash, cwd)
    else:
        return {"continue": True} if event == "Stop" else {}

    receipt = _hook_receipt(payload, task_hash, item["status"], state_root)
    if receipt.exists():
        _cleanup(active_path, pending_path)
        return {"continue": True} if event == "Stop" else {}
    ok, detail = _run_notifier(item, state_root, event)
    if ok:
        _write_json(receipt, {"status": item["status"], "sent_at": int(time.time())})
        _cleanup(active_path, pending_path)
        return {"continue": True} if event == "Stop" else {}
    if event == "Stop" and not bool(payload.get("stop_hook_active")):
        return {
            "decision": "block",
            "reason": f"ServerChan delivery failed ({detail}); retry the terminal notification before ending this task.",
        }
    if event == "Stop":
        return {
            "continue": True,
            "systemMessage": f"ServerChan delivery failed ({detail}); notification remains an open delivery risk.",
        }
    return {"systemMessage": f"ServerChan delivery failed ({detail}); notification remains an open delivery risk."}


def handle(payload: Any, state_root: Path = STATE_ROOT) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        task_id = _registration_task_id(payload)
        session_id = _session(payload)
        if task_id and session_id:
            register_active_session(session_id, task_id, state_root)
        return {}
    if event not in {"Stop", "Interrupt", "SessionEnd"}:
        return {}
    return _deliver_active(payload, event, state_root)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("{}")
        return 0
    try:
        result = handle(payload, STATE_ROOT)
    except Exception:
        event = payload.get("hook_event_name") if isinstance(payload, dict) else ""
        if event == "SessionEnd":
            print("V2 ServerChan hook failed; notification is an open delivery risk.", file=sys.stderr)
            return 1
        if event == "Stop" and not bool(payload.get("stop_hook_active")):
            result = {"decision": "block", "reason": "V2 ServerChan hook failed; retry before ending the task."}
        elif event == "PreToolUse":
            result = {}
        elif event == "Stop":
            result = {"systemMessage": "V2 ServerChan hook failed; notification is an open delivery risk."}
        else:
            result = {"systemMessage": "V2 ServerChan hook failed; notification is an open delivery risk."}
    event = payload.get("hook_event_name") if isinstance(payload, dict) else ""
    if event == "PreToolUse":
        return 0
    if event == "SessionEnd":
        message = result.get("systemMessage")
        if isinstance(message, str) and message:
            print(message, file=sys.stderr)
            return 1
        return 0
    if event in {"Interrupt"} and not result.get("systemMessage"):
        return 0
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
