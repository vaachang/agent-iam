# Agent IAM Architecture

## Goals

- Provide verifiable agent identity with signed access tokens.
- Enforce capability-based authorization across a `User -> Agent A -> Agent B` chain.
- Record every authorization decision for traceability.

## Runtime Modules

- `auth`: issues, introspects, and revokes JWT access tokens.
- `policy`: computes `user permissions ∩ caller agent capabilities ∩ target agent capabilities`.
- `agents`: contains the three demo agents.
- `audit`: stores allow and deny decisions in SQLite.
- `demo`: exposes a success path and a denial path for judges.

## Core Flow

1. A user asks `doc-agent` to generate a report.
2. `doc-agent` requests a delegated token for `enterprise-data-agent`.
3. The policy layer computes the effective capability set.
4. If `bitable.read` is allowed, a JWT is signed and persisted.
5. `enterprise-data-agent` validates the token and returns enterprise data.
6. `doc-agent` writes the report and all decisions are saved in audit logs.

## Denial Flow

1. `web-search-agent` requests a delegated token to read enterprise data.
2. The policy layer finds that `web-search-agent` lacks `bitable.read`.
3. Token issuance is denied with `AUTHZ_001`.
4. The denial is stored in `audit_logs`.

## Token Fields

- `iss`: issuer, fixed to `agent-iam`
- `sub`: caller agent identifier
- `aud`: target agent identifier
- `iat`: issue time
- `exp`: expiration time
- `jti`: token identifier
- `trace_id`: end-to-end workflow identifier
- `parent_jti`: parent token identifier if a chain expands
- `delegated_user`: original user context
- `capabilities`: effective capabilities granted to this token
- `task`: task name and requested action
- `delegation`: caller and target agent pair

## Audit Fields

- `request_id`
- `trace_id`
- `token_jti`
- `parent_jti`
- `caller_agent`
- `target_agent`
- `delegated_user`
- `resource`
- `action`
- `decision`
- `reason_code`
- `reason_detail`
- `created_at`
