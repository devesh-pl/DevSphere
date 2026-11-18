# University evaluation checklist

Actual results are recorded in execution-report.md. Checked items have executed evidence; source presence alone is not runtime evidence.

- [x] Three business services: Java Project, Java Deployment, Python Build.
- [x] One standalone Eureka server and two Java business instances UP.
- [x] Logical-name LoadBalancer call succeeds; unknown/cross-user project rejected; unavailable Project returns503.
- [x] Project backend CRUD with PostgreSQL persistence and owner/slug validation.
- [x] Deployment backend CRUD creates real Kubernetes resources, scales1→2→1, updates allowlisted images, persists revisions, rolls back and safely deletes.
- [x] Build backend CRUD retains claim/lease/retry semantics and rejects active deletion.
- [x] Existing portal demonstrates the three CRUD interfaces, loading/errors and confirmation flows.
- [x] Current-token401 expires the session; stale401 cannot expire a newer one.
- [x] Build-to-Kind still works through legacy Python authority.
- [x] Existing database rows, unrelated workloads and volumes remain intact.
- [x] Local Java21 tests, Python tests and npm ci/test/build pass.
- [ ] Remote GitHub Actions execution: not run without an authorized push.
- [x] Prometheus scrapes Java services; Grafana existing/new dashboards render.
- [x] NGINX routes tested rather than relying only on direct ports.
- [x] Secret-free Postman/REST examples and exact demo cleanup evidence retained.
- [x] No automatic production deployment cutover without verified compatibility.
- [x] Optional two-peer mode documented; second server stopped by default.

Evidence files default to /private/tmp/devsphere-spring-evidence: eureka-registration.json, crud-results.json, postgres-persistence.txt. Credentials/tokens are not included. Copy only reviewed non-secret reports into docs if sharing. Test suites use H2 for HTTP/controller isolation, mock Kubernetes for client contract tests, real PostgreSQL for queue concurrency, and real service/Kind checks separately. Clearly distinguish these levels.
