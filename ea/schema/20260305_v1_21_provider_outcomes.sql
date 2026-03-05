BEGIN;

CREATE TABLE IF NOT EXISTS provider_outcomes (
    provider_outcome_id BIGSERIAL PRIMARY KEY,
    tenant_key TEXT NOT NULL DEFAULT '',
    provider_key TEXT NOT NULL,
    task_type TEXT NOT NULL,
    outcome_status TEXT NOT NULL,
    score_delta INT NOT NULL DEFAULT 0,
    latency_ms INT,
    error_class TEXT,
    source TEXT NOT NULL DEFAULT 'runtime',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provider_outcomes_lookup
    ON provider_outcomes(provider_key, task_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_provider_outcomes_task_time
    ON provider_outcomes(task_type, occurred_at DESC);

COMMIT;
