from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.services.audit_service import list_audit_logs, list_tokens_for_trace, list_trace_summaries


router = APIRouter(tags=["ui"])


def _query_string(**kwargs: str | None) -> str:
    return urlencode({key: value for key, value in kwargs.items() if value})


def _build_trace_options(
    trace_summaries: list[dict],
    selected_trace_id: str | None,
    *,
    reason_code: str | None,
    caller_agent: str | None,
    target_agent: str | None,
    decision: str | None,
) -> str:
    items = []
    for summary in trace_summaries:
        trace_id = summary["trace_id"]
        active_class = "trace-link active" if trace_id == selected_trace_id else "trace-link"
        query = _query_string(
            trace_id=trace_id,
            reason_code=reason_code,
            caller_agent=caller_agent,
            target_agent=target_agent,
            decision=decision,
        )
        items.append(
            (
                f"<a class='{active_class}' href='/ui/audit?{query}'>"
                f"<strong>{escape(trace_id[:8])}</strong>"
                f"<span>{escape(summary['delegated_user'] or 'n/a')}</span>"
                f"<span>{summary['allow_count']} allow / {summary['deny_count']} deny</span>"
                "</a>"
            )
        )
    return "".join(items) or "<p class='empty'>No traces match the active filters.</p>"


def _build_filter_form(
    *,
    trace_id: str | None,
    reason_code: str | None,
    caller_agent: str | None,
    target_agent: str | None,
    decision: str | None,
) -> str:
    return f"""
    <form class='filters' method='get' action='/ui/audit'>
      <input type='hidden' name='trace_id' value='{escape(trace_id or "")}' />
      <label><span>reason_code</span><input name='reason_code' value='{escape(reason_code or "")}' placeholder='AUTHZ_001' /></label>
      <label><span>caller_agent</span><input name='caller_agent' value='{escape(caller_agent or "")}' placeholder='doc-agent' /></label>
      <label><span>target_agent</span><input name='target_agent' value='{escape(target_agent or "")}' placeholder='enterprise-data-agent' /></label>
      <label>
        <span>decision</span>
        <select name='decision'>
          <option value='' {'selected' if not decision else ''}>all</option>
          <option value='allow' {'selected' if decision == 'allow' else ''}>allow</option>
          <option value='deny' {'selected' if decision == 'deny' else ''}>deny</option>
        </select>
      </label>
      <button type='submit'>Apply Filters</button>
    </form>
    """


def _build_token_cards(tokens: list[dict]) -> str:
    if not tokens:
        return "<p class='empty'>No delegated tokens recorded for this trace.</p>"

    items = []
    for token in tokens:
        capabilities = ", ".join(token["capabilities"])
        items.append(
            """
            <article class='token-card'>
              <div class='token-head'>
                <h3>{subject} → {audience}</h3>
                <span class='pill {revoked_class}'>{revoked_label}</span>
              </div>
              <dl>
                <div><dt>jti</dt><dd>{jti}</dd></div>
                <div><dt>delegated_user</dt><dd>{delegated_user}</dd></div>
                <div><dt>capabilities</dt><dd>{capabilities}</dd></div>
                <div><dt>expires_at</dt><dd>{expires_at}</dd></div>
                <div><dt>parent_jti</dt><dd>{parent_jti}</dd></div>
              </dl>
            </article>
            """.format(
                subject=escape(token["subject_agent"]),
                audience=escape(token["audience_agent"]),
                revoked_class="revoked" if token["revoked"] else "active",
                revoked_label="revoked" if token["revoked"] else "active",
                jti=escape(token["jti"]),
                delegated_user=escape(token["delegated_user"]),
                capabilities=escape(capabilities),
                expires_at=escape(token["expires_at"]),
                parent_jti=escape(token["parent_jti"] or "-"),
            )
        )
    return "".join(items)


def _build_audit_timeline(logs: list[dict]) -> str:
    if not logs:
        return "<p class='empty'>No audit logs recorded for this trace under the active filters.</p>"

    items = []
    for log in logs:
        decision_class = "allow" if log["decision"] == "allow" else "deny"
        items.append(
            """
            <article class='timeline-item {decision_class}'>
              <div class='timeline-top'>
                <span class='pill {decision_class}'>{decision}</span>
                <strong>{caller} → {target}</strong>
                <span>{created_at}</span>
              </div>
              <p>{resource}.{action} | {reason_code}</p>
              <p class='detail'>{reason_detail}</p>
            </article>
            """.format(
                decision_class=decision_class,
                decision=escape(log["decision"]),
                caller=escape(log["caller_agent"]),
                target=escape(log["target_agent"]),
                created_at=escape(log["created_at"]),
                resource=escape(log["resource"]),
                action=escape(log["action"]),
                reason_code=escape(log["reason_code"]),
                reason_detail=escape(log["reason_detail"]),
            )
        )
    return "".join(items)


def _build_curl_snippet(
    *,
    trace_id: str | None,
    reason_code: str | None,
    caller_agent: str | None,
    target_agent: str | None,
    decision: str | None,
) -> str:
    query = _query_string(
        trace_id=trace_id,
        reason_code=reason_code,
        caller_agent=caller_agent,
        target_agent=target_agent,
        decision=decision,
    )
    suffix = f"?{query}" if query else ""
    return (
        "curl 'http://127.0.0.1:8000/api/v1/audit/logs"
        f"{escape(suffix)}'"
    )


@router.get("/ui/audit", response_class=HTMLResponse)
def audit_dashboard(
    trace_id: str | None = None,
    reason_code: str | None = None,
    caller_agent: str | None = None,
    target_agent: str | None = None,
    decision: str | None = None,
):
    trace_summaries = list_trace_summaries(
        limit=12,
        reason_code=reason_code,
        caller_agent=caller_agent,
        target_agent=target_agent,
        decision=decision,
    )
    selected_trace_id = trace_id or (trace_summaries[0]["trace_id"] if trace_summaries else None)
    tokens = list_tokens_for_trace(selected_trace_id) if selected_trace_id else []
    logs = (
        list_audit_logs(
            trace_id=selected_trace_id,
            reason_code=reason_code,
            caller_agent=caller_agent,
            target_agent=target_agent,
            decision=decision,
        )
        if selected_trace_id
        else []
    )

    html = """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Agent IAM Audit Dashboard</title>
          <style>
            :root {
              --bg: #f5efe4;
              --panel: #fffaf2;
              --ink: #1f1a14;
              --muted: #6f6558;
              --line: #d9ccb8;
              --accent: #1f6f5f;
              --accent-soft: #dff2eb;
              --deny: #9f2d2d;
              --deny-soft: #f8dddd;
              --shadow: 0 16px 40px rgba(57, 45, 25, 0.08);
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              font-family: Georgia, "Times New Roman", serif;
              color: var(--ink);
              background:
                radial-gradient(circle at top left, #f8f1de 0, transparent 28rem),
                linear-gradient(180deg, #f2eadf 0%, var(--bg) 100%);
            }
            .shell {
              max-width: 1280px;
              margin: 0 auto;
              padding: 32px 20px 48px;
            }
            .hero {
              margin-bottom: 24px;
              padding: 24px;
              border: 1px solid var(--line);
              border-radius: 24px;
              background: rgba(255, 250, 242, 0.8);
              box-shadow: var(--shadow);
            }
            .hero h1 {
              margin: 0 0 8px;
              font-size: clamp(2rem, 4vw, 3.5rem);
              line-height: 0.95;
            }
            .hero p {
              margin: 0;
              max-width: 60rem;
              color: var(--muted);
              font-size: 1rem;
            }
            .layout {
              display: grid;
              grid-template-columns: 320px minmax(0, 1fr);
              gap: 20px;
            }
            .panel {
              padding: 20px;
              border: 1px solid var(--line);
              border-radius: 20px;
              background: var(--panel);
              box-shadow: var(--shadow);
            }
            .panel h2 {
              margin: 0 0 16px;
              font-size: 1.1rem;
            }
            .trace-list, .main {
              display: grid;
              gap: 12px;
            }
            .trace-link {
              display: grid;
              gap: 4px;
              padding: 14px;
              color: inherit;
              text-decoration: none;
              border: 1px solid var(--line);
              border-radius: 16px;
              background: #fff;
            }
            .trace-link.active {
              border-color: var(--accent);
              background: var(--accent-soft);
            }
            .trace-link span, .subtitle, .detail {
              color: var(--muted);
            }
            .filters {
              display: grid;
              grid-template-columns: repeat(5, minmax(0, 1fr));
              gap: 12px;
              margin-top: 18px;
            }
            .filters label {
              display: grid;
              gap: 6px;
              font-size: 0.9rem;
            }
            .filters input, .filters select, .filters button {
              min-height: 42px;
              border-radius: 12px;
              border: 1px solid var(--line);
              background: #fff;
              padding: 0 12px;
              font: inherit;
              color: var(--ink);
            }
            .filters button {
              align-self: end;
              background: var(--ink);
              color: #fffaf2;
              cursor: pointer;
            }
            .token-card, .snippet, .timeline-item {
              padding: 16px;
              border: 1px solid var(--line);
              border-radius: 18px;
              background: #fff;
            }
            .token-head, .timeline-top {
              display: flex;
              gap: 10px;
              justify-content: space-between;
              align-items: center;
              flex-wrap: wrap;
            }
            .token-head h3 {
              margin: 0;
              font-size: 1rem;
            }
            dl {
              margin: 14px 0 0;
              display: grid;
              gap: 10px;
            }
            dl div {
              display: grid;
              gap: 4px;
              padding-top: 10px;
              border-top: 1px dashed var(--line);
            }
            dt {
              color: var(--muted);
              font-size: 0.85rem;
            }
            dd {
              margin: 0;
              word-break: break-word;
            }
            .timeline {
              display: grid;
              gap: 12px;
            }
            .timeline-item.allow {
              border-left: 8px solid var(--accent);
            }
            .timeline-item.deny {
              border-left: 8px solid var(--deny);
            }
            .timeline-item p {
              margin: 10px 0 0;
            }
            .pill {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              padding: 4px 10px;
              border-radius: 999px;
              font-size: 0.82rem;
              text-transform: uppercase;
              letter-spacing: 0.04em;
            }
            .pill.allow, .pill.active {
              background: var(--accent-soft);
              color: var(--accent);
            }
            .pill.deny, .pill.revoked {
              background: var(--deny-soft);
              color: var(--deny);
            }
            pre {
              margin: 0;
              white-space: pre-wrap;
              word-break: break-word;
              font-family: "Courier New", monospace;
            }
            .empty {
              margin: 0;
              color: var(--muted);
            }
            @media (max-width: 900px) {
              .layout {
                grid-template-columns: 1fr;
              }
              .filters {
                grid-template-columns: 1fr;
              }
            }
          </style>
        </head>
        <body>
          <main class="shell">
            <section class="hero">
              <h1>Agent IAM Trace Console</h1>
              <p>
                Review the latest delegation traces, inspect delegated token fields,
                filter audit decisions by reason code or agent pair, and copy a direct cURL query for the active view.
              </p>
              __FILTER_FORM__
            </section>
            <section class="layout">
              <aside class="panel">
                <h2>Recent Traces</h2>
                <div class="trace-list">__TRACE_OPTIONS__</div>
              </aside>
              <section class="main">
                <section class="panel">
                  <h2>Audit Query</h2>
                  <p class="subtitle">Use this exact request to reproduce the current filtered log view from a terminal.</p>
                  <div class="snippet"><pre>__CURL_SNIPPET__</pre></div>
                </section>
                <section class="panel">
                  <h2>Delegated Tokens</h2>
                  __TOKEN_CARDS__
                </section>
                <section class="panel">
                  <h2>Audit Timeline</h2>
                  <div class="timeline">__TIMELINE__</div>
                </section>
              </section>
            </section>
          </main>
        </body>
        </html>
        """
    html = html.replace(
        "__FILTER_FORM__",
        _build_filter_form(
            trace_id=selected_trace_id,
            reason_code=reason_code,
            caller_agent=caller_agent,
            target_agent=target_agent,
            decision=decision,
        ),
    )
    html = html.replace(
        "__TRACE_OPTIONS__",
        _build_trace_options(
            trace_summaries,
            selected_trace_id,
            reason_code=reason_code,
            caller_agent=caller_agent,
            target_agent=target_agent,
            decision=decision,
        ),
    )
    html = html.replace("__TOKEN_CARDS__", _build_token_cards(tokens))
    html = html.replace("__TIMELINE__", _build_audit_timeline(logs))
    html = html.replace(
        "__CURL_SNIPPET__",
        escape(
            _build_curl_snippet(
                trace_id=selected_trace_id,
                reason_code=reason_code,
                caller_agent=caller_agent,
                target_agent=target_agent,
                decision=decision,
            )
        ),
    )
    return HTMLResponse(html)
