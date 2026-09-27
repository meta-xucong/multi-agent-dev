#!/usr/bin/env python3
"""Fenced namespace leases for controller-owned task execution."""
from __future__ import annotations
import time, uuid
from typing import Any
from state_store import StateStore, StateError, LeaseError

ACTIVE="ACTIVE"; EXPIRED="EXPIRED"; REVOKED="REVOKED"; RELEASED="RELEASED"
DEFAULT_TTL=90; HEARTBEAT_INTERVAL=20

class LeaseStore:
    def __init__(self, state: StateStore): self.state=state
    def acquire(self, run_id: str, task_id: str, namespace: str, owner: str, controller_epoch: int, ttl: int=DEFAULT_TTL) -> dict[str,Any]:
        return self.acquire_many(run_id,task_id,[namespace],owner,controller_epoch,ttl)[0]

    def acquire_many(self, run_id: str, task_id: str, namespaces: list[str], owner: str, controller_epoch: int, ttl: int=DEFAULT_TTL) -> list[dict[str,Any]]:
        names=list(dict.fromkeys(namespaces))
        if not names: raise LeaseError("at least one namespace is required")
        now=int(time.time()); self.state._begin()
        try:
            if controller_epoch!=self.state.current_controller_epoch(): raise LeaseError("stale controller epoch")
            task=self.state.db.execute("SELECT state,revision FROM tasks WHERE task_id=? AND run_id=?",(task_id,run_id)).fetchone()
            if not task: raise StateError("unknown task")
            task_spec=__import__("json").loads(self.state.db.execute("SELECT spec_json FROM tasks WHERE task_id=?",(task_id,)).fetchone()["spec_json"])
            declared_names=set(task_spec.get("namespace") or ("task:"+task_id,))
            if set(names)!=declared_names: raise LeaseError("lease namespaces must match frozen TaskSpec")
            placeholders=",".join("?" for _ in names)
            rows=self.state.db.execute(f"SELECT * FROM leases WHERE namespace IN ({placeholders}) AND status=?",( *names,ACTIVE)).fetchall()
            expired_tasks={row["task_id"] for row in rows if int(row["expires_at"])<=now}
            active_conflict=any(int(row["expires_at"])>now for row in rows)
            for expired_task_id in expired_tasks:
                self.state.db.execute("UPDATE leases SET status=?,revision=revision+1 WHERE task_id=? AND status=?",(EXPIRED,expired_task_id,ACTIVE))
                stale=self.state.db.execute("SELECT run_id,state,revision FROM tasks WHERE task_id=?",(expired_task_id,)).fetchone()
                if stale and stale["state"] in {"LEASED","RUNNING","CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING"}:
                    self.state.db.execute("UPDATE tasks SET state=?,revision=revision+1 WHERE task_id=? AND revision=?",("UNKNOWN",expired_task_id,stale["revision"]))
                    self.state._event(stale["run_id"],expired_task_id,int(stale["revision"])+1,"controller",stale["state"],"UNKNOWN","expired_lease_requires_stop_evidence",{"namespaces":names})
            if expired_tasks:
                self.state._finish(True)
                raise LeaseError("expired lease requires stop evidence")
            if active_conflict: raise LeaseError("namespace already leased")
            if task["state"] not in {"PLANNED","RETRYABLE"}: raise LeaseError("task is not dispatchable; stop evidence required for UNKNOWN")
            leases=[]
            for namespace in names:
                lease_id=str(uuid.uuid4()); fence=int(self.state.db.execute("SELECT COALESCE(MAX(fencing_token),0)+1 FROM leases WHERE namespace=?",(namespace,)).fetchone()[0])
                self.state.db.execute("INSERT INTO leases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(lease_id,run_id,task_id,namespace,owner,controller_epoch,fence,0,now,now+max(1,ttl),now,ACTIVE,None))
                leases.append({"lease_id":lease_id,"task_id":task_id,"namespace":namespace,"owner":owner,"controller_epoch":controller_epoch,"fencing_token":fence,"revision":0,"expires_at":now+max(1,ttl),"status":ACTIVE})
            primary=leases[0]["lease_id"]
            self.state.db.execute("UPDATE tasks SET state=?,owner=?,lease_id=?,revision=revision+1 WHERE task_id=? AND revision=?",("LEASED",owner,primary,task_id,task["revision"]))
            self.state._event(run_id,task_id,int(task["revision"])+1,owner,task["state"],"LEASED","lease_acquired",{"leases":leases})
            self.state._finish(True); return leases
        except Exception:
            if self.state.db.in_transaction: self.state._finish(False)
            raise

    def _get(self, lease_id: str):
        row=self.state.db.execute("SELECT * FROM leases WHERE lease_id=?",(lease_id,)).fetchone()
        if not row: raise LeaseError("unknown lease")
        return row

    def validate(self, lease_id: str, task_id: str, owner: str, controller_epoch: int, fencing_token: int) -> dict[str,Any]:
        row=self._get(lease_id); now=int(time.time())
        if controller_epoch!=self.state.current_controller_epoch(): raise LeaseError("controller epoch is stale")
        if row["task_id"]!=task_id or row["owner"]!=owner or int(row["controller_epoch"])!=controller_epoch or int(row["fencing_token"])!=fencing_token: raise LeaseError("stale fence")
        if row["status"]!=ACTIVE or int(row["expires_at"])<=now: raise LeaseError("lease inactive or expired")
        return dict(row)

    def heartbeat(self, lease_id: str, expected_revision: int, owner: str, controller_epoch: int, fencing_token: int, ttl: int=DEFAULT_TTL):
        now=int(time.time()); self.state._begin()
        try:
            row=self._get(lease_id); self.validate(lease_id,row["task_id"],owner,controller_epoch,fencing_token)
            if int(row["revision"])!=expected_revision: raise LeaseError("stale lease revision")
            cur=self.state.db.execute("UPDATE leases SET revision=revision+1,heartbeat_at=?,expires_at=? WHERE lease_id=? AND revision=? AND status=?",(now,now+max(1,ttl),lease_id,expected_revision,ACTIVE))
            if cur.rowcount!=1: raise LeaseError("heartbeat CAS failed")
            self.state._finish(True); return {"lease_id":lease_id,"revision":expected_revision+1,"expires_at":now+max(1,ttl),"status":ACTIVE}
        except Exception: self.state._finish(False); raise

    def release_bundle(self, task_id: str, owner: str, controller_epoch: int, fencing_tokens: dict[str,int], stop_evidence: dict[str,str], expected_revisions: dict[str,int]|None=None):
        if expected_revisions is None: raise LeaseError("expected lease revision bundle is required")
        if not stop_evidence or any(not str(value).strip() for value in stop_evidence.values()): raise LeaseError("stop evidence required")
        self.state._begin()
        try:
            if controller_epoch!=self.state.current_controller_epoch(): raise LeaseError("controller epoch is stale")
            rows=self.state.db.execute("SELECT * FROM leases WHERE task_id=? AND status=?",(task_id,ACTIVE)).fetchall()
            if not rows: raise LeaseError("no active lease bundle")
            if set(fencing_tokens)!={row["lease_id"] for row in rows}: raise LeaseError("complete lease bundle required")
            if set(stop_evidence)!={row["lease_id"] for row in rows}: raise LeaseError("stop evidence for every lease is required")
            if expected_revisions is not None and set(expected_revisions)!={row["lease_id"] for row in rows}: raise LeaseError("complete lease revision bundle required")
            for row in rows:
                if expected_revisions is not None and int(row["revision"])!=int(expected_revisions[row["lease_id"]]): raise LeaseError("stale lease bundle revision")
                if row["owner"]!=owner or int(row["controller_epoch"])!=controller_epoch or int(row["fencing_token"])!=int(fencing_tokens[row["lease_id"]]): raise LeaseError("stale lease bundle fence")
                self.state.db.execute("UPDATE leases SET revision=revision+1,status=?,stop_evidence=? WHERE lease_id=? AND status=?",(RELEASED,str(stop_evidence[row["lease_id"]]),row["lease_id"],ACTIVE))
            task=self.state.db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            lease_ids=[row["lease_id"] for row in rows]
            if task:
                old_state=task["state"]
                new_state="PLANNED" if old_state=="LEASED" else "UNKNOWN" if old_state in {"RUNNING","CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING","RETRYABLE"} else old_state
                self.state.db.execute("UPDATE tasks SET state=?,lease_id=NULL,owner=NULL,revision=revision+1 WHERE task_id=? AND revision=?",(new_state,task_id,task["revision"]))
                self.state._event(task["run_id"],task_id,int(task["revision"])+1,owner,old_state,new_state,"lease_bundle_released",{"lease_ids":lease_ids})
            self.state._finish(True); return {"task_id":task_id,"status":RELEASED,"lease_ids":lease_ids}
        except Exception:
            if self.state.db.in_transaction: self.state._finish(False)
            raise

    def release(self, lease_id: str, expected_revision: int, owner: str, controller_epoch: int, fencing_token: int, stop_evidence: str):
        row=self._get(lease_id)
        rows=self.state.db.execute("SELECT lease_id FROM leases WHERE task_id=? AND status=?",(row["task_id"],ACTIVE)).fetchall()
        if len(rows)!=1: raise LeaseError("multi-namespace lease requires release_bundle")
        return self.release_bundle(row["task_id"],owner,controller_epoch,{lease_id:fencing_token},{lease_id:stop_evidence},{lease_id:expected_revision})

    def confirm_stop_bundle(self, task_id: str, stop_evidence: dict[str,str], actor: str, controller_epoch: int, fencing_tokens: dict[str,int], expected_revisions: dict[str,int]|None=None):
        if expected_revisions is None: raise LeaseError("expected stop lease revision bundle is required")
        if not stop_evidence or any(not str(value).strip() for value in stop_evidence.values()): raise LeaseError("stop evidence required")
        self.state._begin()
        try:
            if controller_epoch!=self.state.current_controller_epoch(): raise LeaseError("controller epoch is stale")
            rows=self.state.db.execute("SELECT * FROM leases WHERE task_id=? AND status IN (?,?)",(task_id,EXPIRED,REVOKED)).fetchall()
            if not rows: raise LeaseError("no expired lease bundle")
            lease_ids={row["lease_id"] for row in rows}
            if set(stop_evidence)!=lease_ids or set(fencing_tokens)!=lease_ids: raise LeaseError("complete stop bundle evidence and fencing are required")
            if expected_revisions is not None and set(expected_revisions)!=lease_ids: raise LeaseError("complete stop bundle revisions are required")
            for row in rows:
                if actor!="controller" and row["owner"]!=actor: raise LeaseError("stop confirmer is not lease owner")
                if int(fencing_tokens[row["lease_id"]])!=int(row["fencing_token"]): raise LeaseError("stale stop fencing token")
                if expected_revisions is not None and int(expected_revisions[row["lease_id"]])!=int(row["revision"]): raise LeaseError("stale stop lease revision")
                self.state.db.execute("UPDATE leases SET status=?,stop_evidence=?,revision=revision+1 WHERE lease_id=? AND status IN (?,?)",(RELEASED,str(stop_evidence[row["lease_id"]]),row["lease_id"],EXPIRED,REVOKED))
            task=self.state.db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            lease_ids=[row["lease_id"] for row in rows]
            if task and task["state"]=="UNKNOWN":
                self.state.db.execute("UPDATE tasks SET state=?,lease_id=NULL,owner=NULL,revision=revision+1 WHERE task_id=? AND revision=?",("PLANNED",task_id,task["revision"]))
                self.state._event(task["run_id"],task_id,int(task["revision"])+1,"controller",task["state"],"PLANNED","stop_confirmed",{"lease_ids":lease_ids})
            elif task:
                self.state._event(task["run_id"],task_id,int(task["revision"]),"controller",task["state"],task["state"],"stop_confirmed",{"lease_ids":lease_ids})
            self.state._finish(True); return {"task_id":task_id,"status":RELEASED,"lease_ids":lease_ids}
        except Exception:
            if self.state.db.in_transaction: self.state._finish(False)
            raise

    def confirm_stop(self, lease_id: str, stop_evidence: str, actor: str, controller_epoch: int, fencing_token: int, expected_revision: int|None=None):
        row=self._get(lease_id)
        return self.confirm_stop_bundle(row["task_id"],{lease_id:stop_evidence},actor,controller_epoch,{lease_id:fencing_token},{lease_id:expected_revision} if expected_revision is not None else None)

    def expire(self):
        now=int(time.time()); self.state._begin()
        try:
            rows=self.state.db.execute("SELECT lease_id,task_id FROM leases WHERE status=? AND expires_at<=?",(ACTIVE,now)).fetchall()
            for task_id in {row["task_id"] for row in rows}:
                self.state.db.execute("UPDATE leases SET status=?,revision=revision+1 WHERE task_id=? AND status=?",(EXPIRED,task_id,ACTIVE))
                task=self.state.db.execute("SELECT state,revision,run_id FROM tasks WHERE task_id=?",(task_id,)).fetchone()
                if task and task["state"] in {"LEASED","RUNNING","CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING"}:
                    self.state.db.execute("UPDATE tasks SET state=?,revision=revision+1 WHERE task_id=? AND revision=?",("UNKNOWN",task_id,task["revision"]))
                    self.state._event(task["run_id"],task_id,task["revision"]+1,"controller",task["state"],"UNKNOWN","lease_bundle_expired",{})
                elif task:
                    self.state._event(task["run_id"],task_id,task["revision"],"controller",task["state"],task["state"],"lease_bundle_expired",{})
            self.state._finish(True); return len(rows)
        except Exception: self.state._finish(False); raise
