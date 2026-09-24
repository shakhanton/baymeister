"""
Суми наряду. Рахуються при читанні з рядків, у базі не зберігаються —
неможливо, щоб «разом» розійшлося з рядками.

Порядок: сума рядка = кількість × ціна, до копійки; знижка — від суми всіх
рядків, до копійки; до сплати = сума − знижка. Округлення — половина вгору.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.models import Line, Order
from app.money import quantize

HUNDRED = Decimal(100)


def line_amount(line: Line) -> Decimal:
    return quantize(line.qty * line.unit_price)


@dataclass(frozen=True)
class OrderTotals:
    services: Decimal
    parts: Decimal
    subtotal: Decimal
    discount_percent: Decimal
    discount: Decimal
    total: Decimal


def totals(order: Order) -> OrderTotals:
    services = sum((line_amount(x) for x in order.lines if x.kind == "service"), Decimal(0))
    parts = sum((line_amount(x) for x in order.lines if x.kind == "part"), Decimal(0))
    subtotal = services + parts
    discount = quantize(subtotal * order.discount_percent / HUNDRED)
    return OrderTotals(
        services=quantize(services),
        parts=quantize(parts),
        subtotal=quantize(subtotal),
        discount_percent=order.discount_percent,
        discount=discount,
        total=quantize(subtotal - discount),
    )
