from __future__ import annotations

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    request_id: str
    trace_id: str
    token_jti: str | None
    parent_jti: str | None
    caller_agent: str
    target_agent: str
    delegated_user: str | None
    resource: str
    action: str
    decision: str
    reason_code: str
    reason_detail: str
    created_at: str
