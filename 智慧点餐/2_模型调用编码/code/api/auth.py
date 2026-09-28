from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.schemas import Credentials
from database import get_db
from models import LoginSession, User
from security import COOKIE_NAME, create_session, current_user, hash_password, token_digest, user_data, verify_password

router = APIRouter(prefix="/auth", tags=["用户"])


@router.post("/register", status_code=201)
def register(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    user = User(username=data.username.lower(), password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "用户名已存在")
    create_session(db, user, response, request.cookies.get(COOKIE_NAME))
    db.commit()
    return user_data(user)


@router.post("/login")
def login(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username.lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    create_session(db, user, response, request.cookies.get(COOKIE_NAME))
    db.commit()
    return user_data(user)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_data(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_digest(token)))
    response.delete_cookie(COOKIE_NAME, path="/")
    db.commit()
    return {"message": "已退出登录"}
