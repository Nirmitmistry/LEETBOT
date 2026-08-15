"""
backend/rag/bm25_index.py — Sparse BM25 retrieval leg for hybrid search.

The BM25 index is built *in-process* from the same chunk corpus that lives in
Chroma.  On startup (via ``warm_bm25_index``) we read every document out of
Chroma's collection, tokenise the page_content, and fit a BM25Okapi model.
The index is then kept in a module-level singleton so retrieval calls are
O(1) lookup + O(k·vocab) scoring — no disk I/O per request.

Sync strategy
-------------
``warm_bm25_index(chroma)`` is called once from ``backend.db.connect_db``.
If the Chroma collection is empty (e.g. fresh dev environment) the index is
left as None and BM25 retrieval degrades gracefully to an empty result set.
The index can be refreshed at any time by calling ``warm_bm25_index`` again
(e.g. after an ingestion run) — it replaces the singleton atomically.

Tokenisation
------------
We use a simple whitespace + punctuation split lowercased tokeniser.  This is
intentionally lightweight — BM25 is the *lexical* complement to dense search;
heavy NLP preprocessing is not needed here.  stop-word removal is omitted to
keep dependencies minimal (rank_bm25 is already enough).
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# ── Module-level singleton protected by a read-write lock ────────────────────
_bm25_lock = threading.Lock()

# Each entry: {"document": Document, "tokens": list[str]}
_corpus: list[dict[str, Any]] = []
_bm25_model: Any = None  # rank_bm25.BM25Okapi | None


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenise(text: str) -> list[str]:
    """Lowercase whitespace/punctuation split — fast and dependency-free."""
    return _TOKEN_RE.findall(text.lower())


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

def warm_bm25_index(chroma: Chroma) -> int:
    """
    Build (or rebuild) the BM25 index from all documents in *chroma*.

    Returns the number of documents indexed.  Thread-safe: replaces the
    module-level singleton atomically under ``_bm25_lock``.

    Called from ``backend.db.connect_db`` at startup, and can be called
    again after ingestion to refresh the index without restarting the server.
    """
    global _corpus, _bm25_model

    try:
        from rank_bm25 import BM25Okapi  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "rank_bm25 is not installed. Run: pip install rank-bm25"
        ) from exc

    try:
        # Chroma's get() without IDs returns the entire collection.
        # Large collections (>100k chunks) should still fit in RAM because
        # we only keep text + metadata, not embeddings.
        result = chroma._collection.get()
    except Exception as exc:
        logger.error("BM25 warm-up: failed to read Chroma collection — %s", exc)
        return 0

    documents_text: list[str] = result.get("documents") or []
    metadatas: list[dict] = result.get("metadatas") or []

    if not documents_text:
        logger.warning("BM25 warm-up: Chroma collection is empty — sparse index not built")
        return 0

    # Pad metadatas if Chroma omitted them (shouldn't happen but be safe)
    while len(metadatas) < len(documents_text):
        metadatas.append({})

    new_corpus: list[dict[str, Any]] = []
    tokenised: list[list[str]] = []

    for text, meta in zip(documents_text, metadatas):
        tokens = _tokenise(text)
        doc = Document(page_content=text, metadata=meta)
        new_corpus.append({"document": doc, "tokens": tokens})
        tokenised.append(tokens)

    new_model = BM25Okapi(tokenised)

    with _bm25_lock:
        _corpus = new_corpus
        _bm25_model = new_model

    logger.info("BM25 index built — %d chunks indexed", len(new_corpus))
    return len(new_corpus)


def is_ready() -> bool:
    """Return True if the BM25 index has been built and is ready to query."""
    return _bm25_model is not None


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def bm25_retrieve(query: str, k: int = 20) -> list[Document]:
    """
    Return the top-*k* Documents from the BM25 index for *query*.

    Returns an empty list (rather than raising) if the index has not been
    built yet, allowing graceful degradation to dense-only retrieval.

    Parameters
    ----------
    query : The raw user query or a HyDE/multi-query expansion string.
    k     : Maximum number of documents to return.

    Returns
    -------
    List of Document objects ordered by descending BM25 score.
    Documents with a score of 0.0 (no term overlap) are excluded.
    """
    with _bm25_lock:
        model = _bm25_model
        corpus = _corpus

    if model is None or not corpus:
        logger.debug("BM25 retrieve called but index is not ready — returning empty")
        return []

    tokens = _tokenise(query)
    if not tokens:
        return []

    scores: list[float] = model.get_scores(tokens).tolist()

    # Pair (score, Document) and sort descending
    ranked = sorted(
        ((s, entry["document"]) for s, entry in zip(scores, corpus) if s > 0.0),
        key=lambda x: x[0],
        reverse=True,
    )

    return [doc for _, doc in ranked[:k]]
