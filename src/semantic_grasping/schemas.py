from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


SCHEMA_VERSION = "semantic-grasping-v1"


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


@dataclass
class SelectedGrasp:
    pose_cam: list[list[float]]
    pose_robot: list[list[float]] | None
    score: float | None
    uncertainty: float | None
    candidate_rank: int
    frontend_name: str
    frontend_type: str
    task_instruction: str
    target_object: str | None
    target_part: str | None
    affordance_region: str | None
    part_mask_path: str | None
    is_task_oriented: bool
    semantic_validity_manual_label: bool | None
    raw_output_path: str
    anchor_source: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}


@dataclass
class ExecutionPlan:
    execution_policy: str
    theta_exec: dict[str, Any]
    selected_grasp_path: str
    safety_checks: dict[str, Any]
    expected_motion: dict[str, Any]
    dry_run_plan_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}


@dataclass
class TrialResult:
    trial_id: str
    scene: str
    object_id: str
    task_instruction: str
    frontend: str
    execution_policy: str
    method: str
    target_object_correct: bool | None
    target_part_correct: bool | None
    task_oriented_grasp_valid: bool | None
    execution_success: bool | None
    overall_task_success: bool | None
    failure_type: str
    raw_paths: dict[str, str]
    date: str = field(default_factory=iso_now)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}
