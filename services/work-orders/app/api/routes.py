import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, repository
from app.api.auth import Principal, require
from app.db import get_session
from app.models import EDITABLE_STATUSES
from app.models import Line as LineModel
from app.models import Order as OrderModel
from app.peers import (
    BLOCK_TITLE,
    CatalogItem,
    PeerForbidden,
    PeerNotFound,
    Peers,
    PeerUnavailable,
)
from app.pricing import line_amount, totals
from app.schemas import (
    Error,
    Line,
    LineCreate,
    LineUpdate,
    Order,
    OrderCreate,
    OrderPage,
    OrderSummary,
    OrderUpdate,
    Status,
    StatusChange,
    Totals,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]
CanRead = Annotated[Principal, Depends(require("work_orders.read"))]
CanWrite = Annotated[Principal, Depends(require("work_orders.write"))]

NOT_FOUND = {"model": Error, "description": "Не знайдено"}
CONFLICT = {"model": Error, "description": "Конфлікт"}

TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"in_progress", "cancelled"}),
    "in_progress": frozenset({"done", "cancelled"}),
    "done": frozenset({"closed", "in_progress"}),
    "closed": frozenset(),
    "cancelled": frozenset(),
}

STATUS_LABEL = {
    "open": "прийнято",
    "in_progress": "в роботі",
    "done": "роботи завершено",
    "closed": "закрито",
    "cancelled": "скасовано",
}

PERMISSION = {"customers": "customers.read", "vehicles": "vehicles.read", "catalog": "catalog.read"}


def get_peers(request: Request) -> Peers:
    peers: Peers = request.app.state.peers
    return peers


PeersDep = Annotated[Peers, Depends(get_peers)]


def _peer_error(exc: PeerNotFound, what: str) -> HTTPException:
    if isinstance(exc, PeerUnavailable):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Блок «{BLOCK_TITLE[exc.block]}» недоступний. Спробуйте за хвилину.",
        )
    if isinstance(exc, PeerForbidden):
        return HTTPException(
            status.HTTP_403_FORBIDDEN, detail=f"Бракує права {PERMISSION[exc.block]}"
        )
    return HTTPException(422, detail=f"Такого {what} не існує")


def _out(order: OrderModel) -> Order:
    t = totals(order)
    return Order(
        id=order.id,
        number=order.number,
        status=order.status,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        vehicle_id=order.vehicle_id,
        vehicle_label=order.vehicle_label,
        total=t.total,
        opened_at=order.opened_at,
        updated_at=order.updated_at,
        appointment_id=order.appointment_id,
        complaint=order.complaint,
        mileage_km=order.mileage_km,
        notes=order.notes,
        done_at=order.done_at,
        closed_at=order.closed_at,
        lines=[
            Line(
                id=x.id,
                kind=x.kind,
                catalog_id=x.catalog_id,
                code=x.code,
                name=x.name,
                qty=x.qty,
                unit=x.unit,
                unit_price=x.unit_price,
                amount=line_amount(x),
            )
            for x in order.lines
        ],
        totals=Totals(
            services=t.services,
            parts=t.parts,
            subtotal=t.subtotal,
            discount_percent=t.discount_percent,
            discount=t.discount,
            total=t.total,
        ),
    )


def _reservation_event(order: OrderModel, line: LineModel) -> dict[str, str]:
    """
    Резерв рядка під наряд. Та сама подія — і на додавання, і на зміну
    кількості: inventory тримає один резерв на рядок і бере новіший.
    Назва й одиниця — щоб склад міг завести картку деталі, якої ще не бачив.
    """
    return {
        "order_id": str(order.id),
        "order_number": order.number,
        "line_id": str(line.id),
        "part_id": str(line.catalog_id),
        "code": line.code,
        "name": line.name,
        "unit": line.unit,
        "qty": f"{line.qty:.3f}",
    }


def _event(order: OrderModel) -> dict[str, object]:
    t = totals(order)
    return {
        "id": str(order.id),
        "number": order.number,
        "status": order.status,
        "customer_id": str(order.customer_id),
        "vehicle_id": str(order.vehicle_id),
        "appointment_id": str(order.appointment_id) if order.appointment_id else None,
        "total": f"{t.total:.2f}",
    }


async def _order_or_404(session: AsyncSession, order_id: uuid.UUID) -> OrderModel:
    order = await repository.get(session, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Наряд не знайдено")
    return order


def _ensure_editable(order: OrderModel) -> None:
    if order.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Наряд {order.number} — {STATUS_LABEL[order.status]}, змінювати його не можна",
        )


# ── Наряди ──────────────────────────────────────────────────────────────────


@router.get("/work-orders", response_model=OrderPage, tags=["orders"])
async def list_orders(
    _: CanRead,
    session: Session,
    search: Annotated[str | None, Query(max_length=120)] = None,
    status_: Annotated[Status | None, Query(alias="status")] = None,
    customer_id: Annotated[uuid.UUID | None, Query()] = None,
    vehicle_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrderPage:
    items, total = await repository.list_page(
        session,
        search=search,
        status=status_,
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        limit=limit,
        offset=offset,
    )
    return OrderPage(
        items=[OrderSummary.model_validate(_out(o).model_dump()) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/work-orders",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    tags=["orders"],
)
async def open_order(
    data: OrderCreate, _: CanWrite, session: Session, peers: PeersDep, request: Request
) -> Order:
    headers = dict(request.headers)
    try:
        customer = await peers.customer(data.customer_id, headers)
    except PeerNotFound as exc:
        raise _peer_error(exc, "клієнта") from exc
    try:
        vehicle = await peers.vehicle(data.vehicle_id, headers)
    except PeerNotFound as exc:
        raise _peer_error(exc, "автомобіля") from exc

    if vehicle.customer_id != customer.id:
        raise HTTPException(422, detail="Цей автомобіль належить іншому клієнту")

    order = await repository.create(session, data, customer, vehicle)
    await session.commit()
    order = await repository.reload(session, order)

    await events.publish("order.created", _event(order))
    return _out(order)


@router.get(
    "/work-orders/{order_id}", response_model=Order, responses={404: NOT_FOUND}, tags=["orders"]
)
async def get_order(order_id: uuid.UUID, _: CanRead, session: Session) -> Order:
    return _out(await _order_or_404(session, order_id))


@router.patch(
    "/work-orders/{order_id}",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["orders"],
)
async def update_order(
    order_id: uuid.UUID, data: OrderUpdate, _: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id)
    # Примітку можна дописати й до виданого авто; скаргу й пробіг — лише до закриття.
    fields = data.model_dump(exclude_unset=True)
    if fields.keys() - {"notes"} or order.status == "cancelled":
        _ensure_editable(order)
    for field, value in fields.items():
        setattr(order, field, value)
    await session.commit()
    return _out(await repository.reload(session, order))


@router.post(
    "/work-orders/{order_id}/status",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["orders"],
)
async def change_status(
    order_id: uuid.UUID, data: StatusChange, _: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id)

    if data.status not in TRANSITIONS[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Наряд {STATUS_LABEL[order.status]} — не можна перевести в "
            f"«{STATUS_LABEL[data.status]}»",
        )
    if data.status == "done" and not order.lines:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="У наряді немає жодної роботи чи запчастини. "
            "Порожній наряд можна лише скасувати.",
        )

    now = datetime.now(UTC)
    order.status = data.status
    if data.status == "done":
        order.done_at = now
    elif data.status == "in_progress":
        order.done_at = None  # повернули в роботу після «завершено»
    elif data.status == "closed":
        order.closed_at = now
    await session.commit()
    order = await repository.reload(session, order)

    event = {
        "in_progress": "order.started",
        "done": "order.completed",
        "closed": "order.closed",
        "cancelled": "order.cancelled",
    }[data.status]
    await events.publish(event, _event(order))
    return _out(order)


# ── Рядки ───────────────────────────────────────────────────────────────────


@router.post(
    "/work-orders/{order_id}/lines",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["lines"],
)
async def add_line(
    order_id: uuid.UUID,
    data: LineCreate,
    _: CanWrite,
    session: Session,
    peers: PeersDep,
    request: Request,
) -> Order:
    order = await _order_or_404(session, order_id)
    _ensure_editable(order)

    what = "роботи" if data.kind == "service" else "запчастини"
    try:
        fetch = peers.service if data.kind == "service" else peers.part
        item: CatalogItem = await fetch(data.catalog_id, dict(request.headers))
    except PeerNotFound as exc:
        raise _peer_error(exc, f"{what} в каталозі") from exc

    if item.archived:
        raise HTTPException(
            422, detail=f"«{item.name}» в архіві прайсу — оберіть актуальну позицію"
        )
    if item.price is None:
        raise HTTPException(
            422,
            detail=f"Ціна «{item.name}» невідома: задайте вартість нормо-години в прайсі",
        )

    line = await repository.add_line(session, order, data.kind, item, data.qty)
    await session.commit()
    order = await repository.reload(session, order)

    if data.kind == "part":
        # inventory резервує деталь під наряд.
        await events.publish("parts.reserved", _reservation_event(order, line))
    return _out(order)


async def _line_or_404(order: OrderModel, line_id: uuid.UUID):  # type: ignore[no-untyped-def]
    for line in order.lines:
        if line.id == line_id:
            return line
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Рядок не знайдено")


@router.patch(
    "/work-orders/{order_id}/lines/{line_id}",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["lines"],
)
async def update_line(
    order_id: uuid.UUID, line_id: uuid.UUID, data: LineUpdate, _: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id)
    _ensure_editable(order)
    line = await _line_or_404(order, line_id)
    line.qty = data.qty
    await session.commit()
    order = await repository.reload(session, order)

    if line.kind == "part":
        # Інакше склад тримав би резерв на стару кількість.
        await events.publish("parts.reserved", _reservation_event(order, line))
    return _out(order)


@router.delete(
    "/work-orders/{order_id}/lines/{line_id}",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["lines"],
)
async def remove_line(
    order_id: uuid.UUID, line_id: uuid.UUID, _: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id)
    _ensure_editable(order)
    line = await _line_or_404(order, line_id)
    order.lines.remove(line)
    await session.commit()
    order = await repository.reload(session, order)

    if line.kind == "part":
        await events.publish(
            "parts.released",
            {"order_id": str(order.id), "line_id": str(line.id), "part_id": str(line.catalog_id)},
        )
    return _out(order)


@router.get("/health", tags=["health"])
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
