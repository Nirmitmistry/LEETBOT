import os
from datetime import datetime, timedelta,timezone
from jose import jwt,JWTError

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 1440))

def createaccesstoken(user_id:str,email:str)->str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decodeaccesstoken(token:str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        email = payload.get("email")
        if user_id is None or email is None:
            raise JWTError("Invalid token payload")
        return {"user_id": user_id, "email": email}
    except JWTError as e:
        raise JWTError(f"Token decode error: {str(e)}")