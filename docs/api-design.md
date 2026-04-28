# API Design

## Health

- `GET /healthz`
  - Service readiness check

## Auth

- `POST /api/v1/auth/agent/register`
  - Register or update an agent record
- `POST /api/v1/auth/token/delegate`
  - Issue a delegated access token for `caller_agent -> target_agent`
  - Supports runtime context such as `task_name`, `purpose`, and `current_hour`
- `POST /api/v1/auth/token/introspect`
  - Decode and validate a token
- `POST /api/v1/auth/token/revoke`
  - Mark a token as revoked

## Policy

- `POST /api/v1/policies/check`
  - Compute the effective capability set for a caller, target, and delegated user
  - Evaluates runtime context such as task scope and request hour

## Agents

- `POST /api/v1/agents/doc-agent/tasks/generate-report`
  - Runs the allowed workflow and returns a report with `trace_id`
- `POST /api/v1/agents/doc-agent/tasks/generate-report-with-fallback`
  - Simulates a downstream timeout and returns a degraded report
- `POST /api/v1/agents/enterprise-data-agent/bitable/read`
  - Requires a delegated token
- `POST /api/v1/agents/web-search-agent/search`
  - Returns public web-search style mock results
- `POST /api/v1/agents/web-search-agent/tasks/attempt-internal-read`
  - Demonstrates a denied internal-data attempt

## Demo

- `POST /api/v1/demo/run/allowed-flow`
  - Judge-friendly wrapper for the successful delegation path
- `POST /api/v1/demo/run/denied-flow`
  - Judge-friendly wrapper for the denied path
- `POST /api/v1/demo/run/timeout-flow`
  - Judge-friendly wrapper for timeout simulation and graceful fallback
- `POST /api/v1/demo/run/unavailable-flow`
  - Judge-friendly wrapper for explicit downstream unavailability with `AGENT_001`
- `POST /api/v1/demo/run/task-scope-denied-flow`
  - Demonstrates task-scoped dynamic authorization denial
- `POST /api/v1/demo/run/offhours-denied-flow`
  - Demonstrates time-scoped dynamic authorization denial

## Audit

- `GET /api/v1/audit/logs`
  - Lists audit entries in reverse chronological order
  - Supports filtering by `trace_id`, `reason_code`, `caller_agent`, `target_agent`, `decision`, and `limit`
- `GET /api/v1/audit/export`
  - Exports audit records as CSV with the same filters

## UI

- `GET /ui/audit`
  - Lightweight trace console that shows recent traces, delegated token fields, filtered audit timelines, and a copyable cURL query
