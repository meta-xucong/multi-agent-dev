#!/usr/bin/env python3
"""Validated evidence index records for controller receipts."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any
from parallel_manifest import ContractError, SHA256, validate_id
from state_store import StateStore

KINDS={"TEST_RECEIPT","DIFF_RECEIPT","HASH_RECEIPT","GUARD_RECEIPT","AUDIT_RECEIPT","ROUTE_PROVENANCE","HOOK_PROBE","PROFILE_PROBE","USER_DECISION"}
SECRET_MARKERS=("api_key","sendkey","password","bearer ","sk-")

@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str; run_id: str; kind: str; source: str; manifest_hash: str
    base_revision: str|None; result_revision: str|None; artifact_hash: str|None
    command_or_ui_step: str|None; exit_code: int|None; observed_at: str
    limitations: str; redaction_status: str; task_id: str|None=None
    payload: dict[str,Any]=None

    def __post_init__(self):
        validate_id(self.evidence_id,"evidence_id"); validate_id(self.run_id,"run_id")
        if self.task_id: validate_id(self.task_id,"task_id")
        if self.kind not in KINDS: raise ContractError("invalid evidence kind")
        if not self.source or not self.observed_at or not self.limitations or not self.redaction_status: raise ContractError("incomplete evidence metadata")
        if self.exit_code is not None and type(self.exit_code) is not int: raise ContractError("exit_code must be an integer")
        if self.kind=="TEST_RECEIPT" and type(self.exit_code) is not int: raise ContractError("TEST_RECEIPT exit_code must be an integer")
        if self.artifact_hash and re.fullmatch(SHA256,self.artifact_hash) is None: raise ContractError("invalid artifact hash")
        serialized=" ".join(str(x or "") for x in (self.source,self.command_or_ui_step,self.limitations,self.payload or {})).lower()
        if any(marker in serialized for marker in SECRET_MARKERS): raise ContractError("evidence contains secret-like text")

    def as_dict(self) -> dict[str,Any]:
        return {"evidence_id":self.evidence_id,"run_id":self.run_id,"task_id":self.task_id,"kind":self.kind,"source":self.source,"manifest_hash":self.manifest_hash,"base_revision":self.base_revision,"result_revision":self.result_revision,"artifact_hash":self.artifact_hash,"command_or_ui_step":self.command_or_ui_step,"exit_code":self.exit_code,"observed_at":self.observed_at,"limitations":self.limitations,"redaction_status":self.redaction_status,"payload":self.payload or {}}

class EvidenceIndex:
    def __init__(self,state: StateStore): self.state=state
    def record(self, evidence: EvidenceRecord) -> dict[str,Any]:
        return self.state.record_evidence(evidence.as_dict())
    def for_task(self, task_id: str) -> list[dict[str,Any]]:
        rows=self.state.db.execute("SELECT * FROM evidence WHERE task_id=? ORDER BY observed_at,evidence_id",(task_id,)).fetchall()
        return [dict(row) for row in rows]
