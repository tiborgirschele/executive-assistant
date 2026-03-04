# EA OS v1.19.1 Patch Memo

Date: 2026-03-04

## Purpose

Translate the v1.19 audit/design feedback into a concrete patch sequence against the
current repo with low-risk, test-backed increments.

This memo is intentionally implementation-led: each section maps to specific files,
expected SQL deltas, and gate coverage.

## Scope of this patch wave

1. Prevent duplicate `/brief` deliveries caused by near-simultaneous triggers.
2. Harden sentinel watchdog timing to reduce false deadlock restarts.
3. Expand future-intelligence beyond travel with project + finance commitment seams.
4. Keep runbook output operationally actionable (reduce expected-noise dominance).

## Implemented in this repo state

### A. `/brief` duplicate-request guard

Files:
- `ea/app/poll_listener.py`
- `tests/smoke_brief_dedupe_guard.py`
- `tests/smoke_v1_18_1_runtime_alignment.py`
- `scripts/docker_e2e.sh`

Behavior:
- in-flight per-chat lock (`_brief_enter/_brief_exit`)
- persisted short-window dedupe (`.brief_last_command.json`)
- configurable window: `EA_BRIEF_COMMAND_MIN_INTERVAL_SEC` (default `120`)

### B. Sentinel watchdog reliability hardening

Files:
- `ea/app/poll_listener.py`
- `tests/smoke_sentinel_user_message.py`
- `tests/smoke_v1_18_1_runtime_alignment.py`

Behavior:
- monotonic heartbeat source (`time.monotonic()`)
- startup grace to avoid boot false positives
- configurable timeout / exit behavior:
  - `EA_SENTINEL_HEARTBEAT_TIMEOUT_SEC`
  - `EA_SENTINEL_STARTUP_GRACE_SEC`
  - `EA_SENTINEL_EXIT_ON_STALL`

### C. Future-intelligence expansion (non-travel seams)

Files:
- `ea/app/intelligence/dossiers.py`
- `ea/app/intelligence/future_situations.py`
- `ea/app/intelligence/readiness.py`
- `ea/app/intelligence/critical_lane.py`
- `ea/app/intelligence/scores.py`
- `tests/smoke_v1_19_1_future_intelligence_expansion.py`
- `scripts/run_v119_smoke.sh`
- `scripts/docker_e2e.sh`
- `.github/workflows/release-gates.yml`

Behavior:
- added dossier builders:
  - `build_project_dossier`
  - `build_finance_commitment_dossier`
- new future situation kinds:
  - `meeting_prep_window`
  - `deadline_window`
- readiness and critical-lane now handle project/finance dossier signals
- score model expanded beyond trip-only branch

### D. Runbook output quality

Files:
- `scripts/runbook.sh`

Behavior:
- filtered DB-log mode by default (`EA_DB_LOG_MODE=filtered`)
- configurable DB log filter pattern / tail size
- expected idempotency duplicate noise no longer dominates the runbook output

## Proposed SQL additions (next patch)

No SQL migration was required for the changes above, but v1.19.1 should include
new persistence surfaces in the next schema increment.

Proposed migration file: `ea/schema/20260304_v1_19_1_intelligence_expansion.sql`

Suggested tables:

1. `profile_snapshots`
- `snapshot_id uuid pk`
- `tenant_key text`
- `person_id text`
- `stable_json jsonb`
- `situational_json jsonb`
- `learned_json jsonb`
- `confidence_json jsonb`
- `created_at timestamptz`
- unique `(tenant_key, person_id, created_at)`

2. `dossier_snapshots`
- `dossier_id uuid pk`
- `tenant_key text`
- `person_id text`
- `kind text` (`trip`, `project`, `finance_commitment`, ...)
- `status text`
- `payload_json jsonb`
- `evidence_json jsonb`
- `created_at timestamptz`
- index `(tenant_key, person_id, kind, created_at desc)`

3. `future_situation_snapshots`
- `situation_id uuid pk`
- `tenant_key text`
- `person_id text`
- `kind text`
- `horizon_hours int`
- `confidence numeric`
- `evidence_json jsonb`
- `created_at timestamptz`

4. `readiness_snapshots`
- `readiness_id uuid pk`
- `tenant_key text`
- `person_id text`
- `status text`
- `score int`
- `payload_json jsonb`
- `created_at timestamptz`

## Test mapping

### Host smokes

- `tests/smoke_sentinel_user_message.py`
  - sentinel user copy and throttle contracts
  - no internal deadlock phrasing leakage

- `tests/smoke_brief_dedupe_guard.py`
  - `/brief` in-flight + dedupe contract

- `tests/smoke_v1_18_1_runtime_alignment.py`
  - runtime alignment symbols + watchdog/brief dedupe knobs

- `tests/smoke_v1_19_future_intelligence_pack.py`
  - incoming v1.19 contract pack baseline

- `tests/smoke_v1_19_1_future_intelligence_expansion.py`
  - project/finance dossier + future/readiness/critical behavior

### End-to-end gates

- `scripts/docker_e2e.sh`
  - now includes the new v1.19.1 smoke step

- `tests/real_milestone_suite.py`
  - continues validating full staged milestone path through v1.19 + v1.12.6 chain

## Remaining gaps after v1.19.1

1. De-minify core control-plane files (`main.py`, `supervisor.py`, `briefings.py`, `scheduler.py`).
2. Persist profile/dossier/future/readiness snapshots in DB (schema above).
3. Add missingness engine for "expected-but-missing" commitments.
4. Expand dossier set with health/household ops/evidence-first dossier types.
5. Strengthen LLM gateway from adapter to full trust-boundary implementation.

## Release checklist

1. `python3 tests/smoke_v1_19_future_intelligence_pack.py`
2. `python3 tests/smoke_v1_19_1_future_intelligence_expansion.py`
3. `python3 tests/smoke_v1_18_1_runtime_alignment.py`
4. `bash scripts/run_v119_smoke.sh /docker/EA`
5. `bash scripts/docker_e2e.sh`

