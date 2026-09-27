from __future__ import annotations
import tempfile
import unittest
import json
from dataclasses import replace
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from parallel_manifest import ContractError, ScopeManifest, TaskTemplate
from state_store import StateStore, StateError, LeaseError, IdempotencyConflict
from lease_store import LeaseStore, EXPIRED, RELEASED, ACTIVE
from audit_receipt import AuditReceipt
from handoff_contract import HandoffPacket
from worker_adapter import WorkerAdapter
from evidence_index import EvidenceIndex, EvidenceRecord
from task_scheduler import Scheduler
from test_parallel_v21 import manifest
class V21DefectRegressionTests(unittest.TestCase):
    def two_namespace_manifest(self):
        base=manifest()
        task=replace(base.task_templates[0],namespace=("ns-a","ns-b"))
        return replace(base,task_templates=(task,))

    def test_expired_bundle_blocks_reacquire_until_all_stop_evidence(self):
        m=self.two_namespace_manifest()
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")])
            l=LeaseStore(s); epoch=s.acquire_controller("worker")
            leases=l.acquire_many("run-1","task-a",["ns-a","ns-b"],"worker",epoch,30)
            s.db.execute("UPDATE leases SET expires_at=0 WHERE task_id='task-a'")
            with self.assertRaises(LeaseError): l.acquire_many("run-1","task-a",["ns-a","ns-b"],"worker",epoch)
            self.assertEqual(s.get_task("task-a")["state"],"UNKNOWN")
            self.assertEqual(s.db.execute("SELECT COUNT(*) AS n FROM leases WHERE task_id='task-a' AND status=?",(EXPIRED,)).fetchone()["n"],2)
            with self.assertRaises(LeaseError): l.confirm_stop(leases[0]["lease_id"],"one-stop","worker",epoch,leases[0]["fencing_token"],leases[0]["revision"])
            current_revisions={x["lease_id"]:s.db.execute("SELECT revision FROM leases WHERE lease_id=?",(x["lease_id"],)).fetchone()["revision"] for x in leases}; l.confirm_stop_bundle("task-a",{x["lease_id"]:"stopped-"+x["namespace"] for x in leases},"worker",epoch,{x["lease_id"]:x["fencing_token"] for x in leases},current_revisions)
            self.assertEqual(s.get_task("task-a")["state"],"PLANNED")
            fresh=l.acquire_many("run-1","task-a",["ns-a","ns-b"],"worker",epoch)
            self.assertEqual(len(fresh),2); s.close()
    def test_frozen_manifest_rejects_rogue_hash_and_write_scope(self):
        m=manifest()
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); s.create_run(m)
            rogue=m.runtime_task("task-a"); rogue["task_id"]="rogue"
            with self.assertRaises(ContractError): s.add_tasks("run-1",[rogue])
            wrong=m.runtime_task("task-a"); wrong["manifest_hash"]="0"*64
            with self.assertRaises(ContractError): s.add_tasks("run-1",[wrong])
            escaped=m.runtime_task("task-a"); escaped["write_set"]=["secrets/x"]
            with self.assertRaises(ContractError): s.add_tasks("run-1",[escaped])
            self.assertEqual(s.list_tasks("run-1"),[]); s.close()

    def test_handoff_identity_and_failed_receipt_fail_closed(self):
        p=HandoffPacket("task-a","run-1","attempt-1","h"*64,1,"lease","base","r","SUCCEEDED",("src/a.py",),"d"*64,("a"*64,),({"command":"unit","exit_code":0},),("ev",),None,{"route_status":"ROUTE_UNVERIFIED"},"HOOK_UNVERIFIED","WARN",(),(),("audit",),{},("src/a.py",))
        with self.assertRaises(ContractError): HandoffPacket(**{**p.__dict__,"test_receipts":({"command":"unit","exit_code":1},)})
        with self.assertRaises(ContractError): HandoffPacket(**{**p.__dict__,"test_receipts":()})
    def test_audit_pass_requires_dimensions_route_and_hook(self):
        args=("a1","audit","h"*64,"task-a","r","d"*64,"PASS","PASS","PASS","ROUTE_UNVERIFIED",(),(),"PASS",{"hook_status":"HOOK_UNVERIFIED"},"now","writer")
        with self.assertRaises(ContractError): AuditReceipt(*args)
        args=("a2","audit","h"*64,"task-a","r","d"*64,"FAIL","PASS","PASS","EXPLICIT_ROUTE_VERIFIED",(),(),"PASS",{"hook_status":"HOOK_ENFORCED"},"now","writer")
        with self.assertRaises(ContractError): AuditReceipt(*args)

    def test_bottom_fence_requires_epoch_and_token(self):
        m=manifest()
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")])
            epoch=s.acquire_controller("worker"); lease=LeaseStore(s).acquire("run-1","task-a","ns-a","worker",epoch)
            with self.assertRaises(LeaseError): s.transition_task("task-a",1,"RUNNING","worker","start",{},None,lease["lease_id"])
            with self.assertRaises(LeaseError): s.transition_task("task-a",1,"RUNNING","worker","start",{},None,lease["lease_id"],"none",epoch,lease["fencing_token"]+1)
            s.close()
    def test_retry_failure_does_not_consume_attempt(self):
        m=manifest()
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")])
            epoch=s.acquire_controller("worker"); lease=LeaseStore(s).acquire("run-1","task-a","ns-a","worker",epoch,1)
            s.db.execute("UPDATE leases SET expires_at=0 WHERE lease_id=?",(lease["lease_id"],)); LeaseStore(s).expire()
            with self.assertRaises(LeaseError): s.retry_task("task-a","worker","recover",["ev"],"attempt-2")
            self.assertEqual(s.db.execute("SELECT COUNT(*) AS n FROM attempts WHERE task_id='task-a'").fetchone()["n"],0)
            s.close()
    def test_release_bundle_is_atomic_and_evented(self):
        m=self.two_namespace_manifest()
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")])
            l=LeaseStore(s); epoch=s.acquire_controller("worker"); leases=l.acquire_many("run-1","task-a",["ns-a","ns-b"],"worker",epoch)
            l.release_bundle("task-a","worker",epoch,{x["lease_id"]:x["fencing_token"] for x in leases},{x["lease_id"]:"done" for x in leases},{x["lease_id"]:x["revision"] for x in leases})
            self.assertEqual(s.db.execute("SELECT COUNT(*) AS n FROM leases WHERE task_id='task-a' AND status=?",(ACTIVE,)).fetchone()["n"],0)
            self.assertEqual(s.get_task("task-a")["state"],"PLANNED")
            self.assertTrue(s.db.execute("SELECT 1 FROM events WHERE task_id='task-a' AND reason='lease_bundle_released'").fetchone()); s.close()
    def test_multi_namespace_transition_requires_all_fences(self):
        m=self.two_namespace_manifest()
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")])
            l=LeaseStore(s); epoch=s.acquire_controller("worker"); leases=l.acquire_many("run-1","task-a",["ns-a","ns-b"],"worker",epoch)
            with self.assertRaises(LeaseError):
                s.transition_task("task-a",1,"RUNNING","worker","start",{},None,leases[0]["lease_id"],"none",epoch,leases[0]["fencing_token"],m.manifest_hash())
            fences={item["namespace"]:item["fencing_token"] for item in leases}
            result=s.transition_task("task-a",1,"RUNNING","worker","start",{},None,leases[0]["lease_id"],"none",epoch,leases[0]["fencing_token"],m.manifest_hash(),fences)
            self.assertEqual(result["state"],"RUNNING"); s.close()

    def test_init_replay_and_epoch_reuse_takeover(self):
        from orchestrate import handle
        m=replace(manifest(),task_templates=(manifest().task_templates[0],))
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); raw=m.payload_without_hash()
            first=handle(s,"init",{"payload":{"manifest":raw},"actor_id":"main","idempotency_key":"same"})
            second=handle(s,"init",{"payload":{"manifest":raw},"actor_id":"main","idempotency_key":"same"})
            self.assertEqual(first["data"]["revision"],second["data"]["revision"])
            one=handle(s,"dispatch-next",{"payload":{"run_id":"run-1"},"actor_id":"main"})
            two=handle(s,"dispatch-next",{"payload":{"run_id":"run-1"},"actor_id":"main"})
            self.assertEqual(one["data"]["controller_epoch"],two["data"]["controller_epoch"])
            three=handle(s,"dispatch-next",{"payload":{"run_id":"run-1","takeover":True},"actor_id":"main"})
            self.assertGreater(three["data"]["controller_epoch"],two["data"]["controller_epoch"]); s.close()
    def test_manifest_cycle_is_rejected_and_worker_boundary_is_explicit(self):
        base=manifest(); a=replace(base.task_templates[0],dependency_ids=("task-b",))
        b=replace(base.task_templates[1],dependency_ids=("task-a",))
        with self.assertRaises(ContractError): replace(base,task_templates=(a,b))
        self.assertIn("not an untrusted sandbox",WorkerAdapter.__doc__)

    def test_scheduler_blocks_overlapping_write_sets_across_namespaces(self):
        from orchestrate import handle
        base=manifest(); a=base.task_templates[0]; b=replace(a,task_id="task-b",namespace=("ns-b",),dependency_ids=())
        m=replace(base,task_templates=(a,b),concurrency_limit=2)
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite")
            handle(s,"init",{"payload":{"manifest":m.payload_without_hash()},"actor_id":"main","idempotency_key":"init"})
            epoch=s.current_controller_epoch(); items=Scheduler(s,LeaseStore(s)).dispatch_next("run-1","main",epoch)
            self.assertEqual([item["task_id"] for item in items],["task-a"])
            s.close()

    def test_intake_and_superseded_runs_cannot_dispatch(self):
        from orchestrate import handle
        old_task=replace(manifest().task_templates[0],task_id="old-task")
        m1=replace(manifest(),task_templates=(old_task,))
        new_task=replace(manifest().task_templates[0],task_id="new-task")
        m2=replace(manifest(),run_id="run-2",supersedes="run-1",task_templates=(new_task,))
        intake_task=replace(manifest().task_templates[0],task_id="intake-task")
        m3=replace(manifest(),run_id="run-3",task_templates=(intake_task,))
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite")
            handle(s,"init",{"payload":{"manifest":m1.payload_without_hash()},"actor_id":"main","idempotency_key":"init-1"})
            handle(s,"init",{"payload":{"manifest":m2.payload_without_hash()},"actor_id":"main","idempotency_key":"init-2"})
            self.assertEqual(s.get_run("run-1")["state"],"SUPERSEDED")
            with self.assertRaises(StateError):
                handle(s,"dispatch-next",{"payload":{"run_id":"run-1"},"actor_id":"main"})
            self.assertFalse(handle(s,"integrate-check",{"payload":{"run_id":"run-1"},"actor_id":"main"})["ok"])
            s.create_run(m3); s.add_tasks("run-3",[m3.runtime_task("intake-task")]); epoch=s.acquire_controller("main")
            with self.assertRaises(StateError):
                Scheduler(s,LeaseStore(s)).dispatch_next("run-3","main",epoch)
            s.close()

    def test_audit_receipt_binds_route_evidence_and_acceptance_command(self):
        m=manifest()
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")])
            packet={"result_revision":"r","diff_hash":"d"*64,"evidence_refs":["ev-test"],"test_receipts":[{"command":"unit","exit_code":0}]}
            s.db.execute("UPDATE tasks SET state='AUDIT_PENDING',owner='writer',result_json=? WHERE task_id='task-a'",(json.dumps({"packet":packet}),))
            def receipt(audit_id, model="gpt-6-luna", effort="high", refs=("ev-test",)):
                return AuditReceipt(audit_id,"audit",m.manifest_hash(),"task-a","r","d"*64,"PASS","PASS","PASS","EXPLICIT_ROUTE_VERIFIED",(),(),"PASS",{"hook_status":"HOOK_ENFORCED","source":"codex-runtime","observed_model":model,"observed_effort":effort,"evidence_refs":list(refs)},"now","writer").as_dict()
            with self.assertRaises(ContractError):
                s.store_audit_receipt(receipt("audit-mismatch",model="other-model"))
            with self.assertRaises(ContractError):
                s.store_audit_receipt(receipt("audit-missing"))
            EvidenceIndex(s).record(EvidenceRecord("ev-test","run-1","TEST_RECEIPT","unittest",m.manifest_hash(),None,"r","a"*64,"unit",0,"now","local","REDACTED","task-a",{}))
            EvidenceIndex(s).record(EvidenceRecord("ev-route","run-1","ROUTE_PROVENANCE","codex-runtime",m.manifest_hash(),None,"r",None,"route probe",0,"now","local","REDACTED","task-a",{"observed_model":"gpt-6-luna","observed_effort":"high"}))
            packet["test_receipts"]=[{"command":"uni","exit_code":0}]
            s.db.execute("UPDATE tasks SET result_json=? WHERE task_id='task-a'",(json.dumps({"packet":packet}),))
            with self.assertRaisesRegex(ContractError,"handoff test command lacks persisted evidence"):
                s.store_audit_receipt(receipt("audit-wrong-command",refs=("ev-route",)))
            s.close()

    def test_full_command_evidence_rejects_packet_substring_end_to_end(self):
        from orchestrate import handle
        full_command="python -m unittest discover -s tests -p test_*.py"
        task=replace(manifest().task_templates[0],acceptance_checks=(full_command,))
        m=replace(manifest(),task_templates=(task,))
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite")
            try:
                handle(s,"init",{"payload":{"manifest":m.payload_without_hash()},"actor_id":"main","idempotency_key":"init"})
                EvidenceIndex(s).record(EvidenceRecord("ev-test","run-1","TEST_RECEIPT","unittest",m.manifest_hash(),None,"result","a"*64,full_command,0,"now","isolated test","REDACTED","task-a",{}))
                EvidenceIndex(s).record(EvidenceRecord("ev-route","run-1","ROUTE_PROVENANCE","codex-runtime",m.manifest_hash(),None,"result",None,"route probe",0,"now","synthetic provenance","REDACTED","task-a",{"observed_model":"gpt-6-luna","observed_effort":"high"}))
                dispatched=handle(s,"dispatch-next",{"payload":{"run_id":"run-1"},"actor_id":"main"})
                lease=dispatched["data"]["items"][0]["lease"]; epoch=dispatched["data"]["controller_epoch"]
                started=handle(s,"bind-start",{"payload":{"task_id":"task-a","lease_id":lease["lease_id"],"controller_epoch":epoch,"fencing_token":lease["fencing_token"]},"expected_revision":s.get_task("task-a")["revision"],"actor_id":"main"})
                packet=HandoffPacket("task-a","run-1","attempt-1",m.manifest_hash(),started["entity_revision"],lease["lease_id"],"base","result","SUCCEEDED",("src/a.py",),"d"*64,("a"*64,),({"command":"unit","exit_code":0},),("ev-test",),None,{"route_status":"EXPLICIT_ROUTE_VERIFIED"},"HOOK_ENFORCED","WARN",(),(),("audit",),{"tokens":1},("src/a.py",))
                handed=handle(s,"handoff",{"payload":{"task_id":"task-a","packet":packet.as_dict(),"lease_id":lease["lease_id"],"controller_epoch":epoch,"fencing_token":lease["fencing_token"]},"expected_revision":started["entity_revision"],"actor_id":"main"})
                self.assertTrue(handed["ok"])
                receipt=AuditReceipt("audit-full-command","audit",m.manifest_hash(),"task-a","result","d"*64,"PASS","PASS","PASS","EXPLICIT_ROUTE_VERIFIED",(),(),"PASS",{"hook_status":"HOOK_ENFORCED","source":"codex-runtime","observed_model":"gpt-6-luna","observed_effort":"high","evidence_refs":["ev-route"]},"now","main")
                with self.assertRaisesRegex(ContractError,"handoff test command lacks persisted evidence"):
                    handle(s,"attach-receipt",{"payload":{"task_id":"task-a","receipt":receipt.as_dict(),"controller_epoch":epoch,"fencing_token":lease["fencing_token"]},"expected_revision":handed["entity_revision"],"actor_id":"audit"})
                self.assertEqual(s.get_task("task-a")["state"],"AUDIT_PENDING")
                self.assertEqual(s.list_receipts("task-a"),[])
                self.assertFalse(handle(s,"integrate-check",{"payload":{"run_id":"run-1"},"actor_id":"main"})["ok"])
                self.assertNotEqual(s.get_run("run-1")["state"],"READY_TO_MERGE")
            finally: s.close()

    def test_exit_code_types_fail_closed_at_evidence_and_handoff_boundaries(self):
        m=manifest()
        for bad in (False,0.0,"0"):
            with self.subTest(exit_code=repr(bad)):
                with self.assertRaisesRegex(ContractError,"exit_code"):
                    EvidenceRecord("ev-bad","run-1","TEST_RECEIPT","unittest",m.manifest_hash(),None,"r1",None,"unit",bad,"now","local","REDACTED","task-a",{})
                with tempfile.TemporaryDirectory() as td:
                    s=StateStore(Path(td)/"state.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")])
                    raw={"evidence_id":"ev-raw","run_id":"run-1","task_id":"task-a","kind":"TEST_RECEIPT","source":"unittest","manifest_hash":m.manifest_hash(),"base_revision":None,"result_revision":"r1","artifact_hash":None,"command_or_ui_step":"unit","exit_code":bad,"observed_at":"now","limitations":"local","redaction_status":"REDACTED","payload":{}}
                    with self.assertRaisesRegex(ContractError,"exit_code"):
                        s.record_evidence(raw)
                    self.assertEqual(s.db.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"],0)
                    s.close()
                packet_data={"task_id":"task-a","run_id":"run-1","attempt_id":"attempt-1","manifest_hash":"h"*64,"state_revision":1,"lease_id":"lease","base_revision":"base","result_revision":"result","status":"SUCCEEDED","changed_paths":("src/a.py",),"diff_hash":"d"*64,"artifact_hashes":("a"*64,),"test_receipts":({"command":"unit","exit_code":bad},),"evidence_refs":("ev",),"audit_receipt":None,"route_provenance":{"route_status":"EXPLICIT_ROUTE_VERIFIED"},"hook_status":"HOOK_ENFORCED","guard_decision":"WARN","assumptions":(),"open_questions":(),"next_allowed_actions":("audit",),"budget_usage":{},"write_set":("src/a.py",)}
                with self.assertRaisesRegex(ContractError,"integer zero-exit"):
                    HandoffPacket(**packet_data)

    def test_event_ledger_metadata_is_controller_owned(self):
        m=manifest()
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); s.create_run(m); s.add_tasks("run-1",[m.runtime_task("task-a")])
            with self.assertRaises(ContractError):
                s.transition_task("task-a",0,"LEASED","main","ledger-spoof",{"_ledger":{"entity_revision":999}})
            self.assertEqual(s.db.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"],0); s.close()

    def test_retry_idempotency_replay_does_not_recheck_budget(self):
        from orchestrate import handle
        m=replace(manifest(),task_templates=(replace(manifest().task_templates[0],max_retries=2),))
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); handle(s,"init",{"payload":{"manifest":m.payload_without_hash()},"actor_id":"main","idempotency_key":"init"})
            s.transition_task("task-a",0,"LEASED","main","fail",{},None,None,"none"); s.transition_task("task-a",1,"FAILED","main","fail",{},None,None,"none")
            request={"payload":{"task_id":"task-a","reason":"worker crash"},"actor_id":"main","idempotency_key":"retry-same"}
            first=handle(s,"retry",request); second=handle(s,"retry",request)
            self.assertTrue(first["ok"]); self.assertEqual(first["data"],second["data"])
            with self.assertRaises(IdempotencyConflict):
                handle(s,"retry",{"payload":{"task_id":"task-a","reason":"different"},"actor_id":"main","idempotency_key":"retry-same"})
            self.assertEqual(s.db.execute("SELECT COUNT(*) AS n FROM attempts WHERE task_id='task-a'").fetchone()["n"],1); s.close()

    def test_handoff_idempotency_replay_is_single_chain(self):
        from orchestrate import handle
        m=replace(manifest(),task_templates=(manifest().task_templates[0],))
        with tempfile.TemporaryDirectory() as td:
            s=StateStore(Path(td)/"state.sqlite"); handle(s,"init",{"payload":{"manifest":m.payload_without_hash()},"actor_id":"main","idempotency_key":"init"})
            dispatched=handle(s,"dispatch-next",{"payload":{"run_id":"run-1"},"actor_id":"main"}); item=dispatched["data"]["items"][0]; epoch=dispatched["data"]["controller_epoch"]; task=s.get_task("task-a")
            started=handle(s,"bind-start",{"payload":{"task_id":"task-a","lease_id":item["lease"]["lease_id"],"controller_epoch":epoch,"fencing_token":item["lease"]["fencing_token"]},"expected_revision":task["revision"],"actor_id":"main"})
            packet=HandoffPacket("task-a","run-1","attempt-1","h"*64,1,"lease","base","result","SUCCEEDED",("src/a.py",),"d"*64,("a"*64,),({"command":"unit","exit_code":0},),("ev-1",),None,{"route_status":"EXPLICIT_ROUTE_VERIFIED"},"HOOK_UNVERIFIED","WARN",(),(),("audit",),{"tokens":1},("src/a.py",))
            packet=HandoffPacket(**{**packet.__dict__,"manifest_hash":m.manifest_hash(),"state_revision":started["entity_revision"],"lease_id":item["lease"]["lease_id"],"hook_status":"HOOK_ENFORCED"})
            request={"payload":{"task_id":"task-a","packet":packet.as_dict(),"lease_id":item["lease"]["lease_id"],"controller_epoch":epoch,"fencing_token":item["lease"]["fencing_token"]},"expected_revision":started["entity_revision"],"actor_id":"main","idempotency_key":"handoff-same"}
            first=handle(s,"handoff",request); second=handle(s,"handoff",request)
            self.assertTrue(first["ok"]); self.assertEqual(first["data"],second["data"])
            self.assertEqual(s.db.execute("SELECT COUNT(*) AS n FROM events WHERE task_id='task-a'").fetchone()["n"],5); s.close()

if __name__=="__main__":
    unittest.main()
