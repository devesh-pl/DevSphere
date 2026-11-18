# Existing implementation audit — 2026-11-18

Inspected before source changes. Clean `main` at `0846657`; protected tag `v0.1.0-rc1` resolves to `e00cc00f6084e106f2c7815376fc708c8ba804ba`. Created requested `feat/springboot-eureka` branch. No applicable AGENTS.md found. Existing secrets were not printed or copied.

## Architecture and actual contracts
- Auth FastAPI, port 8001: `/auth/register`, `/auth/login`, `/auth/me`. HS256 JWT issuer `devsphere-auth`, audience `devsphere-api`, access type, 30-minute lifetime; active account lookup. Services validate through `/auth/me`.
- Catalog FastAPI 8002: `/catalog/services`; global listing and owner/admin deletion. Internal provisioning registration uses separate shared credential.
- Template FastAPI 8003: authenticated templates and internal archive generation.
- Orchestrator FastAPI 8004: `/operations`, `/{id}`, `/{id}/download`. Provision requests store slug/template/repository. Durable operations plus transactional outbox, RabbitMQ, worker leases/recovery. Completed result includes slug, template, Catalog ID and archive download URL.
- Python Deployment 8005: POST/GET/DELETE `/deployments`, PATCH `/{id}`, GET `/{id}/revisions`, POST `/{id}/rollback`, GET `/{id}/pods` and `/logs`; `/health`, `/ready`, `/metrics`. POST returns 201, ownership mismatch returns 404. Snake-case JSON. Replicas 1–2, fixed namespace `devsphere-apps`, generated names `ds-<uuid prefix>`.
- Build FastAPI on host 8006: POST `/builds` (202), GET collection/item, POST retry (202). Only completed owned FastAPI provisioning accepted; unique operation ID gives idempotency. Host worker builds Docker images and loads Kind.
- Existing React/Vite portal has in-memory JWT, token-specific 401 expiry event, overview/projects/build/deployment screens, provisioning, retry, scaling/history/rollback/logs. Vite directly proxies 8001/8004/8005/8006. NGINX 8080 currently routes auth, orchestrator and Python deployment, but lacks build route.

## Database ownership
PostgreSQL 18.7 Docker, dedicated database users per service. Auth and Catalog use Alembic. Orchestrator owns operations/outbox. Build owns `build_jobs` with queued/building/deploying/completed/failed CHECK, lease/heartbeat/attempt/token columns and observability view. Deployment owns `deployments` (varchar UUID, owner/name/image/port/replicas/namespace/status/error/timestamp) and `deployment_revisions` (FK, unique deployment/revision). Do not reset tables or volumes. New Java project gets isolated project_db. Java deployment uses additive authority/project linkage columns; existing records default to Python authority.

## Deployment lifecycle and security
Python commits deploying record, creates Deployment and ClusterIP Service, cleans partial failures, stores failed; scale/image changes lock row and append revisions. Reconciler compares image/replicas/status snapshots before changing status. Delete soft-deletes after Kubernetes cleanup. Image policy allows fixed unprivileged nginx and `devsphere-built/<slug>:<hex>`. UID 101, no privilege escalation, ALL capabilities dropped, RuntimeDefault seccomp, requests 25m/32Mi and limits 200m/128Mi. Namespace Role and restricted kubeconfig already exist; base compose also has older kubeconfig mount, so always use RBAC override.

## Build worker dependencies
Host Docker/Kind CLI, generated ZIP via Orchestrator, encrypted developer JWT, PostgreSQL `FOR UPDATE SKIP LOCKED`, leases and heartbeat, retry max attempts, Python deployment route. Tokens expire: preserve encryption and current auth; workload identity/service authentication remains separate follow-up. Never use permanent admin tokens. Cancellation must atomically exclude worker claim; preserve known statuses by archiving queued jobs and changing them to existing terminal `failed` with explicit cancellation reason. Retry excludes archived jobs.

## Environment and validation baseline
Java 23.0.1 only; Maven missing; isolated Maven/JDK21 tooling required. Docker memory 4,108,828,672 bytes (~3.8 GiB); 15 existing containers including Kind. Host free disk ~16 GiB; Docker images ~5GB, volumes ~1.9GB. Ports 8761/8087/8088 had no listeners. Docker inspection required sandbox escalation and succeeded. Existing CI compiles Python, tests rollout classifier, runs npm ci/build. Existing integration suites hit live services and require carefully isolated accounts/resources. Historical 18/18 and 21.92s are not post-change results.

## Migration strategy and breaking-change controls
1. Add standalone Eureka and Java Project CRUD, existing Auth validation, isolated Flyway schema.
2. Integrate portal Project CRUD while preserving provision operations. Associate only verified owned provisioning results; status derives from actual operation.
3. Add Java Deployment preview at 8088 / `/api/deployment-spring`, real Fabric8 Kubernetes client, namespace RBAC, explicit Java labels and database authority. Python APIs/reconciler exclude Java authority, Java refuses legacy writes. Read existing Python rows for comparison. No bulk adoption.
4. Deployment verifies referenced project via load-balanced `http://PROJECT-SERVICE`, forwarding existing bearer credential. Legacy no-project requests remain on Python.
5. Add safe queued metadata editing and cancellation/terminal archiving to Build, without new status values or hard deletion.
6. Add opt-in compose/gateway/monitoring, unit and isolated integration verification, docs. Switch production deployment routing only after parity/e2e evidence; otherwise retain preview and document unmet cutover gate.

Spring Boot 4.1.2 / Cloud 2025.1.4 verified in Maven Central; official compatibility table maps 2025.1.2+ to Boot 4.1.x: https://spring.io/projects/spring-cloud/ . No live workloads, containers, volumes or release tags changed during audit.

## Live ownership findings
The running Build API uses restricted devsphere_build rather than build_service. build_jobs and deployment_revisions are owned by the PostgreSQL administrator, while deployments belongs to deployment_service. Safe preparation uses the existing administrator only for additive Build DDL; Java migration does not create a redundant index on the administrator-owned revisions table. Existing grants and table ownership are preserved.
