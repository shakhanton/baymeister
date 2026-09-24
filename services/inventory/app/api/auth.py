"""
Хто робить запит.

Токен перевіряє gateway і передає результат заголовками X-User-*. Сервіс їм
довіряє, тому до сервісу не можна ходити в обхід gateway — у проді порт сервісу
відкритий тільки у внутрішній мережі. Gateway зрізає ці заголовки з вхідного
запиту, тож підробити їх ззовні неможливо.

Цей файл — зразок для решти блоків: копіюється як є.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    role: str
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions


async def current_principal(
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
    x_user_permissions: Annotated[str | None, Header()] = None,
) -> Principal:
    if not x_user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Потрібно увійти")
    try:
        user_id = uuid.UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Потрібно увійти") from exc

    permissions = frozenset(p for p in (x_user_permissions or "").split(",") if p)
    return Principal(user_id=user_id, role=x_user_role or "", permissions=permissions)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def require(permission: str) -> Callable[[Principal], Awaitable[Principal]]:
    async def dependency(principal: CurrentPrincipal) -> Principal:
        if not principal.can(permission):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Бракує права {permission}",
            )
        return principal

    return dependency
