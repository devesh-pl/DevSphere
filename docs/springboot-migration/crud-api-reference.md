# REST CRUD practical reference

All business endpoints require `Authorization: Bearer <developer token>` from existing `/api/auth/login`. Never commit tokens or actual passwords. External URLs below go through NGINX. Project JSON uses camelCase; Deployment and Build retain snake_case compatibility. Lists are bounded to 100; Project accepts `?page=0&size=50`.

| Service | Operation | Method / external endpoint | Controller method | Portal control | Table | Status | Evidence |
|---|---|---|---|---|---|---|---|
| Project (Java) | CREATE | POST /api/projects | ProjectController.create | Create project record | project_db.projects | 201 | REST report, SQL |
| Project | READ | GET /api/projects, /api/projects/{id} | list / get | Project list / View project | projects | 200 | Details panel |
| Project | UPDATE | PUT /api/projects/{id} | update | Edit project / Save / Link completed | projects | 200 | Updated description/link |
| Project | DELETE | DELETE /api/projects/{id} | delete | Delete project + confirmation | projects | 204 | GET returns 404 |
| Deployment (Java) | CREATE | POST /api/deployment-spring/deployments | DeploymentController.create | Java deployments / Deploy application | deployment_db.deployments | 201 | Kubernetes resources + SQL |
| Deployment | READ | GET /api/deployment-spring/deployments, /{id} | list / get | Cards / readiness | deployments | 200 | Live ready replicas |
| Deployment | UPDATE | PUT or PATCH /api/deployment-spring/deployments/{id} | update | Scale 1/2 / Edit image | deployments, deployment_revisions | 200 | kubectl + history |
| Deployment | DELETE | DELETE /api/deployment-spring/deployments/{id} | delete | Delete deployment + confirmation | deployments (soft delete) | 200 | Resources gone, audit kept |
| Build (Python) | CREATE | POST /api/build/builds | create_build | Build & deploy on completed operation | build_db.build_jobs | 202 | Job UUID / worker lifecycle |
| Build | READ | GET /api/build/builds, /{id} | list_builds / get_build | Build pipeline / View build | build_jobs | 200 | Backend job details |
| Build | UPDATE | PUT /api/build/builds/{id} | update_build | Edit label (queued only) | build_jobs.label | 200 | Saved label |
| Build | DELETE | DELETE /api/build/builds/{id} | delete_build | Cancel build / Archive build | build_jobs.archived_at | 200 | Audit retained; list hides row |

Python legacy deployments still use `/api/deployment/deployments` with existing POST/GET/PATCH/DELETE semantics. Java preview keeps collection/item, revisions, rollback, pods/logs contracts and adds PUT; it requires an owned project_id. Do not route the legacy Build Worker to Java yet.

## Request examples

Project create/update (PUT includes all fields):
```json
{"name":"University API","slug":"university-api","description":"Practical","templateId":"fastapi-basic","provisioningOperationId":null}
```
Response 201/200 includes UUID id, trusted ownerId, status draft, createdAt and updatedAt. Link a completed matching operation UUID to obtain status provisioned; arbitrary pending/other-owner operation is rejected. Existing provisioning and build flows remain separate actual operations.

Java deployment:
```json
{"name":"university-api","image":"nginxinc/nginx-unprivileged:stable-alpine","container_port":8080,"replicas":1,"project_id":"<owned project UUID>"}
```
Response 201 includes id, generated ds-java-* name, namespace devsphere-apps, status deploying, image, replicas and service_dns. `PUT {"replicas":2}` scales Kubernetes; `PUT {"image":"devsphere-built/university-api:abcdef12"}` accepts only an existing allowlisted built image. Image policy validation alone does not create/load an image.

`POST .../{id}/rollback {"revision":1}` restores the persisted revision and appends a rollback revision. GET `.../{id}/revisions`, `/pods`, `/logs?tail_lines=100` provide evidence.

Build create: `{"operation_id":"<completed FastAPI provisioning UUID>"}`. Update: `{"label":"Practical demo"}`. DELETE cancels only queued or archives terminal; running returns 409. All cancellation races are resolved by PostgreSQL row locking/state predicates.

## Error examples

| Status | Trigger | Example detail |
|---|---|---|
| 400 | Invalid Java DTO/UUID/slug/replicas, unknown ownerId field | Invalid request fields |
| 401 | Missing/expired/invalid JWT | Authentication required / Authentication failed |
| 403 | Authenticated account has disallowed business role | Developer access required |
| 404 | Unknown or another owner's record | Project not found / Deployment not found |
| 409 | Duplicate owner slug; edit active job; mutate Python-owned record; link incomplete operation | Record conflicts / Only visible queued build metadata can be edited |
| 422 | Container image fails allowlist; invalid Python request | Image not in development allowlist |
| 502 | Kubernetes request fails | Kubernetes creation/update/deletion failed |
| 503 | Auth/Orchestrator/discovery dependency unavailable | Project service discovery unavailable |

Source comments: `services/project-service-spring/.../controller/ProjectController.java`, `services/deployment-service-spring/.../controller/DeploymentController.java`, `services/build-service/app/main.py`, and portal `CrudPanels.jsx`, `App.jsx`. Search `rg -n 'CREATE:|READ:|UPDATE:|DELETE:' services frontend/developer-portal/src`.

Import `devsphere-spring.postman_collection.json`; set baseUrl/token/projectId/deploymentId/operationId/buildId in your private Postman environment. Or run `bash scripts/demo-springboot-crud.sh` for actual assertions and isolated cleanup.
