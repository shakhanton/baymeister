"""Pydantic-схеми. Вони ж джерело OpenAPI, який має збігатись із contracts/scheduling.yaml."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

BayKind = Literal["lift", "pit", "alignment", "diagnostics", "wash", "other"]
Status = Literal["booked", "arrived", "completed", "cancelled", "no_show"]
Source = Literal["phone", "walk_in", "online"]

MAX_DURATION = timedelta(hours=12)


def _aware_utc(value: datetime) -> datetime:
    """Час без поясу — помилка клієнта: «10:00» у Києві і в UTC — різні записи."""
    if value.tzinfo is None:
        raise ValueError("Час має містити часовий пояс, напр. 2026-09-25T10:00:00+03:00")
    return value.astimezone(UTC)


Instant = Annotated[datetime, AfterValidator(_aware_utc)]
BayName = Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]
Note = Annotated[str, StringConstraints(max_length=500)]


# ── Пости ───────────────────────────────────────────────────────────────────


class BayCreate(BaseModel):
    name: BayName
    kind: BayKind
    position: Annotated[int, Field(ge=0, le=1000)] = 0


class BayUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: BayName | None = None
    kind: BayKind | None = None
    position: Annotated[int, Field(ge=0, le=1000)] | None = None


class Bay(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: BayKind
    position: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ── Записи ──────────────────────────────────────────────────────────────────


def check_period(starts_at: datetime, ends_at: datetime) -> None:
    if ends_at <= starts_at:
        raise ValueError("Кінець запису має бути пізніше за початок")
    if ends_at - starts_at > MAX_DURATION:
        raise ValueError("Запис не може тривати довше 12 годин")


class AppointmentCreate(BaseModel):
    bay_id: uuid.UUID
    customer_id: uuid.UUID
    vehicle_id: uuid.UUID | None = None
    starts_at: Instant
    ends_at: Instant
    source: Source = "phone"
    note: Note | None = None

    @model_validator(mode="after")
    def _period(self) -> "AppointmentCreate":
        check_period(self.starts_at, self.ends_at)
        return self


class AppointmentUpdate(BaseModel):
    """Перенесення: інший пост, інший час, примітка. Клієнт і авто не змінюються."""

    model_config = ConfigDict(extra="forbid")

    bay_id: uuid.UUID | None = None
    starts_at: Instant | None = None
    ends_at: Instant | None = None
    note: Note | None = None


class StatusChange(BaseModel):
    status: Status


class Appointment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bay_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    customer_phone: str
    vehicle_id: uuid.UUID | None
    vehicle_label: str | None
    starts_at: datetime
    ends_at: datetime
    status: Status
    source: Source
    note: str | None
    created_at: datetime
    updated_at: datetime


class Error(BaseModel):
    detail: str
