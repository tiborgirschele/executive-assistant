# Environment Matrix

## Core Variables

- `EA_STORAGE_BACKEND`:
  - `memory` -> in-process repositories only
  - `postgres` -> force Postgres repositories
  - `auto` -> try Postgres, fallback to memory
- `EA_LEDGER_BACKEND`: deprecated compatibility alias for `EA_STORAGE_BACKEND`
- `DATABASE_URL`: required for reliable Postgres-backed operation
- `EA_BOOTSTRAP_DB=1`: optional deploy-time migration bootstrap

## Recommended Profiles

| Environment | EA_STORAGE_BACKEND | DATABASE_URL | EA_BOOTSTRAP_DB | Rationale |
|---|---|---|---|---|
| Local quick dev | `memory` | optional | `0` | Fast startup, no DB dependency |
| Local integration | `postgres` | required | `1` | Validate DB-backed runtime behavior |
| CI smoke | `memory` | unset | `0` | Deterministic and lightweight |
| CI integration | `postgres` | required | `1` | Exercises migrations and DB backends |
| Staging | `postgres` | required | `1` (initial), `0` (steady state) | Closest to production |
| Production | `postgres` | required | controlled rollout only | Avoid silent fallback and enforce durability |

## Guardrails

- Prefer `EA_STORAGE_BACKEND`; use `EA_LEDGER_BACKEND` only for temporary compatibility with older env files.
- For production/staging, prefer `EA_STORAGE_BACKEND=postgres` instead of `auto`.
- Use `auto` only where memory fallback is acceptable.
- Run `scripts/db_status.sh` after bootstrap to verify kernel table presence.
