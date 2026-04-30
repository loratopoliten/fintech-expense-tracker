"""Auth — bcrypt passwords + JWT cookie tokens."""

import os, json, hashlib, hmac, base64, time
import bcrypt
from typing import Optional
from fastapi import Request, HTTPException, status

JWT_SECRET = os.getenv("JWT_SECRET", "fintrack-dev-secret-CHANGE-IN-PROD")
JWT_EXPIRY  = 60 * 60 * 24 * 7   # 7 days


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def _b64enc(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_token(user_id: int, username: str) -> str:
    header  = _b64enc(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64enc(json.dumps({"sub": user_id, "username": username,
                                   "exp": int(time.time()) + JWT_EXPIRY}).encode())
    sig = _b64enc(hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(),
                            hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def _verify_token(token: str) -> Optional[dict]:
    try:
        header, payload, sig = token.split(".")
        expected = _b64enc(hmac.new(JWT_SECRET.encode(),
                                     f"{header}.{payload}".encode(),
                                     hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        padded_payload = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded_payload))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None


def get_current_user(request: Request) -> dict:
    token = (request.cookies.get("token") or
             request.headers.get("Authorization", "").replace("Bearer ", ""))
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated")
    payload = _verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token")
    return payload


def optional_user(request: Request) -> Optional[dict]:
    try:
        return get_current_user(request)
    except HTTPException:
        return None
