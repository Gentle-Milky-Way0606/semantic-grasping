#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from semantic_grasping.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the semantic grasping dry-run pipeline.")
    parser.add_argument("--method", default="M3", choices=["M1", "M2", "M3"])
    parser.add_argument("--observation", default=str(ROOT / "examples" / "sample_observation.json"))
    parser.add_argument("--output-dir", default=str(ROOT / "runs" / "demo"))
    parser.add_argument("--runtime", default=str(ROOT / "configs" / "runtime.yaml"))
    parser.add_argument("--profiles", default=str(ROOT / "configs" / "method_profiles.yaml"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    observation = json.loads(Path(args.observation).read_text(encoding="utf-8"))
    summary = run_pipeline(
        observation=observation,
        method=args.method,
        output_dir=args.output_dir,
        runtime_path=args.runtime,
        profiles_path=args.profiles,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
