from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.db import connect_db, close_db
from backend.routers import problems, hints, recommend, complexity, sessions, auth, users, chat
from fastapi.middleware.cors import CORSMiddleware


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
origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(problems.router,   prefix="/problems",   tags=["problems"])
app.include_router(hints.router,      prefix="/hints",      tags=["hints"])
app.include_router(recommend.router,  prefix="/recommend",  tags=["recommend"])
app.include_router(complexity.router, prefix="/complexity", tags=["complexity"])
app.include_router(sessions.router,   prefix="/sessions",   tags=["sessions"])
app.include_router(auth.router,       prefix="/auth",        tags=["auth"])
app.include_router(users.router,      prefix="/users",       tags=["users"])
app.include_router(chat.router,       tags=["chat"])


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "message": "LeetBot API is running"}
