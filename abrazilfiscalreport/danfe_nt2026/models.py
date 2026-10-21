from __future__ import annotations

from typing import NamedTuple


class LabeledValue(NamedTuple):
    label: str
    value: str


class ProductInfo(NamedTuple):
    code: str
    description: str
    cst_cfop: list[LabeledValue]
    qty_unit: str
    unit_price: str
    total_price: str
    tax_bases: list[LabeledValue]
    # Rates and values come in the two columns of the reference layout of
    # NT 2026.010, read line by line as ICMS / CBS, IBS UF / IPI, IBS MUN / IS.
    tax_rates: tuple[list[LabeledValue], list[LabeledValue]]
    tax_values: tuple[list[LabeledValue], list[LabeledValue]]


class BaseFieldInfo(NamedTuple):
    w: float
    description: str
    content: str
    type: str = ""
