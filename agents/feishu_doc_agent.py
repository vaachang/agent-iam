"""
飞书文档助手 Agent

负责理解用户需求，调用其他Agent完成企业数据查询和外部信息检索，
并将最终报告写入飞书文档。

Capabilities: feishu_doc:read, feishu_doc:write, delegate:enterprise_data, delegate:external_search
"""

import json
import httpx
from . import AgentBase
from config import FEISHU_APPS, FEISHU_API_BASE, LLM_API_KEY, LLM_MODEL_ID, LLM_API_BASE as LLM_BASE


class FeishuDocAgent(AgentBase):
    """飞书文档助手 - orchestrates report generation via other agents."""

    def __init__(self):
        super().__init__("feishu_doc_agent")

    # ------------------------------------------------------------------
    # Feishu doc operations
    # ------------------------------------------------------------------

    def _get_feishu_token(self) -> str:
        """Get Feishu tenant access token for this agent's Feishu app."""
        app = FEISHU_APPS["feishu_doc_agent"]
        resp = httpx.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": app["app_id"], "app_secret": app["app_secret"]},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get Feishu token: {resp.text}")
        return resp.json()["tenant_access_token"]

    def create_doc(self, title: str, content: str) -> dict:
        """Create a Feishu doc and write content into it.

        Steps:
        1. Create the document via /docx/v1/documents
        2. Fetch the root block (page block) via /docx/v1/documents/{id}/blocks
        3. Batch-create text blocks as children of the page block
        """
        fs_token = self._get_feishu_token()
        headers = {
            "Authorization": f"Bearer {fs_token}",
            "Content-Type": "application/json",
        }

        # Step 1: Create the document
        resp = httpx.post(
            f"{FEISHU_API_BASE}/docx/v1/documents",
            headers=headers,
            json={"title": title},
        )
        if resp.status_code != 200:
            return {"status": "error", "detail": f"Failed to create doc: {resp.text}"}

        doc_data = resp.json()
        document_id = doc_data["data"]["document"]["document_id"]

        # Step 2: Get the page block (root container for content)
        blocks_resp = httpx.get(
            f"{FEISHU_API_BASE}/docx/v1/documents/{document_id}/blocks",
            headers=headers,
        )
        if blocks_resp.status_code != 200:
            return {
                "status": "ok",
                "document_id": document_id,
                "document_url": f"https://bytedance.feishu.cn/docx/{document_id}",
                "title": title,
                "note": "Document created but block query failed; content not written",
            }

        blocks_data = blocks_resp.json()
        root_items = blocks_data.get("data", {}).get("items", [])
        root_block_id = None
        for item in root_items:
            if item.get("block_type") == 1:  # page / document block
                root_block_id = item["block_id"]
                break

        if root_block_id is None:
            return {
                "status": "ok",
                "document_id": document_id,
                "document_url": f"https://bytedance.feishu.cn/docx/{document_id}",
                "title": title,
                "note": "Document created but page block not found",
            }

        # Step 3: Build text blocks from report content
        def _build_text_block(text: str, heading_level: int = 0) -> dict:
            """Build a Feishu docx block element.

            Feishu block types: 1=page, 2=text, 3=h1, 4=h2, 5=h3, ...
            Property names vary by block type: text→"text", h1→"heading1", etc.
            """
            _type_map = {0: (2, "text"), 1: (3, "heading1"), 2: (4, "heading2"), 3: (5, "heading3")}
            block_type, prop_name = _type_map.get(heading_level, (2, "text"))
            elements = [{"text_run": {"content": text}}]
            return {
                "block_type": block_type,
                prop_name: {"elements": elements, "style": {}},
            }

        children = []
        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# ") and len(stripped) == 2:
                children.append(_build_text_block(stripped[2:].strip() or " ", heading_level=1))
            elif stripped.startswith("## "):
                children.append(_build_text_block(stripped[3:].strip() or " ", heading_level=2))
            elif stripped.startswith("### "):
                children.append(_build_text_block(stripped[4:].strip() or " ", heading_level=3))
            else:
                children.append(_build_text_block(stripped))

        if not children:
            children.append(_build_text_block("(empty report)"))

        # Write in batches of 50 (Feishu API limit per request)
        batch_size = 50
        written = 0
        for i in range(0, len(children), batch_size):
            batch = children[i : i + batch_size]
            child_resp = httpx.post(
                f"{FEISHU_API_BASE}/docx/v1/documents/{document_id}/blocks/{root_block_id}/children",
                headers=headers,
                json={"children": batch},
            )
            if child_resp.status_code == 200:
                written += len(batch)
            else:
                return {
                    "status": "ok",
                    "document_id": document_id,
                    "document_url": f"https://bytedance.feishu.cn/docx/{document_id}",
                    "title": title,
                    "blocks_written": written,
                    "note": f"Partial write: batch at offset {i} failed",
                }

        return {
            "status": "ok",
            "document_id": document_id,
            "document_url": f"https://bytedance.feishu.cn/docx/{document_id}",
            "title": title,
            "blocks_written": written,
        }

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------

    def delegate_to_enterprise_data(self, token: str, operation: str,
                                    params: dict | None = None) -> dict:
        """Delegate a data query to 企业数据Agent."""
        import importlib
        mod = importlib.import_module("agents.enterprise_data_agent")
        agent_cls = getattr(mod, "EnterpriseDataAgent")
        enterprise = agent_cls()

        if operation == "list_bitable_apps":
            return enterprise.list_bitable_apps(token)
        elif operation == "list_users":
            return enterprise.list_users(token)
        elif operation == "list_calendars":
            return enterprise.list_calendars(token)
        elif operation == "list_wiki_spaces":
            return enterprise.list_wiki_spaces(token)
        elif operation == "get_all_enterprise_data":
            return enterprise.get_all_enterprise_data(token)
        else:
            raise ValueError(f"Unknown enterprise data operation: {operation}")

    def delegate_to_external_search(self, token: str, query: str) -> dict:
        """Delegate a search to 外部检索Agent."""
        import importlib
        mod = importlib.import_module("agents.external_search_agent")
        agent_cls = getattr(mod, "ExternalSearchAgent")
        external = agent_cls()
        return external.search(query, token)

    # ------------------------------------------------------------------
    # Main workflow
    # ------------------------------------------------------------------

    def execute_report_workflow(self, user_request: str,
                                delegated_user: str = "anonymous") -> dict:
        """
        Execute the full report generation workflow:

        1. Get IAM token
        2. Delegate to 企业数据Agent for enterprise data
        3. Delegate to 外部检索Agent for external info
        4. Compile and write report to Feishu doc
        """
        client = httpx.Client()
        steps_log = []

        # Step 1: Get token
        token = self.get_token(delegated_user, client)
        steps_log.append({
            "step": "get_token",
            "status": "ok",
            "agent": self.agent_name,
        })

        # Step 2: Delegate to enterprise data agent
        try:
            enterprise_data = self.delegate_to_enterprise_data(
                token, "get_all_enterprise_data"
            )
            steps_log.append({
                "step": "delegate_enterprise_data",
                "status": "ok",
                "data_summary": enterprise_data,
            })
        except PermissionError as e:
            steps_log.append({
                "step": "delegate_enterprise_data",
                "status": "denied",
                "error": str(e),
            })
            enterprise_data = {"error": str(e)}

        # Step 3: Delegate to external search agent
        try:
            search_results = self.delegate_to_external_search(
                token, user_request
            )
            steps_log.append({
                "step": "delegate_external_search",
                "status": "ok",
                "data_summary": search_results,
            })
        except PermissionError as e:
            steps_log.append({
                "step": "delegate_external_search",
                "status": "denied",
                "error": str(e),
            })
            search_results = {"error": str(e)}

        # Step 4: Compile report (try LLM enhancement, fall back to template)
        report_content = self._compile_report_enhanced(
            user_request, enterprise_data, search_results
        )
        steps_log.append({
            "step": "compile_report",
            "status": "ok",
            "llm_enhanced": getattr(self, "_llm_used", False),
        })

        # Step 5: Write to Feishu doc
        try:
            doc_result = self.create_doc(
                title=f"综合报告: {user_request[:50]}",
                content=report_content,
            )
            steps_log.append({
                "step": "write_doc",
                "status": "ok",
                "doc_result": doc_result,
            })
        except Exception as e:
            steps_log.append({
                "step": "write_doc",
                "status": "error",
                "error": str(e),
            })
            doc_result = {"status": "error", "detail": str(e)}

        client.close()

        return {
            "workflow": "report_generation",
            "user_request": user_request,
            "delegated_user": delegated_user,
            "steps": steps_log,
            "final_report": report_content,
            "doc_result": doc_result,
        }

    # ------------------------------------------------------------------
    # LLM-enhanced report compilation
    # ------------------------------------------------------------------

    def _compile_report_enhanced(self, user_request: str,
                                 enterprise_data: dict,
                                 search_results: dict) -> str:
        """Try LLM-enhanced compilation; fall back to template-based if unavailable."""
        if LLM_API_KEY and LLM_MODEL_ID:
            try:
                report = self._generate_report_with_llm(
                    user_request, enterprise_data, search_results
                )
                if report:
                    self._llm_used = True
                    return report
            except Exception as e:
                import sys
                print(f"  [INFO] LLM增强失败，回退到模板: {type(e).__name__}: {e}",
                      file=sys.stderr)
        self._llm_used = False
        return self._compile_report(user_request, enterprise_data, search_results)

    def _generate_report_with_llm(self, user_request: str,
                                  enterprise_data: dict,
                                  search_results: dict) -> str | None:
        """Use the volcano-engine LLM to generate a structured report.

        Includes retry logic and tighter prompt to reduce timeout failures.
        """
        import sys

        data_summary = {
            "user_request": user_request,
            "enterprise": _summarize_enterprise_data(enterprise_data),
            "external_search": _summarize_search_results(search_results),
        }

        prompt = (
            "根据数据生成企业调研报告（Markdown格式，含摘要/企业数据发现/外部信息/结论）。\n"
            f"数据：{json.dumps(data_summary, ensure_ascii=False)}\n"
            "要求：数据驱动、层次分明、专业可读。直接输出报告："
        )

        # Retry up to 2 times with shorter timeout on retry
        for attempt in (1, 2):
            try:
                resp = httpx.post(
                    f"{LLM_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL_ID,
                        "messages": [
                            {"role": "system", "content": "你是一位企业数据分析师，只输出报告，不要其他内容。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.5,
                        "max_tokens": 2048,
                    },
                    timeout=90.0,
                )
                if resp.status_code == 200:
                    choices = resp.json().get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content.strip():
                            return content.strip()
                # Non-200 → retry
                if attempt == 1 and resp.status_code not in (200,):
                    print(f"  [LLM] attempt 1 failed (status={resp.status_code}), retrying...", file=sys.stderr)
            except Exception as e:
                if attempt == 1:
                    print(f"  [LLM] attempt 1: {type(e).__name__}, retrying...", file=sys.stderr)
                continue

        return None

    def _compile_report(self, user_request: str,
                        enterprise_data: dict,
                        search_results: dict) -> str:
        """Compile all data into a report."""
        parts = [
            f"# 综合报告",
            f"",
            f"## 用户需求",
            f"{user_request}",
            f"",
            f"## 企业数据",
        ]

        if enterprise_data.get("status") == "ok":
            data = enterprise_data.get("data", {})
            if isinstance(data, dict):
                for category, items in data.items():
                    parts.append(f"### {category}")
                    if isinstance(items, list):
                        parts.append(f"共获取 {len(items)} 条记录")
                    elif isinstance(items, dict):
                        parts.append(json.dumps(items, ensure_ascii=False, indent=2))
            elif isinstance(data, list):
                parts.append(f"共获取 {len(data)} 条记录")
            else:
                parts.append(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            parts.append(f"企业数据获取失败: {enterprise_data.get('error', 'unknown')}")

        parts.append("")
        parts.append("## 外部检索结果")

        if isinstance(search_results, dict) and search_results.get("status") == "ok":
            results = search_results.get("results", [])
            parts.append(f"共检索到 {len(results)} 条外部信息")
        else:
            parts.append("外部检索失败或未执行")

        parts.append("")
        parts.append("## 报告生成时间")
        from datetime import datetime
        parts.append(datetime.now().isoformat())

        return "\n".join(parts)


# ------------------------------------------------------------------
# Helpers for LLM prompt construction
# ------------------------------------------------------------------

def _summarize_enterprise_data(enterprise_data: dict) -> dict:
    """Extract a compact summary of enterprise data for the LLM prompt."""
    if not isinstance(enterprise_data, dict) or enterprise_data.get("status") != "ok":
        return {"status": "unavailable"}
    data = enterprise_data.get("data", {})
    if isinstance(data, list):
        return {"count": len(data), "sample": data[:3]}
    if isinstance(data, dict):
        summary = {}
        for category, items in data.items():
            if isinstance(items, dict) and items.get("status") == "ok":
                summary[category] = {
                    "count": items.get("count", 0),
                    "sample": items.get("data", [])[:3] if isinstance(items.get("data"), list) else None,
                }
            elif isinstance(items, dict):
                summary[category] = {"status": items.get("status", "error")}
        return summary
    return {"raw_summary": str(data)[:200]}


def _summarize_search_results(search_results: dict) -> dict:
    """Extract a compact summary of search results for the LLM prompt."""
    if not isinstance(search_results, dict) or search_results.get("status") != "ok":
        return {"status": "unavailable"}
    results = search_results.get("results", [])
    return {
        "count": len(results),
        "titles": [r.get("title", "") for r in results[:5]],
    }
