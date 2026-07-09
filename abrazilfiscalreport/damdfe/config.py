from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from numbers import Number
from typing import Optional, Union


class FontType(Enum):
    COURIER = "Courier"
    TIMES = "Times"
    HELVETICA = "Helvetica"


@dataclass
class CustomFont:
    """Fonte TTF personalizada. Informe o nome e os caminhos dos arquivos."""

    name: str
    regular: str  # caminho para o .ttf regular
    bold: str = ""  # caminho para o .ttf bold; usa regular se vazio


class ModalType(Enum):
    RODOVIARIO = "RODOVIÁRIO"
    AEREO = "AÉREO"
    AQUAVIARIO = "AQUAVIÁRIO"
    FERROVIARIO = "FERROVIÁRIO"


class EmissionType(Enum):
    NORMAL = "NORMAL"
    CONTINGENCIA = "CONTINGÊNCIA"


@dataclass
class Margins:
    top: Number = 5
    right: Number = 5
    bottom: Number = 5
    left: Number = 5


@dataclass
class DecimalConfig:
    price_precision: int = 4
    quantity_precision: int = 4


@dataclass
class FooterStamp:
    logo: Union[str, BytesIO, bytes] = None
    text: str = ""
    height: Number = 5
    logo_max_width: Number = 20
    spacing: Number = 1


@dataclass
class DamdfeConfig:
    logo: Union[str, BytesIO, bytes] = None
    margins: Margins = field(default_factory=Margins)
    decimal_config: DecimalConfig = field(default_factory=DecimalConfig)
    font_type: FontType = FontType.HELVETICA
    custom_font: Optional[CustomFont] = None
    display_origem_destino_prestacao: bool = False
    footer_stamp: FooterStamp = field(default_factory=FooterStamp)
