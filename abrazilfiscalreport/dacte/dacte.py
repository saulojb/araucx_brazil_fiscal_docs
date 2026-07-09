# Copyright (C) 2024 Engenere - Cristiano Mafra Junior

import re
import textwrap
import warnings
import xml.etree.ElementTree as ET
from io import BytesIO
from xml.etree.ElementTree import Element

from barcode.codex import Code128
from barcode.writer import SVGWriter

from ..generate_qrcode import draw_qr_code
from ..utils import (
    format_cep,
    format_cpf_cnpj,
    format_number,
    format_phone,
    format_xDime,
    get_date_utc,
    get_tag_text,
    limit_text,
)
from ..xfpdf import xFPDF
from .config import DacteConfig, ForcedOrientation, ModalType, ReceiptPosition
from .dacte_conf import (
    RESP_FATURAMENTO,
    TP_CODIGO_MEDIDA,
    TP_CODIGO_MEDIDA_REDUZIDO,
    TP_CTE,
    TP_FERROV_EMITENTE,
    TP_ICMS,
    TP_MANUSEIO,
    TP_MODAL,
    TP_SERVICO,
    TP_TOMADOR,
    TP_TRAFICO,
    URL,
)


def extract_text(node: Element, tag: str) -> str:
    return get_tag_text(node, URL, tag)


class Dacte(xFPDF):
    def __init__(self, xml, config: DacteConfig = None):
        super().__init__(unit="mm", format="A4")
        config = config if config is not None else DacteConfig()
        self.set_margins(
            left=config.margins.left, top=config.margins.top, right=config.margins.right
        )
        self.footer_stamp = config.footer_stamp
        self._has_footer_stamp = bool(self.footer_stamp.logo or self.footer_stamp.text)
        # Reserva espaço para o footer stamp dentro da margem inferior, para
        # a área de conteúdo (eph) encolher sozinha e nunca sobrepor o carimbo.
        bottom_margin = config.margins.bottom
        if self._has_footer_stamp:
            bottom_margin += self.footer_stamp.height + self.footer_stamp.spacing
        self.set_auto_page_break(auto=False, margin=bottom_margin)
        self.set_title("DACTE")
        self.logo_image = config.logo
        self.receipt_pos = config.receipt_pos
        self._base_l_margin = config.margins.left
        # Margem esquerda "efetiva" do conteúdo. Em paisagem com recibo à
        # esquerda ela é deslocada (ver _draw_landscape_receipt) para abrir
        # espaço para a faixa do recibo; várias rotinas de desenho resetam
        # self.l_margin via set_margins(left=...) e precisam usar este valor
        # em vez de config.margins.left para não perder o deslocamento.
        self.content_l_margin = self._base_l_margin
        if config.custom_font:
            self._register_custom_font(config.custom_font)
        else:
            self.default_font = config.font_type.value
        self.price_precision = config.decimal_config.price_precision
        self.quantity_precision = config.decimal_config.quantity_precision
        self.watermark_cancelled = config.watermark_cancelled
        self.display_ibs_cbs = config.display_ibs_cbs
        self.forced_orientation = config.forced_orientation

        root = ET.fromstring(xml)
        self.inf_cte = root.find(f"{URL}infCte")
        self.prot_cte = root.find(f"{URL}protCTe")
        self.emit = root.find(f"{URL}emit")
        self.ide = root.find(f"{URL}ide")
        self.dest = root.find(f"{URL}dest")
        self.exped = root.find(f"{URL}exped")
        self.receb = root.find(f"{URL}receb")
        self.rem = root.find(f"{URL}rem")
        self.outros = root.find(f"{URL}toma4")
        self.inf_prot = root.find(f"{URL}infProt")
        self.inf_cte_supl = root.find(f"{URL}infCTeSupl")
        self.tomador = root.find(f"{URL}toma3") or self.outros
        self.inf_carga = root.find(f"{URL}infCarga")
        self.inf_doc = root.find(f"{URL}infDoc")
        self.v_prest = root.find(f"{URL}vPrest")
        self.inf_modal = root.find(f"{URL}infModal")
        self.imp = root.find(f"{URL}imp")
        self.compl = root.find(f"{URL}compl")
        self.aquav = root.find(f"{URL}aquav")
        self.ferrov = root.find(f"{URL}ferrov")
        self.imp_ibscbs = root.find(f"{URL}IBSCBS")

        self.obs_dacte_list = []
        if self.compl is not None:
            for obs in self.compl:
                self.x_texto = extract_text(obs, "xTexto")
                self.x_texto = " ".join(
                    re.split(r"\s+", self.x_texto.strip(), flags=re.UNICODE)
                )
                self.obs_dacte_list.append(self.x_texto)

        self.page_lines = 0
        self.inf_carga_list = []
        if self.inf_carga is not None:
            for infQ in self.inf_carga:
                self.c_unid = extract_text(infQ, "cUnid")
                self.tp_media = extract_text(infQ, "tpMed")
                self.q_carga = extract_text(infQ, "qCarga")
                self.inf_carga_list.append((self.c_unid, self.tp_media, self.q_carga))

        self.inf_doc_list = []
        if self.inf_doc is not None:
            for chave in self.inf_doc:
                self.chave = extract_text(chave, "chave")
                self.inf_doc_list.append(self.chave)

        self.comp_list = []
        for comp in self.v_prest.findall(f"{URL}Comp"):
            self.xNome = extract_text(comp, "xNome")
            self.vComp = format_number(extract_text(comp, "vComp"), precision=2)
            self.comp_list.append((self.xNome, self.vComp))

        # extract orientation
        if self.forced_orientation == ForcedOrientation.PORTRAIT:
            self.orientation = "P"
        elif self.forced_orientation == ForcedOrientation.LANDSCAPE:
            self.orientation = "L"
        else:
            tpImp = extract_text(self.ide, "tpImp")
            self.orientation = "P" if tpImp == "1" else "L"

        if self.orientation == "L":
            # force receipt position
            # landscape support only left receipt
            self.receipt_pos = ReceiptPosition.LEFT

        self.recibo_text = self._get_receipt_text()
        self.nr_dacte = extract_text(self.ide, "nCT")
        self.serie_cte = extract_text(self.ide, "serie")
        self.key_cte = self.inf_cte.attrib.get("Id")[3:]
        self.tp_cte = TP_CTE[extract_text(self.ide, "tpCTe")]
        self.tp_serv = TP_SERVICO[extract_text(self.ide, "tpServ")]
        self.prot_uso = self._get_usage_protocol()
        self.mod = extract_text(self.ide, "mod")
        self.nct = extract_text(self.ide, "nCT")
        self.toma = TP_TOMADOR[extract_text(self.tomador, "toma")]
        self.cfop = extract_text(self.ide, "CFOP")
        self.nat_op = extract_text(self.ide, "natOp")

        self.add_page(orientation=self.orientation)
        if self.receipt_pos == ReceiptPosition.LEFT:
            self._draw_landscape_receipt()
        else:
            self._draw_receipt()
        self._draw_header()
        self._draw_recipient_sender(config)
        self._draw_service_recipient(config)
        self._draw_service_fee_value()
        self._draw_documents_obs()
        self._draw_specific_data(config)
        self._draw_void_watermark()
        self._draw_footer_stamp()
        self._add_new_page(config)

    def _get_usage_protocol(self):
        dt, hr = get_date_utc(extract_text(self.prot_cte, "dhRecbto"))
        protocol = extract_text(self.prot_cte, "nProt")
        prot_text = f"{protocol} - {dt} {hr}"
        return prot_text

    def _get_receipt_text(self):
        return (
            "DECLARO QUE RECEBI OS VOLUMES DESTE CONHECIMENTO "
            "EM PERFEITO ESTADO PELO QUE DOU POR "
            "CUMPRIDO O PRESENTE CONTRATO DE TRANSPORTE"
        )

    def _draw_void_watermark(self):
        """
        Draw a watermark on the DACTE when the protocol is not available or
        when the environment is homologation.
        """
        is_production_environment = extract_text(self.ide, "tpAmb") == "1"
        is_protocol_available = self.prot_cte is not None

        # Exit early if no watermark is needed
        watermark_text = None
        font_size = 60
        if self.watermark_cancelled:
            if is_production_environment:
                watermark_text = "CANCELADA"
            else:
                watermark_text = "CANCELADA - SEM VALOR FISCAL"
                font_size = 45

        elif not is_production_environment or not is_protocol_available:
            watermark_text = "SEM VALOR FISCAL"

        if watermark_text:
            self.set_font(self.default_font, "B", font_size)

            width = self.get_string_width(watermark_text)
            self.set_text_color(r=220, g=150, b=150)
            height = font_size * 0.25
            page_width = self.w
            page_height = self.h
            x_center = (page_width - width) / 2
            y_center = (page_height + height) / 2
            with self.rotation(55, x_center + (width / 2), y_center - (height / 2)):
                self.text(x_center, y_center, watermark_text)
            self.set_text_color(r=0, g=0, b=0)

    def _draw_dashed_line(self, distance):
        self.set_dash_pattern(dash=0.2, gap=0.8)
        if self.orientation == "P":
            self.line(
                x1=self.l_margin,
                y1=distance,
                x2=self.w - self.r_margin,
                y2=distance,
            )
        else:
            self.line(
                x1=distance,
                y1=self.t_margin,
                x2=distance,
                y2=self.h - self.b_margin,
            )
        self.set_dash_pattern(dash=0, gap=0)

    def _draw_label_value(
        self,
        x,
        y,
        label,
        value,
        label_width=12,
        value_width=34,
        label_size=7,
        value_size=7,
    ):
        self.set_font(self.default_font, "", label_size)
        self.set_xy(x, y)
        self.cell(w=label_width, h=3.2, text=label, align="L", border=0)
        self.set_font(self.default_font, "B", value_size)
        self.set_xy(x + label_width, y)
        self.cell(w=value_width, h=3.2, text=value, align="L", border=0)

    def _draw_receipt(self):
        x_margin = self.l_margin
        y_margin = self.y
        page_width = self.epw
        w_date_field = 40
        line_height = 8
        cell_height = -5

        def draw_vertical_lines(start_y, end_y):
            col_width = page_width / 4
            x_line1 = x_margin + col_width
            x_line2 = x_margin + 2 * col_width
            x_line3 = x_margin + 3 * col_width

            self.line(x1=x_line1, x2=x_line1, y1=start_y, y2=end_y)
            self.line(x1=x_line2, x2=x_line2, y1=start_y, y2=end_y)
            self.line(x1=x_line3, x2=x_line3, y1=start_y, y2=end_y)

            return x_line1, x_line2, x_line3

        self._draw_dashed_line(distance=y_margin + 21)
        self.set_dash_pattern(dash=0, gap=0)

        self.rect(x=x_margin, y=y_margin, w=page_width - 0.5, h=3, style="")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=x_margin, y=y_margin)
        self.cell(
            w=page_width - 2 * x_margin, h=3, text=self.recibo_text, border=0, align="L"
        )

        h_recibo = 17
        self.rect(
            x=x_margin, y=y_margin + 3.5, w=page_width - 0.5, h=h_recibo, style=""
        )

        x_line1, x_line2, x_line3 = draw_vertical_lines(
            y_margin + 3.5, y_margin + h_recibo + 3.5
        )

        y_start = y_margin + 10
        self.line(x1=x_margin, x2=x_line1, y1=y_start + 2, y2=y_start + 2)

        self.set_font(self.default_font, "B", 8)
        self.set_xy(x=x_margin + 1, y=y_start - 2)
        self.cell(w=w_date_field, h=cell_height, text="NOME", border=0, align="L")

        self.set_xy(x=x_margin + 1, y=y_start - 1.5 + line_height)
        self.cell(w=w_date_field, h=cell_height, text="RG", border=0, align="L")

        self.set_xy(x=x_line1 + 7.5, y=y_start + 11)
        self.cell(
            w=w_date_field,
            h=cell_height,
            text="ASSINATURA / CARIMBO",
            border=0,
            align="L",
        )

        self.set_xy(x=x_line2 + 2, y=y_start - 2)
        self.cell(
            w=w_date_field, h=cell_height, text="CHEGADA DATA/HORA", border=0, align="L"
        )

        self.set_xy(x=x_line2 + 2, y=y_start - 2 + line_height)
        self.cell(
            w=w_date_field, h=cell_height, text="SAÍDA DATA/HORA", border=0, align="L"
        )

        self.set_xy(x=x_line3 + 5, y=y_start - 1)
        self.set_font(self.default_font, "B", 12)
        self.cell(w=w_date_field, h=cell_height, text="CT-E", border=0, align="C")

        self.set_xy(x=x_line3 + 5, y=y_start + 4)
        self.set_font(self.default_font, "", 7)
        self.cell(
            w=w_date_field, h=cell_height, text="NRO. DOCUMENTO", border=0, align="L"
        )

        self.set_xy(x=x_line3 + 5, y=y_start + line_height)
        self.cell(w=w_date_field, h=cell_height, text="SÉRIE", border=0, align="L")

        self.set_xy(x=x_line3 + 35, y=y_start + 4)
        self.set_font(self.default_font, "B", 7)
        self.cell(
            w=w_date_field, h=cell_height, text=self.nr_dacte, border=0, align="L"
        )

        self.set_xy(x=x_line3 + 38, y=y_start  + line_height)
        self.cell(
            w=w_date_field, h=cell_height, text=self.serie_cte, border=0, align="L"
        )

    def _draw_landscape_receipt(self):
        """
        Recibo em paisagem: faixa estreita rotacionada na borda esquerda
        (mesmo padrão do DANFE), com a linha pontilhada de corte na borda
        direita da faixa. desloca self.l_margin para depois da faixa, então
        todo o restante do documento (cabeçalho, tabelas etc.) é desenhado
        automaticamente deslocado, já que essas rotinas usam self.l_margin.
        """
        h_recibo = 17
        base_margin = self._base_l_margin
        w_top_box = 30  # altura (ao longo da página) da caixa CT-E/Nº/SÉRIE

        self.set_dash_pattern(dash=0, gap=0)
        self.rect(x=base_margin, y=self.t_margin, w=h_recibo, h=self.eph, style="")
        self.line(
            x1=base_margin,
            y1=self.t_margin + w_top_box,
            x2=base_margin + h_recibo,
            y2=self.t_margin + w_top_box,
        )

        self.set_font(self.default_font, "B", 8)
        text = f"CT-E\n\nNº {self.nr_dacte}\n\nSÉRIE {self.serie_cte}"
        self.text_box(
            text=text,
            text_align="C",
            w=h_recibo,
            h=w_top_box,
            h_line=3,
            x=base_margin,
            y=self.t_margin,
        )

        # divide a faixa restante em 2 subcolunas (declaração | campos)
        x_col2 = base_margin + h_recibo / 2
        self.line(
            x1=x_col2,
            y1=self.t_margin + w_top_box,
            x2=x_col2,
            y2=self.t_margin + self.eph,
        )

        self.set_font(self.default_font, "", 5)
        h_text = 2
        self.set_xy(x=base_margin + 1, y=self.eph + h_text)
        with self.rotation(90):
            self.multi_cell(
                w=self.eph - w_top_box,
                h=h_text,
                text=self.recibo_text,
                border=0,
                align="L",
            )

        self.set_xy(x=x_col2 + 0.5, y=self.eph + h_text)
        with self.rotation(90):
            for label in (
                "NOME",
                "RG",
                "ASSINATURA / CARIMBO",
                "CHEGADA DATA/HORA",
                "SAÍDA DATA/HORA",
            ):
                self.cell(w=25, h=h_text, text=label, new_x="RIGHT", align="L")

        self._draw_dashed_line(distance=base_margin + h_recibo + 1)
        self.content_l_margin = base_margin + h_recibo + 2
        self.set_left_margin(self.content_l_margin)
        self.set_xy(x=self.l_margin, y=self.t_margin)

    def _draw_header(self):
        x_margin = self.l_margin
        y_margin = self.y
        # Em paisagem o cabeçalho já começa colado no topo útil da página
        # (self.t_margin, mesmo ponto onde a faixa do recibo começa) — não
        # precisa do respiro de 4mm pensado para quando o recibo ficava
        # acima do cabeçalho, em retrato.
        section_start_y = y_margin + (0 if self.orientation == "L" else 4)
        qr_section_y = section_start_y  # y inicial da coluna — usado para o frame do QR
        is_landscape = self.orientation == "L"
        # Em paisagem o cabeçalho usa a mesma grade de 3 colunas iguais do
        # corpo (ver _draw_entities_landscape); em retrato as larguras
        # históricas (identificação = epw/2-33, coluna central = 84) são
        # mantidas à risca. mid_shift recentraliza os textos da coluna
        # central que são ancorados em posições absolutas afinadas para 84.
        total_w = self.epw - 0.1 * self._base_l_margin
        left_col_w = total_w / 3 if is_landscape else (self.epw / 2) - 33
        mid_col_w = total_w / 3 if is_landscape else 84
        mid_shift = (mid_col_w - 84) / 2
        w_rect = left_col_w
        # 32 em paisagem: encosta o fundo da caixa do emitente no topo da
        # caixa TIPO DO CT-E (37), em vez de invadi-la 3mm como no retrato.
        h_rect = 32 if is_landscape else 35
        self.emit_name = extract_text(self.emit, "xNome")
        self.cep = format_cep(extract_text(self.emit, "CEP"))
        self.fone = format_phone(extract_text(self.emit, "fone"))
        self.modal = TP_MODAL[extract_text(self.ide, "modal")]
        self.mod = extract_text(self.ide, "mod")
        self.serie = extract_text(self.ide, "serie")
        self.nct = extract_text(self.ide, "nCT")
        self.dt, self.hr = get_date_utc(extract_text(self.ide, "dhEmi"))
        self.protocol = extract_text(self.prot_cte, "nProt")
        self.dh_recebto, hr_recebto = get_date_utc(
            extract_text(self.prot_cte, "dhRecbto")
        )
        self.emit_cnpj = format_cpf_cnpj(extract_text(self.emit, "CNPJ"))
        address = (
            f"CNPJ: {self.emit_cnpj} IE: {extract_text(self.emit, 'IE')}\n"
            f"{extract_text(self.emit, 'xLgr')}, "
            f"{extract_text(self.emit, 'nro')}\n"
            f"{extract_text(self.emit, 'xBairro')}\n"
            f"{extract_text(self.emit, 'xMun')} - "
            f"{extract_text(self.emit, 'UF')}\n"
            f"{self.cep}\nFone: {self.fone}"
        )
        self.rect(x=x_margin, y=section_start_y, w=left_col_w, h=h_rect)
        logo_h = 8
        logo_y = section_start_y + 1
        if self.logo_image:
            self.image(
                name=self.logo_image,
                x=x_margin + 2,
                y=logo_y,
                w=w_rect - 4,
                h=logo_h,
                keep_aspect_ratio=True,
            )
            x_text = x_margin + 2
            y_text = section_start_y + logo_h + 2
            w_text = w_rect - 4
        else:
            x_text = x_margin + 2
            y_text = y_margin + 6
            w_text = w_rect - 4
        self.set_font(self.default_font, "B", 9)
        self.set_xy(x=x_text, y=y_text)
        self.multi_cell(w=w_text, h=4, text=self.emit_name, border=0, align="C")
        self.set_font(self.default_font, "", 7.5)
        self.set_xy(x=x_text, y=self.get_y() + 0.5)
        self.multi_cell(w=w_text, h=2.8, text=address, border=0, align="C")

        y_margin = self.l_margin + 22
        y_start = self.y + 4
        y_margin_ret = self.l_margin + left_col_w
        w_rect = 53
        h_rect = 11

        self.rect(x=y_margin_ret, y=section_start_y, w=w_rect, h=h_rect)
        self.set_font(self.default_font, "B", 10)
        self.set_xy(x=y_margin_ret + 2, y=section_start_y + 1.2)
        self.cell(w=w_rect - 4, h=3.2, text="DACTE", align="C", border=0)
        self.set_font(self.default_font, "", 6)
        self.set_xy(x=y_margin_ret + 2, y=section_start_y + 4.7)
        self.multi_cell(
            w=w_rect - 4,
            h=2.8,
            text="DOCUMENTO AUXILIAR DO CONHECIMENTO\nDE TRANSPORTE ELETRÔNICO",
            align="C",
        )

        self.rect(
            x=y_margin_ret + w_rect, y=section_start_y, w=mid_col_w - 53, h=11, style=""
        )

        self.set_font(self.default_font, "", 8)
        self.set_xy(y_margin_ret + 55, section_start_y + 2)
        self.multi_cell(w=mid_col_w - 57, h=1, text="MODAL", align="C")
        self.set_xy(y_margin_ret + 55, section_start_y + 2)
        self.set_font(self.default_font, "B", 8)
        self.multi_cell(w=mid_col_w - 57, h=11, text=self.modal, align="C")

        section_start_y += 11

        self.rect(x=y_margin_ret, y=section_start_y, w=mid_col_w, h=11, style="")

        # Colunas MODELO/SÉRIE/NÚMERO/DATA/FL ancoradas em y_margin_ret (início
        # da caixa à direita). O fator col_scale (1 no retrato) redistribui
        # proporcionalmente o alargamento da coluna central em paisagem —
        # sem ele, os 5mm extras iriam todos para a última coluna (FL).
        col_scale = mid_col_w / 84
        col_width = 17.8 * col_scale
        x_line_1 = y_margin_ret + 20.8 * col_scale
        x_line_2 = x_line_1 + col_width
        x_line_3 = x_line_2 + col_width
        x_line_4 = x_line_3 + col_width
        x_line_5 = x_line_4
        self.line(
            x1=x_line_1 - 5 * col_scale,
            x2=x_line_1 - 5 * col_scale,
            y1=section_start_y,
            y2=section_start_y + 11,
        )
        self.line(
            x1=x_line_2 - 5 * col_scale,
            x2=x_line_2 - 5 * col_scale,
            y1=section_start_y,
            y2=section_start_y + 11,
        )
        self.line(
            x1=x_line_3 - 8 * col_scale,
            x2=x_line_3 - 8 * col_scale,
            y1=section_start_y,
            y2=section_start_y + 11,
        )
        self.line(x1=x_line_4, x2=x_line_4, y1=section_start_y, y2=section_start_y + 11)
        self.line(x1=x_line_5, x2=x_line_5, y1=section_start_y, y2=section_start_y + 11)

        self.set_font(self.default_font, "", 7)
        self.set_xy(y_margin_ret, section_start_y + 2)
        self.multi_cell(
            w=x_line_1 - 5 * col_scale - y_margin_ret, h=1, text="MODELO", align="C"
        )
        self.set_xy(y_margin_ret, section_start_y + 2)
        self.set_font(self.default_font, "B", 7)
        self.multi_cell(
            w=x_line_1 - 5 * col_scale - y_margin_ret, h=11, text=self.mod, align="C"
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_2 - 28, section_start_y + 2)
        self.multi_cell(w=31 - 4, h=1, text="SÉRIE", align="C")
        self.set_xy(x_line_2 - 28, section_start_y + 2)
        self.set_font(self.default_font, "B", 7)
        self.multi_cell(w=31 - 4, h=11, text=self.serie, align="C")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_3 - 29, section_start_y + 2)
        self.multi_cell(w=31 - 4, h=1, text="NÚMERO", align="C")
        self.set_xy(x_line_3 - 29, section_start_y + 2)
        self.set_font(self.default_font, "B", 7)
        self.multi_cell(w=31 - 4, h=11, text=self.nct, align="C")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_4 - 27, section_start_y + 0.9)
        self.multi_cell(w=31 - 4, h=2.5, text="DATA E HORA\nDE EMISSÃO", align="C")
        self.set_xy(x_line_4 - 27, section_start_y + 2)
        self.set_font(self.default_font, "B", 7)
        self.multi_cell(w=31 - 4, h=11, text=f"{self.dt} {self.hr}", align="C")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_5 - 9, section_start_y + 2)
        self.multi_cell(w=31 - 4, h=1, text="FL", align="C")
        self.set_xy(x_line_5 - 9, section_start_y + 2)
        self.set_font(self.default_font, "B", 7)
        self.multi_cell(w=31 - 1, h=11, text=f"{self.page_no()}/{{nb}}", align="C")

        section_start_y += 11
        y = section_start_y + 0.5
        w = mid_col_w - 2
        h = 8.5
        self.rect(x=y_margin_ret, y=section_start_y, w=mid_col_w, h=10, style="")
        svg_img_bytes = BytesIO()
        Code128(self.key_cte, writer=SVGWriter()).write(
            svg_img_bytes, options={"write_text": False}
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            self.image(svg_img_bytes, x=y_margin_ret + 1, y=y, w=w, h=h)

        section_start_y += 10

        self.set_font(self.default_font, "", 8)
        self.rect(x=y_margin_ret, y=section_start_y, w=mid_col_w, h=10, style="")
        self.set_xy(x_line_5 - 55 + mid_shift, section_start_y + 2)
        self.multi_cell(w=45, h=0, text="CHAVE DE ACESSO", align="C")
        self.set_xy(x_line_5 - 70 + mid_shift, section_start_y + 2)
        self.set_font(self.default_font, "B", 8)
        self.multi_cell(w=75, h=10, text=self.key_cte, align="C")
        section_start_y += 10

        self.rect(x=y_margin_ret, y=section_start_y, w=mid_col_w, h=9, style="")
        self.set_xy(x=y_margin_ret, y=section_start_y)
        self.multi_cell(
            w=mid_col_w + 1,
            h=10,
            text="CONSULTA EM http://www.cte.fazenda.gov.br",
            align="C",
        )
        section_start_y += 9

        self.set_font(self.default_font, "", 8)
        self.rect(x=y_margin_ret, y=section_start_y, w=mid_col_w, h=10, style="")
        self.set_xy(x=y_margin_ret, y=section_start_y)
        self.multi_cell(
            w=mid_col_w + 1, h=4, text="PROTOCOLO DE AUTORIZAÇÃO DE USO", align="C"
        )
        self.set_xy(x=y_margin_ret, y=section_start_y)
        self.set_font(self.default_font, "B", 8)
        self.multi_cell(
            w=mid_col_w + 2,
            h=14,
            text=f"{self.protocol} {self.dh_recebto} {hr_recebto}",
            align="C",
        )

        section_start_y += 10
        # TIPO DO CT-E / TIPO DO SERVIÇO — alinha com CHAVE DE ACESSO (h=10)
        self.set_font(self.default_font, "", 8)
        self.rect(
            x=self.l_margin,
            y=section_start_y - 29,
            w=left_col_w,
            h=10,
            style="",
        )

        cell_width = left_col_w / 2
        self.line(
            x1=self.l_margin + cell_width,
            y1=section_start_y - 29,
            x2=self.l_margin + cell_width,
            y2=section_start_y - 19,
        )

        self.set_font(self.default_font, "", 7.2)
        self.set_xy(x=self.l_margin + 1, y=section_start_y - 29)
        self.cell(w=cell_width - 1, h=3.2, text="TIPO DO CT-E", align="L", border=0)
        self.set_xy(x=self.l_margin + 1, y=section_start_y - 25)
        self.set_font(self.default_font, "B", 7.2)
        self.cell(w=cell_width - 1, h=3.2, text=self.tp_cte, align="L", border=0)

        self.set_font(self.default_font, "", 7.2)
        self.set_xy(x=self.l_margin + cell_width + 1, y=section_start_y - 29)
        self.cell(
            w=cell_width - 1,
            h=3.2,
            text="TIPO DO SERVIÇO",
            align="L",
            border=0,
        )
        self.set_xy(x=self.l_margin + cell_width + 1, y=section_start_y - 25)
        self.set_font(self.default_font, "B", 7.2)
        self.cell(
            w=cell_width - 1,
            h=3.2,
            text=self.tp_serv,
            align="L",
            border=0,
        )

        section_start_y += 10

        # TOMADOR DO SERVIÇO — alinha com CONSULTA EM (h=9)
        self.set_font(self.default_font, "", 8)
        self.rect(
            x=self.l_margin,
            y=section_start_y - 29,
            w=left_col_w,
            h=9,
            style="",
        )
        self.set_xy(x=self.l_margin, y=section_start_y - 29)
        self.multi_cell(w=85, h=4, text="TOMADOR DO SERVIÇO", align="L")
        self.set_xy(x=self.l_margin, y=section_start_y - 29)
        self.set_font(self.default_font, "B", 8)
        self.multi_cell(w=85, h=10, text=self.toma, align="L")

        section_start_y += 9

        # CFOP — alinha com PROTOCOLO (h=10)
        self.set_font(self.default_font, "", 8)
        self.rect(
            x=self.l_margin,
            y=section_start_y - 29,
            w=left_col_w,
            h=10,
            style="",
        )
        self.set_xy(x=self.l_margin, y=section_start_y - 29)
        self.multi_cell(w=85, h=4, text="CFOP - NATUREZA DA PRESTAÇÃO", align="L")
        self.set_font(self.default_font, "B", 7)
        cfop_text = f"{self.cfop} - {self.nat_op}"

        wrapped_lines = textwrap.wrap(cfop_text, width=42)
        cfop_text_wrapped = "\n".join(wrapped_lines)

        self.set_xy(x=self.l_margin, y=section_start_y - 25)
        self.multi_cell(w=200, h=2.5, text=cfop_text_wrapped, align="L")

        qr_code = extract_text(self.inf_cte_supl, "qrCodCTe")
        qr_box_size = 38
        qr_col_h = 61  # mesma altura da coluna DACTE
        qr_frame_x = y_margin_ret + mid_col_w
        qr_frame_w = x_margin + self.epw - 0.1 * self._base_l_margin - qr_frame_x

        # Em paisagem, INÍCIO/TÉRMINO DA PRESTAÇÃO saem da linha própria (que
        # em retrato fica acima de REMETENTE/DESTINATÁRIO) e passam a ocupar
        # a parte de baixo da célula do QR Code, que sobra vazia — o QR é
        # recentralizado no espaço restante (acima dessa faixa).
        # 10mm: deixa o topo da faixa exatamente na mesma linha do topo das
        # caixas PROTOCOLO/CFOP (56mm), alinhando as três colunas do
        # cabeçalho — e dá folga para os rótulos em fonte 7.
        inicio_fim_h = 10 if is_landscape else 0
        qr_area_h = qr_col_h - inicio_fim_h

        # centraliza o QR horizontalmente e verticalmente dentro do frame
        x_offset = mid_col_w + (qr_frame_w - qr_box_size) / 2
        y_offset = (qr_section_y - self.t_margin) + (qr_area_h - qr_box_size) / 2

        self.rect(x=qr_frame_x, y=qr_section_y, w=qr_frame_w, h=qr_col_h, style="")
        draw_qr_code(self, qr_code, y_margin_ret, x_offset, y_offset, box_size=qr_box_size)

        if is_landscape:
            mun_ini = extract_text(self.ide, "xMunIni")
            mun_fim = extract_text(self.ide, "xMunFim")
            est_inicio = extract_text(self.ide, "UFIni")
            est_fim = extract_text(self.ide, "UFFim")

            inicio_fim_y = qr_section_y + qr_area_h
            mid_x = qr_frame_x + qr_frame_w / 2

            self.line(
                x1=qr_frame_x,
                y1=inicio_fim_y,
                x2=qr_frame_x + qr_frame_w,
                y2=inicio_fim_y,
            )
            self.line(
                x1=mid_x, y1=inicio_fim_y, x2=mid_x, y2=qr_section_y + qr_col_h
            )

            col_w = qr_frame_w / 2 - 2
            self.set_font(self.default_font, "", 7)
            self.set_xy(x=qr_frame_x + 1, y=inicio_fim_y + 2)
            self.multi_cell(w=col_w, h=0, text="INÍCIO DA PRESTAÇÃO", align="L")
            self.set_xy(x=qr_frame_x + 1, y=inicio_fim_y + 2)
            # 6.5 no valor: municípios longos ("VARGEM GRANDE PAULISTA -
            # SP") ainda cabem em uma linha na meia-coluna de ~42mm.
            self.set_font(self.default_font, "B", 6.5)
            self.multi_cell(w=col_w, h=6, text=f"{mun_ini} - {est_inicio}", align="L")

            self.set_font(self.default_font, "", 7)
            self.set_xy(x=mid_x + 1, y=inicio_fim_y + 2)
            self.multi_cell(w=col_w, h=0, text="TÉRMINO DA PRESTAÇÃO", align="L")
            self.set_xy(x=mid_x + 1, y=inicio_fim_y + 2)
            self.set_font(self.default_font, "B", 6.5)
            self.multi_cell(w=col_w, h=6, text=f"{mun_fim} - {est_fim}", align="L")

            # Deixa self.y no fundo real do cabeçalho (as três colunas —
            # CFOP, PROTOCOLO e moldura do QR — terminam todas aqui). O
            # self.y "natural" fica no fim do texto do CFOP, alguns mm
            # acima, o que fazia o corpo começar por dentro destas caixas.
            self.set_y(qr_section_y + qr_col_h)

    def _draw_recipient_sender(self, config):
        self.mun_ini = extract_text(self.ide, "xMunIni")
        self.mun_fim = extract_text(self.ide, "xMunFim")
        self.est_inico = extract_text(self.ide, "UFIni")
        self.est_fim = extract_text(self.ide, "UFFim")
        self.prod_pre = extract_text(self.inf_carga, "proPred")
        self.v_total_carga = format_number(
            extract_text(self.inf_carga, "vCarga"), precision=2
        )

        # Função para extrair dados de uma entidade do XML
        def extract_entity_data(node, prefix):
            """Extrai todos os campos padrão de uma entidade (pessoa) do XML"""
            if node is None:
                empty_data = {
                    f"{prefix}_{field}": ""
                    for field in [
                        "nome",
                        "loga",
                        "nro",
                        "bairro",
                        "mun",
                        "cnpj",
                        "pais",
                        "cep",
                        "ie",
                        "fone",
                        "uf",
                    ]
                }
                for field, value in empty_data.items():
                    setattr(self, field, value)
                return

            # Extrai os dados básicos da entidade
            setattr(self, f"{prefix}_nome", extract_text(node, "xNome"))
            setattr(self, f"{prefix}_loga", extract_text(node, "xLgr"))
            setattr(self, f"{prefix}_nro", extract_text(node, "nro"))
            setattr(self, f"{prefix}_bairro", extract_text(node, "xBairro"))
            setattr(self, f"{prefix}_mun", extract_text(node, "xMun"))
            setattr(self, f"{prefix}_cnpj", format_cpf_cnpj(extract_text(node, "CNPJ")))
            setattr(self, f"{prefix}_pais", extract_text(node, "xPais"))
            setattr(self, f"{prefix}_cep", format_cep(extract_text(node, "CEP")))
            setattr(self, f"{prefix}_ie", extract_text(node, "IE"))
            setattr(self, f"{prefix}_fone", format_phone(extract_text(node, "fone")))
            setattr(self, f"{prefix}_uf", extract_text(node, "UF"))

        # Extrai dados de todas as entidades
        extract_entity_data(self.rem, "rem")
        extract_entity_data(self.dest, "dest")
        extract_entity_data(self.exped, "exped")
        extract_entity_data(self.receb, "receb")
        extract_entity_data(self.outros, "outros")

        # Mapeamento de tipos de tomador para prefixos de atributos
        tomador_map = {
            "REMETENTE": "rem",
            "EXPEDIDOR": "exped",
            "RECEBEDOR": "receb",
            "DESTINATÁRIO": "dest",
            "OUTRO": "outros",
        }

        # Determina o prefixo correto com base no tipo de tomador,
        # padrão para "rem" se não encontrado
        entity_prefix = tomador_map.get(self.toma, "rem")

        # Define os dados do tomador copiando os atributos da entidade correspondente
        for field in [
            "nome",
            "loga",
            "nro",
            "bairro",
            "mun",
            "cnpj",
            "pais",
            "cep",
            "ie",
            "fone",
            "uf",
        ]:
            value = getattr(self, f"{entity_prefix}_{field}", "")
            setattr(self, f"tomador_{field}", value)

        x_margin = self.l_margin
        # Largura fixa (não escala com self.epw): os campos CEP/IE/FONE são
        # ancorados relativos a x_line_middle, não ao conteúdo à esquerda —
        # esticar a coluna aqui só abriria um vão entre o endereço e esses
        # campos. Em paisagem sobra espaço em branco à direita da caixa, mas
        # sem vãos internos.
        page_width = 155

        self.set_margins(
            left=self.content_l_margin, top=config.margins.top, right=config.margins.right
        )

        if self.orientation == "L":
            # Em paisagem a largura extra permite três blocos iguais lado a
            # lado (REMETENTE / DESTINATÁRIO / TOMADOR DO SERVIÇO) — o
            # TOMADOR sai da faixa própria de 10mm (ver
            # _draw_service_recipient) e o espaço liberado desce para as
            # seções finais.
            self._draw_entities_landscape()
            return
        # Continua logo abaixo de onde o cabeçalho realmente terminou (self.y),
        # em vez de uma posição fixa pensada só para retrato — em paisagem o
        # cabeçalho termina mais cedo (o recibo não ocupa mais o topo), o que
        # antes deixava um vão em branco aqui.
        section_start_y = self.y + 3.5

        if self.orientation != "L":
            # Em paisagem, INÍCIO/TÉRMINO DA PRESTAÇÃO são desenhados dentro
            # da célula do QR Code (ver _draw_header) em vez desta linha
            # própria, que só existe em retrato.
            self.rect(
                x=x_margin,
                y=section_start_y,
                w=self.epw - 0.1 * self._base_l_margin,
                h=7,
                style="",
            )
            col_width = (page_width - x_margin) / 2
            x_line_middle = x_margin + col_width + 20

            self.line(
                x1=x_line_middle,
                x2=x_line_middle,
                y1=section_start_y + 7,
                y2=section_start_y,
            )

            self.set_font(self.default_font, "", 8)
            self.set_xy(x=self.l_margin, y=section_start_y + 2)
            self.multi_cell(w=0, h=0, text="INÍCIO DA PRESTAÇÃO", align="L")
            self.set_xy(x=self.l_margin, y=section_start_y + 2)
            self.set_font(self.default_font, "B", 8)
            self.multi_cell(
                w=0, h=6, text=f"{self.mun_ini} - {self.est_inico}", align="L"
            )

            self.set_font(self.default_font, "", 8)
            self.set_xy(x_line_middle, section_start_y + 2)
            self.multi_cell(w=0, h=0, text="TÉRMINO DA PRESTAÇÃO", align="L")
            self.set_xy(x_line_middle, section_start_y + 2)
            self.set_font(self.default_font, "B", 8)
            self.multi_cell(
                w=0, h=6, text=f"{self.mun_fim} - {self.est_fim}", align="L"
            )

        self.rect(
            x=x_margin, y=section_start_y, w=self.epw - 0.1 * self._base_l_margin, h=24, style=""
        )
        col_width = (page_width - x_margin) / 2
        x_line_middle = x_margin + col_width + 20
        self.line(
            x1=x_line_middle,
            x2=x_line_middle,
            y1=section_start_y + 42,
            y2=section_start_y,
        )

        # Remetente
        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 2)
        self.multi_cell(w=0, h=15, text="REMETENTE ", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 2)
        self.multi_cell(w=0, h=15, text=limit_text(self.rem_nome, 48), align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 2)
        self.multi_cell(
            w=0,
            h=21,
            text="ENDEREÇO ",
            align="L",
        )

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 2)
        self.multi_cell(
            w=0,
            h=21,
            text=f"{self.rem_loga}, {self.rem_bairro}, {self.rem_nro}",
            align="L",
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 2)
        self.multi_cell(w=0, h=27, text="MUNICÍPIO ", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 2)
        self.multi_cell(
            w=0,
            h=27,
            text=f"{self.rem_mun}{' - ' + self.rem_uf if self.rem_uf else ''}",
            align="L",
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 2)
        self.multi_cell(w=0, h=33, text="CNPJ/CPF ", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 2)
        self.multi_cell(w=0, h=33, text=f"{self.rem_cnpj}", align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 2)
        self.multi_cell(w=0, h=39, text="PAÍS ", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 2)
        self.multi_cell(w=0, h=39, text=f"{self.rem_pais}", align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle - 29, section_start_y + 2)
        self.multi_cell(w=10, h=27, text="CEP", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle - 19, section_start_y + 2)
        if len(self.rem_cep.strip()) == 9:
            self.multi_cell(w=17, h=27, text=f"{self.rem_cep}", align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle - 29, section_start_y + 2)
        self.multi_cell(w=10, h=33, text="IE", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle - 19, section_start_y + 2)
        self.multi_cell(w=17, h=33, text=f"{self.rem_ie}", align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle - 29, section_start_y + 2)
        self.cell(w=10, h=39, text="FONE", align="L", border=0)
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle - 19, section_start_y + 2)
        self.cell(w=17, h=39, text=self.rem_fone, align="R", border=0)

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 2)
        self.multi_cell(w=0, h=15, text="DESTINATÁRIO ", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 22, section_start_y + 2)
        self.multi_cell(w=0, h=15, text=limit_text(self.dest_nome, 48), align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 2)
        self.multi_cell(
            w=0,
            h=21,
            text="ENDEREÇO ",
            align="L",
        )

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 22, section_start_y + 2)
        self.multi_cell(
            w=0,
            h=21,
            text=f"{self.dest_loga}, {self.dest_bairro}, {self.dest_nro}",
            align="L",
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 2)
        self.multi_cell(w=0, h=27, text="MUNICÍPIO ", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 22, section_start_y + 2)
        self.multi_cell(
            w=0,
            h=27,
            text=f"{self.dest_mun}{' - ' + self.dest_uf if self.dest_uf else ''}",
            align="L",
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 2)
        self.multi_cell(w=0, h=33, text="CNPJ/CPF ", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 22, section_start_y + 2)
        self.multi_cell(w=0, h=33, text=f"{self.dest_cnpj}", align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 2)
        self.multi_cell(w=0, h=39, text="PAÍS ", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 22, section_start_y + 2)
        self.multi_cell(w=0, h=39, text=f"{self.dest_pais}", align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle + 70, section_start_y + 2)
        self.multi_cell(w=10, h=27, text="CEP", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 80, section_start_y + 2)
        if len(self.dest_cep.strip()) == 9:
            self.multi_cell(w=22, h=27, text=f"{self.dest_cep}", align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle + 70, section_start_y + 2)
        self.multi_cell(w=10, h=33, text="IE", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 80, section_start_y + 2)
        self.multi_cell(w=22, h=33, text=f"{self.dest_ie}", align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle + 70, section_start_y + 2)
        self.cell(w=10, h=39, text="FONE", align="L", border=0)
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 80, section_start_y + 2)
        self.cell(w=22, h=39, text=self.dest_fone, align="R", border=0)

        section_start_y += 24

        self.rect(
            x=x_margin, y=section_start_y, w=self.epw - 0.1 * self._base_l_margin, h=18, style=""
        )
        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 0.5)
        self.multi_cell(w=0, h=3, text="RECEBEDOR", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 20, section_start_y + 0.5)
        self.multi_cell(w=0, h=3, text=limit_text(self.receb_nome, 48), align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 0.5)
        self.multi_cell(w=0, h=10, text="ENDEREÇO", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 20, section_start_y + 0.5)
        self.multi_cell(
            w=0,
            h=10.6,
            text=f"{self.receb_loga} {self.receb_bairro} {self.receb_nro}",
            align="L",
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 0.5)
        self.multi_cell(w=0, h=17, text="MUNICÍPIO", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 20, section_start_y + 0.5)
        self.multi_cell(
            w=0,
            h=18.2,
            text=f"{self.receb_mun}{' - ' + self.receb_uf if self.receb_uf else ''}",
            align="L",
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 0.5)
        self.multi_cell(w=0, h=25, text="CNPJ/CPF", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 20, section_start_y + 0.5)
        self.multi_cell(w=0, h=25.8, text=f"{self.receb_cnpj}", align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle, section_start_y + 0.5)
        self.multi_cell(w=0, h=32, text="PAÍS", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 20, section_start_y)
        self.multi_cell(w=0, h=33.4, text=f"{self.receb_pais}", align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle + 70, section_start_y + 0.5)
        self.multi_cell(w=10, h=17, text="CEP", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 80, section_start_y + 0.5)
        if len(self.receb_cep.strip()) == 9:
            self.multi_cell(w=22, h=17, text=f"{self.receb_cep}", align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle + 70, section_start_y + 0.5)
        self.multi_cell(w=10, h=25, text="IE", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 80, section_start_y + 0.5)
        self.multi_cell(w=22, h=25, text=f"{self.receb_ie}", align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle + 70, section_start_y + 0.5)
        self.cell(w=10, h=32, text="FONE", align="L", border=0)
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 80, section_start_y + 0.5)
        self.cell(w=22, h=32, text=self.receb_fone, align="R", border=0)

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 0.5)
        self.multi_cell(w=0, h=3, text="EXPEDIDOR", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 0.5)
        self.multi_cell(w=0, h=3, text=limit_text(self.exped_nome, 48), align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 0.5)
        self.multi_cell(w=0, h=10, text="ENDEREÇO", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 0.5)
        self.multi_cell(
            w=0,
            h=10.6,
            text=f"{self.exped_loga} {self.exped_bairro} {self.exped_nro}",
            align="L",
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 0.5)
        self.multi_cell(w=0, h=17, text="MUNICÍPIO", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 0.5)
        self.multi_cell(
            w=0,
            h=18.2,
            text=f"{self.exped_mun}{' - ' + self.exped_uf if self.exped_uf else ''}",
            align="L",
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 0.5)
        self.multi_cell(w=0, h=25, text="CNPJ/CPF", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y + 0.5)
        self.multi_cell(w=0, h=25.8, text=f"{self.exped_cnpj}", align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x=self.l_margin, y=section_start_y + 0.5)
        self.multi_cell(w=0, h=32, text="PAÍS", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x=self.l_margin + 16, y=section_start_y)
        self.multi_cell(w=0, h=33.4, text=f"{self.exped_pais}", align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle - 29, section_start_y + 0.5)
        self.multi_cell(w=10, h=17, text="CEP", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle - 19, section_start_y + 0.5)
        if len(self.exped_cep.strip()) == 9:
            self.multi_cell(w=17, h=17, text=f"{self.exped_cep}", align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle - 29, section_start_y + 0.5)
        self.multi_cell(w=10, h=25, text="IE", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle - 19, section_start_y + 0.5)
        self.multi_cell(w=17, h=25, text=f"{self.exped_ie}", align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle - 29, section_start_y + 0.5)
        self.cell(w=10, h=32, text="FONE", align="L", border=0)
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle - 19, section_start_y + 0.5)
        self.cell(w=17, h=32, text=self.exped_fone, align="R", border=0)

        section_start_y += 18
        self.rect(
            x=x_margin, y=section_start_y, w=self.epw - 0.1 * self._base_l_margin, h=6, style=""
        )
        self.set_font(self.default_font, "", 7)
        self.set_xy(self.l_margin, section_start_y + 2)
        self.multi_cell(w=0, h=2, text="PRODUTO PREDOMINATE", align="L")

        self.set_font(self.default_font, "B", 6.5)
        self.set_xy(self.l_margin + 32, section_start_y + 2)
        self.multi_cell(w=0, h=2, text=limit_text(self.prod_pre, 70), align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x_line_middle + 40, section_start_y + 2)
        self.multi_cell(w=0, h=2, text="VALOR TOTAL DA CARGA", align="L")

        self.set_font(self.default_font, "B", 7)
        self.set_xy(x_line_middle + 72, section_start_y + 2)
        self.multi_cell(w=0, h=2, text=f"R$ {self.v_total_carga}", align="L")

    def _draw_entity_block24_landscape(self, x0, col_w, y0, title, prefix, label_w):
        """Um bloco de entidade (21mm) no padrão do REMETENTE do retrato,
        parametrizado pela coluna — linha de 3 blocos iguais da paisagem."""
        nome = getattr(self, f"{prefix}_nome")
        loga = getattr(self, f"{prefix}_loga")
        nro = getattr(self, f"{prefix}_nro")
        bairro = getattr(self, f"{prefix}_bairro")
        mun = getattr(self, f"{prefix}_mun")
        uf = getattr(self, f"{prefix}_uf")
        cnpj = getattr(self, f"{prefix}_cnpj")
        pais = getattr(self, f"{prefix}_pais")
        cep = getattr(self, f"{prefix}_cep")
        ie = getattr(self, f"{prefix}_ie")
        fone = getattr(self, f"{prefix}_fone")

        # Limites de caracteres derivados da largura útil da coluna
        # (~1.5mm por caractere em Helvetica bold 7): linhas plenas vão até
        # a borda da coluna; MUNICÍPIO para antes do rótulo CEP (col_w-29).
        full_chars = int((col_w - label_w - 2) / 1.5)
        mun_chars = int((col_w - label_w - 30) / 1.5)
        # Alturas bem menores que as do retrato (15/21/27/33/39): lá a
        # primeira linha fica afundada porque o topo da caixa pertence à
        # linha INÍCIO/TÉRMINO, que na paisagem mora na célula do QR — aqui
        # a primeira linha (h=3) encosta no topo da caixa.
        rows = [
            (title, limit_text(nome, full_chars), 3),
            ("ENDEREÇO ", limit_text(f"{loga}, {bairro}, {nro}", full_chars), 9),
            (
                "MUNICÍPIO ",
                # rstrip: se o corte cair entre o município e a UF, não
                # deixa um " -" solto no fim.
                limit_text(f"{mun}{' - ' + uf if uf else ''}", mun_chars).rstrip(" -"),
                15,
            ),
            ("CNPJ/CPF ", cnpj, 21),
            ("PAÍS ", pais, 27),
        ]
        for label, value, h in rows:
            self.set_font(self.default_font, "", 7)
            self.set_xy(x0, y0 + 2)
            self.multi_cell(w=0, h=h, text=label, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x0 + label_w, y0 + 2)
            self.multi_cell(w=0, h=h, text=value, align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x0 + col_w - 29, y0 + 2)
        self.multi_cell(w=10, h=15, text="CEP", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x0 + col_w - 19, y0 + 2)
        if len(cep.strip()) == 9:
            self.multi_cell(w=17, h=15, text=cep, align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x0 + col_w - 29, y0 + 2)
        self.multi_cell(w=10, h=21, text="IE", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x0 + col_w - 19, y0 + 2)
        # cell (sem quebra): IEs longas (SP tem 12 dígitos) transbordam
        # para a esquerda, onde há espaço, em vez de quebrarem por cima da
        # linha do FONE.
        self.cell(w=17, h=21, text=ie, align="R", border=0)

        self.set_font(self.default_font, "", 7)
        self.set_xy(x0 + col_w - 29, y0 + 2)
        self.cell(w=10, h=27, text="FONE", align="L", border=0)
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x0 + col_w - 19, y0 + 2)
        self.cell(w=17, h=27, text=fone, align="R", border=0)

    def _draw_entity_block18_landscape(self, x0, col_w, y0, title, prefix):
        """Um bloco de entidade compacto (20mm) no padrão do EXPEDIDOR do
        retrato, parametrizado pela coluna."""
        nome = getattr(self, f"{prefix}_nome")
        loga = getattr(self, f"{prefix}_loga")
        nro = getattr(self, f"{prefix}_nro")
        bairro = getattr(self, f"{prefix}_bairro")
        mun = getattr(self, f"{prefix}_mun")
        uf = getattr(self, f"{prefix}_uf")
        cnpj = getattr(self, f"{prefix}_cnpj")
        pais = getattr(self, f"{prefix}_pais")
        cep = getattr(self, f"{prefix}_cep")
        ie = getattr(self, f"{prefix}_ie")
        fone = getattr(self, f"{prefix}_fone")

        # Mesma lógica de limites do bloco de 24mm (ver
        # _draw_entity_block24_landscape); rótulos deste bloco usam 16mm.
        full_chars = int((col_w - 18) / 1.5)
        mun_chars = int((col_w - 46) / 1.5)
        rows = [
            (title, limit_text(nome, full_chars), 3, 3),
            ("ENDEREÇO", limit_text(f"{loga} {bairro} {nro}", full_chars), 10, 10.6),
            (
                "MUNICÍPIO",
                limit_text(f"{mun}{' - ' + uf if uf else ''}", mun_chars).rstrip(" -"),
                17,
                18.2,
            ),
            ("CNPJ/CPF", cnpj, 25, 25.8),
            ("PAÍS", pais, 32, 33.4),
        ]
        for label, value, h_label, h_value in rows:
            self.set_font(self.default_font, "", 7)
            self.set_xy(x0, y0 + 0.5)
            self.multi_cell(w=0, h=h_label, text=label, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x0 + 16, y0 + 0.5)
            self.multi_cell(w=0, h=h_value, text=value, align="L")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x0 + col_w - 29, y0 + 0.5)
        self.multi_cell(w=10, h=17, text="CEP", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x0 + col_w - 19, y0 + 0.5)
        if len(cep.strip()) == 9:
            self.multi_cell(w=17, h=17, text=cep, align="R")

        self.set_font(self.default_font, "", 7)
        self.set_xy(x0 + col_w - 29, y0 + 0.5)
        self.multi_cell(w=10, h=25, text="IE", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x0 + col_w - 19, y0 + 0.5)
        # cell (sem quebra) — mesmo motivo do bloco de 18mm acima: IEs de
        # 12 dígitos quebravam por cima da linha do FONE.
        self.cell(w=17, h=25, text=ie, align="R", border=0)

        self.set_font(self.default_font, "", 7)
        self.set_xy(x0 + col_w - 29, y0 + 0.5)
        self.cell(w=10, h=32, text="FONE", align="L", border=0)
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x0 + col_w - 19, y0 + 0.5)
        self.cell(w=17, h=32, text=fone, align="R", border=0)

    def _draw_entities_landscape(self):
        """Versão paisagem das entidades: grade de 3 colunas iguais —
        REMETENTE / DESTINATÁRIO / TOMADOR em cima (18mm), EXPEDIDOR /
        RECEBEDOR embaixo (20mm) e, na terceira célula dessa linha,
        PRODUTO PREDOMINANTE / VALOR TOTAL DA CARGA."""
        x_margin = self.l_margin
        total_w = self.epw - 0.1 * self._base_l_margin
        col_w = total_w / 3
        # Encosta no fundo do cabeçalho — a borda superior desta caixa é a
        # mesma linha da borda inferior dele, como no retrato.
        y0 = self.y

        h_top = 18
        h_bottom = 20
        self.rect(x=x_margin, y=y0, w=total_w, h=h_top, style="")
        self.rect(x=x_margin, y=y0 + h_top, w=total_w, h=h_bottom, style="")
        for i in (1, 2):
            x_div = x_margin + i * col_w
            self.line(x1=x_div, x2=x_div, y1=y0, y2=y0 + h_top + h_bottom)

        self._draw_entity_block24_landscape(
            x_margin, col_w, y0, "REMETENTE ", "rem", 16
        )
        self._draw_entity_block24_landscape(
            x_margin + col_w, col_w, y0, "DESTINATÁRIO ", "dest", 22
        )
        self._draw_entity_block24_landscape(
            x_margin + 2 * col_w, col_w, y0, "TOMADOR ", "tomador", 16
        )

        y1 = y0 + h_top
        self._draw_entity_block18_landscape(x_margin, col_w, y1, "EXPEDIDOR", "exped")
        self._draw_entity_block18_landscape(
            x_margin + col_w, col_w, y1, "RECEBEDOR", "receb"
        )

        # A célula à direita do RECEBEDOR recebe o conteúdo da antiga faixa
        # de PRODUTO PREDOMINANTE (rótulo, produto, linha em branco, VALOR
        # TOTAL DA CARGA e valor) — a faixa própria de 6mm do retrato deixa
        # de existir e o espaço desce para OBSERVAÇÕES.
        x2 = x_margin + 2 * col_w
        self.set_font(self.default_font, "", 7)
        self.set_xy(x2 + 1, y1 + 1)
        self.multi_cell(w=col_w - 2, h=3, text="PRODUTO PREDOMINANTE", align="L")
        self.set_font(self.default_font, "B", 6.5)
        self.set_xy(x2 + 1, y1 + 4.5)
        self.multi_cell(
            w=col_w - 2, h=3, text=limit_text(self.prod_pre, 60), align="L"
        )

        self.set_font(self.default_font, "", 7)
        self.set_xy(x2 + 1, y1 + 11.5)
        self.multi_cell(w=col_w - 2, h=3, text="VALOR TOTAL DA CARGA", align="L")
        self.set_font(self.default_font, "B", 7)
        self.set_xy(x2 + 1, y1 + 15)
        self.multi_cell(w=col_w - 2, h=3, text=f"R$ {self.v_total_carga}", align="L")

        self.set_y(y1 + h_bottom)

    def _draw_service_recipient(self, config):
        self.inf_carga_nome = extract_text(self.inf_carga, "proPred")
        self.inf_carga_car = extract_text(self.inf_carga, "xOutCat")

        self.inf_unid = extract_text(self.inf_carga, "cUnid")

        self.inf_carga_q = extract_text(self.inf_carga, "qCarga")

        x_margin = self.l_margin
        page_width = self.epw

        self.set_margins(
            left=self.content_l_margin, top=config.margins.top, right=config.margins.right
        )
        # Continua logo abaixo de onde a seção remetente/destinatário
        # realmente terminou (self.y), em vez de uma posição fixa pensada só
        # para retrato (ver _draw_recipient_sender).
        # Em paisagem a faixa de medidas encosta no bloco de entidades
        # (borda compartilhada); o respiro de 2mm é só do retrato.
        section_start_y = self.y + (0 if self.orientation == "L" else 2)

        if self.orientation == "L":
            # Em paisagem o TOMADOR já foi desenhado como terceiro bloco ao
            # lado de REMETENTE/DESTINATÁRIO (ver _draw_entities_landscape);
            # esta faixa própria de 10mm só existe em retrato.
            self._draw_measure_row(section_start_y)
            return

        self.rect(
            x=x_margin, y=section_start_y, w=page_width - 0.1 * self._base_l_margin, h=10, style=""
        )

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin, section_start_y)
        self.multi_cell(w=0, h=4, text="TOMADOR DO SERVIÇO ", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 32, section_start_y)
        self.multi_cell(w=0, h=4, text=limit_text(self.tomador_nome, 38), align="L")

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin, section_start_y)
        self.multi_cell(w=0, h=10, text="ENDEREÇO ", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 16, section_start_y)
        self.multi_cell(
            w=0,
            h=10,
            text=f"{self.tomador_loga}  {self.tomador_nro}  {self.tomador_bairro}",
            align="L",
        )

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin, section_start_y)
        self.multi_cell(w=0, h=16, text="CNPJ/CPF ", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 14, section_start_y)
        self.multi_cell(w=0, h=16, text=f"{self.tomador_cnpj}", align="L")

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin + 85, section_start_y)
        self.multi_cell(w=0, h=16, text="IE ", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 89, section_start_y)
        self.multi_cell(w=0, h=16, text=f"{self.tomador_ie}", align="L")

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin + 115, section_start_y)
        self.multi_cell(w=0, h=16, text="PAÍS ", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 122, section_start_y)
        self.multi_cell(w=0, h=16, text=f"{self.tomador_pais}", align="L")

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin + 100, section_start_y)
        self.multi_cell(w=0, h=4, text="MUNICÍPIO ", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 116, section_start_y)
        self.multi_cell(w=0, h=4, text=f"{self.tomador_mun}", align="L")

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin + 150, section_start_y)
        self.multi_cell(w=0, h=4, text="UF ", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 154, section_start_y)
        self.multi_cell(w=0, h=4, text=f"{self.tomador_uf}", align="L")

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin + 150, section_start_y)
        self.multi_cell(w=10, h=10, text="FONE", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 160, section_start_y)
        self.multi_cell(w=0, h=10, text=f"{self.tomador_fone}", align="L")

        self.set_font(self.default_font, "", 7.6)
        self.set_xy(x_margin + 160, section_start_y)
        self.multi_cell(w=0, h=4, text="CEP ", align="L")

        self.set_font(self.default_font, "B", 7.6)
        self.set_xy(x_margin + 166, section_start_y)
        self.multi_cell(w=0, h=4, text=f"{self.tomador_cep}", align="L")

        section_start_y += 10
        self._draw_measure_row(section_start_y)

    def _draw_measure_row(self, section_start_y):
        """Faixa TIPO MEDIDA/QTD/CUBAGEM/VOLUMES (11mm) — compartilhada
        entre retrato (abaixo da faixa TOMADOR) e paisagem (direto abaixo
        do grupo de entidades)."""
        x_margin = self.l_margin
        page_width = self.epw

        self.rect(
            x=x_margin,
            y=section_start_y,
            w=page_width - 0.1 * self._base_l_margin,
            h=11,
            style="",
        )

        # Define largura específica para o campo de cubagem
        cubagem_width = 20  # Largura ajustada para o título "CUBAGEM (M³)"
        volume_width = 25  # Largura ajustada para o título "QTD DE VOLUMES"

        # Distribui o espaço restante entre os outros 4 campos
        remaining_width = page_width - (x_margin + 2) - cubagem_width - volume_width
        other_col_width = remaining_width / 3

        # Calcula as posições X para cada coluna
        x_line_1 = x_margin + other_col_width
        x_line_2 = x_line_1 + other_col_width
        x_line_3 = x_line_2 + other_col_width
        x_line_4 = x_line_3 + cubagem_width  # Posição após o campo de cubagem

        # Desenha as linhas verticais
        self.line(x1=x_line_1, x2=x_line_1, y1=section_start_y, y2=section_start_y + 11)
        self.line(x1=x_line_2, x2=x_line_2, y1=section_start_y, y2=section_start_y + 11)
        self.line(x1=x_line_3, x2=x_line_3, y1=section_start_y, y2=section_start_y + 11)
        self.line(x1=x_line_4, x2=x_line_4, y1=section_start_y, y2=section_start_y + 11)

        # Define as posições X e larguras para todos os campos
        x_positions = [x_margin, x_line_1, x_line_2, x_line_3, x_line_4]
        col_widths = [
            other_col_width,
            other_col_width,
            other_col_width,
            cubagem_width,
            volume_width,
        ]

        # Imprime os títulos das colunas
        for i in range(5):
            self.set_xy(x_positions[i], section_start_y + 1)
            self.set_font(self.default_font, "", 6)
            if i < 3:
                # Para as três primeiras colunas, divide em duas subcolunas
                # 65% da largura para TIPO MEDIDA
                tipo_medida_width = col_widths[i] * 0.65
                # 35% da largura para QTD/UN
                qtd_un_width = col_widths[i] * 0.35
                self.cell(w=tipo_medida_width, h=3, text="TIPO MEDIDA", align="L")
                self.set_xy(x_positions[i] + tipo_medida_width, section_start_y + 1)
                self.cell(w=qtd_un_width, h=3, text="QTD/UN.", align="L")
            else:
                # Para as duas últimas colunas
                title = "CUBAGEM (M³)" if i == 3 else "QTD DE VOLUMES"
                self.multi_cell(w=col_widths[i], h=3, text=title, align="L")

        # Organiza os dados para as três primeiras colunas (até 2 linhas por coluna)
        column_data = [[], [], []]
        current_col = 0

        for item in self.inf_carga_list:
            c_unid, tp_media, q_carga = item
            if c_unid in TP_CODIGO_MEDIDA and q_carga and float(q_carga) > 0:
                if len(column_data[current_col]) < 2:  # Máximo de 2 linhas por coluna
                    column_data[current_col].append((tp_media, q_carga, c_unid))
                elif current_col < 2:  # Move para próxima coluna se atual está cheia
                    current_col += 1
                    column_data[current_col].append((tp_media, q_carga, c_unid))

        # Imprime os dados nas três primeiras colunas
        data_start_y = section_start_y + 4  # Espaço após os títulos
        line_height = 3.5  # Altura reduzida para caber duas linhas

        for col in range(3):
            items = column_data[col]
            for row, item in enumerate(items):
                tp_media, q_carga, c_unid = item
                y_pos = data_start_y + (row * line_height)
                # 65% da largura para TIPO MEDIDA
                tipo_medida_width = col_widths[col] * 0.65
                # 35% da largura para QTD/UN
                qtd_un_width = col_widths[col] * 0.35

                # Tipo Medida
                self.set_xy(x_positions[col], y_pos)
                self.set_font(self.default_font, "B", 6)
                self.cell(w=tipo_medida_width, h=line_height, text=tp_media, align="L")

                # Qtd/Un.Medida
                self.set_xy(x_positions[col] + tipo_medida_width, y_pos)
                self.cell(
                    w=qtd_un_width,
                    h=line_height,
                    text=f"{q_carga} {TP_CODIGO_MEDIDA_REDUZIDO[c_unid]}",
                    align="L",
                )

        # Imprime dados nas duas últimas colunas (cubagem e volumes)
        for item in self.inf_carga_list:
            c_unid, tp_media, q_carga = item
            if c_unid == "00" and tp_media in ["M3", "m3"] and float(q_carga) > 0:
                self.set_xy(x_positions[3], data_start_y)
                self.set_font(self.default_font, "B", 6)
                self.multi_cell(
                    w=col_widths[3],
                    h=line_height,
                    text=f"{q_carga} {TP_CODIGO_MEDIDA_REDUZIDO[c_unid]}",
                    align="L",
                )
            elif (
                c_unid == "03"
                and float(q_carga) > 0
                and tp_media.strip().upper() not in ["PARES"]
            ):
                self.set_xy(x_positions[4], data_start_y)
                self.set_font(self.default_font, "B", 6)
                self.multi_cell(
                    w=col_widths[4],
                    h=line_height,
                    text=f"{q_carga} {TP_CODIGO_MEDIDA_REDUZIDO[c_unid]}",
                    align="L",
                )

        # Atualiza a posição Y para a próxima seção
        section_start_y += 10
        self.y = section_start_y

    def draw_section(self, y, height, text, align="C"):
        bar_w = self.epw - 0.1 * self._base_l_margin
        # Em paisagem centraliza na largura real da barra; a fórmula do
        # retrato (epw - 2*l_margin) deixaria o texto ~24mm à esquerda do
        # centro, porque l_margin ali é a margem deslocada pelo recibo.
        text_w = bar_w if self.orientation == "L" else self.epw - 2 * self.l_margin
        self.rect(x=self.l_margin, y=y, w=bar_w, h=3, style="")
        self.set_xy(x=self.l_margin, y=y + 3)
        self.cell(w=text_w, h=-3, text=text, align=align)
        return y + height

    def _draw_service_fee_value(self):
        x_margin = self.l_margin
        y_margin = self.y
        page_width = self.epw
        self.cst = extract_text(self.imp, "CST")
        self.vbc = format_number(extract_text(self.imp, "vBC"), precision=2)
        self.p_icms = format_number(extract_text(self.imp, "pICMS"), precision=2)
        self.v_icms = format_number(extract_text(self.imp, "vICMS"), precision=2)
        self.v_icms_st = format_number(extract_text(self.imp, "vICMS"), precision=2)
        self.p_red_bc = format_number(extract_text(self.imp, "pRedBC"), precision=2)
        g_ibscbs = (
            self.imp_ibscbs.find(f"{URL}gIBSCBS")
            if self.imp_ibscbs is not None
            else None
        )
        g_uf = g_ibscbs.find(f"{URL}gIBSUF") if g_ibscbs is not None else None
        g_mun = g_ibscbs.find(f"{URL}gIBSMun") if g_ibscbs is not None else None
        g_cbs = g_ibscbs.find(f"{URL}gCBS") if g_ibscbs is not None else None
        self.p_ibs_uf = format_number(extract_text(g_uf, "pIBSUF") or "0", precision=2)
        self.v_ibs_uf = format_number(extract_text(g_uf, "vIBSUF") or "0", precision=2)
        self.p_ibs_mun = format_number(
            extract_text(g_mun, "pIBSMun") or "0", precision=2
        )
        self.v_ibs_mun = format_number(
            extract_text(g_mun, "vIBSMun") or "0", precision=2
        )
        self.p_cbs = format_number(extract_text(g_cbs, "pCBS") or "0", precision=2)
        self.v_cbs = format_number(extract_text(g_cbs, "vCBS") or "0", precision=2)
        self.rntrc = extract_text(self.inf_modal, "RNTRC")
        self.x_obs = extract_text(self.compl, "compl")
        self.v_tpprest = format_number(
            extract_text(self.v_prest, "vTPrest"), precision=2
        )
        self.v_rec = format_number(extract_text(self.v_prest, "vRec"), precision=2)

        section_start_y = y_margin + 1

        self.set_font(self.default_font, "", 6.5)
        section_start_y = self.draw_section(
            section_start_y, 3, "COMPONENTES DO VALOR DA PRESTAÇÃO DO SERVIÇO"
        )
        self.rect(
            x=x_margin, y=section_start_y, w=page_width - 0.1 * self._base_l_margin, h=18, style=""
        )

        col_width = (page_width - 2 * x_margin) / 4
        for i in range(1, 4):
            x_line = x_margin + i * col_width
            self.line(x1=x_line, x2=x_line, y1=section_start_y, y2=section_start_y + 18)

        self.set_font(self.default_font, "", 8)

        nome_w = col_width * 0.65
        valor_w = col_width * 0.35

        # Desenha os títulos "NOME" e "VALOR" para as 3 colunas
        titles = ["NOME", "VALOR"]
        for col in range(3):
            nome_x = x_margin + col * col_width
            valor_x = nome_x + nome_w

            # Imprime os títulos
            self.set_xy(nome_x, section_start_y)
            self.cell(w=nome_w, h=4, text=titles[0], align="L")
            self.set_xy(valor_x, section_start_y)
            self.cell(w=valor_w, h=4, text=titles[1], align="R")

        # Distribuir os componentes em 3 colunas com 3 linhas cada
        col1 = self.comp_list[:3]  # Primeiros 3 componentes
        col2 = self.comp_list[3:6]  # Próximos 3 componentes
        col3 = self.comp_list[6:9]  # Últimos 3 componentes

        # Altura inicial para começo dos dados
        data_y = section_start_y + 4

        # Função auxiliar para imprimir uma coluna de componentes
        def print_column(components, x_start):
            current_y = data_y
            for comp in components:
                self.set_xy(x_start, current_y)
                self.cell(w=nome_w, h=4, text=comp[0], align="L")
                self.set_xy(x_start + nome_w, current_y)
                self.cell(w=valor_w, h=4, text=comp[1], align="R")
                current_y += 4  # Incrementa a posição Y para o próximo item

        # Imprime cada coluna
        print_column(col1, x_margin)  # Primeira coluna
        print_column(col2, x_margin + col_width)  # Segunda coluna
        print_column(col3, x_margin + 2 * col_width)  # Terceira coluna

        # Largura explícita (em vez de w=0 até a margem direita): deixa os
        # valores 1mm afastados da borda direita da caixa.
        value_w = page_width - 0.1 * self._base_l_margin - 3 * col_width - 1

        self.set_font(self.default_font, "", 8)
        self.set_xy(x_margin + 3 * col_width, section_start_y)
        self.multi_cell(w=col_width, h=4, text="VALOR TOTAL DO SERVIÇO", align="L")
        self.set_font(self.default_font, "B", 9)
        self.set_xy(x_margin + 3 * col_width, section_start_y + 4)
        self.multi_cell(w=value_w, h=4, text=f"R$ {self.v_tpprest}", align="R")

        self.line(
            x1=x_margin + 3 * col_width,
            x2=x_margin + page_width - 0.1 * self._base_l_margin,
            y1=section_start_y + 9,
            y2=section_start_y + 9,
        )

        self.set_font(self.default_font, "", 8)
        self.set_xy(x_margin + 3 * col_width, section_start_y + 9)
        self.multi_cell(w=col_width, h=4, text="VALOR TOTAL A RECEBER", align="L")
        self.set_font(self.default_font, "B", 9)
        self.set_xy(x_margin + 3 * col_width, section_start_y + 13)
        self.multi_cell(w=value_w, h=4, text=f"R$ {self.v_rec}", align="R")

        section_start_y += 18

        self.set_font(self.default_font, "", 6.5)
        # Em paisagem a caixa de impostos (uma única linha título+valor)
        # dispensa os 15mm do retrato — 10mm bastam e liberam espaço
        # vertical para as seções finais caberem na página mais baixa.
        is_landscape = self.orientation == "L"
        imposto_h = 10 if is_landscape else 15
        section_start_y = self.draw_section(
            section_start_y, imposto_h + 3, "INFORMAÇÕES RELATIVAS AO IMPOSTO"
        )
        self.cst_desc = TP_ICMS[extract_text(self.imp, "CST")]
        total_width = page_width - 0.1 * self._base_l_margin
        self.rect(
            x=x_margin,
            y=section_start_y - imposto_h,
            w=total_width,
            h=imposto_h,
            style="",
        )

        if self.display_ibs_cbs:
            ibs_width = total_width * 0.15
            col_width = (total_width - ibs_width) / 6
        else:
            col_width = total_width / 6
            ibs_width = 0

        for i in range(1, 6):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - imposto_h,
                y2=section_start_y,
            )

        tax_titles = [
            "SITUAÇÃO TRIBUTÁRIA",
            "BASE DE CALCULO",
            "ALÍQ ICMS",
            "VALOR ICMS",
            "% RED. BC ICMS",
            "ICMS ST",
        ]
        tax_values = [
            f"{self.cst} - {self.cst_desc}",
            f"{self.vbc}",
            f"{self.p_icms}",
            f"{self.v_icms}",
            f"{self.p_red_bc}",
            f"{self.v_icms_st}",
        ]

        for i, (title, value) in enumerate(zip(tax_titles, tax_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - imposto_h)
            self.multi_cell(w=col_width, h=4, text=title, align="L")
            self.set_font(self.default_font, "B", 6)
            self.set_xy(x_margin + i * col_width, section_start_y - imposto_h + 4)
            self.multi_cell(w=col_width, h=4, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        if self.display_ibs_cbs:
            col_ibs = x_margin + 6 * col_width
            self.set_font(self.default_font, "", 6)
            self.line(
                x1=col_ibs,
                x2=col_ibs,
                y1=section_start_y - imposto_h,
                y2=section_start_y,
            )
            self.set_xy(col_ibs, section_start_y - imposto_h)
            self.multi_cell(w=ibs_width, h=4, text="IBS E CBS", align="L")
            self.set_font(self.default_font, "B", 4.8)
            valor_area_h = imposto_h - 4
            line_h = valor_area_h / 3
            y_start = section_start_y - imposto_h + 4
            w_label = ibs_width * 0.58
            w_val = ibs_width * 0.21
            ibs_rows = [
                ("IBS ESTADUAL (%/R$)", self.p_ibs_uf, self.v_ibs_uf),
                ("IBS MUNICIPAL (%/R$)", self.p_ibs_mun, self.v_ibs_mun),
                ("CBS (%/R$)", self.p_cbs, self.v_cbs),
            ]
            for i, (label, pct, val) in enumerate(ibs_rows):
                y_row = y_start + i * line_h
                self.set_xy(col_ibs, y_row)
                self.cell(w=w_label, h=line_h, text=label, align="L")
                self.set_xy(col_ibs + w_label + 0.8, y_row)
                self.cell(w=w_val, h=line_h, text=pct, align="R")
                self.set_xy(col_ibs + w_label + w_val + 1, y_row)
                self.cell(w=w_val, h=line_h, text=val, align="R")
            self.set_xy(col_ibs + w_label + w_val + 0.8, y_row - 3.2)

        if is_landscape:
            # Deixa self.y no fundo real da caixa de impostos: as células
            # acima terminam ~7mm antes dele, e a próxima seção parte de
            # self.y — sem isto o título de DOCUMENTOS ORIGINÁRIOS é
            # desenhado por dentro desta caixa.
            self.set_y(section_start_y)

    def _draw_documents_obs(self):
        x_margin = self.l_margin
        page_width = self.epw
        self.set_font(self.default_font, "", 7)
        is_landscape = self.orientation == "L"
        # Em paisagem a página tem bem menos altura útil (200mm vs 287mm no
        # retrato), então esta caixa (a maior do corpo) e as seguintes
        # precisam de um orçamento vertical menor para que OBSERVAÇÕES,
        # DADOS ESPECÍFICOS DO MODAL e USO EXCLUSIVO ainda caibam na página.
        docs_h = 11 if is_landscape else 40
        lines_per_block = 2 if is_landscape else 12
        docs_budget = docs_h + 3

        # Em paisagem self.y já está no fundo da caixa anterior (ver fim de
        # _draw_service_fee_value); em retrato self.y fica 7mm acima dele,
        # daí o +7 para encostar o título no fundo da caixa de impostos.
        section_start_y = self.get_y() + (0 if is_landscape else 7)
        section_start_y = self.draw_section(
            section_start_y, docs_budget, "DOCUMENTOS ORIGINÁRIOS"
        )
        box_w = page_width - 0.1 * self._base_l_margin
        self.rect(
            x=x_margin,
            y=section_start_y - docs_h,
            w=box_w,
            h=docs_h,
            style="",
        )
        # Em paisagem divide no meio real da caixa; a fórmula do retrato
        # (page_width - 2*x_margin) deixaria a divisória ~24mm à esquerda
        # do centro, porque x_margin ali é a margem deslocada pelo recibo.
        col_width = box_w / 2 if is_landscape else (page_width - 2 * x_margin) / 2
        half_col_width = col_width / 3
        x_line_middle = x_margin + col_width

        self.line(
            x1=x_line_middle,
            x2=x_line_middle,
            y1=section_start_y - docs_h,
            y2=section_start_y,
        )

        self.set_font(self.default_font, "", 6)
        self.set_xy(x_margin, section_start_y - docs_h + 3)
        self.multi_cell(w=half_col_width, h=0, text="TIPO DOC", align="L")
        self.set_xy(x_margin + half_col_width - 18, section_start_y - docs_h + 3)
        self.multi_cell(w=half_col_width, h=0, text="CNPJ/CHAVE", align="L")
        self.set_xy(x_margin + 2 * half_col_width, section_start_y - docs_h + 3)
        self.set_font(self.default_font, "", 5.5)
        self.multi_cell(w=half_col_width, h=0, text="SÉRIE/NRO. DOCUMENTO", align="L")

        self.set_font(self.default_font, "", 6)
        self.set_xy(x_line_middle, section_start_y - docs_h + 3)
        self.multi_cell(w=half_col_width, h=0, text="TIPO DOC", align="L")
        self.set_xy(x_line_middle + half_col_width - 20, section_start_y - docs_h + 3)
        self.multi_cell(w=half_col_width, h=0, text="CNPJ/CHAVE", align="L")
        self.set_xy(x_line_middle + 2 * half_col_width, section_start_y - docs_h + 3)
        self.set_font(self.default_font, "", 5.5)
        self.multi_cell(w=half_col_width, h=0, text="SÉRIE/NRO. DOCUMENTO", align="L")

        y_offset_left = section_start_y - docs_h + 4
        y_offset_right = section_start_y - docs_h + 4
        self.max_lines_per_page = lines_per_block * 2
        current_line_left = 0
        current_line_right = 0
        in_right_block = False

        for index, chave in enumerate(self.inf_doc_list):
            self.page_lines = index
            if self.page_lines >= self.max_lines_per_page:
                break

            if current_line_left == lines_per_block:
                current_line_left = 0
                in_right_block = True
                self.set_xy(x_line_middle, y_offset_right)

            if in_right_block:
                x_start = x_line_middle
                y_offset = y_offset_right
            else:
                x_start = x_margin
                y_offset = y_offset_left

            self.set_xy(x_start, y_offset)
            self.set_font(self.default_font, "B", 6)
            self.multi_cell(w=half_col_width, h=4, text="NFE", align="L")

            self.set_xy(x_start + half_col_width - 20, y_offset)
            self.multi_cell(w=half_col_width + 23, h=4, text=chave, align="L")

            key_nfe_1 = chave[22:25]
            key_nfe_2 = chave[25:34]
            key_nfe_format = f"{key_nfe_1}/{key_nfe_2}"

            self.set_font(self.default_font, "B", 6)
            self.set_xy(x_start + 2 * half_col_width + 3, y_offset)
            self.multi_cell(w=half_col_width, h=4, text=key_nfe_format, align="L")

            y_offset += 3
            if in_right_block:
                current_line_right += 1
                y_offset_right = y_offset
            else:
                current_line_left += 1
                y_offset_left = y_offset

            if (
                not in_right_block
                and current_line_left == 0
                and self.page_lines == lines_per_block
            ):
                y_offset_right = section_start_y - docs_h + 7

        self.set_font(self.default_font, "", 7)
        text_width = page_width - 0.1 * self._base_l_margin
        # Em paisagem a caixa comporta 1 linha (~200 caracteres na largura
        # de ~267mm); o excedente vai para a continuação na 2ª página via
        # text_exceeds_limit — o espaço poupado desce para os dados do
        # modal, que são mais apertados em paisagem.
        max_characters = 200 if is_landscape else 350
        combined_obs = " ".join(self.obs_dacte_list)
        obs_budget = 7 if is_landscape else 18
        min_obs_height = 4 if is_landscape else 10
        section_start_y = self.draw_section(section_start_y, obs_budget, "OBSERVAÇÕES")
        initial_y = section_start_y - (obs_budget - 3)

        self.set_xy(x_margin, initial_y)
        text_to_draw = combined_obs[:max_characters]
        self.remaining_text = combined_obs[max_characters:]
        self.text_exceeds_limit = len(combined_obs) > max_characters

        self.multi_cell(w=text_width, h=3, text=text_to_draw, align="L")
        calculated_height = self.get_y() - initial_y

        rectangle_height = max(calculated_height, min_obs_height)
        self.set_xy(x_margin, initial_y)
        self.rect(x=x_margin, y=initial_y, w=text_width, h=rectangle_height)
        if is_landscape:
            # self.y no fundo da caixa de OBSERVAÇÕES, para a próxima seção
            # partir dele em vez de sobrepor o texto acima.
            self.set_y(initial_y + rectangle_height)

    def draw_aereo_info(self, config):
        x_margin = self.l_margin
        page_width = self.epw
        self.nOCA = extract_text(self.inf_modal, "nOCA")
        self.CL = extract_text(self.inf_modal, "CL")
        self.cTar = extract_text(self.inf_modal, "cTar")
        self.vTar = format_number(extract_text(self.inf_modal, "vTar"), precision=2)
        self.nMinu = extract_text(self.inf_modal, "nMinu")
        self.cInfManu = TP_MANUSEIO.get(
            extract_text(self.inf_modal, "cInfManu"), "Não Informado"
        )
        self.dPrevAereo = extract_text(self.inf_modal, "dPrevAereo")
        self.xDime = format_xDime(extract_text(self.inf_modal, "xDime"))
        # Em paisagem o título encosta na caixa anterior (self.y já está no
        # fundo dela); o respiro de 7mm é só do retrato.
        section_start_y = self.get_y() + (0 if self.orientation == "L" else 7)
        section_start_y = self.draw_section(
            section_start_y,
            13,
            "DADOS ESPECÍFICOS DO MODAL AÉREO",
        )
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 4
        for i in range(1, 4):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "NÚMERO OPERACIONAL AÉREO",
            "CLASSE",
            "CÓDIGO DA TARIFA",
            "VALOR DA TARIFA",
        ]

        road_values = [
            f"{self.nOCA}",
            f"{self.CL}",
            f"{self.cTar}",
            f"R$ {self.vTar}",
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        section_start_y = self.get_y() + 10
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 3
        for i in range(1, 3):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "NÚMERO DA MINUTA",
            "RETIRA",
            "DADOS RELATIVOS A RETIRADA DA CARGA",
        ]

        road_values = [
            f"{self.nMinu}",
            "",
            "",
        ]

        text_y = section_start_y - 12
        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            x_pos = x_margin + i * col_width
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            if i == 1:
                square_size = 3
                self.rect(x=x_pos + 10, y=text_y + 4, w=square_size, h=square_size)
                self.set_xy(x=x_pos + 14, y=text_y + 3.8)
                self.multi_cell(w=10, h=3, text="SIM", border=0, align="L")

                self.rect(x=x_pos + 25, y=text_y + 4, w=square_size, h=square_size)
                self.set_xy(x=x_pos + 29, y=text_y + 3.8)
                self.multi_cell(w=10, h=3, text="NÃO", border=0, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        section_start_y = self.get_y() + 10
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 3.3
        for i in range(1, 4):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "CARACTERÍSTICAS ADICIONAL DO SERVIÇO",
            "DATA PREVISTA DA ENTREGA",
            "INFORMAÇÕES DE MANUSEIO",
            "DIMENSÃO",
        ]

        road_values = [
            "",
            f"{self.dPrevAereo}",
            f"{self.cInfManu}",
            f"{self.xDime}",
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            if i == 3:
                self.set_font(self.default_font, "B", 6)
            else:
                self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        self.set_font(self.default_font, "", 7)
        section_start_y = self.get_y()
        section_start_y = self.draw_section(
            section_start_y, 3, "USO EXCLUSIVO DO EMISSOR DO CT-E"
        )
        self.set_margins(
            left=self.content_l_margin,
            top=config.margins.top,
            right=config.margins.right,
        )
        margins_to_height = {
            2: 15,
            3: 14,
            4: 12,
            5: 11,
            6: 8,
            7: 6,
            8: 4,
            9: 2,
            10: 8,
        }
        if self.orientation == "L":
            # Caixa calculada até a margem inferior (como no rodoviário) —
            # a tabela margins_to_height é calibrada para o A4 em pé.
            rect_height = self.h - config.margins.bottom - section_start_y
        else:
            rect_height = margins_to_height[config.margins.left]

        self.rect(
            x=x_margin,
            y=section_start_y,
            w=page_width - 0.1 * self._base_l_margin,
            h=rect_height,
            style="",
        )

    def draw_ferroviario_info(self, config):
        x_margin = self.l_margin
        page_width = self.epw

        self.tpTraf = TP_TRAFICO[extract_text(self.inf_modal, "tpTraf")]
        self.fluxo = extract_text(self.inf_modal, "fluxo")
        self.vFrete = format_number(extract_text(self.inf_modal, "vFrete"), precision=2)
        self.ferrEmi = TP_FERROV_EMITENTE.get(
            extract_text(self.inf_modal, "ferrEmi"), ""
        )
        self.respFat = RESP_FATURAMENTO.get(extract_text(self.inf_modal, "respFat"), "")

        self.inf_ferroviario1 = []
        self.inf_ferroviario2 = []

        for i, ferrov in enumerate(self.ferrov):
            cnpj = extract_text(ferrov, "CNPJ")
            cInt = extract_text(ferrov, "cInt")
            ie = extract_text(ferrov, "IE")
            xNome = extract_text(ferrov, "xNome")

            if xNome:
                if i % 2 == 0:
                    self.inf_ferroviario1.append(
                        {
                            "cnpj": cnpj if cnpj else "00.000.000/0000-00",
                            "cInt": cInt if cInt else " ",
                            "ie": ie if ie else " ",
                            "xNome": xNome if xNome else " ",
                        }
                    )
                else:
                    self.inf_ferroviario2.append(
                        {
                            "cnpj": cnpj if cnpj else "00.000.000/0000-00",
                            "cInt": cInt if cInt else " ",
                            "ie": ie if ie else " ",
                            "xNome": xNome if xNome else " ",
                        }
                    )

        # Em paisagem o título encosta na caixa anterior (self.y já está no
        # fundo dela); o respiro de 7mm é só do retrato.
        section_start_y = self.get_y() + (0 if self.orientation == "L" else 7)
        section_start_y = self.draw_section(
            section_start_y,
            13,
            "INFORMAÇÕES ESPECÍFICAS DO MODAL FERROVIÁRIO",
        )
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 5
        for i in range(1, 5):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "TIPO DE TRÁFICO",
            "FLUXO FERROVIÁRIO",
            "VALOR DO FRETE",
            "FERROVIA EMITENTE DO CT-E",
            "FERROVIA DO FATURAMENTO",
        ]

        road_values = [
            f"{self.tpTraf}",
            f"{self.fluxo}",
            f"R$ {self.vFrete}",
            f"{self.ferrEmi}",
            f"{self.respFat}",
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        section_start_y = self.get_y()
        section_start_y = self.draw_section(
            section_start_y,
            13,
            "INFORMAÇÕES DAS FERROVIARIAS ENVOLVIDAS",
        )
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 4
        for i in range(1, 4):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "CNPJ",
            "COD. INTERNO",
            "IE",
            "RAZÃO SOCIAL",
        ]

        if self.inf_ferroviario1:
            ferro1 = self.inf_ferroviario1[0]
        else:
            ferro1 = {
                "cnpj": "00.000.000/0000-00",
                "cInt": " ",
                "ie": " ",
                "xNome": " ",
            }

        road_values = [
            ferro1["cnpj"],
            ferro1["cInt"],
            ferro1["ie"],
            ferro1["xNome"],
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        section_start_y = self.get_y() + 10
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 4
        for i in range(1, 4):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        if self.inf_ferroviario2:
            ferro2 = self.inf_ferroviario2[0]
        else:
            ferro2 = {
                "cnpj": "00.000.000/0000-00",
                "cInt": " ",
                "ie": " ",
                "xNome": " ",
            }

        road_values = [
            ferro2["cnpj"],
            ferro2["cInt"],
            ferro2["ie"],
            ferro2["xNome"],
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        self.set_font(self.default_font, "", 7)
        section_start_y = self.get_y()
        section_start_y = self.draw_section(
            section_start_y, 3, "USO EXCLUSIVO DO EMISSOR DO CT-E"
        )
        self.set_margins(
            left=self.content_l_margin,
            top=config.margins.top,
            right=config.margins.right,
        )
        margins_to_height = {
            2: 12,
            3: 11,
            4: 10,
            5: 9,
            6: 8,
            7: 8,
            8: 7,
            9: 6,
            10: 5,
        }
        if self.orientation == "L":
            # Caixa calculada até a margem inferior (como no rodoviário) —
            # a tabela margins_to_height é calibrada para o A4 em pé.
            rect_height = self.h - config.margins.bottom - section_start_y
        else:
            rect_height = margins_to_height[config.margins.left]

        self.rect(
            x=x_margin,
            y=section_start_y,
            w=page_width - 0.1 * self._base_l_margin,
            h=rect_height,
            style="",
        )

    def draw_aquaviario_info(self, config):
        x_margin = self.l_margin
        page_width = self.epw
        self.nLacre = extract_text(self.inf_modal, "nLacre")
        self.nCont = extract_text(self.inf_modal, "nCont")
        self.xNavio = extract_text(self.inf_modal, "xNavio")
        self.vAFRMM = format_number(extract_text(self.inf_modal, "vAFRMM"), precision=2)

        self.balsas = []
        for balsa in self.aquav:
            xBalsa = extract_text(balsa, "xBalsa")
            if xBalsa:
                self.balsas.append(xBalsa)

        # Em paisagem o título encosta na caixa anterior (self.y já está no
        # fundo dela); o respiro de 7mm é só do retrato.
        section_start_y = self.get_y() + (0 if self.orientation == "L" else 7)
        section_start_y = self.draw_section(
            section_start_y,
            13,
            "INFORMAÇÕES ESPECÍFICAS DO MODAL AQUAVIÁRIO",
        )
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 2
        for i in range(1, 2):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "LACRE",
            "IDENTIFICAÇÃO DO CONTAINER",
        ]

        road_values = [
            f"{self.nLacre}",
            f"{self.nCont}",
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        section_start_y = self.get_y()
        section_start_y = self.draw_section(
            section_start_y,
            13,
            "INFORMAÇÕES ESPECÍFICAS DO MODAL AQUAVIÁRIO",
        )
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 3
        for i in range(1, 3):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "IDENTIFICAÇÃO DO NAVIO / REBOCADOR",
            "IDENTIFICAÇÃO DA BALSA",
            "VLR DO AFRMM",
        ]

        road_values = [
            f"{self.xNavio}",
            f"{' '.join(self.balsas)}",
            f"R$ {self.vAFRMM}",
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            if i == 3:
                self.set_font(self.default_font, "B", 6)
            else:
                self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        self.set_font(self.default_font, "", 7)
        section_start_y = self.get_y()
        section_start_y = self.draw_section(
            section_start_y, 3, "USO EXCLUSIVO DO EMISSOR DO CT-E"
        )
        self.set_margins(
            left=self.content_l_margin,
            top=config.margins.top,
            right=config.margins.right,
        )
        margins_to_height = {
            2: 18,
            3: 17,
            4: 15,
            5: 14,
            6: 12,
            7: 11,
            8: 10,
            9: 9,
            10: 9,
        }
        if self.orientation == "L":
            # Caixa calculada até a margem inferior (como no rodoviário) —
            # a tabela margins_to_height é calibrada para o A4 em pé.
            rect_height = self.h - config.margins.bottom - section_start_y
        else:
            rect_height = margins_to_height[config.margins.left]

        self.rect(
            x=x_margin,
            y=section_start_y,
            w=page_width - 0.1 * self._base_l_margin,
            h=rect_height,
            style="",
        )

    def draw_multimodal_info(self, config):
        x_margin = self.l_margin
        page_width = self.epw

        self.COTM = extract_text(self.inf_modal, "COTM")
        self.xSeg = extract_text(self.inf_modal, "xSeg")
        self.CNPJ = extract_text(self.inf_modal, "CNPJ")
        self.nApol = extract_text(self.inf_modal, "nApol")
        self.nAver = extract_text(self.inf_modal, "nAver")

        # Em paisagem o título encosta na caixa anterior (self.y já está no
        # fundo dela); o respiro de 7mm é só do retrato.
        section_start_y = self.get_y() + (0 if self.orientation == "L" else 7)
        section_start_y = self.draw_section(
            section_start_y,
            13,
            "INFORMAÇÕES E ESPECIFICAÇÕES DO TRANSPORTE MULTIMODAL DE CAMADAS",
        )
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 2
        for i in range(1, 2):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "Nº DO CERTIFICADO DO OPERADOR DE TRANSPORTE MULTIMODAL",
            "INDICADOR NEGOCIÁVEL",
        ]

        road_values = [
            f"{self.COTM}",
            "",
        ]

        text_y = section_start_y - 12
        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            x_pos = x_margin + i * col_width
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            if i == 1:
                square_size = 3
                self.rect(x=x_pos + 10, y=text_y + 4.5, w=square_size, h=square_size)
                self.set_xy(x=x_pos + 13, y=text_y + 4.5)
                self.multi_cell(w=30, h=3, text="NEGOCIÁVEL", border=0, align="L")

                self.rect(x=x_pos + 35, y=text_y + 4.5, w=square_size, h=square_size)
                self.set_xy(x=x_pos + 38, y=text_y + 4.5)
                self.multi_cell(w=30, h=3, text="NÃO NEGOCIÁVEL", border=0, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        section_start_y = self.get_y() + 10
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 4
        for i in range(1, 4):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "CNPJ DA SEGURADO",
            "NOME DA SEGURADO",
            "NÚMERO DA APÓLICE",
            "NÚMERO DE AVERBAÇÃO",
        ]

        road_values = [
            f"{self.CNPJ}",
            f"{self.xSeg}",
            f"{self.nApol}",
            f"{self.nAver}",
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        self.set_font(self.default_font, "", 7)
        section_start_y = self.get_y()
        section_start_y = self.draw_section(
            section_start_y, 3, "USO EXCLUSIVO DO EMISSOR DO CT-E"
        )
        self.set_margins(
            left=self.content_l_margin,
            top=config.margins.top,
            right=config.margins.right,
        )
        margins_to_height = {
            2: 21,
            3: 20,
            4: 18,
            5: 17,
            6: 15,
            7: 14,
            8: 13,
            9: 12,
            10: 11,
        }
        if self.orientation == "L":
            # Caixa calculada até a margem inferior (como no rodoviário) —
            # a tabela margins_to_height é calibrada para o A4 em pé.
            rect_height = self.h - config.margins.bottom - section_start_y
        else:
            rect_height = margins_to_height[config.margins.left]

        self.rect(
            x=x_margin,
            y=section_start_y,
            w=page_width - 0.1 * self._base_l_margin,
            h=rect_height,
            style="",
        )

    def draw_dutoviario_info(self, config):
        x_margin = self.l_margin
        page_width = self.epw

        # Em paisagem o título encosta na caixa anterior (self.y já está no
        # fundo dela); o respiro de 7mm é só do retrato.
        section_start_y = self.get_y() + (0 if self.orientation == "L" else 7)
        section_start_y = self.draw_section(
            section_start_y,
            13,
            "DADOS ESPECÍFICOS DO MODAL DUTOVIÁRIO",
        )
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 5
        for i in range(1, 5):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "VALOR UNITÁRIO",
            "VALOR DO FRETE",
            "OUTROS",
            "BASE DE CÁLCULO",
            "ALÍQUOTA",
        ]

        road_values = [
            "",
            "",
            "",
            f"{self.vbc}",
            f"{self.p_icms}",
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        section_start_y = self.get_y() + 10
        self.rect(
            x=x_margin,
            y=section_start_y - 10,
            w=page_width - 0.1 * self._base_l_margin,
            h=6,
            style="",
        )

        col_width = (page_width - 2 * x_margin) / 6
        for i in range(1, 6):
            x_line = x_margin + i * col_width
            self.line(
                x1=x_line,
                x2=x_line,
                y1=section_start_y - 10,
                y2=section_start_y - 4,
            )

        self.set_font(self.default_font, "", 6)
        road_titles = [
            "VALOR DO IMPOSTO",
            "VALOR TOTAL DO FRETE",
            "OBSERVAÇÕES",
            "SÉRIE",
            "NÚMERO",
            "EMITENTE",
        ]

        road_values = [
            "",
            f"R$ {self.v_tpprest}",
            "",
            f"{self.serie_cte}",
            f"{self.nr_dacte}",
            f"{self.emit_name}",
        ]

        for i, (title, value) in enumerate(zip(road_titles, road_values)):
            self.set_xy(x_margin + i * col_width, section_start_y - 10)
            self.multi_cell(w=col_width, h=3, text=title, align="L")
            if i == 5:
                self.set_font(self.default_font, "B", 6)
            else:
                self.set_font(self.default_font, "B", 7)
            self.set_xy(x_margin + i * col_width, section_start_y - 7)
            self.multi_cell(w=col_width, h=3, text=value, align="L")
            self.set_font(self.default_font, "", 6)

        self.set_font(self.default_font, "", 7)
        section_start_y = self.get_y()
        section_start_y = self.draw_section(
            section_start_y, 3, "USO EXCLUSIVO DO EMISSOR DO CT-E"
        )
        self.set_margins(
            left=self.content_l_margin,
            top=config.margins.top,
            right=config.margins.right,
        )
        margins_to_height = {
            2: 20,
            3: 19,
            4: 17,
            5: 16,
            6: 13,
            7: 11,
            8: 11,
            9: 9,
            10: 8,
        }
        if self.orientation == "L":
            # Caixa calculada até a margem inferior (como no rodoviário) —
            # a tabela margins_to_height é calibrada para o A4 em pé.
            rect_height = self.h - config.margins.bottom - section_start_y
        else:
            rect_height = margins_to_height[config.margins.left]

        self.rect(
            x=x_margin,
            y=section_start_y,
            w=page_width - 0.1 * self._base_l_margin,
            h=rect_height,
            style="",
        )

    def _draw_specific_data(self, config):
        x_margin = self.l_margin
        page_width = self.epw
        self.tp_modal = ModalType(TP_MODAL[extract_text(self.ide, "modal")])
        if self.tp_modal == ModalType.RODOVIARIO:
            is_landscape = self.orientation == "L"
            # Mesmo motivo do _draw_documents_obs: em paisagem sobra bem
            # menos altura de página, então estas duas últimas seções também
            # usam um orçamento vertical reduzido para caber na página.
            # 9mm: o rótulo longo da 4ª coluna ocupa 3 linhas × 3mm.
            modal_h = 9 if is_landscape else 10
            modal_budget = modal_h + 3
            # Em paisagem self.y já está no fundo da caixa de OBSERVAÇÕES
            # (ver _draw_documents_obs) — o título encosta nela.
            section_start_y = self.get_y() + (0 if is_landscape else 7)
            section_start_y = self.draw_section(
                section_start_y,
                modal_budget,
                "DADOS ESPECÍFICOS DO MODAL RODOVIÁRIO - CARGA FRACIONADA",
            )
            self.rect(
                x=x_margin,
                y=section_start_y - modal_h,
                w=page_width - 0.1 * self._base_l_margin,
                h=modal_h,
                style="",
            )

            col_width = (page_width - 2 * x_margin) / 4
            for i in range(1, 4):
                x_line = x_margin + i * col_width
                self.line(
                    x1=x_line,
                    x2=x_line,
                    y1=section_start_y - modal_h,
                    y2=section_start_y,
                )

            # Em paisagem a coluna é mais estreita: fonte 6 faz o rótulo
            # longo ("ESTE CONHECIMENTO...") caber em 2 linhas dentro da
            # caixa de 7mm, em vez de 3 linhas vazando por baixo dela.
            title_font_size = 6 if is_landscape else 7
            self.set_font(self.default_font, "", title_font_size)
            road_titles = [
                "RNTRC DA EMPRESA",
                "CIOT",
                "DATA PREVISTA DE ENTREGA",
                "ESTE CONHECIMENTO DE TRANSPORTE ATENDE "
                "À LEGISLAÇÃO DE TRANSPORTE RODOVIÁRIO EM VIGOR",
            ]

            road_values = [
                f"{self.rntrc}",
                "",
                "",
                "",
            ]

            for i, (title, value) in enumerate(zip(road_titles, road_values)):
                self.set_xy(x_margin + i * col_width, section_start_y - modal_h)
                self.multi_cell(w=col_width, h=3, text=title, align="L")
                self.set_font(self.default_font, "B", 7)
                self.set_xy(x_margin + i * col_width, section_start_y - modal_h + 3)
                self.multi_cell(w=col_width, h=3, text=value, align="L")
                self.set_font(self.default_font, "", 6)

            self.set_font(self.default_font, "", 7)
            uso_budget = 3 if is_landscape else 18
            section_start_y = self.draw_section(
                section_start_y,
                uso_budget,
                "USO EXCLUSIVO DO EMISSOR DO CT-E",
            )
            self.set_margins(
                left=self.content_l_margin,
                top=config.margins.top,
                right=config.margins.right,
            )
            margins_to_height = {
                2: 23,
                3: 22,
                4: 20,
                5: 18,
                6: 16,
                7: 14,
                8: 12,
                9: 10,
                10: 8,
            }
            if is_landscape:
                # Caixa logo abaixo do título (que aqui termina exatamente
                # em section_start_y, pois uso_budget == 3 == altura da
                # barra), preenchendo o que resta da página.
                rect_y = section_start_y
                rect_height = self.h - config.margins.bottom - rect_y
            else:
                rect_y = section_start_y - 15
                rect_height = margins_to_height[config.margins.left]

            if rect_height > 0:
                self.rect(
                    x=x_margin,
                    y=rect_y,
                    w=page_width - 0.1 * self._base_l_margin,
                    h=rect_height,
                    style="",
                )
        if self.tp_modal == ModalType.AEREO:
            self.draw_aereo_info(config)
        if self.tp_modal == ModalType.AQUAVIARIO:
            self.draw_aquaviario_info(config)
        if self.tp_modal == ModalType.FERROVIARIO:
            self.draw_ferroviario_info(config)
        if self.tp_modal == ModalType.DUTOVIARIO:
            self.draw_dutoviario_info(config)
        if self.tp_modal == ModalType.MULTIMODAL:
            self.draw_multimodal_info(config)

    # Adicionando outra página
    def _add_new_page(self, config):
        x_margin = self.l_margin
        page_width = self.epw
        line_height = 4

        add_new_page = (
            self.page_lines > 0 and self.page_lines % self.max_lines_per_page == 0
        ) or self.text_exceeds_limit

        if add_new_page:
            self.add_page(orientation=self.orientation)
            if self.receipt_pos == ReceiptPosition.LEFT:
                self._draw_landscape_receipt()
            else:
                self._draw_receipt()
            self._draw_header()
        if self.page_lines > 0 and self.page_lines % self.max_lines_per_page == 0:
            # Em paisagem o título encosta no fundo do cabeçalho, como as
            # demais seções; o respiro de 2.5mm é só do retrato.
            section_start_y = self.get_y() + (0 if self.orientation == "L" else 2.5)
            section_start_y = self.draw_section(
                section_start_y, 43, "DOCUMENTOS ORIGINÁRIOS"
            )
            y_offset_left = section_start_y - 33
            y_offset_right = section_start_y - 33
            current_line_left = 0
            current_line_right = 0
            in_right_block = False

            self.set_font(self.default_font, "", 7)
            # Mesma correção do _draw_documents_obs: em paisagem a divisória
            # fica no meio real da caixa.
            box_w = page_width - 0.1 * self._base_l_margin
            col_width = (
                box_w / 2
                if self.orientation == "L"
                else (page_width - 2 * x_margin) / 2
            )
            half_col_width = col_width / 3
            x_line_middle = x_margin + col_width

            total_documents = len(self.inf_doc_list) - self.page_lines
            lines_per_column = (total_documents + 1) // 2
            if self.orientation == "L":
                # Altura pela coluna mais cheia: com total ímpar a coluna
                # esquerda tem uma linha a mais, que a fórmula do retrato
                # (total*h//2) deixa para fora da caixa.
                rectangle_height = lines_per_column * line_height
            else:
                rectangle_height = total_documents * line_height // 2
            self.rect(
                x=x_margin,
                y=section_start_y - 40,
                w=page_width - 0.1 * self._base_l_margin,
                h=rectangle_height + 8,
            )
            self.line(
                x1=x_line_middle,
                x2=x_line_middle,
                y1=section_start_y - 40,
                y2=section_start_y - 32 + rectangle_height,
            )

            self.set_font(self.default_font, "", 6)
            self.set_xy(x_margin, section_start_y - 37)
            self.multi_cell(w=half_col_width, h=0, text="TIPO DOC", align="L")
            self.set_xy(x_margin + half_col_width - 18, section_start_y - 37)
            self.multi_cell(w=half_col_width, h=0, text="CNPJ/CHAVE", align="L")
            self.set_xy(x_margin + 2 * half_col_width, section_start_y - 37)
            self.set_font(self.default_font, "", 5.5)
            self.multi_cell(
                w=half_col_width, h=0, text="SÉRIE/NRO. DOCUMENTO", align="L"
            )

            self.set_font(self.default_font, "", 6)
            self.set_xy(x_line_middle, section_start_y - 37)
            self.multi_cell(w=half_col_width, h=0, text="TIPO DOC", align="L")
            self.set_xy(x_line_middle + half_col_width - 20, section_start_y - 37)
            self.multi_cell(w=half_col_width, h=0, text="CNPJ/CHAVE", align="L")
            self.set_xy(x_line_middle + 2 * half_col_width, section_start_y - 37)
            self.set_font(self.default_font, "", 5.5)
            self.multi_cell(
                w=half_col_width, h=0, text="SÉRIE/NRO. DOCUMENTO", align="L"
            )

            for i, chave in enumerate(self.inf_doc_list):
                if i < self.page_lines:
                    continue

                if current_line_left == lines_per_column:
                    current_line_left = 0
                    in_right_block = True
                    self.set_xy(x_line_middle, y_offset_right)

                if in_right_block:
                    x_start = x_line_middle
                    y_offset = y_offset_right
                else:
                    x_start = x_margin
                    y_offset = y_offset_left

                self.set_xy(x_start, y_offset)
                self.set_font(self.default_font, "B", 6)
                self.multi_cell(w=half_col_width, h=line_height, text="NFE", align="L")

                self.set_xy(x_start + half_col_width - 20, y_offset)
                self.multi_cell(
                    w=half_col_width + 23, h=line_height, text=chave, align="L"
                )

                key_nfe_1 = chave[22:25]
                key_nfe_2 = chave[25:34]
                key_nfe_format = f"{key_nfe_1}/{key_nfe_2}"

                self.set_font(self.default_font, "B", 6)
                self.set_xy(x_start + 2 * half_col_width + 5, y_offset)
                self.multi_cell(
                    w=half_col_width, h=line_height, text=key_nfe_format, align="L"
                )

                y_offset += line_height
                if in_right_block:
                    current_line_right += 1
                    y_offset_right = y_offset
                else:
                    current_line_left += 1
                    y_offset_left = y_offset

            if self.orientation == "L":
                # self.y no fundo real da caixa: o loop termina com self.y
                # no fim da coluna direita, que pode ser mais curta que a
                # esquerda — a seção seguinte partiria de cima do conteúdo.
                self.set_y(section_start_y - 40 + rectangle_height + 8)
        if self.text_exceeds_limit:
            section_start_y = self.get_y() + (0 if self.orientation == "L" else 3)
            self.set_font(self.default_font, "", 7)
            text_width = page_width - 0.1 * self._base_l_margin
            section_start_y = self.draw_section(section_start_y, 18, "OBSERVAÇÕES")
            initial_y = section_start_y - 15

            self.set_xy(x_margin, initial_y)

            self.multi_cell(w=text_width, h=3, text=self.remaining_text, align="L")

            self.set_xy(x_margin, initial_y)
            self.set_margins(
                left=self.content_l_margin,
                top=config.margins.top,
                right=config.margins.right,
            )
            margins_to_height = {
                2: 21,
                3: 19,
                4: 16,
                5: 13,
                6: 10,
                7: 7,
                8: 4,
                9: 2,
                10: -2,
            }
            if self.orientation == "L":
                # Altura calculada: a caixa vai de initial_y até a margem
                # inferior. A fórmula do retrato soma uma coordenada y a uma
                # tabela calibrada para A4 em pé — em paisagem o resultado
                # (~258mm) estoura a página de 210mm.
                rect_height = self.h - config.margins.bottom - initial_y
            else:
                rect_height = section_start_y + margins_to_height[config.margins.left]
            self.rect(x=x_margin, y=initial_y, w=text_width, h=rect_height)

        if add_new_page:
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
