"""Formula and safety-gate regression tests for TII manuscript 2026-09-28."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from semantic_grasping.paper_rules import (
    CUES, PROFILES, condition_cues, decide, material_cue,
    replay_tiers, risk_and_tier,
)


def raw_packet():
    return {
        "invalid_depth_fraction": .10, "depth_std_m": .006,
        "object_height_m": .14, "grasp_table_clearance_m": .060,
        "object_table_clearance_m": .035, "edge_distance_px": 30.,
        "opening_margin_m": .018, "contact_area_m2": .0024 * .75,
        "normalized_safety_margins": {
            "workspace": .9, "tilt": .9, "offset": .9, "rotation": .9,
        },
        "material": {
            "reflectivity": "none", "transparent_or_glass": False,
            "deformable": False, "thin_walled": False,
            "annotation_uncertainty": 0.,
        },
    }


def safe_packet():
    return {
        "grasp_xyz_world_m": [.45, .1, .3],
        "minimum_grasp_height_margin_m": .08,
        "tilt_deg": 2., "required_rotation_deg": 10.,
        "pregrasp_lateral_offset_m": .01,
        "semantic_lateral_deviation_m": .01,
        "semantic_deviation_px": 15.,
        "center_projection_px": 8.,
        "task_target_preserved": True,
        "anchor_in_target_mask": True,
        "reachable": True,
        "collision_free_plan_verified": True,
    }


class PaperRulesTests(unittest.TestCase):
    def test_seven_cues_and_table_i_endpoints(self):
        z = condition_cues(raw_packet())
        self.assertEqual(tuple(z), CUES)
        for k in ("zD", "zH", "zT", "zE", "zC"):
            self.assertEqual(z[k], 0.)
        self.assertEqual(z["zM"], .20)
        self.assertAlmostEqual(z["zA"], .10)
        self.assertTrue(all(0 <= n <= 1 for n in z.values()))

    def test_depth_uses_max_not_sum(self):
        raw = raw_packet()
        raw["invalid_depth_fraction"] = .45
        self.assertEqual(condition_cues(raw)["zD"], 1.)

    def test_contact_opening_ramp_and_area(self):
        raw = raw_packet()
        raw["opening_margin_m"] = .004
        self.assertEqual(condition_cues(raw)["zC"], 1.)
        raw["opening_margin_m"] = .018
        raw["contact_area_m2"] = .0024 * .35
        self.assertEqual(condition_cues(raw)["zC"], 1.)

    def test_material_formula(self):
        record = raw_packet()["material"]
        self.assertAlmostEqual(material_cue(record), .20)
        record["reflectivity"] = "high"
        record["transparent_or_glass"] = True
        record["thin_walled"] = True
        record["annotation_uncertainty"] = 1.
        self.assertAlmostEqual(material_cue(record), 1.0)
        record["reflectivity"] = "invalid"
        with self.assertRaises(ValueError):
            material_cue(record)

    def test_paper_threshold_boundary(self):
        self.assertEqual(risk_and_tier(dict.fromkeys(CUES, .499999))[1], "low")
        self.assertEqual(risk_and_tier(dict.fromkeys(CUES, .50))[1], "mid")
        self.assertEqual(risk_and_tier(dict.fromkeys(CUES, .69999))[1], "mid")
        self.assertEqual(risk_and_tier(dict.fromkeys(CUES, .70))[1], "high")
        with self.assertRaises(ValueError):
            risk_and_tier({"zM": .2})
        with self.assertRaises(ValueError):
            risk_and_tier(dict.fromkeys(CUES, float("nan")))

    def test_profiles_exact_table_ii(self):
        self.assertEqual(
            [PROFILES[k]["motion_scale"] for k in ("low", "mid", "high")],
            [.80, .60, .45])
        self.assertEqual(
            [PROFILES[k]["gripper_force_n"] for k in ("low", "mid", "high")],
            [40, 25, 15])
        self.assertEqual(
            [PROFILES[k]["gripper_speed_mm_s"] for k in ("low", "mid", "high")],
            [150, 100, 50])
        self.assertEqual(
            [PROFILES[k]["exploration_amplitude_m"] for k in ("low","mid","high")],
            [0., .002, .004])

    def test_m1_m2_fixed_low_m3_routed(self):
        raw = raw_packet()
        raw["invalid_depth_fraction"] = .45
        out = [decide(m, raw, safe_packet()) for m in ("M1", "M2", "M3")]
        self.assertEqual([x["risk_level"] for x in out], ["high"]*3)
        self.assertEqual([x["applied_profile_tier"] for x in out],
                         ["low", "low", "high"])
        self.assertEqual([x["profile"]["motion_scale"] for x in out],
                         [.80, .80, .45])
        self.assertTrue(all(not x["abort"] for x in out))

    def test_workspace_and_table_abort_even_for_low(self):
        raw = raw_packet()
        raw["grasp_table_clearance_m"] = .02
        bad = decide("M3", raw, safe_packet())
        self.assertTrue(bad["abort"])
        self.assertIn("grasp_table_clearance_m", bad["abort_reasons"])

    def test_target_reach_and_plan_abort(self):
        for name in ("task_target_preserved", "anchor_in_target_mask",
                     "reachable", "collision_free_plan_verified"):
            safety = safe_packet()
            safety[name] = False
            self.assertIn(name, decide("M3", raw_packet(), safety)["abort_reasons"])

    def test_missing_evidence_is_fail_closed(self):
        result = decide("M3", {}, {})
        self.assertTrue(result["abort"])
        self.assertIsNone(result["profile"])
        raw = raw_packet()
        del raw["normalized_safety_margins"]
        self.assertTrue(decide("M3", raw, safe_packet())["abort"])

    def test_replay_only_tier_not_outcomes(self):
        z = dict.fromkeys(CUES, .25)
        z["zM"] = .75
        self.assertEqual(replay_tiers([z]), ["high"])
        self.assertEqual(replay_tiers([z], deleted_cue="zM"), ["low"])
        self.assertEqual(replay_tiers([z], substitute_material=.65), ["mid"])


if __name__ == "__main__":
    unittest.main()
