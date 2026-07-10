from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


MOLMO_MODEL_URL = "https://huggingface.co/allenai/Molmo-7B-D-0924"
MOLMO_CODE_URL = "https://github.com/allenai/molmo"


@dataclass
class SemanticPoint:
    uv: list[float]
    confidence: float | None
    source: str
    raw: dict[str, Any]


class MolmoFrontendAdapter:
    """Thin interface boundary for Molmo/GraspMolmo-style semantic pointing.

    This repository does not ship model weights. For real use, replace
    `predict_point` with a call into your Molmo or GraspMolmo runner that returns
    the task-relevant image point.
    """

    frontend_name = "GraspMolmo-style + M2T2"
    frontend_type = "graspmolmo_style"

    def __init__(self, cfg: dict[str, Any] | None = None) -> None:
        self.cfg = cfg or {}

    def predict_point(self, observation: dict[str, Any], task_instruction: str) -> SemanticPoint:
        if "semantic_uv" in observation:
            uv = np.asarray(observation["semantic_uv"], dtype=float).reshape(2)
            return SemanticPoint(
                uv=uv.tolist(),
                confidence=observation.get("semantic_confidence"),
                source="observation.semantic_uv",
                raw={
                    "frontend_name": self.frontend_name,
                    "frontend_type": self.frontend_type,
                    "model_url": MOLMO_MODEL_URL,
                    "code_url": MOLMO_CODE_URL,
                    "task_instruction": task_instruction,
                },
            )

        image_size = observation.get("image_size", [640, 480])
        width, height = float(image_size[0]), float(image_size[1])
        return SemanticPoint(
            uv=[width / 2.0, height / 2.0],
            confidence=None,
            source="image_center_fallback",
            raw={
                "frontend_name": self.frontend_name,
                "frontend_type": self.frontend_type,
                "model_url": MOLMO_MODEL_URL,
                "code_url": MOLMO_CODE_URL,
                "task_instruction": task_instruction,
                "note": "Fallback only. Provide observation.semantic_uv or plug in Molmo for real runs.",
            },
        )
