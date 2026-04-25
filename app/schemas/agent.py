from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateReportRequest(BaseModel):
    user_id: str = Field(default="user-001", examples=["user-001"])
    prompt: str = Field(
        default="Generate a quarterly sales report.",
        examples=["Generate a quarterly sales report."],
    )


class GenerateReportResponse(BaseModel):
    trace_id: str
    report: str
    data_rows: list[dict]
    prompt: str


class EnterpriseReadRequest(BaseModel):
    access_token: str


class SearchRequest(BaseModel):
    query: str = Field(..., examples=["AI agent IAM best practices"])


class SearchResponse(BaseModel):
    source: str
    query: str
    results: list[dict]


class InternalReadAttemptRequest(BaseModel):
    user_id: str = Field(default="user-001", examples=["user-001"])
