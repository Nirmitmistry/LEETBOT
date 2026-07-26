from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.database import Database
from jose import JWTError
from bson import ObjectId
from backend.db import get_db
from backend.auth.jwt import decodeaccesstoken

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def getcurrentuser(
    token: str = Depends(oauth2_scheme),
    db:    Database = Depends(get_db),
) -> dict:
    try:
        payload = decodeaccesstoken(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        oid = ObjectId(payload["user_id"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )

    user = db["users"].find_one({"_id": oid}, {"password_hash": 0})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    user["user_id"] = str(user["_id"])
    return user

