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
observed provenance. It may use that argument as the requested route only,
after validating role, profile ID, requested model/effort, and requested sandbox
mode against the frozen V2 route contract. The `source_fidelity` role accepts
only its dedicated A1/A2 profiles; an Audit profile with the same read-only
setting is not interchangeable. A matching but unauthorized request is not compliant.
Observed values must come from the child thread's explicit runtime settings
update event.  Model/effort fields copied into a thread-start event are not
independent route evidence.  Activity items are accepted only when scoped to
the requested parent thread.

## Gate rules

- No child thread ID: `SPAWN_FAILED`/`CHILD_THREAD_NOT_STARTED`.
- Child exists but no model or effort is observed: `ROUTE_UNVERIFIED`.
- Observed values differ from the frozen request: `ROUTE_MISMATCH` and hold.
- Role/profile ID, requested model/effort, or requested sandbox differs from the frozen V2
  route matrix: reject the request before evaluating runtime events.
- Conflicting settings updates, an observed spawn failure, or a parent terminal
  event before child terminal: hold, even if later events look successful.
- Matching observed values plus a terminal child turn: `EXPLICIT_ROUTE_VERIFIED`.
- Parent close before child terminal: `PARENT_CLOSE_BEFORE_CHILD_TERMINAL` and hold.
- A result is admissible only when the child is terminal and route provenance is
  `PROFILE_VERIFIED` or `EXPLICIT_ROUTE_VERIFIED`.

Only model and reasoning effort are observed in the current event adapter. The
sandbox mode is a requested profile setting, not observed runtime provenance;
do not claim the live child was sandboxed read-only from this evidence alone.

The Hook axis remains separate. A missing or unavailable Hook does not become a
route pass, and a Hook receipt does not become model/effort provenance.

## Implementation boundary

`scripts/runtime_dispatch.py` is transport-neutral. `runtime-gate` evaluates
events without writing state. `bind-source-dispatch` additionally requires a
source-sensitive TaskSpec and `source_fidelity` role, then records the accepted
dispatch result and a hash of the supplied event list for later handoff binding.
This binding is only as trustworthy as the controller's event source: the
package does not cryptographically sign app-server events or prove that an
arbitrary caller supplied authentic events.

## Minimum acceptance evidence

Each live probe must retain the parent and child thread IDs, the settings event,
the terminal child event, the requested route, the observed route, and the
resulting route status. A probe that only returns a task name, a Hook receipt,
or an agent self-report is insufficient.
