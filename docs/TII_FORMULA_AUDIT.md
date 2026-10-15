# TII revision formula-to-code audit (2026-09-28)

This repository is an **offline decision/reference implementation**. It is **not** a
calibrated Franka FR3 + RealSense D435 + gripper runtime and does not send motion.
Do **not** claim that running this code reproduces any of the paper's 1070
physical executions or certifies robot safety.

## Manuscript-to-code mapping

| Manuscript | Code | Contract |
|---|---|---|
| Eq. (2), Table I | `paper_rules.condition_cues` | Exactly zD, zH, zT, zE, zM, zA, zC; raw units in meters/pixels |
| Eq. (3) | `paper_rules.risk_and_tier` | rho = max(z), never sum/mean |
| Eq. (4) | `paper_rules.risk_and_tier` | low < 0.50, mid 0.50-<0.70, high >=0.70 |
| Table II | `paper_rules.PROFILES` | fixed low = M1/M2; routed tier = M3 |
| Eq. (5), Table III | `paper_rules.gated_reasons` | independent hard abort before attempting execution |
| Post-hoc sensitivity | `paper_rules.replay_tiers` | recomputes tiers ONLY, does not fabricate real successes |

**Table I raw input** must be present in
`observation.execution_conditions`: `invalid_depth_fraction` (0..1),
`depth_std_m`, `object_height_m`, `grasp_table_clearance_m`,
`object_table_clearance_m`, `edge_distance_px`,
`opening_margin_m` (gripper opening minus estimated thickness),
`contact_area_m2` (pre-execution finger-face overlap estimate divided
internally by 2.4e-3 m²), `normalized_safety_margins` (dictionary
of calibrated 0..1 margins), and `material` (annotated object-level
`reflectivity` = none/medium/high, `transparent_or_glass`,
`deformable`, `thin_walled`, `annotation_uncertainty` in [0,1]).

`observation.execution_safety` must independently contain a **world-frame**
`grasp_xyz_world_m`, `minimum_grasp_height_margin_m`, `tilt_deg`,
`required_rotation_deg`, `pregrasp_lateral_offset_m`,
`semantic_lateral_deviation_m`, `semantic_deviation_px`,
`center_projection_px`, plus explicit booleans
`task_target_preserved`, `anchor_in_target_mask`, `reachable`,
`collision_free_plan_verified`. Merely providing these fields is not
equivalent to independently verifying them with a robot/collision planner.

The depth/geometry producers **must** derive their statistics from the
guarded anchor (30 px local patch) and must invalidate zeros, NaNs,
out-of-workspace depths and samples inconsistent with the table estimate.
A plain image-center fallback and use of XYZ coordinates as pixel UV
were removed because they were not valid GraspMolmo or calibrated camera
outputs.

## Paper-specified vs. not specified

Paper-specified:
- Depth invalid ratio ramps [0.10, 0.45]; valid-depth std [0.006, 0.025] m.
- Object height downward ramp [0.075, 0.140] m.
- Grasp/object table clearances downward ramps [0.028, 0.060] m and
  [0.010, 0.035] m.
- Mask boundary distance downward ramp [0, 30] px.
- Material base 0.20 plus reflectivity 0.20/0.30, transparency 0.25,
  deformability 0.15, thin walls 0.10 and 0.20 times annotation uncertainty.
- Contact cue from opening margin [0.004, 0.018] m and contact-area fraction
  [0.35, 0.75].
- Cartesian stiffness, damping, gripper force and closure speed in Table II.

**Needs the experimental implementation/calibration to reproduce exactly:**
1. The manuscript says zA = 1 - minimum normalized safety margin but does not
   give a unique within-bound margin-normalization formula for each constraint.
   This code requires upstream calibrated normalized margins rather than
   inventing a formula and claiming paper-exact equivalence.
2. The continuous task-preserving guarded projection Pi_g (object/part mask
   interpolation, depth rescue, reachability-aware candidate search) is not
   implemented by this repository's existing candidate re-ranking code.
3. The paper's measured fingertip-overlap contact-area estimator, 30 px depth
   patch evaluator, camera extrinsics/hand-eye transforms and signed frame
   conventions need calibrated hardware inputs, not synthetic examples.
4. The Cartesian waypoint generator, impedance controller, runtime protective
   stops, retraction/recovery and robot/controller interface are not included.
5. Tables I-III should be reconciled against original frozen trial config and
   event logs before claiming reproduction, not tuned to reproduce outcomes.

## Safety and evaluation

If input evidence is missing or malformed, `decide` returns
`abort=True`, `profile=None`, and an explicit error reason. The planner
does not hand over motion commands; `allow_execute` stays false
even for verified-looking dry-run input. A physical controller requires a
separate safety review and experimental qualification.

The sample observation under `examples/` is a legacy dry-run input without
calibrated Table-I/III metadata; it now deliberately produces a **blocked**
decision rather than an invented risk tier.

Run:
```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/run_demo.py --method M3 --output-dir runs/m3_demo
```
Check `execution_plan.json` and `execution_router_output.json` for audit data.
