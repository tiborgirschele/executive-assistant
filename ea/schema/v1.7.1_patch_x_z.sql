-- Patch X1: Die universelle, idempotente Ingress-Tabelle
CREATE TABLE IF NOT EXISTS external_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    attempt_count INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant, source, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_ext_events_poll ON external_events(status, next_attempt_at);

-- Patch Z1: Connector Store
CREATE TABLE IF NOT EXISTS connectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant, connector_type)
);

-- Patch Z2 & Y1
INSERT INTO connectors (tenant, connector_type, is_active, config_json) 
VALUES ('girscheles', 'invoiless', FALSE, '{"reason": "Parked. Not in AP execution path. Future receivables only."}')
ON CONFLICT DO NOTHING;

INSERT INTO connectors (tenant, connector_type, is_active, config_json) 
VALUES ('girscheles', 'apixdrive', TRUE, '{"enabled_flows": ["gmail_invoice_ingest", "drive_invoice_ingest", "generic_webhook_ingest"]}')
ON CONFLICT DO NOTHING;
