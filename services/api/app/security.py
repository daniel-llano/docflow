from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_hasher = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored: str) -> bool:
    try:
        return _hasher.verify(stored, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(user_id: str, email: str, secret: str, minutes: int) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=minutes)
    token = jwt.encode({"sub": user_id, "email": email, "iat": now, "exp": expires}, secret, algorithm=ALGORITHM)
    return token, expires


def current_user_id(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in first.")
    try:
        payload = jwt.decode(creds.credentials, request.app.state.settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as ex:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.") from ex
    return str(payload["sub"])


def keys_match(sent: str | None, expected: str) -> bool:
    return secrets.compare_digest((sent or "").encode(), expected.encode())
