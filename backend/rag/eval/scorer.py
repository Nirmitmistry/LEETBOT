"""
backend/rag/eval/scorer.py — Ragas metric computation for eval results.

Ragas API notes (v0.2+)
-----------------------
Ragas 0.2 restructured its public API:
  - ``faithfulness``, ``context_precision``, ``context_recall``,
    ``answer_relevancy`` are now importable from ``ragas.metrics``.
  - ``evaluate()`` accepts a ``Dataset`` (HuggingFace datasets) or an
    ``EvaluationDataset`` and a list of metrics.
  - LLM and embeddings are configured via ``LangchainLLMWrapper`` and
    ``LangchainEmbeddingsWrapper`` to keep it provider-agnostic.

We use Gemini (already configured in the project) as the judge LLM and
embeddings model so we don't introduce a new API key dependency.

Graceful degradation
--------------------
If Ragas is not installed, ``score_results()`` returns the original
``QueryResult`` list unchanged (all metric fields stay ``None``) and logs a
warning.  The report is still written; the CI gate will skip if faithfulness
is None.

Per-entry scoring vs. batch
----------------------------
Ragas ``evaluate()`` is designed for batch evaluation.  We build a single
dataset from all non-errored entries, call ``evaluate()`` once (more
efficient — one embedding batch for the whole run), then map scores back to
individual ``QueryResult`` objects by position.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.rag.eval.schema import AggregateScores, QueryResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_mean(values: list[float | None]) -> float | None:
    """Return the mean of non-None values, or None if all are absent."""
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def _get_ragas_llm_and_embeddings():
    """
    Return (LangchainLLMWrapper, LangchainEmbeddingsWrapper) configured for
    Gemini.  Raises ImportError if ragas or langchain wrappers are missing.
    """
    from ragas.llms import LangchainLLMWrapper          # type: ignore
    from ragas.embeddings import LangchainEmbeddingsWrapper  # type: ignore
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    from backend.config import settings

    llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.0,
        )
    )
    embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
        )
    )
    return llm, embeddings


# ---------------------------------------------------------------------------
# Public scorer
# ---------------------------------------------------------------------------

def score_results(results: list[QueryResult]) -> list[QueryResult]:
    """
    Compute Ragas metrics for all non-errored ``QueryResult`` objects in-place.

    Metrics computed
    ----------------
    faithfulness        — Is the generated answer grounded in the context?
                          (requires: question, generated_answer, retrieved_context)
    context_precision   — Are the retrieved contexts relevant to the question?
                          (requires: question, ground_truth_answer, retrieved_context)
    context_recall      — Does the retrieved context cover the ground truth?
                          (requires: question, ground_truth_answer, retrieved_context)
    answer_relevancy    — Is the generated answer relevant to the question?
                          (requires: question, generated_answer, retrieved_context)

    All metrics use the Gemini judge LLM + Gemini embeddings.

    Parameters
    ----------
    results : List of ``QueryResult`` objects, mutated in-place with scores.

    Returns
    -------
    The same list with score fields populated.
    """
    # Filter to entries that have both context and an answer
    scoreable = [
        r for r in results
        if not r.error
        and r.retrieved_context
        and r.generated_answer
    ]

    if not scoreable:
        logger.warning("No scoreable entries — all entries either errored or had empty context/answer")
        return results

    try:
        from ragas import evaluate                           # type: ignore
        from ragas.metrics import (                          # type: ignore
            faithfulness,
            context_precision,
            context_recall,
            answer_relevancy,
        )
        from datasets import Dataset                         # type: ignore
    except ImportError as exc:
        logger.warning(
            "Ragas or HuggingFace datasets not installed — skipping metric scoring. "
            "Run: pip install ragas>=0.2.0 datasets>=2.14.0\n"
            "Error: %s",
            exc,
        )
        return results

    # ── Build HuggingFace Dataset ─────────────────────────────────────────────
    # Ragas 0.2 expects these exact column names.
    hf_data: dict[str, list[Any]] = {
        "question":  [],
        "answer":    [],
        "contexts":  [],   # list of strings per row
        "ground_truth": [],
    }
    for r in scoreable:
        hf_data["question"].append(r.question)
        hf_data["answer"].append(r.generated_answer)
        hf_data["contexts"].append(r.retrieved_context)
        hf_data["ground_truth"].append(r.ground_truth_answer)

    dataset = Dataset.from_dict(hf_data)

    # ── Configure Ragas judge ─────────────────────────────────────────────────
    try:
        llm, embeddings = _get_ragas_llm_and_embeddings()
    except Exception as exc:
        logger.error("Failed to initialise Ragas judge LLM/embeddings: %s", exc)
        return results

    metrics = [faithfulness, context_precision, context_recall, answer_relevancy]

    # Inject our LLM + embeddings into each metric object
    for metric in metrics:
        if hasattr(metric, "llm"):
            metric.llm = llm
        if hasattr(metric, "embeddings"):
            metric.embeddings = embeddings

    # ── Run evaluation ────────────────────────────────────────────────────────
    logger.info("Running Ragas evaluation on %d entries…", len(scoreable))
    try:
        ragas_result = evaluate(dataset=dataset, metrics=metrics)
    except Exception as exc:
        logger.error("Ragas evaluate() failed: %s", exc)
        return results

    # ``ragas_result`` is a ``Result`` object; ``.to_pandas()`` gives per-row scores.
    try:
        scores_df = ragas_result.to_pandas()
    except Exception as exc:
        logger.error("Failed to convert Ragas result to DataFrame: %s", exc)
        return results

    # ── Map scores back to QueryResult objects ────────────────────────────────
    col_map = {
        "faithfulness":      "faithfulness",
        "context_precision": "context_precision",
        "context_recall":    "context_recall",
        "answer_relevancy":  "answer_relevancy",
    }

    for i, query_result in enumerate(scoreable):
        if i >= len(scores_df):
            break
        row = scores_df.iloc[i]
        for df_col, attr in col_map.items():
            if df_col in row.index:
                raw = row[df_col]
                try:
                    setattr(query_result, attr, float(raw))
                except (TypeError, ValueError):
                    pass  # NaN or missing — leave as None

    logger.info("Ragas scoring complete")
    return results


# ---------------------------------------------------------------------------
# Aggregate scorer
# ---------------------------------------------------------------------------

def compute_aggregates(results: list[QueryResult]) -> AggregateScores:
    """
    Compute aggregate (mean) scores across all entries and per query-type.
    """
    vague   = [r for r in results if r.query_type == "vague"   and not r.error]
    precise = [r for r in results if r.query_type == "precise" and not r.error]

    return AggregateScores(
        faithfulness=_safe_mean([r.faithfulness       for r in results if not r.error]),
        context_precision=_safe_mean([r.context_precision for r in results if not r.error]),
        context_recall=_safe_mean([r.context_recall      for r in results if not r.error]),
        answer_relevancy=_safe_mean([r.answer_relevancy   for r in results if not r.error]),
        vague_faithfulness=_safe_mean([r.faithfulness     for r in vague]),
        precise_faithfulness=_safe_mean([r.faithfulness   for r in precise]),
    )
