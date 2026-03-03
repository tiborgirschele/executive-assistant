# EA OS v1.12.6-a Implementation Patch Memo

## 1) Purpose
Close the v1.12.3-v1.12.6 design line as a stable implementation baseline.

This memo is normative for patch acceptance and release gating.

## 2) Stabilization Spine (Frozen)
The system baseline is:

- Telegram-first interaction model.
- Mum Brain supervision and bounded repair.
- Inline fallback first; optional enhancements never block primary delivery.
- Cloud-only LLM gateway.
- Fail-closed household safety gating.
- Minimal operator surface.
- AvoMap as optional sidecar, never as architecture center.

Any divergence from this spine requires an explicit design decision memo.

## 3) Scope
In scope:

- Contract precision and release gates for v1.12.x behavior.
- Stable runtime behavior under connector outages and renderer failures.
- Consistent operator and audit semantics.
- Stable AvoMap trigger/budget/caching/late-attach behavior.

Out of scope:

- New large architecture moves.
- Autonomous high-risk actions.
- Large operator portal expansion.

## 4) Required Patch Set

### 4.1 Runtime and Schema
- Required tables must exist and be bootstrapped:
  - `travel_place_history`
  - `travel_video_specs`
  - `avomap_jobs`
  - `avomap_assets`
  - `avomap_credit_ledger`
- Event-worker ingestion must claim `external_events.status='new'` rows.
- BrowserAct finalize path must be idempotent on repeated completions.

### 4.2 AvoMap Baseline
- AvoMap remains optional (`AVOMAP_ENABLED` guard).
- Candidate planning does not block text briefing.
- Budget enforcement is mandatory:
  - per-person/day cap
  - per-tenant/day cap
- Cache-hit path must not dispatch new BrowserAct work.
- Place history must be recorded on successful finalize, not dispatch.

### 4.3 Security and Safety
- BrowserAct webhook must support cryptographic signature validation.
- Webhook completion must be tied to an expected job token.
- Exported route payload must be sanitized for household OpSec:
  - no raw personal labels
  - home-like coordinates obfuscated before sidecar export
- Cloud LLM usage remains behind sanitization and egress audit policy.

### 4.4 Telegram Delivery Rules
- Text briefing is always primary and on-time.
- Sidecar late-attach remains bounded and optional.
- Oversized media must not crash outbox flow.

## 5) Test Gate (Mandatory)
The baseline is accepted only if all are green:

1. Host smoke for v1.12.6 contracts and modules.
2. Containerized v1.12.6 E2E (candidate -> spec -> browser job -> finalize -> ready asset).
3. Design workflow E2E chain (onboarding, surveys, trust, rag, actions, personalization, planner, mum).
4. Post-live container-log scan with zero EA stack errors in the active window.

## 6) Release Decision
Release is blocked if any of the following occur:

- webhook auth/signature bypass,
- budget/caching regression causing credit drain,
- text briefing blocked by sidecar path,
- duplicate late-attach deliveries,
- fail-open household safety path.

## 7) Change Control
From this point, v1.12.x changes are only:

- contract clarifications,
- defect fixes,
- runbook hardening,
- test coverage extensions.

