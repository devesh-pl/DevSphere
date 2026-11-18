CREATE TABLE IF NOT EXISTS public.deployments (
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
ON public.deployments(owner_id);

CREATE TABLE IF NOT EXISTS public.deployment_revisions (
    id BIGSERIAL PRIMARY KEY,
    deployment_id VARCHAR(36) NOT NULL
        REFERENCES public.deployments(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    image VARCHAR(255) NOT NULL,
    replicas INTEGER NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (deployment_id, revision_number)
);

-- The existing UNIQUE(deployment_id, revision_number) already indexes revision lookup.
-- Do not issue CREATE INDEX against a legacy table owned by another role.

ALTER TABLE public.deployments ADD COLUMN IF NOT EXISTS management_service VARCHAR(20) NOT NULL DEFAULT 'python';
ALTER TABLE public.deployments ADD COLUMN IF NOT EXISTS project_id UUID;
CREATE INDEX IF NOT EXISTS ix_deployments_management ON public.deployments(management_service,status);
-- project_db is separate: project ownership is checked through Eureka, never through a cross-database FK.
