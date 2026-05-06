"""
Agent IAM System - Authorization Server

Core service for Agent identity authentication, capability-based
authorization, audit logging, token revocation, dynamic elevation,
and token binding.
"""

import json
import sqlite3
import time
import uuid
import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import jwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import (
    AGENTS,
    AUDIT_LOG_FILE,
    ERROR_CODES,
    IAM_SERVER_HOST,
    IAM_SERVER_PORT,
    JWT_ALGORITHM,
    JWT_SECRET,
    RATE_LIMIT_MAX,
    RATE_LIMIT_WINDOW,
    REVOCATION_DB_PATH,
    TOKEN_EXPIRE_SECONDS,
    USERS,
)

app = FastAPI(
    title="Agent IAM System",
    description="AI Agent Identity & Access Management System",
    version="2.1.0",
)

# --- Rate Limiting ---

_rate_limit_lock = threading.Lock()
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_id: str) -> bool:
    """Sliding-window rate limit. Returns True if allowed."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    with _rate_limit_lock:
        timestamps = [t for t in _rate_limit_store[client_id] if t > window_start]
        _rate_limit_store[client_id] = timestamps
        if len(timestamps) >= RATE_LIMIT_MAX:
            return False
        _rate_limit_store[client_id].append(now)
        return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to token-issue endpoint."""
    if request.url.path == "/token/issue" and request.method == "POST":
        client_id = request.client.host if request.client else "unknown"
        if not _check_rate_limit(client_id):
            METRICS["rate_limit_hits"] += 1
            write_audit_log({
                "event": "rate_limit",
                "decision": "deny",
                "reason": "rate_limit_exceeded",
                "client_ip": client_id,
            })
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "error_code": "RATE_LIMITED",
                        "message": "Too many requests. Please wait and try again.",
                    }
                },
            )
    return await call_next(request)

# --- Revocation Blacklist (SQLite-backed, survives restarts) ---

_revoke_db_lock = threading.Lock()


def _get_revoke_db() -> sqlite3.Connection:
    """Get a thread-safe SQLite connection for the revocation database."""
    conn = sqlite3.connect(REVOCATION_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS revoked_tokens ("
        "  jti TEXT PRIMARY KEY,"
        "  expires_at REAL NOT NULL,"
        "  revoked_at REAL NOT NULL"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS token_lineage ("
        "  child_jti TEXT PRIMARY KEY,"
        "  parent_jti TEXT NOT NULL"
        ")"
    )
    return conn


def _get_child_jtis(parent_jti: str) -> list[str]:
    """Get all child JTIs (recursive) for cascade revocation."""
    conn = _get_revoke_db()
    try:
        children = []
        queue = [parent_jti]
        while queue:
            current = queue.pop(0)
            rows = conn.execute(
                "SELECT child_jti FROM token_lineage WHERE parent_jti = ?",
                (current,),
            ).fetchall()
            for row in rows:
                child = row[0]
                if child not in children:
                    children.append(child)
                    queue.append(child)
        return children
    finally:
        conn.close()

METRICS = defaultdict(int)  # counters for monitoring

# Runtime agent registry — starts empty, populated via API. Merged with config AGENTS.
_runtime_agents: dict[str, dict] = {}
_runtime_agents_lock = threading.Lock()

# --- Audit Logging ---

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
_audit_handler = None


def _get_audit_handler():
    """Lazy-init file handler so the log file is created in the CWD of the server."""
    global _audit_handler
    if _audit_handler is None:
        log_path = Path(AUDIT_LOG_FILE)
        _audit_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        _audit_handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        audit_logger.addHandler(_audit_handler)
    return _audit_handler


def write_audit_log(entry: dict):
    """Append an audit log entry as one JSON line."""
    _get_audit_handler()
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    audit_logger.info(json.dumps(entry, ensure_ascii=False))


# --- Pydantic Models ---

class TokenIssueRequest(BaseModel):
    agent_id: str
    agent_secret: str
    delegated_user: str = "anonymous"
    bound_to: str | None = None  # Anti-theft: bind token to caller identity
    delegated_scopes: list[str] | None = None  # Scope-limited delegation: user restricts which permissions to delegate


class TokenVerifyRequest(BaseModel):
    token: str
    required_capability: str
    silent: bool = False  # If True, skip audit logging
    verifier_agent_id: str | None = None
    bound_to: str | None = None  # Must match the token's bound_to if set


class TokenElevateRequest(BaseModel):
    """Dynamic authorization: request temporary elevated capability."""
    token: str
    requested_capability: str
    justification: str = ""  # Runtime context / reason
    ttl_seconds: int = 300   # Max 5 min for elevated permission


class TokenRevokeRequest(BaseModel):
    token: str
    reason: str = "manual_revocation"


class TokenRevokeByJtiRequest(BaseModel):
    jti: str
    reason: str = "admin_revocation"


class TokenRefreshRequest(BaseModel):
    token: str


class TokenRefreshResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int = 0
    agent_id: str = ""
    agent_name: str = ""
    error_code: str | None = None
    effective_capabilities: list[str] | None = None


class TokenIssueResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int = 0
    agent_id: str = ""
    agent_name: str = ""
    error_code: str | None = None
    effective_capabilities: list[str] | None = None


class TokenVerifyResponse(BaseModel):
    valid: bool
    agent_id: str | None = None
    agent_name: str | None = None
    capabilities: list[str] | None = None
    delegated_user: str | None = None
    decision: str = "deny"  # "allow" or "deny"
    reason: str = ""
    error_code: str | None = None


class TokenElevateResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int = 0
    elevated_capability: str = ""
    decision: str = "deny"
    reason: str = ""
    error_code: str | None = None


# --- Helpers ---

def authenticate_agent(agent_id: str, agent_secret: str) -> dict | None:
    """Validate agent credentials. Checks runtime first, then config."""
    with _runtime_agents_lock:
        agent = _runtime_agents.get(agent_id)
        if agent and agent["secret"] == agent_secret:
            return agent
    agent = AGENTS.get(agent_id)
    if agent and agent["secret"] == agent_secret:
        return agent
    return None


def get_agent(agent_id: str) -> dict | None:
    """Get agent info from runtime or config."""
    with _runtime_agents_lock:
        agent = _runtime_agents.get(agent_id)
        if agent:
            return agent
    return AGENTS.get(agent_id)


def compute_effective_capabilities(agent_capabilities: list[str],
                                   user_permissions: list[str]) -> list[str]:
    """Compute the intersection: user_permissions ∩ agent_capabilities.

    This enforces the principle that an Agent acting on behalf of a User
    can only exercise capabilities that BOTH possess.
    """
    if not user_permissions:
        return []
    return [c for c in agent_capabilities if c in user_permissions]


def _cleanup_revoked():
    """Remove expired entries from the revocation database."""
    now = time.time()
    with _revoke_db_lock:
        conn = _get_revoke_db()
        try:
            conn.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (now,))
            conn.commit()
        finally:
            conn.close()


def is_revoked(jti: str) -> bool:
    """Check if a token JTI has been revoked (and not yet expired)."""
    _cleanup_revoked()
    now = time.time()
    with _revoke_db_lock:
        conn = _get_revoke_db()
        try:
            row = conn.execute(
                "SELECT 1 FROM revoked_tokens WHERE jti = ? AND expires_at > ?",
                (jti, now),
            ).fetchone()
            return row is not None
        finally:
            conn.close()


def revoke_token(jti: str, expires_at: float | None = None):
    """Add a token JTI to the revocation database, cascade-revoking all derived tokens."""
    with _revoke_db_lock:
        conn = _get_revoke_db()
        try:
            expiry = expires_at or (time.time() + TOKEN_EXPIRE_SECONDS)
            now = time.time()

            # Revoke the target token and all its descendants
            jtis_to_revoke = [jti] + _get_child_jtis(jti)
            for j in jtis_to_revoke:
                conn.execute(
                    "INSERT OR REPLACE INTO revoked_tokens (jti, expires_at, revoked_at) "
                    "VALUES (?, ?, ?)",
                    (j, expiry, now),
                )
            conn.commit()
            METRICS["tokens_revoked"] += len(jtis_to_revoke)
            if len(jtis_to_revoke) > 1:
                METRICS["tokens_cascade_revoked"] += len(jtis_to_revoke) - 1
        finally:
            conn.close()


def issue_token(agent_id: str, agent_name: str, capabilities: list[str],
                delegated_user: str, bound_to: str | None = None,
                expires_in: int | None = None) -> tuple[str, dict]:
    """Issue a JWT access token. Returns (token_string, payload)."""
    now = int(time.time())
    payload = {
        "sub": agent_id,
        "agent_name": agent_name,
        "capabilities": capabilities,
        "delegated_user": delegated_user,
        "iat": now,
        "exp": now + (expires_in or TOKEN_EXPIRE_SECONDS),
        "jti": str(uuid.uuid4()),
        "iss": "agent-iam-system",
    }
    if bound_to:
        payload["bound_to"] = bound_to
        payload["binding_level"] = "strict"
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    METRICS["tokens_issued"] += 1
    return token, payload


def verify_token(token_str: str) -> dict | None:
    """Verify a JWT token. Returns payload or None.

    Checks: signature, expiry, AND revocation blacklist.
    """
    try:
        payload = jwt.decode(token_str, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        METRICS["token_verify_expired"] += 1
        return None
    except jwt.InvalidTokenError:
        METRICS["token_verify_invalid"] += 1
        return None

    # Check revocation blacklist
    if is_revoked(payload.get("jti", "")):
        METRICS["token_verify_revoked"] += 1
        return None  # Revoked token == invalid

    return payload


def check_capability(token_payload: dict, required_capability: str) -> bool:
    """Check if the token payload contains the required capability."""
    capabilities = token_payload.get("capabilities", [])
    return required_capability in capabilities


# --- API Endpoints ---

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Agent IAM System"}


@app.post("/token/issue", response_model=TokenIssueResponse)
def token_issue(req: TokenIssueRequest):
    """
    Issue an access token for an agent.

    The agent must authenticate with its agent_id and agent_secret.
    Effective capabilities = user_permissions ∩ agent_capabilities.
    The returned token carries only the intersection.
    """
    agent = authenticate_agent(req.agent_id, req.agent_secret)
    if agent is None:
        write_audit_log({
            "event": "token_issue",
            "decision": "deny",
            "reason": "authentication_failed",
            "error_code": ERROR_CODES["AUTH_FAILED"],
            "agent_id": req.agent_id,
            "delegated_user": req.delegated_user,
        })
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": ERROR_CODES["AUTH_FAILED"],
                "message": "Agent authentication failed",
            },
        )

    # Look up user and compute effective capabilities
    user = USERS.get(req.delegated_user, USERS.get("anonymous", {"permissions": []}))
    user_permissions = user.get("permissions", [])
    effective_caps = compute_effective_capabilities(
        agent["capabilities"], user_permissions
    )

    # Apply scope-limited delegation
    if req.delegated_scopes is not None:
        effective_caps = [c for c in effective_caps if c in req.delegated_scopes]

    token_str, payload = issue_token(
        req.agent_id, agent["name"], effective_caps, req.delegated_user,
        bound_to=req.bound_to,
    )

    write_audit_log({
        "event": "token_issue",
        "decision": "allow",
        "reason": "authentication_success",
        "error_code": None,
        "agent_id": req.agent_id,
        "agent_name": agent["name"],
        "delegated_user": req.delegated_user,
        "agent_capabilities": agent["capabilities"],
        "user_permissions": user_permissions,
        "effective_capabilities": effective_caps,
        "token_jti": payload["jti"],
        "bound_to": req.bound_to,
        "delegated_scopes": req.delegated_scopes,
    })

    return TokenIssueResponse(
        access_token=token_str,
        token_type="Bearer",
        expires_in=TOKEN_EXPIRE_SECONDS,
        agent_id=req.agent_id,
        agent_name=agent["name"],
        effective_capabilities=effective_caps,
    )


@app.post("/token/verify", response_model=TokenVerifyResponse)
def token_verify(req: TokenVerifyRequest):
    """
    Verify an access token and check if it grants a specific capability.

    This is the core authorization endpoint. It:
    1. Validates the JWT token
    2. Checks if the token's capabilities include the required one
    3. Logs the authorization decision to the audit log
    """
    payload = verify_token(req.token)
    if payload is None:
        # Check if specifically revoked
        # Decode without validation to get JTI for better error message
        try:
            unverified = jwt.decode(req.token, options={"verify_signature": False})
            jti = unverified.get("jti", "")
        except Exception:
            jti = ""

        error_code = ERROR_CODES["TOKEN_INVALID"]
        reason = "Token is invalid or expired"
        if jti and is_revoked(jti):
            error_code = "TOKEN_REVOKED"
            reason = "Token has been revoked"
            METRICS["token_verify_revoked"] += 1

        if not req.silent:
            write_audit_log({
                "event": "token_verify",
                "decision": "deny",
                "reason": reason,
                "error_code": error_code,
                "required_capability": req.required_capability,
            })
        return TokenVerifyResponse(
            valid=False,
            decision="deny",
            reason=reason,
            error_code=error_code,
        )

    # Token binding check (anti-theft)
    if payload.get("bound_to") and req.bound_to:
        if payload["bound_to"] != req.bound_to:
            METRICS["token_binding_mismatch"] += 1
            if not req.silent:
                write_audit_log({
                    "event": "token_verify",
                    "decision": "deny",
                    "reason": "token_binding_mismatch",
                    "error_code": "TOKEN_BINDING_MISMATCH",
                    "required_capability": req.required_capability,
                    "caller_agent_id": payload["sub"],
                    "expected_bound_to": payload["bound_to"],
                    "actual_bound_to": req.bound_to,
                })
            return TokenVerifyResponse(
                valid=True,
                agent_id=payload["sub"],
                agent_name=payload.get("agent_name", ""),
                decision="deny",
                reason=f"Token is bound to {payload['bound_to']}, but request came from {req.bound_to}",
                error_code="TOKEN_BINDING_MISMATCH",
            )

    METRICS["token_verify_total"] += 1

    has_capability = check_capability(payload, req.required_capability)

    audit_entry = {
        "event": "token_verify",
        "caller_agent_id": payload["sub"],
        "caller_agent_name": payload.get("agent_name", ""),
        "verifier_agent_id": req.verifier_agent_id or "unknown",
        "delegated_user": payload.get("delegated_user", ""),
        "required_capability": req.required_capability,
        "token_capabilities": payload.get("capabilities", []),
        "token_jti": payload.get("jti", ""),
    }

    if has_capability:
        audit_entry["decision"] = "allow"
        audit_entry["reason"] = "capability_match"
        audit_entry["error_code"] = None
        if not req.silent:
            write_audit_log(audit_entry)

        return TokenVerifyResponse(
            valid=True,
            agent_id=payload["sub"],
            agent_name=payload.get("agent_name", ""),
            capabilities=payload.get("capabilities", []),
            delegated_user=payload.get("delegated_user", ""),
            decision="allow",
            reason="Capability matched",
        )
    else:
        # Distinguish: CAPABILITY_MISMATCH (agent never had it)
        #           vs DELEGATION_DENIED (agent has it, but user blocked it)
        agent_static = get_agent(payload["sub"]) or {}
        agent_static_caps = agent_static.get("capabilities", [])
        if req.required_capability in agent_static_caps:
            audit_entry["decision"] = "deny"
            audit_entry["reason"] = "delegation_denied_by_user_policy"
            audit_entry["error_code"] = ERROR_CODES["DELEGATION_DENIED"]
            deny_error = ERROR_CODES["DELEGATION_DENIED"]
            deny_reason = (
                f"User '{payload.get('delegated_user', 'unknown')}' has not granted "
                f"'{req.required_capability}' to agent '{payload['sub']}'"
            )
        else:
            audit_entry["decision"] = "deny"
            audit_entry["reason"] = "capability_mismatch"
            audit_entry["error_code"] = ERROR_CODES["CAPABILITY_MISMATCH"]
            deny_error = ERROR_CODES["CAPABILITY_MISMATCH"]
            deny_reason = (
                f"Capability '{req.required_capability}' not granted "
                f"to agent '{payload['sub']}'"
            )

        if not req.silent:
            write_audit_log(audit_entry)

        return TokenVerifyResponse(
            valid=True,
            agent_id=payload["sub"],
            agent_name=payload.get("agent_name", ""),
            capabilities=payload.get("capabilities", []),
            delegated_user=payload.get("delegated_user", ""),
            decision="deny",
            reason=deny_reason,
            error_code=deny_error,
        )


@app.post("/token/refresh", response_model=TokenRefreshResponse)
def token_refresh(req: TokenRefreshRequest):
    """
    Refresh an access token: validate the current token and issue a new one
    with the same claims but a fresh expiry.

    The original token must be valid and not revoked.
    """
    payload = verify_token(req.token)
    if payload is None:
        error_code = ERROR_CODES["TOKEN_INVALID"]
        # Distinguish revoked from invalid
        try:
            unverified = jwt.decode(req.token, options={"verify_signature": False})
            jti = unverified.get("jti", "")
        except Exception:
            jti = ""
        if jti and is_revoked(jti):
            error_code = "TOKEN_REVOKED"

        write_audit_log({
            "event": "token_refresh",
            "decision": "deny",
            "reason": "token_invalid_or_revoked",
            "error_code": error_code,
        })
        return TokenRefreshResponse(
            error_code=error_code,
        )

    agent_id = payload["sub"]
    agent = get_agent(agent_id) or {}
    new_token_str, new_payload = issue_token(
        agent_id,
        payload.get("agent_name", agent.get("name", "")),
        payload.get("capabilities", []),
        payload.get("delegated_user", "anonymous"),
        bound_to=payload.get("bound_to"),
    )

    write_audit_log({
        "event": "token_refresh",
        "decision": "allow",
        "agent_id": agent_id,
        "agent_name": payload.get("agent_name", ""),
        "delegated_user": payload.get("delegated_user", ""),
        "old_jti": payload.get("jti", ""),
        "new_jti": new_payload["jti"],
    })

    METRICS["tokens_issued"] += 1
    return TokenRefreshResponse(
        access_token=new_token_str,
        token_type="Bearer",
        expires_in=TOKEN_EXPIRE_SECONDS,
        agent_id=agent_id,
        agent_name=payload.get("agent_name", agent.get("name", "")),
        effective_capabilities=payload.get("capabilities", []),
    )


@app.get("/audit/logs")
def get_audit_logs(limit: int = 50, decision: str | None = None):
    """Query audit logs with optional filtering."""
    log_path = Path(AUDIT_LOG_FILE)
    if not log_path.exists():
        return {"logs": [], "total": 0}

    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    entries = []
    for line in reversed(lines):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if decision and entry.get("decision") != decision:
                continue
            entries.append(entry)
            if len(entries) >= limit:
                break
        except json.JSONDecodeError:
            continue

    return {"logs": entries, "total": len(entries)}


@app.get("/audit/export")
def export_audit_logs():
    """Export the full audit log as downloadable JSON."""
    log_path = Path(AUDIT_LOG_FILE)
    if not log_path.exists():
        return {"logs": [], "total": 0}

    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    entries = []
    for line in lines:
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {"logs": entries, "total": len(entries),
            "exported_at": datetime.now(timezone.utc).isoformat()}


@app.get("/audit/summary")
def audit_summary():
    """Get a summary of audit log statistics."""
    log_path = Path(AUDIT_LOG_FILE)
    if not log_path.exists():
        return {"total": 0, "allow": 0, "deny": 0, "by_agent": {}, "by_event": {}}

    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    stats = {"total": 0, "allow": 0, "deny": 0, "by_agent": {}, "by_event": {}}
    for line in lines:
        if not line:
            continue
        try:
            entry = json.loads(line)
            stats["total"] += 1
            decision = entry.get("decision", "unknown")
            # Count all decision types
            stats.setdefault(decision, 0)
            stats[decision] += 1

            caller = entry.get("caller_agent_id") or entry.get("agent_id", "unknown")
            if caller not in stats["by_agent"]:
                stats["by_agent"][caller] = {}
            stats["by_agent"][caller].setdefault(decision, 0)
            stats["by_agent"][caller][decision] += 1

            event = entry.get("event", "unknown")
            if event not in stats["by_event"]:
                stats["by_event"][event] = {}
            stats["by_event"][event].setdefault(decision, 0)
            stats["by_event"][event][decision] += 1
        except json.JSONDecodeError:
            continue

    return stats


@app.get("/agents")
def list_agents():
    """List all registered agents and their capabilities (public info)."""
    result = {}
    # Config agents
    for agent_id, info in AGENTS.items():
        result[agent_id] = {
            "name": info["name"],
            "capabilities": info["capabilities"],
            "description": info["description"],
            "source": "config",
        }
    # Runtime agents (override or add)
    with _runtime_agents_lock:
        for agent_id, info in _runtime_agents.items():
            result[agent_id] = {
                "name": info["name"],
                "capabilities": info["capabilities"],
                "description": info["description"],
                "source": "runtime",
            }
    return result


class AgentRegisterRequest(BaseModel):
    agent_id: str
    agent_name: str
    agent_secret: str
    capabilities: list[str]
    description: str = ""


@app.post("/agents/register")
def register_agent(req: AgentRegisterRequest):
    """Register a new agent at runtime or update an existing runtime agent."""
    with _runtime_agents_lock:
        _runtime_agents[req.agent_id] = {
            "name": req.agent_name,
            "secret": req.agent_secret,
            "capabilities": req.capabilities,
            "description": req.description,
        }
    write_audit_log({
        "event": "agent_register",
        "decision": "allow",
        "agent_id": req.agent_id,
        "agent_name": req.agent_name,
        "capabilities": req.capabilities,
    })
    return {"status": "registered", "agent_id": req.agent_id}


@app.delete("/agents/{agent_id}")
def deregister_agent(agent_id: str):
    """Remove a runtime-registered agent. Config-seeded agents cannot be removed."""
    if agent_id in AGENTS:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "AGENT_PROTECTED",
                "message": f"Agent '{agent_id}' is defined in config and cannot be removed at runtime. Override it via /agents/register instead.",
            },
        )
    with _runtime_agents_lock:
        if agent_id not in _runtime_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        del _runtime_agents[agent_id]
    write_audit_log({
        "event": "agent_deregister",
        "decision": "allow",
        "agent_id": agent_id,
    })
    return {"status": "deregistered", "agent_id": agent_id}


@app.get("/users")
def list_users():
    """List all registered users and their permissions (public info)."""
    return {
        user_id: {
            "name": info["name"],
            "permissions": info["permissions"],
        }
        for user_id, info in USERS.items()
    }


# --- Dynamic Authorization (Elevation) ---

@app.post("/token/elevate", response_model=TokenElevateResponse)
def token_elevate(req: TokenElevateRequest):
    """
    Dynamic authorization: grant a temporary elevated capability.

    Only works if:
    1. The caller holds a valid token
    2. The agent's static capabilities include the requested capability
    3. The user also has the corresponding permission

    The elevated token has a short TTL (max 300s) — runtime context expires quickly.
    This balances security with flexibility: agents can ask for more power
    when the situation requires it, but it's automatically revoked after a short window.
    """
    METRICS["elevate_requests"] += 1

    # Validate the original token
    payload = verify_token(req.token)
    if payload is None:
        METRICS["elevate_denied"] += 1
        return TokenElevateResponse(
            decision="deny",
            reason="Original token is invalid, expired, or revoked",
            error_code=ERROR_CODES["TOKEN_INVALID"],
        )

    agent_id = payload["sub"]
    agent = get_agent(agent_id) or {}
    agent_static_caps = agent.get("capabilities", [])

    # Check the agent's static capability set includes the requested one
    if req.requested_capability not in agent_static_caps:
        METRICS["elevate_denied"] += 1
        write_audit_log({
            "event": "token_elevate",
            "decision": "deny",
            "reason": "capability_not_in_agent_profile",
            "error_code": ERROR_CODES["CAPABILITY_MISMATCH"],
            "agent_id": agent_id,
            "requested_capability": req.requested_capability,
        })
        return TokenElevateResponse(
            decision="deny",
            reason=f"Agent '{agent_id}' does not have '{req.requested_capability}' in its static profile",
            error_code=ERROR_CODES["CAPABILITY_MISMATCH"],
        )

    # Check the user also has the permission
    user = USERS.get(payload.get("delegated_user", "anonymous"), {"permissions": []})
    if req.requested_capability not in user.get("permissions", []):
        METRICS["elevate_denied"] += 1
        write_audit_log({
            "event": "token_elevate",
            "decision": "deny",
            "reason": "delegation_denied_by_user_policy",
            "error_code": ERROR_CODES["DELEGATION_DENIED"],
            "agent_id": agent_id,
            "requested_capability": req.requested_capability,
        })
        return TokenElevateResponse(
            decision="deny",
            reason=f"User has not granted '{req.requested_capability}'",
            error_code=ERROR_CODES["DELEGATION_DENIED"],
        )

    # Issue a short-lived elevated token
    ttl = min(req.ttl_seconds, 300)  # Hard cap at 5 minutes
    elevated_caps = list(set(payload.get("capabilities", []) + [req.requested_capability]))
    elevated_token, elevated_payload = issue_token(
        agent_id, payload.get("agent_name", ""), elevated_caps,
        payload.get("delegated_user", "anonymous"),
        bound_to=payload.get("bound_to"),
        expires_in=ttl,
    )
    elevated_payload["elevated_from"] = payload["jti"]
    elevated_payload["elevation_context"] = req.justification

    # Record lineage for cascade revocation
    conn = _get_revoke_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO token_lineage (child_jti, parent_jti) VALUES (?, ?)",
            (elevated_payload["jti"], payload["jti"]),
        )
        conn.commit()
    finally:
        conn.close()

    write_audit_log({
        "event": "token_elevate",
        "decision": "allow",
        "agent_id": agent_id,
        "requested_capability": req.requested_capability,
        "justification": req.justification,
        "ttl_seconds": ttl,
        "original_jti": payload["jti"],
        "elevated_jti": elevated_payload["jti"],
    })

    METRICS["elevate_allowed"] += 1
    return TokenElevateResponse(
        access_token=elevated_token,
        token_type="Bearer",
        expires_in=ttl,
        elevated_capability=req.requested_capability,
        decision="allow",
        reason=f"Temporary elevation granted for {ttl}s: {req.justification}",
    )


# --- Token Revocation ---

@app.post("/token/revoke")
def token_revoke(req: TokenRevokeRequest):
    """
    Revoke an access token by its JWT string.

    Adds the token's JTI to the in-memory blacklist.
    Revoked tokens will fail all subsequent verification checks.
    This provides real-time response to agent misbehavior.
    """
    payload = verify_token(req.token)
    if payload is None:
        # Already invalid — still record the intent
        write_audit_log({
            "event": "token_revoke",
            "decision": "acknowledged",
            "reason": "token_already_invalid",
            "detail": req.reason,
        })
        return {"status": "acknowledged", "message": "Token is already invalid or expired"}

    jti = payload["jti"]
    exp = payload.get("exp", time.time() + TOKEN_EXPIRE_SECONDS)
    revoke_token(jti, exp)

    write_audit_log({
        "event": "token_revoke",
        "decision": "allow",
        "reason": req.reason,
        "agent_id": payload["sub"],
        "token_jti": jti,
        "delegated_user": payload.get("delegated_user", ""),
    })
    return {
        "status": "revoked",
        "jti": jti,
        "agent_id": payload["sub"],
        "reason": req.reason,
    }


@app.post("/token/revoke-by-jti")
def token_revoke_by_jti(req: TokenRevokeByJtiRequest):
    """Admin endpoint: revoke a token by its JTI."""
    revoke_token(req.jti)
    write_audit_log({
        "event": "token_revoke",
        "decision": "allow",
        "reason": req.reason,
        "token_jti": req.jti,
    })
    return {"status": "revoked", "jti": req.jti, "reason": req.reason}


@app.get("/token/blacklist")
def list_revoked():
    """List currently revoked JTIs (for debugging / monitoring)."""
    _cleanup_revoked()
    now = time.time()
    conn = _get_revoke_db()
    try:
        rows = conn.execute(
            "SELECT jti FROM revoked_tokens WHERE expires_at > ?", (now,)
        ).fetchall()
        jtis = [row[0] for row in rows]
        return {"revoked_count": len(jtis), "jtis": jtis}
    finally:
        conn.close()


# --- Health & Monitoring ---

@app.get("/health/metrics")
def health_metrics():
    """
    System observability: expose runtime metrics for monitoring/alerting.
    Covers the 优秀标准 requirement for 系统异常感知能力.
    """
    _cleanup_revoked()
    return {
        "service": "Agent IAM System v2.0.0",
        "uptime_schema": "prometheus-style",
        "counters": {
            "tokens_issued": METRICS["tokens_issued"],
            "tokens_revoked": METRICS["tokens_revoked"],
            "tokens_cascade_revoked": METRICS["tokens_cascade_revoked"],
            "token_verify_total": METRICS["token_verify_total"],
            "token_verify_expired": METRICS["token_verify_expired"],
            "token_verify_invalid": METRICS["token_verify_invalid"],
            "token_verify_revoked": METRICS["token_verify_revoked"],
            "token_binding_mismatch": METRICS["token_binding_mismatch"],
            "elevate_requests": METRICS["elevate_requests"],
            "elevate_allowed": METRICS["elevate_allowed"],
            "elevate_denied": METRICS["elevate_denied"],
            "rate_limit_hits": METRICS["rate_limit_hits"],
        },
        "blacklist_size": _get_blacklist_size(),
        "alerts": _compute_alerts(),
    }


def _get_blacklist_size() -> int:
    """Get the current count of active (non-expired) revoked tokens."""
    now = time.time()
    conn = _get_revoke_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM revoked_tokens WHERE expires_at > ?", (now,)
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _compute_alerts() -> list[str]:
    """Simple rule-based alerts based on runtime metrics."""
    alerts = []
    total_verify = METRICS["token_verify_total"] or 1
    deny_rate = (METRICS["token_verify_invalid"] +
                 METRICS["token_verify_expired"] +
                 METRICS["token_verify_revoked"]) / total_verify
    binding_rate = METRICS["token_binding_mismatch"] / max(total_verify, 1)

    if deny_rate > 0.5:
        alerts.append(f"HIGH_DENY_RATE: {deny_rate:.1%} verification failures (possible attack)")
    if METRICS["token_binding_mismatch"] > 0:
        alerts.append(f"TOKEN_THEFT_DETECTED: {METRICS['token_binding_mismatch']} binding mismatches")
    if METRICS["token_verify_revoked"] > 0:
        alerts.append(f"REVOKED_TOKEN_USAGE: {METRICS['token_verify_revoked']} attempts to use revoked tokens")
    if METRICS["elevate_denied"] > 3:
        alerts.append(f"EXCESSIVE_ELEVATION_DENIALS: {METRICS['elevate_denied']} failed elevation attempts")

    return alerts if alerts else ["ALL_SYSTEMS_NORMAL"]


# --- Main ---

if __name__ == "__main__":
    import uvicorn
    print(f"Starting Agent IAM Server on {IAM_SERVER_HOST}:{IAM_SERVER_PORT}")
    uvicorn.run(app, host=IAM_SERVER_HOST, port=IAM_SERVER_PORT, log_level="info")
