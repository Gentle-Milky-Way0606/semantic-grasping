from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[2] / "configs" / "method_profiles.yaml"


def deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_profiles(path: str | Path = DEFAULT_PROFILE_PATH) -> dict[str, Any]:
    data = load_yaml(path)
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError(f"Invalid profile file: {path}")
    return profiles


def get_profile(method: str, path: str | Path = DEFAULT_PROFILE_PATH) -> dict[str, Any]:
    profiles = load_profiles(path)
    if method not in profiles:
        raise KeyError(f"Unknown method {method!r}. Available: {sorted(profiles)}")
    profile = deepcopy(profiles[method])
    profile["name"] = method
    return profile
