# Copyright (C) 2021-2022 Edson Bernardino <edsones at yahoo.com.br>
# Copyright (C) 2024 Engenere - Antônio S. Pereira Neto <neto@engenere.one>

import warnings
import xml.etree.ElementTree as ET
from io import BytesIO

from barcode.codex import Code128
from barcode.writer import SVGWriter

from ..utils import (
    chunks,
    format_cpf_cnpj,
    get_date_utc,
    get_tag_text,
)
from ..xfpdf import xFPDF
from .config import DacceConfig

NFE_NS = "http://www.portalfiscal.inf.br/nfe"
CTE_NS = "http://www.portalfiscal.inf.br/cte"

# Textos que diferem entre NF-e e CT-e (mantidos verbatim para NF-e — não
# alterar, fixtures existentes dependem do texto exato).
_TEXTO_INSTRUCAO = {
    "NFe": (
        "De acordo com as determinações legais vigentes, vimos por "
        "meio desta comunicar-lhe que a Nota Fiscal, "
        "abaixo referenciada, contêm irregularidades que estão "
        "destacadas e suas respectivas correções, solicitamos que "
        "sejam aplicadas essas correções ao executar seus "
        "lançamentos fiscais."
    ),
    "CTe": (
        "De acordo com as determinações legais vigentes, vimos por "
        "meio desta comunicar-lhe que o Conhecimento de Transporte "
        "Eletrônico, abaixo referenciado, contêm irregularidades que "
        "estão destacadas e suas respectivas correções, solicitamos que "
        "sejam aplicadas essas correções ao executar seus "
        "lançamentos fiscais."
    ),
}
_ROTULO_DOCUMENTO = {"NFe": "Nota Fiscal", "CTe": "CT-e"}


def _detect_documento(root):
    """Detecta NFe/CTe pelo namespace do XML raiz (procEventoNFe/procEventoCTe)."""
    if root.tag.startswith(f"{{{CTE_NS}}}"):
        return "CTe"
    return "NFe"


def _build_cte_correction_text(det_event, url):
    """CT-e não tem um campo único xCorrecao (como a NF-e) — a correção vem
    como uma lista de infCorrecao (grupo/campo/valor/item alterado)."""
    correcoes = det_event.findall(f"{url}infCorrecao")
    if not correcoes:
        return ""
    blocos = []
    for correcao in correcoes:
        grupo = get_tag_text(node=correcao, url=url, tag="grupoAlterado")
        campo = get_tag_text(node=correcao, url=url, tag="campoAlterado")
        valor = get_tag_text(node=correcao, url=url, tag="valorAlterado")
        item = get_tag_text(node=correcao, url=url, tag="nroItemAlterado")
        cabecalho = f"Grupo: {grupo} | Campo: {campo}"
        if item:
            cabecalho += f" | Item: {item}"
        blocos.append(f"{cabecalho}\nNovo valor: {valor}")
    return "\n\n".join(blocos)


class DaCCe(xFPDF):
    """
    Document generation:
    DACCe - Documento Auxilar da Carta de Correção Eletronica

    Suporta CC-e de NF-e e de CT-e — o tipo é detectado automaticamente
    pelo namespace do XML (procEventoNFe vs procEventoCTe); a estrutura de
    correção difere entre os dois (NF-e: texto livre xCorrecao; CT-e: lista
    de infCorrecao por grupo/campo alterado).
    """

    def __init__(self, xml=None, emitente=None, image=None, config: DacceConfig = None):
        super().__init__("P", "mm", "A4")
        config = config if config is not None else DacceConfig()
        if config.custom_font:
            self._register_custom_font(config.custom_font)
        else:
            self.default_font = config.font_type.value

        self.footer_stamp = config.footer_stamp
        self._has_footer_stamp = bool(self.footer_stamp.logo or self.footer_stamp.text)
        bottom_margin = 10.0
        if self._has_footer_stamp:
            bottom_margin += self.footer_stamp.height + self.footer_stamp.spacing
        self.set_auto_page_break(auto=False, margin=bottom_margin)
        self.set_title("DACCe")

        root = ET.fromstring(xml)
        documento = _detect_documento(root)
        ns_uri = CTE_NS if documento == "CTe" else NFE_NS
        url = f".//{{{ns_uri}}}"
        key_tag = "chCTe" if documento == "CTe" else "chNFe"
        ret_tag = "retEventoCTe" if documento == "CTe" else "retEvento"

        det_event = root.find(f"{url}detEvento")
        inf_event = root.find(f"{url}infEvento")
        ret_event = root.find(f".//{{{ns_uri}}}{ret_tag}")
        inf_ret_event = ret_event.find(f"{url}infEvento") if ret_event is not None else None

        self.add_page(orientation="P", format="A4")

        # Emitente
        self.rect(x=10, y=10, w=190, h=33, style="")
        self.line(90, 10, 90, 43)

        text = ""
        emitente_nome = ""
        if emitente:
            emitente_nome = emitente["nome"]
            text = (
                f"{emitente['end']}\n"
                f"{emitente['bairro']}\n"
                f"{emitente['cidade']} - {emitente['uf']} {emitente['fone']}"
            )

        if image:
            col_ = 23
            col_end = 28
            w_ = 67
            self.image(image, 12, 12, 12)
        else:
            col_ = 11
            col_end = 24
            w_ = 80

        self.set_xy(x=col_, y=16)
        self.set_font(self.default_font, "B", 10)
        self.multi_cell(w=w_, h=4, text=emitente_nome, border=0, align="C", fill=False)
        self.set_xy(x=11, y=col_end)
        self.set_font(self.default_font, "", 8)
        self.multi_cell(w=80, h=4, text=text, border=0, align="C", fill=False)

        self.set_font(self.default_font, "B", 10)
        self.text(x=118, y=16, text="Representação Gráfica de CC-e")
        # Itálico fica sempre na fonte core (Helvetica): custom_font só
        # registra regular/bold (ver xFPDF._register_custom_font), então
        # "I" quebraria com fonte customizada.
        self.set_font("Helvetica", "I", 9)
        self.text(x=123, y=20, text="(Carta de Correção Eletrônica)")

        self.set_font(self.default_font, "", 8)
        self.text(
            x=92, y=30, text="ID do Evento: {}".format(inf_event.attrib.get("Id")[2:])
        )

        dt, hr = get_date_utc(get_tag_text(node=inf_event, url=url, tag="dhEvento"))

        self.text(x=92, y=35, text=f"Criado em: {dt} {hr}")

        if inf_ret_event is not None:
            dt, hr = get_date_utc(
                get_tag_text(node=inf_ret_event, url=url, tag="dhRegEvento")
            )
            n_prot = get_tag_text(node=inf_ret_event, url=url, tag="nProt")
        else:
            dt, hr, n_prot = "", "", ""

        self.text(
            x=92,
            y=40,
            text=f"Protocolo: {n_prot} - Registrado na SEFAZ em: {dt} {hr}",
        )

        # Destinatário
        self.rect(x=10, y=47, w=190, h=50, style="")
        self.line(10, 83, 200, 83)

        self.set_xy(x=11, y=48)
        text = _TEXTO_INSTRUCAO[documento]

        self.set_font(self.default_font, "", 8)
        self.multi_cell(w=185, h=4, text=text, border=0, align="L", fill=False)

        key = get_tag_text(node=inf_event, url=url, tag=key_tag)

        # Generate a Code128 Barcode as SVG:
        svg_img_bytes = BytesIO()
        Code128(key, writer=SVGWriter()).write(
            svg_img_bytes, options={"write_text": False}
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            self.image(svg_img_bytes, x=127, y=60, w=73, h=8)

        self.set_font(self.default_font, "", 7)
        self.text(x=130, y=78, text=" ".join(chunks(key, 4)))

        self.set_font(self.default_font, "B", 9)

        # CT-e: o protocolo de registro do evento não traz CNPJ do
        # destinatário (campo existe só no retEvento da NF-e) — a linha
        # fica em branco nesse caso.
        if documento == "NFe" and inf_ret_event is not None:
            text = "CNPJ Destinatário:  %s" % format_cpf_cnpj(
                get_tag_text(node=inf_ret_event, url=url, tag="CNPJDest")
            )
            self.text(x=12, y=71, text=text)

        text = (
            f"{_ROTULO_DOCUMENTO[documento]}: {int(key[25:34]):011,}".replace(",", ".")
            + f" - Série: {key[22:25]}"
        )

        self.text(x=12, y=76, text=text)

        self.set_xy(x=11, y=84)
        text = get_tag_text(node=det_event, url=url, tag="xCondUso")
        self.set_font("Helvetica", "I", 7)
        self.multi_cell(w=185, h=3, text=text, border=0, align="L", fill=False)

        # Correções
        self.set_font(self.default_font, "B", 9)
        self.text(x=11, y=103, text="CORREÇÕES A SEREM CONSIDERADAS")

        self.rect(x=10, y=104, w=190, h=170, style="")

        self.set_xy(x=11, y=106)
        if documento == "CTe":
            text = _build_cte_correction_text(det_event, url)
        else:
            text = get_tag_text(node=det_event, url=url, tag="xCorrecao")
        self.multi_cell(w=185, h=4, text=text, border=0, align="L", fill=False)

        self.set_xy(x=11, y=265)
        text = (
            "Este documento é uma representação gráfica da CC-e e "
            "foi impresso apenas para sua informação e não possue validade "
            "fiscal.\nA CC-e deve ser recebida e mantida em arquivo "
            "eletrônico XML e pode ser consultada através dos portais "
            "das SEFAZ."
        )

        self.set_font("Helvetica", "I", 8)
        self.multi_cell(w=185, h=4, text=text, border=0, align="C", fill=False)

        self._draw_footer_stamp()

    def _draw_footer_stamp(self):
        if not self._has_footer_stamp:
            return

        stamp = self.footer_stamp
        y_top = self.h - self.b_margin + stamp.spacing
        logo_box_w = stamp.logo_max_width if stamp.logo else 0
        x_logo = self.w - self.r_margin - logo_box_w

        if stamp.text:
            self.set_font(self.default_font, style="B", size=7)
            text_w = self.get_string_width(stamp.text)
            text_gap = 2 if stamp.logo else 0
            cell_w = text_w + 2 * self.c_margin
            cell_x = x_logo - text_gap - text_w - self.c_margin
            self.set_xy(cell_x, y_top)
            self.cell(cell_w, stamp.height, stamp.text, align="R")

        if stamp.logo:
            self.image(
                stamp.logo,
                x=x_logo,
                y=y_top,
                w=logo_box_w,
                h=stamp.height,
                keep_aspect_ratio=True,
            )
