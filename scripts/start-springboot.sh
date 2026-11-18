#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.spring.local ]] || { echo 'Run .venv/bin/python scripts/prepare-spring-databases.py first.'; exit 1; }
[[ -f infrastructure/docker/kubeconfig/deployment-restricted.yaml ]] || { echo 'Generate the restricted Kubernetes credential first (see setup.md).'; exit 1; }
compose=(docker compose --parallel 1 --env-file .env --env-file .env.spring.local
 -f infrastructure/docker/docker-compose.yml -f infrastructure/docker/docker-compose.dev.yml
 -f infrastructure/docker/docker-compose.spring.yml)
"${compose[@]}" config --quiet
# Target only new services: preserve existing Python containers and volumes.
"${compose[@]}" build eureka-server project-service-spring deployment-service-spring
"${compose[@]}" up -d --no-deps eureka-server project-service-spring deployment-service-spring
printf 'Java preview started. Eureka: http://localhost:8761\nRun scripts/verify-springboot-platform.sh after health checks pass.\n'
