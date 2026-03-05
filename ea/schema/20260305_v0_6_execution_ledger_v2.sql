-- Execution ledger v2
-- Adds steps, tool receipts, and run-cost audit tables.

CREATE TABLE IF NOT EXISTS execution_steps (
    step_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
    parent_step_id TEXT NULL,
    step_kind TEXT NOT NULL,
    state TEXT NOT NULL,
    attempt_count INT NOT NULL,
    input_json JSONB NOT NULL,
    output_json JSONB NOT NULL,
    error_json JSONB NOT NULL,
    correlation_id TEXT NOT NULL,
    causation_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_steps_session_created
ON execution_steps(session_id, created_at, step_id);

CREATE TABLE IF NOT EXISTS tool_receipts (
    receipt_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
    step_id TEXT NOT NULL REFERENCES execution_steps(step_id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    action_kind TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    receipt_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_receipts_session_created
ON tool_receipts(session_id, created_at, receipt_id);

CREATE TABLE IF NOT EXISTS run_costs (
    cost_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    tokens_in BIGINT NOT NULL,
    tokens_out BIGINT NOT NULL,
    cost_usd DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_costs_session_created
ON run_costs(session_id, created_at, cost_id);
