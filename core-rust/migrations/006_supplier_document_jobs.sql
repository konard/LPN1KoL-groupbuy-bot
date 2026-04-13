-- Migration: 006_supplier_document_jobs
-- Tracks document export jobs sent to suppliers.
-- Status machine: pending → processing → sent | failed_retry | fatal_error
-- Idempotency: unique (procurement_id, job_type, idempotency_key) prevents duplicate sends.

CREATE TABLE IF NOT EXISTS supplier_document_jobs (
    id                  SERIAL PRIMARY KEY,
    procurement_id      INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    organizer_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_type            VARCHAR(50) NOT NULL DEFAULT 'receipt_table',
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'processing', 'sent', 'failed_retry', 'fatal_error')),
    idempotency_key     VARCHAR(255) NOT NULL,
    retry_count         SMALLINT NOT NULL DEFAULT 0,
    max_retries         SMALLINT NOT NULL DEFAULT 3,
    supplier_api_url    TEXT NOT NULL DEFAULT '',
    -- Full request dump to supplier API (for audit / retry)
    request_payload     JSONB NOT NULL DEFAULT '{}',
    -- Full response from supplier API (for audit / debugging)
    response_payload    JSONB,
    error_message       TEXT,
    last_attempt_at     TIMESTAMPTZ,
    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Prevent duplicate jobs for the same procurement + type + idempotency_key
    CONSTRAINT supplier_document_jobs_idempotent UNIQUE (procurement_id, job_type, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_sdj_status ON supplier_document_jobs (status)
    WHERE status IN ('pending', 'failed_retry');
CREATE INDEX IF NOT EXISTS idx_sdj_procurement ON supplier_document_jobs (procurement_id);
CREATE INDEX IF NOT EXISTS idx_sdj_created ON supplier_document_jobs (created_at DESC);

-- Trigger: keep updated_at current
CREATE TRIGGER supplier_document_jobs_updated_at
    BEFORE UPDATE ON supplier_document_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
