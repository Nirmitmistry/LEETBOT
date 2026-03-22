from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.database import Database
from jose import JWTError
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

    user = db["users"].find_one({"_id": payload["user_id"]}, {"password_hash": 0})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    user["user_id"] = str(user["_id"])
    return user
