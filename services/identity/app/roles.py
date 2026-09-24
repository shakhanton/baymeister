"""
Каталог ролей.

Ролі — код, а не таблиця. Набір посад в автосервісі стабільний, а права ролі
мусять змінюватись разом із кодом блоків, які ці права перевіряють. Таблиця
ролей дала б змогу видати право, якого жоден сервіс не знає.

Право має вигляд `<блок>.<дія>`: `.read` — бачити, `.write` — змінювати.
Ідентифікатор блоку з дефісом пишеться з підкресленням: `work_orders.read`.
"""

from dataclasses import dataclass
from typing import Literal

RoleId = Literal["owner", "manager", "mechanic", "cashier", "storekeeper"]

FULL_ACCESS = "*"


@dataclass(frozen=True)
class Role:
    id: RoleId
    title: str
    permissions: tuple[str, ...]


def _rw(*blocks: str) -> tuple[str, ...]:
    return tuple(p for b in blocks for p in (f"{b}.read", f"{b}.write"))


def _r(*blocks: str) -> tuple[str, ...]:
    return tuple(f"{b}.read" for b in blocks)


ROLES: dict[RoleId, Role] = {
    "owner": Role("owner", "Власник", (FULL_ACCESS,)),
    "manager": Role(
        "manager",
        "Адміністратор",
        _rw("customers", "vehicles", "scheduling", "work_orders", "inspections", "documents")
        + _r("catalog", "inventory", "finance", "analytics", "notifications"),
    ),
    "mechanic": Role(
        "mechanic",
        "Механік",
        _rw("inspections") + _r("work_orders", "vehicles", "customers", "scheduling", "catalog"),
    ),
    "cashier": Role(
        "cashier",
        "Касир",
        _rw("finance") + _r("customers", "work_orders", "documents"),
    ),
    "storekeeper": Role(
        "storekeeper",
        "Комірник",
        _rw("inventory", "procurement") + _r("catalog", "work_orders"),
    ),
}


def permissions_of(role: RoleId) -> list[str]:
    return list(ROLES[role].permissions)
