from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

from backend.config import settings


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str):
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        email = payload.get("email")
        if user_id is None or email is None:
            raise JWTError("Invalid token payload")
        return {"user_id": user_id, "email": email}
    except JWTError as e:
        raise JWTError(f"Token decode error: {str(e)}")
