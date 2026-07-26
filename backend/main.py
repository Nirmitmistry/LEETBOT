import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db import connect_db, close_db
from backend.routers import problems, hints, recommend, complexity, sessions, auth, users, chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="LeetBot API",
    description="RAG-based LeetCode assistant — hints, complexity analysis, recommendations",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Global exception handler — never leak stack traces to the client ─────────


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s",
                     request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(problems.router,   prefix="/problems",   tags=["problems"])
app.include_router(hints.router,      prefix="/hints",      tags=["hints"])
app.include_router(recommend.router,  prefix="/recommend",  tags=["recommend"])
app.include_router(complexity.router, prefix="/complexity",
                   tags=["complexity"])
app.include_router(sessions.router,   prefix="/sessions",   tags=["sessions"])
app.include_router(auth.router,       prefix="/auth",        tags=["auth"])
app.include_router(users.router,      prefix="/users",       tags=["users"])
app.include_router(chat.router,       tags=["chat"])


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "message": "LeetBot API is running"}


@app.get("/health", tags=["health"])
def health_check():
    """Lightweight health check for deployment monitoring.

    Never exposes secrets or raw exception details.
    """
    from backend.db import get_db, get_chroma

    health = {
        "status": "ok",
        "mongodb": "unknown",
        "vector_store": "unknown",
    }

    # ── MongoDB ──────────────────────────────────────────────────────────
    try:
        db = get_db()
        db.client.admin.command("ping")
        health["mongodb"] = "connected"
    except Exception as exc:
        logger.warning("Health-check MongoDB error: %s", exc)
        health["mongodb"] = "unavailable"
        health["status"] = "degraded"

    # ── Chroma ───────────────────────────────────────────────────────────
    try:
        chroma = get_chroma()
        count = chroma._collection.count()
        health["vector_store"] = f"available ({count} vectors)"
    except RuntimeError:
        # Chroma was never initialised (empty dir, etc.)
        health["vector_store"] = "unavailable"
        health["status"] = "degraded"
    except Exception as exc:
        logger.warning("Health-check Chroma error: %s", exc)
        health["vector_store"] = "unavailable"
        health["status"] = "degraded"

    return health


logger.info("Allowed CORS origins: %s", settings.CORS_ORIGINS)

# Wrap the entire application so even 500 responses receive CORS headers.
app = CORSMiddleware(
    app=app,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
    ],
)
