# EA OS Household Safety Contract v1.0

## 1) Scope
Defines ownership confidence, action gating, triage, replay, and evidence handling.

## 2) Ownership Confidence Bands
- `high` (>= 0.85): user-bound execution allowed for permitted low-risk actions.
- `medium` (0.60-0.84): read-only and draft/stage operations only.
- `low` (< 0.60): blind triage only, no execution side effects.

## 3) Blocked Actions (Fail-Closed)
Blocked regardless of confidence unless explicit future policy enables:
- autonomous payment execution,
- autonomous irreversible deletion,
- autonomous household member sharing/security changes.

## 4) Blind Triage Behavior
When confidence is low:
- classify and queue safely,
- produce minimal user-safe output,
- route to review queue if required,
- never execute external side effects.

## 5) Replay and Dead-Letter
- All denied/failed side-effect intents MUST be replay-safe (idempotency key required).
- Dead-letter records MUST include failure class, source pointer, redacted payload hints.
- Replay requires operator authorization and explicit action.

## 6) Raw Evidence Reveal
- Raw evidence access is claim-based and time-limited.
- Reveals MUST be logged with actor, reason, correlation id.
- Default mode is redacted pointer-first access.

## 7) Required Audit Fields
- actor id (or system),
- tenant,
- action type,
- confidence band,
- policy decision,
- correlation id,
- reference pointers (not raw secrets).

## 8) Acceptance Criteria
- Unsafe side effects are blocked at low/medium confidence.
- Fail-closed behavior on policy engine errors.
- Replay does not duplicate side effects.
- Every reveal/review action is auditable.

