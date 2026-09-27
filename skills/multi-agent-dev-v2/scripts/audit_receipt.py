#!/usr/bin/env python3
"""Independent audit receipt binding target hashes and actor separation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from parallel_manifest import ContractError, ROUTE_STATUSES

DECISIONS={"PASS","HOLD","REJECT","DEGRADED"}
AUDIT_RESULTS={"PASS","FAIL","HOLD","UNVERIFIED","MISSING"}
@dataclass(frozen=True)
class AuditReceipt:
    audit_id: str; auditor_actor: str; target_manifest_hash: str; target_task_id: str
    target_result_revision: str; target_diff_hash: str; scope_result: str; behavior_result: str
    evidence_result: str; route_result: str; findings: tuple[str,...]; required_corrections: tuple[str,...]
    decision: str; provenance: dict[str,Any]; created_at: str; writer_actor: str
    def __post_init__(self):
        if self.decision not in DECISIONS: raise ContractError("invalid audit decision")
        if self.auditor_actor==self.writer_actor: raise ContractError("auditor must differ from writer")
        if self.route_result not in ROUTE_STATUSES: raise ContractError("invalid route result")
        if any(value not in AUDIT_RESULTS for value in (self.scope_result,self.behavior_result,self.evidence_result)): raise ContractError("invalid audit dimension")
        if self.decision=="PASS":
            if any(value!="PASS" for value in (self.scope_result,self.behavior_result,self.evidence_result)): raise ContractError("PASS requires all audit dimensions to PASS")
            if self.route_result not in {"PROFILE_VERIFIED","EXPLICIT_ROUTE_VERIFIED"}: raise ContractError("PASS requires verified route")
            if self.provenance.get("hook_status") not in {"HOOK_ENFORCED","HOOK_VERIFIED"}: raise ContractError("PASS requires verified hook provenance")
            if self.provenance.get("source") not in {"codex-runtime","profile-runtime","hook-runtime"}: raise ContractError("PASS requires runtime provenance source")
            if not self.provenance.get("observed_model") or not self.provenance.get("observed_effort") or not self.provenance.get("evidence_refs"): raise ContractError("PASS requires model, effort and evidence provenance")
            if self.required_corrections: raise ContractError("pass has required corrections")
    def as_dict(self):
        return {"audit_id":self.audit_id,"auditor_actor":self.auditor_actor,"target_manifest_hash":self.target_manifest_hash,"target_task_id":self.target_task_id,"target_result_revision":self.target_result_revision,"target_diff_hash":self.target_diff_hash,"scope_result":self.scope_result,"behavior_result":self.behavior_result,"evidence_result":self.evidence_result,"route_result":self.route_result,"findings":list(self.findings),"required_corrections":list(self.required_corrections),"decision":self.decision,"provenance":self.provenance,"created_at":self.created_at,"writer_actor":self.writer_actor}

def validate_receipt(receipt: AuditReceipt, manifest_hash: str, result_revision: str, diff_hash: str) -> None:
    if receipt.target_manifest_hash!=manifest_hash or receipt.target_result_revision!=result_revision or receipt.target_diff_hash!=diff_hash: raise ContractError("audit target binding mismatch")
    if receipt.decision=="PASS" and receipt.route_result=="ROUTE_MISMATCH": raise ContractError("PASS cannot contain route mismatch")
