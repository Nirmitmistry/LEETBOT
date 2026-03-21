"""
routers/problems.py

GET /problems/{slug}   → fetch one problem from MongoDB
GET /problems/search   → semantic search via Chroma
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pymongo.database import Database

from backend.db import get_db, get_chroma
from backend.models.schemas import ProblemDetail, SearchResponse, ProblemSummary, ComplexityInfo
from langchain_chroma import Chroma

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_list(value) -> list:
    """
    Normalise a MongoDB field that may be stored as a string or a list.
      - list   → return as-is
      - string → split on newlines, strip each line, drop empty lines
      - other  → return []
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _to_summary(doc: dict) -> ProblemSummary:
    return ProblemSummary(
        slug=doc["slug"],
        title=doc["title"],
        difficulty=doc["difficulty"],
        acceptance_rate=doc.get("acceptance_rate", 0.0),
        tags=_to_list(doc.get("tags", [])),
        is_premium=doc.get("is_premium", False),
    )


# ---------------------------------------------------------------------------
# Routes  (search MUST come before /{slug} to avoid "search" being a slug)
# ---------------------------------------------------------------------------

@router.get("/search", response_model=SearchResponse)
async def search_problems(
    q:          str = Query(..., min_length=3,
                            description="Natural language query"),
    top_k:      int = Query(5, ge=1, le=20),
    difficulty: str | None = Query(None),
    db:         Database = Depends(get_db),
    chroma:     Chroma = Depends(get_chroma),
):
    """Semantic search over problem statements via Chroma embeddings."""
    where_filter = {"hint_stage": 0}
    if difficulty:
        where_filter["difficulty"] = difficulty

    docs = chroma.similarity_search(query=q, k=top_k, filter=where_filter)

    slugs = [d.metadata.get("slug") for d in docs if d.metadata.get("slug")]
    cursor = db["problems"].find({"slug": {"$in": slugs}}, {"_id": 0})
    results = [_to_summary(p) for p in cursor]

    return SearchResponse(results=results, query=q)


@router.get("/{slug}", response_model=ProblemDetail)
async def get_problem(slug: str, db: Database = Depends(get_db)):
    """Fetch a single problem by slug from MongoDB."""
    doc = db["problems"].find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(
            status_code=404, detail=f"Problem '{slug}' not found")

    # complexity may be dict, string, or missing
    complexity = None
    raw_c = doc.get("complexity")
    if isinstance(raw_c, dict):
        complexity = ComplexityInfo(
            time=raw_c.get("time", "Unknown"),
            space=raw_c.get("space", "Unknown"),
        )
    elif isinstance(raw_c, str) and raw_c.strip():
        complexity = ComplexityInfo(time=raw_c, space="Unknown")

    # examples must be list[dict] — if stored as a string, wrap it
    raw_examples = doc.get("examples", [])
    if isinstance(raw_examples, str):
        raw_examples = [{"raw": raw_examples}]

    return ProblemDetail(
        slug=doc["slug"],
        title=doc["title"],
        difficulty=doc["difficulty"],
        acceptance_rate=doc.get("acceptance_rate", 0.0),
        tags=_to_list(doc.get("tags", [])),
        is_premium=doc.get("is_premium", False),
        problem_statement=doc.get("problem_statement", ""),
        constraints=_to_list(doc.get("constraints", [])),
        examples=raw_examples,
        complexity=complexity,
        similar_problem_ids=_to_list(doc.get("similar_problem_ids", [])),
    )
