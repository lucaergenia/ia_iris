import os
import time
from typing import Optional, Tuple

import jwt
from passlib.context import CryptContext


JWT_SECRET = os.getenv("JWT_SECRET", "change-me-please")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
ACCESS_TTL = int(os.getenv("JWT_ACCESS_TTL", "900"))  # 15min
REFRESH_TTL = int(os.getenv("JWT_REFRESH_TTL", "604800"))  # 7d

pctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pctx.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pctx.verify(password, hashed)
    except Exception:
        return False


def _make_token(sub: str, ttl: int, scope: str) -> str:
    now = int(time.time())
    payload = {"sub": sub, "iat": now, "exp": now + ttl, "scope": scope}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def make_access_token(user_id: str) -> str:
    return _make_token(user_id, ACCESS_TTL, "access")


def make_refresh_token(user_id: str) -> str:
    return _make_token(user_id, REFRESH_TTL, "refresh")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        return None


def verify_access_token(token: str) -> Optional[str]:
    data = decode_token(token)
    if not data or data.get("scope") != "access":
        return None
    return data.get("sub")


def verify_refresh_token(token: str) -> Optional[str]:
    data = decode_token(token)
    if not data or data.get("scope") != "refresh":
        return None
    return data.get("sub")


def cookie_settings() -> dict:
    # Secure for https in prod. SameSite Lax for CSRF protection while allowing navigation.
    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    return dict(
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )



