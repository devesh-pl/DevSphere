#!/usr/bin/env bash

set -Eeuo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(
    docker compose
    --env-file .env
    -f infrastructure/docker/docker-compose.yml
)

echo "Checking PostgreSQL..."

"${COMPOSE[@]}" exec -T postgres \
    pg_isready -U devsphere_admin -d postgres

echo ""
echo "Checking RabbitMQ..."

"${COMPOSE[@]}" exec -T rabbitmq \
    rabbitmq-diagnostics -q ping

echo ""
echo "All infrastructure health checks passed."
