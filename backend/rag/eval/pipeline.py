"""
backend/rag/eval/pipeline.py — Full retrieval + generation pipeline for eval.

This module wires together the existing LEETBOT components in the same way the
live hint endpoint does, but as a standalone async function that:

  1. Runs ``retrieve_and_rerank`` (hybrid or dense-only, controlled by
     the same config flags used in production).
  2. Generates an answer with Gemini using the reranked context.
  3. Returns both the retrieved context strings and the generated answer
     so the Ragas scorer can compute all four metrics.

It intentionally does NOT go through the hints router — we don't want to
depend on MongoDB hint sessions or stage logic during evaluation.  Instead
we drive the LLM directly with a clean "answer this question given this
context" prompt that mirrors what the hints endpoint would produce.

Connection management
---------------------
The pipeline opens its own MongoDB + Chroma connections for the eval run and
tears them down when done, so it can be run outside a running FastAPI server.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pymongo import MongoClient
from pymongo.database import Database

from backend.config import settings
from backend.rag.retriever import retrieve_and_rerank
from backend.rag.eval.schema import GoldenEntry, QueryResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Generation prompt — neutral "answer from context" format for eval
# ---------------------------------------------------------------------------

_EVAL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are an expert LeetCode tutor. "
            "Answer the student's question using ONLY the provided context. "
            "Be concise and accurate. If the context does not contain enough "
            "information to answer, say so explicitly."
        ),
    ),
    (
        "human",
        (
            "Context:\n{context}\n\n"
            "---\n"
            "Question: {question}\n\n"
            "Answer:"
        ),
    ),
])


def _make_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL_NAME,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.1,   # lower temperature for reproducible eval answers
    )


# ---------------------------------------------------------------------------
# Connection helpers (eval-specific — no FastAPI dependency injection)
# ---------------------------------------------------------------------------

def _open_connections() -> tuple[MongoClient, Database, Chroma]:
    """
    Open MongoDB and Chroma connections for a standalone eval run.
    Returns (client, db, chroma).  Caller must call ``client.close()`` after.
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    import os

    # MongoDB
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=10_000)
    db = client[settings.MONGO_DB_NAME]
    client.admin.command("ping")
    logger.info("Eval: MongoDB connected (%s)", settings.MONGO_DB_NAME)

    # Chroma
    os.makedirs(settings.CHROMA_PATH, exist_ok=True)
    embeddings = GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
    )
    chroma = Chroma(
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=settings.CHROMA_PATH,
    )
    count = chroma._collection.count()
    logger.info("Eval: Chroma ready (%d vectors)", count)

    # BM25 warm-up (mirrors db.connect_db)
    if settings.HYBRID_RETRIEVAL:
        try:
            from backend.rag.bm25_index import warm_bm25_index
            n = warm_bm25_index(chroma)
            logger.info("Eval: BM25 index warmed (%d chunks)", n)
        except Exception as exc:
            logger.warning("Eval: BM25 warm-up failed (non-fatal): %s", exc)

    return client, db, chroma


# ---------------------------------------------------------------------------
# Single-entry pipeline
# ---------------------------------------------------------------------------

async def run_single(
    entry: GoldenEntry,
    db: Database,
    chroma: Chroma,
) -> QueryResult:
    """
    Run the full retrieval + generation pipeline for one golden entry.

    Returns a ``QueryResult`` with populated ``retrieved_context``,
    ``generated_answer``, latency fields, and an ``error`` string if anything
    went wrong (so the harness can continue rather than crash on one bad entry).
    """
    result = QueryResult(
        sample_id=entry.id,
        problem_id=entry.problem_id,
        slug=entry.slug,
        question=entry.question,
        query_type=entry.query_type,
        ground_truth_answer=entry.ground_truth_answer,
        expected_context_chunk_ids=entry.expected_context_chunk_ids,
    )

    # ── Step 1: Retrieval ─────────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        docs: list[Document] = await retrieve_and_rerank(
            query=entry.question,
            chroma=chroma,
            db=db,
        )
        result.retrieval_latency_s = time.perf_counter() - t0

        result.retrieved_context = [d.page_content for d in docs]
        result.retrieved_chunk_ids = [
            str(d.metadata.get("doc_id", d.metadata.get("problem_id", "")))
            for d in docs
        ]
        logger.debug(
            "Entry %s: retrieved %d docs in %.2fs",
            entry.id, len(docs), result.retrieval_latency_s,
        )
    except Exception as exc:
        result.error = f"Retrieval failed: {exc}"
        logger.error("Entry %s — retrieval error: %s", entry.id, exc)
        return result

    if not result.retrieved_context:
        result.error = "Retrieval returned empty context"
        logger.warning("Entry %s — empty context", entry.id)
        return result

    # ── Step 2: Generation ────────────────────────────────────────────────────
    t1 = time.perf_counter()
    try:
        context_text = "\n\n---\n\n".join(result.retrieved_context)
        llm = _make_llm()
        chain = _EVAL_PROMPT | llm | StrOutputParser()

        # Run blocking chain.invoke in the thread-pool
        loop = asyncio.get_event_loop()
        result.generated_answer = await loop.run_in_executor(
            None,
            lambda: chain.invoke({"context": context_text, "question": entry.question}),
        )
        result.generation_latency_s = time.perf_counter() - t1
        logger.debug(
            "Entry %s: generated answer in %.2fs (%d chars)",
            entry.id, result.generation_latency_s, len(result.generated_answer),
        )
    except Exception as exc:
        result.error = f"Generation failed: {exc}"
        logger.error("Entry %s — generation error: %s", entry.id, exc)

    return result


# ---------------------------------------------------------------------------
# Full dataset pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(
    entries: list[GoldenEntry],
    db: Database,
    chroma: Chroma,
    *,
    concurrency: int = 3,
) -> list[QueryResult]:
    """
    Run the pipeline for all entries with bounded concurrency.

    ``concurrency`` controls how many entries run simultaneously.  Keeping
    this low (default 3) avoids hammering the Gemini API rate limit.
    Results are returned in the same order as ``entries``.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(entry: GoldenEntry) -> QueryResult:
        async with semaphore:
            return await run_single(entry, db, chroma)

    tasks = [_bounded(e) for e in entries]
    results: list[QueryResult] = await asyncio.gather(*tasks)
    return results
