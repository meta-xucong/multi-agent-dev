#!/usr/bin/env python3
"""Structured worker handoff facts; workers cannot self-approve."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from parallel_manifest import ContractError, ROUTE_STATUSES, HOOK_STATUSES, validate_path

STATUSES={"SUCCEEDED","INCOMPLETE","BLOCKED","FAILED","CANCELLED","UNKNOWN"}
@dataclass(frozen=True)
class HandoffPacket:
    task_id: str; run_id: str; attempt_id: str; manifest_hash: str; state_revision: int
    lease_id: str; base_revision: str; result_revision: str; status: str
    changed_paths: tuple[str,...]; diff_hash: str; artifact_hashes: tuple[str,...]
    test_receipts: tuple[dict[str,Any],...]; evidence_refs: tuple[str,...]
    audit_receipt: dict[str,Any]|None; route_provenance: dict[str,Any]
    hook_status: str; guard_decision: str; assumptions: tuple[str,...]
    open_questions: tuple[str,...]; next_allowed_actions: tuple[str,...]; budget_usage: dict[str,Any]
    write_set: tuple[str,...]=()
    lease_fencing_tokens: dict[str,int]|None=None
    def __post_init__(self):
        if self.status not in STATUSES: raise ContractError("invalid handoff status")
        if self.audit_receipt is not None: raise ContractError("worker handoff audit_receipt must be null")
        if self.route_provenance.get("route_status") not in ROUTE_STATUSES: raise ContractError("invalid route provenance")
        if self.hook_status not in HOOK_STATUSES: raise ContractError("invalid hook status")
        if self.state_revision<0 or not self.task_id or not self.run_id or not self.attempt_id: raise ContractError("invalid handoff identity")
        allowed={validate_path(path) for path in self.write_set}
        changed={validate_path(path) for path in self.changed_paths}
        if not changed<=allowed: raise ContractError("changed path outside write_set")
        if self.status=="SUCCEEDED" and self.open_questions: raise ContractError("succeeded handoff has open questions")
        if self.status=="SUCCEEDED" and not self.test_receipts: raise ContractError("succeeded handoff needs test receipts")
        if self.status=="SUCCEEDED" and any(not isinstance(item,dict) or not isinstance(item.get("command"),str) or not item.get("command") or type(item.get("exit_code")) is not int or item.get("exit_code")!=0 for item in self.test_receipts): raise ContractError("successful handoff requires integer zero-exit test receipts")
        if self.status=="SUCCEEDED" and not self.next_allowed_actions: raise ContractError("succeeded handoff needs next actions")
        if not self.result_revision or not self.diff_hash and not self.artifact_hashes: raise ContractError("handoff result evidence is missing")
        serialized=" ".join(self.assumptions+self.open_questions)
        if any(marker in serialized.lower() for marker in ("api_key","sendkey","password","bearer ","sk-")): raise ContractError("handoff contains secret-like text")
    def as_dict(self):
        return {"task_id":self.task_id,"run_id":self.run_id,"attempt_id":self.attempt_id,"manifest_hash":self.manifest_hash,"state_revision":self.state_revision,"lease_id":self.lease_id,"base_revision":self.base_revision,"result_revision":self.result_revision,"status":self.status,"changed_paths":list(self.changed_paths),"diff_hash":self.diff_hash,"artifact_hashes":list(self.artifact_hashes),"test_receipts":list(self.test_receipts),"evidence_refs":list(self.evidence_refs),"audit_receipt":None,"route_provenance":self.route_provenance,"hook_status":self.hook_status,"guard_decision":self.guard_decision,"assumptions":list(self.assumptions),"open_questions":list(self.open_questions),"next_allowed_actions":list(self.next_allowed_actions),"budget_usage":self.budget_usage,"write_set":list(self.write_set),"lease_fencing_tokens":self.lease_fencing_tokens}

def validate_controller_handoff(packet: HandoffPacket, current_manifest_hash: str) -> None:
    if packet.manifest_hash!=current_manifest_hash: raise ContractError("manifest hash mismatch")
    if packet.status!="SUCCEEDED": raise ContractError("handoff not successful")
    if packet.guard_decision in {"BLOCK","NEEDS_USER_DECISION"}: raise ContractError("guard does not allow handoff")
    if packet.route_provenance.get("route_status")=="ROUTE_MISMATCH": raise ContractError("route mismatch")
    if not packet.diff_hash and not packet.artifact_hashes: raise ContractError("missing result hash")
