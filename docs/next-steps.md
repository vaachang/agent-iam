# Next Steps

## Highest Priority

- Add a real architecture diagram.
  - The project already has textual architecture notes, but the acceptance criteria explicitly require an architecture diagram.
- Add an exception-flow demo for agent timeout or downstream failure.
  - The project already demonstrates permission denial.
  - It still needs a clear "agent timeout/failure and system response" path.
- Improve judge-facing demo materials.
  - Add a concise acceptance walkthrough.
  - Add screenshots or a short recorded demo when ready.

## High Value Improvements

- Build a lightweight visualization page for:
  - trace IDs
  - token core fields
  - allow/deny audit chain
- Strengthen dynamic authorization.
  - Add task-scoped conditions.
  - Add time-scoped conditions.
  - Make delegated tokens more context-aware.
- Add timeout simulation and graceful fallback behavior.
  - Example: enterprise-data-agent timeout, doc-agent returns a clear failure response and writes audit logs.

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

1. Add the architecture diagram.
2. Implement the timeout/failure demo flow.
3. Build the minimal audit visualization page.
4. Strengthen dynamic authorization rules.
5. Refactor external integrations behind adapters.
