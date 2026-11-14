CREATE TABLE IF NOT EXISTS build_jobs (
    id VARCHAR(32) PRIMARY KEY,
    operation_id VARCHAR(36) NOT NULL UNIQUE,
    owner_id VARCHAR(36) NOT NULL,
    project_slug VARCHAR(63) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    lease_expires_at TIMESTAMPTZ,
    last_heartbeat_at TIMESTAMPTZ,
    image VARCHAR(255),
    deployment_id VARCHAR(36),
    kubernetes_name VARCHAR(63),
    namespace VARCHAR(63),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT build_jobs_status_valid
      CHECK (status IN (
        'queued', 'building', 'deploying', 'completed', 'failed'
      ))
);

CREATE INDEX IF NOT EXISTS ix_build_jobs_owner
    ON build_jobs(owner_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_build_jobs_recovery
    ON build_jobs(status, lease_expires_at);
