from dataclasses import dataclass
from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Agent IAM"
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    jwt_secret: str = os.getenv(
        "JWT_SECRET",
        "agent-iam-demo-secret-change-me-1234567890",
    )
    jwt_algorithm: str = "HS256"
    token_ttl_seconds: int = int(os.getenv("TOKEN_TTL_SECONDS", "900"))
    database_path: Path = BASE_DIR / "data" / "agent_iam.db"


settings = Settings()
