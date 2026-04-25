from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.database import get_connection
from app.core.security import build_token_payload, decode_token, encode_token
from app.services.audit_service import write_audit_log
from app.services.policy_service import compute_effective_capabilities


def register_agent(agent_id: str, name: str, role: str, description: str) -> dict:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO agents (
                agent_id,
                name,
                role,
                description,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, 'active', datetime('now'))
            """,
            (agent_id, name, role, description),
        )
        row = connection.execute(
            "SELECT * FROM agents WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
    return dict(row)


def issue_delegated_token(
    *,
    caller_agent: str,
    target_agent: str,
    delegated_user: str,
    resource: str,
    action: str,
    task_name: str,
    trace_id: str | None,
    parent_jti: str | None,
) -> dict:
    effective_capabilities = compute_effective_capabilities(
        delegated_user,
        caller_agent,
        target_agent,
    )
    requested_capability = f"{resource}.{action}"
    resolved_trace_id = trace_id

    if requested_capability not in effective_capabilities:
        resolved_trace_id = resolved_trace_id or "trace-denied"
        write_audit_log(
            trace_id=resolved_trace_id,
            token_jti=None,
            parent_jti=parent_jti,
            caller_agent=caller_agent,
            target_agent=target_agent,
            delegated_user=delegated_user,
            resource=resource,
            action=action,
            decision="deny",
            reason_code="AUTHZ_001",
            reason_detail="Capability intersection is empty for the requested action.",
        )
        raise ValueError("AUTHZ_001")

    payload = build_token_payload(
        subject_agent=caller_agent,
        audience_agent=target_agent,
        delegated_user=delegated_user,
        capabilities=sorted(effective_capabilities),
        task={
            "name": task_name,
            "resource": resource,
            "action": action,
        },
        trace_id=trace_id,
        parent_jti=parent_jti,
    )
    token = encode_token(payload)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tokens (
                jti,
                subject_agent,
                audience_agent,
                delegated_user,
                capabilities_json,
                trace_id,
                parent_jti,
                expires_at,
                revoked,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
            """,
            (
                payload["jti"],
                caller_agent,
                target_agent,
                delegated_user,
                json.dumps(payload["capabilities"], ensure_ascii=True),
                payload["trace_id"],
                parent_jti,
                expires_at,
            ),
        )

    write_audit_log(
        trace_id=payload["trace_id"],
        token_jti=payload["jti"],
        parent_jti=parent_jti,
        caller_agent=caller_agent,
        target_agent=target_agent,
        delegated_user=delegated_user,
        resource=resource,
        action=action,
        decision="allow",
        reason_code="OK",
        reason_detail="Delegated token issued.",
    )

    return {
        "access_token": token,
        "expires_at": expires_at,
        "trace_id": payload["trace_id"],
        "jti": payload["jti"],
        "capabilities": payload["capabilities"],
    }


def introspect_token(token: str, *, expected_audience: str | None = None) -> dict:
    payload = decode_token(token)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT revoked FROM tokens WHERE jti = ?",
            (payload["jti"],),
        ).fetchone()
    if row is None:
        raise ValueError("AUTH_002")
    if row["revoked"]:
        raise ValueError("AUTH_004")
    if expected_audience and payload["aud"] != expected_audience:
        raise ValueError("AUTH_005")
    return payload


def revoke_token(jti: str) -> dict:
    with get_connection() as connection:
        connection.execute("UPDATE tokens SET revoked = 1 WHERE jti = ?", (jti,))
        row = connection.execute("SELECT * FROM tokens WHERE jti = ?", (jti,)).fetchone()
    if row is None:
        raise ValueError("AUTH_002")
    return dict(row)
