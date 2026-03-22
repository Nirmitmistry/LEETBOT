from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database
from backend.db import get_db
from backend.auth.hashing import hash_password, verify_password
from backend.auth.jwt import createaccesstoken
from backend.models.userschema import UserRegister, UserLogin, TokenResponse, UserResponse

router = APIRouter()


def _fmt_user(user: dict) -> UserResponse:
    return UserResponse(
        user_id=str(user["_id"]),
        email=user["email"],
        username=user["username"],
        solved_problems=user.get("solved_problems", []),
        attempted_problems=user.get("attempted_problems", []),
        preferred_difficulty=user.get("preferred_difficulty"),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: UserRegister, db: Database = Depends(get_db)):
    if db["users"].find_one({"email": body.email}):
        raise HTTPException(status_code=409, detail="Email already registered")

    if db["users"].find_one({"username": body.username}):
        raise HTTPException(status_code=409, detail="Username already taken")

    doc = {
        "email":                body.email,
        "username":             body.username,
        "password_hash":        hash_password(body.password),
        "solved_problems":      [],
        "attempted_problems":   [],
        "preferred_difficulty": None,
        "created_at":           datetime.now(timezone.utc),
    }
    result = db["users"].insert_one(doc)
    doc["_id"] = result.inserted_id

    token = createaccesstoken(str(result.inserted_id), body.email)
    return TokenResponse(access_token=token, user=_fmt_user(doc))


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: Database = Depends(get_db)):
    user = db["users"].find_one({"email": body.email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=401, detail="Invalid email or password")

    token = createaccesstoken(str(user["_id"]), user["email"])
    return TokenResponse(access_token=token, user=_fmt_user(user))
