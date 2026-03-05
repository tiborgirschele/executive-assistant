BEGIN;

ALTER TABLE IF EXISTS typed_actions
    ADD COLUMN IF NOT EXISTS session_id UUID;
ALTER TABLE IF EXISTS typed_actions
    ADD COLUMN IF NOT EXISTS step_id UUID;
ALTER TABLE IF EXISTS typed_actions
    ADD COLUMN IF NOT EXISTS approval_gate_id UUID;

CREATE INDEX IF NOT EXISTS idx_typed_actions_session
    ON typed_actions(session_id);
CREATE INDEX IF NOT EXISTS idx_typed_actions_approval_gate
    ON typed_actions(approval_gate_id);

CREATE TABLE IF NOT EXISTS approval_gates (
    approval_gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
    tenant TEXT NOT NULL,
    chat_id BIGINT,
    approval_class TEXT NOT NULL DEFAULT 'explicit_callback_required',
    decision_status TEXT NOT NULL DEFAULT 'pending',
    action_id TEXT,
    decision_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_approval_gates_session
    ON approval_gates(session_id, decision_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_gates_action
    ON approval_gates(action_id);

COMMIT;
