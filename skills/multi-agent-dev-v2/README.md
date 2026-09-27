# multi-agent-dev-v2

Independent V2 package. It does not replace or modify V1.

## Install

Copy this directory as a whole into the Codex skills directory, for example:

```text
%USERPROFILE%\.codex\skills\multi-agent-dev-v2\
```

Restart or refresh Codex as required by the installed version, then explicitly load `multi-agent-dev-v2` and verify it appears in the skill list. Do not overwrite an existing directory without reviewing its differences.

Optional custom-agent profiles are in `profiles/`. Review and copy only the needed TOML files into either the user profile directory `%USERPROFILE%\.codex\agents\` or the project-local `.codex\agents\`. Check for name collisions first; do not overwrite an existing profile. Profile installation is not evidence that the current dispatch tool loads it or that the runtime model/effort matches.

V2 intentionally ships no active route Hook registration: the current dispatch path has not passed the required runtime rewrite/reject probe. A separate optional terminal-notification Hook example is provided under `hooks/`; it is not installed or trusted. Do not merge it into global `hooks.json` or trust it based only on this package. Re-test after Codex/tool updates before relying on route enforcement or interruption compensation.

## Validate

From the repository root:

```powershell
python -B -m unittest discover -s skills/multi-agent-dev-v2/tests -p "test_*.py" -v
```

The deterministic tests validate package metadata, routing contract, profiles, and notification behavior. They do not prove Codex Hook activation, custom-profile discovery, or actual model/effort provenance. The separate skill-creator `quick_validate.py` may also be run when available with its PyYAML dependency installed.


## V2.1 controlled parallel controller

The package now includes a local, controller-owned orchestration core. orchestrate.py accepts one JSON request on stdin and exposes init, plan, dispatch-next, bind-start, checkpoint, handoff, attach-receipt, status, cancel, recover, and integrate-check. State is kept in a caller-selected private SQLite file with WAL/FULL durability, CAS revisions, idempotency, outbox events, controller epochs, fenced leases, dependency scheduling, and fail-closed Guard/Audit gates.

Workers do not write the ledger. They submit structured HandoffPacket facts; the controller advances a task only after Guard and an independent AuditReceipt. Requested model/effort fields remain requests until runtime provenance is observed. capability_registry.py only reads the bundled TOML metadata and does not install or activate Profiles.

The V2.1 implementation is still a development component: the tests and local CLI probes do not prove Codex Hook activation, Profile discovery in the live runtime, actual model/effort use, or the forward workflow gates. Keep external side effects held until those gates have independent evidence.

The controller also provides evidence_index.py for version-bound evidence records, notification_state.py for idempotent notification intents, and StateStore outbox claim/complete/recovery methods for bounded external side effects. The tester handoff is documented in docs/multi-agent-dev-v2/12-v2-tester-handoff.md.

## Runtime child dispatch gate

`scripts/runtime_dispatch.py` is a transport-neutral lifecycle/provenance gate for live Codex child threads. It requires child start, child settings, a terminal child event, and an observed model/effort match before a dispatch is admissible. It blocks parent shutdown while the child is active and records `SPAWN_FAILED`, `ROUTE_UNVERIFIED`, or `ROUTE_MISMATCH` instead of silently advancing. This complements, but does not replace, Hook enforcement.
