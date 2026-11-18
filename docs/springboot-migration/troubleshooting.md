# Troubleshooting and migration limits

- Maven absent: use ./mvnw. Java 23 can compile with --release 21, but final deployment images use Java 21; report the actual test runtime. Install a complete JDK21 for strict local Java21 tests. A partially downloaded archive produces "Failed setting boot class path"; do not use it.
- Public dependency downloads may be slow/blocked. Do not replace version checks with fabricated success. Use Maven Central access or a verified organizational mirror; retain dependency/test logs.
- Missing PROJECT_DB_PASSWORD: run prepare-spring-databases.py. It intentionally refuses to rotate an existing account if the matching ignored config is missing. Restore the correct password privately.
- Permission denied applying Build DDL: existing build_jobs can be owned by the PostgreSQL administrator, while the host worker uses restricted devsphere_build. Preparation runs only additive DDL as the configured container administrator. Do not change all table owners or grant superuser.
- Nonempty deployment_db: no Flyway baseline flag is needed. Java keeps its migration history in deployment_spring and performs additive DDL on existing public tables. Do not enable clean or ddl-auto=create.
- 409 Java writes disabled: default preview is read-only. Rebuild Python isolation first; then enable JAVA_DEPLOYMENT_WRITES=true in ignored config and recreate only Java Deployment. Existing Python records remain read-only through Java.
- 503 discovery: confirm both UP registrations, forwarded valid JWT, shared network and PROJECT-SERVICE logical name. Allow registry refresh. Never hard-code a fallback localhost port.
- 401 during long build: developer JWT expires after 30 minutes; existing retry refreshes the encrypted credential. Permanent admin tokens are not a solution. Internal workload/service authentication remains follow-up work.
- Kubernetes 401: renew short-lived restricted credential; no admin kubeconfig in application. 403: verify namespace Role/Binding. Container cannot read mode0600 file: check Compose LOCAL_UID/GID match host owner.
- K8s readiness pending: inspect only the demo pod, image availability in Kind, container port 8080 for nginx-unprivileged, requests/limits and rollout conditions. Allowlisted local image must be built and loaded first.
- 409 ownership labels mismatch: investigate; never remove the ownership check to force deletion.
- SQL/K8s crash window: compare record/revisions to live resource. Retry the intended update under the same owner or delete this exact owned deployment; reconciliation deliberately avoids overwriting changed desired state. There is no distributed transaction.
- Gateway 502: optional backend may be stopped; dynamic DNS keeps legacy startup working. Build runs on host port8006; ensure host.docker.internal can reach it. Reload NGINX after nginx -t.
- Existing default route remains Python until complete migration parity is demonstrated. A Java preview is not a claim that legacy records were migrated.
- Monitoring targets down: verify services first, reload only relevant monitoring components and inspect target labels/dashboard datasource UID.
- Memory pressure: Kind currently consumes much of Docker's allocation. Run tests before bringing up the Java platform, or stop only the new Java services with stop-springboot.sh; never prune volumes or unrelated containers.

See execution-report.md for verified results and outstanding environment limitations. Historical v0.1.0-rc1 measurements are not new performance results.
