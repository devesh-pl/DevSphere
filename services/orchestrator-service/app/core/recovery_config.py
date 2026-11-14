"""Worker recovery policy for DevSphere."""

import os

MAX_OPERATION_ATTEMPTS = int(
    os.getenv("MAX_OPERATION_ATTEMPTS", "3")
)

OPERATION_LEASE_SECONDS = int(
    os.getenv("OPERATION_LEASE_SECONDS", "60")
)

WORKER_HEARTBEAT_SECONDS = int(
    os.getenv("WORKER_HEARTBEAT_SECONDS", "10")
)

RECOVERY_SCAN_SECONDS = int(
    os.getenv("RECOVERY_SCAN_SECONDS", "5")
)

if MAX_OPERATION_ATTEMPTS < 1:
    raise ValueError("MAX_OPERATION_ATTEMPTS must be positive")

if OPERATION_LEASE_SECONDS <= WORKER_HEARTBEAT_SECONDS * 3:
    raise ValueError(
        "Lease duration must exceed three heartbeat intervals"
    )
