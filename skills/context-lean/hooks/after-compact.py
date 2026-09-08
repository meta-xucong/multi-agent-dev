#!/usr/bin/env python3
"""Inject a short checkpoint after WorkBuddy resumes from compaction."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MAX_LINES = 24
MAX_CHARS = 4000


def read_event() -> dict:
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def find_progress(project_dir: Path) -> Path | None:
    candidates = [project_dir / "PROGRESS.md", project_dir / ".workbuddy" / "PROGRESS.md"]
    return next((path for path in candidates if path.is_file()), None)


def main() -> int:
    event = read_event()
    project_dir = Path(
        os.environ.get("CODEBUDDY_PROJECT_DIR")
        or os.environ.get("WORKBUDDY_PROJECT_DIR")
        or os.getcwd()
    ).resolve()
    progress = find_progress(project_dir)
    if progress is None:
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return 0

    lines = progress.read_text(encoding="utf-8", errors="replace").splitlines()
    excerpt = "\n".join(lines[:MAX_LINES])[:MAX_CHARS].strip()
    if not excerpt:
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return 0

    context = (
        "压缩后状态恢复。请以以下 PROGRESS.md 为准继续工作；"
        "不要假设压缩前未写入的细节仍然可靠。\n\n"
        + excerpt
    )
    print(json.dumps({
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
