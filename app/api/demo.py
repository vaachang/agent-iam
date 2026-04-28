from __future__ import annotations

from fastapi import APIRouter

from app.agents.doc_agent import (
    generate_report,
    generate_report_with_fallback,
    generate_report_with_unavailable_dependency,
    issue_enterprise_read_token,
)
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


@router.post("/run/timeout-flow")
def run_timeout_flow():
    return generate_report_with_fallback("user-001")


@router.post("/run/unavailable-flow")
def run_unavailable_flow():
    try:
        return generate_report_with_unavailable_dependency("user-001")
    except ValueError as error:
        raise to_http_exception(str(error)) from error


@router.post("/run/task-scope-denied-flow")
def run_task_scope_denied_flow():
    try:
        issue_enterprise_read_token(
            "user-001",
            task_name="freeform_brainstorm",
            purpose="ad_hoc_request",
            current_hour=10,
        )
        return {"status": "unexpected"}
    except ValueError as error:
        raise to_http_exception(str(error)) from error


@router.post("/run/offhours-denied-flow")
def run_offhours_denied_flow():
    try:
        issue_enterprise_read_token(
            "user-001",
            task_name="generate_report",
            purpose="quarterly_reporting",
            current_hour=2,
        )
        return {"status": "unexpected"}
    except ValueError as error:
        raise to_http_exception(str(error)) from error
