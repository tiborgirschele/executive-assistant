BEGIN;

CREATE TABLE IF NOT EXISTS llm_egress_policies (
    id BIGSERIAL PRIMARY KEY,
    tenant TEXT NOT NULL DEFAULT '*',
    person_id TEXT NULL,
    task_type TEXT NOT NULL DEFAULT '*',
    data_class TEXT NOT NULL DEFAULT '*',
    action TEXT NOT NULL DEFAULT 'allow',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_egress_policies_lookup
    ON llm_egress_policies(tenant, task_type, data_class, active, updated_at DESC);

COMMIT;
