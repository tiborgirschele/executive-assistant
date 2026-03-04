# EA LTD Inventory (Auditor Reference)

Last updated: 2026-03-04  
Scope: Operator-declared lifetime deals (LTDs) and tier/plan values currently tracked for EA OS.

## Notes
- This is the single auditor-facing LTD/tier inventory for external tooling.
- Tier values are recorded from operator declarations and are not independently verified by runtime.
- Capability keys map to `ea/app/skills/capability_registry.py`.
- Where product naming is uncertain, the assumption is explicitly marked.

## Capability-Backed LTD Inventory

| Product | Tier / Plan | Capability key(s) | EA OS role | Tier status |
|---|---|---|---|---|
| AppSumo Plus | Plus membership | n/a | Procurement channel (not runtime capability) | Declared |
| BrowserAct | Tier 5 | `browseract` | Browser automation ingress and event enrichment | Declared |
| MetaSurvey | 4 codes | `metasurvey` | Structured intake and feedback collection | Declared |
| Vizologi | Tier 4 | `vizologi` | Secondary research and strategy support | Declared |
| PeekShot | Tier 3 | `peekshot` | Multimodal support asset generation | Declared |
| Paperguide | Tier 4 | `paperguide` | Secondary research support | Declared |
| ApproveThis | Tier 3 | `approvethis` | Approval routing and typed-safe-action support | Declared |
| AvoMap | Tier 10 | `avomap` | Travel route/video sidecar and trip context support | Declared |
| Prompting.Systems | Tier not specified | `prompting_systems` | Prompt pack compilation | Unspecified tier |
| Undetectable / Humanizer AI | Tier not specified | `undetectable` | Tone polishing for approved outbound copy | Unspecified tier |
| ApiX-Drive | Highest tier | `apix_drive` | External event/action bridge via connectors/webhooks | Declared |
| Involvness (assumed involve.me) | Tier not verified | `involve_me` | Guided external intake front-end | Assumed product |
| OneAir Elite | Elite | `oneair` | Travel savings/reprice optimization | Declared |
| Magix AI / AI Magicx | Highest tier | `ai_magicx` | Secondary AI workbench / multimodal support | Declared |
| 1minAI | Highest tier | `one_min_ai` | Multimodal burst support | Declared |

## Runtime Dependencies (Not LTD Tiered)

These are runtime-side dependencies referenced by code/deployment and intentionally tracked separate from LTD tiers.

| Dependency | Type | Tier tracked here |
|---|---|---|
| OpenClaw container runtime | Execution/runtime dependency | No |
| LiteLLM route/provider gateway | Execution/runtime dependency | No |
| Paperless connector | Connector dependency | No |
| Immich connector | Connector dependency | No |
| OneDrive Folder connector | Connector dependency | No |

## Auditor checks
- Verify every listed capability key exists in `CAPABILITY_REGISTRY`.
- Verify skill routing uses capability keys (provider names stay behind contracts).
- Verify assumed or unspecified tiers are resolved before production-critical usage.
- Verify runtime dependencies are not misclassified as LTD-tier contracts.
