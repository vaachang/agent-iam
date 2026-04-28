#!/usr/bin/env bash

set -euo pipefail

source .venv/bin/activate
uvicorn app.main:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8000}" --reload
