"""Auth domain logic: user creation and credential checks."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalproject.core.security import hash_password, verify_password
from finalproject.db.models import Account, User

VALID_ROLES = ("client", "engineer", "manager", "viewer")


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def create_user(
    session: Session,
    email: str,
    password: str,
    full_name: str,
    role: str,
    account_code: str | None = None,
) -> User:
    email = email.strip().lower()
    if role not in VALID_ROLES:
        raise AuthError(f"invalid role '{role}'; must be one of {VALID_ROLES}")
    if len(password) < 8:
        raise AuthError("password must be at least 8 characters")
    if role == "client" and not account_code:
        raise AuthError("client users must provide their company account code")

    account_id = None
    if account_code:
        account = session.scalar(select(Account).where(Account.code == account_code))
        if not account:
            raise AuthError(f"unknown account code '{account_code}'", 404)
        account_id = account.id

    if session.scalar(select(User).where(User.email == email)):
        raise AuthError("email already registered", 409)

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip() or email,
        role=role,
        account_id=account_id,
    )
    session.add(user)
    session.commit()
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        raise AuthError("invalid email or password", 401)
    return user
