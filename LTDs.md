# LTDs

Workspace-scoped inventory of discovered lifetime services with API keys or account-backed access.

## Tier Guide

- `Tier 1`: actively wired into the local workspace/runtime and ready for operational use
- `Tier 2`: account or key exists, but local runtime wiring is partial or parked
- `Tier 3`: known service/account placeholder with no active local integration yet

## Inventory

| Service | Tier | Access Model | Local Integration | Description |
|---|---|---|---|---|
| `1min.AI` | `Tier 1` | API key | Local `.env` key rotation slots: `ONEMIN_AI_API_KEY` and `ONEMIN_AI_API_KEY_FALLBACK_1` | Lifetime AI service access for model/API usage. The workspace now reserves a primary slot and a protected fallback key slot in the gitignored `.env`, plus `scripts/resolve_onemin_ai_key.sh` for local key-resolution order. |

## Notes

- This file reflects LTDs discoverable from the current workspace and local repo configuration.
- The Codex session skill list is not used as the LTD source of truth; skills are local agent capabilities, while this file tracks external services/accounts with keys or logins.
- No additional AI-service LTDs are listed until they are concretely discoverable from local config, tracked docs, or local-only secret wiring.
- Secrets are intentionally omitted here; only the service inventory and local integration contract are documented.
