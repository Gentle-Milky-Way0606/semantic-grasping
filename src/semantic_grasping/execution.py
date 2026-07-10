from __future__ import annotations

from typing import Any

from semantic_grasping.schemas import ExecutionPlan, SelectedGrasp


def estimate_risk(
    *,
    observation: dict[str, Any],
    guard_debug: dict[str, Any],
) -> dict[str, Any]:
    object_id = str(observation.get("object_id", "")).lower()
    declared_uncertainty = str(observation.get("uncertainty_level", "")).lower()
    score = 0.0
    reasons: list[str] = []

    if any(token in object_id for token in ["transparent", "glass", "reflective", "metal"]):
        score += 0.35
        reasons.append("difficult_material")
    if declared_uncertainty == "high":
        score += 0.40
        reasons.append("declared_high_uncertainty")
    elif declared_uncertainty == "mid":
        score += 0.20
        reasons.append("declared_mid_uncertainty")
    if guard_debug.get("far_reasons"):
        score += 0.30
        reasons.extend(guard_debug["far_reasons"])
    if float(guard_debug.get("selected_tilt_deg", 0.0)) > 10.0:
        score += 0.15
        reasons.append("tilted_candidate")

    if score >= 0.65:
        level = "high"
    elif score >= 0.30:
        level = "mid"
    else:
        level = "low"
    return {"risk_score": round(score, 4), "risk_level": level, "reasons": reasons}


def build_execution_plan(
    *,
    selected_grasp: SelectedGrasp,
    method_profile: dict[str, Any],
    runtime_cfg: dict[str, Any],
    observation: dict[str, Any],
    guard_debug: dict[str, Any],
) -> ExecutionPlan:
    execution = str(method_profile.get("execution", "fixed_execution"))
    policy = str(method_profile.get("execution_policy", "original_fixed_execution"))
    risk = estimate_risk(observation=observation, guard_debug=guard_debug)

    if execution == "bounded_adaptive_execution":
        bounded_cfg = runtime_cfg.get("execution", {}).get("bounded", {})
        theta = dict(bounded_cfg.get(risk["risk_level"], {}))
        theta.update(
            {
                "approach_direction_adjustment": "tabletop_and_semantic_guarded",
                "local_refine_delta": {
                    "enabled": True,
                    "source": "semantic point + table clearance guard",
                    "delta_m": [0.0, 0.0, 0.0],
                },
                "stop_retry_gate": {
                    "stop_on_force": True,
                    "stop_on_width_anomaly": True,
                    "max_retries": 1,
                    "abort_reasons": guard_debug.get("far_reasons", []),
                },
                "risk": risk,
            }
        )
    else:
        theta = dict(method_profile.get("execution_theta") or runtime_cfg.get("execution", {}).get("fixed", {}))
        theta.update(
            {
                "approach_direction_adjustment": "fixed",
                "local_refine_delta": {"enabled": False},
                "stop_retry_gate": {"max_retries": 0},
                "risk": risk,
            }
        )

    expected_motion = {
        "motion_sent": False,
        "dry_run_plan_only": True,
        "note": "This package emits robot-agnostic execution parameters. Hardware adapters consume theta_exec.",
    }
    safety_checks = {
        "semantic_guard": guard_debug,
        "allow_execute": not guard_debug.get("far_reasons"),
        "policy_scope": "post-selection execution adapter after GraspMolmo-style selected grasp",
    }
    return ExecutionPlan(
        execution_policy=policy,
        theta_exec=theta,
        selected_grasp_path="selected_grasp.json",
        safety_checks=safety_checks,
        expected_motion=expected_motion,
        dry_run_plan_only=True,
    )
