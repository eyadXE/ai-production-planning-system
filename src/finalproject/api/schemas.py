"""Pydantic request/response models for the auth API."""

from pydantic import BaseModel, EmailStr, Field

from finalproject.auth.service import VALID_ROLES


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    account_code: str | None = None      # existing customer
    company_name: str | None = None      # new customer -> auto retail account


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    account_id: int | None = None

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
