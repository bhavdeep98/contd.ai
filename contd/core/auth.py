from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
import os
import secrets
import string
import hashlib

# Configuration (Env vars in real app)
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_api_key(prefix="sk_live_"):
    """Generates a random API key and its hash."""
    # 32 chars of randomness
    alphabet = string.ascii_letters + string.digits
    key_part = "".join(secrets.choice(alphabet) for i in range(32))
    full_key = f"{prefix}{key_part}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_hash


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verifies an API key against its stored hash."""
    computed_hash = hashlib.sha256(api_key.encode()).hexdigest()
    # Constant time comparison to prevent timing attacks
    return secrets.compare_digest(computed_hash, stored_hash)
