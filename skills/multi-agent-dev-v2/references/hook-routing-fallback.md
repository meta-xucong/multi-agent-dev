# Hook and routing fallback

## Keep two facts separate

**Hook status** is `HOOK_ENFORCED`, `HOOK_UNAVAILABLE`, or `HOOK_UNVERIFIED`. Only a fresh runtime probe of the exact dispatch tool can establish `HOOK_ENFORCED`: an allowed route is corrected as contracted, an invalid route is rejected before creation, and unrelated tools pass transparently. A registered Hook or its receipt alone is insufficient.

**Route provenance** is `PROFILE_VERIFIED`, `EXPLICIT_ROUTE_VERIFIED`, `ROUTE_UNVERIFIED`, or `ROUTE_MISMATCH`. Only independent runtime metadata showing both model and effort establishes a verified route. Requested arguments, TOML contents, task names, agent self-report, and Hook receipts do not.

These axes are independent. `HOOK_ENFORCED` does not prove route provenance; `HOOK_UNAVAILABLE` does not imply an automatic model switch.

## Safe fallback

Prefer a profile proven to load on this exact dispatch tool. If unavailable, use explicit model/effort only when that route has actual runtime provenance. Keep hooks optional. If no route has provenance, mark `ROUTE_UNVERIFIED` and continue only bounded work that does not require that route; do not treat the unknown agent as qualified for required independent audit. If actual metadata proves a mismatch, mark `ROUTE_MISMATCH` and do not use that work as compliant evidence. Re-dispatch only through a verified path; otherwise stop the dependent gate and explain the smallest blocker.

The current package intentionally does not register a route Hook: the current specialized dispatch path has not passed a fresh rewrite/reject/transparent-pass probe. Re-test after a Codex/tool update before creating or registering a V2 PreToolUse route Hook. Do not edit the user's global config or trust a Hook automatically.

Custom-agent TOML templates in `../profiles/` are inert until manually reviewed and installed. Installation does not establish discovery, precedence, or actual runtime use. V2's route-contract helper is a deterministic format/consistency validator, not a guard and not a runtime detector.
