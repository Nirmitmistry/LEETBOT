"""
backend/rag/eval/schema.py — Data models for the golden dataset and eval reports.

Golden dataset format
---------------------
Each entry in the golden dataset JSON file is a ``GoldenEntry``:

    {
        "id":                       "two-sum-vague-1",
        "problem_id":               "1",
        "slug":                     "two-sum",
        "question":                 "i'm stuck, can you help?",
        "query_type":               "vague",
        "expected_context_chunk_ids": ["1_statement", "1_hint_1"],
        "ground_truth_answer":      "Use a hash map to look up the complement..."
    }

Fields
------
id
    Unique identifier for this eval sample.  Use ``{slug}-{type}-{n}`` convention.

problem_id
    String ID matching the ``_id`` field of the problem in MongoDB (and Chroma
    metadata ``problem_id``).  Used to verify the pipeline retrieved the right
    parent document.

slug
    URL slug of the problem (e.g. ``"two-sum"``).  Used to fetch the problem
    from MongoDB during generation and for human-readable reporting.

question
    The exact string submitted as the user query to the retrieval pipeline.
    Cover both *vague* phrasings ("I'm stuck") and *precise* phrasings
    ("How does the sliding window reduce time complexity here?").

query_type
    ``"vague"`` or ``"precise"``.  Informational — used for per-type aggregate
    scoring in the report.

expected_context_chunk_ids
    List of Chroma ``doc_id`` metadata values that should be present in the
    retrieved context.  Used to compute context precision / recall.
    If you don't track chunk IDs yet, set to an empty list — those metrics
    will be skipped for that entry rather than crashing.

ground_truth_answer
    The reference answer used by Ragas ``faithfulness`` and
    ``answer_relevancy``.  Should be a concise, factually correct answer to
    the ``question``.

Report models
-------------
``QueryResult``   — per-query scores + metadata emitted by the pipeline.
``EvalReport``    — top-level report written to the timestamped JSON file.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Golden dataset
# ---------------------------------------------------------------------------

class GoldenEntry(BaseModel):
    id: str = Field(..., description="Unique sample ID, e.g. 'two-sum-vague-1'")
    problem_id: str = Field(..., description="String _id from MongoDB / Chroma metadata")
    slug: str = Field(..., description="URL slug of the problem")
    question: str = Field(..., description="User query submitted to the RAG pipeline")
    query_type: Literal["vague", "precise"] = Field(
        ..., description="vague = short/hedge-word query; precise = specific technical question"
    )
    expected_context_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Chroma doc_id values expected in the retrieved context (for precision/recall)",
    )
    ground_truth_answer: str = Field(
        ..., description="Reference answer used by Ragas faithfulness and answer_relevancy"
    )


class GoldenDataset(BaseModel):
    version: str = Field("1.0", description="Dataset schema version")
    entries: list[GoldenEntry]


# ---------------------------------------------------------------------------
# Per-query result
# ---------------------------------------------------------------------------

class QueryResult(BaseModel):
    # Identification
    sample_id: str
    problem_id: str
    slug: str
    question: str
    query_type: Literal["vague", "precise"]

    # Retrieved context
    retrieved_chunk_ids: list[str] = Field(
        default_factory=list,
        description="doc_id values from the reranked context documents",
    )
    retrieved_context: list[str] = Field(
        default_factory=list,
        description="page_content strings of reranked documents (fed to Ragas)",
    )

    # Generated answer
    generated_answer: str = ""

    # Ground truth
    ground_truth_answer: str = ""
    expected_context_chunk_ids: list[str] = Field(default_factory=list)

    # Ragas per-metric scores (None = metric was skipped / errored)
    faithfulness: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    answer_relevancy: float | None = None

    # Execution metadata
    retrieval_latency_s: float = 0.0
    generation_latency_s: float = 0.0
    error: str | None = None


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------

class AggregateScores(BaseModel):
    faithfulness: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    answer_relevancy: float | None = None

    # Per query-type breakdown
    vague_faithfulness: float | None = None
    precise_faithfulness: float | None = None


class EvalReport(BaseModel):
    # Run metadata
    run_id: str = Field(..., description="ISO-8601 timestamp used as the report filename stem")
    pipeline_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of key config values at eval time",
    )

    # Results
    query_results: list[QueryResult]
    aggregate: AggregateScores

    # CI gate
    faithfulness_threshold: float = Field(
        0.85, description="Threshold that triggers a non-zero CI exit"
    )
    passed_faithfulness_gate: bool = Field(
        ..., description="True when aggregate faithfulness >= threshold"
    )

    # Counts
    total_samples: int = 0
    errored_samples: int = 0
