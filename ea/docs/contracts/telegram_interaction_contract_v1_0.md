# EA OS Telegram Interaction Contract v1.0

## 1) Scope
Defines user-visible Telegram interaction behavior for v1.12.x.

## 2) Message Types
- `primary_briefing`: required, text-first.
- `system_card`: bounded diagnostic card for degraded mode.
- `follow_up`: optional enhancement (for example late sidecar result).

## 3) Section Budget Rules
- `primary_briefing` MUST fit into one Telegram message.
- Total text target: <= 3500 chars.
- Hard fail cap: 3900 chars; content must be trimmed before enqueue.
- Priority order for trimming:
  1. optional diagnostics
  2. low-priority noise summaries
  3. tertiary links
  4. never trim critical actions or blockers

## 4) Button Semantics
- Buttons MUST map to a command contract (`/api/commands` or callback token action family).
- Callback tokens MUST be:
  - single-use,
  - TTL-bound,
  - bound to intended user and chat.
- Expired/invalid callbacks MUST return safe user copy and no side effects.

## 5) Edit vs Follow-Up Rules
- If enhancing the same logical message within the enhancement window:
  - prefer `edit_message_text` or `edit_message_reply_markup`.
- If edit fails or window is closed:
  - send one bounded `follow_up`.
- Same enhancement MUST NOT deliver more than once.

## 6) System Card Rules
- System cards are permitted only for:
  - degraded mode explanation,
  - transient service failure explanation,
  - operator-safe escalation reference.
- System cards MUST NOT expose secrets, raw stack traces, or unsafe internals.

## 7) Degraded Mode Copy
Degraded copy MUST:
- confirm core outcome first,
- explain optional feature degradation briefly,
- provide one next action (retry/passive wait/operator route).

## 8) AI Error vs Noise
- `AI Error`:
  - model or validator failure affecting quality/path.
  - MUST emit bounded audit event and safe user copy.
- `Noise`:
  - low-value or non-actionable signal.
  - MUST be silently deprioritized; no alarm copy.

## 9) Acceptance Criteria
- No duplicate callback action execution.
- No double follow-up for same correlation id.
- No broken HTML payload sent to Telegram.
- Primary briefing always sent even when optional sidecars fail.

