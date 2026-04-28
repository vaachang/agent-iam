from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.database import get_connection


@dataclass(frozen=True)
class PolicyContext:
    task_name: str | None = None
    purpose: str | None = None
    current_hour: int | None = None


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


def _matches_time_window(conditions: dict, current_hour: int | None) -> bool:
    time_window = conditions.get("time_window")
    if not time_window:
        return True
    if current_hour is None:
        return False

    start_hour = time_window.get("start_hour", 0)
    end_hour = time_window.get("end_hour", 23)
    return start_hour <= current_hour <= end_hour


def _matches_conditions(
    conditions: dict,
    *,
    audience: str | None,
    context: PolicyContext,
) -> bool:
    audiences = conditions.get("audiences")
    if audience and audiences and audience not in audiences:
        return False

    allowed_tasks = conditions.get("allowed_tasks")
    if allowed_tasks and context.task_name not in allowed_tasks:
        return False

    allowed_purposes = conditions.get("allowed_purposes")
    if allowed_purposes and context.purpose not in allowed_purposes:
        return False

    return _matches_time_window(conditions, context.current_hour)


def get_allowed_capabilities(
    subject_type: str,
    subject_id: str,
    *,
    audience: str | None = None,
    context: PolicyContext | None = None,
) -> set[str]:
    resolved_context = context or PolicyContext()
    capabilities = set()
    for row in get_subject_capability_rows(subject_type, subject_id):
        if row["effect"] != "allow":
            continue
        conditions = json.loads(row["conditions_json"])
        if not _matches_conditions(conditions, audience=audience, context=resolved_context):
            continue
        capabilities.add(f"{row['resource']}.{row['action']}")
    return capabilities


def get_denial_reasons(
    subject_type: str,
    subject_id: str,
    resource: str,
    action: str,
    *,
    audience: str | None = None,
    context: PolicyContext | None = None,
) -> list[str]:
    rows = get_subject_capability_rows(subject_type, subject_id)
    target_capability = f"{resource}.{action}"
    resolved_context = context or PolicyContext()
    reasons: list[str] = []
    for row in rows:
        if f"{row['resource']}.{row['action']}" != target_capability:
            continue
        if row["effect"] != "allow":
            continue
        conditions = json.loads(row["conditions_json"])
        audiences = conditions.get("audiences")
        if audience and audiences and audience not in audiences:
            reasons.append(
                f"{subject_type}:{subject_id} audience mismatch for {target_capability}"
            )
        allowed_tasks = conditions.get("allowed_tasks")
        if allowed_tasks and resolved_context.task_name not in allowed_tasks:
            reasons.append(
                f"{subject_type}:{subject_id} task_name {resolved_context.task_name!r} is outside {allowed_tasks}"
            )
        allowed_purposes = conditions.get("allowed_purposes")
        if allowed_purposes and resolved_context.purpose not in allowed_purposes:
            reasons.append(
                f"{subject_type}:{subject_id} purpose {resolved_context.purpose!r} is outside {allowed_purposes}"
            )
        time_window = conditions.get("time_window")
        if time_window and not _matches_time_window(conditions, resolved_context.current_hour):
            reasons.append(
                f"{subject_type}:{subject_id} current_hour {resolved_context.current_hour!r} is outside "
                f"{time_window['start_hour']}-{time_window['end_hour']}"
            )
    return reasons


def compute_effective_capabilities(
    user_id: str,
    caller_agent: str,
    target_agent: str,
    *,
    task_name: str | None = None,
    purpose: str | None = None,
    current_hour: int | None = None,
) -> set[str]:
    context = PolicyContext(
        task_name=task_name,
        purpose=purpose,
        current_hour=current_hour,
    )
    user_capabilities = get_allowed_capabilities("user", user_id, context=context)
    caller_capabilities = get_allowed_capabilities(
        "agent",
        caller_agent,
        audience=target_agent,
        context=context,
    )
    target_capabilities = get_allowed_capabilities("agent", target_agent, context=context)
    return user_capabilities & caller_capabilities & target_capabilities
