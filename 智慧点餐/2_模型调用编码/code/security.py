import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from config import COOKIE_SECURE, SESSION_HOURS
from database import get_db
from models import LoginSession, User, now

COOKIE_NAME = "aimenu_session"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, response: Response, old_token: str | None = None):
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now()))
    if old_token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_digest(old_token)))
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_digest(token), user_id=user.id, expires_at=now() + timedelta(hours=SESSION_HOURS)))
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_HOURS * 3600,
                        httponly=True, secure=COOKIE_SECURE, samesite="strict", path="/")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    session = db.get(LoginSession, token_digest(token)) if token else None
    if session is None or session.expires_at <= now():
        raise HTTPException(401, "请先登录，或重新登录")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "账号不存在")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return user


def user_data(user: User):
    return {"id": user.id, "username": user.username, "is_admin": user.is_admin}
