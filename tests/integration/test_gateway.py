"""DevSphere API Gateway integration tests."""

import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8080"


def check(path, expected_status):
    try:
        with urllib.request.urlopen(
            BASE + path,
            timeout=10,
        ) as response:
            status = response.status

    except urllib.error.HTTPError as error:
        status = error.code

    assert status == expected_status, (
        f"{path}: expected HTTP {expected_status}, "
        f"received HTTP {status}"
    )

    print(f"PASS: {path} -> HTTP {status}")


def main():
    print("\n===== DEVSPHERE API GATEWAY TEST =====\n")

    check("/gateway/health", 200)
    check("/api/orchestrator/health", 200)
    check("/api/deployment/health", 200)
    check("/api/auth/me", 401)

    print("\nALL GATEWAY ROUTING CHECKS PASSED")


if __name__ == "__main__":
    main()
