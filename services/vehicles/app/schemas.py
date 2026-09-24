"""Pydantic-схеми. Вони ж джерело OpenAPI, який має збігатись із contracts/vehicles.yaml."""

import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

# Кириличні літери, які на українських номерах пишуться латиницею. Оператор
# набирає як бачить — «АА1234ВС» кирилицею, — а база мусить бачити один номер.
_CYRILLIC_TWINS = str.maketrans("АВЕІКМНОРСТХ", "ABEIKMHOPCTX")
_PLATE_JUNK = re.compile(r"[\s\-]")
_PLATE_OK = re.compile(r"^[A-Z0-9]{2,12}$")


def normalize_plate(value: str) -> str:
    plate = _PLATE_JUNK.sub("", value).upper().translate(_CYRILLIC_TWINS)
    if not _PLATE_OK.match(plate):
        raise ValueError("Держномер: від 2 до 12 латинських літер і цифр")
    return plate


def _normalize_vin(value: str) -> str:
    return value.upper()


Plate = Annotated[
    str, StringConstraints(min_length=2, max_length=16), AfterValidator(normalize_plate)
]
Vin = Annotated[
    str,
    StringConstraints(pattern=r"^[A-HJ-NPR-Za-hj-npr-z0-9]{17}$"),
    AfterValidator(_normalize_vin),
]
Make = Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]
Year = Annotated[int, Field(ge=1900, le=2100)]
Color = Annotated[str, StringConstraints(max_length=40)]
Notes = Annotated[str, StringConstraints(max_length=2000)]
Km = Annotated[int, Field(ge=0, le=9_999_999)]


class VehicleCreate(BaseModel):
    customer_id: uuid.UUID
    vin: Vin | None = None
    plate: Plate
    make: Make
    model: Make
    year: Year | None = None
    color: Color | None = None
    notes: Notes | None = None
    mileage_km: Km | None = None


class VehicleUpdate(BaseModel):
    """Часткове оновлення: передаються тільки поля, що змінюються."""

    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID | None = None
    vin: Vin | None = None
    plate: Plate | None = None
    make: Make | None = None
    model: Make | None = None
    year: Year | None = None
    color: Color | None = None
    notes: Notes | None = None


class Vehicle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    customer_phone: str
    vin: str | None
    plate: str
    make: str
    model: str
    year: int | None
    color: str | None
    notes: str | None
    mileage_km: int | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VehiclePage(BaseModel):
    items: list[Vehicle]
    total: int
    limit: int
    offset: int


class MileageCreate(BaseModel):
    km: Km
    note: Annotated[str, StringConstraints(max_length=200)] | None = None


class MileageReading(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    km: int
    recorded_at: datetime
    note: str | None


class Error(BaseModel):
    detail: str
