from __future__ import annotations

from fastapi import APIRouter

from app.schemas.policy import PolicyCheckRequest, PolicyCheckResponse
from app.services.policy_service import compute_effective_capabilities


router = APIRouter(prefix="/api/v1/policies", tags=["policy"])


@router.post("/check", response_model=PolicyCheckResponse)
def check_policy(payload: PolicyCheckRequest):
    effective_capabilities = sorted(
        compute_effective_capabilities(
            user_id=payload.delegated_user,
            caller_agent=payload.caller_agent,
            target_agent=payload.target_agent,
        )
    )
    requested_capability = f"{payload.resource}.{payload.action}"
    return {
        "allowed": requested_capability in effective_capabilities,
        "requested_capability": requested_capability,
        "effective_capabilities": effective_capabilities,
    }
