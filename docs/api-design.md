# API Design

## Health

- `GET /healthz`
  - Service readiness check

## Auth

- `POST /api/v1/auth/agent/register`
  - Register or update an agent record
- `POST /api/v1/auth/token/delegate`
  - Issue a delegated access token for `caller_agent -> target_agent`
- `POST /api/v1/auth/token/introspect`
  - Decode and validate a token
- `POST /api/v1/auth/token/revoke`
  - Mark a token as revoked

## Policy

- `POST /api/v1/policies/check`
  - Compute the effective capability set for a caller, target, and delegated user

## Agents

- `POST /api/v1/agents/doc-agent/tasks/generate-report`
  - Runs the allowed workflow and returns a report with `trace_id`
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

## Audit

- `GET /api/v1/audit/logs`
  - Lists audit entries in reverse chronological order
- `GET /api/v1/audit/export`
  - Exports audit records as CSV
