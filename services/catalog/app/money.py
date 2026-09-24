"""
Гроші й нормо-години.

Скрізь Decimal, ніде float: 0.1 + 0.2 у float — не 0.3, а в касі копійка має
сходитись. Назовні — рядок із рівно двома знаками («850.00»), бо JSON-число
будь-який клієнт може прочитати у float і округлити по-своєму.

Приймається й людський ввід: «850», «850,5» — кома як у бухгалтерії.
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema

CENT = Decimal("0.01")

_MONEY_INPUT = re.compile(r"^\d{1,9}([.,]\d{1,2})?$")
_HOURS_INPUT = re.compile(r"^\d{1,3}([.,]\d{1,2})?$")


def quantize(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _parse(pattern: re.Pattern[str], message: str):  # type: ignore[no-untyped-def]
    def parse(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return quantize(value)
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str) or not pattern.match(value.strip()):
            raise ValueError(message)
        return quantize(Decimal(value.strip().replace(",", ".")))

    return parse


def format_2(value: Decimal) -> str:
    return f"{quantize(value):.2f}"


Money = Annotated[
    Decimal,
    BeforeValidator(_parse(_MONEY_INPUT, "Сума: до 9 цифр і до 2 знаків після коми")),
    PlainSerializer(format_2, return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^\d{1,9}\.\d{2}$", "examples": ["850.00"]}),
]

Hours = Annotated[
    Decimal,
    BeforeValidator(_parse(_HOURS_INPUT, "Нормо-години: до 3 цифр і до 2 знаків після коми")),
    PlainSerializer(format_2, return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^\d{1,3}\.\d{2}$", "examples": ["1.50"]}),
]
