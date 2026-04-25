from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_token_payload(
    subject_agent: str,
    audience_agent: str,
    delegated_user: str,
    capabilities: list[str],
    task: dict[str, Any],
    trace_id: str | None = None,
    parent_jti: str | None = None,
) -> dict[str, Any]:
    issued_at = utcnow()
    return {
        "iss": "agent-iam",
        "sub": subject_agent,
        "aud": audience_agent,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(seconds=settings.token_ttl_seconds)).timestamp()),
        "jti": str(uuid4()),
        "trace_id": trace_id or str(uuid4()),
        "parent_jti": parent_jti,
        "delegated_user": delegated_user,
        "capabilities": capabilities,
        "task": task,
        "delegation": {
            "from_agent": subject_agent,
            "to_agent": audience_agent,
        },
    }


def encode_token(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["exp", "iat", "sub", "aud", "jti"],
                "verify_aud": False,
            },
        )
    except ExpiredSignatureError as error:
        raise ValueError("AUTH_003") from error
    except InvalidTokenError as error:
        raise ValueError("AUTH_002") from error
