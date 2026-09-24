import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, repository
from app.api.auth import Principal, require
from app.db import get_session
from app.models import Part as PartModel
from app.models import Service as ServiceModel
from app.money import format_2, quantize
from app.schemas import (
    Error,
    LaborRate,
    LaborRateCreate,
    Part,
    PartCreate,
    PartPage,
    PartUpdate,
    Service,
    ServiceCreate,
    ServicePage,
    ServiceUpdate,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]
CanRead = Annotated[Principal, Depends(require("catalog.read"))]
CanWrite = Annotated[Principal, Depends(require("catalog.write"))]

NOT_FOUND = {"model": Error, "description": "Не знайдено"}
CONFLICT = {"model": Error, "description": "Конфлікт"}


def _service_out(service: ServiceModel, rate: Decimal | None) -> Service:
    """Ціна рахується при читанні: зміна ставки одразу видна у всьому прайсі."""
    if service.fixed_price is not None:
        price, source = service.fixed_price, "fixed"
    elif rate is not None:
        price, source = quantize(service.norm_hours * rate), "norm_hours"
    else:
        price, source = None, "unknown"
    return Service(
        id=service.id,
        code=service.code,
        name=service.name,
        category=service.category,
        norm_hours=service.norm_hours,
        fixed_price=service.fixed_price,
        price=price,
        price_source=source,
        archived_at=service.archived_at,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


async def _current_rate(session: AsyncSession) -> Decimal | None:
    rate = await repository.rate_at(session)
    return rate.amount if rate else None


# ── Ставка ──────────────────────────────────────────────────────────────────


@router.get(
    "/catalog/labor-rate",
    response_model=LaborRate,
    responses={404: NOT_FOUND},
    tags=["labor-rate"],
)
async def get_labor_rate(
    _: CanRead, session: Session, at: Annotated[datetime | None, Query()] = None
) -> LaborRate:
    rate = await repository.rate_at(session, at)
    if rate is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Вартість нормо-години ще не задана"
            if at is None
            else "На цей момент ставки не було",
        )
    return LaborRate.model_validate(rate)


@router.put("/catalog/labor-rate", response_model=LaborRate, tags=["labor-rate"])
async def set_labor_rate(data: LaborRateCreate, _: CanWrite, session: Session) -> LaborRate:
    if data.amount <= 0:
        raise HTTPException(422, detail="Вартість нормо-години має бути більшою за нуль")

    rate = await repository.add_rate(session, data.amount, data.effective_from)
    await session.commit()

    await events.publish(
        "labor_rate.changed",
        {"amount": format_2(rate.amount), "effective_from": rate.effective_from.isoformat()},
    )
    return LaborRate.model_validate(rate)


@router.get("/catalog/labor-rate/history", response_model=list[LaborRate], tags=["labor-rate"])
async def list_labor_rates(_: CanRead, session: Session) -> list[LaborRate]:
    return [LaborRate.model_validate(r) for r in await repository.list_rates(session)]


# ── Роботи ──────────────────────────────────────────────────────────────────


async def _get_service_or_404(session: AsyncSession, service_id: uuid.UUID) -> ServiceModel:
    service = await repository.get_service(session, service_id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Роботу не знайдено")
    return service


@router.get("/catalog/services", response_model=ServicePage, tags=["services"])
async def list_services(
    _: CanRead,
    session: Session,
    search: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(max_length=60)] = None,
    archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ServicePage:
    items, total = await repository.list_services(
        session, search=search, category=category, archived=archived, limit=limit, offset=offset
    )
    rate = await _current_rate(session)
    return ServicePage(
        items=[_service_out(s, rate) for s in items],
        total=total,
        limit=limit,
        offset=offset,
        labor_rate=rate,
    )


@router.post(
    "/catalog/services",
    response_model=Service,
    status_code=status.HTTP_201_CREATED,
    responses={409: CONFLICT},
    tags=["services"],
)
async def create_service(data: ServiceCreate, _: CanWrite, session: Session) -> Service:
    if await repository.find_active_service(session, data.code):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Робота з кодом {data.code} уже існує"
        )

    service = await repository.create_service(session, data)
    await session.commit()

    await events.publish("service.created", {"id": str(service.id), "code": service.code})
    return _service_out(service, await _current_rate(session))


@router.get(
    "/catalog/services/{service_id}",
    response_model=Service,
    responses={404: NOT_FOUND},
    tags=["services"],
)
async def get_service(service_id: uuid.UUID, _: CanRead, session: Session) -> Service:
    service = await _get_service_or_404(session, service_id)
    return _service_out(service, await _current_rate(session))


@router.patch(
    "/catalog/services/{service_id}",
    response_model=Service,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["services"],
)
async def update_service(
    service_id: uuid.UUID, data: ServiceUpdate, _: CanWrite, session: Session
) -> Service:
    service = await _get_service_or_404(session, service_id)

    if data.code and data.code != service.code:
        taken = await repository.find_active_service(session, data.code)
        if taken is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"Код {data.code} зайнятий роботою «{taken.name}»"
            )

    service = await repository.update_service(session, service, data)
    await session.commit()

    await events.publish("service.updated", {"id": str(service.id), "code": service.code})
    return _service_out(service, await _current_rate(session))


@router.post(
    "/catalog/services/{service_id}/archive",
    response_model=Service,
    responses={404: NOT_FOUND},
    tags=["services"],
)
async def archive_service(service_id: uuid.UUID, _: CanWrite, session: Session) -> Service:
    service = await _get_service_or_404(session, service_id)
    await repository.archive(session, service)
    await session.commit()

    await events.publish("service.archived", {"id": str(service.id)})
    return _service_out(service, await _current_rate(session))


# ── Запчастини ──────────────────────────────────────────────────────────────


def _part_event(part: PartModel) -> dict[str, str]:
    """Усе, що потрібно inventory для картки номенклатури, — без запиту назад."""
    return {
        "id": str(part.id),
        "sku": part.sku,
        "brand": part.brand,
        "name": part.name,
        "unit": part.unit,
    }


async def _get_part_or_404(session: AsyncSession, part_id: uuid.UUID) -> PartModel:
    part = await repository.get_part(session, part_id)
    if part is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Запчастину не знайдено")
    return part


@router.get("/catalog/parts", response_model=PartPage, tags=["parts"])
async def list_parts(
    _: CanRead,
    session: Session,
    search: Annotated[str | None, Query(max_length=120)] = None,
    archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PartPage:
    items, total = await repository.list_parts(
        session, search=search, archived=archived, limit=limit, offset=offset
    )
    return PartPage(
        items=[Part.model_validate(p) for p in items], total=total, limit=limit, offset=offset
    )


@router.post(
    "/catalog/parts",
    response_model=Part,
    status_code=status.HTTP_201_CREATED,
    responses={409: CONFLICT},
    tags=["parts"],
)
async def create_part(data: PartCreate, _: CanWrite, session: Session) -> Part:
    if await repository.find_active_part(session, data.sku, data.brand):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Запчастина {data.brand} {data.sku} уже є в каталозі",
        )

    part = await repository.create_part(session, data)
    await session.commit()

    await events.publish("part.created", _part_event(part))
    return Part.model_validate(part)


@router.get(
    "/catalog/parts/{part_id}",
    response_model=Part,
    responses={404: NOT_FOUND},
    tags=["parts"],
)
async def get_part(part_id: uuid.UUID, _: CanRead, session: Session) -> Part:
    return Part.model_validate(await _get_part_or_404(session, part_id))


@router.patch(
    "/catalog/parts/{part_id}",
    response_model=Part,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["parts"],
)
async def update_part(part_id: uuid.UUID, data: PartUpdate, _: CanWrite, session: Session) -> Part:
    part = await _get_part_or_404(session, part_id)

    sku = data.sku or part.sku
    brand = data.brand or part.brand
    if (sku, brand) != (part.sku, part.brand):
        taken = await repository.find_active_part(session, sku, brand)
        if taken is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"Запчастина {brand} {sku} уже є в каталозі"
            )

    old_price = part.price
    part = await repository.update_part(session, part, data)
    await session.commit()

    await events.publish("part.updated", _part_event(part))
    if part.price != old_price:
        await events.publish(
            "part.price_changed",
            {"id": str(part.id), "old": format_2(old_price), "new": format_2(part.price)},
        )
    return Part.model_validate(part)


@router.post(
    "/catalog/parts/{part_id}/archive",
    response_model=Part,
    responses={404: NOT_FOUND},
    tags=["parts"],
)
async def archive_part(part_id: uuid.UUID, _: CanWrite, session: Session) -> Part:
    part = await _get_part_or_404(session, part_id)
    await repository.archive(session, part)
    await session.commit()

    await events.publish("part.archived", {"id": str(part.id)})
    return Part.model_validate(part)


@router.get("/health", tags=["health"])
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
