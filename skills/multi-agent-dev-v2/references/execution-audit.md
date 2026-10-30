# Scope, execution, and optional audit

The `Scope discipline` section in the parent `SKILL.md` controls this workflow. This reference must not be used to add gates or checks that the request and project do not require.

## Before writing

Understand the requested outcome, relevant project instructions, actual call path, and existing implementation. Inspect the working tree when needed to avoid overwriting existing user work. Keep a concise scope note only when delegation or a multi-step task makes one useful; do not create a task record, enumerate artificial non-goals, or freeze allowed files for a simple change.

## Implement and validate

- Make the smallest sufficient change using project conventions and existing mechanisms.
- Add a fallback only with verified evidence for its existing consumer, call path, and dependency on that exact behavior.
- Add edge-case handling only for a reachable, verified P0 scenario under the project's established criteria.
- Run project-required checks and the minimum additional validation tied to the requested behavior. Do not generate or verify hashes/checksums unless explicitly requested.
- If an assumption proves unsupported, omit the dependent behavior and continue the rest of the requested work where possible. Ask only when the unresolved point materially prevents the requested outcome.

## Independent audit (conditional)

Use a separate read-only auditor when the user requests one or an existing project acceptance rule requires one. Otherwise, a concise self-review of the changed behavior and diff is sufficient for routine work. Do not turn audit into a general security review or require route/provenance evidence unless the requested outcome or project rule depends on it.

When an audit is required, bind it to the actual request and changed version, and ask it to identify only concrete scope violations, behavior defects, or missing required evidence. It may return `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE`; do not demand evidence unrelated to the acceptance criteria. A failed finding should lead to the smallest correction supported by the request. Missing optional evidence is not a blocker.
