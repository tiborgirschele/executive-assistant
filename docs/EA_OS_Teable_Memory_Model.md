# EA OS Teable Memory Model

## Positioning
Teable is a **curated memory projection layer** for operator-maintained knowledge.
It is **not** the primary runtime memory store.

## Runtime-local first
The assistant runtime keeps execution-critical memory local (Postgres + attachments):
- execution sessions and step logs
- queue/outbox state
- approval state
- repair/retry state
- transient run artifacts

Teable sync is asynchronous and must never block runtime execution.

## What goes to Teable
- reviewed durable facts
- commitments and dossier notes
- preference/relationship memory approved for long-term use
- vendor/LTD reference data

## What must stay out of Teable
- raw session transcripts
- tool dumps
- stack traces/internal diagnostics
- hidden reasoning payloads

## Provenance requirements
Every promoted memory should carry provenance fields:
- `Source`
- `Confidence`
- `Last Verified`
- `Sensitivity`
- `Sharing Policy`
- `Reviewer`

## Sync behavior
- Source file: `/attachments/brain.json` (configurable).
- Approved candidate source: local `memory_candidates` rows with `review_status='approved'`.
- Sync state: `/attachments/teable_sync_state.json` (configurable).
- API base defaults to `https://app.teable.ai/api`.
- Legacy `app.teable.io` base is normalized to `app.teable.ai`.
- Candidate-id dedupe state is tracked so already-synced approved candidates are not replayed.
