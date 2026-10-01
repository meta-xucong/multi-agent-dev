#!/usr/bin/env python3
"""SQLite-backed controller state with transactional CAS, idempotency and fencing."""
from __future__ import annotations
import hashlib, json, re, sqlite3, time, uuid
from pathlib import Path
from typing import Any
from parallel_manifest import canonical_hash, canonical_json, ContractError, ScopeManifest, TASK_STATES, parse_manifest, validate_id
from audit_receipt import AuditReceipt
from source_fidelity import SourceFidelityReceipt
from route_contract import PROFILE_ROUTE_CONTRACT, SOURCE_FIDELITY_PROFILE
from runtime_dispatch import RuntimeDispatchRequest

class StateError(RuntimeError): pass
class StaleRevision(StateError): pass
class IdempotencyConflict(StateError): pass
class LeaseError(StateError): pass

RUN_INITIAL="INTAKE"; TASK_INITIAL="PLANNED"
RUN_TRANSITIONS={
    "INTAKE":{"DESIGN_PENDING","CANCELLED"},
    "DESIGN_PENDING":{"SCOPE_FROZEN","HELD","CANCELLED"},
    "SCOPE_FROZEN":{"DISPATCHABLE","HELD","CANCELLED"},
    "DISPATCHABLE":{"RUNNING","HELD","CANCELLED"},
    "RUNNING":{"EVIDENCE_COLLECTION","HELD","UNKNOWN","CANCELLED"},
    "EVIDENCE_COLLECTION":{"AUDIT_HOLD","READY_TO_MERGE","HELD","UNKNOWN","CANCELLED"},
    "AUDIT_HOLD":{"EVIDENCE_COLLECTION","HELD","CANCELLED"},
    "READY_TO_MERGE":{"INTEGRATED","HELD","CANCELLED"},
    "INTEGRATED":{"RELEASED","HELD","CANCELLED"},
    "RELEASED":set(),"HELD":{"EVIDENCE_COLLECTION","CANCELLED"},"UNKNOWN":{"EVIDENCE_COLLECTION","HELD","CANCELLED"},"SUPERSEDED":set(),"CANCELLED":set(),
}
TASK_TRANSITIONS={
    "PLANNED":{"LEASED","CANCELLED","SUPERSEDED"},
    "LEASED":{"RUNNING","RETRYABLE","FAILED","HELD","UNKNOWN","CANCELLED"},
    "RUNNING":{"CHECKPOINTED","WAITING_HANDOFF","RETRYABLE","FAILED","HELD","UNKNOWN","CANCELLED"},
    "CHECKPOINTED":{"WAITING_HANDOFF","RETRYABLE","FAILED","HELD","UNKNOWN","CANCELLED"},
    "WAITING_HANDOFF":{"AUDIT_PENDING","RETRYABLE","FAILED","HELD","UNKNOWN"},
    "AUDIT_PENDING":{"ACCEPTED","RETRYABLE","FAILED","HELD","UNKNOWN"},
    "RETRYABLE":{"LEASED","CANCELLED","SUPERSEDED"},
    "UNKNOWN":{"PLANNED","HELD","CANCELLED"},
    "FAILED":{"RETRYABLE","HELD","SUPERSEDED"},
    "HELD":{"RETRYABLE","CANCELLED","SUPERSEDED"},
    "ACCEPTED":set(),"SUPERSEDED":set(),"CANCELLED":set(),
}
def _now() -> int: return int(time.time())
def _dump(value: Any) -> str: return canonical_json(value).decode("utf-8")
def _hash(value: Any) -> str: return hashlib.sha256(_dump(value).encode()).hexdigest()

SECRET_PATTERNS=(re.compile(r"\bapi[_-]?key\b", re.I), re.compile(r"\bsendkey\b", re.I), re.compile(r"\bpassword\b", re.I), re.compile(r"\bbearer\s+", re.I), re.compile(r"(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9]{16,}(?:$|[^A-Za-z0-9])", re.I))

class StateStore:
    def __init__(self, path: str|Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(self.path), isolation_level=None, timeout=10)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON"); self.db.execute("PRAGMA journal_mode=WAL"); self.db.execute("PRAGMA synchronous=FULL")
        self._schema()

    def close(self): self.db.close()
    def _schema(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, manifest_hash TEXT NOT NULL, manifest_json TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id), spec_json TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL, owner TEXT, lease_id TEXT, result_json TEXT);
        CREATE TABLE IF NOT EXISTS attempts(attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id), number INTEGER NOT NULL, state TEXT NOT NULL, evidence_json TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS leases(lease_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(task_id), namespace TEXT NOT NULL, owner TEXT NOT NULL, controller_epoch INTEGER NOT NULL, fencing_token INTEGER NOT NULL, revision INTEGER NOT NULL, issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, heartbeat_at INTEGER NOT NULL, status TEXT NOT NULL, stop_evidence TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS active_namespace ON leases(namespace) WHERE status='ACTIVE';
        CREATE TABLE IF NOT EXISTS events(event_seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, run_id TEXT NOT NULL, task_id TEXT, entity_revision INTEGER NOT NULL, actor_id TEXT NOT NULL, from_state TEXT, to_state TEXT, reason TEXT NOT NULL, payload_json TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS idempotency(request_key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, response_json TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(outbox_id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL, side_effect_class TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', created_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, claimed_by TEXT, claimed_until INTEGER, last_error TEXT, completed_at INTEGER, result_json TEXT);
        CREATE TABLE IF NOT EXISTS evidence(evidence_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT, kind TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'unknown', manifest_hash TEXT NOT NULL, base_revision TEXT, result_revision TEXT, artifact_hash TEXT, command_or_ui_step TEXT, exit_code INTEGER, observed_at TEXT NOT NULL, limitations TEXT NOT NULL, redaction_status TEXT NOT NULL, payload_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS receipts(receipt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL, manifest_hash TEXT NOT NULL, result_revision TEXT NOT NULL, diff_hash TEXT NOT NULL, auditor_actor TEXT NOT NULL, writer_actor TEXT NOT NULL, decision TEXT NOT NULL, receipt_json TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS notification_intents(intent_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, run_id TEXT, task_id TEXT, status TEXT NOT NULL, payload_json TEXT NOT NULL, attempts INTEGER NOT NULL, last_error TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS controller_epoch(singleton INTEGER PRIMARY KEY CHECK(singleton=1), epoch INTEGER NOT NULL, owner TEXT NOT NULL, acquired_at INTEGER NOT NULL);
        """)
        self._ensure_schema_columns()

    def _ensure_schema_columns(self):
        migrations=(
            ("outbox","attempts","ALTER TABLE outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"),
            ("outbox","claimed_by","ALTER TABLE outbox ADD COLUMN claimed_by TEXT"),
            ("outbox","claimed_until","ALTER TABLE outbox ADD COLUMN claimed_until INTEGER"),
            ("outbox","last_error","ALTER TABLE outbox ADD COLUMN last_error TEXT"),
            ("outbox","completed_at","ALTER TABLE outbox ADD COLUMN completed_at INTEGER"),
            ("outbox","result_json","ALTER TABLE outbox ADD COLUMN result_json TEXT"),
            ("evidence","source","ALTER TABLE evidence ADD COLUMN source TEXT NOT NULL DEFAULT 'unknown'"),
        )
        for table,column,statement in migrations:
            columns={row["name"] for row in self.db.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in columns: self.db.execute(statement)

    def _begin(self): self.db.execute("BEGIN IMMEDIATE")
    def _finish(self, ok: bool): self.db.execute("COMMIT" if ok else "ROLLBACK")
    def _idem(self, key: str|None, payload: Any):
        if not key: return None
        row=self.db.execute("SELECT payload_hash,response_json FROM idempotency WHERE request_key=?",(key,)).fetchone()
        if row:
            if row["payload_hash"]!=_hash(payload): raise IdempotencyConflict("idempotency key reused with different payload")
            return json.loads(row["response_json"])
        return None

    def replay_idempotency(self, key: str|None, payload: Any):
        """Return a committed response for an exact request replay without running precondition gates."""
        if not key: return None
        row=self.db.execute("SELECT payload_hash,response_json FROM idempotency WHERE request_key=?",(key,)).fetchone()
        if not row: return None
        if row["payload_hash"]!=_hash(payload): raise IdempotencyConflict("idempotency key reused with different payload")
        return json.loads(row["response_json"])
    def _store_idem(self,key: str|None,payload: Any,response: Any):
        if key: self.db.execute("INSERT INTO idempotency VALUES(?,?,?,?)",(key,_hash(payload),_dump(response),_now()))

    def acquire_controller(self, owner: str, takeover: bool=False) -> int:
        """Acquire the durable controller epoch; same-owner reuse assumes one trusted process, while takeover fences the prior session."""
        validate_id(owner,"controller_owner")
        self._begin()
        try:
            row=self.db.execute("SELECT epoch,owner FROM controller_epoch WHERE singleton=1").fetchone()
            if row and row["owner"]==owner and not takeover:
                epoch=int(row["epoch"])
            else:
                epoch=(int(row["epoch"])+1) if row else 1
                self.db.execute("INSERT INTO controller_epoch(singleton,epoch,owner,acquired_at) VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET epoch=excluded.epoch,owner=excluded.owner,acquired_at=excluded.acquired_at",(epoch,owner,_now()))
            self._finish(True); return epoch
        except Exception: self._finish(False); raise

    def current_controller_epoch(self) -> int:
        row=self.db.execute("SELECT epoch FROM controller_epoch WHERE singleton=1").fetchone()
        return int(row["epoch"]) if row else 0

    def create_run(self, manifest: ScopeManifest, request_key: str|None=None) -> dict[str,Any]:
        payload=manifest.payload_without_hash(); manifest_hash=manifest.manifest_hash(); payload["manifest_hash"]=manifest_hash
        self._begin()
        try:
            replay=self._idem(request_key,payload)
            if replay is not None: self._finish(True); return replay
            if manifest.supersedes:
                old=self.db.execute("SELECT * FROM runs WHERE run_id=?",(manifest.supersedes,)).fetchone()
                if not old: raise ContractError("superseded run does not exist")
                active_lease=self.db.execute("SELECT 1 FROM leases WHERE run_id=? AND status='ACTIVE' LIMIT 1",(manifest.supersedes,)).fetchone()
                active_task=self.db.execute("SELECT 1 FROM tasks WHERE run_id=? AND state IN ('LEASED','RUNNING','CHECKPOINTED','WAITING_HANDOFF','AUDIT_PENDING') LIMIT 1",(manifest.supersedes,)).fetchone()
                if active_lease or active_task: raise StateError("cannot supersede run with active leases or tasks")
                if old["state"]!="SUPERSEDED":
                    new_revision=int(old["revision"])+1
                    cur=self.db.execute("UPDATE runs SET state='SUPERSEDED',revision=? WHERE run_id=? AND revision=?",(new_revision,manifest.supersedes,int(old["revision"])))
                    if cur.rowcount!=1: raise StaleRevision("supersede run CAS failed")
                    self._event(manifest.supersedes,None,new_revision,manifest.created_by,old["state"],"SUPERSEDED","run_superseded",{"superseded_by":manifest.run_id})
                    for task in self.db.execute("SELECT * FROM tasks WHERE run_id=? AND state IN ('PLANNED','RETRYABLE')",(manifest.supersedes,)).fetchall():
                        task_revision=int(task["revision"])+1
                        self.db.execute("UPDATE tasks SET state='SUPERSEDED',revision=?,result_json=? WHERE task_id=? AND revision=?",(task_revision,_dump({"superseded_by":manifest.run_id}),task["task_id"],int(task["revision"])))
                        self._event(manifest.supersedes,task["task_id"],task_revision,manifest.created_by,task["state"],"SUPERSEDED","run_superseded",{"superseded_by":manifest.run_id})
            self.db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)",(manifest.run_id,manifest_hash,_dump(payload),RUN_INITIAL,0,_now()))
            response={"run_id":manifest.run_id,"manifest_hash":manifest_hash,"revision":0,"state":RUN_INITIAL}
            self._store_idem(request_key,payload,response); self._finish(True); return response
        except Exception: self._finish(False); raise

    def add_tasks(self, run_id: str, specs: list[dict[str,Any]], request_key: str|None=None):
        payload={"run_id":run_id,"task_specs":specs}; self._begin()
        try:
            replay=self._idem(request_key,payload)
            if replay is not None: self._finish(True); return replay
            run=self.db.execute("SELECT * FROM runs WHERE run_id=?",(run_id,)).fetchone()
            if not run: raise StateError("unknown run")
            manifest=parse_manifest(json.loads(run["manifest_json"]))
            allowed={task.task_id for task in manifest.task_templates}
            seen=set()
            for spec in specs:
                if not isinstance(spec,dict): raise ContractError("TaskSpec must be an object")
                task_id=spec.get("task_id")
                if task_id not in allowed: raise ContractError("task is not declared by frozen manifest")
                if task_id in seen or self.db.execute("SELECT 1 FROM tasks WHERE task_id=?",(task_id,)).fetchone(): raise ContractError("duplicate task_id")
                seen.add(task_id)
                expected=manifest.runtime_task(task_id)
                if spec.get("manifest_hash")!=run["manifest_hash"]: raise ContractError("TaskSpec manifest hash mismatch")
                if set(spec)!=set(expected): raise ContractError("TaskSpec fields do not match frozen manifest")
                if any(spec[key]!=expected[key] for key in expected if key!="state_revision"): raise ContractError("TaskSpec differs from frozen manifest")
                if spec.get("state_revision")!=0: raise ContractError("initial TaskSpec revision must be zero")
                self.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)",(task_id,run_id,_dump(spec),TASK_INITIAL,0,None,None,None))
            response={"run_id":run_id,"task_count":len(specs)}; self._store_idem(request_key,payload,response); self._finish(True); return response
        except Exception: self._finish(False); raise

    def get_run(self, run_id: str):
        row=self.db.execute("SELECT * FROM runs WHERE run_id=?",(run_id,)).fetchone()
        return dict(row) if row else None
    def get_task(self, task_id: str):
        row=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if not row: return None
        result=dict(row); result["spec"]=json.loads(result.pop("spec_json")); result["result"]=json.loads(result.pop("result_json")) if result.get("result_json") else None; return result

    def _event(self, run_id, task_id, revision, actor, old, new, reason, payload, side_effect="none"):
        payload=dict(payload or {})
        ledger=dict(payload.get("_ledger") or {})
        run_row=self.db.execute("SELECT manifest_hash FROM runs WHERE run_id=?",(run_id,)).fetchone()
        expected_ledger={"manifest_hash":run_row["manifest_hash"] if run_row else None,"controller_epoch":self.current_controller_epoch(),"entity_revision":revision}
        for key,value in expected_ledger.items():
            if key in ledger and ledger[key]!=value: raise ContractError("event ledger metadata is controller-owned")
            ledger[key]=value
        payload["_ledger"]=ledger
        event_id=str(uuid.uuid4()); self.db.execute("INSERT INTO events(event_id,run_id,task_id,entity_revision,actor_id,from_state,to_state,reason,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(event_id,run_id,task_id,revision,actor,old,new,reason,_dump(payload),_now()))
        if side_effect!="none": self.db.execute("INSERT INTO outbox(event_id,side_effect_class,payload_json,created_at) VALUES(?,?,?,?)",(event_id,side_effect,_dump(payload),_now()))
        return event_id

    def transition_task(self, task_id: str, expected_revision: int, new_state: str, actor: str, reason: str, payload: dict[str,Any]|None=None, request_key: str|None=None, lease_id: str|None=None, side_effect: str="none", controller_epoch: int|None=None, fencing_token: int|None=None, manifest_hash: str|None=None, fencing_tokens: dict[str,int]|None=None) -> dict[str,Any]:
        if new_state not in {"PLANNED","LEASED","RUNNING","CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING","ACCEPTED","RETRYABLE","FAILED","HELD","UNKNOWN","SUPERSEDED","CANCELLED"}: raise ContractError("invalid task state")
        if new_state in {"RUNNING","CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING","ACCEPTED"} and lease_id is None: raise LeaseError("execution transition requires lease fence")
        if side_effect not in {"none","local-write","external"}: raise ContractError("invalid side effect class")
        payload=payload or {}; idem_payload={"task_id":task_id,"expected_revision":expected_revision,"new_state":new_state,"actor":actor,"reason":reason,"payload":payload,"lease_id":lease_id,"controller_epoch":controller_epoch,"fencing_token":fencing_token,"manifest_hash":manifest_hash,"fencing_tokens":fencing_tokens}
        self._begin()
        try:
            replay=self._idem(request_key,idem_payload)
            if replay is not None: self._finish(True); return replay
            row=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if not row: raise StateError("unknown task")
            if int(row["revision"])!=expected_revision: raise StaleRevision(f"task revision {row['revision']} != {expected_revision}")
            if new_state not in TASK_TRANSITIONS.get(row["state"],set()): raise StateError(f"illegal task transition {row['state']} -> {new_state}")
            if manifest_hash is not None and json.loads(row["spec_json"]).get("manifest_hash")!=manifest_hash: raise LeaseError("manifest fence mismatch")
            if lease_id is not None:
                if controller_epoch is None or fencing_token is None or manifest_hash is None: raise LeaseError("epoch, fencing token and manifest hash are required")
                if row["lease_id"]!=lease_id: raise LeaseError("lease fence mismatch")
                lease=self.db.execute("SELECT * FROM leases WHERE lease_id=?",(lease_id,)).fetchone()
                if not lease or lease["run_id"]!=row["run_id"] or lease["status"]!="ACTIVE" or int(lease["expires_at"])<=_now(): raise LeaseError("lease inactive or expired")
                if int(controller_epoch)!=self.current_controller_epoch(): raise LeaseError("controller epoch is stale")
                if int(lease["controller_epoch"])!=controller_epoch: raise LeaseError("controller epoch fence mismatch")
                if int(lease["fencing_token"])!=fencing_token: raise LeaseError("fencing token mismatch")
                if lease["owner"]!=actor: raise LeaseError("lease owner mismatch")
                spec=json.loads(row["spec_json"]); required_namespaces=list(spec.get("namespace") or [lease["namespace"]])
                if len(required_namespaces)>1:
                    if not fencing_tokens or set(fencing_tokens)!=set(required_namespaces): raise LeaseError("all namespace fencing tokens are required")
                for namespace in required_namespaces:
                    bundle_lease=self.db.execute("SELECT * FROM leases WHERE task_id=? AND namespace=?",(task_id,namespace)).fetchone()
                    if not bundle_lease or bundle_lease["status"]!="ACTIVE" or int(bundle_lease["expires_at"])<=_now() or bundle_lease["owner"]!=actor or int(bundle_lease["controller_epoch"])!=int(controller_epoch):
                        raise LeaseError("lease bundle is incomplete or stale")
                    if len(required_namespaces)>1 and int(bundle_lease["fencing_token"])!=int(fencing_tokens[namespace]):
                        raise LeaseError("namespace fencing token mismatch")
            elif row["lease_id"] is not None:
                raise LeaseError("active or stale lease must be presented")
            new_revision=expected_revision+1
            cur=self.db.execute("UPDATE tasks SET state=?,revision=?,result_json=? WHERE task_id=? AND revision=?",(new_state,new_revision,_dump(payload),task_id,expected_revision))
            if cur.rowcount!=1: raise StaleRevision("CAS failed")
            event_payload=dict(payload); event_payload["_fence"]={"lease_id":lease_id,"controller_epoch":controller_epoch,"fencing_token":fencing_token,"manifest_hash":manifest_hash,"fencing_tokens":fencing_tokens} if lease_id is not None else {}
            event_id=self._event(row["run_id"],task_id,new_revision,actor,row["state"],new_state,reason,event_payload,side_effect)
            response={"task_id":task_id,"state":new_state,"revision":new_revision,"event_id":event_id}
            self._store_idem(request_key,idem_payload,response); self._finish(True); return response
        except Exception: self._finish(False); raise

    def transition_task_chain(self, task_id: str, expected_revision: int, new_states: list[str], actor: str, reason: str, payload: dict[str,Any]|None=None, request_key: str|None=None, request_payload: Any|None=None, lease_id: str|None=None, controller_epoch: int|None=None, fencing_token: int|None=None, manifest_hash: str|None=None, fencing_tokens: dict[str,int]|None=None) -> dict[str,Any]:
        """Apply an ordered handoff state chain in one transaction and one idempotency record."""
        if not new_states: raise ContractError("state chain is empty")
        payload=payload or {}
        idem_payload=request_payload if request_payload is not None else {"task_id":task_id,"expected_revision":expected_revision,"new_states":new_states,"actor":actor,"reason":reason,"payload":payload,"lease_id":lease_id,"controller_epoch":controller_epoch,"fencing_token":fencing_token,"manifest_hash":manifest_hash,"fencing_tokens":fencing_tokens}
        self._begin()
        try:
            replay=self._idem(request_key,idem_payload)
            if replay is not None: self._finish(True); return replay
            row=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if not row: raise StateError("unknown task")
            if int(row["revision"])!=expected_revision: raise StaleRevision("task revision mismatch")
            if any(state not in TASK_STATES for state in new_states): raise ContractError("invalid task state in chain")
            if any(state in {"RUNNING","CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING","ACCEPTED"} for state in new_states) and lease_id is None:
                raise LeaseError("execution transition requires lease fence")
            if lease_id is None and row["lease_id"] is not None: raise LeaseError("active or stale lease must be presented")
            spec=json.loads(row["spec_json"])
            if manifest_hash is not None and spec.get("manifest_hash")!=manifest_hash: raise LeaseError("manifest fence mismatch")
            if lease_id is not None:
                if controller_epoch is None or fencing_token is None or manifest_hash is None: raise LeaseError("epoch, fencing token and manifest hash are required")
                if row["lease_id"]!=lease_id: raise LeaseError("lease fence mismatch")
                lease=self.db.execute("SELECT * FROM leases WHERE lease_id=?",(lease_id,)).fetchone()
                if not lease or lease["run_id"]!=row["run_id"] or lease["status"]!="ACTIVE" or int(lease["expires_at"])<=_now(): raise LeaseError("lease inactive or expired")
                if int(controller_epoch)!=self.current_controller_epoch() or int(lease["controller_epoch"])!=int(controller_epoch): raise LeaseError("controller epoch fence mismatch")
                if int(lease["fencing_token"])!=int(fencing_token) or lease["owner"]!=actor: raise LeaseError("lease owner mismatch")
                required_namespaces=list(spec.get("namespace") or [lease["namespace"]])
                if len(required_namespaces)>1 and (not fencing_tokens or set(fencing_tokens)!=set(required_namespaces)): raise LeaseError("all namespace fencing tokens are required")
                for namespace in required_namespaces:
                    bundle_lease=self.db.execute("SELECT * FROM leases WHERE task_id=? AND namespace=?",(task_id,namespace)).fetchone()
                    if not bundle_lease or bundle_lease["status"]!="ACTIVE" or int(bundle_lease["expires_at"])<=_now() or bundle_lease["owner"]!=actor or int(bundle_lease["controller_epoch"])!=int(controller_epoch):
                        raise LeaseError("lease bundle is incomplete or stale")
                    if len(required_namespaces)>1 and int(bundle_lease["fencing_token"])!=int(fencing_tokens[namespace]): raise LeaseError("namespace fencing token mismatch")
            current=row["state"]; revision=expected_revision; events=[]
            for next_state in new_states:
                if next_state not in TASK_TRANSITIONS.get(current,set()): raise StateError(f"illegal task transition {current} -> {next_state}")
                revision+=1
                cur=self.db.execute("UPDATE tasks SET state=?,revision=?,result_json=? WHERE task_id=? AND revision=?", (next_state,revision,_dump(payload),task_id,revision-1))
                if cur.rowcount!=1: raise StaleRevision("task chain CAS failed")
                event_payload=dict(payload); event_payload["_fence"]={"lease_id":lease_id,"controller_epoch":controller_epoch,"fencing_token":fencing_token,"manifest_hash":manifest_hash,"fencing_tokens":fencing_tokens}
                events.append(self._event(row["run_id"],task_id,revision,actor,current,next_state,reason+"_"+next_state.lower(),event_payload))
                current=next_state
            response={"task_id":task_id,"state":current,"revision":revision,"event_ids":events,"chain":list(new_states),"handoff":payload}
            self._store_idem(request_key,idem_payload,response); self._finish(True); return response
        except Exception:
            self._finish(False); raise

    def list_tasks(self, run_id: str):
        rows=self.db.execute("SELECT task_id,state,revision,owner,lease_id,spec_json FROM tasks WHERE run_id=? ORDER BY task_id",(run_id,)).fetchall()
        return [{"task_id":r["task_id"],"state":r["state"],"revision":r["revision"],"owner":r["owner"],"lease_id":r["lease_id"],"spec":json.loads(r["spec_json"])} for r in rows]

    def transition_run(self, run_id: str, expected_revision: int, new_state: str, actor: str, reason: str, payload: dict[str,Any]|None=None, controller_epoch: int|None=None, manifest_hash: str|None=None):
        payload=payload or {}; self._begin()
        try:
            row=self.db.execute("SELECT * FROM runs WHERE run_id=?",(run_id,)).fetchone()
            if not row: raise StateError("unknown run")
            if controller_epoch is None or manifest_hash is None: raise LeaseError("run transition requires controller epoch and manifest hash")
            if int(controller_epoch)!=self.current_controller_epoch(): raise LeaseError("controller epoch is stale")
            if manifest_hash!=row["manifest_hash"]: raise LeaseError("run manifest fence mismatch")
            if int(row["revision"])!=expected_revision: raise StaleRevision("run revision mismatch")
            if new_state not in RUN_TRANSITIONS.get(row["state"],set()): raise StateError(f"illegal run transition {row['state']} -> {new_state}")
            cur=self.db.execute("UPDATE runs SET state=?,revision=? WHERE run_id=? AND revision=?",(new_state,expected_revision+1,run_id,expected_revision))
            if cur.rowcount!=1: raise StaleRevision("run CAS failed")
            event_payload=dict(payload); event_payload["_fence"]={"controller_epoch":controller_epoch,"manifest_hash":manifest_hash}
            event_id=self._event(run_id,None,expected_revision+1,actor,row["state"],new_state,reason,event_payload)
            self._finish(True); return {"run_id":run_id,"state":new_state,"revision":expected_revision+1,"event_id":event_id}
        except Exception: self._finish(False); raise

    def retry_task(self, task_id: str, actor: str, reason: str, evidence_refs: list[str], attempt_id: str, request_key: str|None=None, controller_epoch: int|None=None, fencing_token: int|None=None, manifest_hash: str|None=None, fencing_tokens: dict[str,int]|None=None):
        payload={"task_id":task_id,"actor":actor,"reason":reason,"evidence_refs":list(evidence_refs),"attempt_id":attempt_id,"controller_epoch":controller_epoch,"fencing_token":fencing_token,"manifest_hash":manifest_hash,"fencing_tokens":fencing_tokens}
        self._begin()
        try:
            replay=self._idem(request_key,payload)
            if replay is not None: self._finish(True); return replay
            row=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
            if not row: raise StateError("unknown task")
            attempts=int(self.db.execute("SELECT COUNT(*) AS n FROM attempts WHERE task_id=?",(task_id,)).fetchone()["n"])
            max_retries=int(json.loads(row["spec_json"]).get("max_retries",0))
            if attempts>=max_retries: raise StateError("retry budget exhausted")
            if attempts and not evidence_refs: raise ContractError("retry requires new evidence")
            new_state="RETRYABLE" if row["state"] in {"FAILED","HELD"} else "PLANNED" if row["state"]=="UNKNOWN" else None
            if new_state is None: raise StateError("task is not retryable")
            if new_state not in TASK_TRANSITIONS.get(row["state"],set()): raise StateError("illegal retry transition")
            if row["lease_id"] is not None:
                if controller_epoch is None or fencing_token is None or manifest_hash is None: raise LeaseError("epoch, fencing token and manifest hash are required")
                spec=json.loads(row["spec_json"])
                if manifest_hash!=spec.get("manifest_hash"): raise LeaseError("manifest fence mismatch")
                lease=self.db.execute("SELECT * FROM leases WHERE lease_id=?",(row["lease_id"],)).fetchone()
                if not lease or lease["status"]!="ACTIVE" or int(lease["expires_at"])<=_now(): raise LeaseError("lease inactive or expired")
                if int(controller_epoch)!=self.current_controller_epoch() or int(lease["controller_epoch"])!=int(controller_epoch): raise LeaseError("controller epoch fence mismatch")
                if int(lease["fencing_token"])!=int(fencing_token) or lease["owner"]!=actor: raise LeaseError("stale retry fence")
                required_namespaces=list(spec.get("namespace") or [lease["namespace"]])
                if len(required_namespaces)>1:
                    if not fencing_tokens or set(fencing_tokens)!=set(required_namespaces): raise LeaseError("all retry namespace fencing tokens are required")
                    for namespace in required_namespaces:
                        bundle_lease=self.db.execute("SELECT * FROM leases WHERE task_id=? AND namespace=?",(task_id,namespace)).fetchone()
                        if not bundle_lease or bundle_lease["status"]!="ACTIVE" or int(bundle_lease["expires_at"])<=_now() or bundle_lease["owner"]!=actor or int(bundle_lease["controller_epoch"])!=int(controller_epoch) or int(bundle_lease["fencing_token"])!=int(fencing_tokens[namespace]): raise LeaseError("stale retry namespace fence")
            self.db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,?)",(attempt_id,task_id,attempts+1,"REQUESTED",_dump({"evidence_refs":list(evidence_refs),"reason":reason}),_now()))
            new_revision=int(row["revision"])+1
            cur=self.db.execute("UPDATE tasks SET state=?,revision=?,result_json=? WHERE task_id=? AND revision=?",(new_state,new_revision,_dump(payload),task_id,int(row["revision"])))
            if cur.rowcount!=1: raise StaleRevision("retry CAS failed")
            event_id=self._event(row["run_id"],task_id,new_revision,actor,row["state"],new_state,"retry_requested",payload)
            response={"task_id":task_id,"state":new_state,"revision":new_revision,"attempt_id":attempt_id,"attempt_number":attempts+1,"event_id":event_id}
            self._store_idem(request_key,payload,response); self._finish(True); return response
        except Exception: self._finish(False); raise

    def record_attempt(self, task_id: str, attempt_id: str, number: int, state: str, evidence: dict[str,Any], request_key: str|None=None):
        raise StateError("record_attempt is disabled; use atomic retry_task")

    def record_evidence(self, evidence: dict[str,Any]):
        required={"evidence_id","run_id","kind","source","manifest_hash","observed_at","limitations","redaction_status"}
        if not required.issubset(evidence): raise ContractError("incomplete evidence")
        if evidence.get("kind") not in {"TEST_RECEIPT","DIFF_RECEIPT","HASH_RECEIPT","GUARD_RECEIPT","AUDIT_RECEIPT","SOURCE_FIDELITY_RECEIPT","ROUTE_PROVENANCE","HOOK_PROBE","PROFILE_PROBE","USER_DECISION"}: raise ContractError("invalid evidence kind")
        exit_code=evidence.get("exit_code")
        if exit_code is not None and type(exit_code) is not int: raise ContractError("exit_code must be an integer")
        if evidence.get("kind")=="TEST_RECEIPT" and type(exit_code) is not int: raise ContractError("TEST_RECEIPT exit_code must be an integer")
        serialized=_dump(evidence).lower()
        if any(pattern.search(serialized) for pattern in SECRET_PATTERNS): raise ContractError("evidence contains secret-like text")
        self._begin()
        try:
            run=self.db.execute("SELECT manifest_hash FROM runs WHERE run_id=?",(evidence["run_id"],)).fetchone()
            if not run: raise StateError("unknown evidence run")
            if run["manifest_hash"]!=evidence["manifest_hash"]: raise ContractError("evidence manifest mismatch")
            if evidence.get("task_id") is not None:
                task=self.db.execute("SELECT run_id,spec_json FROM tasks WHERE task_id=?",(evidence["task_id"],)).fetchone()
                if not task or task["run_id"]!=evidence["run_id"]: raise StateError("unknown evidence task")
                if json.loads(task["spec_json"]).get("manifest_hash")!=evidence["manifest_hash"]: raise ContractError("evidence task manifest mismatch")
            self.db.execute("INSERT INTO evidence(evidence_id,run_id,task_id,kind,source,manifest_hash,base_revision,result_revision,artifact_hash,command_or_ui_step,exit_code,observed_at,limitations,redaction_status,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(evidence["evidence_id"],evidence["run_id"],evidence.get("task_id"),evidence["kind"],evidence["source"],evidence["manifest_hash"],evidence.get("base_revision"),evidence.get("result_revision"),evidence.get("artifact_hash"),evidence.get("command_or_ui_step"),evidence.get("exit_code"),evidence["observed_at"],evidence["limitations"],evidence["redaction_status"],_dump(evidence)))
            self._finish(True); return {"evidence_id":evidence["evidence_id"],"run_id":evidence["run_id"]}
        except Exception: self._finish(False); raise

    @staticmethod
    def _unwrap_source_receipt_payload(payload: dict[str,Any]) -> dict[str,Any]:
        if isinstance(payload, dict) and payload.get("kind")=="SOURCE_FIDELITY_RECEIPT" and isinstance(payload.get("payload"), dict):
            return payload["payload"]
        return payload

    @staticmethod
    def _validate_source_receipt_payload(payload: dict[str,Any], run_id: str, task_id: str, manifest_hash: str, target_manifest_hash: str, result_revision: str, diff_hash: str, expected_commit: str, expected_source_manifest: str, expected_mapping_revision: str, expected_target_manifest: str, expected_target_baseline_manifest: str, expected_mapping_manifest: str, expected_producer_thread_id: str) -> None:
        payload=StateStore._unwrap_source_receipt_payload(payload)
        try:
            receipt=SourceFidelityReceipt(**payload)
        except (TypeError, ValueError, KeyError) as exc:
            raise ContractError("invalid source fidelity receipt schema") from exc
        if receipt.status!="PASS" or receipt.producer_thread_id!=expected_producer_thread_id or receipt.run_id!=run_id or receipt.task_id!=task_id or receipt.scope_manifest_hash!=manifest_hash or receipt.target_manifest_hash!=target_manifest_hash or receipt.target_manifest_hash!=expected_target_manifest or receipt.target_base_manifest_sha256!=expected_target_baseline_manifest or receipt.mapping_manifest_sha256!=expected_mapping_manifest or str(receipt.target_result_revision)!=str(result_revision) or receipt.target_diff_hash!=diff_hash or receipt.reference.get("commit")!=expected_commit or receipt.reference.get("manifest_sha256")!=expected_source_manifest or receipt.mapping_revision!=expected_mapping_revision:
            raise ContractError("source fidelity receipt target binding mismatch")

    @staticmethod
    def _validate_source_dispatch_payload(row: Any, run_id: str, task_id: str, manifest_hash: str, result_revision: str) -> str:
        if row["kind"]!="ROUTE_PROVENANCE" or row["source"]!="codex-runtime" or row["run_id"]!=run_id or row["task_id"]!=task_id or row["manifest_hash"]!=manifest_hash or str(row["result_revision"])!=str(result_revision):
            raise ContractError("source fidelity runtime dispatch evidence binding mismatch")
        try:
            evidence=json.loads(row["payload_json"])
            payload=evidence.get("payload") or {}
            result=payload.get("runtime_dispatch") or {}
            if re.fullmatch(r"[0-9a-f]{64}",str(payload.get("runtime_events_sha256",""))) is None or row["artifact_hash"]!=canonical_hash(result):
                raise ContractError("source dispatch event/hash evidence is incomplete")
            request_data=result.get("request") or {}
            request=RuntimeDispatchRequest(
                parent_thread_id=request_data["parent_thread_id"], task_id=request_data["task_id"],
                requested_model=request_data["requested_model"], requested_effort=request_data["requested_effort"],
                profile_id=request_data["profile_id"], hook_status=request_data["hook_status"],
                sandbox_mode=request_data["requested_sandbox_mode"], role=request_data["role"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError("invalid source fidelity runtime dispatch evidence") from exc
        if request.role!="source_fidelity" or request.task_id!=task_id or request.profile_id not in set(SOURCE_FIDELITY_PROFILE.values()):
            raise ContractError("runtime dispatch is not the required Source Fidelity role")
        if request.sandbox_mode!="read-only":
            raise ContractError("Source Fidelity sandbox was not requested read-only")
        expected=PROFILE_ROUTE_CONTRACT[request.profile_id]
        route=result.get("route_provenance") or {}
        child_id=result.get("child_thread_id")
        refs=set(result.get("evidence_refs") or ())
        if (result.get("admissible") is not True or result.get("lifecycle")!="CHILD_COMPLETED" or result.get("child_started_observed") is not True or result.get("child_completed") is not True or result.get("parent_close_allowed") is not True or result.get("blockers") or not child_id or f"child-thread:{child_id}" not in refs or not any(str(ref).endswith(":settings") for ref in refs) or not any(str(ref).endswith(":child-terminal") for ref in refs)):
            raise ContractError("Source Fidelity child lifecycle is not admissible")
        if result.get("sandbox_observed") is not False:
            raise ContractError("runtime evidence must not claim sandbox observation")
        if route.get("route_status") not in {"PROFILE_VERIFIED","EXPLICIT_ROUTE_VERIFIED"} or route.get("observed_model")!=expected[0] or route.get("observed_effort")!=expected[1] or route.get("source")!="codex-app-server.thread.settings":
            raise ContractError("Source Fidelity child runtime route does not match its role profile")
        if request.requested_model!=expected[0] or request.requested_effort!=expected[1]:
            raise ContractError("Source Fidelity requested route does not match its role profile")
        return child_id

    def validate_audit_receipt_binding(self, receipt: dict[str,Any]) -> None:
        """Validate PASS receipt provenance against the frozen task and persisted evidence."""
        task=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(receipt.get("target_task_id"),)).fetchone()
        if not task: raise StateError("unknown audit task")
        run=self.db.execute("SELECT * FROM runs WHERE run_id=?",(task["run_id"],)).fetchone()
        if not run: raise StateError("unknown audit run")
        if receipt.get("target_manifest_hash")!=run["manifest_hash"]: raise ContractError("audit manifest mismatch")
        result=json.loads(task["result_json"] or "{}"); packet=result.get("packet",{})
        if str(receipt.get("target_result_revision"))!=str(packet.get("result_revision")) or receipt.get("target_diff_hash")!=packet.get("diff_hash"):
            raise ContractError("audit target revision or diff mismatch")
        if receipt.get("decision")!="PASS": return
        spec=json.loads(task["spec_json"])
        provenance=receipt.get("provenance") or {}
        if provenance.get("observed_model")!=spec.get("requested_model") or provenance.get("observed_effort")!=spec.get("requested_effort"):
            raise ContractError("observed route does not match requested model or effort")
        packet_source_refs=set(packet.get("source_fidelity_evidence_refs") or ())
        provenance_source_refs=set(provenance.get("source_fidelity_evidence_refs") or ())
        packet_dispatch_refs=set(packet.get("source_fidelity_dispatch_evidence_refs") or ())
        provenance_dispatch_refs=set(provenance.get("source_fidelity_dispatch_evidence_refs") or ())
        source_refs=packet_source_refs | provenance_source_refs
        if spec.get("source_fidelity_required"):
            if provenance.get("source_fidelity_status")!="PASS" or packet.get("source_fidelity_status")!="PASS" or not source_refs or packet_source_refs!=provenance_source_refs or not packet_dispatch_refs or packet_dispatch_refs!=provenance_dispatch_refs:
                raise ContractError("source fidelity PASS evidence is required")
        refs=set(packet.get("evidence_refs") or ()) | set(provenance.get("evidence_refs") or ()) | source_refs | packet_dispatch_refs | provenance_dispatch_refs
        if not refs: raise ContractError("PASS requires bound evidence references")
        placeholders=",".join("?" for _ in refs)
        rows=self.db.execute(f"SELECT * FROM evidence WHERE evidence_id IN ({placeholders})",tuple(refs)).fetchall()
        by_id={row["evidence_id"]:row for row in rows}
        if set(by_id)!=refs: raise ContractError("audit evidence reference is missing")
        for row in rows:
            if row["run_id"]!=task["run_id"] or row["task_id"] not in {None,task["task_id"]} or row["manifest_hash"]!=run["manifest_hash"]:
                raise ContractError("audit evidence binding mismatch")
        if spec.get("source_fidelity_required"):
            if len(packet_dispatch_refs)!=1: raise ContractError("exactly one Source Fidelity runtime dispatch receipt is required")
            dispatch_rows=[row for row in rows if row["evidence_id"] in packet_dispatch_refs]
            if len(dispatch_rows)!=1: raise ContractError("Source Fidelity runtime dispatch evidence is missing")
            producer_thread_id=self._validate_source_dispatch_payload(dispatch_rows[0],task["run_id"],task["task_id"],run["manifest_hash"],packet.get("result_revision"))
            source_rows=[row for row in rows if row["evidence_id"] in source_refs and row["kind"]=="SOURCE_FIDELITY_RECEIPT" and row["source"]=="source-fidelity-agent"]
            if set(row["evidence_id"] for row in source_rows)!=source_refs:
                raise ContractError("source fidelity evidence reference is missing or wrong kind")
            for row in source_rows:
                try: source_payload=json.loads(row["payload_json"]).get("payload") or {}
                except (TypeError,ValueError): source_payload={}
                self._validate_source_receipt_payload(source_payload, task["run_id"], task["task_id"], run["manifest_hash"], packet.get("source_fidelity_target_manifest_hash"), packet.get("result_revision"), packet.get("diff_hash"), spec.get("source_reference_commit"), spec.get("source_reference_manifest_sha256"), spec.get("source_mapping_revision"), spec.get("source_target_manifest_sha256"), spec.get("source_target_baseline_manifest_sha256"), spec.get("source_mapping_manifest_sha256"), producer_thread_id)
        route_refs=set(provenance.get("evidence_refs") or ())
        route_ok=False
        for row in rows:
            if row["evidence_id"] not in route_refs: continue
            try: route_payload=json.loads(row["payload_json"]).get("payload") or {}
            except (TypeError,ValueError): route_payload={}
            if row["source"] in {"codex-runtime","profile-runtime","hook-runtime"} and route_payload.get("observed_model")==spec.get("requested_model") and route_payload.get("observed_effort")==spec.get("requested_effort"):
                route_ok=True
        if not route_ok: raise ContractError("route evidence does not bind observed model or effort")
        test_rows=[row for row in rows if row["kind"]=="TEST_RECEIPT" and row["exit_code"]==0]
        for check in spec.get("acceptance_checks",()):
            if not isinstance(check,str) or not check or not any(check==row["command_or_ui_step"] for row in test_rows):
                raise ContractError("required acceptance check lacks successful evidence")
        for test in packet.get("test_receipts") or ():
            if not isinstance(test,dict) or not isinstance(test.get("command"),str) or not test["command"] or type(test.get("exit_code")) is not int or test["exit_code"]!=0:
                raise ContractError("handoff test receipt is not successful")
            if not any(test["command"]==row["command_or_ui_step"] for row in test_rows):
                raise ContractError("handoff test command lacks persisted evidence")

    def validate_source_fidelity_packet(self, task_id: str, packet: dict[str,Any]) -> None:
        """Fail closed before a source-sensitive handoff enters AUDIT_PENDING."""
        task=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if not task: raise StateError("unknown source fidelity task")
        spec=json.loads(task["spec_json"])
        if not spec.get("source_fidelity_required"): return
        run=self.db.execute("SELECT * FROM runs WHERE run_id=?",(task["run_id"],)).fetchone()
        if not run: raise StateError("unknown source fidelity run")
        refs=set(packet.get("source_fidelity_evidence_refs") or ())
        if packet.get("source_fidelity_status")!="PASS" or not refs: raise ContractError("source fidelity PASS evidence is required")
        dispatch_refs=set(packet.get("source_fidelity_dispatch_evidence_refs") or ())
        evidence_refs=set(packet.get("evidence_refs") or ())
        if len(dispatch_refs)!=1 or not refs.issubset(evidence_refs) or not dispatch_refs.issubset(evidence_refs): raise ContractError("source fidelity receipt and runtime dispatch must be included in handoff evidence")
        all_refs=refs|dispatch_refs
        placeholders=",".join("?" for _ in all_refs)
        rows=self.db.execute(f"SELECT * FROM evidence WHERE evidence_id IN ({placeholders})",tuple(all_refs)).fetchall()
        if {row["evidence_id"] for row in rows}!=all_refs: raise ContractError("source fidelity evidence reference is missing")
        dispatch_rows=[row for row in rows if row["evidence_id"] in dispatch_refs]
        if len(dispatch_rows)!=1: raise ContractError("source fidelity runtime dispatch evidence is missing")
        producer_thread_id=self._validate_source_dispatch_payload(dispatch_rows[0],task["run_id"],task_id,run["manifest_hash"],packet.get("result_revision"))
        source_rows=[row for row in rows if row["evidence_id"] in refs]
        for row in source_rows:
            if row["kind"]!="SOURCE_FIDELITY_RECEIPT" or row["source"]!="source-fidelity-agent" or row["run_id"]!=task["run_id"] or row["task_id"]!=task_id or row["manifest_hash"]!=run["manifest_hash"]:
                raise ContractError("source fidelity evidence binding mismatch")
            try: payload=json.loads(row["payload_json"]).get("payload") or {}
            except (TypeError,ValueError): payload={}
            payload=self._unwrap_source_receipt_payload(payload)
            self._validate_source_receipt_payload(payload, task["run_id"], task_id, run["manifest_hash"], packet.get("source_fidelity_target_manifest_hash"), packet.get("result_revision"), packet.get("diff_hash"), spec.get("source_reference_commit"), spec.get("source_reference_manifest_sha256"), spec.get("source_mapping_revision"), spec.get("source_target_manifest_sha256"), spec.get("source_target_baseline_manifest_sha256"), spec.get("source_mapping_manifest_sha256"), producer_thread_id)
            required_tests=set(payload.get("tests") or ())
            test_refs=set(payload.get("evidence_refs") or ())
            if not required_tests or not test_refs: raise ContractError("source fidelity tests and evidence refs are required")
            test_placeholders=",".join("?" for _ in test_refs)
            test_rows=self.db.execute(f"SELECT * FROM evidence WHERE evidence_id IN ({test_placeholders})",tuple(test_refs)).fetchall()
            if {test_row["evidence_id"] for test_row in test_rows}!=test_refs: raise ContractError("source fidelity test evidence is missing")
            proven_tests=set()
            for test_row in test_rows:
                if test_row["kind"]!="TEST_RECEIPT" or test_row["run_id"]!=task["run_id"] or test_row["task_id"]!=task_id or test_row["manifest_hash"]!=run["manifest_hash"] or type(test_row["exit_code"]) is not int or test_row["exit_code"]!=0:
                    raise ContractError("source fidelity test evidence binding mismatch")
                proven_tests.add(test_row["command_or_ui_step"])
            if required_tests-proven_tests: raise ContractError("source fidelity regression tests lack successful receipts")

    def store_audit_receipt(self, receipt: dict[str,Any], request_key: str|None=None):
        required={"audit_id","auditor_actor","target_manifest_hash","target_task_id","target_result_revision","target_diff_hash","decision","writer_actor"}
        if not required.issubset(receipt): raise ContractError("incomplete audit receipt")
        self._begin()
        try:
            payload=dict(receipt); replay=self._idem(request_key,payload)
            if replay is not None: self._finish(True); return replay
            task=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(receipt["target_task_id"],)).fetchone()
            if not task: raise StateError("unknown audit task")
            if task["state"]!="AUDIT_PENDING": raise StateError("audit receipt requires AUDIT_PENDING task")
            run=self.db.execute("SELECT * FROM runs WHERE run_id=?",(task["run_id"],)).fetchone()
            if receipt["target_manifest_hash"]!=run["manifest_hash"]: raise ContractError("audit manifest mismatch")
            result=json.loads(task["result_json"] or "{}"); packet=result.get("packet",{})
            if str(receipt["target_result_revision"])!=str(packet.get("result_revision")) or receipt["target_diff_hash"]!=packet.get("diff_hash"): raise ContractError("audit target revision or diff mismatch")
            if receipt["auditor_actor"]==receipt["writer_actor"] or receipt["auditor_actor"]==task["owner"]: raise ContractError("audit actor is not independent")
            AuditReceipt(**receipt)
            self.validate_audit_receipt_binding(receipt)
            if receipt["decision"]=="PASS":
                if any(receipt.get(key)!="PASS" for key in ("scope_result","behavior_result","evidence_result")): raise ContractError("PASS requires all audit dimensions to PASS")
                if receipt.get("route_result") not in {"PROFILE_VERIFIED","EXPLICIT_ROUTE_VERIFIED"}: raise ContractError("PASS requires verified route")
                if receipt.get("provenance",{}).get("hook_status") not in {"HOOK_ENFORCED","HOOK_VERIFIED"}: raise ContractError("PASS requires verified hook provenance")
                if receipt.get("required_corrections"): raise ContractError("PASS has required corrections")
            self.db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?,?,?)",(receipt["audit_id"],task["run_id"],task["task_id"],receipt["target_manifest_hash"],str(receipt["target_result_revision"]),receipt["target_diff_hash"],receipt["auditor_actor"],receipt["writer_actor"],receipt["decision"],_dump(receipt),_now()))
            response={"audit_id":receipt["audit_id"],"decision":receipt["decision"],"task_id":task["task_id"]}; self._store_idem(request_key,payload,response); self._finish(True); return response
        except Exception: self._finish(False); raise

    def list_receipts(self, task_id: str):
        rows=self.db.execute("SELECT * FROM receipts WHERE task_id=? ORDER BY created_at",(task_id,)).fetchall(); return [dict(row) for row in rows]

    def record_notification_intent(self, intent_id: str, idempotency_key: str, payload: dict[str,Any], run_id: str|None=None, task_id: str|None=None):
        now=_now(); self._begin()
        try:
            row=self.db.execute("SELECT * FROM notification_intents WHERE idempotency_key=?",(idempotency_key,)).fetchone()
            if row:
                if json.loads(row["payload_json"])!=payload: raise IdempotencyConflict("notification idempotency key reused with different payload")
                self._finish(True); return dict(row)
            self.db.execute("INSERT INTO notification_intents VALUES(?,?,?,?,?,?,?,?,?,?)",(intent_id,idempotency_key,run_id,task_id,"PENDING",_dump(payload),0,None,now,now))
            self._finish(True); return {"intent_id":intent_id,"status":"PENDING","attempts":0}
        except Exception: self._finish(False); raise

    def update_notification_intent(self, intent_id: str, status: str, error: str|None=None):
        if status not in {"PENDING","SENT","FAILED","SUPPRESSED"}: raise ContractError("invalid notification status")
        self._begin()
        try:
            row=self.db.execute("SELECT attempts FROM notification_intents WHERE intent_id=?",(intent_id,)).fetchone()
            if not row: raise StateError("unknown notification intent")
            attempts=int(row["attempts"])+(1 if status in {"SENT","FAILED"} else 0)
            self.db.execute("UPDATE notification_intents SET status=?,last_error=?,attempts=?,updated_at=? WHERE intent_id=?",(status,error,attempts,_now(),intent_id))
            self._finish(True); return {"intent_id":intent_id,"status":status,"attempts":attempts}
        except Exception: self._finish(False); raise

    def pending_notifications(self):
        rows=self.db.execute("SELECT * FROM notification_intents WHERE status IN ('PENDING','FAILED') ORDER BY created_at").fetchall(); return [dict(row) for row in rows]

    def recover_outbox(self) -> int:
        now=_now(); self._begin()
        try:
            cur=self.db.execute("UPDATE outbox SET status='PENDING',claimed_by=NULL,claimed_until=NULL WHERE status='CLAIMED' AND claimed_until IS NOT NULL AND claimed_until<=?",(now,))
            self._finish(True); return int(cur.rowcount)
        except Exception: self._finish(False); raise

    def claim_outbox(self, actor: str, limit: int=10, lease_seconds: int=60) -> list[dict[str,Any]]:
        validate_id(actor,"outbox_actor")
        if limit<1 or limit>100 or lease_seconds<1: raise ContractError("invalid outbox claim limits")
        now=_now(); self._begin()
        try:
            self.db.execute("UPDATE outbox SET status='PENDING',claimed_by=NULL,claimed_until=NULL WHERE status='CLAIMED' AND claimed_until IS NOT NULL AND claimed_until<=?",(now,))
            rows=self.db.execute("SELECT * FROM outbox WHERE status IN ('PENDING','FAILED') ORDER BY outbox_id LIMIT ?",(limit,)).fetchall()
            until=now+lease_seconds; result=[]
            for row in rows:
                cur=self.db.execute("UPDATE outbox SET status='CLAIMED',claimed_by=?,claimed_until=?,attempts=attempts+1 WHERE outbox_id=? AND status IN ('PENDING','FAILED')",(actor,until,row["outbox_id"]))
                if cur.rowcount!=1: continue
                item=dict(row); item.update({"status":"CLAIMED","claimed_by":actor,"claimed_until":until,"attempts":int(row["attempts"])+1}); result.append(item)
            self._finish(True); return result
        except Exception: self._finish(False); raise

    def complete_outbox(self, outbox_id: int, actor: str, status: str, result: dict[str,Any]|None=None, error: str|None=None) -> dict[str,Any]:
        validate_id(actor,"outbox_actor")
        if status not in {"SENT","FAILED","SUPPRESSED"}: raise ContractError("invalid outbox completion status")
        self._begin()
        try:
            row=self.db.execute("SELECT * FROM outbox WHERE outbox_id=?",(int(outbox_id),)).fetchone()
            if not row: raise StateError("unknown outbox item")
            if row["status"] in {"SENT","SUPPRESSED"}:
                self._finish(True); return dict(row)
            if row["status"]!="CLAIMED" or row["claimed_by"]!=actor: raise StateError("outbox claim ownership required")
            self.db.execute("UPDATE outbox SET status=?,last_error=?,result_json=?,completed_at=?,claimed_by=NULL,claimed_until=NULL WHERE outbox_id=?",(status,(error or "")[:256] or None,_dump(result or {}),_now(),int(outbox_id)))
            updated=self.db.execute("SELECT * FROM outbox WHERE outbox_id=?",(int(outbox_id),)).fetchone()
            self._finish(True); return dict(updated)
        except Exception: self._finish(False); raise

    def pending_outbox(self) -> list[dict[str,Any]]:
        now=_now()
        rows=self.db.execute("SELECT * FROM outbox WHERE status='PENDING' OR (status='CLAIMED' AND claimed_until<=?) OR status='FAILED' ORDER BY outbox_id",(now,)).fetchall()
        return [dict(row) for row in rows]

    def close(self): self.db.close()
