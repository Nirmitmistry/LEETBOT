"""
backend/rag/retriever.py — Parent-document retrieval for LEETBOT.

Architecture
------------
Chroma stores *child chunks* (statement, constraints, example_N,
editorial_approach_N, hint_N, solutions).  Each chunk carries a
``problem_id`` metadata field that maps back to the full problem document
in MongoDB.

Retrieval flow
--------------
1.  Dense retrieval from Chroma  →  top-K child chunks
2.  Deduplicate by problem_id    →  collect unique parent IDs from the hits
3.  Hydrate from MongoDB         →  fetch full problem docs for those IDs
4.  Build enriched Documents     →  one Document per unique problem, with
                                     page_content = full problem text, and
                                     metadata = original chunk metadata
                                     (preserves chunk_type / hint_stage for
                                     downstream filtering)
5.  Cross-encoder reranking      →  score hydrated docs against the query
6.  Threshold filter + LitM sort →  ready for LLM context

Why hydrate?
------------
Child chunks are intentionally small so the embedding captures a tight
semantic signal (e.g. "constraints" or a single example).  But once
retrieved, the LLM benefits from the *full* problem context rather than
just the matching fragment.  Hydration brings back everything: statement,
all examples, constraints, hints, editorial — giving the model maximum
context while keeping retrieval precision high.

Configuration (all via .env / config.py)
-----------------------------------------
RERANKER_BACKEND          local | cohere   (default: local)
RERANKER_CANDIDATE_K      candidates from Chroma  (default: 25)
RERANKER_TOP_N            docs kept after rerank  (default: 4)
RERANKER_THRESHOLD        minimum rerank score    (default: -5.0)
RERANKER_LOCAL_MODEL      sentence-transformers model id
COHERE_API_KEY            required for cohere backend
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from pymongo.database import Database

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
        model = CrossEncoder(settings.RERANKER_LOCAL_MODEL, max_length=512)
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
    return cross_encoder.predict(pairs).tolist()


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
        raise RuntimeError("COHERE_API_KEY is not set but RERANKER_BACKEND=cohere")

    co = cohere.Client(api_key)
    response = co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=[doc.page_content for doc in docs],
        top_n=len(docs),
        return_documents=False,
    )

    scores: list[float] = [0.0] * len(docs)
    for result in response.results:
        scores[result.index] = result.relevance_score
    return scores


# ---------------------------------------------------------------------------
# Parent-document hydration
# ---------------------------------------------------------------------------

def _build_full_problem_text(problem: dict) -> str:
    """
    Render a full problem document as a single text blob for the LLM.
    Includes title, statement, constraints, examples, hints, and editorial.
    Solutions are omitted by default (they can be gated separately).
    """
    lines: list[str] = []

    title = problem.get("title") or problem.get("slug", "")
    if title:
        lines.append(f"# {title}")

    difficulty = problem.get("difficulty", "")
    tags = problem.get("tags", [])
    if isinstance(tags, list):
        tags_str = ", ".join(tags)
    else:
        tags_str = str(tags)
    if difficulty or tags_str:
        lines.append(f"Difficulty: {difficulty}  |  Tags: {tags_str}")

    statement = (problem.get("problem_statement") or "").strip()
    if statement:
        lines.append("\n## Problem\n" + statement)

    constraints = problem.get("constraints", "")
    if isinstance(constraints, list):
        constraints = "\n".join(constraints)
    constraints = constraints.strip()
    if constraints:
        lines.append("\n## Constraints\n" + constraints)

    examples = problem.get("examples", [])
    if isinstance(examples, list) and examples:
        lines.append("\n## Examples")
        for i, ex in enumerate(examples, 1):
            inp = str(ex.get("input", "")).strip()
            out = str(ex.get("output", "")).strip()
            exp = str(ex.get("explanation", "")).strip()
            parts = [f"**Example {i}**"]
            if inp:
                parts.append(f"Input:  {inp}")
            if out:
                parts.append(f"Output: {out}")
            if exp:
                parts.append(f"Explanation: {exp}")
            lines.append("\n".join(parts))

    hints = problem.get("hints", {})
    if isinstance(hints, dict):
        hint_lines = [
            f"  Stage {n}: {hints[f'stage_{n}'].strip()}"
            for n in range(1, 5)
            if hints.get(f"stage_{n}", "").strip()
        ]
        if hint_lines:
            lines.append("\n## Hints\n" + "\n".join(hint_lines))

    editorial = problem.get("editorial", {})
    if isinstance(editorial, dict):
        editorial_text = (editorial.get("content") or "").strip()
    elif isinstance(editorial, str):
        editorial_text = editorial.strip()
    else:
        editorial_text = ""
    if editorial_text:
        lines.append("\n## Editorial\n" + editorial_text)

    return "\n".join(lines)


def _hydrate_from_mongo(
    chunk_hits: list[Document],
    db: Database,
) -> list[Document]:
    """
    Given a list of child-chunk Documents retrieved from Chroma, fetch the
    corresponding full problem documents from MongoDB and return one hydrated
    Document per *unique* problem_id.

    The hydrated Document carries:
      - page_content : full problem text (title + statement + examples + …)
      - metadata     : metadata from the *highest-scoring* child chunk for
                       that problem_id (preserves chunk_type, hint_stage, etc.)

    Order of returned documents follows the order of first appearance in
    chunk_hits so that Chroma's relevance ranking is preserved.
    """
    # Collect unique problem IDs while preserving order of first hit
    seen: dict[str, Document] = {}  # problem_id → representative child chunk
    for chunk in chunk_hits:
        pid = chunk.metadata.get("problem_id")
        if pid and pid not in seen:
            seen[pid] = chunk

    if not seen:
        return []

    # Batch-fetch all parent documents from MongoDB in one query
    int_ids = []
    str_ids = []
    for pid in seen:
        try:
            int_ids.append(int(pid))
        except (ValueError, TypeError):
            str_ids.append(pid)

    query_ids = int_ids if int_ids else str_ids
    problems_col = db[settings.MONGO_PROBLEMS_COLLECTION]
    raw_docs = list(problems_col.find({"_id": {"$in": query_ids}}))

    # Build a lookup: str(_id) → raw doc
    mongo_lookup: dict[str, dict] = {str(d["_id"]): d for d in raw_docs}

    hydrated: list[Document] = []
    for pid, child_chunk in seen.items():
        raw = mongo_lookup.get(pid)
        if raw is None:
            # Parent not found in Mongo — fall back to the child chunk text
            logger.warning(
                "Parent document not found in MongoDB for problem_id=%s; "
                "falling back to child chunk content",
                pid,
            )
            hydrated.append(child_chunk)
            continue

        full_text = _build_full_problem_text(raw)
        hydrated.append(Document(
            page_content=full_text,
            metadata={
                **child_chunk.metadata,          # preserves chunk_type, hint_stage, etc.
                "hydrated":    True,
                "problem_id":  pid,
            },
        ))

    return hydrated


# ---------------------------------------------------------------------------
# Reranking (synchronous — runs in thread-pool)
# ---------------------------------------------------------------------------

def _rerank_sync(
    query: str,
    docs: list[Document],
    backend: str,
    threshold: float,
    top_n: int,
) -> list[Document]:
    """
    Rerank *docs* against *query*, filter by threshold, cap at top_n, and
    apply the lost-in-the-middle reordering strategy.
    """
    if not docs:
        return []

    try:
        if backend == "cohere":
            scores = _score_cohere(query, docs)
        else:
            scores = _score_local(query, docs)
    except Exception as exc:
        logger.error("Reranker (%s) failed — returning unranked docs: %s", backend, exc)
        return docs[:top_n]

    # Filter by threshold
    scored = [(s, d) for s, d in zip(scores, docs) if s >= threshold]
    if not scored:
        logger.warning(
            "All %d candidates fell below threshold %.2f — returning top-%d unfiltered",
            len(docs), threshold, top_n,
        )
        scored = list(zip(scores, docs))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    # Lost-in-the-middle reorder: strongest at edges, weakest in the middle
    if len(top) <= 2:
        return [d for _, d in top]

    reordered: list[Document | None] = [None] * len(top)
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
    return [d for d in reordered if d is not None]


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def retrieve_and_rerank(
    query: str,
    chroma: Chroma,
    db: Database,
    *,
    candidate_k: int | None = None,
    top_n: int | None = None,
    threshold: float | None = None,
    chroma_filter: dict[str, Any] | None = None,
    use_hybrid: bool | None = None,
    use_query_transform: bool | None = None,
) -> list[Document]:
    """
    Full parent-document retrieval pipeline with optional hybrid retrieval.

    Steps
    -----
    1.  Hybrid retrieval (dense Chroma + sparse BM25 via RRF) or dense-only
        →  top-K child chunks (widened candidate set when hybrid is active)
    2.  Hydrate from MongoDB         →  full problem documents
    3.  Rerank hydrated docs         →  cross-encoder scored & filtered
    4.  Return top-N for LLM context

    Parameters
    ----------
    query              : User query / problem description.
    chroma             : Injected Chroma instance (from ``backend.db.get_chroma``).
    db                 : Injected MongoDB Database (from ``backend.db.get_db``).
    candidate_k        : Override for RERANKER_CANDIDATE_K (dense-only) or
                         HYBRID_CANDIDATE_K (hybrid mode).
    top_n              : Override for RERANKER_TOP_N.
    threshold          : Override for RERANKER_THRESHOLD.
    chroma_filter      : Metadata filter dict passed to Chroma
                         (e.g. ``{"hint_stage": 0}`` to exclude hint/solution chunks).
    use_hybrid         : Enable BM25 sparse leg + RRF fusion.
                         Defaults to ``settings.HYBRID_RETRIEVAL``.
                         Pass ``False`` explicitly to force dense-only for A/B testing.
    use_query_transform: Enable HyDE / multi-query transformation.
                         Defaults to ``settings.QUERY_TRANSFORM``.
                         Pass ``False`` explicitly to disable for A/B testing.

    Returns
    -------
    List of hydrated Document objects, reranked and reordered for the LLM.
    Each document's ``page_content`` is the *full* problem text from MongoDB.
    ``metadata["hydrated"]`` is ``True`` when hydration succeeded.
    """
    n = top_n if top_n is not None else settings.RERANKER_TOP_N
    thresh = threshold if threshold is not None else settings.RERANKER_THRESHOLD
    backend = settings.RERANKER_BACKEND

    # Resolve whether hybrid mode is active for this request
    do_hybrid = use_hybrid if use_hybrid is not None else settings.HYBRID_RETRIEVAL

    # ── Step 1: Retrieval (hybrid or dense-only) ──────────────────────────────
    if do_hybrid:
        # Hybrid path: query transform → dense + BM25 → RRF → candidate set
        from backend.rag.hybrid_retriever import hybrid_retrieve  # avoid circular at module level

        # candidate_k in hybrid mode targets the wider HYBRID_CANDIDATE_K budget
        hybrid_k = candidate_k if candidate_k is not None else settings.HYBRID_CANDIDATE_K

        try:
            chunk_hits: list[Document] = await hybrid_retrieve(
                query=query,
                chroma=chroma,
                use_hybrid=True,
                use_query_transform=use_query_transform,
                candidate_k=hybrid_k,
                chroma_filter=chroma_filter,
            )
        except Exception as exc:
            logger.error("Hybrid retrieval failed — falling back to dense-only: %s", exc)
            chunk_hits = []

        if not chunk_hits:
            # Graceful dense-only fallback
            logger.warning("Hybrid retrieve returned no results — falling back to dense search")
            dense_k = candidate_k if candidate_k is not None else settings.RERANKER_CANDIDATE_K
            try:
                kwargs: dict[str, Any] = {"query": query, "k": dense_k}
                if chroma_filter:
                    kwargs["filter"] = chroma_filter
                chunk_hits = chroma.similarity_search(**kwargs)
            except Exception as exc2:
                logger.error("Dense fallback also failed: %s", exc2)
                return []

        logger.debug("Hybrid retrieve returned %d candidate chunks", len(chunk_hits))

    else:
        # Dense-only path (original behaviour, preserved for A/B testing)
        k = candidate_k if candidate_k is not None else settings.RERANKER_CANDIDATE_K
        try:
            kwargs = {"query": query, "k": k}
            if chroma_filter:
                kwargs["filter"] = chroma_filter
            chunk_hits = chroma.similarity_search(**kwargs)
        except Exception as exc:
            logger.error("Chroma similarity_search failed: %s", exc)
            return []

        logger.debug("Dense-only: Chroma returned %d child chunks", len(chunk_hits))

    if not chunk_hits:
        return []

    # ── Step 2: Hydrate from MongoDB (sync I/O in executor) ──────────────────
    loop = asyncio.get_event_loop()
    hydrated: list[Document] = await loop.run_in_executor(
        None,
        _hydrate_from_mongo,
        chunk_hits,
        db,
    )

    if not hydrated:
        return []

    logger.debug("Hydrated %d unique parent documents", len(hydrated))

    # ── Steps 3-4: Rerank in thread-pool ─────────────────────────────────────
    reranked: list[Document] = await loop.run_in_executor(
        None,
        _rerank_sync,
        query,
        hydrated,
        backend,
        thresh,
        n,
    )

    return reranked
