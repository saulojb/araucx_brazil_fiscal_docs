from typing import NamedTuple


class ProductInfo(NamedTuple):
    code: str
    description: str
    ncm_sh: str
    cst: str
    cfop: str
    unid: str
    qty: str
    unit_price: str
    total_price: str
    bs_icms: str
    icms_value: str
    ipi_value: str
    icms_rate: str
    ipi_rate: str


class BaseFieldInfo(NamedTuple):
    w: float
    description: str
    content: str
    type: str = ""
