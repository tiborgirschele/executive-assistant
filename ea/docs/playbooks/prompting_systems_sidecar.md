# Prompting Systems BrowserAct Playbook (Patch R2)

**Status:** Optional Sidecar (Non-Blocking)
**Job Type:** `browseract.prompting_systems.generate`

## Execution Rules
1. Never use in critical path (payments, approvals, auth).
2. EA OS generates a BrowserAct job to navigate to Prompting Systems.
3. BrowserAct submits context, captures the generated prompt.
4. Output is saved as an artifact.
5. **HUMAN REVIEW REQUIRED:** A human must approve the prompt artifact before it is inserted into the template registry or Documentation.AI.
