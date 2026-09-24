import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, repository
from app.api.auth import Principal, require
from app.customers_client import (
    CustomerForbidden,
    CustomerNotFound,
    CustomersClient,
    CustomerSnapshot,
    CustomersUnavailable,
)
from app.db import get_session
from app.models import Vehicle as VehicleModel
from app.schemas import (
    Error,
    MileageCreate,
    MileageReading,
    Vehicle,
    VehicleCreate,
    VehiclePage,
    VehicleUpdate,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]
CanRead = Annotated[Principal, Depends(require("vehicles.read"))]
CanWrite = Annotated[Principal, Depends(require("vehicles.write"))]

NOT_FOUND = {"model": Error, "description": "Автомобіль не знайдено"}
CONFLICT = {"model": Error, "description": "Конфлікт"}
INVALID = {"model": Error, "description": "Клієнта не існує"}
UNAVAILABLE = {"model": Error, "description": "Блок customers недоступний"}


def get_customers(request: Request) -> CustomersClient:
    client: CustomersClient = request.app.state.customers
    return client


Customers = Annotated[CustomersClient, Depends(get_customers)]


async def _owner(
    customers: CustomersClient, customer_id: uuid.UUID, request: Request
) -> CustomerSnapshot:
    try:
        return await customers.get(customer_id, dict(request.headers))
    except CustomerNotFound as exc:
        raise HTTPException(422, detail="Такого клієнта не існує") from exc
    except CustomerForbidden as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Бракує права customers.read, щоб обрати власника"
        ) from exc
    except CustomersUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не вдалося перевірити клієнта: блок «Клієнти» недоступний. "
            "Спробуйте за хвилину.",
        ) from exc


async def _get_or_404(session: AsyncSession, vehicle_id: uuid.UUID) -> VehicleModel:
    vehicle = await repository.get(session, vehicle_id)
    if vehicle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Автомобіль не знайдено")
    return vehicle


async def _ensure_unique(
    session: AsyncSession, *, plate: str | None, vin: str | None, own_id: uuid.UUID | None = None
) -> None:
    if plate is not None:
        taken = await repository.find_active(session, plate=plate)
        if taken is not None and taken.id != own_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Автомобіль із держномером {plate} уже є: {taken.make} {taken.model}, "
                f"власник {taken.customer_name}",
            )
    if vin is not None:
        taken = await repository.find_active(session, vin=vin)
        if taken is not None and taken.id != own_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Автомобіль із VIN {vin} уже є: держномер {taken.plate}",
            )


def _event(vehicle: VehicleModel) -> dict[str, object]:
    return {
        "id": str(vehicle.id),
        "customer_id": str(vehicle.customer_id),
        "plate": vehicle.plate,
        "vin": vehicle.vin,
        "make": vehicle.make,
        "model": vehicle.model,
    }


@router.get("/vehicles", response_model=VehiclePage, tags=["vehicles"])
async def list_vehicles(
    _: CanRead,
    session: Session,
    search: Annotated[str | None, Query(max_length=120)] = None,
    customer_id: Annotated[uuid.UUID | None, Query()] = None,
    archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VehiclePage:
    items, total = await repository.list_page(
        session,
        search=search,
        customer_id=customer_id,
        archived=archived,
        limit=limit,
        offset=offset,
    )
    return VehiclePage(
        items=[Vehicle.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/vehicles",
    response_model=Vehicle,
    status_code=status.HTTP_201_CREATED,
    responses={409: CONFLICT, 422: INVALID, 503: UNAVAILABLE},
    tags=["vehicles"],
)
async def create_vehicle(
    data: VehicleCreate,
    _: CanWrite,
    session: Session,
    customers: Customers,
    request: Request,
) -> Vehicle:
    await _ensure_unique(session, plate=data.plate, vin=data.vin)
    owner = await _owner(customers, data.customer_id, request)

    vehicle = await repository.create(session, data, owner)
    await session.commit()

    await events.publish("vehicle.created", _event(vehicle))
    return Vehicle.model_validate(vehicle)


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=Vehicle,
    responses={404: NOT_FOUND},
    tags=["vehicles"],
)
async def get_vehicle(vehicle_id: uuid.UUID, _: CanRead, session: Session) -> Vehicle:
    return Vehicle.model_validate(await _get_or_404(session, vehicle_id))


@router.patch(
    "/vehicles/{vehicle_id}",
    response_model=Vehicle,
    responses={404: NOT_FOUND, 409: CONFLICT, 422: INVALID, 503: UNAVAILABLE},
    tags=["vehicles"],
)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    data: VehicleUpdate,
    _: CanWrite,
    session: Session,
    customers: Customers,
    request: Request,
) -> Vehicle:
    vehicle = await _get_or_404(session, vehicle_id)
    await _ensure_unique(session, plate=data.plate, vin=data.vin, own_id=vehicle.id)

    # Новий власник — продаж. Перевіряємо клієнта і беремо свіжу копію.
    new_owner = None
    if data.customer_id is not None and data.customer_id != vehicle.customer_id:
        new_owner = await _owner(customers, data.customer_id, request)

    vehicle = await repository.update_vehicle(session, vehicle, data, new_owner)
    await session.commit()

    await events.publish("vehicle.updated", _event(vehicle))
    return Vehicle.model_validate(vehicle)


@router.post(
    "/vehicles/{vehicle_id}/archive",
    response_model=Vehicle,
    responses={404: NOT_FOUND},
    tags=["vehicles"],
)
async def archive_vehicle(vehicle_id: uuid.UUID, _: CanWrite, session: Session) -> Vehicle:
    vehicle = await _get_or_404(session, vehicle_id)
    vehicle = await repository.archive(session, vehicle)
    await session.commit()

    await events.publish("vehicle.archived", {"id": str(vehicle.id)})
    return Vehicle.model_validate(vehicle)


@router.get(
    "/vehicles/{vehicle_id}/mileage",
    response_model=list[MileageReading],
    responses={404: NOT_FOUND},
    tags=["mileage"],
)
async def list_mileage(vehicle_id: uuid.UUID, _: CanRead, session: Session) -> list[MileageReading]:
    await _get_or_404(session, vehicle_id)
    readings = await repository.list_mileage(session, vehicle_id)
    return [MileageReading.model_validate(r) for r in readings]


@router.post(
    "/vehicles/{vehicle_id}/mileage",
    response_model=MileageReading,
    status_code=status.HTTP_201_CREATED,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["mileage"],
)
async def record_mileage(
    vehicle_id: uuid.UUID, data: MileageCreate, _: CanWrite, session: Session
) -> MileageReading:
    vehicle = await _get_or_404(session, vehicle_id)

    # Одометр не крутиться назад. Менше число — помилка введення або скрутка,
    # і в обох випадках людина має це побачити, а не отримати тихий запис.
    if vehicle.mileage_km is not None and data.km < vehicle.mileage_km:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Пробіг {data.km} км менший за останній записаний ({vehicle.mileage_km} км)",
        )

    reading = await repository.add_mileage(session, vehicle, data.km, data.note)
    await session.commit()

    await events.publish(
        "vehicle.mileage_recorded",
        {"id": str(vehicle.id), "km": reading.km, "recorded_at": reading.recorded_at.isoformat()},
    )
    return MileageReading.model_validate(reading)


@router.get("/health", tags=["health"])
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
