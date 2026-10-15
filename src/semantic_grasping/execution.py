"""Paper-aligned dry-run execution planner.

Real-robot execution is intentionally unavailable: these files define the
decision and audit interface, not a calibrated FR3 controller.
"""
from __future__ import annotations

from typing import Any

from semantic_grasping.paper_rules import decide
from semantic_grasping.schemas import ExecutionPlan, SelectedGrasp


def estimate_risk(*, observation: dict[str, Any],
                  guard_debug: dict[str, Any],
                  method: str = "M3") -> dict[str, Any]:
    """Evaluate seven Table-I cues; never sum object-name heuristic weights."""
    decision = decide(
        method,
        observation.get("execution_conditions") or {},
        observation.get("execution_safety") or {},
        list(guard_debug.get("far_reasons") or []),
    )
    return {
        "risk_score": decision["risk_score"],
        "risk_level": decision["risk_level"],
        "cues": decision["cues"],
        "applied_profile_tier": decision["applied_profile_tier"],
        "abort": decision["abort"],
        "abort_reasons": decision["abort_reasons"],
        "status": "blocked" if decision["abort"] else "verified_input_dry_run",
    }


def build_execution_plan(
    *,
    selected_grasp: SelectedGrasp,
    method_profile: dict[str, Any],
    runtime_cfg: dict[str, Any],
    observation: dict[str, Any],
    guard_debug: dict[str, Any],
) -> ExecutionPlan:
    method = str(method_profile.get("name", ""))
    if method not in {"M1", "M2", "M3"}:
        raise ValueError("method_profile.name must be M1/M2/M3")

    decision = decide(
        method,
        observation.get("execution_conditions") or {},
        observation.get("execution_safety") or {},
        list(guard_debug.get("far_reasons") or []),
    )
    risk = {
        "risk_score": decision["risk_score"],
        "risk_level": decision["risk_level"],
        "cues": decision["cues"],
        "applied_profile_tier": decision["applied_profile_tier"],
        "abort": decision["abort"],
        "abort_reasons": decision["abort_reasons"],
    }

    # Do not expose executable motion parameters when safety evidence is absent
    # or the independent pre-execution gate has fired.
    theta = dict(decision["profile"] or {})
    theta["risk"] = risk
    theta["controller_command_enabled"] = False
    theta["motion_sent"] = False
    theta["profile_source"] = "2026-09-28 TII Table II"
    theta["waypoint_plan"] = (
        ["pre_approach", "approach", "close", "lift", "retreat"]
        if not decision["abort"] else []
    )
    # M1/M2 still compute risk for audit, but must execute the fixed LOW tier.
    # M3 uses the selected risk tier. No extra recovery/probe is simulated here.

    return ExecutionPlan(
        execution_policy=str(method_profile.get("execution_policy", "")),
        theta_exec=theta,
        selected_grasp_path="selected_grasp.json",
        safety_checks={
            "semantic_guard": guard_debug,
            "preexecution_abort": decision["abort"],
            "abort_reasons": decision["abort_reasons"],
            # This repository is only a dry-run reference implementation.
            "allow_execute": False,
            "eligible_for_external_adapter": not decision["abort"],
            "hardware_controller_verified": False,
            "source": "TII Eq. (5), Table III",
        },
        expected_motion={
            "motion_sent": False,
            "dry_run_plan_only": True,
            "note": (
                "No calibrated Cartesian controller, collision checker, "
                "runtime force stop, or physical motion is implemented. "
                "Do not interpret this dry-run plan as a safety certification."
            ),
        },
        dry_run_plan_only=True,
    )
