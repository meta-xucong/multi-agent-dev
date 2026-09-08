#!/usr/bin/env python3
"""Persist a compact checkpoint before WorkBuddy context compaction."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def read_event() -> dict:
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def atomic_copy(source: Path, target: Path) -> bool:
    if not source.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        shutil.copyfile(source, temp)
        os.replace(temp, target)
        return True
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    event = read_event()
    project_dir = Path(
        os.environ.get("CODEBUDDY_PROJECT_DIR")
        or os.environ.get("WORKBUDDY_PROJECT_DIR")
        or os.getcwd()
    ).resolve()
    workbuddy_dir = project_dir / ".workbuddy"
    progress = project_dir / "PROGRESS.md"
    if not progress.is_file():
        progress = workbuddy_dir / "PROGRESS.md"

    state_dir = workbuddy_dir / "state"
    snapshot = state_dir / "PROGRESS.precompact.md"
    metadata = state_dir / "precompact.json"
    state_dir.mkdir(parents=True, exist_ok=True)

    copied = atomic_copy(progress, snapshot)
    payload = {
        "savedAt": datetime.now(timezone.utc).isoformat(),
        "trigger": event.get("trigger", "unknown"),
        "sessionId": event.get("session_id"),
        "transcriptPath": event.get("transcript_path"),
        "progressPath": str(progress) if progress.is_file() else None,
        "snapshotPath": str(snapshot) if copied else None,
    }
    metadata.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"continue": True, "systemMessage": "PreCompact checkpoint saved."}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
