from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database

from backend.db import get_db
from backend.models.schemas import RecommendRequest, RecommendResponse, ProblemSummary

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


@router.post("", response_model=RecommendResponse)
async def recommend_problems(
    body: RecommendRequest,
    db:   Database = Depends(get_db),
):
    source = db["problems"].find_one({"slug": body.slug})
    if not source:
        raise HTTPException(
            status_code=404, detail=f"Problem '{body.slug}' not found")

    similar_ids = source.get("similar_problem_ids", [])

    query: dict = {"slug": {"$in": similar_ids}}
    if body.difficulty:
        query["difficulty"] = body.difficulty

    cursor = db["problems"].find(query, {"_id": 0}).limit(body.top_k)
    results = [_to_summary(p) for p in cursor]

    reason = (
        f"[Phase 6 stub] Showing problems tagged as similar to '{body.slug}'. "
        "Claude-generated reasoning coming in Phase 7."
    )

    return RecommendResponse(
        based_on=body.slug,
        recommended=results,
        reason=reason,
    )
