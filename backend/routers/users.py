from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database
from backend.db import get_db
from backend.auth.dependecies import get_current_user
from backend.models.userschema import UserResponse, UpdateProfile
from bson import ObjectId

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        user_id=current_user["user_id"],
        email=current_user["email"],
        username=current_user["username"],
        solved_problems=current_user.get("solved_problems", []),
        attempted_problems=current_user.get("attempted_problems", []),
        preferred_difficulty=current_user.get("preferred_difficulty"),
    )


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body:         UpdateProfile,
    current_user: dict = Depends(get_current_user),
    db:           Database = Depends(get_db),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    db["users"].update_one(
        {"_id": ObjectId(current_user["user_id"])},
        {"$set": updates},
    )
    updated = db["users"].find_one({"_id": ObjectId(current_user["user_id"])})
    updated["user_id"] = str(updated["_id"])
    return UserResponse(**{k: updated[k] for k in UserResponse.model_fields if k in updated})


@router.post("/me/solved/{slug}", response_model=UserResponse)
async def mark_solved(
    slug:         str,
    current_user: dict = Depends(get_current_user),
    db:           Database = Depends(get_db),
):
    db["users"].update_one(
        {"_id": ObjectId(current_user["user_id"])},
        {
            "$addToSet": {"solved_problems":    slug},
            "$pull":     {"attempted_problems": slug},
        },
    )
    updated = db["users"].find_one({"_id": ObjectId(current_user["user_id"])})
    updated["user_id"] = str(updated["_id"])
    return UserResponse(**{k: updated[k] for k in UserResponse.model_fields if k in updated})


@router.post("/me/attempted/{slug}", response_model=UserResponse)
async def mark_attempted(
    slug:         str,
    current_user: dict = Depends(get_current_user),
    db:           Database = Depends(get_db),
):
    db["users"].update_one(
        {"_id": ObjectId(current_user["user_id"])},
        {"$addToSet": {"attempted_problems": slug}},
    )
    updated = db["users"].find_one({"_id": ObjectId(current_user["user_id"])})
    updated["user_id"] = str(updated["_id"])
    return UserResponse(**{k: updated[k] for k in UserResponse.model_fields if k in updated})
