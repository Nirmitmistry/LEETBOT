from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    truncated = plain.encode('utf-8')[:72].decode('utf-8', 'ignore')
    return pwd_context.hash(truncated)

def verify_password(plain: str, hashed: str) -> bool:
    truncated = plain.encode('utf-8')[:72].decode('utf-8', 'ignore')
    return pwd_context.verify(truncated, hashed)