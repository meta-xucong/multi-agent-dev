#!/usr/bin/env python3
"""Separate requested route from observed runtime provenance."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from parallel_manifest import ROUTE_STATUSES, HOOK_STATUSES, ContractError

@dataclass(frozen=True)
class RouteProvenance:
    requested_model: str
    requested_effort: str
    route_status: str="ROUTE_UNVERIFIED"
    hook_status: str="HOOK_UNVERIFIED"
    observed_model: str|None=None
    observed_effort: str|None=None
    source: str=""
    evidence_refs: tuple[str,...]=()
    def __post_init__(self):
        if self.route_status not in ROUTE_STATUSES: raise ContractError("invalid route status")
        if self.hook_status not in HOOK_STATUSES: raise ContractError("invalid hook status")
        if self.route_status=="PROFILE_VERIFIED" and not (self.observed_model and self.observed_effort): raise ContractError("profile verification needs observed provenance")
    def as_dict(self)->dict[str,Any]:
        return {"requested_model":self.requested_model,"requested_effort":self.requested_effort,"route_status":self.route_status,"hook_status":self.hook_status,"observed_model":self.observed_model,"observed_effort":self.observed_effort,"source":self.source,"evidence_refs":list(self.evidence_refs)}
    @classmethod
    def unavailable(cls, model: str, effort: str, hook_status: str="HOOK_UNVERIFIED"): return cls(model,effort,"ROUTE_UNVERIFIED",hook_status)

def compare_requested_observed(requested_model: str, requested_effort: str, observed_model: str|None, observed_effort: str|None, source: str, evidence_refs: tuple[str,...]=()):
    if not observed_model or not observed_effort: return RouteProvenance.unavailable(requested_model,requested_effort)
    status="EXPLICIT_ROUTE_VERIFIED" if (requested_model==observed_model and requested_effort==observed_effort) else "ROUTE_MISMATCH"
    return RouteProvenance(requested_model,requested_effort,status,"HOOK_UNVERIFIED",observed_model,observed_effort,source,evidence_refs)
