from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import route_contract as route  # noqa: E402


def payload(role: str = "execute", **overrides: str) -> dict[str, str]:
    value = {
        "role": role,
        "design_ambiguity": "D0",
        "implementation": "I1",
        "audit_risk": "A0",
        "stage": "CONTRACT_FROZEN",
        "profile_id": "madv2_execute_i1_luna_high",
        "task_id": "task-001",
        "contract_rev": route.CONTRACT_REV,
    }
    value.update(overrides)
    return value


class RouteContractTests(unittest.TestCase):
    def test_round_trip_and_requires_first_nonempty_line(self) -> None:
        marker = route.build_marker(payload())
        self.assertEqual(route.parse_marker("\n  " + marker + "\nbody"), payload())
        self.assertIsNone(route.parse_marker("ordinary message\n" + marker))
        self.assertIsNone(route.parse_marker("MAD_ROUTE_V1 {}"))

    def test_think_requires_material_ambiguity_and_precontract(self) -> None:
        think = payload(
            role="think",
            design_ambiguity="D1",
            stage="PRE_CONTRACT",
            profile_id=route.THINK_PROFILE,
        )
        self.assertEqual(route.validate_payload(think), think)
        with self.assertRaises(route.RouteContractError):
            route.validate_payload({**think, "design_ambiguity": "D0"})

    def test_all_execute_and_audit_profiles_match_tiers(self) -> None:
        for tier, profile in route.IMPLEMENTATION_PROFILE.items():
            item = payload(implementation=tier, profile_id=profile)
            self.assertEqual(route.validate_payload(item)["profile_id"], profile)
        for tier, profile in route.SOURCE_FIDELITY_PROFILE.items():
            item = payload(
                role="source_fidelity",
                audit_risk=tier,
                stage="VERSION_FROZEN",
                profile_id=profile,
            )
            self.assertEqual(route.validate_payload(item)["profile_id"], profile)

    def test_source_fidelity_requires_critical_audit_tier(self) -> None:
        item = payload(
            role="source_fidelity",
            audit_risk="A1",
            stage="VERSION_FROZEN",
            profile_id=route.SOURCE_FIDELITY_PROFILE["A1"],
        )
        self.assertEqual(route.validate_payload(item)["role"], "source_fidelity")
        with self.assertRaises(route.RouteContractError):
            route.validate_payload({**item, "audit_risk": "A0", "profile_id": "madv2_source_fidelity_a1_luna_xhigh"})
        with self.assertRaises(route.RouteContractError):
            route.validate_payload({**item, "implementation": "I2"})
        for tier, profile in route.AUDIT_PROFILE.items():
            item = payload(
                role="audit",
                audit_risk=tier,
                stage="VERSION_FROZEN",
                profile_id=profile,
            )
            self.assertEqual(route.validate_payload(item)["profile_id"], profile)

    def test_rejects_bad_profile_stage_contract_task_and_unknown_fields(self) -> None:
        invalid = [
            {**payload(), "profile_id": "madv2_execute_i0_luna_low"},
            {**payload(), "stage": "PRE_CONTRACT"},
            {**payload(), "contract_rev": "v1"},
            {**payload(), "task_id": "../unsafe"},
            {**payload(), "extra": "unapproved"},
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(route.RouteContractError):
                route.validate_payload(item)

    def test_rejects_duplicate_json_keys_and_malformed_marker(self) -> None:
        raw = json.dumps(payload(), separators=(",", ":"))
        duplicate = raw[:-1] + ',"role":"audit"}'
        with self.assertRaises(route.RouteContractError):
            route.parse_marker(route.MARKER + " " + duplicate)
        with self.assertRaises(route.RouteContractError):
            route.parse_marker(route.MARKER + "not-json")


if __name__ == "__main__":
    unittest.main()
