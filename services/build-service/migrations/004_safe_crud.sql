-- Apply before starting the updated Build API or worker. No status enum changes.
ALTER TABLE build_jobs ADD COLUMN IF NOT EXISTS label VARCHAR(120) NOT NULL DEFAULT '';
ALTER TABLE build_jobs ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_build_jobs_visible_owner ON build_jobs(owner_id,created_at DESC) WHERE archived_at IS NULL;
