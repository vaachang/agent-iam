from __future__ import annotations

from fastapi import HTTPException

from app.core.errors import ERRORS


def to_http_exception(error_code: str) -> HTTPException:
    error = ERRORS[error_code]
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )
