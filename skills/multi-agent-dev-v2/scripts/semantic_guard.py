#!/usr/bin/env python3
"""Semantic gate that never advances persistent state by itself."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from guard_contract import GuardDecision, decide
from handoff_contract import HandoffPacket

def inspect_handoff(packet: HandoffPacket, current_manifest_hash: str, retry_count: int=0, source_fidelity_required: bool=False) -> GuardDecision:
    reasons=[]; findings=[]
    if packet.manifest_hash!=current_manifest_hash: reasons.append("SCOPE_DRIFT"); findings.append("manifest hash mismatch")
    if packet.route_provenance.get("route_status")=="ROUTE_MISMATCH": reasons.append("ROUTE_MISMATCH"); findings.append("observed route mismatches requested route")
    elif packet.route_provenance.get("route_status")=="ROUTE_UNVERIFIED": reasons.append("ROUTE_UNVERIFIED"); findings.append("runtime provenance unavailable")
    if packet.hook_status=="HOOK_UNVERIFIED": reasons.append("HOOK_UNVERIFIED")
    if packet.status!="SUCCEEDED": reasons.append("MISSING_EVIDENCE")
    if packet.open_questions: reasons.append("MISSING_EVIDENCE"); findings.append("open questions remain")
    if not packet.changed_paths and not packet.artifact_hashes: reasons.append("MISSING_EVIDENCE")
    if source_fidelity_required:
        if packet.source_fidelity_status in {"BLOCK","NEEDS_USER_DECISION"}: reasons.append("SOURCE_FIDELITY_BLOCK"); findings.append("source fidelity did not pass")
        elif packet.source_fidelity_status in {"REFERENCE_UNVERIFIED","INSUFFICIENT_EVIDENCE","NOT_APPLICABLE"}: reasons.append("SOURCE_REFERENCE_UNVERIFIED"); findings.append("source fidelity evidence is unavailable")
        elif packet.source_fidelity_status!="PASS": reasons.append("SOURCE_FIDELITY_BLOCK"); findings.append("source fidelity status is not PASS")
        if packet.source_fidelity_status=="PASS" and (not packet.source_fidelity_evidence_refs or not packet.source_fidelity_target_manifest_hash or not packet.source_fidelity_dispatch_evidence_refs): reasons.append("SOURCE_MAPPING_MISSING"); findings.append("source fidelity receipt or runtime dispatch evidence binding is incomplete")
    if retry_count and not packet.evidence_refs: reasons.append("RETRY_WITHOUT_NEW_EVIDENCE")
    return GuardDecision(guard_id=hashlib.sha256((packet.task_id+packet.result_revision).encode()).hexdigest()[:16],target_type="handoff",target_id=packet.task_id,manifest_hash=packet.manifest_hash,state_revision=packet.state_revision,decision=decide(reasons,retry_count),reason_codes=tuple(dict.fromkeys(reasons)),findings=tuple(findings),evidence_refs=packet.evidence_refs,checked_paths=packet.changed_paths,checked_diff_hash=packet.diff_hash,route_status=packet.route_provenance.get("route_status","ROUTE_UNVERIFIED"),hook_status=packet.hook_status,created_at=datetime.now(timezone.utc).isoformat())

def packet_from_dict(value: dict) -> HandoffPacket:
    data=dict(value)
    for key in ("changed_paths","artifact_hashes","test_receipts","evidence_refs","assumptions","open_questions","next_allowed_actions","write_set","source_fidelity_evidence_refs","source_fidelity_dispatch_evidence_refs"): data[key]=tuple(data.get(key,()))
    return HandoffPacket(**data)
