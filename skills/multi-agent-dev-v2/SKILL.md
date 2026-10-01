---
name: multi-agent-dev-v2
description: "按 D/I/A 风险轴组织主控、按需思考、最小执行和独立审计，强调文档边界、持续纠偏与证据放行；适用于用户要求按多 Agent 开发流程实施或审查任务。普通编码、解释或概念讨论不触发。"
---

# Multi-agent development V2

Use this workflow for multi-agent implementation or audit requests. Follow the user's latest instructions and the target project's `AGENTS.md`, contracts, and development documents first. This skill never expands scope or authorizes commits, pushes, deployment, paid calls, or external changes.

Before implementation, load [role-routing.md](references/role-routing.md), [execution-audit.md](references/execution-audit.md), [hook-routing-fallback.md](references/hook-routing-fallback.md), and [long-task-and-notification.md](references/long-task-and-notification.md). For installation, see [README.md](README.md).

For source-driven migrations, compatibility work, or tasks that name a GitHub/history prototype, also load [source-fidelity.md](references/source-fidelity.md). Freeze the reference commit, source manifest, mapping matrix, target baseline, and source-sensitive implementation TaskSpec before writing. Main must dispatch a distinct read-only-requested `source_fidelity` sidecar child (A1 by default, A2 for provider/billing/security/public-contract work) against the writer's frozen output revision, before formal handoff. This sidecar is not a controller DAG TaskTemplate: making it a dependency would deadlock because the implementation handoff itself is gated on its receipt. The controller does not infer user intent or auto-dispatch the child; Main owns both decisions. The implementation TaskSpec remains marked `source_fidelity_required`, and its handoff/integration is fail-closed unless an independent, same-version `SourceFidelityReceipt` has status `PASS` and is bound to a matching terminal source-role runtime dispatch. Runtime evidence currently observes model/effort/lifecycle, not actual sandbox; evidence is not cryptographically signed, so use only a trusted app-server event source and do not claim stronger provenance than observed.

The main session owns baseline, scope freeze, role selection, writer handoff, correction, integration, and reporting. Invoke a thinker only for a material unresolved design ambiguity. Keep one writer at a time. Every implementation requiring acceptance gets a separate read-only auditor; if no independent auditor can be started, report self-review only and do not claim independent acceptance.

When a frozen reference prototype is in scope, the Source Fidelity child is mandatory in addition to the ordinary Audit. It may only inspect the frozen source, target diff, mapping matrix, and tests; it must not edit, repair, reinterpret the mapping, or approve its own findings. Its receipt is a correction signal: the Main stops the affected path, assigns a bounded correction to the writer, and re-runs Source Fidelity on the new version before ordinary Audit.

Freeze the user's goal, non-goals, hard constraints, allowed files, acceptance evidence, D/I/A classification, and current route evidence before dispatch. Compare each change against that frozen contract during implementation. Stop the affected path on drift or an unsupported assumption. An auditor returns `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE`; failures loop back to bounded correction or evidence collection, then a new fixed-version review.

Model/profile files express requested configuration, not proof of runtime use. Keep Hook state separate from actual route provenance. Never claim a model or effort was used without independent runtime metadata. When route evidence is absent, continue only work that does not depend on the unverified route and report the limitation.

Load context-lean only for long, multi-phase, high-volume, handoff-heavy, or context-degraded work. If the optional lifecycle Hook has been installed and its exact event paths verified, request local active-session registration at task start and reuse that task ID for the terminal notification. Otherwise do not claim interruption fallback is active. Send one ServerChan notification for each terminal outcome using the bundled notifier; task ID is optional and local-only; `done` requires concrete verification. Do not add a machine-readable terminal marker to the visible assistant response.


V2.1 adds a persistent controller core under scripts/: canonical manifests and TaskSpecs, SQLite CAS/event/outbox state, fenced multi-namespace leases, dependency scheduling, retry and recovery, structured handoff, Deterministic/Semantic Guard, independent AuditReceipt binding, evidence indexing, notification intents, worker adaptation, and the JSON orchestration CLI. Only the controller may call write-capable operations; worker adapters return artifacts and evidence. The CLI and isolated SQLite probes are implementation evidence, not live Codex Hook/Profile/model provenance.

For operational detail, read [parallel-orchestration.md](references/parallel-orchestration.md), [guard-and-audit.md](references/guard-and-audit.md), and [model-effort-routing.md](references/model-effort-routing.md).

For live child-thread dispatch, also read [runtime-dispatch.md](references/runtime-dispatch.md). Keep the parent alive until the child is terminal, collect observed model/effort from child runtime settings, compare it with the frozen TaskSpec, and block when the child ID, provenance, or terminal event is missing. The transport-neutral helper is `scripts/runtime_dispatch.py`; it does not replace a Codex Hook and does not treat model-generated spawn arguments as observed provenance.
