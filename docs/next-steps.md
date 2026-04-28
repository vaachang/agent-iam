# Next Steps

## Completed In This Iteration

- Added a real architecture diagram in `docs/architecture.md`.
- Added a timeout/degraded-flow demo:
  - `POST /api/v1/demo/run/timeout-flow`
  - `POST /api/v1/agents/doc-agent/tasks/generate-report-with-fallback`
- Added a lightweight visualization page:
  - `GET /ui/audit`
- Improved judge-facing materials:
  - updated `README.md`
  - updated `docs/demo-script.md`
  - added `docs/acceptance-walkthrough.md`
- Strengthened dynamic authorization:
  - task-scoped conditions
  - time-scoped conditions
  - richer token context
- Added a second failure mode:
  - `POST /api/v1/demo/run/unavailable-flow`
  - explicit `AGENT_001` path
- Expanded audit filtering and UI controls:
  - filter by `reason_code`
  - filter by agent pair
  - filter by `decision`
  - copyable cURL snippets per filtered trace view

## Remaining High Value Improvements

- Add a chained delegation demo.
  - Example: `doc-agent -> enterprise-data-agent -> downstream-service-agent`
  - Persist and validate `parent_jti` across more than one hop
- Tighten token hardening further.
  - Bind tokens to narrower task intents
  - Add nonce or one-time-use semantics for sensitive paths
- Expand audit analytics.
  - Add aggregated counts by `reason_code`
  - Add per-agent success/deny summaries

## Optional Enhancements

- Introduce adapter layers for future Feishu/OpenAPI integration.
  - Keep the current mock implementation, but separate the data access layer cleanly.
- Expand token hardening and trust-chain behavior.
  - Tighten token usage scope.
  - Extend chained delegation behavior.
- Improve audit usability further.
  - Add richer filtering.
  - Add export formats beyond CSV if needed.

## Recommended Execution Order

1. Add chained delegation with `parent_jti` validation.
2. Expand audit analytics and summaries.
3. Refactor external integrations behind adapters.
