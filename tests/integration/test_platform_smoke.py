"""Non-destructive DevSphere platform smoke tests."""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1"

checks = [
    ("Gateway", 8080, "/gateway/health", 200),
    ("Orchestrator", 8080, "/api/orchestrator/health", 200),
    ("Deployment", 8005, "/ready", 200),
    ("Build", 8006, "/ready", 200),
    ("Auth protection", 8080, "/api/auth/me", 401),
]


def request(port, path):
    url = f"{BASE}:{port}{path}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read().decode(
                "utf-8", errors="replace"
            )
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(
            "utf-8", errors="replace"
        )


def main():
    failures = []

    print("\n===== DEVSPHERE PLATFORM SMOKE TEST =====\n")

    for name, port, path, expected in checks:
        try:
            status, _ = request(port, path)

            if status != expected:
                raise AssertionError(
                    f"Expected HTTP {expected}, received {status}"
                )

            print(f"PASS: {name} -> HTTP {status}")

        except Exception as error:
            failures.append(name)
            print(f"FAIL: {name} -> {error}")

    try:
        status, body = request(8005, "/metrics")

        if status != 200:
            raise AssertionError(f"Metrics endpoint HTTP {status}")

        success = [
            line for line in body.splitlines()
            if line.startswith("devsphere_k8s_collection_success ")
        ]

        if not success:
            raise AssertionError("Kubernetes collection metric missing")

        value = float(success[0].split()[-1])

        if value != 1:
            raise AssertionError("Kubernetes collection failed")

        print("PASS: Kubernetes metrics collection -> 1")

    except Exception as error:
        failures.append("Kubernetes metrics")
        print(f"FAIL: Kubernetes metrics -> {error}")

    print("\n========================================")

    if failures:
        print(f"FAILED: {len(failures)} checks")
        print("Failed components:", ", ".join(failures))
        sys.exit(1)

    print("ALL PLATFORM SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
