from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from numbers import Number
from typing import Optional, Union


class TaxConfiguration(Enum):
    STANDARD_ICMS_IPI = "Standard ICMS and IPI"
    ICMS_ST = "ICMS ST only"
    WITHOUT_IPI = "Without IPI fields"


class InvoiceDisplay(Enum):
    DUPLICATES_ONLY = "Duplicatas Only"
    FULL_DETAILS = "Full Details"


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


class FontSize(Enum):
    # Os valores a seguir são multiplicadores que ajustam o tamanho da fonte da DANFE.
    SMALL = 1.0
    BIG = 1.35


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
class ProductDescriptionConfig:
    display_branch: bool = False
    display_anp: bool = False
    display_anvisa: bool = False
    branch_info_prefix: str = ""
    display_additional_info: bool = True


@dataclass
class FooterStamp:
    logo: Optional[Union[str, BytesIO, bytes]] = None
    text: str = ""
    height: Number = 5
    logo_max_width: Number = 20
    spacing: Number = 1


@dataclass
class DanfeConfig:
    logo: Union[str, BytesIO, bytes] = None
    margins: Margins = field(default_factory=Margins)
    receipt_pos: ReceiptPosition = ReceiptPosition.TOP
    decimal_config: DecimalConfig = field(default_factory=DecimalConfig)
    tax_configuration: TaxConfiguration = TaxConfiguration.STANDARD_ICMS_IPI
    invoice_display: InvoiceDisplay = InvoiceDisplay.FULL_DETAILS
    font_type: FontType = FontType.HELVETICA
    custom_font: Optional[CustomFont] = None
    font_size: FontSize = FontSize.SMALL
    display_pis_cofins: bool = False
    watermark_cancelled: bool = False
    infcpl_semicolon_newline: bool = False
    forced_orientation: ForcedOrientation = ForcedOrientation.AUTO
    product_description_config: ProductDescriptionConfig = field(
        default_factory=ProductDescriptionConfig
    )
    footer_stamp: FooterStamp = field(default_factory=FooterStamp)
