# Existing React portal demonstration

Use http://localhost:5173. Register or sign in through the existing account form. The portal retains the current dashboard/design and token-specific session-expiry behavior.

1. Projects → Create project record with name, lowercase slug and description. View details; edit name/description; Save. PostgreSQL stores the record as draft.
2. Click Provision on that record. The existing Orchestrator and workers generate the archive. Once its matching operation is completed, click Link completed. The Java backend verifies owner/result; status changes to provisioned. The existing provisioning form below is also preserved for legacy use.
3. In Provisioning operations, click Build & deploy. Build pipeline shows actual queued/building/deploying/completed. Edit label appears only while queued. Cancel build confirms and atomically archives a queued job; Archive build applies only to completed/failed. View build displays server details, with credentials omitted.
4. Existing Deployments continues to show Python-managed build workloads. Scaling/history/rollback/logs remain. Edit image and confirmed deletion now call the existing APIs.
5. Java deployments → choose an owned project, nginx-unprivileged image, container port 8080 and one replica. Deploy application uses Java → Eureka-discovered Project authorization → Kubernetes.
6. Scale 2; watch readiness. Scale 1; History → Restore; View logs shows pods/logs. Edit image accepts only allowlisted images. Delete deployment confirms and removes only its own resources.
7. Projects → Delete project confirms metadata deletion. Generated operations, builds and workload history remain independent.

Loading/error states are visible. A 401 for the current token returns to login with a session-expired message; a delayed 401 for an older token cannot terminate a newer session. No mock data is used by the running portal. Java service errors appear independently of existing overview data.

```bash
cd frontend/developer-portal
npm ci
npm test
npm run build
```

API-mocked component tests exercise Project create/read/edit/delete and cancellation, visible errors, Java deployment submission, safe Build controls and session expiry. See execution report for the actual browser verification performed; automated component tests are distinct from live browser evidence.
