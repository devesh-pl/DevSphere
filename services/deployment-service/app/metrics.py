"""Prometheus HTTP metrics for DevSphere services."""

import time

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)


HTTP_REQUESTS = Counter(
    "devsphere_http_requests",
    "Total HTTP requests",
    ["service", "method", "route", "status"],
)

HTTP_DURATION = Histogram(
    "devsphere_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "route"],
    buckets=(
        0.005, 0.01, 0.025, 0.05, 0.1,
        0.25, 0.5, 1, 2.5, 5, 10
    ),
)


def install_metrics(app: FastAPI, service: str):
    @app.middleware("http")
    async def collect_metrics(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        started = time.perf_counter()
        status = 500

        try:
            response = await call_next(request)
            status = response.status_code
            return response

        finally:
            duration = time.perf_counter() - started

            # Use the route template rather than concrete IDs.
            # This prevents unbounded label cardinality.
            route = request.scope.get("route")
            route_name = getattr(route, "path", "unmatched")

            HTTP_REQUESTS.labels(
                service=service,
                method=request.method,
                route=route_name,
                status=str(status),
            ).inc()

            HTTP_DURATION.labels(
                service=service,
                method=request.method,
                route=route_name,
            ).observe(duration)

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
