ALTER TABLE build_jobs
    ADD COLUMN IF NOT EXISTS token_ciphertext TEXT;

ALTER TABLE build_jobs
    ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(36);

CREATE INDEX IF NOT EXISTS ix_build_jobs_claim
    ON build_jobs(status, created_at);

CREATE INDEX IF NOT EXISTS ix_build_jobs_expired
    ON build_jobs(lease_expires_at)
    WHERE status IN ('building', 'deploying');
