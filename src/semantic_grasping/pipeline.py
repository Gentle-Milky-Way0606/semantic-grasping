from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from semantic_grasping.execution import build_execution_plan
from semantic_grasping.frontend import MolmoFrontendAdapter
from semantic_grasping.profiles import get_profile, load_yaml
from semantic_grasping.schemas import SelectedGrasp, TrialResult, iso_now, jsonable
from semantic_grasping.selection import select_anchor


DEFAULT_RUNTIME_PATH = Path(__file__).resolve().parents[2] / "configs" / "runtime.yaml"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(data), ensure_ascii=False, indent=2), encoding="utf-8")


def run_pipeline(
    *,
    observation: dict[str, Any],
    method: str,
    output_dir: str | Path,
    runtime_path: str | Path = DEFAULT_RUNTIME_PATH,
    profiles_path: str | Path | None = None,
) -> dict[str, Any]:
    runtime_cfg = load_yaml(runtime_path)
    profile = get_profile(method, profiles_path) if profiles_path else get_profile(method)
    task = str(observation.get("task_instruction") or observation.get("task") or "")
    object_id = observation.get("object_id")
    target_part = observation.get("target_part")

    frontend = MolmoFrontendAdapter(runtime_cfg.get("frontend", {}))
    semantic = frontend.predict_point(observation, task)
    selection = select_anchor(
        observation=observation,
        semantic_uv=semantic.uv,
        method_profile=profile,
        runtime_cfg=runtime_cfg,
    )

    selected = SelectedGrasp(
        pose_cam=selection.selected_pose_cam.tolist(),
        pose_robot=None,
        score=float(selection.scores["combined_score"][selection.selected_index]),
        uncertainty=observation.get("uncertainty_score"),
        candidate_rank=int(selection.selected_index),
        frontend_name=str(profile.get("frontend_name", frontend.frontend_name)),
        frontend_type=str(profile.get("frontend_type", frontend.frontend_type)),
        task_instruction=task,
        target_object=object_id,
        target_part=target_part,
        affordance_region=observation.get("affordance_region"),
        part_mask_path=observation.get("part_mask_path"),
        is_task_oriented=True,
        semantic_validity_manual_label=None,
        raw_output_path="frontend_raw_output.json",
        anchor_source=selection.anchor_source,
        notes=str(profile.get("description", "")),
    )
    plan = build_execution_plan(
        selected_grasp=selected,
        method_profile=profile,
        runtime_cfg=runtime_cfg,
        observation=observation,
        guard_debug=selection.guard_debug,
    )

    output_path = Path(output_dir)
    router_input = {
        "schema_version": "semantic-grasping-v1",
        "created_at": iso_now(),
        "method_profile": profile,
        "semantic_point": semantic.__dict__,
        "selection": {
            "raw_selected_index": selection.raw_selected_index,
            "selected_index": selection.selected_index,
            "anchor_source": selection.anchor_source,
            "scores": selection.scores,
            "guard_debug": selection.guard_debug,
        },
    }
    router_output = {
        "schema_version": "semantic-grasping-v1",
        "router_name": "lightweight_rule_codebook_router",
        "router_scope": "post_selection_execution_adapter",
        "policy": plan.execution_policy,
        "theta_exec": plan.theta_exec,
        "evidence_boundary": {
            "learned_router": False,
            "contact_evidence_used_online": False,
            "molmo_weights_vendored": False,
            "external_frontend_comparison_claimed": False,
        },
    }
    trial = TrialResult(
        trial_id=f"{observation.get('id', 'demo')}_{method}",
        scene=str(observation.get("scene", "demo_scene")),
        object_id=str(object_id or ""),
        task_instruction=task,
        frontend=selected.frontend_type,
        execution_policy=plan.execution_policy,
        method=method,
        target_object_correct=None,
        target_part_correct=None,
        task_oriented_grasp_valid=None,
        execution_success=None,
        overall_task_success=None,
        failure_type="unlabeled_dry_run",
        raw_paths={
            "frontend_raw_output": "frontend_raw_output.json",
            "selected_grasp": "selected_grasp.json",
            "execution_router_input": "execution_router_input.json",
            "execution_plan": "execution_plan.json",
            "execution_router_output": "execution_router_output.json",
        },
    )

    write_json(output_path / "frontend_raw_output.json", semantic.raw)
    write_json(output_path / "selected_grasp.json", selected.to_dict())
    write_json(output_path / "execution_router_input.json", router_input)
    write_json(output_path / "execution_plan.json", plan.to_dict())
    write_json(output_path / "execution_router_output.json", router_output)
    write_json(output_path / "paper_result.json", trial.to_dict())

    return {
        "output_dir": str(output_path),
        "method": method,
        "selected_index": selection.selected_index,
        "raw_selected_index": selection.raw_selected_index,
        "anchor_source": selection.anchor_source,
        "execution_policy": plan.execution_policy,
        "allow_execute": plan.safety_checks["allow_execute"],
        "risk": plan.theta_exec.get("risk"),
    }
