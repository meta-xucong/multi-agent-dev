from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from runtime_dispatch import (  # noqa: E402
    RuntimeDispatchError,
    RuntimeDispatchRequest,
    RuntimeDispatchSession,
    collect_child_provenance,
)
from orchestrate import handle  # noqa: E402
from state_store import StateStore  # noqa: E402
from parallel_manifest import ContractError  # noqa: E402


def request(**overrides):
    value = {
        "parent_thread_id": "parent-001",
        "task_id": "task-001",
        "requested_model": "gpt-6-luna",
        "requested_effort": "high",
        "profile_id": "madv2_execute_i1_luna_high",
        "hook_status": "HOOK_UNAVAILABLE",
    }
    value.update(overrides)
    return RuntimeDispatchRequest(**value)


def child_started(child_id="child-001"):
    return {
        "method": "thread/started",
        "params": {
            "thread": {
                "id": child_id,
                "parentThreadId": "parent-001",
                "model": "gpt-6-luna",
                "reasoningEffort": None,
            }
        },
    }


def settings(child_id="child-001", model="gpt-6-luna", effort="high"):
    return {
        "method": "thread/settings/updated",
        "params": {
            "threadId": child_id,
            "threadSettings": {"model": model, "effort": effort},
        },
    }


def completed(child_id="child-001"):
    return {"method": "turn/completed", "params": {"threadId": child_id}}


class RuntimeDispatchTests(unittest.TestCase):
    def test_matching_child_settings_and_terminal_event_are_admissible(self):
        result = collect_child_provenance(request(), [child_started(), settings(), completed()])
        self.assertEqual(result.lifecycle, "CHILD_COMPLETED")
        self.assertEqual(result.route_provenance.route_status, "EXPLICIT_ROUTE_VERIFIED")
        self.assertTrue(result.parent_close_allowed)
        self.assertTrue(result.admissible)

    def test_missing_settings_stays_unverified_even_when_child_finishes(self):
        result = collect_child_provenance(request(), [child_started(), completed()])
        self.assertEqual(result.lifecycle, "CHILD_COMPLETED")
        self.assertEqual(result.route_provenance.route_status, "ROUTE_UNVERIFIED")
        self.assertIn("ROUTE_PROVENANCE_MISSING", result.blockers)
        self.assertFalse(result.admissible)

    def test_mismatched_observed_route_blocks(self):
        result = collect_child_provenance(request(), [child_started(), settings(model="gpt-6-sol", effort="max"), completed()])
        self.assertEqual(result.route_provenance.route_status, "ROUTE_MISMATCH")
        self.assertIn("ROUTE_MISMATCH", result.blockers)
        self.assertFalse(result.admissible)

    def test_parent_cannot_close_before_child_terminal(self):
        session = RuntimeDispatchSession(request())
        session.observe(child_started())
        session.observe(settings())
        with self.assertRaisesRegex(RuntimeDispatchError, "PARENT_CLOSE_BEFORE_CHILD_TERMINAL"):
            session.close_parent()
        self.assertIn("PARENT_CLOSED_BEFORE_CHILD_TERMINAL", session.result().blockers)
        with self.assertRaisesRegex(RuntimeDispatchError, "PARENT_ALREADY_CLOSED"):
            session.observe(completed())

    def test_spawn_failure_does_not_look_like_a_completed_task(self):
        failure = {
            "method": "rawResponseItem/completed",
            "params": {"item": {"type": "function_call_output", "output": "collab spawn failed: no thread with id"}},
        }
        result = collect_child_provenance(request(), [failure])
        self.assertEqual(result.lifecycle, "SPAWN_FAILED")
        self.assertIn("CHILD_THREAD_NOT_STARTED", result.blockers)
        self.assertFalse(result.admissible)

    def test_spawn_failure_remains_a_hold_even_if_child_events_follow(self):
        failure = {"method": "collaboration/spawn_failed", "params": {"threadId": "parent-001"}}
        result = collect_child_provenance(request(), [child_started(), settings(), completed(), failure])
        self.assertEqual(result.lifecycle, "SPAWN_FAILED")
        self.assertIn("SPAWN_FAILED", result.blockers)
        self.assertFalse(result.admissible)

    def test_scoped_subagent_activity_can_bind_child(self):
        activity = {"method": "item/started", "params": {"threadId": "parent-001", "item": {"type": "subAgentActivity", "agentThreadId": "child-001"}}}
        result = collect_child_provenance(request(), [activity, settings(), completed()])
        self.assertEqual(result.child_thread_id, "child-001")
        self.assertTrue(result.admissible)

    def test_unscoped_subagent_activity_cannot_bind_child(self):
        activity = {"method": "item/started", "params": {"item": {"type": "subAgentActivity", "agentThreadId": "child-001"}}}
        result = collect_child_provenance(request(), [activity, settings(), completed()])
        self.assertEqual(result.lifecycle, "SPAWN_REQUESTED")
        self.assertIn("CHILD_THREAD_NOT_STARTED", result.blockers)
        self.assertFalse(result.admissible)

    def test_thread_started_route_fields_are_not_runtime_settings_proof(self):
        started = child_started()
        started["params"]["thread"]["reasoningEffort"] = "high"
        result = collect_child_provenance(request(), [started, completed()])
        self.assertEqual(result.route_provenance.route_status, "ROUTE_UNVERIFIED")
        self.assertEqual(result.route_provenance.source, "")
        self.assertFalse(result.admissible)

    def test_conflicting_settings_fail_closed(self):
        result = collect_child_provenance(request(), [child_started(), settings(), settings(effort="max"), completed()])
        self.assertEqual(result.route_provenance.route_status, "ROUTE_MISMATCH")
        self.assertIn("ROUTE_CONFLICT", result.blockers)
        self.assertFalse(result.admissible)

    def test_parent_terminal_event_blocks_admission(self):
        result = collect_child_provenance(request(), [child_started(), settings(), {"method": "turn/completed", "params": {"threadId": "parent-001"}}, completed()])
        self.assertIn("PARENT_TERMINATED_BEFORE_CHILD_TERMINAL", result.blockers)
        self.assertFalse(result.admissible)

    def test_supplied_child_id_without_start_event_is_not_start_proof(self):
        result = collect_child_provenance(request(child_thread_id="child-001"), [settings(), completed()])
        self.assertEqual(result.lifecycle, "SPAWN_REQUESTED")
        self.assertIn("CHILD_START_EVENT_MISSING", result.blockers)
        self.assertFalse(result.admissible)

    def test_parent_close_after_terminal_is_allowed(self):
        session = RuntimeDispatchSession(request())
        session.observe_many([child_started(), settings(), completed()])
        session.close_parent()
        self.assertTrue(session.result().parent_close_allowed)

    def test_controller_runtime_gate_returns_gate_hold_for_mismatch(self):
        payload = {
            "request": request().__dict__,
            "events": [child_started(), settings(model="gpt-6-sol", effort="max"), completed()],
        }
        with tempfile.TemporaryDirectory() as directory:
            state = StateStore(Path(directory) / "state.sqlite")
            response = handle(state, "runtime-gate", {"payload": payload})
            state.close()
        self.assertFalse(response["ok"])
        self.assertEqual(response["code"], "GATE_HOLD")
        self.assertEqual(response["data"]["route_provenance"]["route_status"], "ROUTE_MISMATCH")

    def test_source_fidelity_profile_cannot_claim_an_arbitrary_matching_route(self):
        with self.assertRaisesRegex(ContractError, "does not match the frozen V2 profile contract"):
            request(
                role="source_fidelity",
                profile_id="madv2_source_fidelity_a2_luna_max",
                requested_model="evil-model",
                requested_effort="low",
                sandbox_mode="read-only",
            )

    def test_source_fidelity_route_requires_read_only_a1_or_a2_contract(self):
        source_request = request(
            role="source_fidelity",
            profile_id="madv2_source_fidelity_a1_luna_xhigh",
            requested_model="gpt-6-luna",
            requested_effort="xhigh",
            sandbox_mode="read-only",
        )
        result = collect_child_provenance(
            source_request,
            [child_started(), settings(effort="xhigh"), completed()],
        )
        self.assertEqual(result.route_provenance.route_status, "EXPLICIT_ROUTE_VERIFIED")
        self.assertTrue(result.admissible)
        with self.assertRaisesRegex(ContractError, "does not match"):
            request(
                role="source_fidelity",
                profile_id="madv2_source_fidelity_a1_luna_xhigh",
                requested_model="gpt-6-luna",
                requested_effort="xhigh",
                sandbox_mode="workspace-write",
            )

    def test_source_fidelity_role_rejects_a_valid_but_wrong_audit_profile(self):
        with self.assertRaisesRegex(ContractError, "not permitted for the requested runtime role"):
            request(
                role="source_fidelity",
                profile_id="madv2_audit_a0_luna_high",
                requested_model="gpt-6-luna",
                requested_effort="high",
                sandbox_mode="read-only",
            )


if __name__ == "__main__":
    unittest.main()
