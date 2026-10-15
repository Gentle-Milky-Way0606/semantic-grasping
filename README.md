# Semantic Grasping

This repository is a clean open-source reference implementation of the current idea:

`GraspMolmo-style semantic point + M2T2-like grasp candidates + conservative frontend guard + bounded execution policy`.

It keeps only the code needed to explain and reproduce the method logic:

- `M1`: raw/base task-oriented anchor + fixed execution baseline.
- `M2`: conservative semantic/frontend guard + fixed execution ablation.
- `M3`: conservative semantic/frontend guard + bounded execution policy, the proposed method.

It deliberately does not include large datasets, robot logs, `.conda`, paper drafts, model weights, or hardware-specific runtime files.

## Layout

```text
semantic-grasping/
  src/semantic_grasping/  # Reusable method code
  configs/                # M1/M2/M3 profiles and runtime thresholds
  scripts/run_demo.py     # Dry-run demo entry point
  examples/               # Tiny JSON observation for smoke testing
  docs/molmo.md           # Molmo download links and integration notes
```

## Quick Start

```bash
cd semantic-grasping
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_demo.py --method M1 --output-dir runs/m1_demo
python scripts/run_demo.py --method M3 --output-dir runs/m3_demo
```

The demo writes:

- `selected_grasp.json`
- `execution_router_input.json`
- `execution_plan.json`
- `execution_router_output.json`
- `paper_result.json`

## Molmo

Molmo weights are not vendored here. Use the links in `docs/molmo.md`, then point your adapter/config to the local Hugging Face cache or model directory.

## What To Replace For Real Robot Use

This package is intentionally dry-run first. To connect the real stack:

1. Replace `MolmoFrontendAdapter.predict_point(...)` with the real Molmo/GraspMolmo point prediction.
2. Replace the example candidate list with real M2T2 6-DoF grasp candidates.
3. Send `ExecutionPlan.theta_exec` to your robot controller instead of using the dry-run artifact.
4. Keep `M1/M2/M3` profiles frozen when reporting baseline/proposed results.


## 2026 TII revised-manuscript alignment

The 2026-09-28 revised TII formulas and parameters are implemented in
`src/semantic_grasping/paper_rules.py` and connected to the dry-run
`execution.py` plan. See [formula audit and limitations](docs/TII_FORMULA_AUDIT.md).

**Important:** `M1` and `M2` use the fixed **low-tier** profile
(velocity scale 0.80). `M3` alone routes using the maximum of all seven
condition cues and thresholds 0.50 and 0.70. Previous ID-token
risk heuristics and the historical 0.30 fixed velocity are not paper-aligned.

This is not a hardware implementation: the example JSON contains no
verified world-frame Table-I/III execution geometry, so dry-run
planning now reports a blocked decision instead of inventing a safe route.
No motion is sent. For an admissible offline decision, supply measured
`execution_conditions` and independently checked `execution_safety`.

Regression tests: `python -m unittest discover -s tests -v`.

