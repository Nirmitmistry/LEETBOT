"""
backend/rag/hybrid_retriever.py — Hybrid dense + sparse retrieval with RRF.

Pipeline
--------
1. Query transformation (optional, controlled by ``use_query_transform``):
   - Vague query  → HyDE: one hypothetical answer text is embedded + BM25'd
   - Normal query → Multi-query: 2-3 reformulations, each dense + BM25'd

2. Dense retrieval (Chroma similarity_search) per transformed query variant.

3. Sparse retrieval (BM25 from ``backend.rag.bm25_index``) per query variant.

4. Reciprocal Rank Fusion across ALL result lists (dense + sparse, all
   variants).  RRF score = Σ  1 / (k + rank_i)  for each unique document.
   Deduplication is by ``doc_id`` metadata field (falls back to page_content
   hash if absent).

5. Return the top ``candidate_k`` documents by RRF score to the caller
   (``retrieve_and_rerank`` in ``backend.rag.retriever``), which then runs
   the cross-encoder reranker on this widened candidate set.

Configuration flags (can be set per-request or globally via config)
-------------------------------------------------------------------
use_hybrid         : bool  — enables BM25 leg (default: settings.HYBRID_RETRIEVAL)
use_query_transform: bool  — enables HyDE/multi-query (default: settings.QUERY_TRANSFORM)
candidate_k        : int   — total candidates to return for reranking (default: settings.HYBRID_CANDIDATE_K)

Why RRF instead of score blending?
-----------------------------------
Dense cosine similarity scores and BM25 scores live on incompatible scales.
Score normalisation and weighting require careful per-collection calibration
and don't generalise across queries.  RRF depends only on *rank position*,
making it parameter-free and consistently robust across score distributions.
See: Cormack, Clarke & Buettcher (2009).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from pymongo.database import Database

from backend.config import settings
from backend.rag import bm25_index
from backend.rag.query_transform import generate_hyde, generate_multi_query, is_vague_query

logger = logging.getLogger(__name__)

# RRF constant — standard value from the original paper; larger k reduces the
# impact of very high-ranked documents from a single result list.
_RRF_K = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc_key(doc: Document) -> str:
    """
    Stable deduplication key for a Document.

    Prefers ``doc_id`` from metadata (set by the ingestion chunker) because
    it is a semantically meaningful stable identifier.  Falls back to a hash
    of page_content so Documents without a doc_id are still deduplicated.
    """
    doc_id = doc.metadata.get("doc_id")
    if doc_id:
        return str(doc_id)
    return hashlib.md5(doc.page_content.encode(), usedforsecurity=False).hexdigest()


def _rrf_fuse(result_lists: list[list[Document]]) -> list[Document]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.

    Each list contributes  1 / (_RRF_K + rank)  to the RRF score of every
    document it contains (rank is 1-indexed).  Documents are deduplicated by
    ``_doc_key``; the highest-scoring representative is kept in the output.

    Returns documents sorted by descending RRF score.
    """
    scores: dict[str, float] = {}
    best_doc: dict[str, Document] = {}

    for ranked_list in result_lists:
        for rank, doc in enumerate(ranked_list, start=1):
            key = _doc_key(doc)
            rrf_contribution = 1.0 / (_RRF_K + rank)
            scores[key] = scores.get(key, 0.0) + rrf_contribution
            if key not in best_doc:
                best_doc[key] = doc

    sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True)
    return [best_doc[k] for k in sorted_keys]


async def _dense_retrieve(
    query: str,
    chroma: Chroma,
    k: int,
    chroma_filter: dict[str, Any] | None,
) -> list[Document]:
    """Run a single dense similarity_search against Chroma (thread-pool)."""
    loop = asyncio.get_event_loop()

    def _search() -> list[Document]:
        kwargs: dict[str, Any] = {"query": query, "k": k}
        if chroma_filter:
            kwargs["filter"] = chroma_filter
        return chroma.similarity_search(**kwargs)

    try:
        return await loop.run_in_executor(None, _search)
    except Exception as exc:
        logger.error("Dense retrieval failed for query %r: %s", query[:60], exc)
        return []


def _sparse_retrieve(query: str, k: int) -> list[Document]:
    """Run BM25 retrieval synchronously (no I/O — pure CPU)."""
    if not bm25_index.is_ready():
        logger.debug("BM25 index not ready — skipping sparse leg")
        return []
    return bm25_index.bm25_retrieve(query, k=k)


# ---------------------------------------------------------------------------
# Public async entry-point
# ---------------------------------------------------------------------------

async def hybrid_retrieve(
    query: str,
    chroma: Chroma,
    *,
    use_hybrid: bool | None = None,
    use_query_transform: bool | None = None,
    candidate_k: int | None = None,
    chroma_filter: dict[str, Any] | None = None,
) -> list[Document]:
    """
    Hybrid dense + sparse retrieval with optional query transformation.

    This is the entry-point called by ``retrieve_and_rerank`` in
    ``backend.rag.retriever``.  It returns a widened candidate set
    (``candidate_k`` docs) for the downstream cross-encoder reranker.

    Parameters
    ----------
    query               : Raw user query.
    chroma              : Chroma instance (injected from ``backend.db``).
    use_hybrid          : Enable BM25 sparse leg.  Defaults to
                          ``settings.HYBRID_RETRIEVAL``.
    use_query_transform : Enable HyDE / multi-query.  Defaults to
                          ``settings.QUERY_TRANSFORM``.
    candidate_k         : Total candidates to return.  Defaults to
                          ``settings.HYBRID_CANDIDATE_K``.
    chroma_filter       : Optional metadata filter forwarded to Chroma.

    Returns
    -------
    List of unique Documents sorted by RRF score, capped at *candidate_k*.
    """
    do_hybrid = use_hybrid if use_hybrid is not None else settings.HYBRID_RETRIEVAL
    do_transform = (
        use_query_transform
        if use_query_transform is not None
        else settings.QUERY_TRANSFORM
    )
    k = candidate_k if candidate_k is not None else settings.HYBRID_CANDIDATE_K

    # Per-leg fetch size: fetch more per leg so fusion has enough material.
    # With N query variants each returning k docs, RRF naturally promotes
    # consistently high-ranked docs over single-list flukes.
    per_leg_k = max(k, 20)

    # ── Step 1: Build query list via transformation ──────────────────────────
    if do_transform:
        if is_vague_query(query):
            hyde_text = await generate_hyde(query)
            # For HyDE: embed the synthetic answer; also keep original for BM25
            query_variants_dense = [hyde_text]
            query_variants_sparse = [hyde_text, query]  # raw query helps BM25
            logger.debug("Query transform: HyDE applied for vague query")
        else:
            query_variants_dense = await generate_multi_query(query, n=2)
            query_variants_sparse = query_variants_dense  # same set for BM25
            logger.debug(
                "Query transform: multi-query generated %d variants",
                len(query_variants_dense),
            )
    else:
        query_variants_dense = [query]
        query_variants_sparse = [query]

    # ── Step 2: Gather all retrieval tasks concurrently ─────────────────────
    dense_tasks = [
        _dense_retrieve(q, chroma, per_leg_k, chroma_filter)
        for q in query_variants_dense
    ]

    dense_results: list[list[Document]] = await asyncio.gather(*dense_tasks)

    # BM25 is CPU-bound sync — run in thread-pool to avoid blocking the loop
    if do_hybrid:
        loop = asyncio.get_event_loop()
        sparse_results: list[list[Document]] = await asyncio.gather(
            *[
                loop.run_in_executor(None, _sparse_retrieve, q, per_leg_k)
                for q in query_variants_sparse
            ]
        )
    else:
        sparse_results = []

    # ── Step 3: RRF fusion across all result lists ───────────────────────────
    all_lists: list[list[Document]] = list(dense_results)
    if sparse_results:
        all_lists.extend(sparse_results)

    fused = _rrf_fuse(all_lists)

    logger.debug(
        "Hybrid retrieve — dense legs: %d, sparse legs: %d, "
        "fused candidates: %d → returning top %d",
        len(dense_results),
        len(sparse_results),
        len(fused),
        k,
    )

    return fused[:k]
