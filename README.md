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
## Why DevSphere?

Developers often need to coordinate multiple tools to provision applications, build container images, deploy workloads, and troubleshoot infrastructure.

DevSphere provides a self-service interface that brings these workflows together using microservices and Kubernetes.

### Key Capabilities

- JWT-based developer authentication and ownership controls
- Project provisioning with generated application templates
- Durable asynchronous build jobs using PostgreSQL
- Independent Build Worker with leases, heartbeats, and retries
- Docker image builds and deployment to local Kind Kubernetes
- Deployment scaling, revisions, and rollback
- Kubernetes deployment-state reconciliation
- Pod diagnostics and application logs
- Prometheus metrics and Grafana dashboards
- GitHub Actions automated Python and React checks

### Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| Data and messaging | PostgreSQL, RabbitMQ |
| Containers and orchestration | Docker, Kubernetes, Kind |
| Gateway | NGINX |
| Monitoring | Prometheus, Grafana |
| CI | GitHub Actions |

### Evaluation Results

| Metric | Local test result |
|---|---:|
| Completed builds | 18/18 |
| Average end-to-end turnaround | 21.92 seconds |
| Minimum turnaround | 11.21 seconds |
| Maximum turnaround | 38.14 seconds |
| Running deployment records | 20 |
| Latest successful GitHub Actions runs | 3/3 |

These measurements come from local development tests and should not be interpreted as production benchmarks.

### Documentation

- [System Architecture](docs/architecture.md)
- [Demo Guide](docs/demo-guide.md)
- [Performance Evaluation](docs/evaluation.md)

### Project Status

DevSphere is a working local prototype. Production deployment requires additional build isolation, internal worker authentication hardening, secret management, and operational testing.


## Spring Boot + Eureka migration

The existing platform is extended on `feat/springboot-eureka` with Java Project Management, a parallel Java Deployment preview, and the existing Python Build Service. The original dashboard and Python deployment route remain available. The Java preview is protected by an explicit write flag and separate workload authority; it is not an automatic traffic migration.

Start with [the inspected current state](docs/springboot-migration/current-state.md), [macOS setup](docs/springboot-migration/setup.md), [architecture](docs/springboot-migration/architecture.md), [CRUD matrix/API reference](docs/springboot-migration/crud-api-reference.md), and [actual execution results](docs/springboot-migration/execution-report.md). The migration folder also contains Eureka, frontend, Docker/Kubernetes and troubleshooting demonstrations plus a Postman collection.

```bash
./mvnw -B verify
.venv/bin/python scripts/prepare-spring-databases.py
bash scripts/start-springboot.sh
bash scripts/verify-springboot-platform.sh
bash scripts/stop-springboot.sh
```

Read setup.md before enabling Java Kubernetes writes. Never reset existing databases, volumes or workloads to run the demonstration. Historical release evaluation remains historical; see the new execution report for rerun evidence.
