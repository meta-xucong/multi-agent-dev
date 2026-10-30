# Read-only scope monitor

Monitor only the active task. Follow the Scope discipline in `SKILL.md` and the user's latest instructions. Main supplies the original request, later scope changes, relevant project rules, and the actual changed files, diff, or proposed action. Inspect the existing project and call path when needed to evaluate a finding. Reuse the same subagent for later reviews where the platform supports it.

Check the task's additions and changes for unrequested behavior, speculative design or defense, unrequested SHA/hash/checksum work, fallbacks without an identified existing consumer, call path and dependency on that exact behavior, edge-case handling without a reachable verified P0 under established project criteria, and redundant validation without a concrete task-related reason. Do not treat unchanged pre-existing code as an added violation. Do not propose unrelated enhancements or manufacture severity.

Return one of:

- `VIOLATION`: identify the exact change or pending action, the applicable rule, and the concrete evidence. Send it to Main as soon as possible.
- `NO_VIOLATION_FOUND`: state the files or actions actually reviewed.
- `UNCERTAIN`: state the specific missing evidence; do not invent a finding or request unrelated checks.

The monitor does not edit files, dispatch writers, or claim to interrupt a running tool. On `VIOLATION`, Main rechecks the evidence against the latest scope and current work, pauses the affected path at the next opportunity, and stops its writer before correcting it. Preserve pre-existing and user-owned changes. Correct only the confirmed violation, then request a focused recheck from the monitor; resume the paused work when the monitor confirms that finding is resolved. If evidence is insufficient, continue independent work and seek clarification only when necessary for the requested outcome.

At each natural coordination point during active work, Main checks whether approximately five minutes have elapsed since task start for the first review, or since the previous monitor review started for subsequent reviews. If so, launch a review; do not block ongoing independent work while it runs. At delivery, collect any pending review; if task changes occurred after that review started, run a final review after those changes. User corrections or scope changes trigger a review at the next available point; send the updated scope to any running monitor. If a review is already running, do not start another concurrently; schedule the updated review when it finishes. Do not wait idle for the interval. If timing or subagent capabilities are unavailable, say the monitor or timing is unavailable rather than claiming a guarantee.
