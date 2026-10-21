"""
DANFE (NF-e modelo 55) no leiaute da NT 2026.010 (Reforma Tributária: IBS/CBS/IS).

Código trazido do upstream Engenere/BrazilFiscalReport (``brazilfiscalreport.danfe``,
LGPL-3.0) e adaptado a este fork: fica num pacote próprio, com cópias isoladas dos
módulos auxiliares, para NÃO alterar o DANFE (``abrazilfiscalreport.danfe``) nem os
demais documentos. A fonte Helvetica/Arial (``FontType.HELVETICA``) é acrescentada
aqui. Use ``uses_nt_2026_010(xml)`` para decidir o leiaute pela data de emissão.
"""

from .config import (
    CustomFont,
    DanfeConfig,
    DecimalConfig,
    FontSize,
    FontType,
    FooterStamp,
    ForcedOrientation,
    InvoiceDisplay,
    Margins,
    ProductDescriptionConfig,
    ReceiptPosition,
    TaxConfiguration,
)
from .danfe_nt_2026_010 import DanfeNt2026010
from .layout import NT_2026_010_START, get_issue_datetime, uses_nt_2026_010

__all__ = [
    "CustomFont",
    "DanfeConfig",
    "DanfeNt2026010",
    "DecimalConfig",
    "FontSize",
    "FontType",
    "FooterStamp",
    "ForcedOrientation",
    "InvoiceDisplay",
    "Margins",
    "NT_2026_010_START",
    "ProductDescriptionConfig",
    "ReceiptPosition",
    "TaxConfiguration",
    "get_issue_datetime",
    "uses_nt_2026_010",
]
