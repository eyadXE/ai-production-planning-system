"""FastAPI dependencies: current user resolution + role guards."""

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from finalproject.auth.jwt import decode_token
from finalproject.db.database import get_session
from finalproject.db.models import User


def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    return header.removeprefix("Bearer ").strip()


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> User:
    try:
        payload = decode_token(_extract_token(request))
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token")
    user = session.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(401, "user no longer exists")
    return user


def require_roles(*roles: str):
    """Dependency factory: allow only listed roles. Empty = any authenticated."""

    def guard(user: User = Depends(get_current_user)) -> User:
        if roles and user.role not in roles:
            raise HTTPException(403, f"requires role in {list(roles)}")
        return user

    return guard
