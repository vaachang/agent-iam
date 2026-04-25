from __future__ import annotations

from pathlib import Path
import unittest

from fastapi import HTTPException

from app.api.agents import (
    attempt_internal_read_endpoint,
    generate_report_endpoint,
    read_bitable_endpoint,
    web_search_endpoint,
)
from app.api.audit import export_logs, list_logs
from app.api.auth import delegate_token_endpoint, revoke_token_endpoint
from app.api.demo import run_denied_flow
from app.core.config import settings
from app.core.database import ensure_database
from app.schemas.agent import (
    EnterpriseReadRequest,
    GenerateReportRequest,
    InternalReadAttemptRequest,
    SearchRequest,
)
from app.schemas.auth import DelegatedTokenRequest, TokenRevokeRequest


class AgentIamApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        db_path = Path(settings.database_path)
        if db_path.exists():
            db_path.unlink()
        ensure_database()

    def test_allowed_flow_creates_traceable_report(self) -> None:
        payload = generate_report_endpoint(
            GenerateReportRequest(user_id="user-001", prompt="Generate a report")
        )

        self.assertIn("trace_id", payload)
        self.assertEqual(payload["prompt"], "Generate a report")
        self.assertGreater(len(payload["data_rows"]), 0)

        logs = list_logs(trace_id=payload["trace_id"])
        self.assertGreaterEqual(len(logs), 3)
        self.assertIn("allow", {entry["decision"] for entry in logs})

    def test_denied_flow_is_rejected_and_logged(self) -> None:
        with self.assertRaises(HTTPException) as context:
            run_denied_flow()

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail["code"], "AUTHZ_001")

        logs = list_logs()
        self.assertTrue(
            any(
                entry["decision"] == "deny" and entry["reason_code"] == "AUTHZ_001"
                for entry in logs
            )
        )

    def test_revoked_token_is_rejected_by_enterprise_agent(self) -> None:
        delegated_payload = delegate_token_endpoint(
            DelegatedTokenRequest(
                caller_agent="doc-agent",
                target_agent="enterprise-data-agent",
                delegated_user="user-001",
                resource="bitable",
                action="read",
                task_name="manual_enterprise_read",
            )
        )
        revoke_token_endpoint(TokenRevokeRequest(jti=delegated_payload["jti"]))

        with self.assertRaises(HTTPException) as context:
            read_bitable_endpoint(
                EnterpriseReadRequest(access_token=delegated_payload["access_token"])
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail["code"], "AUTH_004")

    def test_audit_export_returns_csv(self) -> None:
        generate_report_endpoint(GenerateReportRequest(user_id="user-001"))

        exported = export_logs()

        self.assertIn("trace_id", exported)
        self.assertIn("decision", exported)

    def test_web_search_agent_returns_public_results(self) -> None:
        payload = web_search_endpoint(SearchRequest(query="agent iam"))

        self.assertEqual(payload["source"], "web-search-agent")
        self.assertEqual(payload["query"], "agent iam")
        self.assertGreater(len(payload["results"]), 0)

    def test_web_search_agent_internal_read_endpoint_maps_to_http_error(self) -> None:
        with self.assertRaises(HTTPException) as context:
            attempt_internal_read_endpoint(InternalReadAttemptRequest(user_id="user-001"))

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail["code"], "AUTHZ_001")


if __name__ == "__main__":
    unittest.main()
