# Scope control, execution, and audit

## Freeze before writing

Capture in a short task record:

1. User goal verbatim, non-goals, relevant project documents, and each hard constraint ID.
2. Initial commit/worktree status and pre-existing changes; preserve them as baseline.
3. Allowed files/symbols or change types, one writer, dependencies, and acceptance evidence.
4. D/I/A classification with one factual reason per non-default tier; requested route and current provenance status.

An allowed file is not permission for unrelated behavior inside it. “Do not add variables” or “reuse this exact method” is an explicit contract and must be checked against the complete diff and symbols, including renames and indirect equivalents.

## Execute and correct continuously

- Make the smallest change supported by the frozen contract and source evidence. Reuse existing types, variables, algorithms, and tests when semantically appropriate.
- After each coherent step, inspect the diff against the goal, non-goals, hard constraints, and allowed boundary. Do not postpone drift detection until the end.
- On an unsupported assumption, conflicting document, scope drift, unexpected variable/method/API, repeated no-evidence loop, or route mismatch, stop only the affected path. Record the evidence and choose: bounded correction, evidence request, contract return, or user decision.
- A corrector may change only the authorized implementation. If the correction changes contract, scope, or acceptance, return to Main for a new frozen revision before further writing.
- Handoff requires confirmation that the prior writer stopped and no write is in flight. Never assign overlapping write boundaries concurrently.

## Freeze and audit

Freeze the exact diff/version before audit. Give the auditor the original request, project rules, frozen contract, baseline and changed files, tests/evidence, and known limitations—not the author's preferred conclusion or a suggested repair. The auditor must be a different agent/person and read-only.

The auditor checks:

- user/project scope and every hard constraint against actual diff and symbols;
- no unrequested features, redundant variables/methods, unnecessary renames, parallel logic, or unrelated formatting/dependencies;
- source mapping and deviations where reuse is required;
- expected behavior, negative/error/recovery paths, and independent test evidence;
- requested vs actual route, Hook status vs provenance, and all unsupported claims;
- baseline preservation and secret/privacy exposure.

Return one of `PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE`, with exact file/symbol/test evidence. Missing evidence is not a pass. The auditor never edits the reviewed version or self-approves a repair.

## Rejection loop and release

For `FAIL`, assign a bounded fix to the writer. For `INSUFFICIENT_EVIDENCE`, gather the missing evidence or state a real blocker; do not change code merely to silence the finding. Freeze a new version and have the independent auditor re-review it. Keep a compact issue ledger so the same no-evidence attempt is not repeated.

Release only when required tests and the independent audit pass, with any route uncertainty explicitly separated from functional acceptance. If independent audit, runtime provenance, or another required gate is unavailable, report exactly which gate remains open; do not label the result accepted. Never use successful tests to excuse scope violations.
