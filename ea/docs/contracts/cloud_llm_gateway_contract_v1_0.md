# EA OS Cloud LLM Gateway Contract v1.0

## 1) Scope
Defines safe external model usage for all cloud LLM calls.

## 2) Allowed Inputs
Gateway payload may include only:
- normalized task prompt,
- bounded context excerpts,
- redacted metadata tags,
- correlation id.

## 3) Forbidden Fields
Never send externally:
- raw auth tokens, API secrets, private keys,
- unredacted household PII where not required,
- raw evidence blobs,
- full callback tokens,
- internal operator-only annotations.

## 4) Redaction Rules
- Replace direct identifiers with stable placeholders where possible.
- Trim payloads to minimum fields needed for requested task.
- Enforce deterministic pre-egress sanitizer pass.

## 5) Output Validation Classes
- `schema_invalid`: reject.
- `policy_invalid`: reject.
- `unsafe_content`: reject.
- `acceptable`: pass.

Rejected outputs MUST trigger bounded fallback behavior.

## 6) Routing Policy
- Model selection MUST be policy-driven and deterministic by task class.
- High-risk tasks use stricter validators and lower temperature.
- Optional decorative tasks are suppressible under degradation.

## 7) Egress Audit Schema
Each call MUST log:
- `tenant`
- `correlation_id`
- `provider`
- `model`
- `task_class`
- `input_tokens` / `output_tokens` (if available)
- `sanitizer_version`
- `validator_result`
- `duration_ms`

## 8) Non-Negotiable Rule
If sanitizer or validator fails, the request MUST fail closed and use deterministic fallback.

## 9) Acceptance Criteria
- No forbidden fields appear in egress payload snapshots.
- Validator rejects malformed or policy-breaking model output.
- Every egress call is queryable via audit lookup.

