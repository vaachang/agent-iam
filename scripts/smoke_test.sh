#!/usr/bin/env bash

set -euo pipefail

base_url="${1:-http://127.0.0.1:8000}"

echo "[1/4] health"
curl -s "${base_url}/healthz"
printf '\n\n'

echo "[2/4] allowed flow"
curl -s -X POST "${base_url}/api/v1/demo/run/allowed-flow"
printf '\n\n'

echo "[3/4] denied flow"
curl -s -X POST "${base_url}/api/v1/demo/run/denied-flow"
printf '\n\n'

echo "[4/4] audit export"
curl -s "${base_url}/api/v1/audit/export"
printf '\n'
