"""
retriever.py — Chroma retrieval + cross-encoder reranking pipeline.

Flow
----
1.  Chroma similarity_search  →  top-K candidates  (dense retrieval)
2.  Cross-encoder reranker    →  scored & filtered  (local or Cohere)
3.  Threshold filter          →  drop weak chunks
4.  Lost-in-the-middle sort   →  strongest at edges, weakest in the middle
5.  Return top-N documents    →  ready for LLM context

Config flags (all via environment / config.py)
-----------------------------------------------
RERANKER_BACKEND        local | cohere   (default: local)
RERANKER_CANDIDATE_K    candidates pulled from Chroma  (default: 25)
RERANKER_TOP_N          documents kept after rerank    (default: 4)
RERANKER_THRESHOLD      minimum score to keep a chunk  (default: -5.0 for
                        local cross-encoder logits; 0.05 for Cohere 0-1 scores)
RERANKER_LOCAL_MODEL    sentence-transformers model id (default: BAAI/bge-reranker-large)
COHERE_API_KEY          required when RERANKER_BACKEND=cohere
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy-loaded local cross-encoder (loaded once, reused across requests)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_local_cross_encoder():
    """Load the CrossEncoder model exactly once (thread-safe via lru_cache)."""
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
        model = CrossEncoder(
            settings.RERANKER_LOCAL_MODEL,
            max_length=512,
        )
        logger.info("CrossEncoder loaded: %s", settings.RERANKER_LOCAL_MODEL)
        return model
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        ) from exc


# ---------------------------------------------------------------------------
# Scoring helpers (synchronous — called inside executor)
# ---------------------------------------------------------------------------

def _score_local(query: str, docs: list[Document]) -> list[float]:
    """Return raw cross-encoder logit scores (higher = more relevant)."""
    cross_encoder = _get_local_cross_encoder()
    pairs = [[query, doc.page_content] for doc in docs]
    scores: list[float] = cross_encoder.predict(pairs).tolist()
    return scores


def _score_cohere(query: str, docs: list[Document]) -> list[float]:
    """Return Cohere rerank scores in [0, 1] (higher = more relevant)."""
    try:
        import cohere  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "cohere package is not installed. Run: pip install cohere"
        ) from exc

    api_key = settings.COHERE_API_KEY
    if not api_key:
        raise RuntimeError(
            "COHERE_API_KEY is not set but RERANKER_BACKEND=cohere"
        )

    co = cohere.Client(api_key)
    response = co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=[doc.page_content for doc in docs],
        top_n=len(docs),
        return_documents=False,
    )

    # response.results is ordered by relevance_score desc with original index
    scores: list[float] = [0.0] * len(docs)
    for result in response.results:
        scores[result.index] = result.relevance_score
    return scores


def _rerank_sync(
    query: str,
    docs: list[Document],
    backend: str,
    threshold: float,
    top_n: int,
) -> list[Document]:
    """
    Synchronous reranking — runs inside a thread-pool executor so it never
    blocks the FastAPI event loop.

    Returns at most *top_n* documents that exceed *threshold*, ordered using
    the lost-in-the-middle strategy (strongest at position 0 and -1, weakest
    in the middle).
    """
    if not docs:
        return []

    # 1. Score
    try:
        if backend == "cohere":
            scores = _score_cohere(query, docs)
        else:
            scores = _score_local(query, docs)
    except Exception as exc:
        logger.error("Reranker (%s) failed — returning unranked docs: %s", backend, exc)
        return docs[:top_n]

    # 2. Attach scores and filter by threshold
    scored = [
        (score, doc) for score, doc in zip(scores, docs)
        if score >= threshold
    ]

    if not scored:
        logger.warning(
            "All %d candidates fell below threshold %.2f — returning top-%d unfiltered",
            len(docs), threshold, top_n,
        )
        # Graceful fallback: still sort and return best ones
        scored = list(zip(scores, docs))

    # 3. Sort descending by score, cap at top_n
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    # 4. Lost-in-the-middle reorder:
    #    strongest → position 0, second-strongest → position -1, rest fill middle
    if len(top) <= 2:
        reordered: list[Document] = [doc for _, doc in top]
    else:
        reordered = [None] * len(top)  # type: ignore[list-item]
        left, right = 0, len(top) - 1
        for i, (_, doc) in enumerate(top):
            if i % 2 == 0:
                reordered[left] = doc
                left += 1
            else:
                reordered[right] = doc
                right -= 1

    logger.debug(
        "Reranked %d → kept %d (threshold=%.2f, backend=%s)",
        len(docs), len(reordered), threshold, backend,
    )
    return reordered


# ---------------------------------------------------------------------------
# Public async API — used by routers
# ---------------------------------------------------------------------------

async def retrieve_and_rerank(
    query: str,
    chroma: Chroma,
    *,
    candidate_k: int | None = None,
    top_n: int | None = None,
    threshold: float | None = None,
    chroma_filter: dict[str, Any] | None = None,
) -> list[Document]:
    """
    Retrieve candidate documents from Chroma, rerank them, and return the
    best results ready for LLM context.

    Parameters
    ----------
    query        : The user query / problem text used for both retrieval and reranking.
    chroma       : Injected Chroma instance (from get_chroma()).
    candidate_k  : Override for RERANKER_CANDIDATE_K.
    top_n        : Override for RERANKER_TOP_N.
    threshold    : Override for RERANKER_THRESHOLD.
    chroma_filter: Metadata filter dict passed to Chroma (e.g. {"hint_stage": 0}).

    Returns
    -------
    List of Document objects, reranked and reordered for LLM consumption.
    """
    k = candidate_k if candidate_k is not None else settings.RERANKER_CANDIDATE_K
    n = top_n if top_n is not None else settings.RERANKER_TOP_N
    thresh = threshold if threshold is not None else settings.RERANKER_THRESHOLD
    backend = settings.RERANKER_BACKEND

    # Step 1: Dense retrieval from Chroma
    try:
        kwargs: dict[str, Any] = {"query": query, "k": k}
        if chroma_filter:
            kwargs["filter"] = chroma_filter
        candidates: list[Document] = chroma.similarity_search(**kwargs)
    except Exception as exc:
        logger.error("Chroma similarity_search failed: %s", exc)
        return []

    if not candidates:
        return []

    # Steps 2-4: Rerank in a thread-pool so CPU work doesn't block the event loop
    loop = asyncio.get_event_loop()
    reranked = await loop.run_in_executor(
        None,  # default ThreadPoolExecutor
        _rerank_sync,
        query,
        candidates,
        backend,
        thresh,
        n,
    )

    return reranked
