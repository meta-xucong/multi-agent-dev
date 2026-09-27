#!/usr/bin/env python3
"""Send one V2 terminal notification via ServerChan with local idempotency receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


API_TEMPLATE = "https://sctapi.ftqq.com/{sendkey}.send"
SECRET_FILE = Path.home() / ".codex" / "secrets" / "serverchan_sendkey.txt"
STATE_DIR = Path.home() / ".codex" / "state" / "multi-agent-dev-v2"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
STATUSES = ("done", "blocked", "stopped")


def _normalize(value: str) -> str:
    return value.lstrip("\ufeff").strip()


def load_sendkey() -> str:
    environment_value = os.environ.get("SCT_SENDKEY", "")
    if environment_value.strip():
        return _normalize(environment_value)
    try:
        return _normalize(SECRET_FILE.read_text(encoding="utf-8-sig"))
    except OSError:
        return ""


def _receipt_path(state_dir: Path, task_id: str, status: str) -> Path:
    return state_dir / "receipts" / hashlib.sha256(task_id.encode("utf-8")).hexdigest() / f"{status}.json"


def _pending_path(state_dir: Path, task_id: str, status: str) -> Path:
    return state_dir / "pending" / hashlib.sha256(task_id.encode("utf-8")).hexdigest() / f"{status}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_receipt(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix="receipt-", suffix=".tmp", delete=False
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


def _write_pending(path: Path, value: dict[str, Any]) -> None:
    _write_receipt(path, value)


def build_message(args: argparse.Namespace) -> str:
    project_name = Path(args.project).expanduser().name or "project"
    lines = [
        f"Project: `{project_name}`",
        f"Status: `{args.status}`",
        f"Summary: {args.message.strip() or 'The multi-agent task has stopped.'}",
    ]
    if args.verification.strip():
        lines.append(f"Verification: {args.verification.strip()}")
    lines.append(f"Time: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    return "\n\n".join(lines)


def send_notification(sendkey: str, title: str, short: str, body: str, timeout: int) -> bool:
    data = urllib.parse.urlencode({"title": title, "short": short, "desp": body}).encode("utf-8")
    request = urllib.request.Request(
        API_TEMPLATE.format(sendkey=urllib.parse.quote(_normalize(sendkey), safe="")),
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8", errors="replace"))
    return isinstance(result, dict) and result.get("code") == 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default="", help="Optional local-only idempotency key; never sent to ServerChan.")
    parser.add_argument("--register-active", action="store_true", help="Ask an installed PreToolUse hook to register this session locally.")
    parser.add_argument("--project", default=".")
    parser.add_argument("--status", choices=STATUSES)
    parser.add_argument("--title", default="多 Agent 任务状态通知")
    parser.add_argument("--short", default="Codex 多 Agent 开发任务状态更新")
    parser.add_argument("--message", default="The multi-agent task has stopped.")
    parser.add_argument("--verification", default="")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--state-dir", type=Path, default=STATE_DIR, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.task_id and SAFE_ID.fullmatch(args.task_id) is None:
        print(json.dumps({"ok": False, "error": "invalid_task_id"}), file=sys.stderr)
        return 2
    if args.register_active:
        if not args.task_id:
            print(json.dumps({"ok": False, "error": "registration_requires_task_id"}), file=sys.stderr)
            return 2
        print(json.dumps({"ok": True, "registration_requested": True}))
        return 0
    if args.status not in STATUSES:
        print(json.dumps({"ok": False, "error": "status_required"}), file=sys.stderr)
        return 2
    if args.status == "done" and not args.verification.strip():
        print(json.dumps({"ok": False, "error": "done_requires_verification"}), file=sys.stderr)
        return 2
    body = build_message(args)
    state_dir = args.state_dir.expanduser()
    receipt_path = _receipt_path(state_dir, args.task_id, args.status) if args.task_id else None
    if receipt_path is not None and _read_json(receipt_path):
        print(json.dumps({"ok": True, "already_sent": True}))
        return 0
    if args.dry_run:
        print(json.dumps({"dry_run": True, "title": args.title, "short": args.short, "desp": body}, ensure_ascii=False))
        return 0

    pending_path = _pending_path(state_dir, args.task_id, args.status) if args.task_id else None
    if pending_path is not None:
        _write_pending(
            pending_path,
            {
                "status": args.status,
                "title": args.title,
                "short": args.short,
                "message": args.message.strip() or "The multi-agent task has stopped.",
                "verification": args.verification.strip(),
                "project": args.project,
                "updated_at": int(time.time()),
            },
        )

    sendkey = load_sendkey()
    if not sendkey:
        print(json.dumps({"ok": False, "error": "missing_sendkey"}), file=sys.stderr)
        return 2

    attempts = max(1, args.retries)
    delay = max(0, args.retry_delay_seconds)
    for attempt in range(1, attempts + 1):
        try:
            delivered = send_notification(sendkey, args.title, args.short, body, max(1, args.timeout))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            delivered = False
        if delivered:
            if receipt_path is not None:
                _write_receipt(receipt_path, {"status": args.status, "sent_at": int(time.time())})
            if pending_path is not None:
                _remove(pending_path)
            print(json.dumps({"ok": True, "attempts": attempt}))
            return 0
        if attempt < attempts and delay:
            time.sleep(delay)
    print(json.dumps({"ok": False, "error": "delivery_failed", "attempts": attempts}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
