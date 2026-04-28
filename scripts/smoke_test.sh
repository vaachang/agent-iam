#!/usr/bin/env bash

set -euo pipefail

base_url="${1:-http://127.0.0.1:8000}"

echo "[1/7] health"
curl -s "${base_url}/healthz"
printf '\n\n'

echo "[2/7] allowed flow"
curl -s -X POST "${base_url}/api/v1/demo/run/allowed-flow"
printf '\n\n'

echo "[3/7] denied flow"
curl -s -X POST "${base_url}/api/v1/demo/run/denied-flow"
printf '\n\n'

echo "[4/7] timeout flow"
curl -s -X POST "${base_url}/api/v1/demo/run/timeout-flow"
printf '\n\n'

echo "[5/7] unavailable flow"
curl -s -X POST "${base_url}/api/v1/demo/run/unavailable-flow"
printf '\n\n'

echo "[6/7] offhours denied flow"
curl -s -X POST "${base_url}/api/v1/demo/run/offhours-denied-flow"
printf '\n\n'

echo "[7/7] audit export"
curl -s "${base_url}/api/v1/audit/export"
printf '\n'
