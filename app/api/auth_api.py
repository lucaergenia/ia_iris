from fastapi import APIRouter, Response, Request, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database.database import db
from app.auth.security import (
    hash_password,
    verify_password,
    make_access_token,
    make_refresh_token,
    verify_access_token,
    verify_refresh_token,
    cookie_settings,
)


router = APIRouter()


class LoginBody(BaseModel):
    email: EmailStr
    password: str


def _get_user_by_email(email: str) -> Optional[dict]:
    u = db.users.find_one({"email": email.lower().strip()})
    return u


def _get_user_by_id(uid: str) -> Optional[dict]:
    from bson import ObjectId

    try:
        oid = ObjectId(uid)
    except Exception:
        return None
    return db.users.find_one({"_id": oid})


@router.post("/auth/login")
def login(body: LoginBody, response: Response):
    user = _get_user_by_email(body.email)
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Usuario deshabilitado")

    uid = str(user["_id"])
    access = make_access_token(uid)
    refresh = make_refresh_token(uid)
    ck = cookie_settings()
    response.set_cookie("access_token", access, **ck)
    response.set_cookie("refresh_token", refresh, **ck)
    return {"user": {"email": user.get("email"), "name": user.get("name"), "role": user.get("role", "restricted")}}


@router.post("/auth/logout")
def logout(response: Response):
    ck = cookie_settings()
    response.delete_cookie("access_token", path=ck["path"])
    response.delete_cookie("refresh_token", path=ck["path"])
    return {"ok": True}


@router.post("/auth/refresh")
def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    uid = verify_refresh_token(token or "")
    if not uid:
        raise HTTPException(status_code=401, detail="Refresh inválido")
    access = make_access_token(uid)
    ck = cookie_settings()
    response.set_cookie("access_token", access, **ck)
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    token = request.cookies.get("access_token")
    uid = verify_access_token(token or "")
    if not uid:
        raise HTTPException(status_code=401, detail="No autenticado")
    user = _get_user_by_id(uid)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")
    return {"email": user.get("email"), "name": user.get("name"), "role": user.get("role", "restricted")}

