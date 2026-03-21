from fastapi import APIRouter, HTTPException, Depends, Query
from pymongo.database import Database

from backend.db import get_db, get_chroma
from backend.models.schemas import ProblemDetail, SearchResponse, ProblemSummary
from langchain_chroma import Chroma

router = APIRouter()


def _to_summary(doc: dict) -> ProblemSummary:
    return ProblemSummary(
        slug=doc["slug"],
        title=doc["title"],
        difficulty=doc["difficulty"],
        acceptance_rate=doc.get("acceptance_rate", 0.0),
        tags=doc.get("tags", []),
        is_premium=doc.get("is_premium", False),
    )


@router.get("/search", response_model=SearchResponse)
async def search_problems(
    q:          str = Query(..., min_length=3,
                            description="Natural language query"),
    top_k:      int = Query(5, ge=1, le=20),
    difficulty: str | None = Query(None),
    db:         Database = Depends(get_db),
    chroma:     Chroma = Depends(get_chroma),
):
    where_filter = {"hint_stage": 0}
    if difficulty:
        where_filter["difficulty"] = difficulty

    docs = chroma.similarity_search(
        query=q,
        k=top_k,
        filter=where_filter,
    )

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

    complexity = None
    if raw_c := doc.get("complexity"):
        from backend.models.schemas import ComplexityInfo
        complexity = ComplexityInfo(
            time=raw_c.get("time", "Unknown"),
            space=raw_c.get("space", "Unknown"),
        )

    return ProblemDetail(
        slug=doc["slug"],
        title=doc["title"],
        difficulty=doc["difficulty"],
        acceptance_rate=doc.get("acceptance_rate", 0.0),
        tags=doc.get("tags", []),
        is_premium=doc.get("is_premium", False),
        problem_statement=doc.get("problem_statement", ""),
        constraints=doc.get("constraints", []),
        examples=doc.get("examples", []),
        complexity=complexity,
        similar_problem_ids=doc.get("similar_problem_ids", []),
    )
