BEGIN;

CREATE TABLE IF NOT EXISTS memory_candidates (
    memory_candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_key TEXT NOT NULL,
    source_session_id UUID REFERENCES execution_sessions(session_id) ON DELETE SET NULL,
    concept TEXT NOT NULL,
    candidate_fact TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    sensitivity TEXT NOT NULL DEFAULT 'internal',
    sharing_policy TEXT NOT NULL DEFAULT 'private',
    review_status TEXT NOT NULL DEFAULT 'pending',
    review_note TEXT,
    reviewer TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_memory_candidates_lookup
    ON memory_candidates(tenant_key, review_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_candidates_session
    ON memory_candidates(source_session_id, created_at DESC);

COMMIT;
