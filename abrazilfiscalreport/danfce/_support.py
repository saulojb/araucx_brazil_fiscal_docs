"""
Dependências do DANFCe que no upstream (Engenere/BrazilFiscalReport) vivem em
``utils``, ``generate_qrcode`` e ``xfpdf``, mas que este fork ainda não tem (ou
tem em versão anterior).

Ficam aqui, isoladas no pacote ``danfce``, de propósito: assim o módulo novo
funciona sem alterar nenhum comportamento dos demais documentos (DANFE, DACTE,
DAMDFE, DANFSE, DACCE) do fork. Código derivado do upstream (LGPL-3.0).
"""

import re

import qrcode
import qrcode.constants

from ..utils import number_filter
from ..xfpdf import xFPDF as _BaseXFPDF


def to_float(value):
    """Converte valor numérico cru do XML, tolerando ausência/formato inválido."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_cpf_cnpj(doc):
    """CPF/CNPJ formatado, aceitando o CNPJ alfanumérico (a partir de 2026).

    Cópia do upstream; o ``utils.format_cpf_cnpj`` do fork só entende dígitos e
    descartaria as letras do novo CNPJ.
    """
    doc = re.sub(r"[^0-9A-Za-z]", "", doc).upper()
    if doc:
        if len(doc) > 11:
            doc = f"{doc:0>14.14}"
            doc = f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[-2:]}"
        else:
            doc = number_filter(doc)
            doc = f"{doc:0>11.11}"
            doc = f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    return doc


def make_qr_code_image(
    qr_code_data,
    box_size=10,
    border=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
):
    qr = qrcode.QRCode(
        version=1,
        error_correction=error_correction,
        box_size=box_size,
        border=border,
    )
    qr.add_data(qr_code_data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")
    return qr_img.get_image()


def draw_qr_code(
    self,
    qr_code_data,
    y_margin_ret,
    x_offset,
    y_offset,
    box_size=10,
    border=1,
    size=None,
):
    """Desenha o QR Code; ``box_size`` = resolução e ``size`` = lado impresso (mm)."""
    size = box_size if size is None else size
    qr_img_bytes = make_qr_code_image(qr_code_data, box_size=box_size, border=border)
    num_x = y_margin_ret + x_offset
    num_y = self.t_margin + y_offset

    self.image(qr_img_bytes, x=num_x + 1, y=num_y + 1, w=size, h=size)


class xFPDF(_BaseXFPDF):
    """``xFPDF`` do fork + os métodos de layout que o DANFCe usa e o fork não tem."""

    def wrap_text(self, text="", width=0):
        """Quebra o texto nas linhas que cabem em ``width`` com a fonte corrente."""
        if not text or width <= 0:
            return []
        prev_c_margin = self.c_margin
        self.c_margin = 0
        try:
            return self.multi_cell(w=width, text=text, dry_run=True, output="LINES")
        finally:
            self.c_margin = prev_c_margin

    def space_left(self):
        """Altura livre entre o cursor e a margem inferior."""
        return self.h - self.b_margin - self.get_y()

    def ensure_space(self, height):
        """Abre uma página nova se ``height`` não couber no que resta da atual."""
        if height > 0 and self.space_left() < height:
            self.add_page()
            return True
        return False
