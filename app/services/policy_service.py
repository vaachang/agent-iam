from __future__ import annotations

import json

from app.core.database import get_connection


def get_subject_capability_rows(subject_type: str, subject_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT resource, action, effect, conditions_json
            FROM capabilities
            WHERE subject_type = ? AND subject_id = ?
            """,
            (subject_type, subject_id),
        ).fetchall()
    return [dict(row) for row in rows]


def get_allowed_capabilities(subject_type: str, subject_id: str) -> set[str]:
    return {
        f"{row['resource']}.{row['action']}"
        for row in get_subject_capability_rows(subject_type, subject_id)
        if row["effect"] == "allow"
    }


def subject_has_capability(
    subject_type: str,
    subject_id: str,
    resource: str,
    action: str,
    *,
    audience: str | None = None,
) -> bool:
    rows = get_subject_capability_rows(subject_type, subject_id)
    target_capability = f"{resource}.{action}"
    for row in rows:
        if f"{row['resource']}.{row['action']}" != target_capability:
            continue
        if row["effect"] != "allow":
            continue
        conditions = json.loads(row["conditions_json"])
        audiences = conditions.get("audiences")
        if audience and audiences and audience not in audiences:
            continue
        return True
    return False


def compute_effective_capabilities(
    user_id: str,
    caller_agent: str,
    target_agent: str,
) -> set[str]:
    user_capabilities = get_allowed_capabilities("user", user_id)
    caller_capabilities = {
        capability
        for capability in get_allowed_capabilities("agent", caller_agent)
        if subject_has_capability(
            "agent",
            caller_agent,
            capability.split(".", maxsplit=1)[0],
            capability.split(".", maxsplit=1)[1],
            audience=target_agent,
        )
    }
    target_capabilities = get_allowed_capabilities("agent", target_agent)
    return user_capabilities & caller_capabilities & target_capabilities
