import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext

from config import get_settings
from database import get_db_connection
from rbac import has_permission

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
basic_security = HTTPBasic(auto_error=False)
bearer_security = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def find_user_by_username_timing_safe(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT id, username, password, role FROM users")
    rows = cur.fetchall()
    for row in rows:
        stored = row["username"]
        if len(stored) != len(username):
            continue
        try:
            if secrets.compare_digest(
                stored.encode("utf-8"),
                username.encode("utf-8"),
            ):
                return row
        except ValueError:
            continue
    return None


def auth_user_dependency(
    credentials: HTTPBasicCredentials | None = Depends(basic_security),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )
    conn = get_db_connection()
    try:
        user = find_user_by_username_timing_safe(conn, credentials.username)
        if user is None or not verify_password(credentials.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        return user["username"]
    finally:
        conn.close()


def create_access_token(*, username: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_token_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_security)) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    username = payload.get("sub")
    role = payload.get("role")
    if not isinstance(username, str) or not isinstance(role, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return {"username": username, "role": role}


def require_permission(permission: str):
    def _dep(user: dict = Depends(get_token_user)) -> dict:
        if not has_permission(user["role"], permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _dep
