"""
Auth utilities — bcrypt passwords (Lab8 pattern) + JWT tokens (CapitalPyre pattern).
"""

import os
import json
import hashlib
import hmac
import base64
import time
import bcrypt
from typing import Optional
from fastapi import Request, HTTPException, status
from app.database import db_cursor

JWT_SECRET = os.getenv("JWT_SECRET", "fintrack-dev-secret-change-in-prod")
JWT_EXPIRY  = 60 * 60 * 24 * 7  # 7 days

# ── Password hashing (bcrypt — same as Lab8 password_hash()) ──

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False

# ── Simple JWT (no external library required) ─────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _sign(payload: dict) -> str:
    header  = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body    = _b64(json.dumps(payload).encode())
    sig     = _b64(hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"

def _verify(token: str) -> Optional[dict]:
    try:
        header, body, sig = token.split(".")
        expected = _b64(hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        padded_body = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

def create_token(user_id: int, username: str) -> str:
    return _sign({"sub": user_id, "username": username, "exp": int(time.time()) + JWT_EXPIRY})

# ── FastAPI dependency — get current user ─────────────────

def get_current_user(request: Request) -> dict:
    token = request.cookies.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = _verify(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return payload

def optional_user(request: Request) -> Optional[dict]:
    try:
        return get_current_user(request)
    except HTTPException:
        return None
