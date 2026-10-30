---
name: multi-agent-dev-v2
description: "按 D/I/A 风险轴组织主控、按需思考、最小执行和独立审计，强调文档边界、持续纠偏与证据放行；适用于用户要求按多 Agent 开发流程实施或审查任务。普通编码、解释或概念讨论不触发。"
---

# Multi-agent development V2

Use this workflow for multi-agent implementation or audit requests. Follow the user's latest instructions and the target project's `AGENTS.md`, contracts, and development documents first. This skill never expands scope or authorizes commits, pushes, deployment, paid calls, or external changes.

## Scope discipline — highest-priority operating rule

Implement only the user's explicit request. Inspect the actual project and call path, follow its conventions, reuse existing mechanisms, and make the smallest sufficient change. Do not prepare for hypothetical future requirements or add speculative abstractions, defensive layers, duplicate safeguards, or unrelated cleanup.

- **No hash work by default:** Do not generate or verify SHA, hashes, checksums, fingerprints, or equivalent integrity digests unless the user explicitly requests it. Do not select an orchestration path whose required operation would do this implicitly.
- **Fallbacks need a proven consumer:** Add a fallback only when project evidence identifies the existing downstream consumer, its call path, and why it depends on that exact behavior. If any part is unverified, omit the fallback.
- **Edge cases need verified P0 impact:** Add special handling only for a reachable failure scenario that meets the project's already-established P0 criteria and has major impact. Do not invent or inflate severity; omit hypothetical and non-P0 handling.
- **Validation stays proportional:** Run required project checks and the minimum additional validation that verifies the requested behavior. Do not add or run redundant checks without a concrete task-related reason.
- **No self-authorized expansion:** “Best practice,” extra safety, or assumed future risk is not authorization. Leave optional work out and continue the requested task.

These rules take precedence over optional mechanisms, generic checklists, and conflicting conventions elsewhere in this skill or project. Follow project instructions for the requested behavior within these constraints; hash/SHA/checksum generation or verification still requires the user's explicit request. Do not turn these rules into extra forms, gates, or user interruptions.

### Periodic scope review

While this skill is active, after every three user turns (counting the initiating request), briefly compare the work so far with the rules above and the user's latest scope. Repeat immediately after a user correction or scope change. This is an internal review only: no report, checklist artifact, extra audit, or pause is needed unless the review finds actual drift. If drift exists, stop only that out-of-scope work, undo it when safe, and continue the requested task.

### Scope monitor

For active implementation or audit work under this skill, use one read-only scope-monitor subagent when subagents are available and delegation is permitted. Start the interval at task start; at a natural coordination point, launch the first review after about five minutes, then launch or reuse it about five minutes after the previous review started. Review before delivery even if the task finishes sooner. On a user correction or scope change, notify it and review the updated scope at the next available point. Do not run overlapping monitor reviews. Pass the original request, subsequent scope changes, relevant project instructions, and the actual changed files or proposed action; read [scope-monitor.md](references/scope-monitor.md) for the handoff and correction procedure.

The monitor reports concrete scope violations to Main, which pauses only the affected path at the next opportunity, checks the evidence, coordinates the smallest correction, and asks the monitor to recheck that finding. Resume the paused work automatically once corrected. Continue independent work where possible. This is a scope check, not a general audit. If a monitor cannot be started, report that limitation honestly; do not claim independent monitoring.

The five-minute interval is best effort during active work: check elapsed time at coordination points, not through a polling loop. A subagent message cannot guarantee interruption of an in-flight tool call or work while the session is idle. Do not add a timer, Hook, external scheduler, or persistent state solely for this monitor.

Load reference files only when their mechanism is relevant: [role-routing.md](references/role-routing.md) for requested delegation, [execution-audit.md](references/execution-audit.md) for a requested or project-required audit, [hook-routing-fallback.md](references/hook-routing-fallback.md) for an explicitly required route, and [long-task-and-notification.md](references/long-task-and-notification.md) for long-task recovery or an explicitly requested notification. For installation, see [README.md](README.md).

Use the lightest workflow that fits the request. If the user asks for multi-agent execution, use only the delegation needed to carry it out; otherwise the main session owns implementation and integration unless the user requests delegation or a project instruction requires it. Invoke a thinker only for a material unresolved design ambiguity. Keep one writer at a time when delegating. Independent audit is not a default gate for routine, localized work; use it when requested or required by an established project acceptance rule. Never claim an audit that did not occur.

For delegated work, give the writer a concise statement of the requested outcome, explicit constraints, relevant files or call paths, and the evidence needed to verify that outcome. Do not require exhaustive manifests, invented non-goals, risk tiers, or route records for a simple task. Compare changes to the actual request as you work. Stop only the affected path when it relies on an unsupported assumption; continue independent requested work.

Model/profile files express requested configuration, not proof of runtime use. Never claim a model or effort was used without evidence. Route provenance is relevant only when the user or project explicitly requires a particular route; missing route evidence must not block unrelated requested implementation.

Load context-lean only for long, multi-phase, high-volume, handoff-heavy, or context-degraded work. Lifecycle registration, Hooks, and ServerChan notifications are optional external mechanisms: use them only when the user explicitly requests them or the project explicitly requires them. Do not add an external notification or registration as a default terminal step.


The V2.1 controller and its hash-bound manifests, receipts, and evidence index are an optional advanced implementation path, not the default workflow. Do not invoke them unless the user explicitly asks for that controller workflow and authorizes its required hash operations. For ordinary tasks, work directly in the project using its existing process.

For the optional controller workflow, read [parallel-orchestration.md](references/parallel-orchestration.md), [guard-and-audit.md](references/guard-and-audit.md), and [model-effort-routing.md](references/model-effort-routing.md).

For live child-thread dispatch, read [runtime-dispatch.md](references/runtime-dispatch.md) only when that dispatch mechanism is requested. Do not use it as a default gate for routine work. The helper `scripts/runtime_dispatch.py` is an optional transport-specific mechanism and may perform hash-bound checks; do not run it without explicit authorization for those operations.
