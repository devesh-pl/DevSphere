# DevSphere — Demonstration Guide

## Goal
Demonstrate application provisioning, automated building, Kubernetes deployment, monitoring, and platform reliability.

## 1. Open the Developer Portal
Local URL: http://127.0.0.1:5173

Sign in using an existing developer account.

## 2. Show Project Provisioning
Explain how the Orchestrator creates a starter application and tracks asynchronous operations.

## 3. Show the Build Pipeline
Open Builds and explain durable PostgreSQL jobs, independent workers, leases, heartbeats, and retries.

## 4. Demonstrate Kubernetes Deployment
Select an existing application.
Show deployment readiness, scaling, revision history, and rollback.

## 5. Demonstrate Diagnostics
Open Pod information and application logs.

## 6. Show Observability
Open Grafana at http://127.0.0.1:3000.
Show service health, HTTP performance, build pipeline metrics, and Kubernetes workload readiness.

## 7. Show CI
Open the GitHub Actions page and show successful Python and React checks.

## 8. Discuss Technical Decisions
- Why the Build Worker is separate from the Build API
- How PostgreSQL row locks prevent concurrent job claims
- Why worker leases and heartbeats matter
- How the deployment reconciler handles stale states
- How deployment ownership and Kubernetes RBAC limit access

## 9. Explain Limitations
- Local Kind cluster rather than hosted Kubernetes
- Developer JWT dependency in the current Build Worker
- Additional production security and failure testing required

## Cleanup
Use the authenticated deployment cleanup utility only for known test workloads.
