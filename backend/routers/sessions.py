from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database
from bson import ObjectId
from backend.db import get_db
from backend.auth.dependecies import getcurrentuser
from backend.models.schemas import SessionCreateRequest, SessionResponse

router = APIRouter()


def _fmt(session: dict) -> SessionResponse:
    return SessionResponse(
        session_id=str(session["_id"]),
        slug=session["slug"],
        user_id=str(session["user_id"]),
        current_stage=session.get("current_stage", 0),
        max_stage=5,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body:         SessionCreateRequest,
    current_user: dict = Depends(getcurrentuser),
    db:           Database = Depends(get_db),
):
    user_id = current_user["user_id"]

    # Return existing session if one already exists for this user+problem
    existing = db["hint_sessions"].find_one(
        {"slug": body.slug, "user_id": user_id})
    if existing:
        return _fmt(existing)

    doc = {
        "slug":          body.slug,
        "user_id":       user_id,
        "current_stage": 0,
        "created_at":    datetime.now(timezone.utc),
    }
    result = db["hint_sessions"].insert_one(doc)
    doc["_id"] = result.inserted_id

    # Mark problem as attempted on session creation
    db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$addToSet": {"attempted_problems": body.slug}},
    )

    return _fmt(doc)


@router.get("/me", response_model=list[SessionResponse])
async def get_my_sessions(
    current_user: dict = Depends(getcurrentuser),
    db:           Database = Depends(get_db),
):
    # Returns all sessions for the logged in user
    cursor = db["hint_sessions"].find({"user_id": current_user["user_id"]})
    return [_fmt(s) for s in cursor]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id:   str,
    current_user: dict = Depends(getcurrentuser),
    db:           Database = Depends(get_db),
):
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid session_id format")

    session = db["hint_sessions"].find_one({"_id": oid})
    if not session:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' not found")

    # Make sure the session belongs to the requesting user
    if str(session["user_id"]) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your session")

    return _fmt(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id:   str,
    current_user: dict = Depends(getcurrentuser),
    db:           Database = Depends(get_db),
):
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid session_id format")

    session = db["hint_sessions"].find_one({"_id": oid})
    if not session:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' not found")

    if str(session["user_id"]) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your session")

    db["hint_sessions"].delete_one({"_id": oid})
