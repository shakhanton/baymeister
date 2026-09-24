import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, repository
from app.api.auth import CurrentPrincipal, Principal, require
from app.config import get_settings
from app.db import get_session
from app.models import User as UserModel
from app.roles import ROLES, permissions_of
from app.schemas import (
    Error,
    Jwks,
    LoginRequest,
    Me,
    Role,
    TokenResponse,
    User,
    UserCreate,
    UserPage,
    UserUpdate,
)
from app.security import issue_token, jwks, verify_password

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]
CanRead = Annotated[Principal, Depends(require("identity.read"))]
CanWrite = Annotated[Principal, Depends(require("identity.write"))]

UNAUTHORIZED = {"model": Error, "description": "Немає або недійсний токен"}
FORBIDDEN = {"model": Error, "description": "Бракує права"}
NOT_FOUND = {"model": Error, "description": "Співробітника не знайдено"}
CONFLICT = {"model": Error, "description": "Конфлікт"}

BAD_CREDENTIALS = "Невірний email або пароль"


def _me(user: UserModel) -> Me:
    return Me(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,  # CHECK у базі гарантує RoleId
        permissions=permissions_of(user.role),  # type: ignore[arg-type]
    )


async def _get_or_404(session: AsyncSession, user_id: uuid.UUID) -> UserModel:
    user = await repository.get(session, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Співробітника не знайдено")
    return user


async def _ensure_owner_remains(session: AsyncSession, user: UserModel) -> None:
    """Система без жодного активного власника — це система, якою ніхто не керує."""
    if user.role != "owner" or not user.is_active:
        return
    if await repository.count_active_owners(session) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Це останній власник. Спершу призначте іншого власника.",
        )


def _user_event(user: UserModel) -> dict[str, str]:
    return {"id": str(user.id), "name": user.name, "role": user.role}


# ── Вхід ────────────────────────────────────────────────────────────────────


@router.post(
    "/identity/auth/login",
    response_model=TokenResponse,
    responses={401: {"model": Error, "description": BAD_CREDENTIALS}},
    tags=["auth"],
)
async def login(data: LoginRequest, session: Session) -> TokenResponse:
    user = await repository.get_by_email(session, data.email)

    # Пароль перевіряється завжди, навіть коли користувача немає: інакше час
    # відповіді підказує, які email зареєстровані.
    password_ok = verify_password(user.password_hash if user else None, data.password)
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=BAD_CREDENTIALS)

    await repository.touch_login(session, user)
    await session.commit()

    me = _me(user)
    token = issue_token(user_id=user.id, name=user.name, role=user.role, permissions=me.permissions)
    return TokenResponse(
        access_token=token,
        expires_in=get_settings().access_token_ttl_seconds,
        user=me,
    )


@router.get("/identity/.well-known/jwks.json", response_model=Jwks, tags=["auth"])
async def get_jwks(response: Response) -> Jwks:
    response.headers["Cache-Control"] = "public, max-age=300"
    return Jwks.model_validate(jwks())


@router.get("/identity/me", response_model=Me, responses={401: UNAUTHORIZED}, tags=["auth"])
async def get_me(principal: CurrentPrincipal, session: Session) -> Me:
    user = await repository.get(session, principal.user_id)
    # Токен ще живий, а людину вже вимкнули — каркас має вийти на екран входу.
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Обліковий запис вимкнено")
    return _me(user)


# ── Ролі ────────────────────────────────────────────────────────────────────


@router.get(
    "/identity/roles",
    response_model=list[Role],
    responses={401: UNAUTHORIZED, 403: FORBIDDEN},
    tags=["roles"],
)
async def list_roles(_: CanRead) -> list[Role]:
    return [Role(id=r.id, title=r.title, permissions=list(r.permissions)) for r in ROLES.values()]


# ── Співробітники ───────────────────────────────────────────────────────────


@router.get(
    "/identity/users",
    response_model=UserPage,
    responses={401: UNAUTHORIZED, 403: FORBIDDEN},
    tags=["users"],
)
async def list_users(
    _: CanRead,
    session: Session,
    search: Annotated[str | None, Query(max_length=120)] = None,
    inactive: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserPage:
    items, total = await repository.list_page(
        session, search=search, inactive=inactive, limit=limit, offset=offset
    )
    return UserPage(
        items=[User.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/identity/users",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    responses={401: UNAUTHORIZED, 403: FORBIDDEN, 409: CONFLICT},
    tags=["users"],
)
async def create_user(data: UserCreate, _: CanWrite, session: Session) -> User:
    if await repository.get_by_email(session, data.email):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Співробітник з email {data.email} уже існує",
        )

    user = await repository.create(session, data)
    await session.commit()

    await events.publish("user.created", _user_event(user))
    return User.model_validate(user)


@router.get(
    "/identity/users/{user_id}",
    response_model=User,
    responses={401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    tags=["users"],
)
async def get_user(user_id: uuid.UUID, _: CanRead, session: Session) -> User:
    return User.model_validate(await _get_or_404(session, user_id))


@router.patch(
    "/identity/users/{user_id}",
    response_model=User,
    responses={401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND, 409: CONFLICT},
    tags=["users"],
)
async def update_user(user_id: uuid.UUID, data: UserUpdate, _: CanWrite, session: Session) -> User:
    user = await _get_or_404(session, user_id)

    if data.email and data.email != user.email:
        taken = await repository.get_by_email(session, data.email)
        if taken is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Email {data.email} належить іншому співробітнику",
            )

    if data.role is not None and data.role != "owner":
        await _ensure_owner_remains(session, user)

    user = await repository.update(session, user, data)
    await session.commit()

    await events.publish("user.updated", _user_event(user))
    return User.model_validate(user)


@router.post(
    "/identity/users/{user_id}/deactivate",
    response_model=User,
    responses={401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND, 409: CONFLICT},
    tags=["users"],
)
async def deactivate_user(user_id: uuid.UUID, principal: CanWrite, session: Session) -> User:
    user = await _get_or_404(session, user_id)

    if user.id == principal.user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Не можна вимкнути самого себе")
    await _ensure_owner_remains(session, user)

    user = await repository.set_active(session, user, False)
    await session.commit()

    # scheduling прибирає механіка з планувальника, payroll закриває табель.
    await events.publish("user.deactivated", {"id": str(user.id)})
    return User.model_validate(user)


@router.post(
    "/identity/users/{user_id}/activate",
    response_model=User,
    responses={401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    tags=["users"],
)
async def activate_user(user_id: uuid.UUID, _: CanWrite, session: Session) -> User:
    user = await _get_or_404(session, user_id)
    user = await repository.set_active(session, user, True)
    await session.commit()

    await events.publish("user.activated", _user_event(user))
    return User.model_validate(user)


@router.get("/health", tags=["health"])
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
