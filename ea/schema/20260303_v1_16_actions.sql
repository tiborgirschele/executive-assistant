BEGIN;

CREATE TABLE IF NOT EXISTS action_drafts (
    draft_id UUID PRIMARY KEY,
    tenant_key TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    action_payload_json JSONB NOT NULL,
    preconditions_json JSONB NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_key, idempotency_key)
);

CREATE TABLE IF NOT EXISTS action_state_history (
    state_event_id SERIAL PRIMARY KEY,
    draft_id UUID NOT NULL REFERENCES action_drafts(draft_id),
    from_state TEXT,
    to_state TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS approval_requests (
    approval_request_id SERIAL PRIMARY KEY,
    draft_id UUID NOT NULL REFERENCES action_drafts(draft_id),
    tenant_key TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    request_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS approval_decisions (
    approval_decision_id SERIAL PRIMARY KEY,
    approval_request_id BIGINT NOT NULL REFERENCES approval_requests(approval_request_id),
    decided_by TEXT NOT NULL,
    decision TEXT NOT NULL,
    decision_payload_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS action_callbacks (
    callback_id SERIAL PRIMARY KEY,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    tenant_key TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    action_family TEXT NOT NULL,
    draft_id UUID NOT NULL REFERENCES action_drafts(draft_id),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS action_executions (
    execution_id SERIAL PRIMARY KEY,
    draft_id UUID NOT NULL REFERENCES action_drafts(draft_id),
    tenant_key TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    execution_status TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS execution_receipts (
    receipt_id SERIAL PRIMARY KEY,
    execution_id BIGINT NOT NULL REFERENCES action_executions(execution_id),
    validated_preconditions_json JSONB,
    changed_fields_json JSONB,
    receipt_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saga_instances (
    saga_id UUID PRIMARY KEY,
    draft_id UUID NOT NULL REFERENCES action_drafts(draft_id),
    saga_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saga_steps (
    saga_step_id SERIAL PRIMARY KEY,
    saga_id UUID NOT NULL REFERENCES saga_instances(saga_id),
    step_name TEXT NOT NULL,
    step_status TEXT NOT NULL,
    step_payload_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS compensation_events (
    compensation_event_id SERIAL PRIMARY KEY,
    saga_id UUID NOT NULL REFERENCES saga_instances(saga_id),
    step_name TEXT NOT NULL,
    compensation_status TEXT NOT NULL,
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_action_drafts_status ON action_drafts(tenant_key, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(tenant_key, request_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_action_callbacks_expires ON action_callbacks(expires_at, used_at);
CREATE INDEX IF NOT EXISTS idx_action_executions_status ON action_executions(tenant_key, execution_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_saga_instances_status ON saga_instances(saga_status, updated_at DESC);

COMMIT;
