# Environment Matrix

## Core Variables

- `EA_RUNTIME_MODE`:
  - `dev` -> local-default ergonomics; memory fallback allowed
  - `test` -> CI/test ergonomics; memory fallback allowed
  - `prod` -> fail fast if durable Postgres boot is not available
- `EA_STORAGE_BACKEND`:
  - `memory` -> in-process repositories only
  - `postgres` -> force Postgres repositories
  - `auto` -> try Postgres, fallback to memory outside `prod`
- `EA_LEDGER_BACKEND`: deprecated compatibility alias for `EA_STORAGE_BACKEND`
- `DATABASE_URL`: required for reliable Postgres-backed operation
- `EA_DEFAULT_PRINCIPAL_ID`: fallback request principal for principal-scoped connector/memory routes when `X-EA-Principal-ID` is omitted
- `EA_BOOTSTRAP_DB=1`: optional deploy-time migration bootstrap

## Recommended Profiles

| Environment | EA_STORAGE_BACKEND | DATABASE_URL | EA_BOOTSTRAP_DB | Rationale |
|---|---|---|---|---|
| Local quick dev | `memory` | optional | `0` | Fast startup, no DB dependency |
| Local integration | `postgres` | required | `1` | Validate DB-backed runtime behavior |
| CI smoke | `memory` | unset | `0` | Deterministic and lightweight |
| CI integration | `postgres` | required | `1` | Exercises migrations and DB backends |
| Staging | `postgres` | required | `1` (initial), `0` (steady state) | Closest to production |
| Production | `postgres` | required | controlled rollout only | Avoid silent fallback and enforce durability (`EA_RUNTIME_MODE=prod`) |

## Guardrails

- Prefer `EA_STORAGE_BACKEND`; use `EA_LEDGER_BACKEND` only for temporary compatibility with older env files.
- Set `EA_RUNTIME_MODE=prod` for production-like boots so missing/unavailable Postgres fails fast instead of degrading to memory.
- For production/staging, use `EA_STORAGE_BACKEND=postgres` instead of `auto`.
- Use `auto` only where memory fallback is acceptable.
- Run `scripts/db_status.sh` after bootstrap to verify kernel table presence.
