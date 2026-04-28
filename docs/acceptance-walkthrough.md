# Acceptance Walkthrough

## 1. Start The System

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash scripts/start.sh
```

Optional smoke verification:

```bash
bash scripts/smoke_test.sh
```

Expected result:

- `GET /healthz` returns `{"status":"ok","service":"Agent IAM"}`

## 2. Allowed Delegation Flow

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/run/allowed-flow
```

Expected result:

- response contains `trace_id`
- response contains generated report text
- response contains enterprise data rows

## 3. Denied Delegation Flow

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/demo/run/denied-flow
```

Expected result:

- HTTP `403`
- body contains `AUTHZ_001`

## 4. Timeout And Fallback Flow

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/run/timeout-flow
```

Expected result:

- HTTP `200`
- body contains `"status":"degraded"`
- body contains `"fallback_used":true`
- body contains `AGENT_002`

## 5. Unavailable Agent Flow

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/demo/run/unavailable-flow
```

Expected result:

- HTTP `503`
- body contains `AGENT_001`

## 6. Dynamic Authorization Checks

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/demo/run/task-scope-denied-flow
curl -i -X POST http://127.0.0.1:8000/api/v1/demo/run/offhours-denied-flow
```

Expected result:

- both return HTTP `403`
- body contains `AUTHZ_001`
- the corresponding audit entries explain task-scope or off-hours denial

## 7. Audit Verification

```bash
curl http://127.0.0.1:8000/api/v1/audit/logs
curl http://127.0.0.1:8000/api/v1/audit/export
curl "http://127.0.0.1:8000/api/v1/audit/logs?reason_code=AUTHZ_001&decision=deny"
```

Expected result:

- allow logs exist for the successful report flow
- deny logs exist for the unauthorized web-search delegation
- timeout logs with `AGENT_002` exist for the degraded flow
- unavailable logs with `AGENT_001` exist for the unavailable flow
- filtered denial queries only return matching records

## 8. Visual Trace Review

Open:

```text
http://127.0.0.1:8000/ui/audit
```

Expected result:

- recent traces are listed on the left
- delegated token core fields are shown for the selected trace
- the audit timeline shows allow / deny / timeout decisions in order
- filters and copyable cURL query are available on the page
