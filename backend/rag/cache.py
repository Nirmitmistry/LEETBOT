"""
backend/rag/cache.py — Problem-scoped semantic cache for LLM-generated hints.

Architecture
------------
Uses RedisVL's SemanticCache with an HNSW index so look-ups are O(log N)
rather than a linear scan.  Every cache entry is scoped to a specific
(problem_id, stage) pair — a response for problem 1 will **never** be
served for problem 2, even if the query text is identical.

Key-space design
----------------
The cache is partitioned by ``problem_id`` + ``stage``.  This is achieved by
creating one SemanticCache instance per (problem_id, stage) pair, or — more
efficiently — by encoding them into the stored metadata and filtering on
retrieval.

Because RedisVL's SemanticCache doesn't expose a built-in metadata filter on
``check()``, we implement the scope guarantee by *namespacing the Redis index*
itself: each (problem_id, stage) pair gets its own named index under the
prefix ``leetbot:hints:{problem_id}:{stage}``.  This means:

  • Look-ups are always scoped to the exact (problem_id, stage) at the
    HNSW index level — zero risk of cross-problem contamination.
  • Index creation is lazy and idempotent (RedisVL handles this).
  • Memory is shared across workers because Redis is the backing store.

Similarity threshold
---------------------
Default: 0.92 (configurable via SEMANTIC_CACHE_THRESHOLD in .env).
Only a hit ≥ threshold triggers a cache return; misses fall through to
full RAG + generation.

TTL
---
Each entry has a TTL (default 7 days, configurable via SEMANTIC_CACHE_TTL_S).
This ensures stale hints (e.g. after problem content is refined) are evicted
automatically.

Embedding
---------
We reuse the Gemini embedding model already configured in settings
(GEMINI_EMBEDDING_MODEL) for consistency with the rest of the pipeline.
Embeddings are computed synchronously inside an executor to avoid blocking
the async event loop.

Usage pattern (in routers/hints.py)
------------------------------------
    from backend.rag.cache import HintSemanticCache

    cache = HintSemanticCache()            # one shared instance per process

    # Before generation:
    hit = await cache.check(problem_id="1", stage=2, query="two pointer approach?")
    if hit is not None:
        return hit  # cached response string

    # After generation:
    await cache.store(problem_id="1", stage=2, query="...", response="...")
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Optional

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy Redis + RedisVL initialisation
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_redis_client():
    """
    Return a connected ``redis.Redis`` client.
    Raises ``RuntimeError`` with a clear message if redis-py is not installed
    or if the connection fails.
    """
    try:
        import redis  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "redis-py is not installed. Run: pip install redis>=5.0.0"
        ) from exc

    client = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=False,  # RedisVL needs bytes
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    # Ping to surface connection errors early at startup rather than at
    # first cache access.
    try:
        client.ping()
        logger.info("Redis connected: %s", settings.REDIS_URL.split("@")[-1])
    except Exception as exc:
        logger.warning(
            "Redis connection failed — semantic cache disabled: %s", exc
        )
        raise RuntimeError(f"Redis unavailable: {exc}") from exc

    return client


def _make_index_name(problem_id: str, stage: int) -> str:
    """
    Return a deterministic Redis index name scoped to (problem_id, stage).

    E.g. ``leetbot:hints:42:3`` for problem 42, stage 3.
    The name is used as RedisVL's ``name`` parameter so each (problem, stage)
    pair gets its own independent HNSW index.
    """
    return f"leetbot:hints:{problem_id}:{stage}"


@lru_cache(maxsize=256)  # cache up to 256 distinct (problem, stage) instances
def _get_semantic_cache(problem_id: str, stage: int):
    """
    Return (or lazily create) a ``SemanticCache`` instance for a given
    (problem_id, stage) pair.

    RedisVL creates the HNSW index on first use; subsequent calls with the
    same name reuse the existing index, making this safe to call on every
    request.

    Returns ``None`` (and logs a warning) if RedisVL is not installed or
    Redis is not reachable, so callers can degrade gracefully.
    """
    try:
        from redisvl.extensions.llmcache import SemanticCache  # type: ignore
    except ImportError:
        logger.warning(
            "redisvl is not installed — semantic cache disabled. "
            "Run: pip install redisvl>=0.3.0"
        )
        return None

    try:
        redis_client = _get_redis_client()
    except RuntimeError as exc:
        logger.warning("Semantic cache disabled: %s", exc)
        return None

    try:
        cache = SemanticCache(
            name=_make_index_name(problem_id, stage),
            redis_client=redis_client,
            distance_threshold=1.0 - settings.SEMANTIC_CACHE_THRESHOLD,
            # SemanticCache uses *distance* not *similarity* — invert.
            ttl=settings.SEMANTIC_CACHE_TTL_S,
            vectorizer=_GeminiVectorizer(),
        )
        return cache
    except Exception as exc:
        logger.warning(
            "SemanticCache init failed for problem=%s stage=%d: %s",
            problem_id, stage, exc,
        )
        return None


# ---------------------------------------------------------------------------
# Gemini vectorizer shim for RedisVL
# ---------------------------------------------------------------------------

class _GeminiVectorizer:
    """
    Minimal vectorizer adapter that satisfies RedisVL's vectorizer interface
    using the Gemini embedding model already configured in the project.

    RedisVL's ``SemanticCache`` expects an object with:
        .embed(text: str) -> list[float]
        .dims            -> int
    """

    def __init__(self) -> None:
        self._embedder = GoogleGenerativeAIEmbeddings(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
        )
        self._dims: int | None = None

    # -- interface required by RedisVL ----------------------------------------

    @property
    def dims(self) -> int:
        if self._dims is None:
            sample = self._embedder.embed_query("probe")
            self._dims = len(sample)
        return self._dims

    def embed(self, text: str) -> list[float]:
        return self._embedder.embed_query(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed_documents(texts)


# ---------------------------------------------------------------------------
# Public cache interface
# ---------------------------------------------------------------------------

class HintSemanticCache:
    """
    Process-level singleton for semantic cache operations on hint responses.

    Thread/coroutine safety: RedisVL's ``SemanticCache.check()`` and
    ``store()`` are synchronous; we run them in ``loop.run_in_executor``
    so the async event loop is never blocked.

    Instantiate once at module level (or in the router file) and share
    the instance across requests.
    """

    # -- look-up ---------------------------------------------------------------

    async def check(
        self,
        *,
        problem_id: str,
        stage: int,
        query: str,
    ) -> Optional[str]:
        """
        Return a cached response string if a semantically similar query
        exists for this exact (problem_id, stage), or ``None`` on a miss.

        The similarity threshold (default 0.92) is applied inside RedisVL's
        HNSW look-up so only entries above the threshold are ever returned.

        Parameters
        ----------
        problem_id : The problem's string ID (e.g. ``"42"``).
        stage      : Hint stage (1–6).
        query      : The incoming user query / hint request string.

        Returns
        -------
        Cached response string, or ``None`` on a miss or cache unavailability.
        """
        sem_cache = _get_semantic_cache(problem_id, stage)
        if sem_cache is None:
            return None

        loop = asyncio.get_event_loop()
        try:
            results: list[dict] = await loop.run_in_executor(
                None,
                lambda: sem_cache.check(prompt=query),
            )
            if results:
                response_text: str = results[0].get("response", "")
                if response_text:
                    logger.info(
                        "Semantic cache HIT  problem=%s stage=%d (similarity≥%.2f)",
                        problem_id, stage, settings.SEMANTIC_CACHE_THRESHOLD,
                    )
                    return response_text
        except Exception as exc:
            logger.warning(
                "Semantic cache check error — bypassing cache: %s", exc
            )
        return None

    # -- write -----------------------------------------------------------------

    async def store(
        self,
        *,
        problem_id: str,
        stage: int,
        query: str,
        response: str,
    ) -> None:
        """
        Store a (query → response) pair in the semantic cache for
        (problem_id, stage).

        TTL is set automatically from ``settings.SEMANTIC_CACHE_TTL_S``.
        Errors are logged as warnings and never raised to the caller —
        a failed cache write should never break the request.

        Parameters
        ----------
        problem_id : The problem's string ID.
        stage      : Hint stage (1–6).
        query      : The original user query.
        response   : The full generated response string to cache.
        """
        sem_cache = _get_semantic_cache(problem_id, stage)
        if sem_cache is None:
            return

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: sem_cache.store(prompt=query, response=response),
            )
            logger.info(
                "Semantic cache WRITE problem=%s stage=%d (%d chars, TTL=%ds)",
                problem_id, stage, len(response), settings.SEMANTIC_CACHE_TTL_S,
            )
        except Exception as exc:
            logger.warning(
                "Semantic cache store error — response not cached: %s", exc
            )
