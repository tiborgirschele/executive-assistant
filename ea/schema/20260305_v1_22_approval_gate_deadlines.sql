BEGIN;

ALTER TABLE IF EXISTS approval_gates
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS approval_gates
    ADD COLUMN IF NOT EXISTS decision_source TEXT;
ALTER TABLE IF EXISTS approval_gates
    ADD COLUMN IF NOT EXISTS decision_actor TEXT;
ALTER TABLE IF EXISTS approval_gates
    ADD COLUMN IF NOT EXISTS decision_ref TEXT;

CREATE INDEX IF NOT EXISTS idx_approval_gates_expiry
    ON approval_gates(decision_status, expires_at);

COMMIT;
