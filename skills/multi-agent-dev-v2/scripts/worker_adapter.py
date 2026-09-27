#!/usr/bin/env python3
"""Trusted local command runner; it is not an untrusted sandbox or write-set enforcer.
Workers return facts and never mutate the ledger. Frozen TaskSpec and lease checks remain controller responsibilities."""
from __future__ import annotations
from dataclasses import dataclass
import os, re, subprocess, time, uuid
from typing import Any, Sequence
from parallel_manifest import ContractError, validate_id

SECRET_PATTERN=re.compile(r"(?i)(api[_-]?key|sendkey|token|password|secret)\s*[:=]\s*([^\s,}]+)")
JSON_SECRET_PATTERN=re.compile(r'(?i)("[^"]*(?:api[_-]?key|sendkey|token|password|secret)[^"]*"\s*:\s*")[^"]*(")')
BEARER_PATTERN=re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+")
def redact(text: str) -> str:
    value=SECRET_PATTERN.sub(r"\1=<redacted>",text)
    value=JSON_SECRET_PATTERN.sub(r"\1<redacted>\2",value)
    value=BEARER_PATTERN.sub(r"\1<redacted>",value)
    return value[:16000]

@dataclass(frozen=True)
class WorkerLaunchTicket:
    ticket_id: str; run_id: str; task_id: str; attempt_id: str; manifest_hash: str
    controller_epoch: int; fencing_token: int; lease_id: str; argv: tuple[str,...]
    cwd: str|None; timeout_seconds: int; side_effect_class: str="none"
    def __post_init__(self):
        for value,name in ((self.ticket_id,"ticket_id"),(self.run_id,"run_id"),(self.task_id,"task_id"),(self.attempt_id,"attempt_id"),(self.lease_id,"lease_id")): validate_id(value,name)
        if not self.argv or not all(isinstance(item,str) and item for item in self.argv): raise ContractError("argv is required")
        if self.timeout_seconds<=0 or self.controller_epoch<1 or self.fencing_token<1: raise ContractError("invalid launch ticket")
        if self.side_effect_class not in {"none","local-write","external"}: raise ContractError("invalid side effect class")

@dataclass(frozen=True)
class WorkerResult:
    ticket_id: str; exit_code: int|None; stdout: str; stderr: str; timed_out: bool; duration_seconds: float; evidence_refs: tuple[str,...]
    def as_dict(self)->dict[str,Any]: return {"ticket_id":self.ticket_id,"exit_code":self.exit_code,"stdout":self.stdout,"stderr":self.stderr,"timed_out":self.timed_out,"duration_seconds":self.duration_seconds,"evidence_refs":list(self.evidence_refs)}

class WorkerAdapter:
    """Trusted local command runner, not an untrusted sandbox or write-set enforcer."""
    def __init__(self, allow_external: bool=False, environment: dict[str,str]|None=None): self.allow_external=allow_external; self.environment=environment or {}
    def run(self, ticket: WorkerLaunchTicket) -> WorkerResult:
        if ticket.side_effect_class=="external" and not self.allow_external: raise ContractError("external side effect is held")
        env={key:value for key,value in os.environ.items() if key in {"PATH","SystemRoot","TEMP","TMP","PYTHONPATH","PYTHONUTF8","PYTHONIOENCODING"}}; env.update(self.environment)
        started=time.monotonic(); process=None
        try:
            process=subprocess.Popen(list(ticket.argv),cwd=ticket.cwd,env=env,shell=False,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace")
            stdout,stderr=process.communicate(timeout=ticket.timeout_seconds); timed_out=False; code=process.returncode
        except subprocess.TimeoutExpired:
            if process is not None: process.kill(); stdout,stderr=process.communicate()
            timed_out=True; code=None
        duration=round(time.monotonic()-started,3)
        evidence=("worker:"+ticket.ticket_id,"exit:"+str(code) if code is not None else "worker:"+ticket.ticket_id,"timeout" if timed_out else "")
        return WorkerResult(ticket.ticket_id,code,redact(stdout or ""),redact(stderr or ""),timed_out,duration,tuple(x for x in evidence if x))
