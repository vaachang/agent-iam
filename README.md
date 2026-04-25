# agent-iam

Multi-agent IAM prototype for the "给 AI 发通行证" project.

## Features

- JWT-based agent identity
- Capability-based authorization
- Delegated authorization with effective permission intersection
- Audit logs for both allow and deny decisions
- Three demo agents:
  - `doc-agent`
  - `enterprise-data-agent`
  - `web-search-agent`

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash scripts/start.sh
```

In another terminal:

```bash
bash scripts/smoke_test.sh
```

## Demo Endpoints

- `POST /api/v1/demo/run/allowed-flow`
- `POST /api/v1/demo/run/denied-flow`
- `POST /api/v1/agents/doc-agent/tasks/generate-report`
- `POST /api/v1/agents/enterprise-data-agent/bitable/read`
- `POST /api/v1/agents/web-search-agent/search`
- `POST /api/v1/policies/check`
- `GET /api/v1/audit/logs`
- `GET /api/v1/audit/export`

## Notes

- Override `JWT_SECRET` in production-like demos.
- SQLite data is stored under `data/agent_iam.db`.
- Run tests with `.venv/bin/python -m unittest`.

## Docs

- `docs/architecture.md`
- `docs/api-design.md`
- `docs/demo-script.md`
- `docs/worklog-2026-04-25.md`
- `docs/next-steps.md`

## Project Layout

```text
app/
  api/
  agents/
  core/
  schemas/
  services/
docs/
scripts/
tests/
```
