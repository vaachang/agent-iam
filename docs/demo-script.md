# Demo Script

## Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash scripts/start.sh
```

Optional one-shot verification after the server starts:

```bash
bash scripts/smoke_test.sh
```

## Allowed Flow

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/run/allowed-flow
```

Expected result:

- report content is returned
- response contains a `trace_id`

You can also call the agent endpoint directly:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agents/doc-agent/tasks/generate-report \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-001","prompt":"Generate a quarterly sales report."}'
```

## Denied Flow

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/run/denied-flow
```

Expected result:

- HTTP 403
- error code `AUTHZ_001`

## Audit Verification

```bash
curl http://127.0.0.1:8000/api/v1/audit/logs
curl http://127.0.0.1:8000/api/v1/audit/export
```

Expected result:

- both allow and deny entries are visible
- the allowed flow shows enterprise data access and report write
- CSV export can be downloaded or redirected to a file
