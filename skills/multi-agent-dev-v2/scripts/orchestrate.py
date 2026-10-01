#!/usr/bin/env python3
"""Controller-only V2.1 orchestration CLI; stdin/stdout are one-line JSON."""
from __future__ import annotations
import argparse, json, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from parallel_manifest import ContractError, canonical_hash, parse_manifest, validate_fs_paths, strict_loads
from state_store import StateStore, StateError, StaleRevision, IdempotencyConflict, LeaseError
from lease_store import LeaseStore
from task_scheduler import Scheduler
from semantic_guard import packet_from_dict, inspect_handoff
from handoff_contract import HandoffPacket
from audit_receipt import AuditReceipt, validate_receipt
from runtime_dispatch import RuntimeDispatchRequest, collect_child_provenance

EXIT={"ok":0,"schema":2,"conflict":3,"gate":4,"internal":5}
def reply(ok: bool, code: str, data=None, entity_revision=None, evidence_refs=None):
    return {"ok":ok,"code":code,"entity_revision":entity_revision,"data":data,"evidence_refs":evidence_refs or []}

def handle(state: StateStore, op: str, request: dict):
    payload=request.get("payload") or {}; actor=request.get("actor_id","main"); idem=request.get("idempotency_key")
    if op=="runtime-gate":
        runtime_request=RuntimeDispatchRequest(**(payload.get("request") or {}))
        result=collect_child_provenance(runtime_request,payload.get("events") or [])
        return reply(result.admissible,"OK" if result.admissible else "GATE_HOLD",result.as_dict(),evidence_refs=list(result.evidence_refs))
    if op=="bind-source-dispatch":
        runtime_request=RuntimeDispatchRequest(**(payload.get("request") or {}))
        if runtime_request.role!="source_fidelity": raise ContractError("source dispatch binding requires the source_fidelity role")
        run=state.get_run(payload["run_id"]); task=state.get_task(runtime_request.task_id)
        if not run or not task: raise StateError("unknown source dispatch run or task")
        if task["run_id"]!=payload["run_id"] or task["spec"].get("manifest_hash")!=run["manifest_hash"] or not task["spec"].get("source_fidelity_required"):
            raise ContractError("source dispatch does not bind a frozen source-sensitive task")
        if payload.get("manifest_hash")!=run["manifest_hash"] or not payload.get("result_revision") or not payload.get("evidence_id"):
            raise ContractError("source dispatch evidence needs manifest, target revision and evidence id")
        events=payload.get("events") or []
        result=collect_child_provenance(runtime_request,events)
        if not result.admissible: return reply(False,"GATE_HOLD",result.as_dict(),task["revision"],list(result.evidence_refs))
        result_data=result.as_dict()
        state.record_evidence({"evidence_id":payload["evidence_id"],"run_id":payload["run_id"],"task_id":runtime_request.task_id,"kind":"ROUTE_PROVENANCE","source":"codex-runtime","manifest_hash":run["manifest_hash"],"base_revision":payload.get("base_revision"),"result_revision":payload["result_revision"],"artifact_hash":canonical_hash(result_data),"command_or_ui_step":"Codex app-server source_fidelity child lifecycle/settings","exit_code":0,"observed_at":datetime.now(timezone.utc).isoformat(),"limitations":"Runtime events must come from the active Codex app-server; requested read-only sandbox is not runtime-observed.","redaction_status":"REDACTED","payload":{"runtime_dispatch":result_data,"runtime_events_sha256":canonical_hash(events),"sandbox_observed":False}})
        return reply(True,"OK",{"runtime_dispatch":result_data,"runtime_events_sha256":canonical_hash(events),"sandbox_observed":False},task["revision"],[payload["evidence_id"]])
    if op=="init":
        raw_manifest=payload.get("manifest",payload); manifest=parse_manifest(raw_manifest)
        if payload.get("workspace_root"): validate_fs_paths(payload["workspace_root"],list(manifest.allowed_paths)+list(manifest.read_paths))
        state.create_run(manifest,idem)
        if not state.list_tasks(manifest.run_id): state.add_tasks(manifest.run_id,[manifest.runtime_task(t.task_id) for t in manifest.task_templates])
        run=state.get_run(manifest.run_id)
        init_epoch=state.acquire_controller(actor)
        if run["state"]=="INTAKE":
            for next_state in ("DESIGN_PENDING","SCOPE_FROZEN","DISPATCHABLE"):
                run=state.transition_run(manifest.run_id,run["revision"],next_state,actor,"manifest_frozen",{},init_epoch,manifest.manifest_hash())
        run=dict(state.get_run(manifest.run_id)); run["manifest_hash"]=manifest.manifest_hash(); return reply(True,"OK",run,run["revision"],["manifest:"+run["manifest_hash"]])
    if op=="plan":
        added=state.add_tasks(payload["run_id"],payload["task_specs"],idem); return reply(True,"OK",added)
    if op=="dispatch-next":
        takeover=bool(request.get("takeover") or payload.get("takeover"))
        epoch=int(request["controller_epoch"]) if request.get("controller_epoch") is not None else state.acquire_controller(actor,takeover=takeover)
        run=state.get_run(payload["run_id"])
        if run["state"]=="DISPATCHABLE": state.transition_run(payload["run_id"],run["revision"],"RUNNING",actor,"dispatch_started",{},epoch,run["manifest_hash"])
        leases=LeaseStore(state); items=Scheduler(state,leases).dispatch_next(payload["run_id"],actor,epoch); return reply(True,"OK",{"controller_epoch":epoch,"items":items})
    if op in {"bind-start","checkpoint","handoff","cancel"}:
        task_id=payload["task_id"]; task=state.get_task(task_id)
        if not task: raise StateError("unknown task")
        expected=int(request.get("expected_revision",payload.get("expected_revision",task["revision"])))
        epoch=request.get("controller_epoch",payload.get("controller_epoch")); fence=payload.get("fencing_token"); fences=payload.get("fencing_tokens") or payload.get("lease_fencing_tokens")
        if payload.get("lease_id") and (epoch is None or fence is None): raise ContractError("controller epoch and fencing token are required")
        manifest_hash=task["spec"].get("manifest_hash")
        attempt_id=payload.get("attempt_id") or (task.get("result") or {}).get("attempt_id") or "attempt-1"
        value={**payload,"attempt_id":attempt_id} if op=="bind-start" else payload
        if op=="handoff":
            packet=packet_from_dict(payload["packet"]); run=state.get_run(task["run_id"])
            fences=fences or packet.lease_fencing_tokens
            required_namespaces=list(task["spec"].get("namespace") or ["task:"+task_id])
            if len(required_namespaces)>1 and (not fences or set(fences)!=set(required_namespaces)): raise ContractError("multi-namespace handoff requires complete fencing bundle")
            if packet.task_id!=task_id or packet.run_id!=task["run_id"]: raise ContractError("handoff task or run binding mismatch")
            if packet.manifest_hash!=run["manifest_hash"] or packet.lease_id!=payload.get("lease_id") or packet.lease_id!=task.get("lease_id"): raise ContractError("handoff manifest or lease binding mismatch")
            if packet.state_revision!=expected: raise StaleRevision("handoff state revision mismatch")
            if packet.attempt_id!=attempt_id: raise ContractError("handoff attempt binding mismatch")
            if set(packet.changed_paths)-set(task["spec"].get("write_set",())): raise ContractError("handoff changed path escapes frozen write_set")
            frozen_packet=HandoffPacket(**{**packet.__dict__,"write_set":tuple(task["spec"].get("write_set",())),"lease_fencing_tokens":dict(fences) if fences else packet.lease_fencing_tokens})
            source_fidelity_required=bool(task["spec"].get("source_fidelity_required",False))
            if source_fidelity_required:
                state.validate_source_fidelity_packet(task_id, frozen_packet.as_dict())
            guard=inspect_handoff(frozen_packet,run["manifest_hash"],int(payload.get("retry_count",0)),source_fidelity_required=source_fidelity_required); value={"packet":frozen_packet.as_dict(),"guard":guard.as_dict()}
            if guard.decision in {"BLOCK","NEEDS_USER_DECISION"}: return reply(False,"GATE_HOLD",value,task["revision"],list(packet.evidence_refs))
            raw_idem={"operation":"handoff","payload":payload,"actor_id":actor,"expected_revision":expected,"controller_epoch":epoch}
            if idem:
                replay=state.replay_idempotency(idem,raw_idem)
                if replay is not None:
                    replay_data={"task_id":task_id,"state":replay["state"],"revision":replay["revision"],"handoff":replay.get("handoff",value),"transition":replay}
                    return reply(True,"OK",replay_data,replay.get("revision"),list(packet.evidence_refs))
            current=task["state"]
            chains={"RUNNING":["CHECKPOINTED","WAITING_HANDOFF","AUDIT_PENDING"],"CHECKPOINTED":["WAITING_HANDOFF","AUDIT_PENDING"],"WAITING_HANDOFF":["AUDIT_PENDING"]}
            chain=chains.get(current)
            if not chain: raise StateError("handoff requires a non-terminal task state")
            result=state.transition_task_chain(task_id,expected,chain,actor,"handoff",value,idem,raw_idem,payload.get("lease_id"),int(epoch) if epoch is not None else None,int(fence) if fence is not None else None,manifest_hash,fences)
            return reply(True,"OK",{"task_id":task_id,"state":result["state"],"revision":result["revision"],"handoff":value,"transition":result},result["revision"],list(packet.evidence_refs))
        new_state={"bind-start":"RUNNING","checkpoint":"CHECKPOINTED","cancel":"CANCELLED"}[op]
        result=state.transition_task(task_id,expected,new_state,actor,op,value,idem,payload.get("lease_id"),"none",int(epoch) if epoch is not None else None,int(fence) if fence is not None else None,manifest_hash,fences); return reply(True,"OK",result,result["revision"],payload.get("evidence_refs",[]))
    if op=="attach-receipt":
        task=state.get_task(payload["task_id"]); receipt_data=payload["receipt"]
        if not task: raise StateError("unknown task")
        receipt=AuditReceipt(**receipt_data); run=state.get_run(task["run_id"]); packet=(task["result"] or {}).get("packet",{})
        validate_receipt(receipt,run["manifest_hash"],str(packet.get("result_revision")),packet.get("diff_hash",""))
        if receipt.target_task_id!=task["task_id"] or receipt.writer_actor!=task.get("owner"): raise ContractError("audit task or writer binding mismatch")
        if receipt.decision=="PASS" and (packet.get("route_provenance",{}).get("route_status")!=receipt.route_result or packet.get("hook_status")!=receipt.provenance.get("hook_status")): raise ContractError("audit route or hook evidence mismatch")
        stored=state.store_audit_receipt(receipt.as_dict(),idem)
        if receipt.decision!="PASS": return reply(False,"GATE_HOLD",{"receipt":stored},task["revision"],list(receipt.findings))
        epoch=request.get("controller_epoch",payload.get("controller_epoch")); fence=payload.get("fencing_token")
        if task.get("lease_id") and (epoch is None or fence is None): raise ContractError("controller epoch and fencing token are required")
        transition_actor=task.get("owner") or actor
        result=state.transition_task(task["task_id"],int(request.get("expected_revision",task["revision"])),"ACCEPTED",transition_actor,"audit_pass",{"packet":packet,"receipt":stored},None,task.get("lease_id"),"none",int(epoch) if epoch is not None else None,int(fence) if fence is not None else None,run["manifest_hash"],payload.get("fencing_tokens") or payload.get("lease_fencing_tokens"))
        return reply(True,"OK",result,result["revision"],payload.get("evidence_refs",[]))
    if op=="retry":
        task=state.get_task(payload["task_id"])
        if not task: raise StateError("unknown task")
        attempts=int(state.db.execute("SELECT COUNT(*) AS n FROM attempts WHERE task_id=?",(task["task_id"],)).fetchone()["n"])
        attempt_id=payload.get("attempt_id") or ("attempt-"+str(attempts+1) if not idem else "retry-"+idem)
        retry_payload={"task_id":task["task_id"],"actor":actor,"reason":payload.get("reason",""),"evidence_refs":list(payload.get("evidence_refs",[])),"attempt_id":attempt_id,"controller_epoch":request.get("controller_epoch"),"fencing_token":payload.get("fencing_token"),"manifest_hash":task["spec"].get("manifest_hash"),"fencing_tokens":payload.get("fencing_tokens") or payload.get("lease_fencing_tokens")}
        replay=state.replay_idempotency(idem,retry_payload)
        if replay is not None: return reply(True,"OK",replay,replay.get("revision"),payload.get("evidence_refs",[]))
        max_retries=int(task["spec"].get("max_retries",0))
        if attempts>=max_retries: return reply(False,"GATE_HOLD",{"reason":"BUDGET_EXHAUSTED","attempts":attempts},task["revision"])
        if attempts and not payload.get("evidence_refs"): return reply(False,"GATE_HOLD",{"reason":"RETRY_WITHOUT_NEW_EVIDENCE"},task["revision"])
        result=state.retry_task(task["task_id"],actor,payload.get("reason",""),payload.get("evidence_refs",[]),attempt_id,idem,request.get("controller_epoch"),payload.get("fencing_token"),task["spec"].get("manifest_hash"),payload.get("fencing_tokens") or payload.get("lease_fencing_tokens"))
        return reply(True,"OK",result,result["revision"],payload.get("evidence_refs",[]))
    if op=="status":
        run=state.get_run(payload["run_id"]); return reply(True,"OK",{"run":run,"tasks":state.list_tasks(payload["run_id"])},run["revision"] if run else None)
    if op=="recover":
        count=LeaseStore(state).expire(); return reply(True,"OK",{"expired":count})
    if op=="integrate-check":
        run=state.get_run(payload["run_id"])
        if not run: raise StateError("unknown run")
        if run["state"] not in {"RUNNING","EVIDENCE_COLLECTION"}:
            return reply(False,"GATE_HOLD",{"ready":False,"blockers":["run:"+run["state"]]},run["revision"])
        ok,blockers=Scheduler(state,LeaseStore(state)).can_ready_to_merge(payload["run_id"]); run_manifest_hash=run["manifest_hash"]
        epoch=int(request["controller_epoch"]) if request.get("controller_epoch") is not None else state.acquire_controller(actor,takeover=bool(payload.get("takeover")))
        if run["state"]=="RUNNING": run=state.transition_run(payload["run_id"],run["revision"],"EVIDENCE_COLLECTION",actor,"evidence_collection_started",{},epoch,run_manifest_hash)
        if ok and run["state"]=="EVIDENCE_COLLECTION": result=state.transition_run(payload["run_id"],run["revision"],"READY_TO_MERGE",actor,"all_required_tasks_accepted",{},epoch,run_manifest_hash); return reply(True,"OK",result,result["revision"])
        return reply(ok,"OK" if ok else "GATE_HOLD",{"ready":ok,"blockers":blockers},run["revision"])
    raise ContractError("unknown operation")

def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument("operation",choices=["init","plan","dispatch-next","bind-start","checkpoint","handoff","attach-receipt","retry","status","cancel","recover","integrate-check","runtime-gate","bind-source-dispatch"]); parser.add_argument("--state-dir",default="")
    args=parser.parse_args(argv)
    try:
        request=strict_loads(sys.stdin.read().strip() or "{}")
        if not isinstance(request,dict): raise ContractError("request must be an object")
    except (TypeError,json.JSONDecodeError,ContractError) as exc: print(json.dumps(reply(False,"SCHEMA",{"error":str(exc)}),separators=(",",":"))); return EXIT["schema"]
    state_path=Path(args.state_dir or (Path(tempfile.gettempdir())/"multi-agent-dev-v2"/"state.sqlite3")); state=StateStore(state_path)
    try: result=handle(state,args.operation,request); print(json.dumps(result,ensure_ascii=False,separators=(",",":"))); return EXIT["ok"] if result["ok"] else EXIT["gate"]
    except (ContractError,KeyError,TypeError,ValueError,json.JSONDecodeError) as exc: print(json.dumps(reply(False,"SCHEMA",{"error":str(exc)},None)),file=sys.stdout); return EXIT["schema"]
    except (StaleRevision,IdempotencyConflict,LeaseError) as exc: print(json.dumps(reply(False,"CONFLICT",{"error":str(exc)},None)),file=sys.stdout); return EXIT["conflict"]
    except (StateError,OSError) as exc: print(json.dumps(reply(False,"INTERNAL",{"error":str(exc)},None)),file=sys.stdout); return EXIT["internal"]
    finally: state.close()

if __name__=="__main__": raise SystemExit(main())
