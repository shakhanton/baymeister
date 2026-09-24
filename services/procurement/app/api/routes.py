import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, repository
from app.api.auth import Principal, require
from app.catalog_client import CatalogClient, CatalogForbidden, CatalogUnavailable, PartNotFound
from app.db import get_session
from app.models import Line as LineModel
from app.models import Need as NeedModel
from app.models import Order as OrderModel
from app.models import Receipt as ReceiptModel
from app.models import ReceiptLine as ReceiptLineModel
from app.models import Supplier as SupplierModel
from app.money import quantize
from app.schemas import (
    Error,
    Line,
    LineCreate,
    LineUpdate,
    Need,
    NeedOrder,
    Order,
    OrderCreate,
    OrderPage,
    OrderRef,
    OrderSummary,
    OrderUpdate,
    Receipt,
    ReceiptCreate,
    Status,
    StatusChange,
    Supplier,
    SupplierCreate,
    SupplierPage,
    SupplierRef,
    SupplierUpdate,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]
CanRead = Annotated[Principal, Depends(require("procurement.read"))]
CanWrite = Annotated[Principal, Depends(require("procurement.write"))]

NOT_FOUND = {"model": Error, "description": "Не знайдено"}
CONFLICT = {"model": Error, "description": "Конфлікт"}

TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"ordered", "cancelled"}),
    "ordered": frozenset({"received", "cancelled"}),
    "received": frozenset(),
    "cancelled": frozenset(),
}

STATUS_LABEL = {
    "draft": "чернетка",
    "ordered": "відправлено",
    "received": "отримано",
    "cancelled": "скасовано",
}


def get_catalog(request: Request) -> CatalogClient:
    client: CatalogClient = request.app.state.catalog
    return client


Catalog = Annotated[CatalogClient, Depends(get_catalog)]


# ── Перетворення ───────────────────────────────────────────────────────────


def _amount(line: LineModel) -> Decimal:
    return quantize(line.qty * line.unit_cost)


def _total(order: OrderModel) -> Decimal:
    return sum((_amount(line) for line in order.lines), Decimal(0))


def _supplier_ref(supplier: SupplierModel) -> SupplierRef:
    return SupplierRef(id=supplier.id, name=supplier.name)


def _order_out(order: OrderModel) -> Order:
    return Order(
        id=order.id,
        number=order.number,
        status=_status(order.status),
        auto=order.auto,
        supplier=_supplier_ref(order.supplier),
        note=order.note,
        expected_on=order.expected_on,
        created_at=order.created_at,
        ordered_at=order.ordered_at,
        closed_at=order.closed_at,
        lines=[
            Line(
                id=line.id,
                part_id=line.part_id,
                sku=line.sku,
                brand=line.brand,
                name=line.name,
                unit=line.unit,
                qty=line.qty,
                unit_cost=line.unit_cost,
                amount=_amount(line),
                qty_received=line.qty_received,
            )
            for line in order.lines
        ],
        receipts=[
            Receipt(
                id=r.id,
                invoice_number=r.invoice_number,
                received_at=r.received_at,
                lines=len(r.lines),
                total=sum((quantize(rl.qty * rl.unit_cost) for rl in r.lines), Decimal(0)),
            )
            for r in order.receipts
        ],
        total=_total(order),
    )


def _summary_out(order: OrderModel) -> OrderSummary:
    ordered = sum((line.qty for line in order.lines), Decimal(0))
    received = sum((min(line.qty_received, line.qty) for line in order.lines), Decimal(0))
    return OrderSummary(
        id=order.id,
        number=order.number,
        status=_status(order.status),
        auto=order.auto,
        supplier=_supplier_ref(order.supplier),
        expected_on=order.expected_on,
        created_at=order.created_at,
        lines=len(order.lines),
        total=_total(order),
        received_share=float(received / ordered) if ordered else 0.0,
    )


def _human(qty: Decimal) -> str:
    """10.000 → «10», 2.500 → «2,5» — для повідомлень людині."""
    return f"{qty.normalize():f}".replace(".", ",")


def _status(value: str) -> Status:
    assert value in STATUS_LABEL
    return value  # type: ignore[return-value]


# ── Постачальники ──────────────────────────────────────────────────────────


async def _supplier_or_404(session: AsyncSession, supplier_id: uuid.UUID) -> SupplierModel:
    supplier = await session.get(SupplierModel, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Постачальника не знайдено")
    return supplier


def _name_taken(name: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=f"Постачальник «{name}» уже є")


async def _commit_supplier(session: AsyncSession, name: str) -> None:
    """Перевірка вище ловить звичайний дубль; одночасний — зупиняє унікальний ключ."""
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _name_taken(name) from exc


@router.get("/procurement/suppliers", response_model=SupplierPage, tags=["suppliers"])
async def list_suppliers(
    _: CanRead,
    session: Session,
    search: str | None = None,
    archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SupplierPage:
    items, total = await repository.suppliers(
        session, search=search, archived=archived, limit=limit, offset=offset
    )
    return SupplierPage(items=[Supplier.model_validate(s) for s in items], total=total)


@router.post(
    "/procurement/suppliers",
    response_model=Supplier,
    status_code=status.HTTP_201_CREATED,
    responses={409: CONFLICT},
    tags=["suppliers"],
)
async def create_supplier(data: SupplierCreate, _: CanWrite, session: Session) -> Supplier:
    if await repository.supplier_name_taken(session, data.name):
        raise _name_taken(data.name)
    supplier = SupplierModel(**data.model_dump(), name_key=data.name.casefold(), active=True)
    session.add(supplier)
    await _commit_supplier(session, data.name)
    return Supplier.model_validate(supplier)


@router.get(
    "/procurement/suppliers/{supplier_id}",
    response_model=Supplier,
    responses={404: NOT_FOUND},
    tags=["suppliers"],
)
async def get_supplier(supplier_id: uuid.UUID, _: CanRead, session: Session) -> Supplier:
    return Supplier.model_validate(await _supplier_or_404(session, supplier_id))


@router.patch(
    "/procurement/suppliers/{supplier_id}",
    response_model=Supplier,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["suppliers"],
)
async def update_supplier(
    supplier_id: uuid.UUID, data: SupplierUpdate, _: CanWrite, session: Session
) -> Supplier:
    supplier = await _supplier_or_404(session, supplier_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name") is None:
        changes.pop("name", None)
    if changes.get("active") is None:
        changes.pop("active", None)
    if "name" in changes and await repository.supplier_name_taken(
        session, changes["name"], except_id=supplier.id
    ):
        raise _name_taken(changes["name"])
    for field, value in changes.items():
        setattr(supplier, field, value)
    supplier.name_key = supplier.name.casefold()
    await _commit_supplier(session, supplier.name)
    return Supplier.model_validate(supplier)


# ── Замовлення ─────────────────────────────────────────────────────────────


async def _order_or_404(
    session: AsyncSession, order_id: uuid.UUID, *, lock: bool = False
) -> OrderModel:
    order = await (
        repository.lock_order(session, order_id) if lock else session.get(OrderModel, order_id)
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Замовлення не знайдено")
    return order


async def _active_supplier(session: AsyncSession, supplier_id: uuid.UUID) -> SupplierModel:
    supplier = await session.get(SupplierModel, supplier_id)
    if supplier is None:
        raise HTTPException(422, detail="Такого постачальника немає")
    if not supplier.active:
        raise HTTPException(422, detail=f"Постачальник «{supplier.name}» в архіві")
    return supplier


def _draft_only(order: OrderModel) -> None:
    if order.status != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Замовлення {STATUS_LABEL[order.status]} — рядки змінюються лише в чернетці",
        )


@router.get("/procurement/orders", response_model=OrderPage, tags=["orders"])
async def list_orders(
    _: CanRead,
    session: Session,
    search: str | None = None,
    order_status: Annotated[Status | None, Query(alias="status")] = None,
    supplier_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrderPage:
    items, total = await repository.orders(
        session,
        search=search,
        status=order_status,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    return OrderPage(items=[_summary_out(o) for o in items], total=total)


@router.post(
    "/procurement/orders",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    tags=["orders"],
)
async def create_order(data: OrderCreate, _: CanWrite, session: Session) -> Order:
    supplier = await _active_supplier(session, data.supplier_id)
    now = datetime.now(UTC)
    order = OrderModel(
        number=await repository.next_number(session, now),
        supplier_id=supplier.id,
        supplier=supplier,
        status="draft",
        auto=False,
        note=data.note,
        expected_on=data.expected_on,
        created_at=now,
        lines=[],
        receipts=[],
    )
    session.add(order)
    await session.commit()
    return _order_out(order)


@router.get(
    "/procurement/orders/{order_id}",
    response_model=Order,
    responses={404: NOT_FOUND},
    tags=["orders"],
)
async def get_order(order_id: uuid.UUID, _: CanRead, session: Session) -> Order:
    return _order_out(await _order_or_404(session, order_id))


@router.patch(
    "/procurement/orders/{order_id}",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["orders"],
)
async def update_order(
    order_id: uuid.UUID, data: OrderUpdate, _: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id, lock=True)
    changes = data.model_dump(exclude_unset=True)
    if order.status in ("received", "cancelled"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Замовлення {STATUS_LABEL[order.status]}"
        )
    supplier_id = changes.pop("supplier_id", None)
    if supplier_id is not None and supplier_id != order.supplier_id:
        _draft_only(order)
        supplier = await _active_supplier(session, supplier_id)
        order.supplier_id, order.supplier = supplier.id, supplier
    for field, value in changes.items():
        setattr(order, field, value)
    await session.commit()
    return _order_out(order)


@router.post(
    "/procurement/orders/{order_id}/status",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["orders"],
)
async def change_status(
    order_id: uuid.UUID, data: StatusChange, _: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id, lock=True)
    if data.status not in TRANSITIONS[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Замовлення {STATUS_LABEL[order.status]} — не можна перевести в "
            f"«{STATUS_LABEL[data.status]}»",
        )
    now = datetime.now(UTC)
    if data.status == "ordered":
        if not order.lines:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="У замовленні немає жодного рядка")
        unpriced = [line.name for line in order.lines if line.unit_cost <= 0]
        if unpriced:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"Не вказано ціну: {', '.join(unpriced)}"
            )
        order.ordered_at = now
    elif data.status == "cancelled" and order.receipts:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Частину вже отримано — скасувати не можна. Закрийте з недопоставкою.",
        )
    elif data.status == "received":
        if not order.receipts:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Нічого ще не отримано — якщо поставки не буде, скасуйте замовлення",
            )
    if data.status in ("received", "cancelled"):
        order.closed_at = now
    order.status = data.status
    await session.commit()

    if data.status == "ordered":
        await events.publish(
            "purchase.ordered",
            {
                "id": str(order.id),
                "number": order.number,
                "supplier_id": str(order.supplier_id),
                "supplier": order.supplier.name,
                "total": f"{_total(order):.2f}",
                "expected_on": order.expected_on.isoformat() if order.expected_on else None,
            },
        )
    return _order_out(order)


@router.post(
    "/procurement/orders/{order_id}/lines",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["orders"],
)
async def add_line(
    order_id: uuid.UUID,
    data: LineCreate,
    _: CanWrite,
    session: Session,
    catalog: Catalog,
    request: Request,
) -> Order:
    order = await _order_or_404(session, order_id, lock=True)
    _draft_only(order)
    if data.qty <= 0:
        raise HTTPException(422, detail="Кількість має бути більшою за нуль")
    if any(line.part_id == data.part_id for line in order.lines):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Ця деталь уже є в замовленні — змініть кількість"
        )
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

    order.lines.append(
        LineModel(
            part_id=part.id,
            sku=part.sku,
            brand=part.brand,
            name=part.name,
            unit=part.unit,
            qty=data.qty,
            unit_cost=data.unit_cost,
            qty_received=Decimal(0),
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return _order_out(order)


def _line_or_404(order: OrderModel, line_id: uuid.UUID) -> LineModel:
    line = next((x for x in order.lines if x.id == line_id), None)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Рядка не знайдено")
    return line


@router.patch(
    "/procurement/orders/{order_id}/lines/{line_id}",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["orders"],
)
async def update_line(
    order_id: uuid.UUID, line_id: uuid.UUID, data: LineUpdate, _: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id, lock=True)
    _draft_only(order)
    line = _line_or_404(order, line_id)
    if data.qty is not None:
        if data.qty <= 0:
            raise HTTPException(422, detail="Кількість має бути більшою за нуль")
        line.qty = data.qty
    if data.unit_cost is not None:
        line.unit_cost = data.unit_cost
    await session.commit()
    return _order_out(order)


@router.delete(
    "/procurement/orders/{order_id}/lines/{line_id}",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["orders"],
)
async def delete_line(
    order_id: uuid.UUID, line_id: uuid.UUID, _: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id, lock=True)
    _draft_only(order)
    order.lines.remove(_line_or_404(order, line_id))
    await session.commit()
    return _order_out(order)


@router.post(
    "/procurement/orders/{order_id}/receipts",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["orders"],
)
async def receive(
    order_id: uuid.UUID, data: ReceiptCreate, who: CanWrite, session: Session
) -> Order:
    order = await _order_or_404(session, order_id, lock=True)
    if order.status != "ordered":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Замовлення {STATUS_LABEL[order.status]} — приймати можна лише відправлене",
        )
    ids = [rl.line_id for rl in data.lines]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, detail="Рядок замовлення повторюється в приході")

    now = datetime.now(UTC)
    receipt = ReceiptModel(
        invoice_number=data.invoice_number or None,
        received_at=now,
        received_by=who.user_id,
        lines=[],
    )
    event_lines: list[dict[str, Any]] = []
    for rl in data.lines:
        line = next((x for x in order.lines if x.id == rl.line_id), None)
        if line is None:
            raise HTTPException(422, detail="Такого рядка в замовленні немає")
        if rl.qty <= 0:
            raise HTTPException(422, detail=f"{line.name}: кількість має бути більшою за нуль")
        left = line.qty - line.qty_received
        if rl.qty > left:
            raise HTTPException(
                422,
                detail=f"{line.name}: замовлено {_human(line.qty)}, "
                f"лишилось отримати {_human(left)}",
            )
        cost = rl.unit_cost if rl.unit_cost is not None else line.unit_cost
        receipt_line = ReceiptLineModel(
            id=uuid.uuid4(), line_id=line.id, qty=rl.qty, unit_cost=cost
        )
        receipt.lines.append(receipt_line)
        line.qty_received += rl.qty
        event_lines.append(
            {
                "receipt_line_id": str(receipt_line.id),
                "part_id": str(line.part_id),
                "sku": line.sku,
                "brand": line.brand,
                "name": line.name,
                "unit": line.unit,
                "qty": f"{rl.qty:.3f}",
                "unit_cost": f"{cost:.2f}",
            }
        )
    order.receipts.append(receipt)
    if all(line.qty_received >= line.qty for line in order.lines):
        order.status = "received"
        order.closed_at = now
    await session.commit()

    await events.publish(
        "purchase.received",
        {
            "order_id": str(order.id),
            "number": order.number,
            "supplier_id": str(order.supplier_id),
            "supplier": order.supplier.name,
            "receipt_id": str(receipt.id),
            "invoice_number": receipt.invoice_number,
            "lines": event_lines,
        },
    )
    return _order_out(order)


# ── Потреби ────────────────────────────────────────────────────────────────


async def _need_out(session: AsyncSession, need: NeedModel) -> Need:
    order = await repository.active_order(session, need.part_id)
    last = await repository.last_line(session, need.part_id)
    return Need(
        part_id=need.part_id,
        sku=need.sku,
        brand=need.brand,
        name=need.name,
        unit=need.unit,
        free=need.free,
        min_qty=need.min_qty,
        raised_at=need.raised_at,
        order=OrderRef(
            id=order.id,
            number=order.number,
            status=_status(order.status),
            supplier=_supplier_ref(order.supplier),
        )
        if order is not None
        else None,
        last_supplier=_supplier_ref(last[1]) if last is not None else None,
    )


@router.get("/procurement/needs", response_model=list[Need], tags=["needs"])
async def list_needs(_: CanRead, session: Session) -> list[Need]:
    return [await _need_out(session, need) for need in await repository.open_needs(session)]


async def _open_need_or_404(session: AsyncSession, part_id: uuid.UUID) -> NeedModel:
    need = await session.get(NeedModel, part_id)
    if need is None or not need.open:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Такої потреби немає")
    return need


@router.post(
    "/procurement/needs/{part_id}/order",
    response_model=Order,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["needs"],
)
async def order_need(part_id: uuid.UUID, data: NeedOrder, _: CanWrite, session: Session) -> Order:
    need = await _open_need_or_404(session, part_id)
    existing = await repository.active_order(session, part_id)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Деталь уже в замовленні {existing.number}"
        )
    supplier = await _active_supplier(session, data.supplier_id)
    order = await repository.add_need_to_draft(
        session, need, supplier, datetime.now(UTC), auto=False
    )
    await session.commit()
    return _order_out(order)


@router.delete(
    "/procurement/needs/{part_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: NOT_FOUND},
    tags=["needs"],
)
async def dismiss_need(part_id: uuid.UUID, _: CanWrite, session: Session) -> Response:
    """«Не замовляти»: потреба закривається до наступного сигналу складу."""
    need = await _open_need_or_404(session, part_id)
    need.open = False
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health", tags=["health"])
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
