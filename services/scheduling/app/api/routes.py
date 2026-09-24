import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, repository
from app.api.auth import Principal, require
from app.db import get_session
from app.models import Appointment as AppointmentModel
from app.models import Bay as BayModel
from app.peers import (
    CustomerSnapshot,
    PeerForbidden,
    PeerNotFound,
    Peers,
    PeerUnavailable,
    VehicleSnapshot,
)
from app.schemas import (
    Appointment,
    AppointmentCreate,
    AppointmentUpdate,
    Bay,
    BayCreate,
    BayUpdate,
    Error,
    Instant,
    StatusChange,
    check_period,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]
CanRead = Annotated[Principal, Depends(require("scheduling.read"))]
CanWrite = Annotated[Principal, Depends(require("scheduling.write"))]

NOT_FOUND = {"model": Error, "description": "Не знайдено"}
CONFLICT = {"model": Error, "description": "Конфлікт"}

MAX_RANGE = timedelta(days=31)

# Дозволені переходи статусу. Кінцеві статуси нікуди не ведуть.
TRANSITIONS: dict[str, frozenset[str]] = {
    "booked": frozenset({"arrived", "cancelled", "no_show"}),
    "arrived": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "no_show": frozenset(),
}

STATUS_LABEL = {
    "booked": "записаний",
    "arrived": "приїхав",
    "completed": "завершений",
    "cancelled": "скасований",
    "no_show": "не приїхав",
}

# Подія на кожен статус — щоб слухачі не розбирали payload.
STATUS_EVENT = {
    "arrived": "appointment.arrived",
    "completed": "appointment.completed",
    "cancelled": "appointment.cancelled",
    "no_show": "appointment.no_show",
}


def get_peers(request: Request) -> Peers:
    peers: Peers = request.app.state.peers
    return peers


PeersDep = Annotated[Peers, Depends(get_peers)]


def _event(a: AppointmentModel) -> dict[str, object]:
    return {
        "id": str(a.id),
        "bay_id": str(a.bay_id),
        "customer_id": str(a.customer_id),
        "vehicle_id": str(a.vehicle_id) if a.vehicle_id else None,
        "starts_at": a.starts_at.isoformat(),
        "ends_at": a.ends_at.isoformat(),
        "status": a.status,
    }


def _hhmm(value: datetime) -> str:
    return value.strftime("%d.%m %H:%M UTC")


async def _bay_or_404(session: AsyncSession, bay_id: uuid.UUID) -> BayModel:
    bay = await repository.get_bay(session, bay_id)
    if bay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пост не знайдено")
    return bay


async def _active_bay_or_422(session: AsyncSession, bay_id: uuid.UUID) -> BayModel:
    bay = await repository.get_bay(session, bay_id)
    if bay is None or bay.archived_at is not None:
        raise HTTPException(422, detail="Такого поста немає або його прибрано з дошки")
    return bay


async def _appointment_or_404(session: AsyncSession, appointment_id: uuid.UUID) -> AppointmentModel:
    appointment = await repository.get(session, appointment_id)
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Запис не знайдено")
    return appointment


async def _ensure_free(
    session: AsyncSession,
    bay: BayModel,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: uuid.UUID | None = None,
) -> None:
    clash = await repository.find_overlap(
        session, bay_id=bay.id, starts_at=starts_at, ends_at=ends_at, exclude_id=exclude_id
    )
    if clash is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"{bay.name} зайнятий з {_hhmm(clash.starts_at)} до {_hhmm(clash.ends_at)}: "
            f"{clash.customer_name}",
        )


@asynccontextmanager
async def _slot_guard(session: AsyncSession) -> AsyncIterator[None]:
    """
    Перевірка перетину й запис — не атомарні: два одночасні запити можуть обидва
    пройти перевірку. Тоді другого зупиняє exclusion constraint у базі.

    Помилка приходить уже на flush (INSERT/UPDATE), не лише на commit, — тому
    під охороною весь запис, а не тільки коміт.
    """
    try:
        yield
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Цей час на посту щойно зайняли. Оновіть дошку й оберіть інший.",
        ) from exc


def _peer_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PeerNotFound):
        what = "клієнта" if str(exc) == "customers" else "автомобіля"
        return HTTPException(422, detail=f"Такого {what} не існує")
    if isinstance(exc, PeerForbidden):
        perm = "customers.read" if str(exc) == "customers" else "vehicles.read"
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=f"Бракує права {perm}")
    block = (
        "Клієнти" if isinstance(exc, PeerUnavailable) and exc.block == "customers" else "Автомобілі"
    )
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Не вдалося перевірити дані: блок «{block}» недоступний. Спробуйте за хвилину.",
    )


# ── Пости ───────────────────────────────────────────────────────────────────


@router.get("/scheduling/bays", response_model=list[Bay], tags=["bays"])
async def list_bays(
    _: CanRead, session: Session, archived: Annotated[bool, Query()] = False
) -> list[Bay]:
    return [Bay.model_validate(b) for b in await repository.list_bays(session, archived=archived)]


@router.post(
    "/scheduling/bays",
    response_model=Bay,
    status_code=status.HTTP_201_CREATED,
    responses={409: CONFLICT},
    tags=["bays"],
)
async def create_bay(data: BayCreate, _: CanWrite, session: Session) -> Bay:
    if await repository.find_active_bay(session, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Пост «{data.name}» уже є")
    bay = await repository.create_bay(session, data)
    await session.commit()
    return Bay.model_validate(bay)


@router.patch(
    "/scheduling/bays/{bay_id}",
    response_model=Bay,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["bays"],
)
async def update_bay(bay_id: uuid.UUID, data: BayUpdate, _: CanWrite, session: Session) -> Bay:
    bay = await _bay_or_404(session, bay_id)
    if data.name and data.name != bay.name and await repository.find_active_bay(session, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Пост «{data.name}» уже є")
    bay = await repository.update_bay(session, bay, data)
    await session.commit()
    return Bay.model_validate(bay)


@router.post(
    "/scheduling/bays/{bay_id}/archive",
    response_model=Bay,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["bays"],
)
async def archive_bay(bay_id: uuid.UUID, _: CanWrite, session: Session) -> Bay:
    bay = await _bay_or_404(session, bay_id)
    if await repository.has_future_appointments(session, bay.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"На «{bay.name}» є майбутні записи. Спершу перенесіть або скасуйте їх.",
        )
    bay = await repository.archive_bay(session, bay)
    await session.commit()
    return Bay.model_validate(bay)


# ── Записи ──────────────────────────────────────────────────────────────────


@router.get("/scheduling/appointments", response_model=list[Appointment], tags=["appointments"])
async def list_appointments(
    _: CanRead,
    session: Session,
    from_: Annotated[Instant, Query(alias="from")],
    to: Annotated[Instant, Query()],
    bay_id: Annotated[uuid.UUID | None, Query()] = None,
    customer_id: Annotated[uuid.UUID | None, Query()] = None,
    include_cancelled: Annotated[bool, Query()] = False,
) -> list[Appointment]:
    if to <= from_:
        raise HTTPException(422, detail="Кінець проміжку має бути пізніше за початок")
    if to - from_ > MAX_RANGE:
        raise HTTPException(422, detail="Проміжок не довше 31 дня")
    items = await repository.list_between(
        session,
        starts=from_,
        ends=to,
        bay_id=bay_id,
        customer_id=customer_id,
        include_cancelled=include_cancelled,
    )
    return [Appointment.model_validate(a) for a in items]


@router.post(
    "/scheduling/appointments",
    response_model=Appointment,
    status_code=status.HTTP_201_CREATED,
    responses={409: CONFLICT},
    tags=["appointments"],
)
async def create_appointment(
    data: AppointmentCreate,
    _: CanWrite,
    session: Session,
    peers: PeersDep,
    request: Request,
) -> Appointment:
    bay = await _active_bay_or_422(session, data.bay_id)
    # Спершу дешева перевірка в своїй базі, потім — запити до сусідів.
    await _ensure_free(session, bay, data.starts_at, data.ends_at)

    headers = dict(request.headers)
    try:
        customer: CustomerSnapshot = await peers.customer(data.customer_id, headers)
        vehicle: VehicleSnapshot | None = (
            await peers.vehicle(data.vehicle_id, headers) if data.vehicle_id else None
        )
    except (PeerNotFound, PeerForbidden, PeerUnavailable) as exc:
        raise _peer_error(exc) from exc

    if vehicle is not None and vehicle.customer_id != customer.id:
        raise HTTPException(422, detail="Цей автомобіль належить іншому клієнту")

    async with _slot_guard(session):
        appointment = await repository.create(session, data, customer, vehicle)
        await session.commit()

    await events.publish("appointment.booked", _event(appointment))
    return Appointment.model_validate(appointment)


@router.get(
    "/scheduling/appointments/{appointment_id}",
    response_model=Appointment,
    responses={404: NOT_FOUND},
    tags=["appointments"],
)
async def get_appointment(appointment_id: uuid.UUID, _: CanRead, session: Session) -> Appointment:
    return Appointment.model_validate(await _appointment_or_404(session, appointment_id))


@router.patch(
    "/scheduling/appointments/{appointment_id}",
    response_model=Appointment,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["appointments"],
)
async def reschedule_appointment(
    appointment_id: uuid.UUID, data: AppointmentUpdate, _: CanWrite, session: Session
) -> Appointment:
    appointment = await _appointment_or_404(session, appointment_id)
    fields = data.model_dump(exclude_unset=True)
    moves = {"bay_id", "starts_at", "ends_at"} & fields.keys()

    if moves:
        if appointment.status != "booked":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Запис уже {STATUS_LABEL[appointment.status]} — переносити пізно",
            )
        bay = await _active_bay_or_422(session, data.bay_id or appointment.bay_id)
        starts_at = data.starts_at or appointment.starts_at
        ends_at = data.ends_at or appointment.ends_at
        try:
            check_period(starts_at, ends_at)
        except ValueError as exc:
            raise HTTPException(422, detail=str(exc)) from exc
        await _ensure_free(session, bay, starts_at, ends_at, exclude_id=appointment.id)
        appointment.bay_id, appointment.starts_at, appointment.ends_at = bay.id, starts_at, ends_at

    if "note" in fields:
        appointment.note = data.note

    async with _slot_guard(session):
        appointment = await repository.save(session, appointment)
        await session.commit()

    if moves:
        await events.publish("appointment.rescheduled", _event(appointment))
    return Appointment.model_validate(appointment)


@router.post(
    "/scheduling/appointments/{appointment_id}/status",
    response_model=Appointment,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["appointments"],
)
async def change_status(
    appointment_id: uuid.UUID, data: StatusChange, _: CanWrite, session: Session
) -> Appointment:
    appointment = await _appointment_or_404(session, appointment_id)

    if data.status not in TRANSITIONS[appointment.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Запис {STATUS_LABEL[appointment.status]} — не можна зробити "
            f"«{STATUS_LABEL[data.status]}»",
        )

    appointment.status = data.status
    appointment = await repository.save(session, appointment)
    await session.commit()

    await events.publish(STATUS_EVENT[data.status], _event(appointment))
    return Appointment.model_validate(appointment)


@router.get("/health", tags=["health"])
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
