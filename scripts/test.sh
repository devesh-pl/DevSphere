#!/usr/bin/env bash

set -Eeuo pipefail

cd "$(dirname "$0")/.."

bash scripts/health-check.sh

echo ""
echo "DevSphere infrastructure tests passed."
