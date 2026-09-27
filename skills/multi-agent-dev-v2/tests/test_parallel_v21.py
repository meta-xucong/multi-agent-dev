from __future__ import annotations
import tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from parallel_manifest import *
from state_store import StateStore, StaleRevision, IdempotencyConflict
from lease_store import LeaseStore, LeaseError
from task_scheduler import Scheduler
from route_provenance import compare_requested_observed
from handoff_contract import HandoffPacket
from semantic_guard import inspect_handoff
from audit_receipt import AuditReceipt, validate_receipt
from notification_state import NotificationState
from worker_adapter import WorkerAdapter, WorkerLaunchTicket
from evidence_index import EvidenceIndex, EvidenceRecord

def manifest():
    t1=TaskTemplate("task-a","execute","CONTRACT_FROZEN","D0","I1","A0","gpt-6-luna","high","workspace-write",write_set=("src/a.py",),namespace=("ns-a",),acceptance_checks=("unit",))
    t2=TaskTemplate("task-b","test","INTEGRATION","D0","I0","A0","gpt-6-luna","low","read-only",read_set=("src/a.py",),dependency_ids=("task-a",))
    return ScopeManifest("run-1","goal",("no external",),({"id":"c1"},),({"id":"r1"},),"base","0"*64,("src",),("secrets",),("src",),"D0","I1","A0","CONTRACT_FROZEN",{"main":"main","integrator":"main","audit":"audit"},(t1,t2),2,4,("tests",))

class ParallelV21Tests(unittest.TestCase):
    def test_canonical_vector_and_manifest_binding(self):
        self.assertEqual(canonical_json({}),b"{}")
        m=manifest(); self.assertEqual(len(m.manifest_hash()),64); self.assertEqual(m.runtime_task("task-a")["manifest_hash"],m.manifest_hash())
        self.assertNotIn("manifest_hash",m.payload_without_hash()["task_templates"][0])

    def test_path_and_duplicate_rejected(self):
        with self.assertRaises(ContractError): validate_path("../x")
        with self.assertRaises(ContractError): validate_path("C:/x")
        with self.assertRaises(ContractError): ScopeManifest(**{**manifest().__dict__,"allowed_paths":("src/A","src/a")})

    def test_route_provenance_unverified_and_mismatch(self):
        p=compare_requested_observed("m","high",None,None,"none"); self.assertEqual(p.route_status,"ROUTE_UNVERIFIED")
        p=compare_requested_observed("m","high","other","high","runtime"); self.assertEqual(p.route_status,"ROUTE_MISMATCH")

    def test_state_cas_and_idempotency(self):
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); r=s.create_run(manifest(),"req-init"); s.add_tasks("run-1",[manifest().runtime_task("task-a"),manifest().runtime_task("task-b")])
            epoch=s.acquire_controller("main"); lease=LeaseStore(s).acquire("run-1","task-a","ns-a","main",epoch)
            a=s.transition_task("task-a",1,"RUNNING","main","start",{},"req-start",lease["lease_id"],"none",epoch,lease["fencing_token"],manifest().manifest_hash())
            replay=s.transition_task("task-a",1,"RUNNING","main","start",{},"req-start",lease["lease_id"],"none",epoch,lease["fencing_token"],manifest().manifest_hash()); self.assertEqual(a,replay)
            with self.assertRaises(StaleRevision): s.transition_task("task-a",1,"CHECKPOINTED","main","bad",{},None,lease["lease_id"],"none",epoch,lease["fencing_token"],manifest().manifest_hash())
            with self.assertRaises(IdempotencyConflict): s.transition_task("task-a",1,"RUNNING","main","changed",{},"req-start",lease["lease_id"],"none",epoch,lease["fencing_token"],manifest().manifest_hash())
            s.close()

    def test_lease_fence_and_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); s.create_run(manifest()); s.add_tasks("run-1",[manifest().runtime_task("task-a")]); l=LeaseStore(s); epoch=s.acquire_controller("controller"); lease=l.acquire("run-1","task-a","ns-a","worker",epoch,1); self.assertEqual(lease["status"],"ACTIVE")
            with self.assertRaises(LeaseError): l.validate(lease["lease_id"],"task-a","other",1,lease["fencing_token"])
            s.db.execute("UPDATE leases SET expires_at=0 WHERE lease_id=?",(lease["lease_id"],)); self.assertEqual(l.expire(),1); self.assertEqual(s.get_task("task-a")["state"],"UNKNOWN"); s.close()

    def test_scheduler_respects_dependency_and_namespace(self):
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); s.create_run(manifest()); s.add_tasks("run-1",[manifest().runtime_task("task-a"),manifest().runtime_task("task-b")]); l=LeaseStore(s); epoch=s.acquire_controller("controller")
            for next_state in ("DESIGN_PENDING","SCOPE_FROZEN","DISPATCHABLE"):
                run=s.get_run("run-1"); s.transition_run("run-1",run["revision"],next_state,"controller","test",{},epoch,manifest().manifest_hash())
            sch=Scheduler(s,l); self.assertEqual([x["task_id"] for x in sch.ready("run-1")],["task-a"]); dispatched=sch.dispatch_next("run-1","worker",epoch); self.assertEqual(len(dispatched),1); self.assertEqual(sch.ready("run-1"),[]); s.close()

    def packet(self, route="ROUTE_UNVERIFIED"):
        return HandoffPacket("task-a","run-1","attempt-1","h"*64,1,"lease","base","result","SUCCEEDED",("src/a.py",),"d"*64,("a"*64,),({"command":"unit","exit_code":0},),("ev-1",),None,{"route_status":route},"HOOK_UNVERIFIED","WARN",(),(),("audit",),{"tokens":1},("src/a.py",))

    def test_handoff_and_guard_fail_closed(self):
        p=self.packet(); g=inspect_handoff(p,"h"*64); self.assertEqual(g.decision,"WARN"); self.assertIn("ROUTE_UNVERIFIED",g.reason_codes)
        with self.assertRaises(ContractError): HandoffPacket(**{**p.__dict__,"audit_receipt":{"decision":"PASS"}})
        self.assertEqual(inspect_handoff(self.packet("ROUTE_MISMATCH"),"h"*64).decision,"BLOCK")

    def test_audit_separation_and_binding(self):
        r=AuditReceipt("a1","auditor","h"*64,"task-a","result","d"*64,"PASS","PASS","PASS","ROUTE_UNVERIFIED",(),(),"DEGRADED",{},"now","writer"); validate_receipt(r,"h"*64,"result","d"*64)
        with self.assertRaises(ContractError): AuditReceipt(**{**r.__dict__,"auditor_actor":"writer"})

    def test_strict_json_and_illegal_transition(self):
        with self.assertRaises(ContractError): strict_loads('{"a":1,"a":2}')
        with self.assertRaises(ContractError): strict_loads('{"a":NaN}')
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); s.create_run(manifest()); s.add_tasks("run-1",[manifest().runtime_task("task-a")])
            with self.assertRaises(Exception): s.transition_task("task-a",0,"RUNNING","main","illegal")
            s.close()

    def test_expired_lease_requires_stop_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); s.create_run(manifest()); s.add_tasks("run-1",[manifest().runtime_task("task-a")]); epoch=s.acquire_controller("controller"); l=LeaseStore(s); lease=l.acquire("run-1","task-a","ns-a","worker",epoch,1)
            s.db.execute("UPDATE leases SET expires_at=0 WHERE lease_id=?",(lease["lease_id"],)); self.assertEqual(l.expire(),1)
            with self.assertRaises(LeaseError): l.acquire("run-1","task-a","ns-a","worker",epoch)
            expired=s.db.execute("SELECT revision FROM leases WHERE lease_id=?",(lease["lease_id"],)).fetchone(); l.confirm_stop(lease["lease_id"],"process-terminated","worker",epoch,lease["fencing_token"],expired["revision"]); self.assertEqual(l.acquire("run-1","task-a","ns-a","worker",epoch)["status"],"ACTIVE"); s.close()

    def test_concurrent_task_cas_has_single_winner(self):
        import threading
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"s.sqlite"; s=StateStore(db); s.create_run(manifest()); s.add_tasks("run-1",[manifest().runtime_task("task-a")]); epoch=s.acquire_controller("controller"); lease=LeaseStore(s).acquire("run-1","task-a","ns-a","worker",epoch); s.close()
            barrier=threading.Barrier(2); results=[]
            def worker():
                local=StateStore(db)
                try:
                    barrier.wait(); results.append(local.transition_task("task-a",1,"RUNNING","worker","cas",{},None,lease["lease_id"],"none",epoch,lease["fencing_token"],manifest().manifest_hash()))
                except Exception as exc: results.append(type(exc).__name__)
                finally: local.close()
            threads=[threading.Thread(target=worker) for _ in range(2)]
            [t.start() for t in threads]; [t.join() for t in threads]
            self.assertEqual(sum(isinstance(x,dict) for x in results),1); self.assertEqual(sum(x=="StaleRevision" for x in results),1)

    def test_multi_namespace_acquisition_is_atomic(self):
        with tempfile.TemporaryDirectory() as td:
            from dataclasses import replace
            m=replace(manifest(),task_templates=(replace(manifest().task_templates[0],namespace=("ns-1","ns-2")),))
            s=StateStore(Path(td)/"s.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")]); epoch=s.acquire_controller("controller"); leases=LeaseStore(s).acquire_many("run-1","task-a",["ns-1","ns-2"],"worker",epoch); self.assertEqual({x["namespace"] for x in leases},{"ns-1","ns-2"}); self.assertEqual(s.get_task("task-a")["state"],"LEASED"); s.close()

    def test_profile_capability_discovery_is_read_only(self):
        from capability_registry import CapabilityRegistry
        root=Path(__file__).resolve().parents[1]/"profiles"; registry=CapabilityRegistry.from_profiles(root)
        item=registry.get("madv2_execute_i1_luna_high"); self.assertIsNotNone(item); self.assertEqual(item.model,"gpt-6-luna")
        self.assertEqual(registry.require(item.profile_id,item.model,item.effort,item.sandbox_mode).profile_id,item.profile_id)

    def test_task_spec_freeze_keeps_manifest_binding(self):
        from task_spec import build_task_spec, freeze_task_spec
        spec=freeze_task_spec(build_task_spec(manifest(),"task-a")); self.assertEqual(spec["manifest_hash"],manifest().manifest_hash())
        with self.assertRaises(ContractError): freeze_task_spec({"task_id":"x"})

    def test_controller_end_to_end_isolated_run(self):
        from orchestrate import handle
        from dataclasses import replace
        m=replace(manifest(),task_templates=(manifest().task_templates[0],))
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite")
            raw=m.payload_without_hash(); init=handle(s,"init",{"payload":{"manifest":raw},"actor_id":"main","idempotency_key":"init"})
            self.assertTrue(init["ok"])
            EvidenceIndex(s).record(EvidenceRecord("ev-1","run-1","TEST_RECEIPT","unittest",m.manifest_hash(),None,"result","a"*64,"unit",0,"2026-09-27T00:00:00Z","local deterministic probe","REDACTED","task-a",{"acceptance":"unit"}))
            EvidenceIndex(s).record(EvidenceRecord("ev-route","run-1","ROUTE_PROVENANCE","codex-runtime",m.manifest_hash(),None,None,None,"route probe",0,"2026-09-27T00:00:00Z","local isolated provenance","REDACTED","task-a",{"observed_model":"gpt-6-luna","observed_effort":"high"}))
            dispatched=handle(s,"dispatch-next",{"payload":{"run_id":"run-1"},"actor_id":"main"})
            item=dispatched["data"]["items"][0]; task=s.get_task("task-a"); epoch=dispatched["data"]["controller_epoch"]; fence=item["lease"]["fencing_token"]
            started=handle(s,"bind-start",{"payload":{"task_id":"task-a","lease_id":item["lease"]["lease_id"],"controller_epoch":epoch,"fencing_token":fence},"expected_revision":task["revision"],"actor_id":"main"})
            packet=self.packet("EXPLICIT_ROUTE_VERIFIED"); packet=HandoffPacket(**{**packet.__dict__,"manifest_hash":m.manifest_hash(),"state_revision":started["entity_revision"],"lease_id":item["lease"]["lease_id"],"hook_status":"HOOK_ENFORCED"})
            handoff=handle(s,"handoff",{"payload":{"task_id":"task-a","packet":packet.as_dict(),"lease_id":item["lease"]["lease_id"],"controller_epoch":epoch,"fencing_token":fence},"expected_revision":started["entity_revision"],"actor_id":"main"})
            receipt=AuditReceipt("audit-1","audit",m.manifest_hash(),"task-a","result","d"*64,"PASS","PASS","PASS","EXPLICIT_ROUTE_VERIFIED",(),(),"PASS",{"hook_status":"HOOK_ENFORCED","source":"codex-runtime","observed_model":"gpt-6-luna","observed_effort":"high","evidence_refs":["ev-route"]}, "now","main")
            self.assertTrue(handoff["ok"]); accepted=handle(s,"attach-receipt",{"payload":{"task_id":"task-a","receipt":receipt.as_dict(),"controller_epoch":epoch,"fencing_token":fence},"expected_revision":handoff["entity_revision"],"actor_id":"audit"})
            self.assertTrue(accepted["ok"]); ready=handle(s,"integrate-check",{"payload":{"run_id":"run-1"},"actor_id":"main"}); self.assertTrue(ready["ok"]); s.close()

    def test_scope_and_read_only_contracts(self):
        with self.assertRaises(ContractError):
            TaskTemplate("bad","test","INTEGRATION","D0","I0","A0","m","low","read-only",write_set=("src/x",))
        with self.assertRaises(ContractError):
            ScopeManifest(**{**manifest().__dict__,"task_templates":(TaskTemplate("bad","execute","CONTRACT_FROZEN","D0","I1","A0","m","high","workspace-write",write_set=("outside/x",)),)})

    def test_notification_state_is_idempotent_and_replayable(self):
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); n=NotificationState(s); first=n.record("run-1","task-a","blocked",{"summary":"held"},"notice-1"); again=n.record("run-1","task-a","blocked",{"summary":"held"},"notice-1"); self.assertEqual(first["intent_id"],again["intent_id"])
            with self.assertRaises(IdempotencyConflict): n.record("run-1","task-a","blocked",{"summary":"changed"},"notice-1")
            n.mark_failed(first["intent_id"],"network"); self.assertEqual(len(n.replayable()),1); n.mark_sent(first["intent_id"]); self.assertEqual(n.replayable(),[]); s.close()

    def test_worker_adapter_is_bounded_and_redacts_output(self):
        import sys as runtime_sys
        ticket=WorkerLaunchTicket("ticket-1","run-1","task-a","attempt-1","h"*64,1,1,"lease-1",(runtime_sys.executable,"-c","print('api_key=secret')"),None,10)
        result=WorkerAdapter().run(ticket); self.assertEqual(result.exit_code,0); self.assertIn("<redacted>",result.stdout)
        slow=WorkerLaunchTicket("ticket-2","run-1","task-a","attempt-2","h"*64,1,1,"lease-1",(runtime_sys.executable,"-c","import time; time.sleep(2)"),None,1)
        self.assertTrue(WorkerAdapter().run(slow).timed_out)
        with self.assertRaises(ContractError): WorkerAdapter().run(WorkerLaunchTicket("ticket-3","run-1","task-a","attempt-3","h"*64,1,1,"lease-1",(runtime_sys.executable,"-c","print(1)"),None,10,"external"))

    def test_stale_epoch_fence_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); s.create_run(manifest()); s.add_tasks("run-1",[manifest().runtime_task("task-a")]); epoch=s.acquire_controller("controller"); lease=LeaseStore(s).acquire("run-1","task-a","ns-a","worker",epoch)
            with self.assertRaises(LeaseError): s.transition_task("task-a",1,"RUNNING","worker","start",{},None,lease["lease_id"],"none",epoch+1,lease["fencing_token"],manifest().manifest_hash())
            s.acquire_controller("new-controller")
            with self.assertRaises(LeaseError): LeaseStore(s).validate(lease["lease_id"],"task-a","worker",epoch,lease["fencing_token"])
            s.close()

    def test_outbox_claim_completion_and_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); s.create_run(manifest()); s.add_tasks("run-1",[manifest().runtime_task("task-a")])
            s.transition_task("task-a",0,"LEASED","main","external_notice",{"x":1},None,None,"external")
            claimed=s.claim_outbox("notify",1,60); self.assertEqual(len(claimed),1)
            with self.assertRaises(Exception): s.complete_outbox(claimed[0]["outbox_id"],"other","SENT")
            s.db.execute("UPDATE outbox SET claimed_until=0 WHERE outbox_id=?",(claimed[0]["outbox_id"],))
            self.assertEqual(s.recover_outbox(),1); reclaimed=s.claim_outbox("notify2",1,60); self.assertEqual(len(reclaimed),1)
            done=s.complete_outbox(reclaimed[0]["outbox_id"],"notify2","SENT",{"provider":"mock"}); self.assertEqual(done["status"],"SENT"); self.assertEqual(s.pending_outbox(),[]); s.close()

    def test_evidence_index_binds_manifest_and_redacts(self):
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); s.create_run(manifest()); s.add_tasks("run-1",[manifest().runtime_task("task-a")])
            record=EvidenceRecord("ev-1","run-1","TEST_RECEIPT","unittest",manifest().manifest_hash(),None,"r1","a"*64,"python -m unittest",0,"2026-09-27T00:00:00Z","local deterministic probe","REDACTED","task-a",{"case":"ok"})
            self.assertEqual(EvidenceIndex(s).record(record)["evidence_id"],"ev-1")
            with self.assertRaises(ContractError):
                EvidenceRecord("ev-2","run-1","TEST_RECEIPT","unittest",manifest().manifest_hash(),None,None,None,"password=secret",0,"now","limited","REDACTED")
            s.close()

    def test_retry_requires_new_evidence_and_budget(self):
        from orchestrate import handle
        from dataclasses import replace
        m=replace(manifest(),task_templates=(replace(manifest().task_templates[0],max_retries=2),))
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"s.sqlite"); handle(s,"init",{"payload":{"manifest":m.payload_without_hash()},"actor_id":"main","idempotency_key":"init"})
            s.transition_task("task-a",0,"LEASED","main","failed",{},None,None,"none")
            s.transition_task("task-a",1,"FAILED","main","failed",{},None,None,"none")
            first=handle(s,"retry",{"payload":{"task_id":"task-a","reason":"worker crash"},"actor_id":"main"})
            self.assertTrue(first["ok"]); self.assertEqual(first["data"]["state"],"RETRYABLE")
            second=handle(s,"retry",{"payload":{"task_id":"task-a","reason":"still failing"},"actor_id":"main"})
            self.assertFalse(second["ok"]); self.assertEqual(second["data"]["reason"],"RETRY_WITHOUT_NEW_EVIDENCE")
            epoch=s.acquire_controller("main"); lease=LeaseStore(s).acquire("run-1","task-a","ns-a","main",epoch); self.assertEqual(lease["status"],"ACTIVE")
            s.transition_task("task-a",4,"FAILED","main","failed_again",{},None,lease["lease_id"],"none",epoch,lease["fencing_token"],m.manifest_hash())
            third=handle(s,"retry",{"payload":{"task_id":"task-a","reason":"new probe","evidence_refs":["ev-2"],"controller_epoch":epoch,"fencing_token":lease["fencing_token"]},"actor_id":"main","controller_epoch":epoch})
            self.assertTrue(third["ok"]); s.close()


if __name__=="__main__": unittest.main()
