from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agents import router as agent_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.demo import router as demo_router
from app.api.policy import router as policy_router
from app.core.config import settings
from app.core.database import ensure_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    description="Agent identity and authorization prototype for multi-agent collaboration.",
)

app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(demo_router)
app.include_router(policy_router)
app.include_router(agent_router)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": settings.app_name}
