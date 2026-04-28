from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.audit import AuditLogResponse
from app.services.audit_service import export_audit_logs_csv, list_audit_logs


router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogResponse])
def list_logs(
    trace_id: str | None = None,
    reason_code: str | None = None,
    caller_agent: str | None = None,
    target_agent: str | None = None,
    decision: str | None = None,
    limit: int | None = None,
):
    return list_audit_logs(
        trace_id=trace_id,
        reason_code=reason_code,
        caller_agent=caller_agent,
        target_agent=target_agent,
        decision=decision,
        limit=limit,
    )


@router.get("/export", response_class=PlainTextResponse)
def export_logs(
    trace_id: str | None = None,
    reason_code: str | None = None,
    caller_agent: str | None = None,
    target_agent: str | None = None,
    decision: str | None = None,
    limit: int | None = None,
):
    return export_audit_logs_csv(
        trace_id=trace_id,
        reason_code=reason_code,
        caller_agent=caller_agent,
        target_agent=target_agent,
        decision=decision,
        limit=limit,
    )
