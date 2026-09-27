#!/usr/bin/env python3
"""Deterministic dependency scheduler; only the controller calls write methods."""
from __future__ import annotations
import json
from typing import Any
from lease_store import LeaseStore, LeaseError
from state_store import StateStore, StateError

_ACTIVE={"LEASED","RUNNING","CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING"}

def _paths_conflict(left, right):
    for raw_a in left:
        for raw_b in right:
            a,b=raw_a.casefold(),raw_b.casefold()
            if a==b or a.startswith(b+"/") or b.startswith(a+"/"):
                return True
    return False

class Scheduler:
    def __init__(self, state: StateStore, leases: LeaseStore): self.state,self.leases=state,leases
    def ready(self, run_id: str) -> list[dict[str,Any]]:
        run=self.state.get_run(run_id)
        if not run: raise StateError("unknown run")
        if run["state"] not in {"DISPATCHABLE","RUNNING"}:
            raise StateError("run is not dispatchable")
        tasks=self.state.list_tasks(run_id); by={t["task_id"]:t for t in tasks}
        active_items=[t for t in tasks if t["state"] in _ACTIVE]
        active=len(active_items)
        manifest=json.loads(run["manifest_json"]); limit=min(int(manifest.get("concurrency_limit",2)),int(manifest.get("total_agent_limit",4)))
        if active>=limit: return []
        reserved=[tuple(t["spec"].get("write_set",())) for t in active_items]
        ready=[]
        for item in tasks:
            if item["state"] not in {"PLANNED","RETRYABLE"}: continue
            deps=item["spec"].get("dependency_ids",[])
            if not all(d in by and by[d]["state"]=="ACCEPTED" for d in deps): continue
            writes=tuple(item["spec"].get("write_set",()))
            if any(_paths_conflict(writes,held) for held in reserved): continue
            ready.append(item); reserved.append(writes)
            if len(ready)>=max(0,limit-active): break
        return ready

    def dispatch_next(self, run_id: str, owner: str, controller_epoch: int) -> list[dict[str,Any]]:
        results=[]
        for item in self.ready(run_id):
            namespaces=item["spec"].get("namespace") or ["task:"+item["task_id"]]
            try:
                bundle=self.leases.acquire_many(run_id,item["task_id"],namespaces,owner,controller_epoch)
            except LeaseError:
                continue
            results.append({"task_id":item["task_id"],"lease":bundle[0],"leases":bundle,"spec":item["spec"]})
        return results

    def can_ready_to_merge(self, run_id: str) -> tuple[bool,list[str]]:
        tasks=self.state.list_tasks(run_id); blockers=[]
        for item in tasks:
            if item["state"]!="ACCEPTED":
                blockers.append(item["task_id"]+":"+item["state"]); continue
            receipts=self.state.list_receipts(item["task_id"])
            if not receipts or receipts[-1]["decision"]!="PASS":
                blockers.append(item["task_id"]+":AUDIT_REQUIRED"); continue
            receipt=json.loads(receipts[-1]["receipt_json"])
            try:
                self.state.validate_audit_receipt_binding(receipt)
            except (StateError, ValueError) as exc:
                blockers.append(item["task_id"]+":AUDIT_BINDING_REQUIRED")
                continue
            provenance=receipt.get("provenance",{})
            if (any(receipt.get(key)!="PASS" for key in ("scope_result","behavior_result","evidence_result")) or receipt.get("route_result") not in {"PROFILE_VERIFIED","EXPLICIT_ROUTE_VERIFIED"} or provenance.get("hook_status") not in {"HOOK_ENFORCED","HOOK_VERIFIED"} or provenance.get("source") not in {"codex-runtime","profile-runtime","hook-runtime"} or not provenance.get("observed_model") or not provenance.get("observed_effort") or not provenance.get("evidence_refs") or receipt.get("required_corrections")):
                blockers.append(item["task_id"]+":AUDIT_PROVENANCE_REQUIRED")
        return (not blockers,blockers)
