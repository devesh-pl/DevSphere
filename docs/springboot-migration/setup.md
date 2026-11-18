# macOS setup and shutdown

Use the existing repository and existing .env files. Do not reset databases, volumes or Kind. Reserve ports 8761, 8087 and 8088. Install a Java 21 JDK and Docker Desktop; use the provided Maven Wrapper. The supported Homebrew cask is documented at https://formulae.brew.sh/cask/temurin@21 .

```bash
brew install --cask temurin@21
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
```

The current host still has Java23; Java21 service and test execution was verified in Docker. No system Java installation was silently replaced. Docker currently has ~3.8 GiB on an 8 GB Mac, so avoid concurrent image builds and watch `docker stats`.

```bash
cd "$HOME/Downloads/DevSphere"
git switch feat/springboot-eureka
.venv/bin/python -m pip install -r requirements-dev.txt
java -version                 # Java 21 recommended
./mvnw -B verify
.venv/bin/python scripts/prepare-spring-databases.py
```

Preparation generates a unique project password into ignored mode-0600 `.env.spring.local`, creates isolated project_db/project_service and applies only additive Build CRUD columns. It never rotates an existing role password. Existing DB/table ownership may differ from the initialization script; preparation runs DDL via the local PostgreSQL administrator without exposing its credentials. Never paste .env contents into logs.

Before enabling Java writes, deploy the tested Python authority isolation change:

```bash
docker compose --env-file .env  -f infrastructure/docker/docker-compose.yml  -f infrastructure/docker/docker-compose.dev.yml  -f infrastructure/docker/docker-compose.deployment.yml  -f infrastructure/docker/docker-compose.deployment-rbac.yml  up -d --build --no-deps deployment-service
```

Restart only your existing host Build API/worker after the additive migration so they load new handlers/claim predicates. Their existing launch commands and encrypted-token configuration remain valid; keep port 8006. The worker still calls Python port 8005.

Apply the existing namespace Role if needed and generate/rotate a short-lived restricted kubeconfig using the existing scripts:

```bash
kubectl --context kind-devsphere apply -f infrastructure/kubernetes/rbac/deployment-service.yaml
.venv/bin/python scripts/create-deployment-kubeconfig.py
```

The base kubeconfig is read only by the credential preparation script; the application mounts only `deployment-restricted.yaml`. Keep this file ignored and mode 0600. The Java Compose process uses LOCAL_UID/LOCAL_GID from .env.spring.local to read the restricted file without changing its permissions. Renew the service-account token when it expires.

Set `JAVA_DEPLOYMENT_WRITES=true` in ignored `.env.spring.local` only after the Python isolation build and tests pass. Default false gives a read-only Java preview. Then:

```bash
bash scripts/start-springboot.sh
# Wait for health checks, then validate/reload gateway configuration:
docker exec devsphere-gateway nginx -t
docker exec devsphere-gateway nginx -s reload
# In a separate terminal:
cd frontend/developer-portal
npm ci
npm test
npm run build
npm run dev
```

Start script targets only the three new services with --no-deps. Existing Auth/PostgreSQL/Orchestrator must already be running. It does not remove orphans. Default route remains Python. Multi-stage images use Maven + Java 21 and non-root JRE runtimes with bounded heaps. First builds require public dependency downloads.

```bash
# Full isolated REST/Kubernetes verification; optional real image build:
bash scripts/verify-springboot-platform.sh
bash scripts/verify-springboot-platform.sh --end-to-end
# Stop only new Java services, preserving existing containers and all volumes:
bash scripts/stop-springboot.sh
```

Open portal http://localhost:5173, Eureka http://localhost:8761, gateway http://localhost:8080 and Grafana at its existing configured port (normally http://localhost:3000). Starting/stopping the optional peer configuration is covered separately. Run independent tests before starting the Java platform to reduce memory pressure. If needed, stop only the newly added Java services with stop-springboot.sh while building/testing; keep existing workloads intact.

## Traffic cutover gate

Do not replace `/api/deployment` with Java until existing-record parity, lifecycle, logs, scaling, rollback and isolated end-to-end tests all pass for the release. This implementation deliberately retains preview routing. Legacy worker requests lack project_id and must continue through Python. Reverting preview use requires only returning to the original Deployments screen and stopping the three Java services; additive schemas remain safe. No bulk ownership adoption or automatic production cutover.

## Lightweight runtime image build

After `./mvnw verify`, reuse verified JARs to avoid repeating Maven downloads inside Docker. The multi-stage Dockerfiles remain the default clean build.

```bash
docker compose --env-file .env --env-file .env.spring.local \
 -f infrastructure/docker/docker-compose.yml \
 -f infrastructure/docker/docker-compose.dev.yml \
 -f infrastructure/docker/docker-compose.spring.yml \
 -f infrastructure/docker/docker-compose.spring-runtime.yml \
 up -d --build --no-deps eureka-server project-service-spring deployment-service-spring
```

This optional overlay still runs the services on Java 21 and retains all limits/health checks. It requires freshly packaged JARs from the same source revision.
