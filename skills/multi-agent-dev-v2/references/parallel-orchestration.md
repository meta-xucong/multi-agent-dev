# Controlled parallel orchestration

The main session owns user intent, scope freeze, authorization, integration and reporting. The SQLite Controller is the only state writer and owns DAG scheduling, controller epoch, CAS, leases, retry budget and recovery. Workers return facts and never edit the ledger.

## Lifecycle

1. Freeze a ScopeManifest and compute its hash.
2. Add immutable TaskSpecs with disjoint write sets and namespaces.
3. Dispatch only ready tasks; acquire all namespace leases atomically.
4. Bind start, checkpoint, and submit a HandoffPacket.
5. Deterministic/Semantic Guard evaluates the packet.
6. An independent auditor binds an AuditReceipt to manifest, result revision and diff hash.
7. Only accepted tasks can make the Run READY_TO_MERGE.

PLANNED, RETRYABLE, LEASED, RUNNING, CHECKPOINTED, WAITING_HANDOFF, AUDIT_PENDING and ACCEPTED are task states. HANDOFF_READY is evidence, not a persisted state.

Use scripts/orchestrate.py with one JSON request per invocation. Keep the state database private to the run. External side effects are written to the outbox first, then claimed and completed by a separate notifier.
