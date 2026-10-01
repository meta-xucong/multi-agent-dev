# Source Fidelity Agent

`Source Fidelity Agent` is a separate read-only sidecar child role. It compares a frozen GitHub repository commit, tag, historical version, or local prototype with a frozen target revision. It is not the general Audit role and never edits code, tests, scope, mappings, or acceptance criteria. Main dispatches it through the `source_fidelity` runtime route; it is deliberately not a Controller DAG `TaskTemplate`, because requiring its receipt for writer handoff while scheduling it only after that handoff would deadlock. Reusing the general Audit profile or treating a worker self-report as source evidence is non-compliant.

## When it is required

Use it when the user requires strict migration, compatibility, maximal reuse, or behavior derived from a named repository/version. Skip it for genuinely new platform behavior with no reference prototype. Trigger it at reference freeze, source-sensitive diffs, integration, and final acceptance; stay quiet when no relevant state changed.

## Frozen inputs

Create a `ReferenceSpec` with repository/path, immutable commit/tag, submodule policy, source files/symbols/tests, source manifest hash, target root, target baseline, run/task IDs, changed paths, and a `SourceMappingMatrix`. Read reference files only; do not execute repository hooks, installers, build scripts, or provider calls. Local reference roots must be canonical non-symlink directories. A missing commit/file/manifest is `REFERENCE_UNVERIFIED` or `INSUFFICIENT_EVIDENCE`, never `PASS`.

Each mapping class is one of:

- `DIRECT_REUSE`: conservative structural and fragment checks are required.
- `THIN_ADAPTER`: only explicit boundary additions are allowed.
- `PLATFORM_SHELL`: auth/workspace/storage/queue/audit additions require explicit authorization and must not alter source semantics.
- `AUTHORIZED_NEW`: explicit user/contract authorization is required.

Unmapped changed paths, unapproved identifiers/renames, deleted source symbols, new thresholds/fallbacks/branches, source gaps, and source/contract conflicts are blockers. If the checker cannot prove a semantic property for the language, it returns `INSUFFICIENT_EVIDENCE` rather than guessing.

## Receipt and controller gate

The checker is `scripts/source_fidelity.py`. It independently hashes the frozen reference and target trees, checks mapped files/symbols/fragments and conservative structural drift, and emits a version-bound `SourceFidelityReceipt`. `SOURCE_FIDELITY_RECEIPT` is a first-class evidence kind.

Main must identify source-sensitive tasks during scope freeze and set `source_fidelity_required=true`; this is a semantic decision based on the user's request and cannot be inferred safely from changed files alone. After the writer completes and freezes a target revision, but before formal handoff, Main dispatches the read-only-requested sidecar with the exact same frozen reference/mapping contract and observes its child lifecycle/route evidence. The runtime route contract binds the `source_fidelity` role to its dedicated A1/A2 profile and rejects a wrong model/effort or non-read-only requested sandbox. It observes model/effort and child lifecycle, but not actual runtime sandbox state. The child is not added to the Controller DAG; the implementation's handoff gate is the mechanical enforcement point. Handoff packets carry source receipt refs and exactly one source-dispatch runtime evidence ref. When recording the returned receipt, Main binds `producer_thread_id` to the child ID from the observed dispatch record; the controller requires this exact match. Semantic Guard, AuditReceipt binding, and `can_ready_to_merge` require `PASS` plus same-run/task/manifest/result/diff/child bindings. A receipt from an earlier target revision cannot authorize a later revision.

`PASS` permits the ordinary independent Audit to run; it does not replace that audit. `WARN`, `BLOCK`, `NEEDS_USER_DECISION`, `INSUFFICIENT_EVIDENCE`, and `REFERENCE_UNVERIFIED` keep the affected path held. The role defaults to Source Fidelity A1 / Luna xhigh and escalates to Source Fidelity A2 / Luna max for provider, billing, security, or public-contract migrations. A source-sensitive implementation cannot formally hand off or integrate until this child returns a same-version `SourceFidelityReceipt` with `PASS` and the matching runtime dispatch evidence is recorded.

Trust boundary: `producer_role`, evidence `source`, and receipt fields are not cryptographic identities. The controller requires a bound Codex app-server child lifecycle/settings record, but authenticity of the supplied app-server event stream depends on the trusted controller/runtime integration. The current adapter cannot prove the child's actual sandbox mode or cryptographically prove which process submitted the receipt. When those facts are required and no trusted event source exists, keep the result `ROUTE_UNVERIFIED`/`INSUFFICIENT_EVIDENCE`; do not describe the evidence as tamper-proof.
