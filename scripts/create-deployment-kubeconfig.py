"""Create a restricted Kubernetes credential for local DevSphere."""

import json
import os
import subprocess
from pathlib import Path

root = Path("infrastructure/docker/kubeconfig")
original = root / "devsphere.yaml"
target = root / "deployment-restricted.yaml"

if not original.exists():
    raise SystemExit(f"Missing original kubeconfig: {original}")

config = json.loads(
    subprocess.check_output([
        "kubectl",
        "config", "view",
        "--kubeconfig", str(original),
        "--raw",
        "--minify",
        "-o", "json",
    ], text=True)
)

cluster = config["clusters"][0]["cluster"]

if not cluster.get("certificate-authority-data"):
    raise SystemExit(
        "Expected CA certificate data missing. "
        "Refusing to create an insecure kubeconfig."
    )

token = subprocess.check_output([
    "kubectl",
    "--context", "kind-devsphere",
    "-n", "devsphere-apps",
    "create", "token", "devsphere-deployment",
    "--duration=24h",
], text=True).strip()

if not token:
    raise SystemExit("Kubernetes did not issue a token")

restricted = {
    "apiVersion": "v1",
    "kind": "Config",
    "clusters": [{
        "name": "devsphere-restricted",
        "cluster": cluster,
    }],
    "users": [{
        "name": "devsphere-deployment",
        "user": {"token": token},
    }],
    "contexts": [{
        "name": "devsphere-restricted",
        "context": {
            "cluster": "devsphere-restricted",
            "user": "devsphere-deployment",
            "namespace": "devsphere-apps",
        },
    }],
    "current-context": "devsphere-restricted",
}

# JSON is also valid YAML and can be read by the Kubernetes SDK.
# Use restrictive permissions and never display the token.
fd = os.open(
    target,
    os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
    0o600,
)
with os.fdopen(fd, "w") as f:
    json.dump(restricted, f, indent=2)

target.chmod(0o600)

print("PASS: Restricted kubeconfig generated")
print(f"Location: {target}")
print("Requested token lifetime: 24 hours")
print("Do not commit this file.")
