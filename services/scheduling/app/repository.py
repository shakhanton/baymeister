import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import ACTIVE_STATUSES, Appointment, Bay
from app.peers import CustomerSnapshot, VehicleSnapshot
from app.schemas import AppointmentCreate, BayCreate, BayUpdate

# ── Пости ───────────────────────────────────────────────────────────────────


async def get_bay(session: AsyncSession, bay_id: uuid.UUID) -> Bay | None:
    return await session.get(Bay, bay_id)


async def find_active_bay(session: AsyncSession, name: str) -> Bay | None:
    result = await session.execute(
        select(Bay).where(Bay.name == name, Bay.archived_at.is_(None)).limit(1)
    )
    return result.scalar_one_or_none()


async def list_bays(session: AsyncSession, *, archived: bool) -> list[Bay]:
    condition = Bay.archived_at.is_not(None) if archived else Bay.archived_at.is_(None)
    result = await session.execute(select(Bay).where(condition).order_by(Bay.position, Bay.name))
    return list(result.scalars().all())


async def create_bay(session: AsyncSession, data: BayCreate) -> Bay:
    bay = Bay(**data.model_dump())
    session.add(bay)
    await session.flush()
    await session.refresh(bay)
    return bay


async def update_bay(session: AsyncSession, bay: Bay, data: BayUpdate) -> Bay:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(bay, field, value)
    await session.flush()
    await session.refresh(bay)
    return bay


async def archive_bay(session: AsyncSession, bay: Bay) -> Bay:
    bay.archived_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(bay)
    return bay


async def has_future_appointments(session: AsyncSession, bay_id: uuid.UUID) -> bool:
    result = await session.execute(
        select(Appointment.id)
        .where(
            Appointment.bay_id == bay_id,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.ends_at > datetime.now(UTC),
        )
        .limit(1)
    )
    return result.first() is not None


# ── Записи ──────────────────────────────────────────────────────────────────


async def get(session: AsyncSession, appointment_id: uuid.UUID) -> Appointment | None:
    return await session.get(Appointment, appointment_id)


async def find_overlap(
    session: AsyncSession,
    *,
    bay_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: uuid.UUID | None = None,
) -> Appointment | None:
    """
    Активний запис на тому самому посту, що перетинається з [starts_at, ends_at).

    Межі напіввідкриті: запис до 11:00 і запис з 11:00 не конфліктують —
    машину здали, наступну поставили.
    """
    conditions: list[ColumnElement[bool]] = [
        Appointment.bay_id == bay_id,
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.starts_at < ends_at,
        Appointment.ends_at > starts_at,
    ]
    if exclude_id is not None:
        conditions.append(Appointment.id != exclude_id)
    result = await session.execute(
        select(Appointment).where(*conditions).order_by(Appointment.starts_at).limit(1)
    )
    return result.scalar_one_or_none()


async def list_between(
    session: AsyncSession,
    *,
    starts: datetime,
    ends: datetime,
    bay_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
    include_cancelled: bool,
) -> list[Appointment]:
    conditions: list[ColumnElement[bool]] = [
        Appointment.starts_at < ends,
        Appointment.ends_at > starts,
    ]
    if bay_id is not None:
        conditions.append(Appointment.bay_id == bay_id)
    if customer_id is not None:
        conditions.append(Appointment.customer_id == customer_id)
    if not include_cancelled:
        conditions.append(Appointment.status != "cancelled")
    result = await session.execute(
        select(Appointment).where(*conditions).order_by(Appointment.starts_at, Appointment.bay_id)
    )
    return list(result.scalars().all())


async def create(
    session: AsyncSession,
    data: AppointmentCreate,
    customer: CustomerSnapshot,
    vehicle: VehicleSnapshot | None,
) -> Appointment:
    now = datetime.now(UTC)
    appointment = Appointment(
        bay_id=data.bay_id,
        customer_id=customer.id,
        customer_name=customer.name,
        customer_phone=customer.phone,
        customer_synced_at=now,
        vehicle_id=vehicle.id if vehicle else None,
        vehicle_label=vehicle.label if vehicle else None,
        vehicle_synced_at=now if vehicle else None,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        source=data.source,
        note=data.note,
        status="booked",
    )
    session.add(appointment)
    await session.flush()
    await session.refresh(appointment)
    return appointment


async def save(session: AsyncSession, appointment: Appointment) -> Appointment:
    await session.flush()
    await session.refresh(appointment)
    return appointment


# ── Копії з інших блоків ────────────────────────────────────────────────────


async def apply_customer_update(
    session: AsyncSession, *, customer_id: uuid.UUID, name: str, phone: str, occurred_at: datetime
) -> int:
    """Ідемпотентно й стійко до перестановки — як у vehicles: новіша подія перемагає."""
    result = await session.execute(
        update(Appointment)
        .where(
            Appointment.customer_id == customer_id,
            Appointment.customer_synced_at < occurred_at,
        )
        .values(customer_name=name, customer_phone=phone, customer_synced_at=occurred_at)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def apply_vehicle_update(
    session: AsyncSession, *, vehicle_id: uuid.UUID, label: str, occurred_at: datetime
) -> int:
    result = await session.execute(
        update(Appointment)
        .where(
            Appointment.vehicle_id == vehicle_id,
            Appointment.vehicle_synced_at < occurred_at,
        )
        .values(vehicle_label=label, vehicle_synced_at=occurred_at)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
