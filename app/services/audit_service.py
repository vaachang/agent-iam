from __future__ import annotations

import csv
import json
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


def list_audit_logs(
    trace_id: str | None = None,
    *,
    reason_code: str | None = None,
    caller_agent: str | None = None,
    target_agent: str | None = None,
    decision: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    query = "SELECT * FROM audit_logs"
    filters = []
    params: list[str | int] = []
    if trace_id:
        filters.append("trace_id = ?")
        params.append(trace_id)
    if reason_code:
        filters.append("reason_code = ?")
        params.append(reason_code)
    if caller_agent:
        filters.append("caller_agent = ?")
        params.append(caller_agent)
    if target_agent:
        filters.append("target_agent = ?")
        params.append(target_agent)
    if decision:
        filters.append("decision = ?")
        params.append(decision)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY id DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def list_trace_audit_logs(trace_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM audit_logs WHERE trace_id = ? ORDER BY id ASC",
            (trace_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_trace_summaries(
    limit: int = 10,
    *,
    reason_code: str | None = None,
    caller_agent: str | None = None,
    target_agent: str | None = None,
    decision: str | None = None,
) -> list[dict]:
    filters = []
    params: list[str | int] = []
    if reason_code:
        filters.append("reason_code = ?")
        params.append(reason_code)
    if caller_agent:
        filters.append("caller_agent = ?")
        params.append(caller_agent)
    if target_agent:
        filters.append("target_agent = ?")
        params.append(target_agent)
    if decision:
        filters.append("decision = ?")
        params.append(decision)

    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT
                trace_id,
                MAX(created_at) AS latest_created_at,
                MAX(COALESCE(delegated_user, '')) AS delegated_user,
                COUNT(*) AS log_count,
                SUM(CASE WHEN decision = 'allow' THEN 1 ELSE 0 END) AS allow_count,
                SUM(CASE WHEN decision = 'deny' THEN 1 ELSE 0 END) AS deny_count,
                MAX(id) AS latest_id
            FROM audit_logs
            {where_clause}
            GROUP BY trace_id
            ORDER BY latest_id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_tokens_for_trace(trace_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
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
            FROM tokens
            WHERE trace_id = ?
            ORDER BY created_at ASC
            """,
            (trace_id,),
        ).fetchall()

    tokens = []
    for row in rows:
        item = dict(row)
        item["capabilities"] = json.loads(item.pop("capabilities_json"))
        tokens.append(item)
    return tokens


def export_audit_logs_csv(
    trace_id: str | None = None,
    *,
    reason_code: str | None = None,
    caller_agent: str | None = None,
    target_agent: str | None = None,
    decision: str | None = None,
    limit: int | None = None,
) -> str:
    logs = list_audit_logs(
        trace_id=trace_id,
        reason_code=reason_code,
        caller_agent=caller_agent,
        target_agent=target_agent,
        decision=decision,
        limit=limit,
    )
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
