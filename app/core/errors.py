from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDefinition:
    code: str
    message: str
    status_code: int


ERRORS = {
    "AUTH_001": ErrorDefinition("AUTH_001", "Token missing", 401),
    "AUTH_002": ErrorDefinition("AUTH_002", "Token invalid", 401),
    "AUTH_003": ErrorDefinition("AUTH_003", "Token expired", 401),
    "AUTH_004": ErrorDefinition("AUTH_004", "Token revoked", 401),
    "AUTH_005": ErrorDefinition("AUTH_005", "Token audience mismatch", 403),
    "AUTHZ_001": ErrorDefinition("AUTHZ_001", "Capability denied", 403),
    "AUTHZ_002": ErrorDefinition("AUTHZ_002", "User permission denied", 403),
    "AUTHZ_003": ErrorDefinition("AUTHZ_003", "Delegation chain invalid", 403),
    "AGENT_001": ErrorDefinition("AGENT_001", "Target agent unavailable", 503),
    "AGENT_002": ErrorDefinition("AGENT_002", "Task execution timeout", 504),
}
