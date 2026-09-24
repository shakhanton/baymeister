import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.customers_client import CustomerSnapshot
from app.models import MileageReading, Vehicle
from app.schemas import VehicleCreate, VehicleUpdate


async def get(session: AsyncSession, vehicle_id: uuid.UUID) -> Vehicle | None:
    return await session.get(Vehicle, vehicle_id)


async def find_active(
    session: AsyncSession, *, plate: str | None = None, vin: str | None = None
) -> Vehicle | None:
    """Активний автомобіль із таким номером або VIN — для зрозумілого 409."""
    condition = Vehicle.plate == plate if plate is not None else Vehicle.vin == vin
    result = await session.execute(
        select(Vehicle).where(condition, Vehicle.archived_at.is_(None)).limit(1)
    )
    return result.scalar_one_or_none()


async def list_page(
    session: AsyncSession,
    *,
    search: str | None,
    customer_id: uuid.UUID | None,
    archived: bool,
    limit: int,
    offset: int,
) -> tuple[list[Vehicle], int]:
    conditions: list[ColumnElement[bool]] = [
        Vehicle.archived_at.is_not(None) if archived else Vehicle.archived_at.is_(None)
    ]

    if customer_id is not None:
        conditions.append(Vehicle.customer_id == customer_id)

    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Vehicle.plate.ilike(pattern),
                Vehicle.vin.ilike(pattern),
                Vehicle.make.ilike(pattern),
                Vehicle.model.ilike(pattern),
                Vehicle.customer_name.ilike(pattern),
            )
        )

    total = await session.scalar(select(func.count()).select_from(Vehicle).where(*conditions))

    result = await session.execute(
        select(Vehicle)
        .where(*conditions)
        .order_by(Vehicle.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(result.scalars().all()), int(total or 0)


async def create(session: AsyncSession, data: VehicleCreate, owner: CustomerSnapshot) -> Vehicle:
    vehicle = Vehicle(
        **data.model_dump(exclude={"mileage_km"}),
        customer_name=owner.name,
        customer_phone=owner.phone,
        customer_synced_at=datetime.now(UTC),
    )
    session.add(vehicle)
    await session.flush()

    if data.mileage_km is not None:
        await add_mileage(session, vehicle, data.mileage_km, note="При прийманні")

    await session.refresh(vehicle)
    return vehicle


async def update_vehicle(
    session: AsyncSession,
    vehicle: Vehicle,
    data: VehicleUpdate,
    new_owner: CustomerSnapshot | None,
) -> Vehicle:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    if new_owner is not None:
        vehicle.customer_name = new_owner.name
        vehicle.customer_phone = new_owner.phone
        vehicle.customer_synced_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(vehicle)
    return vehicle


async def archive(session: AsyncSession, vehicle: Vehicle) -> Vehicle:
    vehicle.archived_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(vehicle)
    return vehicle


async def add_mileage(
    session: AsyncSession, vehicle: Vehicle, km: int, note: str | None
) -> MileageReading:
    reading = MileageReading(vehicle_id=vehicle.id, km=km, note=note)
    session.add(reading)
    vehicle.mileage_km = km
    await session.flush()
    await session.refresh(reading)
    return reading


async def list_mileage(session: AsyncSession, vehicle_id: uuid.UUID) -> list[MileageReading]:
    result = await session.execute(
        select(MileageReading)
        .where(MileageReading.vehicle_id == vehicle_id)
        .order_by(MileageReading.recorded_at.desc(), MileageReading.km.desc())
    )
    return list(result.scalars().all())


async def apply_customer_update(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    name: str,
    phone: str,
    occurred_at: datetime,
) -> int:
    """
    Оновити копію власника в усіх його автомобілях.

    Ідемпотентно й стійко до перестановки: брокер гарантує at-least-once і не
    гарантує порядок, тому подія застосовується, лише якщо вона новіша за вже
    застосовану. Повтор тієї самої події або запізніла стара нічого не змінюють.
    """
    result = await session.execute(
        update(Vehicle)
        .where(Vehicle.customer_id == customer_id, Vehicle.customer_synced_at < occurred_at)
        .values(customer_name=name, customer_phone=phone, customer_synced_at=occurred_at)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
