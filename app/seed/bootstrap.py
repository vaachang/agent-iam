from app.core.database import ensure_database


def bootstrap() -> None:
    ensure_database()
