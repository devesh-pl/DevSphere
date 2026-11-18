#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
exec "${PYTHON:-python3}" scripts/demo-springboot-crud.py "$@"
