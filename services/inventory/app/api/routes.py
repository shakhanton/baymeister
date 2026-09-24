import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, repository, stock
from app.api.auth import Principal, require
from app.catalog_client import CatalogClient, CatalogForbidden, CatalogUnavailable, PartNotFound
from app.db import get_session
from app.models import Item
from app.schemas import (
    CountCreate,
    Error,
    Lot,
    Movement,
    ReceiptCreate,
    Reservation,
    StockDetail,
    StockItem,
    StockItemUpdate,
    StockPage,
)
from app.stock import Levels

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]
CanRead = Annotated[Principal, Depends(require("inventory.read"))]
CanWrite = Annotated[Principal, Depends(require("inventory.write"))]

NOT_FOUND = {"model": Error, "description": "Деталі на складі немає"}


def get_catalog(request: Request) -> CatalogClient:
    client: CatalogClient = request.app.state.catalog
    return client


Catalog = Annotated[CatalogClient, Depends(get_catalog)]


def _item_out(item: Item, lv: Levels) -> StockItem:
    return StockItem(
        part_id=item.part_id,
        sku=item.sku,
        brand=item.brand,
        name=item.name,
        unit=item.unit,
        location=item.location,
        on_hand=lv.on_hand,
        reserved=lv.reserved,
        free=lv.free,
        min_qty=item.min_qty,
        value=lv.value,
        low=stock.is_low(item, lv),
    )


async def _item_or_404(session: AsyncSession, part_id: uuid.UUID, *, lock: bool = False) -> Item:
    item = await (stock.lock(session, part_id) if lock else repository.get(session, part_id))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Цієї деталі на складі ще немає")
    return item


async def _low_event(item: Item, lv: Levels) -> None:
    await events.publish("stock.low", stock.low_payload(item, lv))


@router.get("/inventory/stock", response_model=StockPage, tags=["stock"])
async def list_stock(
    _: CanRead,
    session: Session,
    search: Annotated[str | None, Query(max_length=120)] = None,
    low: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StockPage:
    rows, total = await repository.list_page(
        session, search=search, low=low, limit=limit, offset=offset
    )
    return StockPage(
        items=[_item_out(item, lv) for item, lv in rows], total=total, limit=limit, offset=offset
    )


@router.get(
    "/inventory/stock/{part_id}",
    response_model=StockDetail,
    responses={404: NOT_FOUND},
    tags=["stock"],
)
async def get_stock_item(part_id: uuid.UUID, _: CanRead, session: Session) -> StockDetail:
    item = await _item_or_404(session, part_id)
    base = _item_out(item, await stock.levels(session, part_id))
    return StockDetail(
        **base.model_dump(),
        lots=[Lot.model_validate(x) for x in await repository.lots_left(session, part_id)],
        reservations=[
            Reservation.model_validate(x)
            for x in await repository.active_reservations(session, part_id)
        ],
        movements=[
            Movement.model_validate(x) for x in await repository.movements(session, part_id)
        ],
    )


@router.patch(
    "/inventory/stock/{part_id}",
    response_model=StockItem,
    responses={404: NOT_FOUND},
    tags=["stock"],
)
async def update_stock_item(
    part_id: uuid.UUID, data: StockItemUpdate, _: CanWrite, session: Session
) -> StockItem:
    item = await _item_or_404(session, part_id, lock=True)
    was_low = stock.is_low(item, await stock.levels(session, part_id))
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await session.flush()
    lv = await stock.levels(session, part_id)
    await session.commit()

    # Підняли мінімум вище за вільний залишок — це теж привід замовити.
    if stock.is_low(item, lv) and not was_low:
        await _low_event(item, lv)
    return _item_out(item, lv)


@router.post(
    "/inventory/stock/{part_id}/count",
    response_model=StockItem,
    responses={404: NOT_FOUND},
    tags=["stock"],
)
async def count_stock(
    part_id: uuid.UUID, data: CountCreate, _: CanWrite, session: Session
) -> StockItem:
    item = await _item_or_404(session, part_id, lock=True)
    before = await stock.levels(session, part_id)
    diff = data.counted - before.on_hand
    now = datetime.now(UTC)

    if diff > 0:
        # Надлишок — нова партія за ціною останнього приходу.
        await stock.receive(
            session,
            item,
            qty=diff,
            unit_cost=await stock.last_cost(session, part_id),
            source="count",
            note=data.note or "Надлишок при інвентаризації",
            now=now,
        )
    elif diff < 0:
        await stock.write_off(
            session,
            item,
            qty=-diff,
            kind="count_minus",
            now=now,
            note=data.note or "Нестача при інвентаризації",
        )

    lv = await stock.levels(session, part_id)
    await session.commit()
    if stock.is_low(item, lv) and not stock.is_low(item, before):
        await _low_event(item, lv)
    return _item_out(item, lv)


@router.post(
    "/inventory/receipts",
    response_model=StockItem,
    status_code=status.HTTP_201_CREATED,
    tags=["receipts"],
)
async def receive(
    data: ReceiptCreate, _: CanWrite, session: Session, catalog: Catalog, request: Request
) -> StockItem:
    if data.qty <= 0:
        raise HTTPException(422, detail="Кількість приходу має бути більшою за нуль")

    try:
        part = await catalog.part(data.part_id, dict(request.headers))
    except PartNotFound as exc:
        raise HTTPException(422, detail="Такої деталі немає в каталозі") from exc
    except CatalogForbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Бракує права catalog.read") from exc
    except CatalogUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не вдалося перевірити деталь: блок «Послуги та прайс» недоступний.",
        ) from exc

    now = datetime.now(UTC)
    await repository.upsert_item(
        session,
        part_id=part.id,
        sku=part.sku,
        brand=part.brand,
        name=part.name,
        unit=part.unit,
        synced_at=now,
    )
    item = await _item_or_404(session, part.id, lock=True)
    await stock.receive(
        session,
        item,
        qty=data.qty,
        unit_cost=data.unit_cost,
        source="receipt",
        note=data.note,
        now=now,
    )
    lv = await stock.levels(session, part.id)
    await session.commit()

    await events.publish(
        "stock.received", stock.received_payload(item, lv, data.qty, data.unit_cost)
    )
    return _item_out(item, lv)


@router.get("/health", tags=["health"])
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
