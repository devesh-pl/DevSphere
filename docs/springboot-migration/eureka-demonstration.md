# Eureka service discovery demonstration

Open http://localhost:8761 and locate PROJECT-SERVICE and DEPLOYMENT-SERVICE with UP instances. Eureka itself is infrastructure. Default is one standalone server with register-with-eureka=false and fetch-registry=false.

```bash
curl -fsS http://localhost:8761/actuator/health
curl -fsS -H 'Accept: application/json' http://localhost:8761/eureka/apps
python3 scripts/verify-springboot-platform.py
bash scripts/demo-springboot-crud.sh
```

The demo creates an owned Project record and requests `/api/deployment-spring/discovery/projects/{id}`. Source `discovery/ProjectDiscovery.java` calls the logical URI `http://PROJECT-SERVICE/...`; `config/DiscoveryConfiguration.java` supplies @LoadBalanced RestClient.Builder. The authenticated lookup succeeds through actual Eureka registration and owner validation. It also verifies unknown and cross-user projects return 404. Unit integration tests use a test-only simple registry to exercise the LoadBalancer and failure mapping; runtime verification uses the real Eureka registry without static fallback.

For classroom failure demonstration, stop only the Project container, wait for registry/cache refresh, then repeat lookup: it returns 503. Restart it, wait until UP and retry. Registration leases/caches mean dashboard changes are not instantaneous. Avoid changing global self-preservation just to make a screenshot look healthy.

## Optional two-peer mode

Only use if the teacher literally requests two discovery servers. Not enabled by default on the 8 GB machine. Add `infrastructure/docker/docker-compose.eureka-peers.yml` to the same compose arguments and use `--profile eureka-peers up -d --no-deps eureka-server eureka-peer`. Both use the same image, register/fetch true and point at one another. Dashboard ports 8761 and 8762. Set client EUREKA_URL to the comma-separated peer URLs for failover, recreate only the two Java clients. Peer mode adds ~384 MiB budget. To revert, stop only eureka-peer, remove the peers overlay and recreate only eureka-server and the two clients. Do not run `down -v`.

Automated optional runtime failure check: `.venv/bin/python scripts/verify-discovery-failure.py`. It creates its own account/project, stops only the new Project container, asserts 503 through the discovery endpoint, restores that same container in a finally block and removes only its own Project record. Run when other Java Project operations are idle.

```bash
docker compose --env-file .env --env-file .env.spring.local \
 -f infrastructure/docker/docker-compose.yml \
 -f infrastructure/docker/docker-compose.dev.yml \
 -f infrastructure/docker/docker-compose.spring.yml \
 -f infrastructure/docker/docker-compose.eureka-peers.yml \
 --profile eureka-peers up -d --no-deps eureka-server eureka-peer
```

Only this explicit optional command starts the second server. Stop it with the same arguments followed by `stop eureka-peer`; remove the peer overlay and recreate only the primary to return to standalone.
