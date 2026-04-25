from __future__ import annotations

from fastapi import APIRouter

from app.api.common import to_http_exception
from app.schemas.auth import (
    AgentRegistrationRequest,
    DelegatedTokenRequest,
    DelegatedTokenResponse,
    TokenIntrospectionRequest,
    TokenRevokeRequest,
)
from app.services.auth_service import (
    introspect_token,
    issue_delegated_token,
    register_agent,
    revoke_token,
)


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/agent/register")
def register_agent_endpoint(payload: AgentRegistrationRequest):
    return register_agent(
        agent_id=payload.agent_id,
        name=payload.name,
        role=payload.role,
        description=payload.description,
    )


@router.post("/token/delegate", response_model=DelegatedTokenResponse)
def delegate_token_endpoint(payload: DelegatedTokenRequest):
    try:
        return issue_delegated_token(
            caller_agent=payload.caller_agent,
            target_agent=payload.target_agent,
            delegated_user=payload.delegated_user,
            resource=payload.resource,
            action=payload.action,
            task_name=payload.task_name,
            trace_id=payload.trace_id,
            parent_jti=payload.parent_jti,
        )
    except ValueError as error:
        raise to_http_exception(str(error)) from error


@router.post("/token/introspect")
def introspect_token_endpoint(payload: TokenIntrospectionRequest):
    try:
        return introspect_token(payload.token)
    except ValueError as error:
        raise to_http_exception(str(error)) from error


@router.post("/token/revoke")
def revoke_token_endpoint(payload: TokenRevokeRequest):
    try:
        return revoke_token(payload.jti)
    except ValueError as error:
        raise to_http_exception(str(error)) from error
