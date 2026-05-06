"""
Agent IAM System - Agent Base Class
"""

from config import AGENTS, IAM_SERVER_URL


class AgentBase:
    """Base class for all agents with common IAM operations."""

    def __init__(self, agent_id: str):
        agent_info = AGENTS.get(agent_id)
        if agent_info is None:
            raise ValueError(f"Unknown agent_id: {agent_id}")

        self.agent_id = agent_id
        self.agent_name = agent_info["name"]
        self.agent_secret = agent_info["secret"]
        self.capabilities = agent_info["capabilities"]
        self.description = agent_info["description"]
        self._token: str | None = None

    # ------------------------------------------------------------------
    # IAM operations (delegate to the IAM server via HTTP)
    # ------------------------------------------------------------------

    def get_token(self, delegated_user: str = "anonymous",
                  client=None) -> str:
        """Obtain an access token from the IAM server."""
        import httpx

        def _issue(cli):
            resp = cli.post(
                f"{IAM_SERVER_URL}/token/issue",
                json={
                    "agent_id": self.agent_id,
                    "agent_secret": self.agent_secret,
                    "delegated_user": delegated_user,
                },
            )
            if resp.status_code != 200:
                detail = resp.json().get("detail", resp.text)
                raise PermissionError(f"Failed to get token: {detail}")
            data = resp.json()
            self._effective_capabilities = data.get("effective_capabilities", [])
            return data["access_token"]

        if client is None:
            with httpx.Client() as cli:
                return _issue(cli)
        return _issue(client)

    @property
    def effective_capabilities(self) -> list[str]:
        """Return the effective capabilities from the last token issued."""
        return getattr(self, "_effective_capabilities", self.capabilities)

    def verify_capability(self, required_capability: str,
                          token: str | None = None,
                          client=None,
                          silent: bool = False) -> dict:
        """Verify a token has the required capability via the IAM server.

        Args:
            silent: If True, skip audit logging (used for pre-checks).
        """
        import httpx

        token = token or self._token
        if not token:
            raise ValueError("No token available")

        def _verify(cli):
            resp = cli.post(
                f"{IAM_SERVER_URL}/token/verify",
                json={
                    "token": token,
                    "required_capability": required_capability,
                    "silent": silent,
                    "verifier_agent_id": self.agent_id,
                },
            )
            if resp.status_code != 200:
                detail = resp.json().get("detail", resp.text)
                raise PermissionError(f"Token verification failed: {detail}")
            return resp.json()

        if client is None:
            with httpx.Client() as cli:
                return _verify(cli)
        return _verify(client)

    def check_and_enforce(self, required_capability: str,
                          token: str | None = None,
                          client=None) -> dict:
        """
        Verify a capability and raise PermissionError if not allowed.

        Returns the verification result on success.
        """
        result = self.verify_capability(required_capability, token, client)
        if result["decision"] != "allow":
            error_code = result.get("error_code", "UNKNOWN")
            raise PermissionError(
                f"[{error_code}] {result['reason']} "
                f"(agent={result.get('agent_id')}, "
                f"required={required_capability})"
            )
        return result

    def check_any_enforce(self, capabilities: list[str],
                          token: str | None = None,
                          client=None) -> dict:
        """
        Verify that the token has at least one of the listed capabilities.
        Uses silent pre-checks to avoid spurious DENY audit entries,
        then makes one audited call for the final result.
        Raises PermissionError if none match.
        """
        import httpx

        token = token or self._token

        def _check(cli):
            # Silent pre-checks to find a matching capability
            for cap in capabilities[:-1]:
                result = self.verify_capability(cap, token, cli, silent=True)
                if result["decision"] == "allow":
                    return self.verify_capability(cap, token, cli, silent=False)

            # Last capability: check with audit logging (allow or deny)
            last_cap = capabilities[-1]
            result = self.verify_capability(last_cap, token, cli, silent=False)
            if result["decision"] == "allow":
                return result

            raise PermissionError(
                f"[{result.get('error_code', 'UNKNOWN')}] None of {capabilities} granted "
                f"(agent={result.get('agent_id', 'unknown')})"
            )

        if client is None:
            with httpx.Client() as cli:
                return _check(cli)
        return _check(client)
