#!/usr/bin/env python3
"""Deterministic Guard decisions and fail-closed reason codes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from parallel_manifest import ContractError, ROUTE_STATUSES, HOOK_STATUSES

HARD={"SCOPE_DRIFT","WRITE_CONFLICT","LEASE_STALE","UNKNOWN_WRITER","INVALID_STAGE","CONTRACT_MISMATCH","MISSING_EVIDENCE","UNSAFE_SIDE_EFFECT","ROUTE_MISMATCH","AUDIT_REQUIRED","BUDGET_EXHAUSTED"}
SOFT={"ROUTE_UNVERIFIED","HOOK_UNVERIFIED","BUDGET_NEAR_LIMIT","OPTIONAL_CHECK_UNRUN","RETRY_WITHOUT_NEW_EVIDENCE"}
DECISIONS={"ALLOW","WARN","BLOCK","NEEDS_USER_DECISION"}
@dataclass(frozen=True)
class GuardDecision:
    guard_id: str; target_type: str; target_id: str; manifest_hash: str; state_revision: int
    decision: str; reason_codes: tuple[str,...]; findings: tuple[str,...]; evidence_refs: tuple[str,...]
    checked_paths: tuple[str,...]; checked_diff_hash: str; route_status: str; hook_status: str; created_at: str
    def __post_init__(self):
        if self.decision not in DECISIONS: raise ContractError("invalid guard decision")
        if any(code not in HARD|SOFT for code in self.reason_codes): raise ContractError("unknown guard reason")
        if self.route_status not in ROUTE_STATUSES or self.hook_status not in HOOK_STATUSES: raise ContractError("invalid guard provenance")
        if self.decision=="ALLOW" and any(code in HARD for code in self.reason_codes): raise ContractError("hard finding cannot allow")
    def as_dict(self)->dict[str,Any]:
        return {"guard_id":self.guard_id,"target_type":self.target_type,"target_id":self.target_id,"manifest_hash":self.manifest_hash,"state_revision":self.state_revision,"decision":self.decision,"reason_codes":list(self.reason_codes),"findings":list(self.findings),"evidence_refs":list(self.evidence_refs),"checked_paths":list(self.checked_paths),"checked_diff_hash":self.checked_diff_hash,"route_status":self.route_status,"hook_status":self.hook_status,"created_at":self.created_at}

def decide(reason_codes: list[str], retry_count: int=0, route_status: str="ROUTE_UNVERIFIED", hook_status: str="HOOK_UNVERIFIED") -> str:
    codes=set(reason_codes)
    if "RETRY_WITHOUT_NEW_EVIDENCE" in codes and retry_count>=1: return "NEEDS_USER_DECISION"
    if codes & HARD: return "BLOCK"
    if codes: return "WARN"
    return "ALLOW"
