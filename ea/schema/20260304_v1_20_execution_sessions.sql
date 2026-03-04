BEGIN;

CREATE TABLE IF NOT EXISTS execution_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'telegram_free_text',
    chat_id BIGINT,
    intent_type TEXT NOT NULL DEFAULT 'free_text',
    objective TEXT NOT NULL DEFAULT '',
    intent_spec_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    last_error TEXT,
    outcome_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_sessions_poll
    ON execution_sessions(tenant, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_sessions_corr
    ON execution_sessions(correlation_id);

CREATE TABLE IF NOT EXISTS execution_steps (
    step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
    step_order INT NOT NULL,
    step_key TEXT NOT NULL,
    step_title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    preconditions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_text TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(session_id, step_key)
);

CREATE INDEX IF NOT EXISTS idx_execution_steps_poll
    ON execution_steps(session_id, status, step_order);

CREATE TABLE IF NOT EXISTS execution_events (
    event_id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
    level TEXT NOT NULL DEFAULT 'info',
    event_type TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_events_lookup
    ON execution_events(session_id, created_at DESC);

COMMIT;
