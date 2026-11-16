CREATE TABLE IF NOT EXISTS deployment_revisions (
    id BIGSERIAL PRIMARY KEY,
    deployment_id VARCHAR(36) NOT NULL
        REFERENCES deployments(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    image VARCHAR(255) NOT NULL,
    replicas INTEGER NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (deployment_id, revision_number)
);

CREATE INDEX IF NOT EXISTS ix_deployment_revisions_lookup
ON deployment_revisions(deployment_id, revision_number DESC);
