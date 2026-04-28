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

## Timeout / Degraded Flow

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/run/timeout-flow
```

Expected result:

- HTTP 200
- response contains `"status": "degraded"`
- response contains `upstream_error.code = "AGENT_002"`
- audit logs contain both the timeout event and the fallback report write

## Unavailable Flow

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/demo/run/unavailable-flow
```

Expected result:

- HTTP 503
- error code `AGENT_001`
- audit logs contain one entry for downstream unavailability and one for upstream abort

## Dynamic Authorization Denials

Task-scoped denial:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/demo/run/task-scope-denied-flow
```

Off-hours denial:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/demo/run/offhours-denied-flow
```

Expected result:

- both return HTTP 403 with `AUTHZ_001`
- audit `reason_detail` explains whether the denial came from task scope or time window

## Visualization

Open in browser:

```text
http://127.0.0.1:8000/ui/audit
```

Expected result:

- recent `trace_id` list is visible
- delegated token core fields are visible
- allow / deny / timeout audit chain is visible per trace
- filters by `reason_code`, `caller_agent`, `target_agent`, `decision` are available
- the page shows a copyable cURL query for the active filter set

## Audit Verification

```bash
curl http://127.0.0.1:8000/api/v1/audit/logs
curl http://127.0.0.1:8000/api/v1/audit/export
curl "http://127.0.0.1:8000/api/v1/audit/logs?reason_code=AUTHZ_001&decision=deny"
```

Expected result:

- both allow and deny entries are visible
- timeout entries with `AGENT_002` are visible after the degraded demo
- unavailable entries with `AGENT_001` are visible after the unavailable demo
- the allowed flow shows enterprise data access and report write
- CSV export can be downloaded or redirected to a file
