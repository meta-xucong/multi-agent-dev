# Role and route rules

## Logical roles

| Role | Responsibility | Write access |
| --- | --- | --- |
| Main | Read project rules, freeze contract, classify D/I/A, coordinate one writer, correct drift, integrate and report | Owns orchestration; implementation only when explicitly acting as the sole writer |
| Think | Resolve a material design/source/contract/acceptance ambiguity; return the minimum decision and risks | Read-only; no code, tests, or scope expansion |
| Execute | Implement the frozen contract and targeted tests in its owned boundary | One writer at a time; no public semantic or acceptance changes |
| Audit | Independently compare a fixed version with requirements, diff, tests, and evidence | Read-only; cannot repair or approve its own changes |

Do not keep all roles running permanently. Skip Think when D0; do not create a second Main. If independent dispatch is unavailable, state that audit is not independent.

## D/I/A classification

- **D0 / D1 — design ambiguity.** D0 means goal, source semantics, implementation method, contract, and acceptance are clear. D1 means a real unresolved choice could change one of those. Task size alone is not D1. D1 invokes Think before the contract is frozen.
- **I0 / I1 / I2 / I3 — implementation difficulty.** I0 requires an exact bounded change, known files/symbols, no public/high-consequence semantic changes, located source when required, and a test that requires no invented behavior. I1 is normal implementation under a frozen contract. I2 requires a concrete cross-module invariant, interacting failure/recovery branches, competing causal paths, or steps not directly derivable from existing implementation. I3 is exceptional: an I2 issue has resisted evidence-producing attempts without changing scope, and a human rechecks before the highest tier.
- **A0 / A1 / A2 — audit risk.** A0 is localized behavior; A1 covers cross-module invariants, recovery paths, source equivalence, or strict negative constraints; A2 covers security, permissions, billing, persistence, public contracts, secrets/privacy, or another project-declared critical gate.

File count, task size, a routine failure, or an agent asking for more effort is not an upgrade reason. Record one concise factual trigger. Reclassify downward when the difficult issue is resolved.

## Fixed route matrix

| Role/profile | Requested model | Requested effort | Use |
| --- | --- | --- | --- |
| Think `madv2_think_sol_xhigh` | `gpt-6-sol` | `xhigh` | D1 only; isolated reasoning task |
| Execute I0 `madv2_execute_i0_luna_low` | `gpt-6-luna` | `low` | Every I0 admission condition is evidenced |
| Execute I1 `madv2_execute_i1_luna_high` | `gpt-6-luna` | `high` | Normal frozen-contract work |
| Execute I2 `madv2_execute_i2_luna_xhigh` | `gpt-6-luna` | `xhigh` | A specific I2 trigger is recorded |
| Execute I3 `madv2_execute_i3_luna_max` | `gpt-6-luna` | `max` | Exceptional, human-reviewed I3 only |
| Audit A0 `madv2_audit_a0_luna_high` | `gpt-6-luna` | `high` | Default independent audit |
| Audit A1 `madv2_audit_a1_luna_xhigh` | `gpt-6-luna` | `xhigh` | Deep cross-boundary/constraint audit |
| Audit A2 `madv2_audit_a2_luna_max` | `gpt-6-luna` | `max` | Critical acceptance gate |

The current main session's suggested setting is Luna/high, but this skill cannot change it. Sol is reserved for Think. Never silently substitute a model or effort. See matching TOML templates in `../profiles/`.

## Dispatch contract

The optional pure helper `../scripts/route_contract.py` builds/parses the first non-empty marker line:

```text
MAD_ROUTE_V2 {"role":"execute","design_ambiguity":"D0","implementation":"I1","audit_risk":"A0","stage":"CONTRACT_FROZEN","profile_id":"madv2_execute_i1_luna_high","task_id":"task-001","contract_rev":"v2.0.0-route-contract"}
```

The marker is routing intent only. It is not a Hook receipt, proof of profile discovery, or runtime model provenance. Role-stage bindings are fixed: Think → `PRE_CONTRACT` and D1; Execute → `CONTRACT_FROZEN` and D0; Audit → `VERSION_FROZEN` and D0. Profile ID must agree with the corresponding I or A tier. Reject malformed, duplicate-key, unknown-field, unsafe task-id, wrong-stage, wrong-profile, and wrong-contract inputs. Unmarked unrelated messages are not errors for the helper.

At every dispatch record the requested profile/explicit model-effort separately from the actual runtime provenance status: `PROFILE_VERIFIED`, `EXPLICIT_ROUTE_VERIFIED`, `ROUTE_UNVERIFIED`, or `ROUTE_MISMATCH`. A profile file or returned receipt is not provenance.
