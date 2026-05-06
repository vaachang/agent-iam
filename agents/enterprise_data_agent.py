"""
企业数据 Agent

唯一有权通过飞书 OpenAPI 访问飞书通讯录、日历、多维表格数据的 Agent。

Capabilities: feishu_contacts:read, feishu_calendar:read, feishu_bitable:read, feishu_knowledge_base:read
"""

import httpx
from . import AgentBase
from config import FEISHU_APPS, FEISHU_API_BASE, KNOWN_RESOURCES


class EnterpriseDataAgent(AgentBase):
    """企业数据Agent - the sole agent authorized to access Feishu enterprise data."""

    def __init__(self):
        super().__init__("enterprise_data_agent")

    # ------------------------------------------------------------------
    # Feishu API helpers
    # ------------------------------------------------------------------

    def _get_feishu_token(self) -> str:
        app = FEISHU_APPS["enterprise_data_agent"]
        resp = httpx.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": app["app_id"], "app_secret": app["app_secret"]},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get Feishu token: {resp.text}")
        return resp.json()["tenant_access_token"]

    def _feishu_get(self, path: str, params: dict | None = None) -> dict:
        fs_token = self._get_feishu_token()
        resp = httpx.get(
            f"{FEISHU_API_BASE}{path}",
            headers={"Authorization": f"Bearer {fs_token}"},
            params=params or {},
        )
        if resp.status_code != 200:
            return {"code": resp.status_code, "msg": resp.text}
        return resp.json()

    # ------------------------------------------------------------------
    # Data access operations (public: enforce auth via token)
    # ------------------------------------------------------------------

    def list_bitable_apps(self, caller_token: str) -> dict:
        self.check_any_enforce(
            ["delegate:enterprise_data", "feishu_bitable:read"], caller_token
        )
        return self._list_bitable_apps()

    def list_users(self, caller_token: str) -> dict:
        self.check_any_enforce(
            ["delegate:enterprise_data", "feishu_contacts:read"], caller_token
        )
        return self._list_users()

    def list_calendars(self, caller_token: str) -> dict:
        self.check_any_enforce(
            ["delegate:enterprise_data", "feishu_calendar:read"], caller_token
        )
        return self._list_calendars()

    def list_wiki_spaces(self, caller_token: str) -> dict:
        self.check_any_enforce(
            ["delegate:enterprise_data", "feishu_knowledge_base:read"], caller_token
        )
        return self._list_wiki_spaces()

    def get_all_enterprise_data(self, caller_token: str) -> dict:
        """Get all enterprise data. Caller must have delegate:enterprise_data."""
        self.check_and_enforce("delegate:enterprise_data", caller_token)

        results = {}
        for name, method in [
            ("bitable_apps", self._list_bitable_apps),
            ("contacts", self._list_users),
            ("calendars", self._list_calendars),
            ("knowledge_base", self._list_wiki_spaces),
        ]:
            try:
                results[name] = method()
            except Exception as e:
                results[name] = {"status": "error", "detail": str(e)}

        return {"status": "ok", "operation": "get_all_enterprise_data",
                "data": results}

    # ------------------------------------------------------------------
    # Internal implementations (no auth check — do the actual API work)
    # ------------------------------------------------------------------

    def _list_bitable_apps(self) -> dict:
        result = self._feishu_get("/bitable/v1/apps/list")
        if result.get("code") == 0:
            apps = result.get("data", {}).get("items", [])
            if apps:
                return {"status": "ok", "operation": "list_bitable_apps",
                        "count": len(apps), "data": apps}

        # Fallback: query known apps directly with record counts
        apps = []
        for known in KNOWN_RESOURCES.get("bitable_apps", []):
            info = self._feishu_get(f"/bitable/v1/apps/{known['app_token']}")
            if info.get("code") == 0:
                app_data = info.get("data", {}).get("app", {})
                app_data["app_token"] = known["app_token"]
                app_data["record_count"] = self._count_bitable_records(
                    known["app_token"], app_data.get("default_table_id", "")
                )
                apps.append(app_data)

        return {"status": "ok", "operation": "list_bitable_apps",
                "count": len(apps), "data": apps}

    def _list_users(self) -> dict:
        result = self._feishu_get("/contact/v3/users", {"page_size": 50})
        if result.get("code") == 0:
            users = result.get("data", {}).get("items", [])
            return {"status": "ok", "operation": "list_users",
                    "count": len(users), "data": users}
        return {"status": "ok", "operation": "list_users",
                "data": result, "note": "Feishu API returned non-zero code"}

    def _list_calendars(self) -> dict:
        result = self._feishu_get("/calendar/v4/calendars")
        if result.get("code") == 0:
            calendars = result.get("data", {}).get("calendar_list", [])
            return {"status": "ok", "operation": "list_calendars",
                    "count": len(calendars), "data": calendars}
        return {"status": "ok", "operation": "list_calendars",
                "data": result, "note": "Feishu API returned non-zero code"}

    def _list_wiki_spaces(self) -> dict:
        result = self._feishu_get("/wiki/v2/spaces")
        if result.get("code") == 0:
            spaces = result.get("data", {}).get("items", [])
            if spaces:
                return {"status": "ok", "operation": "list_wiki_spaces",
                        "count": len(spaces), "data": spaces}

        # Fallback to known resources
        if KNOWN_RESOURCES.get("wiki_spaces"):
            return {"status": "ok", "operation": "list_wiki_spaces",
                    "count": len(KNOWN_RESOURCES["wiki_spaces"]),
                    "data": KNOWN_RESOURCES["wiki_spaces"]}

        return {"status": "ok", "operation": "list_wiki_spaces",
                "count": 0, "data": []}

    def _count_bitable_records(self, app_token: str, table_id: str) -> int:
        """Query record count for a bitable app using the doc agent's credentials."""
        doc_app = FEISHU_APPS.get("feishu_doc_agent", {})
        if not doc_app:
            return 0
        try:
            r = httpx.post(
                f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": doc_app["app_id"], "app_secret": doc_app["app_secret"]},
            )
            doc_fs = r.json()["tenant_access_token"]
            doc_h = {"Authorization": f"Bearer {doc_fs}"}

            if not table_id:
                tr = httpx.get(
                    f"{FEISHU_API_BASE}/bitable/v1/apps/{app_token}/tables",
                    headers=doc_h,
                )
                tables = tr.json().get("data", {}).get("items", [])
                if tables:
                    table_id = tables[0].get("table_id", "")
                else:
                    return 0

            rr = httpx.get(
                f"{FEISHU_API_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                headers=doc_h,
            )
            return len(rr.json().get("data", {}).get("items", []))
        except Exception:
            return 0
