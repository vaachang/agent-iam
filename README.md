# agent-iam

Multi-agent IAM prototype for the "给 AI 发通行证" project.

## Features

- JWT-based agent identity
- Capability-based authorization
- Delegated authorization with effective permission intersection
- Runtime-aware authorization with task-scoped and time-scoped checks
- Audit logs for both allow and deny decisions
- Timeout/failure demo with degraded fallback handling
- Unavailable-agent demo with explicit `AGENT_001` failure
- Built-in audit visualization page for traces and tokens
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
- `POST /api/v1/demo/run/timeout-flow`
- `POST /api/v1/demo/run/unavailable-flow`
- `POST /api/v1/demo/run/task-scope-denied-flow`
- `POST /api/v1/demo/run/offhours-denied-flow`
- `POST /api/v1/agents/doc-agent/tasks/generate-report`
- `POST /api/v1/agents/doc-agent/tasks/generate-report-with-fallback`
- `POST /api/v1/agents/enterprise-data-agent/bitable/read`
- `POST /api/v1/agents/web-search-agent/search`
- `POST /api/v1/policies/check`
- `GET /api/v1/audit/logs`
- `GET /api/v1/audit/export`
- `GET /ui/audit`

## Notes

- Override `JWT_SECRET` in production-like demos.
- SQLite data is stored under `data/agent_iam.db`.
- Run tests with `.venv/bin/python -m unittest`.
- Demo `bitable.read` delegation is intentionally context-aware:
  task scope and a `08:00-20:00` request-hour window are enforced at runtime.

## Docs

- `docs/architecture.md`
- `docs/api-design.md`
- `docs/acceptance-walkthrough.md`
- `docs/demo-script.md`
- `docs/worklog-2026-04-28.md`
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
