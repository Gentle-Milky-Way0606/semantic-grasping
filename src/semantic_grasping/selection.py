from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class SelectionResult:
    selected_index: int
    raw_selected_index: int
    anchor_source: str
    selected_pose_cam: np.ndarray
    scores: dict[str, Any]
    guard_debug: dict[str, Any]


def _as_grasps(candidates: Any) -> np.ndarray:
    arr = np.asarray(candidates, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[1:] != (4, 4):
        raise ValueError("Expected candidates to have shape [N, 4, 4].")
    if arr.shape[0] == 0:
        raise ValueError("Expected at least one grasp candidate.")
    return arr


def contact_centers(candidate_grasps: np.ndarray, gripper_depth_m: float) -> np.ndarray:
    return candidate_grasps[:, :3, 3] + float(gripper_depth_m) * candidate_grasps[:, :3, 2]


def _candidate_uv(observation: dict[str, Any], key: str, fallback_xyz: np.ndarray) -> np.ndarray:
    if key in observation:
        uv = np.asarray(observation[key], dtype=np.float64)
        if uv.shape[0] != fallback_xyz.shape[0] or uv.shape[1] != 2:
            raise ValueError(f"{key} must have shape [N, 2].")
        return uv
    return fallback_xyz[:, :2]


def _tilt_deg(T: np.ndarray) -> float:
    z_axis = T[:3, 2]
    z_axis = z_axis / (np.linalg.norm(z_axis) + 1e-12)
    tabletop_axis = np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
    return float(np.degrees(np.arccos(np.clip(abs(float(np.dot(z_axis, tabletop_axis))), -1.0, 1.0))))


def score_candidates(
    *,
    observation: dict[str, Any],
    semantic_uv: list[float],
    runtime_cfg: dict[str, Any],
) -> dict[str, np.ndarray]:
    cfg = runtime_cfg.get("selection", runtime_cfg)
    grasps = _as_grasps(observation["candidate_grasps"])
    gripper_depth_m = float(cfg.get("gripper_depth_m", 0.1406))
    centers = contact_centers(grasps, gripper_depth_m)
    contact_uv = _candidate_uv(observation, "candidate_contact_uv", centers)
    grasp_uv = _candidate_uv(observation, "candidate_grasp_uv", grasps[:, :3, 3])

    semantic = np.asarray(semantic_uv, dtype=np.float64).reshape(2)
    contact_dist_px = np.linalg.norm(contact_uv - semantic.reshape(1, 2), axis=1)
    grasp_dist_px = np.linalg.norm(grasp_uv - semantic.reshape(1, 2), axis=1)
    projection_score = (
        float(cfg.get("semantic_projection_origin_weight", 0.7)) * contact_dist_px
        + float(cfg.get("semantic_projection_grasp_point_weight", 0.3)) * grasp_dist_px
    )

    semantic_xyz = observation.get("semantic_xyz_cam")
    semantic_xy_dist_m = np.full(grasps.shape[0], np.nan, dtype=np.float64)
    if semantic_xyz is not None:
        semantic_xyz_arr = np.asarray(semantic_xyz, dtype=np.float64).reshape(3)
        semantic_xy_dist_m = np.linalg.norm(centers[:, :2] - semantic_xyz_arr[:2].reshape(1, 2), axis=1)
        projection_score = projection_score + 700.0 * semantic_xy_dist_m

    table_z = float(cfg.get("table_z_cam_m", observation.get("table_z_cam_m", 0.62)))
    table_clearance = float(cfg.get("table_grasp_clearance_m", 0.028))
    target_z_margin = float(cfg.get("target_z_margin_m", 0.120))
    max_tilt = float(cfg.get("max_tilt_deg", 14.0))
    tilt = np.asarray([_tilt_deg(T) for T in grasps], dtype=np.float64)
    grasp_z = centers[:, 2]
    table_shortfall = np.maximum(0.0, table_z + table_clearance - grasp_z)
    target_shortfall = np.maximum(0.0, table_z + target_z_margin - grasps[:, 2, 3])
    tilt_violation = np.maximum(0.0, tilt - max_tilt)
    execution_penalty = 10000.0 * table_shortfall + 6000.0 * target_shortfall + 50.0 * tilt_violation

    return {
        "contact_dist_px": contact_dist_px,
        "grasp_dist_px": grasp_dist_px,
        "semantic_xy_dist_m": semantic_xy_dist_m,
        "projection_score": projection_score,
        "execution_penalty": execution_penalty,
        "combined_score": projection_score + execution_penalty,
        "tilt_deg": tilt,
        "grasp_z_m": grasp_z,
        "table_shortfall_m": table_shortfall,
        "target_shortfall_m": target_shortfall,
    }


def select_anchor(
    *,
    observation: dict[str, Any],
    semantic_uv: list[float],
    method_profile: dict[str, Any],
    runtime_cfg: dict[str, Any],
) -> SelectionResult:
    cfg = runtime_cfg.get("selection", runtime_cfg)
    grasps = _as_grasps(observation["candidate_grasps"])
    scores = score_candidates(observation=observation, semantic_uv=semantic_uv, runtime_cfg=runtime_cfg)
    raw_index = int(np.argmin(scores["projection_score"]))

    front_end = str(method_profile.get("front_end", "raw_anchor"))
    selection_cfg = method_profile.get("selection", {})
    if front_end == "raw_anchor" or not bool(selection_cfg.get("semantic_selection_guard_enabled", False)):
        selected_index = raw_index
        anchor_source = "raw_anchor"
    else:
        topk = int(cfg.get("semantic_execution_guard_semantic_topk", 6))
        order = np.argsort(scores["projection_score"])[: max(1, min(topk, grasps.shape[0]))]
        selected_index = int(order[np.argmin(scores["combined_score"][order])])
        anchor_source = "conservative_anchor"

    max_contact_dist = float(cfg.get("semantic_selection_guard_max_contact_center_dist_px", 30.0))
    max_semantic_xy = float(cfg.get("semantic_selection_guard_max_semantic_xy_m", 0.030))
    far_reasons: list[str] = []
    if scores["contact_dist_px"][selected_index] > max_contact_dist:
        far_reasons.append("contact_center_far_from_semantic_point")
    semantic_xy = scores["semantic_xy_dist_m"][selected_index]
    if np.isfinite(semantic_xy) and semantic_xy > max_semantic_xy:
        far_reasons.append("semantic_xy_far")
    if scores["table_shortfall_m"][selected_index] > 1e-9:
        far_reasons.append("table_clearance_shortfall")
    if scores["target_shortfall_m"][selected_index] > 1e-9:
        far_reasons.append("target_z_shortfall")

    guard_debug = {
        "semantic_selection_guard_enabled": bool(selection_cfg.get("semantic_selection_guard_enabled", False)),
        "semantic_execution_guard_enabled": bool(selection_cfg.get("semantic_execution_guard_enabled", False)),
        "far_reasons": far_reasons,
        "raw_selected_index": raw_index,
        "selected_index": selected_index,
        "selected_contact_dist_px": float(scores["contact_dist_px"][selected_index]),
        "selected_semantic_xy_dist_m": None if not np.isfinite(semantic_xy) else float(semantic_xy),
        "selected_table_shortfall_m": float(scores["table_shortfall_m"][selected_index]),
        "selected_target_shortfall_m": float(scores["target_shortfall_m"][selected_index]),
        "selected_tilt_deg": float(scores["tilt_deg"][selected_index]),
    }
    return SelectionResult(
        selected_index=selected_index,
        raw_selected_index=raw_index,
        anchor_source=anchor_source,
        selected_pose_cam=grasps[selected_index],
        scores={key: value.tolist() for key, value in scores.items()},
        guard_debug=guard_debug,
    )
