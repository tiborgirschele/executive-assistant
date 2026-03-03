# EA OS Runbook Behavior Contract v1.0

## 1) Scope
Operational behavior contract for recurring failure scenarios.

Each scenario defines:
- trigger,
- expected system behavior,
- user-visible result,
- operator action.

## 2) Scenarios

### 2.1 Cloud LLM Outage
- Trigger: gateway timeout/rate-limit/provider auth error.
- Expected behavior:
  - deterministic fallback response,
  - no unsafe partial AI output.
- User result: concise degraded-mode response.
- Operator action: inspect egress audit and provider breaker state.

### 2.2 Renderer Failure Day
- Trigger: repeated renderer 5xx/timeouts.
- Expected behavior:
  - primary text briefing unaffected,
  - optional renderer path suppressed by breaker.
- User result: text-only briefing; optional visual omitted.
- Operator action: inspect breaker, confirm suppression, retry only after recovery.

### 2.3 Google Token Expiry
- Trigger: connector auth failure class `connector_auth`.
- Expected behavior:
  - fail closed for protected reads/actions,
  - issue re-auth flow prompt.
- User result: explicit re-auth prompt with no hidden retries.
- Operator action: track connector auth repair queue to completion.

### 2.4 BrowserAct Source Failure
- Trigger: repeated BrowserAct completion failures/timeouts.
- Expected behavior:
  - sidecar retries bounded,
  - job timeout marked failed and auditable.
- User result: core briefing delivered without sidecar attachment.
- Operator action: inspect failed jobs and breaker status; replay only retryable items.

### 2.5 AvoMap Credit Exhaustion
- Trigger: tenant/person budget caps reached.
- Expected behavior:
  - dispatch suppressed,
  - no crash/no repeated enqueue.
- User result: text-only path, no noisy error card.
- Operator action: verify ledger counters and daily reset behavior.

### 2.6 Prompt Injection Attempt
- Trigger: validator/policy flags unsafe prompt/output pattern.
- Expected behavior:
  - reject unsafe output,
  - fall back to safe template path.
- User result: normal safe response without leaked prompt internals.
- Operator action: review audit trail and source evidence pointers.

### 2.7 Dead-Letter Replay
- Trigger: operator invokes replay for DLQ item.
- Expected behavior:
  - idempotent replay path,
  - policy and confidence re-check at replay time.
- User result: either resolved action or bounded failure note.
- Operator action: capture replay decision reason and outcome.

### 2.8 Stale Source-Pool Fallback
- Trigger: primary source pool misses freshness SLO.
- Expected behavior:
  - stale fallback allowed only within configured safety window,
  - stale marker included in internal audit.
- User result: stable response with optional freshness caveat.
- Operator action: investigate upstream freshness lag.

## 3) Acceptance Criteria
- All scenarios have deterministic system and user outcomes.
- No scenario requires shell access for routine recovery.
- Every scenario yields auditable event records.

