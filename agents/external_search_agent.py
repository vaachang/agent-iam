"""
外部检索 Agent

负责从外部公开网站获取信息，无权访问任何飞书企业内部数据。

Capabilities: external:search
"""

import httpx
from . import AgentBase
from config import SEARXNG_URL


class ExternalSearchAgent(AgentBase):
    """外部检索Agent - searches public web information only."""

    def __init__(self):
        super().__init__("external_search_agent")

    def search(self, query: str, caller_token: str) -> dict:
        """
        Perform an external web search via SearXNG.
        Caller must have external:search OR delegate:external_search capability.
        """
        self.check_any_enforce(["external:search", "delegate:external_search"], caller_token)

        try:
            resp = httpx.get(
                f"{SEARXNG_URL}/search",
                params={"q": query, "format": "json"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                return {
                    "status": "ok",
                    "operation": "external_search",
                    "query": query,
                    "count": len(results),
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "snippet": r.get("content", "")[:200],
                        }
                        for r in results[:5]
                    ],
                }
            return {
                "status": "error",
                "operation": "external_search",
                "query": query,
                "detail": f"SearXNG returned {resp.status_code}",
            }
        except httpx.ConnectError:
            return {
                "status": "ok",
                "operation": "external_search",
                "query": query,
                "count": 0,
                "results": [],
                "note": "SearXNG unreachable, returning empty results",
            }
        except Exception as e:
            return {
                "status": "error",
                "operation": "external_search",
                "query": query,
                "detail": str(e),
            }
