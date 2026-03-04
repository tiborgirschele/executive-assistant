# EA OS v1.19 Design: Future Intelligence Care OS

## Purpose

v1.19 extends the v1.13 profile-intelligence baseline into a care-oriented
contract that prioritizes expensive commitments, risk intersections, and runtime
confidence before standard briefing composition.

The target behavior is:

1. detect high-exposure commitments (for example travel bookings),
2. detect risk intersections (for example layovers in risk regions),
3. compute readiness and deterministic critical actions,
4. choose a safe briefing mode when runtime confidence is degraded.

## Contract surface

v1.19 continues to use the existing intelligence modules and tightens their
expected behavior:

- `app.intelligence.profile.build_profile_context`
- `app.intelligence.dossiers.build_trip_dossier`
- `app.intelligence.future_situations.build_future_situations`
- `app.intelligence.readiness.build_readiness_dossier`
- `app.intelligence.critical_lane.build_critical_actions`
- `app.intelligence.preparation_planner.build_preparation_plan`
- `app.intelligence.modes.select_briefing_mode`
- `app.intelligence.household_graph.ensure_profile_isolation`

## Key invariants

- Currency extraction must capture high-value commitments from natural text
  formats such as `EUR 15,000`.
- Travel-risk detection must treat known risky layover hints as first-class
  risk signals.
- Future situations must still emit `travel_window` for high-exposure/risky
  travel dossiers even if schedule metadata is partial.
- Confidence-aware mode selection must never regress:
  degraded runtime confidence can switch compose mode to low-confidence.
- Preparation plans remain bounded and must not invent high-risk autonomous
  actions (for example direct payments/wire transfers).

## Test enforcement

The incoming v1.19 pack is mirrored in-repo under:

- `tests/_incoming_v119/`
- `tests/run_incoming_v119_pack.py`
- `tests/smoke_v1_19_future_intelligence_pack.py`

Gate wiring:

- `scripts/run_v119_smoke.sh`
- `scripts/release_v119_future_intelligence_care_os.sh`
- `scripts/docker_e2e.sh` (`smoke_v1_19_future_intelligence_pack` step)

## Rollout

1. Run `bash scripts/run_v119_smoke.sh` for host + contract validation.
2. Run `bash scripts/docker_e2e.sh` for full integration gates.
3. Use guarded rollout flags in production until travel/risk false-positive
   rates are reviewed with real traffic.
