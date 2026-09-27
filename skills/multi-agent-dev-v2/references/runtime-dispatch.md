# Runtime dispatch and child provenance

This package treats Codex Hook availability as an external capability. The
runtime dispatcher therefore enforces the parts that remain under the
controller's control: explicit requested route, child-thread lifecycle,
observed model/effort, and fail-closed handoff.

## Required lifecycle

The parent must remain alive until the child reaches a terminal turn event:

```text
dispatch request
  -> child thread started
  -> child settings update observed
  -> child turn completed or failed
  -> provenance compared with the frozen request
  -> parent may close
```

The controller must not treat a model-generated `spawn_agent` argument as
observed provenance. It may use that argument as the requested route only.
Observed values must come from the child thread's explicit runtime settings
update event.  Model/effort fields copied into a thread-start event are not
independent route evidence.  Activity items are accepted only when scoped to
the requested parent thread.

## Gate rules

- No child thread ID: `SPAWN_FAILED`/`CHILD_THREAD_NOT_STARTED`.
- Child exists but no model or effort is observed: `ROUTE_UNVERIFIED`.
- Observed values differ from the frozen request: `ROUTE_MISMATCH` and hold.
- Conflicting settings updates, an observed spawn failure, or a parent terminal
  event before child terminal: hold, even if later events look successful.
- Matching observed values plus a terminal child turn: `EXPLICIT_ROUTE_VERIFIED`.
- Parent close before child terminal: `PARENT_CLOSE_BEFORE_CHILD_TERMINAL` and hold.
- A result is admissible only when the child is terminal and route provenance is
  `PROFILE_VERIFIED` or `EXPLICIT_ROUTE_VERIFIED`.

The Hook axis remains separate. A missing or unavailable Hook does not become a
route pass, and a Hook receipt does not become model/effort provenance.

## Implementation boundary

`scripts/runtime_dispatch.py` is transport-neutral. The caller supplies raw
app-server events and records the returned `RuntimeDispatchResult` in the
normal TaskSpec/Handoff evidence. It does not open a network connection, call a
Provider, or write the controller ledger by itself. This keeps the runtime
adapter testable and prevents a failed Codex dispatch from silently advancing a
task.

## Minimum acceptance evidence

Each live probe must retain the parent and child thread IDs, the settings event,
the terminal child event, the requested route, the observed route, and the
resulting route status. A probe that only returns a task name, a Hook receipt,
or an agent self-report is insufficient.
