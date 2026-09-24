import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, repository
from app.api.auth import Principal, require
from app.db import get_session
from app.schemas import Customer, CustomerCreate, CustomerPage, CustomerUpdate, Error

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]
CanRead = Annotated[Principal, Depends(require("customers.read"))]
CanWrite = Annotated[Principal, Depends(require("customers.write"))]

NOT_FOUND = {"model": Error, "description": "Клієнта не знайдено"}
CONFLICT = {"model": Error, "description": "Телефон зайнятий"}


@router.get("/customers", response_model=CustomerPage, tags=["customers"])
async def list_customers(
    _: CanRead,
    session: Session,
    search: Annotated[str | None, Query(max_length=120)] = None,
    type: Annotated[Literal["individual", "company"] | None, Query()] = None,
    archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CustomerPage:
    items, total = await repository.list_page(
        session, search=search, type_=type, archived=archived, limit=limit, offset=offset
    )
    return CustomerPage(
        items=[Customer.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/customers",
    response_model=Customer,
    status_code=status.HTTP_201_CREATED,
    responses={409: CONFLICT},
    tags=["customers"],
)
async def create_customer(data: CustomerCreate, _: CanWrite, session: Session) -> Customer:
    if await repository.get_by_phone(session, data.phone):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Клієнт із телефоном {data.phone} уже існує",
        )

    customer = await repository.create(session, data)
    await session.commit()

    await events.publish(
        "customer.created",
        {"id": str(customer.id), "name": customer.name, "phone": customer.phone},
    )
    return Customer.model_validate(customer)


@router.get(
    "/customers/{customer_id}",
    response_model=Customer,
    responses={404: NOT_FOUND},
    tags=["customers"],
)
async def get_customer(customer_id: uuid.UUID, _: CanRead, session: Session) -> Customer:
    customer = await repository.get(session, customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Клієнта не знайдено")
    return Customer.model_validate(customer)


@router.patch(
    "/customers/{customer_id}",
    response_model=Customer,
    responses={404: NOT_FOUND, 409: CONFLICT},
    tags=["customers"],
)
async def update_customer(
    customer_id: uuid.UUID, data: CustomerUpdate, _: CanWrite, session: Session
) -> Customer:
    customer = await repository.get(session, customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Клієнта не знайдено")

    if data.phone and data.phone != customer.phone:
        taken = await repository.get_by_phone(session, data.phone)
        if taken is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Телефон {data.phone} належить іншому клієнту",
            )

    customer = await repository.update(session, customer, data)
    await session.commit()

    # Копію імені й телефону тримають vehicles і work-orders — їм треба знати.
    await events.publish(
        "customer.updated",
        {"id": str(customer.id), "name": customer.name, "phone": customer.phone},
    )
    return Customer.model_validate(customer)


@router.post(
    "/customers/{customer_id}/archive",
    response_model=Customer,
    responses={404: NOT_FOUND},
    tags=["customers"],
)
async def archive_customer(customer_id: uuid.UUID, _: CanWrite, session: Session) -> Customer:
    customer = await repository.get(session, customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Клієнта не знайдено")

    customer = await repository.archive(session, customer)
    await session.commit()

    await events.publish("customer.archived", {"id": str(customer.id)})
    return Customer.model_validate(customer)


@router.get("/health", tags=["health"])
async def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
