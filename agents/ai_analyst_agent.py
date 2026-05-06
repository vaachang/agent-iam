"""
AI 分析 Agent (异构接入示例)

使用火山引擎 LLM 作为推理引擎，展示不同后端（LLM API / Feishu OpenAPI / SearXNG）
的 Agent 如何通过统一的 IAM 框架接入。

Capabilities: analysis:summarize, analysis:classify, analysis:qa
"""
import json
import httpx
from . import AgentBase
from config import LLM_API_KEY, LLM_MODEL_ID, LLM_API_BASE as LLM_BASE


class AIAnalystAgent(AgentBase):
    """AI 分析 Agent - 使用 LLM 推理引擎，不同于其他 Agent 的工具调用模式。

    异构特征:
    - 推理引擎: 火山引擎 LLM API (与飞书 OpenAPI/SearXNG 完全不同)
    - 调用模式: 自然语言推理 (vs REST API 调用)
    - 输出类型: 结构化分析结果 (vs 原始数据)
    - IAM 层: 统一使用 AgentBase + JWT Token (与所有 Agent 一致)
    """

    def __init__(self):
        super().__init__("ai_analyst_agent")

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str | None:
        """Internal: call the LLM API (volcano engine)."""
        if not (LLM_API_KEY and LLM_MODEL_ID):
            raise RuntimeError("LLM not configured (set LLM_API_KEY / LLM_MODEL_ID)")

        resp = httpx.post(
            f"{LLM_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL_ID,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            },
            timeout=60.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"LLM API error: {resp.status_code}")
        choices = resp.json().get("choices", [])
        if not choices:
            raise RuntimeError("LLM returned empty response")
        return choices[0]["message"]["content"]

    # ------------------------------------------------------------------
    # Analysis operations (each enforces capability check via IAM)
    # ------------------------------------------------------------------

    def summarize(self, text: str, caller_token: str,
                  max_words: int = 200) -> dict:
        """Summarize a text. Caller must have analysis:summarize."""
        self.check_and_enforce("analysis:summarize", caller_token)

        content = self._call_llm(
            "你是一位专业的信息分析师。请用中文总结以下内容，"
            f"不超过{max_words}字。直接输出总结，不要前缀。",
            text[:8000],
        )
        return {
            "status": "ok",
            "operation": "summarize",
            "summary": content,
            "original_length": len(text),
        }

    def classify(self, text: str, labels: list[str],
                 caller_token: str) -> dict:
        """Classify text into given labels. Caller must have analysis:classify."""
        self.check_and_enforce("analysis:classify", caller_token)

        content = self._call_llm(
            "你是一位文本分类专家。请将以下文本归类到给定标签之一。"
            "只输出标签名称，不要解释。",
            f"标签列表: {', '.join(labels)}\n\n文本:\n{text[:4000]}",
        )
        return {
            "status": "ok",
            "operation": "classify",
            "label": (content or "").strip(),
            "candidates": labels,
        }

    def answer_question(self, question: str, context: str,
                        caller_token: str) -> dict:
        """Answer a question based on context. Caller must have analysis:qa."""
        self.check_and_enforce("analysis:qa", caller_token)

        content = self._call_llm(
            "你是一位问答专家。请仅根据提供的上下文回答问题。"
            "如果上下文中没有答案，请明确说'信息不足'。",
            f"上下文:\n{context[:6000]}\n\n问题: {question}",
        )
        return {
            "status": "ok",
            "operation": "qa",
            "answer": content,
            "question": question,
        }
