"""Generate DevSphere Kubernetes Monitoring dashboard."""

import json
from pathlib import Path


DS = {
    "type": "prometheus",
    "uid": "devsphere-prometheus",
}


def panel(pid, title, expression, kind, x, y, w, h, unit="short"):
    return {
        "id": pid,
        "title": title,
        "type": kind,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{
            "expr": expression,
            "refId": "A",
            "legendFormat": "{{deployment}}{{pod}}",
            "instant": kind == "stat",
        }],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "min": 0,
            },
            "overrides": [],
        },
        "options": (
            {
                "reduceOptions": {
                    "calcs": ["lastNotNull"],
                    "fields": "",
                    "values": False,
                },
                "colorMode": "value",
                "orientation": "auto",
            }
            if kind == "stat"
            else {
                "legend": {
                    "displayMode": "list",
                    "placement": "bottom",
                }
            }
        ),
    }


dashboard = {
    "uid": "devsphere-kubernetes",
    "title": "DevSphere — Kubernetes Workloads",
    "tags": ["devsphere", "kubernetes", "operations"],
    "schemaVersion": 39,
    "version": 1,
    "refresh": "15s",
    "time": {
        "from": "now-30m",
        "to": "now",
    },
    "panels": [
        panel(
            1,
            "Desired Replicas",
            "sum(devsphere_k8s_deployment_desired_replicas)",
            "stat", 0, 0, 6, 5,
        ),
        panel(
            2,
            "Ready Replicas",
            "sum(devsphere_k8s_deployment_ready_replicas)",
            "stat", 6, 0, 6, 5,
        ),
        panel(
            3,
            "Ready Pods",
            "sum(devsphere_k8s_pod_ready)",
            "stat", 12, 0, 6, 5,
        ),
        panel(
            4,
            "Container Restarts",
            "sum(devsphere_k8s_pod_restarts)",
            "stat", 18, 0, 6, 5,
        ),
        panel(
            5,
            "Ready Replicas by Deployment",
            "devsphere_k8s_deployment_ready_replicas",
            "timeseries", 0, 5, 12, 9,
        ),
        panel(
            6,
            "Desired Replicas by Deployment",
            "devsphere_k8s_deployment_desired_replicas",
            "timeseries", 12, 5, 12, 9,
        ),
        panel(
            7,
            "Pod Restart Counts",
            "devsphere_k8s_pod_restarts",
            "timeseries", 0, 14, 12, 9,
        ),
        panel(
            8,
            "Kubernetes Collection Health",
            "devsphere_k8s_collection_success",
            "timeseries", 12, 14, 12, 9,
        ),
    ],
}

path = Path(
    "infrastructure/monitoring/grafana/dashboards/"
    "devsphere-kubernetes.json"
)

path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(dashboard, indent=2))

print("PASS: Kubernetes Grafana dashboard created")
