from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRegistrationRequest(BaseModel):
    agent_id: str
    name: str
    role: str
    description: str


class DelegatedTokenRequest(BaseModel):
    caller_agent: str = Field(..., examples=["doc-agent"])
    target_agent: str = Field(..., examples=["enterprise-data-agent"])
    delegated_user: str = Field(..., examples=["user-001"])
    resource: str = Field(..., examples=["bitable"])
    action: str = Field(..., examples=["read"])
    task_name: str = Field(..., examples=["generate_report"])
    purpose: str | None = Field(default=None, examples=["quarterly_reporting"])
    current_hour: int | None = Field(default=None, ge=0, le=23, examples=[10])
    trace_id: str | None = None
    parent_jti: str | None = None


class TokenIntrospectionRequest(BaseModel):
    token: str


class TokenRevokeRequest(BaseModel):
    jti: str


class DelegatedTokenResponse(BaseModel):
    access_token: str
    expires_at: str
    trace_id: str
    jti: str
    capabilities: list[str]
