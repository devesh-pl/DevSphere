#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
"${PYTHON:-python3}" scripts/verify-springboot-platform.py
bash scripts/demo-springboot-crud.sh "$@"
(cd frontend/developer-portal && npm run build && npm test)
# Read-only persistence evidence for precisely the deployment created by the demo.
"${PYTHON:-python3}" scripts/verify-springboot-database.py
