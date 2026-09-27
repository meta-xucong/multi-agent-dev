#!/usr/bin/env python3
"""Canonical manifest and task contracts for controlled parallel V2.1 runs."""
from __future__ import annotations
import hashlib, json, re, unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import PurePosixPath, Path
from typing import Any, Mapping

CONTRACT_REV = "v2.1.0-controlled-parallel"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ROUTE_STATUSES = {"PROFILE_VERIFIED","EXPLICIT_ROUTE_VERIFIED","ROUTE_UNVERIFIED","ROUTE_MISMATCH"}
HOOK_STATUSES = {"HOOK_ENFORCED","HOOK_UNAVAILABLE","HOOK_UNVERIFIED"}
STAGES = {"PRE_CONTRACT","CONTRACT_FROZEN","VERSION_FROZEN","INTEGRATION"}
RUN_STATES = {"INTAKE","DESIGN_PENDING","SCOPE_FROZEN","DISPATCHABLE","RUNNING","EVIDENCE_COLLECTION","AUDIT_HOLD","READY_TO_MERGE","INTEGRATED","RELEASED","HELD","UNKNOWN","SUPERSEDED","CANCELLED"}
TASK_STATES = {"PLANNED","LEASED","RUNNING","CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING","ACCEPTED","RETRYABLE","FAILED","HELD","UNKNOWN","SUPERSEDED","CANCELLED"}

class ContractError(ValueError): pass

MANIFEST_FIELDS={"contract_rev","run_id","parent_run_id","manifest_revision","manifest_hash","supersedes","goal","non_goals","hard_constraints","rule_sources","base_revision","base_tree_hash","allowed_paths","forbidden_paths","read_paths","D","I","A","stage","owners","task_templates","concurrency_limit","total_agent_limit","evidence_requirements","route_status","hook_status","side_effect_policy","created_by","created_at"}
TASK_FIELDS={"task_id","role","stage","D","I","A","requested_model","requested_effort","sandbox_mode","read_set","write_set","namespace","dependency_ids","concurrency_group","timeout_seconds","max_retries","side_effect_class","acceptance_checks","evidence_requirements"}

def strict_loads(text: str) -> Any:
    def pairs(items):
        out={}
        for key,value in items:
            if key in out: raise ContractError("duplicate JSON key")
            out[key]=value
        return out
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ContractError("non-finite JSON number")))
    except ContractError: raise
    except (TypeError,json.JSONDecodeError) as exc: raise ContractError("invalid JSON") from exc

def validate_fs_paths(root: str|Path, paths: list[str]) -> None:
    base=Path(root).resolve()
    for relative in paths:
        target=(base/relative).resolve()
        try: target.relative_to(base)
        except ValueError as exc: raise ContractError("path escapes workspace") from exc
        current=base
        for part in PurePosixPath(relative).parts:
            current=current/part
            if current.is_symlink(): raise ContractError("reparse or symlink path is forbidden")


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("value is not canonical JSON") from exc

def sha256_bytes(value: bytes) -> str: return hashlib.sha256(value).hexdigest()
def canonical_hash(value: Any) -> str: return sha256_bytes(canonical_json(value))

def validate_id(value: str, field_name: str = "id") -> str:
    if not isinstance(value, str) or SAFE_ID.fullmatch(value) is None: raise ContractError(f"invalid {field_name}")
    return value

def validate_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value or ":" in value: raise ContractError("invalid path")
    p=PurePosixPath(value)
    if p.is_absolute() or any(part in {".",".."} for part in p.parts): raise ContractError("path must be repo-relative")
    for part in p.parts:
        if part.endswith(("."," ")) or part.upper() in {"CON","PRN","AUX","NUL","COM1","LPT1"}: raise ContractError("unsafe path component")
    return unicodedata.normalize("NFC", value)

def _paths(values: list[str]) -> list[str]:
    if not isinstance(values, list): raise ContractError("paths must be arrays")
    result=[validate_path(v) for v in values]
    folded=[v.casefold() for v in result]
    if len(folded)!=len(set(folded)): raise ContractError("path collision")
    return result

@dataclass(frozen=True)
class TaskTemplate:
    task_id: str; role: str; stage: str; D: str; I: str; A: str
    requested_model: str; requested_effort: str; sandbox_mode: str
    read_set: tuple[str,...]=(); write_set: tuple[str,...]=(); namespace: tuple[str,...]=()
    dependency_ids: tuple[str,...]=(); concurrency_group: str="default"
    timeout_seconds: int=900; max_retries: int=1; side_effect_class: str="none"
    acceptance_checks: tuple[str,...]=(); evidence_requirements: tuple[str,...]=()

    def __post_init__(self):
        validate_id(self.task_id,"task_id")
        if self.stage not in STAGES or self.role not in {"think","execute","test","guard","audit","integrate"}: raise ContractError("invalid task role/stage")
        if self.D not in {"D0","D1"} or self.I not in {"I0","I1","I2","I3"} or self.A not in {"A0","A1","A2"}: raise ContractError("invalid D/I/A")
        if not all(isinstance(value,str) and value for value in (self.requested_model,self.requested_effort,self.sandbox_mode)): raise ContractError("requested route is required")
        if self.side_effect_class not in {"none","local-write","external"}: raise ContractError("invalid side effect class")
        if self.timeout_seconds<=0 or self.max_retries<0: raise ContractError("invalid task limits")
        if self.sandbox_mode=="read-only" and (self.write_set or self.side_effect_class!="none"): raise ContractError("read-only task cannot write or have side effects")
        for collection in (self.read_set,self.write_set,self.namespace): _paths(list(collection))
        for dep in self.dependency_ids: validate_id(dep,"dependency_id")

    def payload(self) -> dict[str,Any]:
        return {"task_id":self.task_id,"role":self.role,"stage":self.stage,"D":self.D,"I":self.I,"A":self.A,"requested_model":self.requested_model,"requested_effort":self.requested_effort,"sandbox_mode":self.sandbox_mode,"read_set":list(self.read_set),"write_set":list(self.write_set),"namespace":list(self.namespace),"dependency_ids":list(self.dependency_ids),"concurrency_group":self.concurrency_group,"timeout_seconds":self.timeout_seconds,"max_retries":self.max_retries,"side_effect_class":self.side_effect_class,"acceptance_checks":list(self.acceptance_checks),"evidence_requirements":list(self.evidence_requirements)}

@dataclass(frozen=True)
class ScopeManifest:
    run_id: str; goal: str; non_goals: tuple[str,...]; hard_constraints: tuple[dict[str,Any],...]
    rule_sources: tuple[dict[str,Any],...]; base_revision: str; base_tree_hash: str
    allowed_paths: tuple[str,...]; forbidden_paths: tuple[str,...]; read_paths: tuple[str,...]
    D: str; I: str; A: str; stage: str; owners: dict[str,str]
    task_templates: tuple[TaskTemplate,...]; concurrency_limit: int=2; total_agent_limit: int=4
    evidence_requirements: tuple[str,...]=(); route_status: str="ROUTE_UNVERIFIED"; hook_status: str="HOOK_UNVERIFIED"
    side_effect_policy: str="none"; created_by: str="main"; created_at: str=""; manifest_revision: int=1; parent_run_id: str|None=None; supersedes: str|None=None

    def __post_init__(self):
        validate_id(self.run_id,"run_id"); validate_id(self.created_by,"created_by")
        if self.parent_run_id: validate_id(self.parent_run_id,"parent_run_id")
        if self.supersedes: validate_id(self.supersedes,"supersedes")
        if self.manifest_revision<1 or self.concurrency_limit<1 or self.total_agent_limit<1: raise ContractError("invalid manifest limits")
        if self.stage not in STAGES or self.D not in {"D0","D1"} or self.I not in {"I0","I1","I2","I3"} or self.A not in {"A0","A1","A2"}: raise ContractError("invalid manifest axes")
        if self.route_status not in ROUTE_STATUSES or self.hook_status not in HOOK_STATUSES: raise ContractError("invalid provenance status")
        _paths(list(self.allowed_paths)); _paths(list(self.forbidden_paths)); _paths(list(self.read_paths))
        seen=set()
        def within(path: str, root: str) -> bool: return path==root or path.startswith(root+"/")
        allowed=list(self.allowed_paths); forbidden=list(self.forbidden_paths); readable=allowed+list(self.read_paths)
        for task in self.task_templates:
            if task.task_id in seen: raise ContractError("duplicate task_id")
            seen.add(task.task_id)
            if task.sandbox_mode=="read-only" and (task.write_set or task.side_effect_class!="none"): raise ContractError("read-only task cannot write or have side effects")
            if any(not any(within(item,root) for root in allowed) for item in task.write_set): raise ContractError("write_set escapes allowed_paths")
            if any(any(within(item,root) for root in forbidden) for item in task.write_set): raise ContractError("write_set overlaps forbidden_paths")
            if any(not any(within(item,root) for root in readable) for item in task.read_set): raise ContractError("read_set escapes readable paths")
            if any(any(within(item,root) for root in forbidden) for item in task.read_set): raise ContractError("read_set overlaps forbidden_paths")
        for task in self.task_templates:
            if set(task.dependency_ids)-seen: raise ContractError("unknown dependency")
        graph={task.task_id:set(task.dependency_ids) for task in self.task_templates}
        visiting=set(); visited=set()
        def visit(task_id: str):
            if task_id in visiting: raise ContractError("dependency cycle")
            if task_id in visited: return
            visiting.add(task_id)
            for dependency_id in graph[task_id]: visit(dependency_id)
            visiting.remove(task_id); visited.add(task_id)
        for task_id in graph: visit(task_id)

    def payload_without_hash(self) -> dict[str,Any]:
        return {"contract_rev":CONTRACT_REV,"run_id":self.run_id,"parent_run_id":self.parent_run_id,"manifest_revision":self.manifest_revision,"supersedes":self.supersedes,"goal":self.goal,"non_goals":list(self.non_goals),"hard_constraints":list(self.hard_constraints),"rule_sources":list(self.rule_sources),"base_revision":self.base_revision,"base_tree_hash":self.base_tree_hash,"allowed_paths":list(self.allowed_paths),"forbidden_paths":list(self.forbidden_paths),"read_paths":list(self.read_paths),"D":self.D,"I":self.I,"A":self.A,"stage":self.stage,"owners":self.owners,"task_templates":[t.payload() for t in self.task_templates],"concurrency_limit":self.concurrency_limit,"total_agent_limit":self.total_agent_limit,"evidence_requirements":list(self.evidence_requirements),"route_status":self.route_status,"hook_status":self.hook_status,"side_effect_policy":self.side_effect_policy,"created_by":self.created_by,"created_at":self.created_at}

    def manifest_hash(self) -> str: return canonical_hash(self.payload_without_hash())

    def runtime_task(self, task_id: str, state_revision: int=0) -> dict[str,Any]:
        task=next((t for t in self.task_templates if t.task_id==task_id),None)
        if task is None: raise ContractError("unknown task")
        value=task.payload(); value.update({"manifest_hash":self.manifest_hash(),"state_revision":state_revision})
        return value

def parse_manifest(value: Mapping[str,Any]) -> ScopeManifest:
    required={"run_id","goal","non_goals","hard_constraints","rule_sources","base_revision","base_tree_hash","allowed_paths","forbidden_paths","read_paths","D","I","A","stage","owners","task_templates"}
    if not isinstance(value,Mapping) or not required.issubset(value): raise ContractError("manifest missing fields")
    if set(value)-MANIFEST_FIELDS: raise ContractError("unknown manifest field")
    if value.get("contract_rev",CONTRACT_REV)!=CONTRACT_REV: raise ContractError("unsupported contract revision")
    raw_tasks=value["task_templates"]
    if not isinstance(raw_tasks,list): raise ContractError("task_templates must be array")
    tasks=[]
    for item in raw_tasks:
        if not isinstance(item,Mapping) or set(item)-TASK_FIELDS: raise ContractError("unknown task field")
        tasks.append(TaskTemplate(**{k:(tuple(v) if k in {"read_set","write_set","namespace","dependency_ids","acceptance_checks","evidence_requirements"} else v) for k,v in item.items()}))
    result=ScopeManifest(run_id=value["run_id"],goal=value["goal"],non_goals=tuple(value["non_goals"]),hard_constraints=tuple(value["hard_constraints"]),rule_sources=tuple(value["rule_sources"]),base_revision=value["base_revision"],base_tree_hash=value["base_tree_hash"],allowed_paths=tuple(value["allowed_paths"]),forbidden_paths=tuple(value["forbidden_paths"]),read_paths=tuple(value["read_paths"]),D=value["D"],I=value["I"],A=value["A"],stage=value["stage"],owners=dict(value["owners"]),task_templates=tuple(tasks),concurrency_limit=value.get("concurrency_limit",2),total_agent_limit=value.get("total_agent_limit",4),evidence_requirements=tuple(value.get("evidence_requirements",())),route_status=value.get("route_status","ROUTE_UNVERIFIED"),hook_status=value.get("hook_status","HOOK_UNVERIFIED"),side_effect_policy=value.get("side_effect_policy","none"),created_by=value.get("created_by","main"),created_at=value.get("created_at",""),manifest_revision=value.get("manifest_revision",1),parent_run_id=value.get("parent_run_id"),supersedes=value.get("supersedes"))
    if value.get("manifest_hash") and value["manifest_hash"]!=result.manifest_hash(): raise ContractError("manifest hash mismatch")
    return result
