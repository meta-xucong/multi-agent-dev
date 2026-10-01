from __future__ import annotations

import sys
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - provides a clear result on unsupported Python
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class ProfileTests(unittest.TestCase):
    @unittest.skipIf(tomllib is None, "Python 3.11+ is required to parse profile TOML")
    def test_each_route_profile_matches_the_frozen_matrix(self) -> None:
        expected = {
            "madv2_think_sol_xhigh": ("gpt-6-sol", "xhigh", "read-only"),
            "madv2_execute_i0_luna_low": ("gpt-6-luna", "low", "workspace-write"),
            "madv2_execute_i1_luna_high": ("gpt-6-luna", "high", "workspace-write"),
            "madv2_execute_i2_luna_xhigh": ("gpt-6-luna", "xhigh", "workspace-write"),
            "madv2_execute_i3_luna_max": ("gpt-6-luna", "max", "workspace-write"),
            "madv2_audit_a0_luna_high": ("gpt-6-luna", "high", "read-only"),
            "madv2_audit_a1_luna_xhigh": ("gpt-6-luna", "xhigh", "read-only"),
            "madv2_audit_a2_luna_max": ("gpt-6-luna", "max", "read-only"),
            "madv2_source_fidelity_a1_luna_xhigh": ("gpt-6-luna", "xhigh", "read-only"),
            "madv2_source_fidelity_a2_luna_max": ("gpt-6-luna", "max", "read-only"),
        }
        profile_files = list((ROOT / "profiles").glob("*.toml"))
        self.assertEqual(len(profile_files), len(expected))
        for path in profile_files:
            with self.subTest(profile=path.name):
                profile = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(profile["name"], path.stem)
                self.assertEqual(
                    (profile["model"], profile["model_reasoning_effort"], profile["sandbox_mode"]),
                    expected[path.stem],
                )
                from route_contract import PROFILE_ROUTE_CONTRACT
                self.assertEqual(
                    PROFILE_ROUTE_CONTRACT[path.stem],
                    (profile["model"], profile["model_reasoning_effort"], profile["sandbox_mode"]),
                )
                self.assertTrue(profile["description"].strip())
                self.assertTrue(profile["developer_instructions"].strip())


if __name__ == "__main__":
    unittest.main()
