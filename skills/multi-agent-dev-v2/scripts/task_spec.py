#!/usr/bin/env python3
"""TaskSpec helpers that preserve requested route separately from provenance."""
from __future__ import annotations
from typing import Any
from parallel_manifest import ContractError, ScopeManifest

def build_task_spec(manifest: ScopeManifest, task_id: str, state_revision: int=0) -> dict[str,Any]:
    spec=manifest.runtime_task(task_id,state_revision)
    if not spec.get("requested_model") or not spec.get("requested_effort"): raise ContractError("requested model and effort are required")
    if spec.get("side_effect_class") not in {"none","local-write","external"}: raise ContractError("invalid side effect class")
    return spec

def freeze_task_spec(spec: dict[str,Any]) -> dict[str,Any]:
    required={"task_id","manifest_hash","write_set","namespace","side_effect_class","acceptance_checks"}
    if not required.issubset(spec): raise ContractError("incomplete TaskSpec")
    return dict(spec)
