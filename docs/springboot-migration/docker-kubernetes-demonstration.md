# Docker, PostgreSQL and Kubernetes evidence

The new Compose overlay joins devsphere-internal. Ports are loopback-only: Eureka 8761, Project 8087, Java Deployment 8088. JVMs use SerialGC, small starting heaps and explicit maximums; existing containers are not restarted by the Java startup script. See setup.md for dependency startup and restricted-credential renewal.

```bash
docker stats --no-stream
docker compose --env-file .env --env-file .env.spring.local  -f infrastructure/docker/docker-compose.yml  -f infrastructure/docker/docker-compose.dev.yml  -f infrastructure/docker/docker-compose.spring.yml config --quiet
kubectl --context kind-devsphere -n devsphere-apps get deployment,service,pods
```

For a known demo name from crud-results.json, inspect only that workload:

```bash
kubectl --context kind-devsphere -n devsphere-apps get deployment <demo-kubernetes-name> -o wide
kubectl --context kind-devsphere -n devsphere-apps get pods -l app=<demo-kubernetes-name>
```

The REST demo scales to two ready replicas, back to one, restores two historical configurations, reads logs, then removes only its own Deployment/Service. No application admin kubeconfig mounts. The existing Role grants namespace-only operations for Deployments/Services/pods/logs. Generated application pods never receive a service-account token.

Database verification does not require revealing a password:

```bash
docker exec devsphere-postgres psql -U project_service -d project_db -c 'SELECT id,name,slug,status,provisioning_operation_id FROM projects ORDER BY created_at DESC LIMIT 10;'
docker exec devsphere-postgres psql -U deployment_service -d deployment_db -c 'SELECT id,management_service,status,replicas FROM deployments ORDER BY created_at DESC LIMIT 10;'
python3 scripts/verify-springboot-database.py
```

The last command uses precisely the recorded demo UUID and prints persisted soft-delete/revision history. Project physical deletion is checked with GET 404; inspect records before deletion for a classroom persistence demonstration. Build audit retains archived_at and known lifecycle statuses. Never reset schemas or volumes to demonstrate persistence.

Prometheus adds `devsphere-spring` scraping /actuator/prometheus at the three Java services. Existing monitoring overlays remain. Grafana adds DevSphere Spring Boot with availability, request rate, error ratio, mean latency, reconciliation outcomes and the existing readiness collector. Reload/restart only Prometheus/Grafana when you intentionally load provisioning changes. Verify `up{job="devsphere-spring"}` and `http_server_requests_seconds_count`; readiness panel retains `devsphere_k8s_deployment_ready_replicas`.

Use `--monitoring` with demo-springboot-crud.sh to assert that the actual Java workload reports two ready replicas in Prometheus before cleanup. The read-only collector includes both ownership labels; lifecycle/reconciliation authority remains separate.
