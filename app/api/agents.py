from __future__ import annotations

from fastapi import APIRouter

from app.agents.doc_agent import generate_report
from app.agents.enterprise_data_agent import read_bitable
from app.agents.web_search_agent import attempt_internal_read, search_public_web
from app.api.common import to_http_exception
from app.schemas.agent import (
    EnterpriseReadRequest,
    GenerateReportRequest,
    GenerateReportResponse,
    InternalReadAttemptRequest,
    SearchRequest,
    SearchResponse,
)


router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("/doc-agent/tasks/generate-report", response_model=GenerateReportResponse)
def generate_report_endpoint(payload: GenerateReportRequest):
    result = generate_report(payload.user_id)
    result["prompt"] = payload.prompt
    return result


@router.post("/enterprise-data-agent/bitable/read")
def read_bitable_endpoint(payload: EnterpriseReadRequest):
    try:
        return read_bitable(payload.access_token)
    except ValueError as error:
        raise to_http_exception(str(error)) from error


@router.post("/web-search-agent/search", response_model=SearchResponse)
def web_search_endpoint(payload: SearchRequest):
    return search_public_web(payload.query)


@router.post("/web-search-agent/tasks/attempt-internal-read")
def attempt_internal_read_endpoint(payload: InternalReadAttemptRequest):
    try:
        return attempt_internal_read(payload.user_id)
    except ValueError as error:
        raise to_http_exception(str(error)) from error
