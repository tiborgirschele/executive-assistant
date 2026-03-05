# EA OS (Assistant Runtime)

EA OS is a Telegram-first assistant runtime with:
- multi-service deployment roles (`ea-api`, `ea-poller`, `ea-worker`, `ea-outbox`, `ea-event-worker`, `ea-teable-sync`)
- secured ingest/debug boundaries (`EA_INGEST_TOKEN`, `EA_OPERATOR_TOKEN`)
- BrowserAct/MetaSurvey/AvoMap intake and sidecar wiring
- capability + skill registries for controlled sidecar/tool routing
- milestone-gated smoke + Docker E2E release checks from v1.12.x through v1.21.x

This repo started as a patched deployment bundle, but current `main` is maintained as a staged assistant-OS codebase with explicit contract gates.

## Quick start

1) Copy this folder to `/docker/EA` on your VPS.
2) Create `.env` from `.env.example` and fill in secrets.
3) Edit `config/tenants.yml` and `config/places.yml` with your local tenant/chat/location data.
   Do not commit personal addresses, chat IDs, or geolocation coordinates.
4) Deploy:

```bash
cd /docker/EA
bash scripts/deploy.sh
```

## Smoke tests

```bash
bash scripts/smoke.sh
bash scripts/runbook.sh
bash scripts/docker_e2e.sh
bash scripts/docker_e2e_design_workflows.sh
bash scripts/run_v113_smoke.sh
bash scripts/run_v119_smoke.sh
bash scripts/run_v120_smoke.sh
```

Milestone release scripts (`scripts/release_v113_onboarding.sh` through
`scripts/release_v119_future_intelligence_care_os.sh`) run full docker gates by default
after their milestone-specific checks. Set `EA_SKIP_FULL_GATES=1` to skip the
final full-gate step.

Gate reports are written to `logs/gates/*.json` and uploaded by CI.
`scripts/docker_e2e.sh` includes the real milestone functional suite as part of design E2E.

## Design docs

- Contract stabilization baseline: `docs/v1_12_7_contract_freeze.md`
- v1.13 profile intelligence core: `docs/EA_OS_Design_v1_13_Profile_Intelligence_Core.md`
- v1.14 epics and trust: `docs/EA_OS_Design_v1_14_Epics_and_Trust.md`
- v1.19 future intelligence care OS: `docs/EA_OS_Design_v1_19_Future_Intelligence_Care_OS.md`
- v1.19.1 patch memo: `docs/EA_OS_v1_19_1_Patch_Memo.md`
- v1.20 commitment OS foundations: `docs/EA_OS_Change_Guide_for_Dev_v1_20_Commitment_OS.md`
- v1.21 task-first contract seed: `docs/EA_OS_Change_Guide_for_Dev_v1_21_Task_Contracts.md`
- Teable curated-memory model: `docs/EA_OS_Teable_Memory_Model.md`
- Product roadmap: `docs/ea_os_design_roadmap_v2026.md`
- Auditor LTD/tier inventory: `LTD_INVENTORY.md`
- Change guide (this rollout state): `docs/EA_OS_Change_Guide_for_Dev_v1_12_7.md`
- v1.19 change guide: `docs/EA_OS_Change_Guide_for_Dev_v1_19_Future_Intelligence_Care_OS.md`

## Notes
- The EA container joins the existing `openclaw-net` network to reach LiteLLM and to exec into OpenClaw containers via docker socket.
- If you run rootless Docker, set `DOCKER_SOCK=/run/user/<uid>/docker.sock` in `.env`.
- Default bootstrap admin creation is disabled unless `EA_ALLOW_BOOTSTRAP_ADMIN=true` is explicitly set.
- You can override generic OpenClaw fallback container names with `EA_DEFAULT_OPENCLAW_CONTAINER`.
- `scripts/runbook.sh` scans EA services by default; set `EA_SCAN_ALL_CONTAINERS=1` for cross-stack scan.
