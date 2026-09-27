# Guard and audit boundaries

Deterministic Guard checks schema, paths, manifest binding, lease and fencing tokens, revision, required evidence and side-effect policy. Semantic Guard is read-only and emits ALLOW, WARN, BLOCK or NEEDS_USER_DECISION with reason codes.

A worker HandoffPacket must have audit_receipt=null. It must include a result revision, diff or artifact hash, test receipts, next allowed actions and no unresolved open questions for SUCCEEDED status.

Independent Audit reads a frozen target and writes an AuditReceipt bound to:

- target manifest hash;
- target task result revision;
- target diff hash;
- auditor identity distinct from writer and task owner.

PASS permits the controller to move AUDIT_PENDING to ACCEPTED, subject to target binding. HOLD, REJECT, or DEGRADED remain visible and do not silently advance acceptance. Missing runtime route evidence stays ROUTE_UNVERIFIED; a route mismatch is a blocking finding.
