# EA OS v1.13 Actionable Briefings Design

## 1) Objective
Expand from read-only briefings to safe, bounded read-write actions.

## 2) Guiding Rules
- Safe actions first.
- No autonomous high-risk side effects.
- Household safety and Mum Brain supervision apply to every action path.
- Actions are staged/drafted unless explicitly approved.

## 3) In-Scope Action Set (v1.13)
- Draft email reply.
- Save task/reminder draft.
- Trigger connector re-auth flow.
- Stage approval request.
- Suggest calendar action draft.
- Trigger optional travel video action.
- Ask one high-value follow-up question when required context is missing.

## 4) Out of Scope (Blocked)
- Automatic payments.
- Autonomous calendar rewrites without confirmation.
- Autonomous household sharing/security modifications.

## 5) UX Contract
- Every action card includes:
  - `why this matters`,
  - `proposed action`,
  - `one-tap safe options` (`approve draft`, `edit`, `dismiss`).
- If confidence is low:
  - provide triage option only, no side-effect option.

## 6) Execution Contract
- Every action carries:
  - correlation id,
  - idempotency key,
  - policy class,
  - required confidence band.
- Execution path:
  1. policy check,
  2. output validation,
  3. side-effect execution (if allowed),
  4. audit write.

## 7) Failure Behavior
- If action generation fails: fallback to concise text guidance.
- If execution fails: keep draft state, show retry/stage options.
- No silent destructive failure.

## 8) Test Gate
Mandatory acceptance tests:
1. safe actions can be created and executed with audit trail.
2. blocked actions remain blocked with fail-closed behavior.
3. low-confidence path only offers triage/draft behaviors.
4. duplicate callbacks do not duplicate side effects.
5. degraded LLM path still yields deterministic user guidance.

## 9) Rollout
- Tenant feature flag: `ACTIONABLE_BRIEFINGS_ENABLED`.
- Canary on internal tenants first.
- Promote only after runbook and operator workflows are green.

