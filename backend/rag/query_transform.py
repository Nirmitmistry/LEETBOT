"""
backend/rag/query_transform.py — Query transformation for hybrid retrieval.

Two transformation strategies are provided:

HyDE (Hypothetical Document Embedding)
    Used when the query is *vague* — short (<6 words) or contains hedge words
    like "stuck", "hint", "help", "don't get it".  The LLM is asked to write
    a short *hypothetical answer* to the query; that synthetic text is then
    embedded instead of the raw query.  The intuition: a hypothetical answer
    lives in the same embedding neighbourhood as real answers, yielding better
    dense retrieval than embedding a 3-word user message.

Multi-Query
    Used for more specific queries.  The LLM generates 2–3 semantically varied
    reformulations of the question.  Dense and sparse retrieval are run
    separately for each reformulation, and the result sets are merged with
    Reciprocal Rank Fusion (RRF) in the calling pipeline.

Both functions are async and call Gemini via the google-generativeai SDK,
matching the existing LLM usage pattern in the project.

Vague-query detection
---------------------
``is_vague_query(text)`` is intentionally kept as a pure, deterministic
function with no LLM call so it has zero latency overhead on the hot path.
"""

from __future__ import annotations

import logging
import re

import google.generativeai as genai  # type: ignore

from backend.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vague-query heuristics
# ---------------------------------------------------------------------------

_VAGUE_WORDS = re.compile(
    r"\b(stuck|hint|help|don'?t get(?: it)?|confused|lost|clueless|"
    r"not sure|no idea|what to do|where to start|how to approach)\b",
    re.IGNORECASE,
)

_SHORT_WORD_THRESHOLD = 6  # fewer than this many words → treat as vague


def is_vague_query(text: str) -> bool:
    """
    Return True when the query should use HyDE rather than multi-query.

    A query is vague when it:
    - Contains fewer than ``_SHORT_WORD_THRESHOLD`` whitespace-delimited words, OR
    - Matches one of the hedge-word patterns above.

    This is a fast, zero-cost check — no LLM call.
    """
    word_count = len(text.split())
    if word_count < _SHORT_WORD_THRESHOLD:
        return True
    if _VAGUE_WORDS.search(text):
        return True
    return False


# ---------------------------------------------------------------------------
# LLM helpers (async, Gemini)
# ---------------------------------------------------------------------------

def _get_gemini_model() -> genai.GenerativeModel:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai.GenerativeModel(settings.GEMINI_MODEL_NAME)


async def generate_hyde(query: str) -> str:
    """
    Generate a short *hypothetical answer* for a vague query.

    The returned string is the text to embed (instead of the raw query) for
    dense retrieval, and also passed as a query to BM25 sparse retrieval.

    Falls back to the original query on any LLM error so retrieval is never
    blocked by a transformer call failure.
    """
    prompt = (
        "You are helping a student practising LeetCode problems.\n"
        "The student sent this vague message: \"{query}\"\n\n"
        "Write a SHORT (2-4 sentence) hypothetical LeetCode editorial answer "
        "that would be relevant to what the student is probably asking about. "
        "Focus on algorithm patterns (e.g. sliding window, two pointers, DP). "
        "Do NOT mention the student. Output only the editorial text, nothing else."
    ).format(query=query)

    try:
        model = _get_gemini_model()
        response = await model.generate_content_async(prompt)
        text = (response.text or "").strip()
        if not text:
            raise ValueError("Empty HyDE response")
        logger.debug("HyDE generated (%d chars) for query: %r", len(text), query[:60])
        return text
    except Exception as exc:
        logger.warning("HyDE generation failed — falling back to raw query: %s", exc)
        return query


async def generate_multi_query(query: str, n: int = 3) -> list[str]:
    """
    Generate *n* semantically varied reformulations of *query*.

    Returns a list that always includes the *original* query so the caller
    can simply iterate the returned list without special-casing the original.
    Falls back to ``[query]`` (single item) on LLM error.

    Parameters
    ----------
    query : The original user question.
    n     : Number of *additional* reformulations to request (2 or 3).
    """
    prompt = (
        "You are helping improve a semantic search system for LeetCode problems.\n"
        "Original question: \"{query}\"\n\n"
        "Write {n} different reformulations of this question that preserve the "
        "original intent but use different wording, synonyms, or perspectives. "
        "Each reformulation on its own line. No numbering, no preamble."
    ).format(query=query, n=n)

    try:
        model = _get_gemini_model()
        response = await model.generate_content_async(prompt)
        raw = (response.text or "").strip()
        if not raw:
            raise ValueError("Empty multi-query response")

        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        # Always keep the original query; deduplicate while preserving order
        seen: set[str] = {query.strip()}
        reformulations: list[str] = [query]
        for line in lines:
            if line not in seen:
                seen.add(line)
                reformulations.append(line)

        logger.debug(
            "Multi-query generated %d variants for query: %r",
            len(reformulations) - 1,
            query[:60],
        )
        return reformulations[:n + 1]  # original + at most n extras

    except Exception as exc:
        logger.warning("Multi-query generation failed — using raw query only: %s", exc)
        return [query]
