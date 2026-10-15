"""Ensure paper router is connected to the public ExecutionPlan interface."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from semantic_grasping.execution import build_execution_plan
from test_paper_rules import raw_packet, safe_packet


class ExecutionIntegrationTests(unittest.TestCase):
    def make_plan(self, method, raw=None, safety=None):
        return build_execution_plan(
            selected_grasp=None,
            method_profile={"name": method, "execution_policy": "test_dry_run"},
            runtime_cfg={},
            observation={"execution_conditions": raw if raw is not None else raw_packet(),
                         "execution_safety": safety if safety is not None else safe_packet()},
            guard_debug={"far_reasons": []},
        )

    def test_m1_m2_fixed_m3_high_on_same_packet(self):
        raw = raw_packet()
        raw["invalid_depth_fraction"] = .45
        plans = [self.make_plan(m, raw=raw) for m in ("M1", "M2", "M3")]
        self.assertEqual([p.theta_exec["motion_scale"] for p in plans], [.80, .80, .45])
        self.assertTrue(all(p.theta_exec["risk"]["risk_level"] == "high" for p in plans))
        self.assertTrue(all(p.safety_checks["eligible_for_external_adapter"] for p in plans))
        self.assertTrue(all(not p.safety_checks["allow_execute"] for p in plans))

    def test_missing_evidence_never_exposes_motion(self):
        plan = build_execution_plan(
            selected_grasp=None, method_profile={"name": "M3"},
            runtime_cfg={}, observation={}, guard_debug={},
        )
        self.assertTrue(plan.safety_checks["preexecution_abort"])
        self.assertEqual(plan.theta_exec["waypoint_plan"], [])
        self.assertNotIn("motion_scale", plan.theta_exec)
        self.assertFalse(plan.safety_checks["allow_execute"])
        self.assertFalse(plan.theta_exec["controller_command_enabled"])

    def test_failed_workspace_gate_blocks_even_fixed_baseline(self):
        s = safe_packet()
        s["grasp_xyz_world_m"][0] = .99
        plan = self.make_plan("M1", safety=s)
        self.assertTrue(plan.safety_checks["preexecution_abort"])
        self.assertEqual(plan.theta_exec["waypoint_plan"], [])
        self.assertFalse(plan.safety_checks["eligible_for_external_adapter"])


if __name__ == "__main__":
    unittest.main()
