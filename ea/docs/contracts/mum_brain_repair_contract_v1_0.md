# EA OS Mum Brain Repair Contract v1.0

## 1) Scope
Defines bounded repair behavior for v1.12.x failure handling.

## 2) Principles
- Inline fallback first.
- Repair is bounded by time and attempts.
- Optional feature failures must not block primary user outcome.
- All repair paths are auditable.

## 3) Failure Classes
- `render_transient`: renderer timeout/5xx on optional visuals.
- `render_contract`: malformed renderer payload/validation failure.
- `llm_transient`: gateway timeout/rate-limit.
- `llm_contract`: output validation failure.
- `connector_auth`: token expired/revoked.
- `connector_data`: malformed source payload.
- `policy_block`: household safety denied action.
- `infra_transient`: short-lived infrastructure fault.
- `infra_persistent`: repeated fault opening breaker.

## 4) Handling Matrix
- `render_transient`:
  - MUST send primary text output.
  - MAY enqueue bounded optional retry.
- `render_contract`:
  - MUST skip retry.
  - MUST emit system card only if user-visible feature requested.
- `llm_transient`:
  - MUST fall back to deterministic/minimal response template.
- `llm_contract`:
  - MUST reject output; MUST NOT emit unsafe/invalid content.
- `connector_auth`:
  - MUST fail closed and issue re-auth action.
- `policy_block`:
  - MUST fail closed with safe user copy.
- `infra_persistent`:
  - MUST open breaker and suppress repeated expensive retries.

## 5) Budgets
- Max repair wall time per request: 8 seconds.
- Max optional repair attempts per correlation id: 2.
- Max concurrent repair jobs per tenant: 3.
- Breaker open TTL default: 6 hours.

## 6) Retry and Breakers
- Retries are allowed only for transient classes.
- Contract/policy failures are non-retryable.
- Breakers open on thresholded repeated failures by `(tenant, component, failure_class)`.
- Breakers suppress optional paths first; core path remains available.

## 7) Audit Events (Required)
Each repair action MUST emit:
- `correlation_id`
- `tenant`
- `failure_class`
- `decision` (`fallback|retry|suppress|breaker_open`)
- `attempt_count`
- `duration_ms`
- `user_visible` boolean

## 8) Acceptance Criteria
- No infinite retry loops.
- No optional failure blocks primary response.
- Breakers suppress repeated flapping failures.
- Policy-blocked actions never execute side effects.

