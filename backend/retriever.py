"""
backend/retriever.py — Public retrieval API for LEETBOT routers.

This module is the stable entry-point that all routers import.  It delegates
to ``backend.rag.retriever`` which implements the full hybrid retrieval
pipeline:

    Query transform (HyDE / multi-query)
    →  Dense (Chroma) + Sparse (BM25) retrieval, fused with RRF
    →  MongoDB hydration (full problem docs)
    →  Cross-encoder reranking
    →  LLM context

Existing router call sites continue to work unchanged because the public
signature of ``retrieve_and_rerank`` is backwards-compatible.  Two new
optional kwargs are available for A/B testing:

    use_hybrid          : bool  — enable BM25 sparse leg (default: settings.HYBRID_RETRIEVAL)
    use_query_transform : bool  — enable HyDE/multi-query (default: settings.QUERY_TRANSFORM)

Configuration (all via .env / config.py)
-----------------------------------------
RERANKER_BACKEND          local | cohere   (default: local)
RERANKER_CANDIDATE_K      candidates from Chroma for dense-only mode  (default: 25)
RERANKER_TOP_N            docs kept after rerank  (default: 4)
RERANKER_THRESHOLD        minimum rerank score    (default: -5.0)
RERANKER_LOCAL_MODEL      sentence-transformers model id
COHERE_API_KEY            required for cohere backend
HYBRID_RETRIEVAL          true | false  (default: true)
QUERY_TRANSFORM           true | false  (default: true)
HYBRID_CANDIDATE_K        candidates from hybrid retrieval before reranking (default: 30)
"""

from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.documents import Document
from pymongo.database import Database

# Re-export the implementation so callers can do either:
#   from backend.retriever import retrieve_and_rerank
#   from backend.rag.retriever import retrieve_and_rerank
from backend.rag.retriever import (  # noqa: F401 — re-exported
    retrieve_and_rerank,
    _get_local_cross_encoder,    # noqa: F401 — exposed for tests / warm-up
    _build_full_problem_text,    # noqa: F401 — exposed for tests
)

__all__ = [
    "retrieve_and_rerank",
    "_get_local_cross_encoder",
    "_build_full_problem_text",
]
