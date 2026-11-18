#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
docker compose --env-file .env --env-file .env.spring.local \
 -f infrastructure/docker/docker-compose.yml -f infrastructure/docker/docker-compose.dev.yml \
 -f infrastructure/docker/docker-compose.spring.yml \
 stop deployment-service-spring project-service-spring eureka-server
