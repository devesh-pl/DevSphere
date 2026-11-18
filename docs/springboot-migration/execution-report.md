# Actual execution report — 18 November 2026

## Outcome

The existing repository now runs a hybrid platform with two Java business services (Project and Deployment), one Python Build business service, and one Eureka infrastructure service. Both Java applications registered UP and a real Deployment→PROJECT-SERVICE lookup succeeded through Eureka and Spring Cloud LoadBalancer. CRUD was exercised through NGINX and the existing React portal, with real PostgreSQL and Kind. The existing Python deployment route remains authoritative for legacy build requests; Java uses an explicit preview route and its own workloads.

No release was pushed or published. The original v0.1.0-rc1 tag still resolves to e00cc00f6084e106f2c7815376fc708c8ba804ba. Work is on feat/springboot-eureka, based on initially clean main at 0846657.

## Executed checks

| Check | Actual result |
|---|---|
| Maven dependency resolution/package | PASS; Boot 4.1.2, Cloud 2025.1.4, Fabric8 8.0.0 BOM resolved |
| Complete Java test run | PASS: 32 tests, 0 failures/errors/skips, Java 21.0.13 container |
| Java breakdown | Eureka 1; Project HTTP/provisioning 12; Deployment/discovery/client/reconciliation 19 |
| Python reconciliation + queue CRUD/worker tests | PASS: 14 tests against disposable PostgreSQL schemas |
| Python syntax | PASS: 125 Python files compiled |
| React install/test/build | PASS: npm ci, 9 tests, production build |
| Existing platform smoke | PASS: gateway, Orchestrator, Deployment, Build, auth protection and K8s metrics |
| Existing worker recovery integration | PASS: original expired lease recovery, outbox publishing, worker restart and attempt 1→2 |
| Real Eureka registration | PASS: PROJECT-SERVICE and DEPLOYMENT-SERVICE UP |
| Real Java-to-Java discovery | PASS, including unknown/cross-user rejection |
| Actual Project outage | PASS: 503 while stopped; same Project container restored; owned test record deleted |
| Project backend CRUD | PASS through NGINX; PostgreSQL-backed draft/provisioned state and ownership checks |
| Java deployment backend CRUD | PASS: actual Deployment/Service creation, 1→2→1 replicas, revisions, rollback, pods/logs, safe delete |
| Python build-to-Kind | PASS: two actual builds completed, one submitted by REST and one by React |
| Frontend Project CRUD | PASS: create/read/edit/provision/link completed operation/delete |
| Frontend Deployment CRUD | PASS: create/read/scale/history/logs/confirmed deletion; Python-built test deployment also removed |
| Frontend Build CRUD | PASS: submit/read, queued label edit, queued cancellation and terminal archive |
| PostgreSQL audit persistence | PASS: deleted Java deployment still persisted with five revision rows; build cancellation/archive retained |
| Prometheus/Grafana | PASS: all 3 Spring targets UP, real request metrics, 6 additional provisioned panels; existing dashboards retained |
| Java workload readiness metric | PASS: real Java deployment reported 2 ready replicas through existing compatible collector |
| Compose/peer-mode/shell syntax | PASS: configurations validated; second Eureka not started |
| Docker runtime images | PASS: all three new applications actually run on Java 21 using verified JAR runtime images |
| Clean multi-stage images | Source/configuration provided; Maven image tag verified. Full clean multi-stage build was not executed locally; runtime overlay was used to avoid redundant downloads on this Mac |
| GitHub Actions | Workflow updated; remote run NOT executed because no push was authorized |

The Java test run used classes compiled with --release21 on host Java 23 and ran the complete suite with Java 21.0.13 in Docker. This verifies the target runtime without changing the system Java installation. The supplied clean multi-stage Dockerfiles compile with a Java 21 JDK. Maven Wrapper is included.

## Live evidence

- [Eureka registry JSON](evidence/eureka-registration.json) and [dashboard screenshot](screenshots/eureka-registration.jpg).
- [REST end-to-end results](evidence/crud-results.json), including exact generated IDs and completed checks.
- [PostgreSQL deployment/revision audit](evidence/postgres-persistence.txt).
- [Prometheus/Grafana evidence](evidence/monitoring.json) and [Java readiness evidence](evidence/java-readiness-crud.json).
- [Actual discovery failure/recovery](evidence/discovery-failure.txt).
- [Project UI proof](screenshots/project-crud.jpg), [Deployment UI proof](screenshots/deployment-crud.jpg), [completed Build](screenshots/build-completed.jpg), [queued Build edit/cancel controls](screenshots/build-queued-crud.jpg), [frontend cleanup](screenshots/frontend-cleanup.jpg).
- [Java test results](evidence/java-tests.json), [legacy platform smoke](evidence/legacy-platform-smoke.txt), [worker recovery](evidence/legacy-worker-recovery.txt), [owned-resource cleanup](evidence/frontend-database-audit.txt).

Portal screenshots were captured at the in-app browser's narrow 436px viewport; tables scroll horizontally. Eureka was captured at 1280px. Native confirmation handling stalled the first browser tab; after user dismissal, live checks were completed in a fresh tab with in-page confirmation/edit dialogs. The final controls reuse existing button styling.

For deterministic live queued CRUD, only the verified idle, task-managed host Build worker was paused briefly. No active job was interrupted. A two-minute automatic-resume guard was in place, and it was explicitly resumed immediately after cancelling the owned queued job. Other workloads/containers were not used as disposable test resources.

## Failures found and corrected

- Truncated temporary Java 21 downloads: do not use those archives. Java 21 runtime images were used successfully; host installation remains Java 23.
- A missing common-module dependency and wrong client API call were corrected during compilation.
- A Project test leaked its own data between cases; tests now reset only the test database between cases.
- Boot dependency management initially selected mismatched Fabric8 transitive versions; the Fabric8 BOM now aligns them.
- A redundant CREATE INDEX failed on the administrator-owned legacy revisions table. The unique key already covers lookup; migration no longer attempts that owner-only operation.
- Eureka transport initially inherited a load-balanced HTTP builder. Separate @Primary plain transport and @LoadBalanced Project clients resolve the bootstrap cycle; a regression test covers it.
- Default Kubernetes transport did not support this kubeconfig's TLS hostname override. Explicit Jetty transport preserves CA/hostname validation and passes real readiness/CRUD.
- Cold-start JVM pauses and CPU throttling caused transient HTTP timeouts. New business JVMs allow one-CPU startup bursts within existing Docker memory. Demo account registration permits the measured Argon2 latency; no hashing/security controls were weakened.
- The CPU-limited mock Kubernetes TLS client timed out once. Tests now use a realistic 30-second cold-TLS timeout with the same Jetty transport; the final complete Java 21 suite passed all 32.
- Native browser prompts blocked automation; accessible in-page confirmations/edit fields now cover the same operations and all nine React tests pass.
- Read-only Kubernetes metrics originally selected only Python ownership labels. The selector now includes Java ownership without changing metric names or lifecycle authority; actual two-replica Java readiness was verified.

## Dependency choice and remaining limits

Spring Boot 4.1.2 manages JUnit Jupiter 6.0.3, and Spring Framework 7 raises its minimum to JUnit 6. This differs from the prompt's JUnit 5 preference. The verified current Boot/Cloud pair was retained; no incompatible JUnit 5 override was added. Sources: [Spring compatibility](https://spring.io/projects/spring-cloud/), [Framework 7 release notes](https://github.com/spring-projects/spring-framework/wiki/Spring-Framework-7.0-Release-Notes).

npm audit reports five high-severity development-tool dependency entries stemming from the unpatched picomatch advisory [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf). The queried latest picomatch 4.0.7 is affected and the advisory lists no patched version. No forced Vite/Vitest major downgrade was performed. These tools are development dependencies; keep the dev server loopback-bound. This is a known remaining security concern, not a clean audit claim.

Default deployment traffic was deliberately not cut over to Java: legacy Build Worker requests lack project_id. Existing Python records remain readable for comparison and cannot be mutated through Java. Bulk adoption/cutover remains a separately gated migration.

The developer-JWT encryption/30-minute expiry model remains unchanged. Workload identity for internal calls is follow-up work. Kubernetes service-account credentials are short-lived and require renewal using existing scripts. Database and Kubernetes operations cannot form one distributed transaction: crash-window reconciliation limits are documented in architecture.md.

Historical 18/18 builds and 21.92s are not presented as new results. This run verified two real builds and correctness; it was not a replacement performance benchmark. Initial service startup and authentication were slow under concurrent tests on the 8 GB Mac. Run builds/tests before the live demonstration, wait for readiness, and avoid unnecessary peer/parallel services.

Synthetic test accounts, completed provisioning/Catalog records, generated archives and soft-deleted audit rows are retained; no account-deletion API exists. Cleanup deleted only the exact demo Kubernetes resources and Project metadata. No existing volume, namespace, database, legacy table or release tag was reset.

## Run and stop

Follow [setup.md](setup.md) for JDK21 installation, restricted credentials, Python isolation and the write flag. Key commands from the repository root:

```bash
./mvnw -B verify
.venv/bin/python scripts/prepare-spring-databases.py
bash scripts/start-springboot.sh
# Or use the lightweight verified-JAR runtime overlay documented in setup.md.
PYTHON=.venv/bin/python bash scripts/verify-springboot-platform.sh --end-to-end --monitoring
.venv/bin/python scripts/verify-springboot-monitoring.py
bash scripts/stop-springboot.sh
```

See [changed-files.md](changed-files.md) for the complete file manifest, [CRUD matrix](crud-api-reference.md), [Postman collection](devsphere-spring.postman_collection.json), and the other university demonstration guides.

## Final repository state

Logical milestones: `1c739c0` (Java services/audit) and `0a9292d` (verified integration, UI, queues, CI and scripts), followed by the documentation/evidence commit. Configured secret values were checked across all changed and new files with no matches. The default Python mount now uses the restricted credential as well, and kubeconfigs are excluded from Docker build contexts. Root development requirements record the tested cryptography/python-dotenv dependencies.

Remaining empty test-only PostgreSQL schemas from the initial failed setup were removed without CASCADE. Public tables and unrelated schema contents were not removed. The final frontend audit proves both demo deployments are soft-deleted, the Project record is gone, the queued build was cancelled before attempt 1, and archived records have cleared credentials.
