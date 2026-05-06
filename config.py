"""
Agent IAM System - Configuration

Sensitive values are read from environment variables.
Copy .env.example to .env and fill in real values.
"""
import os
import sys

# --- Helpers ---

def _env(name: str, default: str = "") -> str:
    """Read an environment variable with an optional default."""
    return os.environ.get(name, default)


def _require_env(name: str) -> str:
    """Read a required environment variable; warn if missing (demo mode)."""
    val = os.environ.get(name)
    if val is None or val == "":
        print(f"[config] WARNING: {name} is not set — using demo fallback", file=sys.stderr)
    return val or ""


# --- IAM Server ---

IAM_SERVER_HOST = "127.0.0.1"
IAM_SERVER_PORT = 8900
IAM_SERVER_URL = f"http://{IAM_SERVER_HOST}:{IAM_SERVER_PORT}"

# --- JWT ---

JWT_SECRET = _env("JWT_SECRET", "agent-iam-demo-secret-change-me")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = int(_env("TOKEN_EXPIRE_SECONDS", "3600"))

# --- Audit log ---

AUDIT_LOG_FILE = "audit.log"
REVOCATION_DB_PATH = "revocation.db"
RATE_LIMIT_MAX = int(_env("RATE_LIMIT_MAX", "60"))
RATE_LIMIT_WINDOW = float(_env("RATE_LIMIT_WINDOW", "60.0"))

# Structured error codes
ERROR_CODES = {
    "AUTH_FAILED": "AUTH_FAILED",
    "TOKEN_INVALID": "TOKEN_INVALID",
    "TOKEN_EXPIRED": "TOKEN_EXPIRED",
    "TOKEN_REVOKED": "TOKEN_REVOKED",
    "CAPABILITY_MISMATCH": "CAPABILITY_MISMATCH",
    "DELEGATION_DENIED": "DELEGATION_DENIED",
    "TOKEN_BINDING_MISMATCH": "TOKEN_BINDING_MISMATCH",
    "RATE_LIMITED": "RATE_LIMITED",
}

# User registry: user_id -> {name, permissions}
# Permissions define what resources/data the user is allowed to access.
# When an Agent acts on behalf of a User, the effective token capabilities
# are the INTERSECTION of: user_permissions ∩ agent_capabilities.
USERS = {
    "user_zhangsan": {
        "name": "张三",
        "permissions": [
            "feishu_doc:read",
            "feishu_doc:write",
            "delegate:enterprise_data",
            "delegate:external_search",
            "analysis:summarize",
            "analysis:classify",
            "analysis:qa",
        ],
    },
    "user_lisi": {
        "name": "李四",
        "permissions": [
            "external:search",
        ],
    },
    "anonymous": {
        "name": "匿名用户",
        "permissions": [],
    },
}

# Agent Registry: agent_id -> {name, secret, capabilities}
AGENTS = {
    "feishu_doc_agent": {
        "name": "飞书文档助手",
        "secret": _env("DOC_AGENT_SECRET", "doc_agent_secret_key_2024"),
        "capabilities": [
            "feishu_doc:read",
            "feishu_doc:write",
            "delegate:enterprise_data",
            "delegate:external_search",
        ],
        "description": "负责理解用户需求，调用其他Agent完成企业数据查询和外部信息检索，并将最终报告写入飞书文档",
    },
    "enterprise_data_agent": {
        "name": "企业数据Agent",
        "secret": _env("ENTERPRISE_AGENT_SECRET", "enterprise_agent_secret_key_2024"),
        "capabilities": [
            "feishu_contacts:read",
            "feishu_calendar:read",
            "feishu_bitable:read",
            "feishu_knowledge_base:read",
        ],
        "description": "唯一有权通过飞书OpenAPI访问飞书通讯录、日历、多维表格数据的Agent",
    },
    "external_search_agent": {
        "name": "外部检索Agent",
        "secret": _env("EXTERNAL_AGENT_SECRET", "external_agent_secret_key_2024"),
        "capabilities": [
            "external:search",
        ],
        "description": "负责从外部公开网站获取信息，无权访问任何飞书企业内部数据",
    },
    "ai_analyst_agent": {
        "name": "AI分析Agent",
        "secret": _env("AI_ANALYST_SECRET", "ai_analyst_secret_key_2024"),
        "capabilities": [
            "analysis:summarize",
            "analysis:classify",
            "analysis:qa",
        ],
        "description": "使用LLM推理引擎进行文本分析（异构Agent示例：不同于飞书API/SearXNG后端）",
    },
}

# Feishu App credentials (for actual API calls)
FEISHU_APPS = {
    "enterprise_data_agent": {
        "app_id": _require_env("FEISHU_ENTERPRISE_APP_ID"),
        "app_secret": _require_env("FEISHU_ENTERPRISE_APP_SECRET"),
    },
    "feishu_doc_agent": {
        "app_id": _require_env("FEISHU_DOC_APP_ID"),
        "app_secret": _require_env("FEISHU_DOC_APP_SECRET"),
    },
}

# Feishu API base URL
FEISHU_API_BASE = _env("FEISHU_API_BASE", "https://open.feishu.cn/open-apis")

# Known enterprise resources (bitable apps, wiki spaces)
# These are queried directly when the list-style API doesn't return them.
KNOWN_RESOURCES = {
    "bitable_apps": [
        {"app_token": "FS9rbADV9aTpApsyBYucdBjGngd", "name": "Agent IAM 项目任务追踪"},
    ],
    "wiki_spaces": [
        {"space_id": "7636336706823719897", "name": "AI Agent 企业知识库"},
    ],
}

# SearXNG
SEARXNG_URL = _env("SEARXNG_URL", "http://192.168.1.248:18935")

# LLM API (火山引擎) — optional, used for report enhancement
LLM_API_KEY = _env("LLM_API_KEY", "")
LLM_MODEL_ID = _env("LLM_MODEL_ID", "")
LLM_API_BASE = _env("LLM_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
