# DevSphere

Self-Service Internal Developer Platform (IDP).

## Project Overview

DevSphere is a microservices-based developer platform designed
to simplify application creation, container builds, Kubernetes
deployment, configuration management, and observability.

## Architecture

The platform consists of eight backend microservices:

1. Authentication Service
2. Service Catalog Service
3. Template Service
4. Orchestrator Service
5. Build Service
6. Deployment Service
7. Configuration Service
8. Monitoring Service

## Technology Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS

### Backend
- Python
- FastAPI
- SQLAlchemy
- Alembic

### Infrastructure
- PostgreSQL
- RabbitMQ
- Docker
- Kubernetes
- Kong
- Istio
- Helm

### Observability
- Prometheus
- Grafana
- Loki
- OpenTelemetry
- Jaeger

## Local Development

### Prerequisites

- macOS
- Python 3
- Node.js
- Git
- Docker Desktop
- Docker Compose

### Initial Setup

```bash
bash scripts/setup.sh