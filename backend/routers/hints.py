"""
backend/routers/hints.py — Hint delivery with SSE streaming and semantic caching.

Endpoints
---------
POST  /hints/{slug}          — original synchronous endpoint (contract unchanged)
GET   /hints/{slug}/stream   — SSE streaming variant (token-by-token via Gemini)

Caching behaviour
-----------------
Both endpoints share the same ``HintSemanticCache`` (backend/rag/cache.py):

  • ``POST /{slug}``      — checks cache first; returns cached response immediately
                            on a hit; writes to cache after successful LLM generation.
  • ``GET /{slug}/stream``— skips the cache on the *first* response (bypassed so the
                            caller always receives a live stream for the first request);
                            after the full response is assembled from the stream it is
                            written to cache so future hits (streaming or non-streaming)
                            can be served from cache.

Scope guarantee
---------------
The cache is keyed on (problem_id, stage) via RedisVL's per-index namespacing
in ``HintSemanticCache``.  A query for problem A will never match a cached
response for problem B regardless of query text similarity.

SSE format
----------
Each token is emitted as a Server-Sent Event:

    data: <token text>\n\n

A terminal event signals end-of-stream:

    data: [DONE]\n\n

An error event is sent if generation fails mid-stream:

    event: error\n
    data: <error message>\n\n
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pymongo.database import Database

from backend.auth.dependencies import get_current_user
from backend.config import settings
from backend.db import get_db
from backend.models.schemas import HintRequest, HintResponse
from backend.rag.cache import HintSemanticCache

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_STAGE = 6

# Shared cache instance — one per process, safe to share across requests.
_hint_cache = HintSemanticCache()

# ---------------------------------------------------------------------------
# Stage configuration
# ---------------------------------------------------------------------------

_STAGE_FIELD: dict[int, str] = {
    1: "hints.stage_1",
    2: "hints.stage_2",
    3: "hints.stage_3",
    4: "hints.stage_4",
    5: "hints.stage_5",
    6: "solutions.python",
}

_STAGE_INSTRUCTION: dict[int, str] = {
    1: "Give a very subtle first hint — just nudge toward the right pattern. No code, no approach.",
    2: "Give a clearer hint about the algorithmic approach (e.g. sliding window, two pointers, DP). No code.",
    3: "Explain the algorithm step by step in plain English. Mention key data structures. No code.",
    4: "Give a detailed walkthrough including edge cases. Pseudocode is fine.",
    5: "Give a final detailed walkthrough of the approach with edge cases. No code.",
    6: "Provide a clean, well-commented C++ solution with time and space complexity analysis and a clear editorial explanation.",
}

_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an expert LeetCode tutor. Be concise, educational, and follow the instruction exactly.",
    ),
    (
        "human",
        (
            "Problem: {title}\n\n"
            "Statement:\n{statement}\n\n"
            "Constraints:\n{constraints}\n\n"
            "Examples:\n{examples}\n\n"
            "---\n"
            "The student is at hint stage {stage} of 5.\n"
            "{instruction}\n"
            "Respond directly. No preamble."
        ),
    ),
])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_field(doc: dict, field_path: str) -> str | None:
    """Walk a dotted field path into *doc* and return the string value, or None."""
    value = doc
    for key in field_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _build_prompt_vars(problem: dict, stage: int) -> dict:
    """Extract and format the template variables for the Gemini prompt."""
    constraints = problem.get("constraints", [])
    if isinstance(constraints, str):
        constraints = [c.strip() for c in constraints.splitlines() if c.strip()]
    constraints_text = "\n".join(f"- {c}" for c in constraints) or "None provided"

    examples = problem.get("examples", [])
    if isinstance(examples, list):
        examples_text = "\n".join(
            f"Input: {e.get('input', '')}  Output: {e.get('output', '')}"
            for e in examples[:2]
        )
    else:
        examples_text = str(examples) if examples else "None provided"

    return {
        "title":       problem.get("title", "Unknown"),
        "statement":   problem.get("problem_statement", ""),
        "constraints": constraints_text,
        "examples":    examples_text,
        "stage":       stage,
        "instruction": _STAGE_INSTRUCTION[stage],
    }


def _make_llm() -> ChatGoogleGenerativeAI:
    """Instantiate a Gemini LLM with streaming enabled."""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL_NAME,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
        streaming=True,   # required for astream() token delivery
    )


def _call_gemini_sync(problem: dict, stage: int) -> str:
    """
    Synchronous (blocking) Gemini call — used by the legacy POST endpoint.
    Preserved for backward compatibility; does not stream.
    """
    llm = _make_llm()
    chain = _PROMPT | llm | StrOutputParser()
    return chain.invoke(_build_prompt_vars(problem, stage))


async def _call_gemini_stream(
    problem: dict,
    stage: int,
) -> AsyncIterator[str]:
    """
    Async generator that yields raw string tokens from Gemini one at a time.

    Used by the SSE streaming endpoint.  Each yielded value is the ``content``
    attribute of an ``AIMessageChunk`` — a string fragment of the final answer.
    """
    llm = _make_llm()
    chain = _PROMPT | llm | StrOutputParser()
    async for chunk in chain.astream(_build_prompt_vars(problem, stage)):
        if chunk:
            yield chunk


# ---------------------------------------------------------------------------
# Shared session / problem resolution
# ---------------------------------------------------------------------------

def _resolve_session_and_problem(
    slug: str,
    session_id: str,
    user_id: str,
    db: Database,
) -> tuple[dict, dict, int, int]:
    """
    Resolve session and problem documents from MongoDB.

    Returns (session, problem, current_stage, next_stage).
    Raises HTTPException on validation failures.
    """
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session_id format")

    session = db["hint_sessions"].find_one({
        "_id": oid,
        "slug": slug,
        "user_id": user_id,
    })
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found for '{slug}' or unauthorized access.",
        )

    current_stage = session.get("current_stage", 0)
    if current_stage >= MAX_STAGE:
        raise HTTPException(status_code=400, detail="All hint stages already unlocked.")

    problem = db["problems"].find_one({"slug": slug})
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem '{slug}' not found")

    next_stage = current_stage + 1
    return session, problem, current_stage, next_stage


# ---------------------------------------------------------------------------
# Existing synchronous endpoint (contract unchanged)
# ---------------------------------------------------------------------------

@router.post("/{slug}", response_model=HintResponse)
async def get_next_hint(
    slug: str,
    body: HintRequest,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> HintResponse:
    """
    Return the next hint stage for *slug*.

    Look-up order:
    1. Semantic cache (Redis/RedisVL) — returns immediately on a hit.
    2. MongoDB stored hint text.
    3. Gemini LLM generation (writes result back to MongoDB and cache).
    """
    session, problem, _current_stage, next_stage = _resolve_session_and_problem(
        slug, body.session_id, current_user["user_id"], db
    )

    problem_id = str(problem["_id"])

    # ── 1. Semantic cache check ───────────────────────────────────────────────
    # Use the stage + problem context as the "query" for the cache.  We key
    # on the stage instruction rather than the user's free-form query because
    # the hints endpoint is deterministic: each stage always produces the same
    # type of hint for a given problem.
    cache_query = f"stage:{next_stage} problem:{slug}"

    cached = await _hint_cache.check(
        problem_id=problem_id,
        stage=next_stage,
        query=cache_query,
    )
    if cached is not None:
        # Advance the session stage even on a cache hit so the client's
        # progress is always recorded.
        oid = ObjectId(body.session_id)
        db["hint_sessions"].update_one(
            {"_id": oid}, {"$set": {"current_stage": next_stage}}
        )
        return HintResponse(
            slug=slug,
            stage=next_stage,
            hint=cached,
            is_final=next_stage == MAX_STAGE,
            next_stage=next_stage + 1 if next_stage < MAX_STAGE else None,
            source="cache",
        )

    # ── 2. MongoDB stored hint ────────────────────────────────────────────────
    hint_text = _extract_field(problem, _STAGE_FIELD[next_stage])
    source = "db"

    # ── 3. LLM fallback ───────────────────────────────────────────────────────
    if not hint_text:
        try:
            # Run the blocking Gemini call in the thread-pool so the event
            # loop is not blocked.
            loop = asyncio.get_event_loop()
            hint_text = await loop.run_in_executor(
                None, _call_gemini_sync, problem, next_stage
            )
            source = "llm"

            # Persist to MongoDB so future DB-path hits skip the LLM.
            db["problems"].update_one(
                {"slug": slug},
                {"$set": {_STAGE_FIELD[next_stage]: hint_text}},
            )

            # Write to semantic cache for future cache-path hits.
            await _hint_cache.store(
                problem_id=problem_id,
                stage=next_stage,
                query=cache_query,
                response=hint_text,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM fallback failed: {exc}")

    # ── Advance session stage ─────────────────────────────────────────────────
    oid = ObjectId(body.session_id)
    db["hint_sessions"].update_one({"_id": oid}, {"$set": {"current_stage": next_stage}})

    return HintResponse(
        slug=slug,
        stage=next_stage,
        hint=hint_text,
        is_final=next_stage == MAX_STAGE,
        next_stage=next_stage + 1 if next_stage < MAX_STAGE else None,
        source=source,
    )


# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------

@router.get("/{slug}/stream")
async def stream_next_hint(
    slug: str,
    session_id: str = Query(..., description="Active hint session ID"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream the next hint stage for *slug* as Server-Sent Events.

    SSE format
    ----------
    Each token arrives as::

        data: <token text>\\n\\n

    End of stream::

        data: [DONE]\\n\\n

    Error mid-stream::

        event: error\\n
        data: <message>\\n\\n

    Cache behaviour
    ---------------
    * The first request for a (problem, stage) always streams live from
      Gemini — no cache look-up — so the client always receives a real
      streaming experience.
    * The assembled full response is written to the semantic cache after
      streaming completes, so subsequent requests (streaming or non-streaming)
      for the same hint can be served from cache.

    Session advancement
    -------------------
    The session's ``current_stage`` is advanced **before** streaming begins,
    matching the POST endpoint behaviour and preventing double-advancement if
    the client disconnects mid-stream.
    """
    session, problem, _current_stage, next_stage = _resolve_session_and_problem(
        slug, session_id, current_user["user_id"], db
    )

    problem_id = str(problem["_id"])

    # Advance session stage immediately (before streaming) so a disconnect
    # doesn't leave the session in an inconsistent state.
    oid = ObjectId(session_id)
    db["hint_sessions"].update_one({"_id": oid}, {"$set": {"current_stage": next_stage}})

    async def _event_generator() -> AsyncIterator[str]:
        """
        Async generator that yields SSE-formatted strings.

        First checks if a DB-stored hint exists (skips LLM call entirely if so).
        Otherwise streams from Gemini token-by-token, assembles the full
        response, then writes it to cache.
        """
        # ── Check MongoDB for pre-stored hint ─────────────────────────────────
        stored = _extract_field(problem, _STAGE_FIELD[next_stage])
        if stored:
            # Emit the entire stored hint as a single SSE chunk, then DONE.
            yield f"data: {_sse_escape(stored)}\n\n"
            yield "data: [DONE]\n\n"

            # Write to cache so future requests are served from cache.
            cache_query = f"stage:{next_stage} problem:{slug}"
            await _hint_cache.store(
                problem_id=problem_id,
                stage=next_stage,
                query=cache_query,
                response=stored,
            )
            return

        # ── Stream from Gemini ────────────────────────────────────────────────
        assembled_chunks: list[str] = []
        try:
            async for token in _call_gemini_stream(problem, next_stage):
                assembled_chunks.append(token)
                yield f"data: {_sse_escape(token)}\n\n"
        except Exception as exc:
            logger.error(
                "Gemini stream error for slug=%s stage=%d: %s",
                slug, next_stage, exc,
            )
            yield f"event: error\ndata: {_sse_escape(str(exc))}\n\n"
            return

        yield "data: [DONE]\n\n"

        # ── Post-stream: persist + cache ──────────────────────────────────────
        full_response = "".join(assembled_chunks)
        if full_response.strip():
            # Persist to MongoDB for future DB-path hits.
            try:
                db["problems"].update_one(
                    {"slug": slug},
                    {"$set": {_STAGE_FIELD[next_stage]: full_response}},
                )
            except Exception as exc:
                logger.warning("Failed to persist streamed hint to MongoDB: %s", exc)

            # Write to semantic cache for future non-streaming / streaming hits.
            cache_query = f"stage:{next_stage} problem:{slug}"
            await _hint_cache.store(
                problem_id=problem_id,
                stage=next_stage,
                query=cache_query,
                response=full_response,
            )

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            # Prevent proxies / CDNs from buffering the stream.
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# SSE utilities
# ---------------------------------------------------------------------------

def _sse_escape(text: str) -> str:
    """
    Escape *text* for safe embedding in an SSE ``data:`` field.

    SSE does not support multi-line ``data`` values natively.  Each newline
    in the token must be sent as a new ``data:`` line.  We JSON-encode the
    string so that newlines and control characters are always single-line safe
    and the client can ``JSON.parse(event.data)`` to recover the original text.
    """
    return json.dumps(text, ensure_ascii=False)
