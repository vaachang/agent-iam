from __future__ import annotations

from pydantic import BaseModel, Field


class PolicyCheckRequest(BaseModel):
    caller_agent: str = Field(..., examples=["doc-agent"])
    target_agent: str = Field(..., examples=["enterprise-data-agent"])
    delegated_user: str = Field(..., examples=["user-001"])
    resource: str = Field(..., examples=["bitable"])
    action: str = Field(..., examples=["read"])
    task_name: str | None = Field(default=None, examples=["generate_report"])
    purpose: str | None = Field(default=None, examples=["quarterly_reporting"])
    current_hour: int | None = Field(default=None, ge=0, le=23, examples=[10])


class PolicyCheckResponse(BaseModel):
    allowed: bool
    requested_capability: str
    effective_capabilities: list[str]
    context: dict[str, str | int | None]
