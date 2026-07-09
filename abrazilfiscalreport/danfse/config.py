from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from numbers import Number
from typing import Optional, Union


class FontType(Enum):
    COURIER = "Courier"
    TIMES = "Times"
    # Equivalente métrico da Arial exigida pela NT 008/2026 (fonte core do
    # PDF, dispensa embutir TTF).
    HELVETICA = "Helvetica"


@dataclass
class CustomFont:
    """Fonte TTF personalizada. Informe o nome e os caminhos dos arquivos."""

    name: str
    regular: str  # caminho para o .ttf regular
    bold: str = ""  # caminho para o .ttf bold; usa regular se vazio


@dataclass
class Margins:
    # NT 008/2026, item 2.2.2: margens entre 0,15 e 0,20 cm.
    top: Number = 2
    right: Number = 2
    bottom: Number = 2
    left: Number = 2


@dataclass
class DecimalConfig:
    # Campos monetários/alíquotas do leiaute v2.0 são 1-15V2/1-2V2 (2 casas).
    price_precision: int = 2
    quantity_precision: int = 2


@dataclass
class FooterStamp:
    logo: Union[str, BytesIO, bytes] = None
    text: str = ""
    height: Number = 5
    logo_max_width: Number = 20
    spacing: Number = 1


@dataclass
class DanfseConfig:
    margins: Margins = field(default_factory=Margins)
    decimal_config: DecimalConfig = field(default_factory=DecimalConfig)
    font_type: FontType = FontType.HELVETICA
    watermark_cancelled: bool = False
    # Marca d'água "SUBSTITUÍDA" (NT 008/2026, item 2.5.2).
    watermark_replaced: bool = False
    custom_font: Optional[CustomFont] = None
    # Bloco de canhoto na base do documento (NT 008/2026, item 2.1.13 e
    # Nota 11 — opcional).
    display_canhoto: bool = False
    footer_stamp: FooterStamp = field(default_factory=FooterStamp)
