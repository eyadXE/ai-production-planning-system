"""Auth routes: signup, login, me."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from finalproject.api.schemas import LoginIn, SignupIn, TokenOut, UserOut
from finalproject.auth.dependencies import get_current_user
from finalproject.auth.jwt import create_access_token
from finalproject.auth.service import AuthError, authenticate, create_user
from finalproject.db.database import get_session
from finalproject.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenOut, status_code=201)
def signup(body: SignupIn, session: Session = Depends(get_session)):
    try:
        user = create_user(
            session,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            role=body.role,
            account_code=body.account_code,
        )
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.message)
    token = create_access_token(user.id, user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, session: Session = Depends(get_session)):
    try:
        user = authenticate(session, body.email, body.password)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.message)
    token = create_access_token(user.id, user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
