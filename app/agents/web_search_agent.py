from __future__ import annotations

from app.services.auth_service import issue_delegated_token


MOCK_PUBLIC_RESULTS = [
    {
        "title": "Open standards for agent identity",
        "url": "https://example.com/agent-identity",
        "snippet": "Overview of identity, delegation, and traceability for AI agents.",
    },
    {
        "title": "Capability-based authorization patterns",
        "url": "https://example.com/capability-authz",
        "snippet": "How capability models constrain downstream agent actions.",
    },
]


def search_public_web(query: str) -> dict:
    return {
        "source": "web-search-agent",
        "query": query,
        "results": MOCK_PUBLIC_RESULTS,
    }


def attempt_internal_read(user_id: str) -> dict:
    issue_delegated_token(
        caller_agent="web-search-agent",
        target_agent="enterprise-data-agent",
        delegated_user=user_id,
        resource="bitable",
        action="read",
        task_name="illicit_internal_read",
        trace_id=None,
        parent_jti=None,
    )
    return {"status": "unexpected"}
