"""Paper-aligned, deterministic TII execution decision (NO hardware commands).

2026-09-28 TII revision: Eq. (2)-(5), Tables I-III.
All cues are derived from explicit upstream measurements, never object-ID tokens.
Unmeasured conditions and unverified geometry are NOT treated as safe.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

CUES = ("zD", "zH", "zT", "zE", "zM", "zA", "zC")
WORKSPACE = ((0.1786, 0.7029), (-0.3268, 0.5419), (0.0414, 0.7200))
# Table II: low is ALSO the fixed execution template for M1 and M2.
PROFILES: dict[str, dict[str, Any]] = {
    "low": dict(approach_offset_m=.08, motion_scale=.80,
                exploration_amplitude_m=.0, compliance_or_stiffness="nominal",
                stiffness_translation_n_m=2000, stiffness_rotation_nm_rad=100,
                damping_translation_ns_m=75, damping_rotation_nms_rad=3.5,
                gripper_force_n=40, gripper_speed_mm_s=150),
    "mid": dict(approach_offset_m=.09, motion_scale=.60,
                exploration_amplitude_m=.002, compliance_or_stiffness="medium_soft",
                stiffness_translation_n_m=1000, stiffness_rotation_nm_rad=60,
                damping_translation_ns_m=53, damping_rotation_nms_rad=2.7,
                gripper_force_n=25, gripper_speed_mm_s=100),
    "high": dict(approach_offset_m=.10, motion_scale=.45,
                 exploration_amplitude_m=.004, compliance_or_stiffness="soft",
                 stiffness_translation_n_m=500, stiffness_rotation_nm_rad=30,
                 damping_translation_ns_m=37, damping_rotation_nms_rad=1.9,
                 gripper_force_n=15, gripper_speed_mm_s=50),
}
BOUNDS = {"approach_offset_m": (.08, .10), "motion_scale": (.45, .80),
          "exploration_amplitude_m": (.0, .004)}


def number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} requires a finite real number")
    return float(value)


def unit(value: Any, label: str) -> float:
    x = number(value, label)
    if not 0 <= x <= 1:
        raise ValueError(f"{label} must be in [0,1]")
    return x


def clip01(value: float) -> float:
    return min(1., max(0., float(value)))


def ramp(x: float, lower: float, upper: float) -> float:
    return clip01((x - lower) / (upper - lower))


def down_ramp(x: float, lower: float, upper: float) -> float:
    return clip01((upper - x) / (upper - lower))


def material_cue(record: Mapping[str, Any]) -> float:
    """Table I: annotated object-level prior, never inferred from ID tokens."""
    reflect = record["reflectivity"]
    if reflect not in ("none", "medium", "high"):
        raise ValueError("reflectivity must be none/medium/high")
    flags = ("transparent_or_glass", "deformable", "thin_walled")
    for flag in flags:
        if type(record[flag]) is not bool:
            raise ValueError(f"material.{flag} requires an annotated boolean")
    u = unit(record["annotation_uncertainty"], "material.annotation_uncertainty")
    return clip01(.20 + {"none": 0., "medium": .20, "high": .30}[reflect]
                  + (.25 if record["transparent_or_glass"] else 0.)
                  + (.15 if record["deformable"] else 0.)
                  + (.10 if record["thin_walled"] else 0.) + .20*u)


def condition_cues(raw: Mapping[str, Any]) -> dict[str, float]:
    """Eq. (2), Table I. Geometry comes from the guarded anchor's 30px patch.

    normalized_safety_margins must be calibrated upstream relative to Table III.
    The paper does not define their exact within-bound normalization mapping;
    this core deliberately DOES NOT invent one.
    """
    names = ("invalid_depth_fraction", "depth_std_m", "object_height_m",
             "grasp_table_clearance_m", "object_table_clearance_m",
             "edge_distance_px", "opening_margin_m", "contact_area_m2")
    v = {k: number(raw[k], k) for k in names}
    unit(v["invalid_depth_fraction"], "invalid_depth_fraction")
    if v["depth_std_m"] < 0 or v["object_height_m"] < 0 or v["edge_distance_px"] < 0:
        raise ValueError("depth std, object height, edge distance must be nonnegative")
    if v["contact_area_m2"] < 0:
        raise ValueError("contact_area_m2 cannot be negative")
    margins = raw["normalized_safety_margins"]
    if not isinstance(margins, dict) or not margins:
        raise ValueError("normalized_safety_margins require nonempty calibrated margins")
    margin = min(unit(value, f"margin.{key}") for key, value in margins.items())
    z = {
        "zD": max(ramp(v["invalid_depth_fraction"], .10, .45),
                  ramp(v["depth_std_m"], .006, .025)),
        "zH": down_ramp(v["object_height_m"], .075, .140),
        "zT": max(down_ramp(v["grasp_table_clearance_m"], .028, .060),
                  down_ramp(v["object_table_clearance_m"], .010, .035)),
        "zE": down_ramp(v["edge_distance_px"], 0., 30.),
        "zM": material_cue(raw["material"]),
        "zA": clip01(1. - margin),
        "zC": max(down_ramp(v["opening_margin_m"], .004, .018),
                  down_ramp(v["contact_area_m2"] / .0024, .35, .75)),
    }
    return z


def risk_and_tier(cues: Mapping[str, float]) -> tuple[float, str]:
    """Eq. (3)-(4): max, thresholds 0.50 and 0.70; no additive heuristic."""
    if set(cues) != set(CUES):
        raise ValueError(f"exact seven cues required: {CUES}")
    rho = max(unit(cues[k], k) for k in CUES)
    return rho, "low" if rho < .50 else ("mid" if rho < .70 else "high")


def gated_reasons(raw: Mapping[str, Any], safety: Mapping[str, Any],
                  frontend_reasons: list[str] | None = None) -> list[str]:
    """Eq. (5), Table III. Fail closed when measurements/verification absent.

    Must be checked against world-frame geometry, not camera-frame pose.
    Runtime protective stopping must additionally be implemented by a robot
    controller before the code can ever be used for hardware execution.
    """
    reasons = list(frontend_reasons or [])
    coordinates = safety["grasp_xyz_world_m"]
    if len(coordinates) != 3:
        raise ValueError("grasp_xyz_world_m must have exactly 3 coordinates")
    for axis, x, (lo, hi) in zip("xyz", coordinates, WORKSPACE):
        if not lo <= number(x, f"world_{axis}") <= hi:
            reasons.append(f"workspace_{axis}")
    bounds = (
        ("grasp_table_clearance_m", raw["grasp_table_clearance_m"], .028, None),
        ("object_table_clearance_m", raw["object_table_clearance_m"], .010, None),
        ("minimum_grasp_height_margin_m", safety["minimum_grasp_height_margin_m"], .075, None),
        ("tilt_deg", safety["tilt_deg"], 0., 14.),
        ("required_rotation_deg", safety["required_rotation_deg"], 0., 110.),
        ("pregrasp_lateral_offset_m", safety["pregrasp_lateral_offset_m"], 0., .035),
        ("semantic_lateral_deviation_m", safety["semantic_lateral_deviation_m"], 0., .030),
        ("semantic_deviation_px", safety["semantic_deviation_px"], 0., 180.),
        ("center_projection_px", safety["center_projection_px"], 0., 30.),
    )
    for name, value, low, high in bounds:
        f = number(value, name)
        if f < low or (high is not None and f > high):
            reasons.append(name)
    for name in ("task_target_preserved", "anchor_in_target_mask",
                 "reachable", "collision_free_plan_verified"):
        if type(safety[name]) is not bool:
            raise ValueError(f"{name} must be explicitly verified")
        if not safety[name]:
            reasons.append(name)
    return reasons


def decide(method: str, raw: Mapping[str, Any], safety: Mapping[str, Any],
           frontend_reasons: list[str] | None = None) -> dict[str, Any]:
    """Return auditable dry-run decision; NEVER drives a robot."""
    if method not in ("M1", "M2", "M3"):
        raise ValueError("method must be M1/M2/M3")
    try:
        z = condition_cues(raw)
        rho, selected_tier = risk_and_tier(z)
        abort_reasons = gated_reasons(raw, safety, frontend_reasons)
    except (KeyError, ValueError, TypeError) as exc:
        return {
            "cues": None, "risk_score": None, "risk_level": None,
            "applied_profile_tier": None, "profile": None,
            "abort": True, "abort_reasons": ["missing_or_invalid_evidence: " + str(exc)],
            "dry_run_plan_only": True,
        }
    applied = selected_tier if method == "M3" else "low"
    profile = dict(PROFILES[applied])
    for key, (lower, upper) in BOUNDS.items():
        profile[key] = min(upper, max(lower, profile[key]))
    return {
        "cues": z, "risk_score": rho, "risk_level": selected_tier,
        "applied_profile_tier": applied, "profile": profile,
        "abort": bool(abort_reasons), "abort_reasons": abort_reasons,
        "dry_run_plan_only": True,
    }


def replay_tiers(cue_records: list[Mapping[str, float]],
                 deleted_cue: str | None = None,
                 substitute_material: float | None = None) -> list[str]:
    """Counterfactual tier replay only: NOT measured physical success."""
    if deleted_cue is not None and deleted_cue not in CUES:
        raise ValueError("unknown cue for deletion")
    results = []
    for item in cue_records:
        if set(item) != set(CUES):
            raise ValueError("record needs all seven cues")
        z = dict(item)
        if deleted_cue:
            z[deleted_cue] = 0.
        if substitute_material is not None:
            z["zM"] = unit(substitute_material, "substitute_material")
        results.append(risk_and_tier(z)[1])
    return results
