from __future__ import annotations

from app.services.audit_service import write_audit_log
from app.services.auth_service import introspect_token


MOCK_BITABLE = [
    {"department": "Sales", "quarter": "Q1", "revenue": 1800000},
    {"department": "Sales", "quarter": "Q2", "revenue": 1930000},
    {"department": "Sales", "quarter": "Q3", "revenue": 2010000},
]


def read_bitable(access_token: str, *, simulate_timeout: bool = False, failure_mode: str | None = None) -> dict:
    payload = introspect_token(access_token, expected_audience="enterprise-data-agent")
    capabilities = set(payload["capabilities"])
    capability = "bitable.read"
    if capability not in capabilities:
        write_audit_log(
            trace_id=payload["trace_id"],
            token_jti=payload["jti"],
            parent_jti=payload.get("parent_jti"),
            caller_agent=payload["sub"],
            target_agent="enterprise-data-agent",
            delegated_user=payload["delegated_user"],
            resource="bitable",
            action="read",
            decision="deny",
            reason_code="AUTHZ_001",
            reason_detail="Delegated token does not allow bitable.read.",
        )
        raise ValueError("AUTHZ_001")

    resolved_failure_mode = "timeout" if simulate_timeout else failure_mode

    if resolved_failure_mode == "timeout":
        write_audit_log(
            trace_id=payload["trace_id"],
            token_jti=payload["jti"],
            parent_jti=payload.get("parent_jti"),
            caller_agent=payload["sub"],
            target_agent="enterprise-data-agent",
            delegated_user=payload["delegated_user"],
            resource="bitable",
            action="read",
            decision="deny",
            reason_code="AGENT_002",
            reason_detail="Enterprise data agent timed out before completing the task.",
        )
        raise ValueError("AGENT_002")

    if resolved_failure_mode == "unavailable":
        write_audit_log(
            trace_id=payload["trace_id"],
            token_jti=payload["jti"],
            parent_jti=payload.get("parent_jti"),
            caller_agent=payload["sub"],
            target_agent="enterprise-data-agent",
            delegated_user=payload["delegated_user"],
            resource="bitable",
            action="read",
            decision="deny",
            reason_code="AGENT_001",
            reason_detail="Enterprise data agent is unavailable and cannot accept the task.",
        )
        raise ValueError("AGENT_001")

    write_audit_log(
        trace_id=payload["trace_id"],
        token_jti=payload["jti"],
        parent_jti=payload.get("parent_jti"),
        caller_agent=payload["sub"],
        target_agent="enterprise-data-agent",
        delegated_user=payload["delegated_user"],
        resource="bitable",
        action="read",
        decision="allow",
        reason_code="OK",
        reason_detail="Enterprise dataset returned.",
    )

    return {
        "source": "enterprise-data-agent",
        "rows": MOCK_BITABLE,
        "trace_id": payload["trace_id"],
    }
