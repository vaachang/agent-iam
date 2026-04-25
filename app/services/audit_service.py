from __future__ import annotations

import csv
import io
from uuid import uuid4

from app.core.database import get_connection


def write_audit_log(
    *,
    trace_id: str,
    token_jti: str | None,
    parent_jti: str | None,
    caller_agent: str,
    target_agent: str,
    delegated_user: str | None,
    resource: str,
    action: str,
    decision: str,
    reason_code: str,
    reason_detail: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO audit_logs (
                request_id,
                trace_id,
                token_jti,
                parent_jti,
                caller_agent,
                target_agent,
                delegated_user,
                resource,
                action,
                decision,
                reason_code,
                reason_detail,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                str(uuid4()),
                trace_id,
                token_jti,
                parent_jti,
                caller_agent,
                target_agent,
                delegated_user,
                resource,
                action,
                decision,
                reason_code,
                reason_detail,
            ),
        )


def list_audit_logs(trace_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM audit_logs"
    params: tuple = ()
    if trace_id:
        query += " WHERE trace_id = ?"
        params = (trace_id,)
    query += " ORDER BY id DESC"

    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def export_audit_logs_csv(trace_id: str | None = None) -> str:
    logs = list_audit_logs(trace_id=trace_id)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "request_id",
            "trace_id",
            "token_jti",
            "parent_jti",
            "caller_agent",
            "target_agent",
            "delegated_user",
            "resource",
            "action",
            "decision",
            "reason_code",
            "reason_detail",
            "created_at",
        ],
    )
    writer.writeheader()
    writer.writerows(logs)
    return output.getvalue()
