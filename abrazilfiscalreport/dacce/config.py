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


@dataclass
class FooterStamp:
    logo: Union[str, BytesIO, bytes] = None
    text: str = ""
    height: Number = 5
    logo_max_width: Number = 20
    spacing: Number = 1


@dataclass
class DacceConfig:
    font_type: FontType = FontType.HELVETICA
    custom_font: Optional[CustomFont] = None
    footer_stamp: FooterStamp = field(default_factory=FooterStamp)
