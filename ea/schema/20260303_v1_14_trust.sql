BEGIN;

CREATE TABLE IF NOT EXISTS review_claims (
    claim_id SERIAL PRIMARY KEY,
    review_queue_item_id BIGINT NOT NULL REFERENCES review_queue_items(id),
    claimed_by TEXT NOT NULL,
    claim_token TEXT NOT NULL,
    claim_expires_at TIMESTAMPTZ NOT NULL,
    claim_status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS evidence_reveals (
    reveal_id SERIAL PRIMARY KEY,
    review_queue_item_id BIGINT NOT NULL REFERENCES review_queue_items(id),
    claim_id BIGINT NOT NULL REFERENCES review_claims(claim_id),
    revealed_by TEXT NOT NULL,
    reveal_reason TEXT,
    correlation_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dead_letter_items (
    dead_letter_id SERIAL PRIMARY KEY,
    tenant_key TEXT NOT NULL,
    source_pointer TEXT,
    connector_type TEXT,
    failure_code TEXT NOT NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    correlation_id TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dead_letter_envelopes (
    envelope_id SERIAL PRIMARY KEY,
    dead_letter_id BIGINT NOT NULL REFERENCES dead_letter_items(dead_letter_id),
    redacted_failure_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_vault_objects (
    vault_object_id UUID PRIMARY KEY,
    tenant_key TEXT NOT NULL,
    correlation_id TEXT,
    object_ref TEXT,
    encrypted_payload BYTEA NOT NULL,
    key_ref TEXT NOT NULL,
    key_version INT NOT NULL DEFAULT 1,
    is_readable BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shredded_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS deletion_tombstones (
    tombstone_id SERIAL PRIMARY KEY,
    tenant_key TEXT NOT NULL,
    object_ref TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS connector_health (
    connector_health_id SERIAL PRIMARY KEY,
    tenant_key TEXT NOT NULL,
    connector_key TEXT NOT NULL,
    status TEXT NOT NULL,
    failure_code TEXT,
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correlation_id TEXT
);

CREATE TABLE IF NOT EXISTS breaker_history (
    breaker_history_id SERIAL PRIMARY KEY,
    breaker_key TEXT NOT NULL,
    breaker_state TEXT NOT NULL,
    reason TEXT,
    correlation_id TEXT,
    changed_by TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operator_audit_events (
    operator_event_id SERIAL PRIMARY KEY,
    actor_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    correlation_id TEXT,
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_claims_item ON review_claims(review_queue_item_id, claim_status);
CREATE INDEX IF NOT EXISTS idx_evidence_reveals_item ON evidence_reveals(review_queue_item_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dead_letter_items_status ON dead_letter_items(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_vault_tenant_ref ON evidence_vault_objects(tenant_key, object_ref);
CREATE INDEX IF NOT EXISTS idx_deletion_tombstones_ref ON deletion_tombstones(tenant_key, object_ref);
CREATE INDEX IF NOT EXISTS idx_connector_health_tenant_key ON connector_health(tenant_key, connector_key);
CREATE INDEX IF NOT EXISTS idx_breaker_history_key ON breaker_history(breaker_key, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_operator_audit_corr ON operator_audit_events(correlation_id, created_at DESC);

COMMIT;
