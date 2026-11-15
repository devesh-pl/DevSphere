"""Rotate DevSphere local Kubernetes credentials when near expiry."""

import argparse
import base64
import fcntl
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KUBECONFIG = (
    ROOT / "infrastructure/docker/kubeconfig/deployment-restricted.yaml"
)

COMPOSE = [
    "docker", "compose",
    "--env-file", str(ROOT / ".env"),
    "-f", str(ROOT / "infrastructure/docker/docker-compose.yml"),
    "-f", str(ROOT / "infrastructure/docker/docker-compose.dev.yml"),
    "-f", str(ROOT / "infrastructure/docker/docker-compose.deployment.yml"),
    "-f", str(ROOT / "infrastructure/docker/docker-compose.deployment-rbac.yml"),
]


def expiry(path):
    try:
        config = json.loads(path.read_text())
        token = config["users"][0]["user"]["token"]
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return int(claims["exp"])
    except (OSError, ValueError, KeyError, IndexError):
        return 0


def run(command):
    subprocess.run(command, cwd=ROOT, check=True)


def ready():
    for _ in range(15):
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8005/ready", timeout=3
            ) as response:
                if response.status == 200:
                    return True
        except (OSError, TimeoutError):
            pass
        time.sleep(2)
    return False


def rotate(force=False):
    current_expiry = expiry(KUBECONFIG)
    remaining = current_expiry - time.time()

    if not force and remaining > 45 * 60:
        print(
            "SKIP: Kubernetes credential remains valid "
            f"for approximately {int(remaining / 60)} minutes"
        )
        return

    print("Rotating restricted Kubernetes credential")

    # Check that Docker is accessible before modifying credentials.
    run(["docker", "info", "--format", "{{.ServerVersion}}"])

    # Validate the Compose configuration and credential mount.
    config = subprocess.check_output(
        COMPOSE + ["config", "--format", "json"],
        cwd=ROOT,
        text=True,
    )
    service = json.loads(config)["services"]["deployment-service"]
    mounts = [
        volume for volume in service.get("volumes", [])
        if "/app/kubeconfig" in volume.get("target", "")
    ]
    assert len(mounts) == 1, "Expected one Kubernetes credential mount"
    assert mounts[0]["target"] == "/app/kubeconfig/config"
    assert mounts[0]["source"].endswith("deployment-restricted.yaml")
    assert mounts[0].get("read_only") is True

    previous = KUBECONFIG.read_bytes() if KUBECONFIG.exists() else None

    # Use the existing Phase 13.3 generator.
    run([
        sys.executable,
        str(ROOT / "scripts/create-deployment-kubeconfig.py"),
    ])

    new_expiry = expiry(KUBECONFIG)

    if new_expiry <= time.time() + 60:
        if previous is not None:
            KUBECONFIG.write_bytes(previous)
            KUBECONFIG.chmod(0o600)
        raise RuntimeError("New token has invalid or insufficient lifetime")

    try:
        run(
            COMPOSE + [
                "up", "-d", "--no-build", "--no-deps",
                "--force-recreate", "deployment-service",
            ]
        )

        if not ready():
            raise RuntimeError(
                "Deployment Service not ready after credential rotation"
            )

    except Exception:
        if previous is not None:
            KUBECONFIG.write_bytes(previous)
            KUBECONFIG.chmod(0o600)
            try:
                run(
                    COMPOSE + [
                        "up", "-d", "--no-build", "--no-deps",
                        "--force-recreate", "deployment-service",
                    ]
                )
            except Exception:
                print("WARNING: Automatic rollback failed", file=sys.stderr)
        raise

    print(
        "PASS: Restricted credential renewed; "
        f"expires in approximately {int((new_expiry-time.time())/60)} minutes"
    )
    print("PASS: Deployment Service is ready")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    lock = ROOT / "infrastructure/docker/kubeconfig/rotation.lock"

    with lock.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rotate(force=args.force)


if __name__ == "__main__":
    main()
