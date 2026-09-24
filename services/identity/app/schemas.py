"""Pydantic-схеми. Вони ж джерело OpenAPI, який має збігатись із contracts/identity.yaml."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, StringConstraints

from app.roles import RoleId

# Email зберігається в нижньому регістрі — інакше Oleh@ і oleh@ стали б двома людьми.
Email = Annotated[EmailStr, AfterValidator(lambda v: v.lower())]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=256)]


class LoginRequest(BaseModel):
    email: Email
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class Me(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: RoleId
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: Me


class Role(BaseModel):
    id: RoleId
    title: str
    permissions: list[str]


class UserCreate(BaseModel):
    email: Email
    name: Name
    role: RoleId
    password: Password


class UserUpdate(BaseModel):
    """Часткове оновлення: передаються тільки поля, що змінюються."""

    model_config = ConfigDict(extra="forbid")

    email: Email | None = None
    name: Name | None = None
    role: RoleId | None = None
    password: Password | None = None


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: RoleId
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserPage(BaseModel):
    items: list[User]
    total: int
    limit: int
    offset: int


class JwkKey(BaseModel):
    kty: Literal["RSA"]
    kid: str
    use: Literal["sig"]
    alg: Literal["RS256"]
    n: str
    e: str


class Jwks(BaseModel):
    keys: list[JwkKey]


class Error(BaseModel):
    detail: str
