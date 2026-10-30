# Long-task recovery and optional notifications

Follow the parent `SKILL.md` scope discipline. These mechanisms are conditional; do not add lifecycle setup, notification, or recovery work to a task that does not need or request it.

## Context recovery

Use `context-lean` for genuinely long, multi-phase, high-volume, handoff-heavy, or context-degraded work. Keep checkpoints short and limited to facts needed to resume the requested task: current scope, baseline or existing changes that must be preserved, active writer, work completed, unresolved blocker, and next action. Do not create checkpoints for short tasks or expand scope during recovery.

## Notifications

Send a ServerChan notification only when the user explicitly requests it or an existing project instruction requires it. Do not register lifecycle Hooks or emit a terminal notification by default. If a notification is requested, use the bundled notifier's documented secret handling and report delivery accurately; do not expose credentials. Never claim that a notification or Hook ran without direct evidence.
