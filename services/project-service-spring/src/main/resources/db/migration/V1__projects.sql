CREATE TABLE projects (
 id UUID PRIMARY KEY, owner_id UUID NOT NULL, name VARCHAR(100) NOT NULL,
 slug VARCHAR(40) NOT NULL, description TEXT NOT NULL DEFAULT '', template_id VARCHAR(50) NOT NULL,
 provisioning_operation_id UUID UNIQUE, status VARCHAR(30) NOT NULL DEFAULT 'draft',
 created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
 CONSTRAINT uq_project_owner_slug UNIQUE(owner_id,slug),
 CONSTRAINT ck_project_slug CHECK (slug ~ '^[a-z][a-z0-9]*(-[a-z0-9]+)*$'),
 CONSTRAINT ck_project_status CHECK(status IN ('draft','provisioned'))
);
CREATE INDEX ix_projects_owner_created ON projects(owner_id,created_at DESC);
