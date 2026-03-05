BEGIN;

ALTER TABLE IF EXISTS execution_sessions
    ADD COLUMN IF NOT EXISTS task_type TEXT NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS execution_sessions
    ADD COLUMN IF NOT EXISTS task_contract_key TEXT NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS execution_sessions
    ADD COLUMN IF NOT EXISTS approval_state TEXT NOT NULL DEFAULT 'none';
ALTER TABLE IF EXISTS execution_sessions
    ADD COLUMN IF NOT EXISTS risk_class TEXT NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS execution_sessions
    ADD COLUMN IF NOT EXISTS budget_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS execution_sessions
    ADD COLUMN IF NOT EXISTS parent_session_id UUID;
ALTER TABLE IF EXISTS execution_sessions
    ADD COLUMN IF NOT EXISTS session_class TEXT NOT NULL DEFAULT 'primary';
ALTER TABLE IF EXISTS execution_sessions
    ADD COLUMN IF NOT EXISTS commitment_key TEXT;

CREATE INDEX IF NOT EXISTS idx_execution_sessions_task
    ON execution_sessions(tenant, task_type, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_sessions_parent
    ON execution_sessions(parent_session_id, created_at DESC);

ALTER TABLE IF EXISTS execution_steps
    ADD COLUMN IF NOT EXISTS step_kind TEXT NOT NULL DEFAULT 'generic';
ALTER TABLE IF EXISTS execution_steps
    ADD COLUMN IF NOT EXISTS provider_key TEXT;
ALTER TABLE IF EXISTS execution_steps
    ADD COLUMN IF NOT EXISTS input_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE IF EXISTS execution_steps
    ADD COLUMN IF NOT EXISTS output_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE IF EXISTS execution_steps
    ADD COLUMN IF NOT EXISTS attempt_count INT NOT NULL DEFAULT 0;
ALTER TABLE IF EXISTS execution_steps
    ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS execution_steps
    ADD COLUMN IF NOT EXISTS approval_gate_id UUID;

CREATE INDEX IF NOT EXISTS idx_execution_steps_provider
    ON execution_steps(provider_key, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_steps_gate
    ON execution_steps(approval_gate_id, status, created_at DESC);

COMMIT;
