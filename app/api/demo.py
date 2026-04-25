from __future__ import annotations

from fastapi import APIRouter

from app.agents.doc_agent import generate_report
from app.agents.web_search_agent import attempt_internal_read
from app.api.common import to_http_exception


router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/run/allowed-flow")
def run_allowed_flow():
    return generate_report("user-001")


@router.post("/run/denied-flow")
def run_denied_flow():
    try:
        return attempt_internal_read("user-001")
    except ValueError as error:
        raise to_http_exception(str(error)) from error
