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
class Margins:
    top: Number = 5
    right: Number = 5
    bottom: Number = 5
    left: Number = 5


class ModalType(Enum):
    RODOVIARIO = "RODOVIÁRIO"
    AEREO = "AÉREO"
    AQUAVIARIO = "AQUAVIÁRIO"
    FERROVIARIO = "FERROVIÁRIO"
    DUTOVIARIO = "DUTOVIÁRIO"
    MULTIMODAL = "MULTIMODAL"


@dataclass
class DecimalConfig:
    price_precision: int = 4
    quantity_precision: int = 4


class ReceiptPosition(Enum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"


class ForcedOrientation(Enum):
    # 0: não força — usa a orientação indicada em ide/tpImp do XML.
    AUTO = 0
    # 1: força retrato, ignorando ide/tpImp.
    PORTRAIT = 1
    # 2: força paisagem, ignorando ide/tpImp.
    LANDSCAPE = 2


@dataclass
class FooterStamp:
    logo: Union[str, BytesIO, bytes] = None
    text: str = ""
    height: Number = 5
    logo_max_width: Number = 20
    spacing: Number = 1


@dataclass
class DacteConfig:
    logo: Union[str, BytesIO, bytes] = None
    margins: Margins = field(default_factory=Margins)
    receipt_pos: ReceiptPosition = ReceiptPosition.TOP
    decimal_config: DecimalConfig = field(default_factory=DecimalConfig)
    font_type: FontType = FontType.HELVETICA
    custom_font: Optional[CustomFont] = None
    watermark_cancelled: bool = False
    display_ibs_cbs: bool = False
    forced_orientation: ForcedOrientation = ForcedOrientation.AUTO
    footer_stamp: FooterStamp = field(default_factory=FooterStamp)

    def __post_init__(self):
        # Aceita também o inteiro (0/1/2) — útil em ambientes como
        # PL/Python; enum puro não compara igual ao int, e passar 1 sem
        # esta coerção cairia silenciosamente no comportamento AUTO.
        if not isinstance(self.forced_orientation, ForcedOrientation):
            self.forced_orientation = ForcedOrientation(self.forced_orientation)
