# EA OS v1.14 Design: Epics and Trust

Date: 2026-03-04  
Status: Implementation in progress

## Design Sentence
v1.14 turns profile intelligence into narrative intelligence by introducing
typed epics with unresolved-state tracking and salience-aware prioritization.

## Why
`mail + calendar + dossier` intelligence remains event-centric. The assistant
needs a long-running thread layer so it can describe what changed, what remains
open, and what deserves top attention now.

## Contracts

### Epic Contract
File: `ea/app/intelligence/epics.py`

- `Epic`: typed narrative object (`epic_id`, `kind`, `status`, `salience`,
  `unresolved_count`, `summary`, `evidence`).
- `build_epics_from_dossiers(profile, dossiers)`: derive epics from dossiers.
- `rank_epics(epics)`: deterministic ordering by salience and unresolved state.
- `summarize_epic_deltas(previous, current)`: human-readable change deltas.
- `load_epic_snapshot(path)` / `save_epic_snapshot(path, epics)`: minimal local
  persistence for delta computation across briefing runs.

### Mode Contract Extension
File: `ea/app/intelligence/modes.py`

- `select_briefing_mode(...)` now accepts optional `epics`.
- High epic salience can promote compose mode into risk mode.
- New mode label: `Epic Focus Mode`.

## Runtime Wiring
File: `ea/app/briefings.py`

Briefing compose now:
1. Builds profile context and dossier(s).
2. Runs deterministic critical lane.
3. Builds epics from dossiers.
4. Computes epic deltas against prior snapshot.
5. Persists latest epic snapshot.
6. Renders:
   - `Immediate Action`
   - `Active Epics`
   - `Epic Deltas`
   before the LLM-composed email/calendar sections.

## Invariants
1. Epic ranking is deterministic.
2. Deltas must compare previous and current snapshots.
3. Epic salience can influence mode selection.
4. Epic state never bypasses profile isolation boundaries.

## Tests
`tests/smoke_v1_14.py` now asserts:
- v1.14 trust/replay schema and module parse.
- epic contract symbols and snapshot functions exist.
- briefing wiring includes epic build/rank/delta and visible sections.

## Next
1. Add multi-domain dossier builders (health/finance/project).
2. Link epics to typed action packs.
3. Introduce durable epic store (DB-backed) after contract freeze period.
