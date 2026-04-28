from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    effect TEXT NOT NULL,
    conditions_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tokens (
    jti TEXT PRIMARY KEY,
    subject_agent TEXT NOT NULL,
    audience_agent TEXT NOT NULL,
    delegated_user TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    parent_jti TEXT,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    token_jti TEXT,
    parent_jti TEXT,
    caller_agent TEXT NOT NULL,
    target_agent TEXT NOT NULL,
    delegated_user TEXT,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    reason_detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


SEED_AGENTS = [
    (
        "doc-agent",
        "Feishu Document Assistant",
        "document_assistant",
        "Generates reports and delegates enterprise reads.",
        "active",
    ),
    (
        "enterprise-data-agent",
        "Enterprise Data Agent",
        "enterprise_data",
        "Reads enterprise datasets and never exposes them without valid delegation.",
        "active",
    ),
    (
        "web-search-agent",
        "Web Search Agent",
        "external_search",
        "Collects public web information only.",
        "active",
    ),
]

SEED_USERS = [
    ("user-001", "Demo User", "employee"),
]

SEED_CAPABILITIES = [
    (
        "agent",
        "doc-agent",
        "bitable",
        "read",
        "allow",
        {
            "audiences": ["enterprise-data-agent"],
            "allowed_tasks": [
                "generate_report",
                "generate_report_with_fallback",
                "manual_enterprise_read",
                "availability_probe",
            ],
            "time_window": {"start_hour": 8, "end_hour": 20},
        },
    ),
    ("agent", "doc-agent", "document", "write", "allow", {"audiences": ["doc-agent"]}),
    ("agent", "doc-agent", "report", "generate", "allow", {"audiences": ["doc-agent"]}),
    (
        "agent",
        "enterprise-data-agent",
        "bitable",
        "read",
        "allow",
        {
            "delegation_only": True,
            "allowed_tasks": [
                "generate_report",
                "generate_report_with_fallback",
                "manual_enterprise_read",
                "availability_probe",
            ],
            "time_window": {"start_hour": 8, "end_hour": 20},
        },
    ),
    ("agent", "enterprise-data-agent", "directory", "read", "allow", {"delegation_only": True}),
    ("agent", "web-search-agent", "web", "search", "allow", {"audiences": ["web-search-agent"]}),
    (
        "user",
        "user-001",
        "bitable",
        "read",
        "allow",
        {
            "allowed_tasks": [
                "generate_report",
                "generate_report_with_fallback",
                "manual_enterprise_read",
                "availability_probe",
            ],
            "time_window": {"start_hour": 8, "end_hour": 20},
        },
    ),
    ("user", "user-001", "document", "write", "allow", {}),
    ("user", "user-001", "web", "search", "allow", {}),
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_database() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(settings.database_path)) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.commit()
    seed_database()


def seed_database() -> None:
    with closing(sqlite3.connect(settings.database_path)) as connection:
        connection.row_factory = sqlite3.Row

        for agent in SEED_AGENTS:
            connection.execute(
                """
                INSERT OR IGNORE INTO agents (agent_id, name, role, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (*agent, _utcnow()),
            )

        for user in SEED_USERS:
            connection.execute(
                """
                INSERT OR IGNORE INTO users (user_id, name, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (*user, _utcnow()),
            )

        for subject_type, subject_id, resource, action, effect, conditions in SEED_CAPABILITIES:
            exists = connection.execute(
                """
                SELECT 1
                FROM capabilities
                WHERE subject_type = ? AND subject_id = ? AND resource = ? AND action = ? AND effect = ?
                """,
                (subject_type, subject_id, resource, action, effect),
            ).fetchone()
            if exists:
                continue
            connection.execute(
                """
                INSERT INTO capabilities (
                    subject_type,
                    subject_id,
                    resource,
                    action,
                    effect,
                    conditions_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    subject_type,
                    subject_id,
                    resource,
                    action,
                    effect,
                    json.dumps(conditions, ensure_ascii=True),
                ),
            )

        connection.commit()


@contextmanager
def get_connection():
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
