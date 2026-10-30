# Optional controller-based parallel orchestration

Use this document only when the user explicitly requests the V2.1 controller workflow. It is not the default for ordinary implementation or review. The parent `SKILL.md` scope discipline remains controlling.

The controller currently uses SHA-256 hashes for manifests, task bindings, diffs, and audit receipts. Do not invoke it unless the user explicitly authorizes those hash operations. A request to implement a feature or use multi-agent work alone does not authorize hash generation or verification.

When explicitly authorized, follow the controller's existing CLI and project documentation. Keep write ownership and task boundaries clear, but define only the task structure needed for the requested work. Do not introduce additional guards, retries, recovery cases, evidence records, or audit steps unless the user or existing project requirements call for them.

Controller records and local probes establish only what they directly observe. Do not infer live Hook, profile, model, effort, or external-service behavior without evidence when the requested workflow depends on it. If it does not depend on those facts, proceed without collecting them.
