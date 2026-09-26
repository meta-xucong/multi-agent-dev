#!/usr/bin/env python3
"""Send a ServerChan notification when a multi-agent task reaches a terminal state."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


API_TEMPLATE = "https://sctapi.ftqq.com/{sendkey}.send"
SECRET_FILE = Path.home() / ".codex" / "secrets" / "serverchan_sendkey.txt"
SAFE_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def normalize_sendkey(value: str) -> str:
    return value.lstrip("\ufeff").strip()


def load_sendkey() -> str:
    if os.environ.get("SCT_SENDKEY"):
        return normalize_sendkey(os.environ["SCT_SENDKEY"])
    if SECRET_FILE.exists():
        return normalize_sendkey(SECRET_FILE.read_text(encoding="utf-8-sig"))
    return ""


def _read_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_verification(state: dict) -> str:
    tests = state.get("tests_run") or []
    if not isinstance(tests, list) or not tests:
        return ""
    latest = tests[-1]
    if isinstance(latest, dict):
        result = latest.get("result")
        command = latest.get("command")
        if not isinstance(result, str) or not result.strip():
            return ""
        result = result.strip()
        if isinstance(command, str) and command.strip():
            return f"{result} (command: {command.strip()})"
        return result
    return str(latest).strip()


def _build_message(args: argparse.Namespace, state: dict) -> str:
    project = Path(args.project).resolve()
    objective = state.get("objective") or "multi-agent development task"
    phase = state.get("current_phase") or "unknown"
    blockers = state.get("blockers") or []
    latest_test = args.verification.strip() or _latest_verification(state) or "not recorded"

    blocker_text = ""
    if args.status == "blocked" and blockers:
        blocker_text = "\n\nBlocked by:\n" + "\n".join(f"- {item}" for item in blockers[:3])

    summary = args.message.strip() if args.message else "The multi-agent task has stopped and is waiting for review."

    return textwrap.dedent(
        f"""
        # {args.title}

        Project: `{project}`

        Status: `{args.status}`

        Objective: {objective}

        Current phase: `{phase}`

        Summary: {summary}

        Latest verification: {latest_test}

        Time: {datetime.now().isoformat(timespec="seconds")}
        {blocker_text}

        Please return to the computer and review the result.
        """
    ).strip()


def send(sendkey: str, title: str, short: str, desp: str, timeout: int) -> dict:
    data = urllib.parse.urlencode(
        {
            "title": title,
            "short": short,
            "desp": desp,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        API_TEMPLATE.format(sendkey=normalize_sendkey(sendkey)),
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"code": -1, "message": "Non-JSON response", "raw": body}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project path associated with the task.")
    parser.add_argument(
        "--state-file",
        default="",
        help="Optional explicit state JSON; never inferred from the project to avoid cross-task contamination.",
    )
    parser.add_argument("--status", default="stopped", choices=["done", "blocked", "stopped"])
    parser.add_argument("--title", default="多 Agent 任务已停止，等待验收")
    parser.add_argument("--message", default="")
    parser.add_argument("--short", default="Codex 多 Agent 任务需要人工查看")
    parser.add_argument("--verification", default="", help="Concrete verification result included in the notification.")
    parser.add_argument(
        "--task-id",
        default="",
        help="Optional MAD route task ID; retires the matching interruption fallback after successful delivery.",
    )
    parser.add_argument("--sendkey", default=load_sendkey())
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _hook_notify_function(name: str):
    """Load a local hook helper without making the notifier depend on hook state."""

    hook_dir = Path(__file__).resolve().parents[1] / "hooks"
    hook_path = str(hook_dir)
    if hook_path not in sys.path:
        sys.path.insert(0, hook_path)
    try:
        from task_terminal_notify import mark_external_delivery, register_external_intent
    except ImportError:
        return None
    return {
        "register": register_external_intent,
        "delivered": mark_external_delivery,
    }.get(name)


def _register_hook_intent(args: argparse.Namespace, message: str) -> int:
    if not args.task_id:
        return 0
    helper = _hook_notify_function("register")
    if helper is None:
        return 0
    return helper(args.task_id, args.status, args.title, args.short, message, args.verification)


def _retire_hook_fallback(task_id: str, status: str) -> int:
    """Clear matching active-hook state after this direct notification succeeds."""

    if not task_id:
        return 0
    if SAFE_TASK_ID_RE.fullmatch(task_id) is None:
        raise ValueError("Invalid task ID")
    helper = _hook_notify_function("delivered")
    if helper is None:
        return 0
    return helper(task_id, status)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    project = Path(args.project).resolve()
    state = _read_state(Path(args.state_file).expanduser().resolve()) if args.state_file else {}
    args.verification = args.verification.strip() or _latest_verification(state)
    if args.status == "done" and not args.verification:
        print(
            json.dumps(
                {"code": -1, "message": "A done notification requires --verification or a recorded test result."},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    desp = _build_message(args, state)

    if not args.sendkey:
        print(
            json.dumps(
                {
                    "code": -1,
                    "message": "Missing SendKey. Set SCT_SENDKEY, pass --sendkey, or create ~/.codex/secrets/serverchan_sendkey.txt.",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    if args.task_id and SAFE_TASK_ID_RE.fullmatch(args.task_id) is None:
        print(json.dumps({"code": -1, "message": "Invalid task ID."}, ensure_ascii=False), file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps({"dry_run": True, "title": args.title, "short": args.short, "desp": desp}, ensure_ascii=False))
        return 0

    retries = max(1, int(args.retries or 1))
    delay_seconds = max(0, int(args.retry_delay_seconds or 0))
    attempts: list[dict[str, object]] = []
    try:
        summary = args.message.strip() or "The multi-agent task has stopped and is waiting for review."
        hook_intents_registered = _register_hook_intent(args, summary)
    except (OSError, ValueError):
        hook_intents_registered = 0
    for index in range(1, retries + 1):
        try:
            result = send(args.sendkey, args.title, args.short, desp, args.timeout)
            attempts.append({"attempt": index, "result": result})
            if result.get("code") == 0:
                retired = 0
                if args.task_id:
                    try:
                        retired = _retire_hook_fallback(args.task_id, args.status)
                    except (OSError, ValueError):
                        # The notification is already delivered; do not invite a duplicate retry.
                        retired = 0
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "attempts": attempts,
                            "result": result,
                            "hook_intents_registered": hook_intents_registered,
                            "hook_fallbacks_retired": retired,
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            attempts.append({"attempt": index, "error": str(exc)})
        if index < retries and delay_seconds > 0:
            time.sleep(delay_seconds)

    print(json.dumps({"ok": False, "attempts": attempts}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
