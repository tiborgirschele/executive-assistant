# EA OS Minimal Operator Surface Spec v1.0

## 1) Goal
Define the smallest safe operator control surface required for v1.12.x operations.

## 2) Included Capabilities Only
- Review Queue
- Connector Auth Repair
- Dead-Letter Queue (DLQ)
- Circuit Breaker Status
- Egress Audit Lookup
- Replay/Retry Action

No additional broad admin UI is in scope.

## 3) Roles
- `operator`: can review, claim, replay, retry, and open/close bounded remediation actions.
- `viewer`: read-only audit/status access.

## 4) Functional Modules

### 4.1 Review Queue
- List pending review items by tenant/status/age.
- Claim item with TTL-bound claim token.
- Record decision (`approve|reject|needs_info`) with reason.

### 4.2 Connector Auth Repair
- Show connector auth status and last failure.
- Trigger re-auth flow issuance.
- Confirm auth recovery and clear related breaker when policy allows.

### 4.3 DLQ
- List dead-letter items by source/failure class.
- View redacted payload hints and source pointers.
- Replay one item with idempotency protection.

### 4.4 Circuit Breakers
- List open/half-open breakers with TTL and failure stats.
- Manual close is allowed only with reason and actor audit.

### 4.5 Egress Audit Lookup
- Query by tenant, correlation id, model/provider, time range.
- Display sanitizer/validator outcomes.

### 4.6 Replay/Retry
- Retry is allowed for retryable classes only.
- Non-retryable classes require explicit override reason and are still policy-checked.

## 5) Security Constraints
- Every write action requires operator auth token and actor identity.
- All actions must emit audit events.
- No raw-secret display in UI.

## 6) Acceptance Criteria
- Operator can resolve the common failure loop without shell access.
- Unsafe retries are blocked by policy checks.
- Every operator action is fully auditable.

