CREATE TABLE IF NOT EXISTS deployments (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    name VARCHAR(63) NOT NULL,
    image VARCHAR(255) NOT NULL,
    container_port INTEGER NOT NULL,
    replicas INTEGER NOT NULL,
    namespace VARCHAR(63) NOT NULL,
    status VARCHAR(30) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_deployments_owner
ON deployments(owner_id);
