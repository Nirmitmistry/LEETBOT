from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.database import Database
from backend.db import get_db
from backend.auth.jwt import decodeaccesstoken

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

