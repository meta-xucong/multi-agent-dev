from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evidence_index import EvidenceRecord
from handoff_contract import HandoffPacket
from parallel_manifest import ContractError
from parallel_manifest import ScopeManifest, TaskTemplate
from state_store import StateStore
from semantic_guard import inspect_handoff
from source_fidelity import ReferenceSpec, SourceMapping, diff_manifest_hash, file_manifest, inspect, mapping_manifest_hash
from orchestrate import handle


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SourceFidelityTests(unittest.TestCase):
    def source_task(self, task_id="task-1", *, role="execute", deps=(), **overrides):
        values = {
            "task_id": task_id, "role": role, "stage": "CONTRACT_FROZEN", "D": "D0", "I": "I1", "A": "A1",
            "requested_model": "gpt-6-luna", "requested_effort": "high", "sandbox_mode": "workspace-write",
            "write_set": ("src/a.py",), "namespace": ("src",), "dependency_ids": tuple(deps),
            "source_fidelity_required": True, "source_mapping_revision": "sfm-1", "source_reference_commit": "abc",
            "source_reference_manifest_sha256": "b" * 64, "source_target_manifest_sha256": "a" * 64,
            "source_target_baseline_manifest_sha256": "c" * 64, "source_mapping_manifest_sha256": "e" * 64,
        }
        values.update(overrides)
        return TaskTemplate(**values)

    def complete_receipt_payload(self, manifest_hash, *, producer_thread_id="sf-child"):
        return {
            "receipt_id": "sfr-valid", "run_id": "run-1", "task_id": "task-1",
            "target_manifest_hash": "a" * 64, "target_result_revision": "r1", "target_diff_hash": "d" * 64,
            "scope_manifest_hash": manifest_hash, "target_base_manifest_sha256": "c" * 64,
            "mapping_manifest_sha256": "e" * 64,
            "reference": {"repository": "https://github.com/example/repo", "commit": "abc", "manifest_sha256": "b" * 64},
            "mapping_revision": "sfm-1", "producer_role": "source-fidelity-agent", "producer_thread_id": producer_thread_id,
            "status": "PASS", "checked_files": ["src/a.py"], "checked_symbols": ["render"],
            "direct_reuse": ["mapping-1"], "thin_adaptations": [], "platform_shell": [], "authorized_new": [],
            "deviations": [], "source_gaps": [], "tests": ["python -m unittest test_render -q"],
            "evidence_refs": ["ev-source-test"], "next_action": "integrate",
        }

    def test_source_sensitive_manifest_keeps_sidecar_out_of_controller_dag(self):
        base = dict(
            run_id="run-1", goal="source migration", non_goals=(), hard_constraints=(), rule_sources=(),
            base_revision="base", base_tree_hash="d" * 64, allowed_paths=("src",), forbidden_paths=(),
            read_paths=("src",), D="D0", I="I1", A="A1", stage="CONTRACT_FROZEN", owners={"main":"main"},
        )
        manifest = ScopeManifest(**base, task_templates=(self.source_task(),))
        self.assertEqual(len(manifest.task_templates), 1)
        self.assertTrue(manifest.task_templates[0].source_fidelity_required)
        self.assertEqual(manifest.task_templates[0].dependency_ids, ())

    def test_source_fidelity_sidecar_is_not_a_controller_task_role(self):
        with self.assertRaises(ContractError):
            TaskTemplate(
                "source-write", "source_fidelity", "VERSION_FROZEN", "D0", "I1", "A1",
                "gpt-6-luna", "xhigh", "read-only",
            )

    def test_source_sensitive_task_requires_complete_frozen_contract(self):
        with self.assertRaisesRegex(ContractError, "requires frozen reference, target and mapping manifests"):
            self.source_task(source_mapping_manifest_sha256=None)

    def make_roots(self, source: str, target: str, base: str | None = None):
        td = tempfile.TemporaryDirectory()
        source_root = Path(td.name) / "source"
        target_root = Path(td.name) / "target"
        source_root.mkdir(); target_root.mkdir()
        base_root = Path(td.name) / "base"
        base_root.mkdir()
        (source_root / "src.py").write_text(source, encoding="utf-8")
        (target_root / "dst.py").write_text(target, encoding="utf-8")
        (base_root / "dst.py").write_text(target if base is None else base, encoding="utf-8")
        return td, source_root, target_root, base_root

    def spec(self, source_root: Path, target_root: Path, base_root: Path, source_hash: str, mapping: SourceMapping, *, target_hash: str | None = None, diff_hash: str | None = None):
        _, base_manifest = file_manifest(base_root)
        if target_hash is None:
            _, target_hash = file_manifest(target_root)
        mapping_hash = mapping_manifest_hash((mapping,))
        return ReferenceSpec(
            reference_id="ref-1", repository="https://github.com/example/repo", commit="abc123",
            reference_root=str(source_root), target_root=str(target_root), source_manifest_sha256=source_hash,
            target_manifest_sha256=target_hash, target_base_root=str(base_root), target_base_manifest_sha256=base_manifest, scope_manifest_hash="a" * 64, mapping_manifest_sha256=mapping_hash, run_id="run-1", task_id="task-1", changed_paths=("dst.py",),
            mappings=(mapping,),
        )

    def test_direct_reuse_passes_only_with_bound_evidence(self):
        text = "def render(value):\n    if value:\n        return 'ok'\n    return 'no'\n"
        td, source_root, target_root, base_root = self.make_roots(text, text)
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("render",),
                                required_source_fragments=("return 'ok'",), required_target_fragments=("return 'ok'",),
                                regression_tests=("python -m unittest test_render -q",))
        diff_hash = diff_manifest_hash(base_root, target_root, ("dst.py",))
        receipt = inspect(self.spec(source_root, target_root, base_root, source_hash, mapping), "sfr-1", "r1", diff_hash, ("ev-sf",))
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.producer_role, "source-fidelity-agent")
        self.assertEqual(receipt.as_dict()["reference"]["commit"], "abc123")

    def test_unexpected_identifier_and_structure_are_blocked(self):
        source = "def render(value):\n    if value:\n        return 'ok'\n    return 'no'\n"
        target = "def render(value, extra):\n    if value:\n        return 'ok'\n    if extra:\n        return 'new'\n    return 'no'\n"
        td, source_root, target_root, base_root = self.make_roots(source, target, source)
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("render",))
        diff_hash = diff_manifest_hash(base_root, target_root, ("dst.py",))
        receipt = inspect(self.spec(source_root, target_root, base_root, source_hash, mapping), "sfr-2", "r1", diff_hash, ("ev-sf",))
        self.assertEqual(receipt.status, "BLOCK")
        self.assertTrue(any(item.startswith("UNAUTHORIZED_IDENTIFIER") for item in receipt.deviations))
        self.assertTrue(any(item.startswith("SOURCE_DRIFT_STRUCTURE") for item in receipt.deviations))

    def test_operator_semantic_drift_is_blocked(self):
        source = "def f(value):\n    return value + 1\n"
        target = "def f(value):\n    return value - 1\n"
        td, source_root, target_root, base_root = self.make_roots(source, target, source)
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-operator", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("f",), regression_tests=("unit-f",))
        diff_hash = diff_manifest_hash(base_root, target_root, ("dst.py",))
        receipt = inspect(self.spec(source_root, target_root, base_root, source_hash, mapping), "sfr-operator", "r1", diff_hash, ("ev-sf",))
        self.assertEqual(receipt.status, "BLOCK")
        self.assertTrue(any(item.startswith("SOURCE_DRIFT_OPERATOR") for item in receipt.deviations))

    def test_pass_receipt_cannot_be_minimal_or_unbound(self):
        with self.assertRaises(ContractError):
            from source_fidelity import SourceFidelityReceipt
            SourceFidelityReceipt("sfr-min", "run-1", "task-1", "a" * 64, "r1", "b" * 64,
                                  {"repository": "repo", "commit": "abc", "manifest_sha256": "c" * 64},
                                  "sfm-1", "PASS", scope_manifest_hash="d" * 64)

    def test_pass_receipt_requires_fixed_producer_role(self):
        text = "def f():\n    return 1\n"
        td, source_root, target_root, base_root = self.make_roots(text, text)
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("f",), regression_tests=("unit-f",))
        receipt = inspect(self.spec(source_root, target_root, base_root, source_hash, mapping), "sfr-role", "r1", diff_manifest_hash(base_root, target_root, ("dst.py",)), ("ev-sf",))
        with self.assertRaises(ContractError):
            from source_fidelity import SourceFidelityReceipt
            SourceFidelityReceipt(**{**receipt.as_dict(), "producer_role": "worker"})

    def test_controller_rejects_complete_source_receipt_without_child_dispatch_evidence(self):
        template = self.source_task()
        manifest = ScopeManifest("run-1", "goal", (), (), (), "base", "d" * 64, ("src",), (), ("src",), "D0", "I1", "A1", "CONTRACT_FROZEN", {"main": "main"}, (template,))
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.sqlite")
            store.create_run(manifest); store.add_tasks("run-1", [manifest.runtime_task("task-1")])
            store.record_evidence({"evidence_id": "ev-source-test", "run_id": "run-1", "task_id": "task-1", "kind": "TEST_RECEIPT", "source": "unittest", "manifest_hash": manifest.manifest_hash(), "base_revision": "base", "result_revision": "r1", "artifact_hash": "f" * 64, "command_or_ui_step": "python -m unittest test_render -q", "exit_code": 0, "observed_at": "now", "limitations": "local deterministic fixture", "redaction_status": "REDACTED", "payload": {}})
            store.record_evidence({"evidence_id": "ev-fake", "run_id": "run-1", "task_id": "task-1", "kind": "SOURCE_FIDELITY_RECEIPT", "source": "source-fidelity-agent", "manifest_hash": manifest.manifest_hash(), "base_revision": "base", "result_revision": "r1", "artifact_hash": "d" * 64, "command_or_ui_step": None, "exit_code": None, "observed_at": "now", "limitations": "synthetic complete receipt without runtime child binding", "redaction_status": "REDACTED", "payload": self.complete_receipt_payload(manifest.manifest_hash())})
            packet = {"source_fidelity_status": "PASS", "source_fidelity_evidence_refs": ["ev-fake"], "source_fidelity_dispatch_evidence_refs": [], "evidence_refs": ["ev-fake", "ev-source-test"], "source_fidelity_target_manifest_hash": "a" * 64, "result_revision": "r1", "diff_hash": "d" * 64}
            with self.assertRaisesRegex(ContractError, "runtime dispatch"):
                store.validate_source_fidelity_packet("task-1", packet)
            store.close()

    def test_controller_binds_source_receipt_to_source_role_child_dispatch(self):
        template = self.source_task()
        manifest = ScopeManifest("run-1", "goal", (), (), (), "base", "d" * 64, ("src",), (), ("src",), "D0", "I1", "A1", "CONTRACT_FROZEN", {"main": "main"}, (template,))
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.sqlite")
            store.create_run(manifest); store.add_tasks("run-1", [manifest.runtime_task("task-1")])
            store.record_evidence({"evidence_id": "ev-source-test", "run_id": "run-1", "task_id": "task-1", "kind": "TEST_RECEIPT", "source": "unittest", "manifest_hash": manifest.manifest_hash(), "base_revision": "base", "result_revision": "r1", "artifact_hash": "f" * 64, "command_or_ui_step": "python -m unittest test_render -q", "exit_code": 0, "observed_at": "now", "limitations": "local deterministic fixture", "redaction_status": "REDACTED", "payload": {}})
            events = [
                {"method": "thread/started", "params": {"thread": {"id": "sf-child", "parentThreadId": "parent-1"}}},
                {"method": "thread/settings/updated", "params": {"threadId": "sf-child", "threadSettings": {"model": "gpt-6-luna", "effort": "xhigh"}}},
                {"method": "turn/completed", "params": {"threadId": "sf-child"}},
            ]
            dispatch = handle(store, "bind-source-dispatch", {"payload": {
                "run_id": "run-1", "manifest_hash": manifest.manifest_hash(), "result_revision": "r1", "base_revision": "base", "evidence_id": "ev-source-dispatch",
                "request": {"parent_thread_id": "parent-1", "task_id": "task-1", "role": "source_fidelity", "requested_model": "gpt-6-luna", "requested_effort": "xhigh", "profile_id": "madv2_source_fidelity_a1_luna_xhigh", "sandbox_mode": "read-only", "hook_status": "HOOK_UNVERIFIED"},
                "events": events,
            }})
            self.assertTrue(dispatch["ok"])
            receipt_payload = self.complete_receipt_payload(manifest.manifest_hash())
            store.record_evidence({"evidence_id": "ev-source-pass", "run_id": "run-1", "task_id": "task-1", "kind": "SOURCE_FIDELITY_RECEIPT", "source": "source-fidelity-agent", "manifest_hash": manifest.manifest_hash(), "base_revision": "base", "result_revision": "r1", "artifact_hash": "d" * 64, "command_or_ui_step": None, "exit_code": None, "observed_at": "now", "limitations": "code-level fixture", "redaction_status": "REDACTED", "payload": receipt_payload})
            packet = {"source_fidelity_status": "PASS", "source_fidelity_evidence_refs": ["ev-source-pass"], "source_fidelity_dispatch_evidence_refs": ["ev-source-dispatch"], "evidence_refs": ["ev-source-pass", "ev-source-test", "ev-source-dispatch"], "source_fidelity_target_manifest_hash": "a" * 64, "result_revision": "r1", "diff_hash": "d" * 64}
            store.validate_source_fidelity_packet("task-1", packet)
            store.close()

    def test_reference_manifest_mismatch_is_not_pass(self):
        td, source_root, target_root, base_root = self.make_roots("def f():\n    return 1\n", "def f():\n    return 1\n")
        self.addCleanup(td.cleanup)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("f",))
        receipt = inspect(self.spec(source_root, target_root, base_root, "0" * 64, mapping), "sfr-3", "r1", "d" * 64, ("ev-sf",))
        self.assertEqual(receipt.status, "REFERENCE_UNVERIFIED")

    def test_target_tree_manifest_mismatch_is_insufficient(self):
        text = "def f():\n    return 1\n"
        td, source_root, target_root, base_root = self.make_roots(text, text)
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("f",))
        receipt = inspect(self.spec(source_root, target_root, base_root, source_hash, mapping, target_hash="0" * 64), "sfr-target-freeze", "r1", "d" * 64, ("ev-sf",))
        self.assertEqual(receipt.status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(receipt.next_action, "freeze_target")

    def test_mapping_manifest_mismatch_is_insufficient(self):
        text = "def f():\n    return 1\n"
        td, source_root, target_root, base_root = self.make_roots(text, text)
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("f",))
        spec = self.spec(source_root, target_root, base_root, source_hash, mapping)
        spec = ReferenceSpec(**{**spec.__dict__, "mapping_manifest_sha256": "0" * 64})
        receipt = inspect(spec, "sfr-mapping-freeze", "r1", diff_manifest_hash(base_root, target_root, ("dst.py",)), ("ev-sf",))
        self.assertEqual(receipt.status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(receipt.next_action, "freeze_mapping")

    def test_diff_hash_mismatch_is_blocked(self):
        text = "def f():\n    return 1\n"
        td, source_root, target_root, base_root = self.make_roots(text, text)
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("f",))
        receipt = inspect(self.spec(source_root, target_root, base_root, source_hash, mapping), "sfr-4", "r1", "d" * 64, ("ev-sf",))
        self.assertEqual(receipt.status, "BLOCK")
        self.assertTrue(any(item.startswith("DIFF_HASH_MISMATCH") for item in receipt.deviations))

    def test_missing_target_baseline_is_insufficient_evidence(self):
        text = "def f():\n    return 1\n"
        td, source_root, target_root, base_root = self.make_roots(text, text)
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE", source_symbols=("f",))
        spec = ReferenceSpec("ref-1", "repo", "abc", str(source_root), str(target_root), source_hash, "run-1", "task-1", scope_manifest_hash="a"*64, changed_paths=("dst.py",), mappings=(mapping,))
        receipt = inspect(spec, "sfr-5", "r1", "d" * 64, ("ev-sf",))
        self.assertEqual(receipt.status, "INSUFFICIENT_EVIDENCE")

    def test_unmapped_changed_path_is_rejected_at_freeze(self):
        td, source_root, target_root, base_root = self.make_roots("x=1\n", "x=1\n")
        self.addCleanup(td.cleanup)
        _, source_hash = file_manifest(source_root)
        mapping = SourceMapping("m-1", "src.py", "dst.py", "DIRECT_REUSE")
        with self.assertRaises(ContractError):
            ReferenceSpec("ref-1", "repo", "abc", str(source_root), str(target_root), source_hash, "run-1", "task-1", changed_paths=("other.py",), mappings=(mapping,))

    def test_platform_shell_requires_explicit_authorization(self):
        with self.assertRaises(ContractError):
            SourceMapping("m-1", None, "auth.py", "PLATFORM_SHELL")

    def test_source_required_handoff_gate_is_fail_closed(self):
        packet = HandoffPacket("task-1", "run-1", "attempt-1", "h" * 64, 1, "lease", "base", "result", "SUCCEEDED", ("src/a.py",), "d" * 64, ("a" * 64,), ({"command": "unit", "exit_code": 0},), ("ev",), None, {"route_status": "ROUTE_UNVERIFIED"}, "HOOK_UNVERIFIED", "WARN", (), (), ("audit",), {}, ("src/a.py",))
        guard = inspect_handoff(packet, "h" * 64, source_fidelity_required=True)
        self.assertEqual(guard.decision, "BLOCK")
        self.assertIn("SOURCE_REFERENCE_UNVERIFIED", guard.reason_codes)

    def test_source_evidence_kind_is_accepted_and_unknown_kind_rejected(self):
        common = dict(evidence_id="ev-sf", run_id="run-1", task_id="task-1", source="source-fidelity-agent", manifest_hash="h" * 64, base_revision=None, result_revision="result", artifact_hash="d" * 64, command_or_ui_step=None, exit_code=None, observed_at="now", limitations="static only", redaction_status="none", payload={"status": "PASS"})
        self.assertEqual(EvidenceRecord(kind="SOURCE_FIDELITY_RECEIPT", **common).as_dict()["kind"], "SOURCE_FIDELITY_RECEIPT")
        with self.assertRaises(ContractError):
            EvidenceRecord(kind="NOT_A_KIND", **common)

    def test_raw_state_evidence_rejects_secret_like_payload(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(Path(td) / "state.sqlite")
            with self.assertRaises(ContractError):
                store.record_evidence({"evidence_id": "ev-secret", "run_id": "run-1", "kind": "USER_DECISION", "source": "operator", "manifest_hash": "a" * 64, "observed_at": "now", "limitations": "none", "redaction_status": "none", "payload": {"note": "sk-1234567890abcdef"}})
            store.close()

    def test_wrapped_source_payload_is_unwrapped(self):
        payload = {"receipt_id": "sfr-1"}
        self.assertEqual(StateStore._unwrap_source_receipt_payload({"kind": "SOURCE_FIDELITY_RECEIPT", "source": "source-fidelity-agent", "payload": payload}), payload)


if __name__ == "__main__":
    unittest.main()
