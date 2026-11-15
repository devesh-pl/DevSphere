"""Generate the DevSphere Build Pipeline Grafana dashboard."""

import json
from pathlib import Path

DS = {"type": "postgres", "uid": "devsphere-build-db"}


def panel(pid, title, sql, kind, x, y, w, h, unit="short"):
    return {
        "id": pid,
        "title": title,
        "type": kind,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{
            "refId": "A",
            "datasource": DS,
            "rawQuery": True,
            "rawSql": sql,
            "format": "time_series" if kind == "timeseries" else "table",
        }],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "palette-classic"},
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
                "orientation": "auto",
                "textMode": "auto",
                "colorMode": "value",
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
    "uid": "devsphere-build-pipeline",
    "title": "DevSphere — Build Pipeline",
    "tags": ["devsphere", "builds", "postgresql"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "15s",
    "time": {"from": "now-24h", "to": "now"},
    "panels": [
        panel(
            1, "Completed Builds (24h)",
            """
            SELECT COUNT(*)::double precision AS value
            FROM build_observability
            WHERE status = 'completed'
              AND updated_at >= NOW() - INTERVAL '24 hours'
            """,
            "stat", 0, 0, 6, 5,
        ),
        panel(
            2, "Failed Builds (24h)",
            """
            SELECT COUNT(*)::double precision AS value
            FROM build_observability
            WHERE status = 'failed'
              AND updated_at >= NOW() - INTERVAL '24 hours'
            """,
            "stat", 6, 0, 6, 5,
        ),
        panel(
            3, "Active / Queued Builds",
            """
            SELECT COUNT(*)::double precision AS value
            FROM build_observability
            WHERE status IN ('queued', 'building', 'deploying')
            """,
            "stat", 12, 0, 6, 5,
        ),
        panel(
            4, "Success Rate (24h)",
            """
            SELECT
              COALESCE(
                100.0 * COUNT(*) FILTER (WHERE status = 'completed')
                / NULLIF(COUNT(*), 0),
                0
              )::double precision AS value
            FROM build_observability
            WHERE status IN ('completed', 'failed')
              AND updated_at >= NOW() - INTERVAL '24 hours'
            """,
            "stat", 18, 0, 6, 5, "percent",
        ),
        panel(
            5, "Completed Builds Over Time",
            """
            SELECT
              date_trunc('minute', updated_at) AS time,
              COUNT(*)::double precision AS completed
            FROM build_observability
            WHERE status = 'completed'
              AND $__timeFilter(updated_at)
            GROUP BY 1
            ORDER BY 1
            """,
            "timeseries", 0, 5, 12, 8,
        ),
        panel(
            6, "Average End-to-End Turnaround",
            """
            SELECT
              date_trunc('minute', updated_at) AS time,
              AVG(turnaround_seconds)::double precision AS seconds
            FROM build_observability
            WHERE status = 'completed'
              AND $__timeFilter(updated_at)
            GROUP BY 1
            ORDER BY 1
            """,
            "timeseries", 12, 5, 12, 8, "s",
        ),
        panel(
            7, "Builds by Attempt Count",
            """
            SELECT
              attempt_count,
              COUNT(*)::double precision AS builds
            FROM build_observability
            WHERE $__timeFilter(created_at)
            GROUP BY attempt_count
            ORDER BY attempt_count
            """,
            "table", 0, 13, 12, 8,
        ),
        panel(
            8, "Build Status Distribution",
            """
            SELECT
              status,
              COUNT(*)::double precision AS builds
            FROM build_observability
            WHERE $__timeFilter(created_at)
            GROUP BY status
            ORDER BY status
            """,
            "table", 12, 13, 12, 8,
        ),
    ],
}

out = Path(
    "infrastructure/monitoring/grafana/dashboards/"
    "devsphere-build-pipeline.json"
)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dashboard, indent=2))

print("PASS: Build Pipeline dashboard created")
print(out)
