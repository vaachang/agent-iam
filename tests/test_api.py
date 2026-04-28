from __future__ import annotations

from pathlib import Path
import unittest

from fastapi import HTTPException

from app.api.agents import (
    attempt_internal_read_endpoint,
    generate_report_endpoint,
    generate_report_with_fallback_endpoint,
    read_bitable_endpoint,
    web_search_endpoint,
)
from app.api.audit import export_logs, list_logs
from app.api.auth import delegate_token_endpoint, revoke_token_endpoint
from app.api.demo import (
    run_denied_flow,
    run_offhours_denied_flow,
    run_task_scope_denied_flow,
    run_timeout_flow,
    run_unavailable_flow,
)
from app.api.policy import check_policy
from app.api.ui import audit_dashboard
from app.core.config import settings
from app.core.database import ensure_database
from app.schemas.agent import (
    EnterpriseReadRequest,
    GenerateReportRequest,
    InternalReadAttemptRequest,
    SearchRequest,
)
from app.schemas.auth import DelegatedTokenRequest, TokenRevokeRequest
from app.schemas.policy import PolicyCheckRequest


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

    def test_timeout_flow_returns_degraded_report_and_logs_timeout(self) -> None:
        payload = run_timeout_flow()

        self.assertEqual(payload["status"], "degraded")
        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["upstream_error"]["code"], "AGENT_002")
        self.assertEqual(payload["data_rows"], [])

        logs = list_logs(trace_id=payload["trace_id"])
        self.assertTrue(any(entry["reason_code"] == "AGENT_002" for entry in logs))
        self.assertTrue(
            any(
                entry["target_agent"] == "doc-agent"
                and entry["decision"] == "allow"
                and entry["reason_code"] == "AGENT_002"
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
                purpose="manual_read",
                current_hour=10,
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

    def test_task_scope_denied_flow_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as context:
            run_task_scope_denied_flow()

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail["code"], "AUTHZ_001")
        self.assertIn("task_name", list_logs(limit=1)[0]["reason_detail"])

    def test_offhours_denied_flow_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as context:
            run_offhours_denied_flow()

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail["code"], "AUTHZ_001")
        self.assertIn("current_hour", list_logs(limit=1)[0]["reason_detail"])

    def test_unavailable_flow_returns_service_unavailable(self) -> None:
        with self.assertRaises(HTTPException) as context:
            run_unavailable_flow()

        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(context.exception.detail["code"], "AGENT_001")

        matching_logs = list_logs(reason_code="AGENT_001")
        self.assertTrue(any(entry["target_agent"] == "enterprise-data-agent" for entry in matching_logs))
        self.assertTrue(any(entry["target_agent"] == "doc-agent" for entry in matching_logs))

    def test_doc_agent_fallback_endpoint_preserves_prompt(self) -> None:
        payload = generate_report_with_fallback_endpoint(
            GenerateReportRequest(user_id="user-001", prompt="Graceful report")
        )

        self.assertEqual(payload["prompt"], "Graceful report")
        self.assertEqual(payload["status"], "degraded")

    def test_audit_dashboard_renders_trace_data(self) -> None:
        payload = generate_report_endpoint(GenerateReportRequest(user_id="user-001"))

        response = audit_dashboard(payload["trace_id"], caller_agent="doc-agent")

        self.assertIn("Agent IAM Trace Console", response.body.decode())
        self.assertIn(payload["trace_id"], response.body.decode())
        self.assertIn("caller_agent", response.body.decode())

    def test_policy_check_respects_runtime_context(self) -> None:
        allowed = check_policy(
            PolicyCheckRequest(
                caller_agent="doc-agent",
                target_agent="enterprise-data-agent",
                delegated_user="user-001",
                resource="bitable",
                action="read",
                task_name="generate_report",
                purpose="quarterly_reporting",
                current_hour=10,
            )
        )
        denied = check_policy(
            PolicyCheckRequest(
                caller_agent="doc-agent",
                target_agent="enterprise-data-agent",
                delegated_user="user-001",
                resource="bitable",
                action="read",
                task_name="generate_report",
                purpose="quarterly_reporting",
                current_hour=2,
            )
        )

        self.assertTrue(allowed["allowed"])
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["context"]["current_hour"], 2)

    def test_audit_log_filters_return_matching_subset(self) -> None:
        generate_report_endpoint(GenerateReportRequest(user_id="user-001"))
        try:
            run_offhours_denied_flow()
        except HTTPException:
            pass

        deny_logs = list_logs(reason_code="AUTHZ_001", decision="deny")

        self.assertGreater(len(deny_logs), 0)
        self.assertTrue(all(entry["reason_code"] == "AUTHZ_001" for entry in deny_logs))
        self.assertTrue(all(entry["decision"] == "deny" for entry in deny_logs))


if __name__ == "__main__":
    unittest.main()
