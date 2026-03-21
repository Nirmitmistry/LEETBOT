

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database
from bson import ObjectId

from backend.db import get_db
from backend.models.schemas import SessionCreateRequest, SessionResponse

router = APIRouter()


def _fmt(session: dict) -> SessionResponse:
    return SessionResponse(
        session_id=str(session["_id"]),
        slug=session["slug"],
        user_id=session["user_id"],
        current_stage=session.get("current_stage", 0),
        max_stage=5,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreateRequest,
    db:   Database = Depends(get_db),
):

    existing = db["hint_sessions"].find_one(
        {"slug": body.slug, "user_id": body.user_id}
    )
    if existing:
        return _fmt(existing)

    doc = {
        "slug":          body.slug,
        "user_id":       body.user_id,
        "current_stage": 0,
        "created_at":    datetime.now(timezone.utc),
    }
    result = db["hint_sessions"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _fmt(doc)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: Database = Depends(get_db)):
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid session_id format")

    session = db["hint_sessions"].find_one({"_id": oid})
    if not session:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' not found")

    return _fmt(session)
