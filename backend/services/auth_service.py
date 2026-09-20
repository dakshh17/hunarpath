"""
HunarPath - Authentication service.

Provides JWT token creation/verification and PIN hashing utilities.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import Artisan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "hunarpath-hackathon-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

import hashlib
import hmac

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_pin(pin: str) -> str:
    """Hash a PIN string using PBKDF2-HMAC-SHA256 with salt (cross-platform, zero dependencies)."""
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 100000).hex()
    return f"pbkdf2_sha256${salt}${key}"


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Verify a plain PIN against its PBKDF2 or bcrypt hash."""
    if not hashed_pin:
        return False
    if hashed_pin.startswith("pbkdf2_sha256$"):
        parts = hashed_pin.split("$")
        if len(parts) == 3:
            salt, expected_key = parts[1], parts[2]
            key = hashlib.pbkdf2_hmac("sha256", plain_pin.encode(), salt.encode(), 100000).hex()
            return hmac.compare_digest(key, expected_key)
    try:
        return _pwd_context.verify(plain_pin, hashed_pin)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT Token
# ---------------------------------------------------------------------------

def create_access_token(artisan_id: str) -> str:
    """Create a JWT access token for the given artisan."""
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": artisan_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Decode a JWT token and return the artisan_id, or None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired.")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT token.")
        return None


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------
_security = HTTPBearer()


async def get_current_artisan(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    session: AsyncSession = Depends(get_session),
) -> Artisan:
    """
    FastAPI dependency that extracts and validates the JWT bearer token,
    loads the corresponding Artisan from the database, and returns it.

    Raises HTTP 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    artisan_id = decode_access_token(token)

    if artisan_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    artisan = await session.get(Artisan, artisan_id)
    if artisan is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Artisan not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return artisan
