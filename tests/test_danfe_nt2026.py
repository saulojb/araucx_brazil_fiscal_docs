"""
DANFE no leiaute da NT 2026.010 (porte do upstream, pacote abrazilfiscalreport.danfe_nt2026).
Fixtures e PDFs de referência isolados em tests/fixtures|generated/danfe_nt2026.
"""

import warnings
from dataclasses import replace

import pytest

from abrazilfiscalreport.danfe_nt2026 import (
    DanfeConfig,
    DanfeNt2026010,
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
from abrazilfiscalreport.danfe_nt2026 import uses_nt_2026_010
from abrazilfiscalreport.danfe_nt2026.models import LabeledValue
from tests.conftest import assert_pdf_equal, get_pdf_output_path


@pytest.fixture
def load_danfe(load_xml):
    def _load_danfe(filename, config=None):
        xml_content = load_xml(f"danfe_nt2026/{filename}")
        config = config or DanfeConfig()
        if config.font_type is None and config.custom_font is None:
            # As referências em tests/generated/danfe_nt2026 (porte do upstream) são em
            # Times; o padrão deste fork é a Roboto Condensed (testes abaixo).
            config = replace(config, font_type=FontType.TIMES)
        return DanfeNt2026010(xml=xml_content, config=config)

    return _load_danfe


@pytest.fixture(scope="module")
def default_danfe_config(logo_path):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        logo=logo_path,
        receipt_pos=ReceiptPosition.TOP,
    )
    return config


def test_danfe_default(tmp_path, load_danfe):
    danfe = load_danfe("nfe_test_1.xml")
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_default")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_sn(tmp_path, load_danfe):
    """
    Tests the creation of a DANFE for an Electronic Invoice (NF-e) issued by a company
    opting for the Simples Nacional regime.
    """
    danfe = load_danfe("nfe_test_sn.xml")
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_sn")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_minimal(tmp_path, load_danfe):
    minimal_config = DanfeConfig(
        margins=Margins(top=8, right=8, bottom=8, left=8),
        decimal_config=DecimalConfig(price_precision=2, quantity_precision=2),
    )
    danfe = load_danfe("nfe_test_1.xml", config=minimal_config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_minimal")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_multi_page_products_lp(tmp_path, load_danfe, default_danfe_config):
    """
    Tests the creation of a DANFE with more than one page of products in landscape mode.
    """
    danfe = load_danfe(
        "nfe_multi_page_products_landscape.xml", config=default_danfe_config
    )
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_multipage_landscape")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_add_info_below_prod(tmp_path, load_danfe, default_danfe_config):
    """
    Tests the creation of a DANFE where the additional information exceeds the standard
    limit and the continuation is placed below the product table.
    This checks the layout adjustments needed when additional data overflows its usual
    space in the document.
    """
    danfe = load_danfe(
        "nfe_additional_info_continuation_in_product_table.xml",
        config=default_danfe_config,
    )
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_add_info_below_prod")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_add_info_next_page(tmp_path, load_danfe, default_danfe_config):
    """
    Tests the creation of a DANFE where additional information exceeds the available
    space and overflows to the next page. This test ensures that the layout properly
    adjusts to accommodate additional data on a new page when it overflows beyond the
    first page's capacity.
    """
    danfe = load_danfe(
        "nfe_additional_info_continuation_in_next_page.xml", config=default_danfe_config
    )
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_add_info_next_page")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_overload(tmp_path, load_danfe, default_danfe_config, logo_path):
    overload_config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        logo=logo_path,
        receipt_pos=ReceiptPosition.BOTTOM,
        decimal_config=DecimalConfig(price_precision=6, quantity_precision=6),
        tax_configuration=TaxConfiguration.ICMS_ST,
        invoice_display=InvoiceDisplay.FULL_DETAILS,
        font_type=FontType.COURIER,
    )
    danfe = load_danfe("nfe_overload.xml", config=overload_config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_overload")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_duplicatas_only(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        invoice_display=InvoiceDisplay.DUPLICATES_ONLY,
    )
    danfe = load_danfe("nfe_overload.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_duplicatas_only")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_pis_config(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        display_pis_cofins=True,
    )
    danfe = load_danfe("nfe_test_1.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_pis_confins")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_product_description_with_branch(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(
            display_branch=True,
            display_additional_info=False,
        ),
    )
    danfe = load_danfe("nfe_test_branch.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_branch")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_product_description_with_branch_prefix(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(
            display_branch=True, branch_info_prefix="=>"
        ),
    )
    danfe = load_danfe("nfe_test_branch.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_branch_with_prefix")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_product_description_with_anp(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(
            display_anp=True,
            display_additional_info=False,
        ),
    )
    danfe = load_danfe("nfe_test_anp.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_anp")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_product_description_with_anvisa(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(
            display_anvisa=True,
            display_additional_info=False,
        ),
    )
    danfe = load_danfe("nfe_test_anvisa.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_anvisa")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_product_description_with_xped(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(display_xped=True),
    )
    danfe = load_danfe("nfe_xped.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_xped")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


@pytest.mark.parametrize(
    "display_xped, n_item_ped, line",
    [
        (True, "<nItemPed>10</nItemPed>", "Pedido: 4500012345 Item: 10"),
        (True, "", "Pedido: 4500012345"),
        (False, "<nItemPed>10</nItemPed>", None),
    ],
)
def test_danfe_xped_in_description(load_xml, display_xped, n_item_ped, line):
    """The purchase order (xPed and nItemPed) is printed only when enabled."""
    xml = load_xml("danfe_nt2026/nfe_xped.xml").replace("<nItemPed>10</nItemPed>", n_item_ped)
    config = DanfeConfig(
        product_description_config=ProductDescriptionConfig(display_xped=display_xped),
    )
    lines = DanfeNt2026010(xml=xml, config=config).products[0].description.splitlines()
    if line:
        assert line in lines
    else:
        assert not [text for text in lines if text.startswith("Pedido:")]


def test_danfe_with_production_environment(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        watermark_cancelled=True,
        product_description_config=ProductDescriptionConfig(
            display_anvisa=True,
            display_additional_info=False,
        ),
    )
    danfe = load_danfe("nfe_with_production_environment.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_with_production_environment")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_without_production_environment(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        watermark_cancelled=True,
        product_description_config=ProductDescriptionConfig(
            display_anvisa=True,
            display_additional_info=False,
        ),
    )
    danfe = load_danfe("nfe_without_production_environment.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_without_production_environment")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_default_production(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(
            display_anvisa=True,
            display_additional_info=False,
        ),
    )
    danfe = load_danfe("nfe_with_production_environment.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_default_production")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_reforma_tributaria(tmp_path, load_danfe):
    danfe = load_danfe("nfe_reforma_tributaria.xml")
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_reforma_tributaria")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_rtc(tmp_path, load_danfe):
    """
    Layout of NT 2026.010: CRT in the header, IBS/CBS/IS totals, optional
    FCP/DIFAL and single-phase totals, ISSQN, item taxes (regular and
    effective rates, IS, IPI, exempt and service items) and QR Code.
    """
    danfe = load_danfe("nfe_rtc.xml")
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_rtc")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_rtc_landscape(tmp_path, load_xml):
    xml = load_xml("danfe_nt2026/nfe_rtc.xml").replace("<tpImp>1</tpImp>", "<tpImp>2</tpImp>")
    danfe = DanfeNt2026010(xml=xml, config=DanfeConfig(font_type=FontType.TIMES))
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_rtc_landscape")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


@pytest.mark.parametrize(
    "tp_imp, orientation",
    [
        ("0", "P"),
        ("1", "P"),
        ("2", "L"),
        ("3", "P"),
        ("4", "P"),
        ("5", "P"),
        ("6", "P"),
    ],
)
def test_danfe_orientation_by_tp_imp(load_xml, tp_imp, orientation):
    """
    Only tpImp=2 is the landscape DANFE; the other formats, including the
    DANFE Simplificado Tipo 2 (tpImp=6), print the regular DANFE in portrait.
    """
    xml = load_xml("danfe_nt2026/nfe_rtc.xml").replace(
        "<tpImp>1</tpImp>", f"<tpImp>{tp_imp}</tpImp>"
    )
    assert DanfeNt2026010(xml=xml).orientation == orientation


@pytest.mark.parametrize(
    "issue_date, usa_nt",
    [
        ("<dhEmi>2026-11-30T23:59:59-03:00</dhEmi>", False),
        ("<dhEmi>2026-12-01T00:00:00-03:00</dhEmi>", True),
        # ainda é 30/11/2026 em Brasília
        ("<dhEmi>2026-12-01T02:59:59+00:00</dhEmi>", False),
        # sem fuso, vale o horário de Brasília
        ("<dhEmi>2026-12-01T00:00:00</dhEmi>", True),
        # dEmi dos leiautes anteriores à 3.10
        ("<dEmi>2026-11-30</dEmi>", False),
    ],
)
def test_uses_nt_2026_010_by_issue_date(load_xml, issue_date, usa_nt):
    xml = load_xml("danfe_nt2026/nfe_rtc.xml").replace(
        "<dhEmi>2026-12-01T10:00:00-03:00</dhEmi>", issue_date
    )
    assert uses_nt_2026_010(xml) is usa_nt


def test_uses_nt_2026_010_samples(load_xml):
    assert uses_nt_2026_010(load_xml("danfe_nt2026/nfe_test_1.xml")) is False
    assert uses_nt_2026_010(load_xml("danfe_nt2026/nfe_rtc.xml")) is True


def test_danfe_rtc_big_font_size(tmp_path, load_danfe):
    """
    With the big font the item taxes no longer fit two per line, so they are
    printed one per line.
    """
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        font_size=FontSize.BIG,
    )
    danfe = load_danfe("nfe_rtc.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_rtc_big_font_size")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_rtc_item_taxes(load_danfe):
    products = load_danfe("nfe_rtc.xml").products

    # regular rates
    assert products[0].tax_bases == [
        LabeledValue("ICMS", "250,00"),
        LabeledValue("IBS / CBS", "250,00"),
        LabeledValue("IPI", "250,00"),
    ]
    assert products[0].tax_rates == (
        [
            LabeledValue("ICMS", "12,00%"),
            LabeledValue("IBS UF", "0,10%"),
            LabeledValue("IBS MUN", "0,00%"),
        ],
        [LabeledValue("CBS", "0,90%"), LabeledValue("IPI", "5,00%")],
    )
    # with gRed the effective rate (pAliqEfet) is printed
    assert products[1].tax_rates == (
        [
            LabeledValue("ICMS", "12,00%"),
            LabeledValue("IBS UF", "0,04%"),
            LabeledValue("IBS MUN", "0,00%"),
        ],
        [LabeledValue("CBS", "0,36%"), LabeledValue("IS", "10,00%")],
    )
    assert products[1].tax_values == (
        [
            LabeledValue("ICMS", "38,40"),
            LabeledValue("IBS UF", "0,21"),
            LabeledValue("IBS MUN", "0,00"),
        ],
        [LabeledValue("CBS", "1,90"), LabeledValue("IS", "48,00")],
    )
    # single-phase ICMS and IBS/CBS, then an exempt item: nothing to print
    for product in products[2:4]:
        assert product.tax_bases == []
        assert product.tax_rates == ([], [])
        assert product.tax_values == ([], [])
    assert products[3].description.endswith("[NCM 49019900] [cClassTrib 410001]")
    # service item: no ICMS group, so no CST
    assert products[4].cst_cfop == [LabeledValue("CFOP", "6933")]


def test_danfe_rtc_totals(load_danfe):
    danfe = load_danfe("nfe_rtc.xml")
    assert len(danfe._get_icms_ipi_lines()) == 3
    assert danfe._get_ibs_cbs_is_lines() == [
        [
            ("VALOR DA CBS", "6,85"),
            ("VALOR DO IBS UF", "0,76"),
            ("VALOR DO IBS MUNICÍPIO", "0,00"),
            ("VALOR DO IMPOSTO SELETIVO", "48,00"),
        ],
        [
            ("VALOR DO IBS MONOFÁSICO", "2,50"),
            ("VALOR DA CBS MONOFÁSICA", "22,50"),
            ("VALOR DO IBS MONOFÁSICO POR RETENÇÃO", "0,00"),
            ("VALOR DA CBS MONOFÁSICA POR RETENÇÃO", "0,00"),
        ],
    ]


def test_danfe_without_rtc_totals(load_danfe):
    """
    Information absent from the XML is left blank instead of printed as
    zero, and the optional lines are omitted (NT 2026.010, item 4.4).
    """
    danfe = load_danfe("nfe_test_1.xml")
    assert len(danfe._get_icms_ipi_lines()) == 1
    assert danfe._get_ibs_cbs_is_lines() == [
        [
            ("VALOR DA CBS", ""),
            ("VALOR DO IBS UF", ""),
            ("VALOR DO IBS MUNICÍPIO", ""),
            ("VALOR DO IMPOSTO SELETIVO", ""),
        ]
    ]


def test_danfe_big_font_size(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(
            display_anvisa=True,
            display_additional_info=False,
            display_branch=True,
            branch_info_prefix="=>",
            display_anp=True,
        ),
        decimal_config=DecimalConfig(
            price_precision=3,
            quantity_precision=2,
        ),
        font_size=FontSize.BIG,
    )
    danfe = load_danfe("nfe_big_font_size.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_big_font_size")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_infcpl_semicolon_newline(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(
            display_anvisa=True,
            display_additional_info=False,
            display_branch=True,
            branch_info_prefix="=>",
            display_anp=True,
        ),
        decimal_config=DecimalConfig(
            price_precision=3,
            quantity_precision=2,
        ),
        font_size=FontSize.BIG,
        infcpl_semicolon_newline=True,
    )
    danfe = load_danfe("nfe_semicolon_line_break.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_infcpl_semicolon_newline")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_mei(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        product_description_config=ProductDescriptionConfig(
            display_anvisa=True,
            display_additional_info=False,
            display_branch=True,
            branch_info_prefix="=>",
            display_anp=True,
        ),
        decimal_config=DecimalConfig(
            price_precision=3,
            quantity_precision=2,
        ),
        font_size=FontSize.BIG,
        infcpl_semicolon_newline=True,
    )
    danfe = load_danfe("nfe_mei.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_mei")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_footer_stamp(tmp_path, load_danfe, logo_path):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        footer_stamp=FooterStamp(logo=logo_path, text="Powered by"),
    )
    danfe = load_danfe("nfe_test_1.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_footer_stamp")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_footer_stamp_text_only(tmp_path, load_danfe):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        footer_stamp=FooterStamp(text="Powered by Engenere"),
    )
    danfe = load_danfe("nfe_test_1.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_footer_stamp_text_only")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_footer_stamp_logo_only(tmp_path, load_danfe, logo_path):
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        footer_stamp=FooterStamp(logo=logo_path),
    )
    danfe = load_danfe("nfe_test_1.xml", config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_footer_stamp_logo_only")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_footer_stamp_multipage(tmp_path, load_danfe, logo_path):
    """
    Footer stamp must appear on all pages, including continuation pages for
    products and for additional data.
    """
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        footer_stamp=FooterStamp(logo=logo_path, text="Powered by"),
    )
    danfe = load_danfe(
        "nfe_additional_info_continuation_in_next_page.xml", config=config
    )
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_footer_stamp_multipage")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_default_footer_stamp_emits_no_warning():
    """
    A default (empty) FooterStamp must not emit any warning, even when the
    bottom margin is small.
    """
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
    )
    with open("tests/fixtures/danfe/nfe_test_1.xml", encoding="utf8") as f:
        xml = f.read()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        DanfeNt2026010(xml=xml, config=config)


def test_danfe_retirada(tmp_path, load_danfe):
    """
    Tests the creation of a DANFE for an NF-e that has only the pickup
    location group (retirada), without the delivery location group (entrega).
    """
    danfe = load_danfe("nfe_retirada.xml")
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_retirada")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_retirada_entrega(tmp_path, load_danfe):
    """
    Tests the creation of a DANFE for an NF-e that has both the pickup
    location group (retirada) and the delivery location group (entrega).
    Both blocks must be rendered in the document. Regression test for
    issue #169.
    """
    danfe = load_danfe("nfe_retirada_entrega.xml")
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_retirada_entrega")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_cnpj_alfanumerico(tmp_path, load_danfe):
    danfe = load_danfe("danfe_cnpj_alfanumerico.xml")
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_cnpj_alfanumerico")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


@pytest.mark.parametrize("receipt_pos", [ReceiptPosition.TOP, ReceiptPosition.BOTTOM])
def test_danfe_carrier_receipt(tmp_path, load_danfe, receipt_pos):
    """
    With carrier_receipt enabled and a carrier informed in the NF-e, an extra
    collection receipt (canhoto de coleta) is printed at the page edge, next
    to the delivery receipt (canhoto de entrega). Issue #197.
    """
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        receipt_pos=receipt_pos,
        carrier_receipt=True,
    )
    danfe = load_danfe("nfe_mei.xml", config=config)
    pdf_path = get_pdf_output_path(
        "danfe_nt2026", f"danfe_carrier_receipt_{receipt_pos.value}"
    )
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_carrier_receipt_landscape(tmp_path, load_xml):
    xml = load_xml("danfe_nt2026/nfe_mei.xml").replace("<tpImp>1</tpImp>", "<tpImp>2</tpImp>")
    config = DanfeConfig(
        margins=Margins(top=2, right=2, bottom=2, left=2),
        carrier_receipt=True,
        font_type=FontType.TIMES,
    )
    danfe = DanfeNt2026010(xml=xml, config=config)
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_carrier_receipt_landscape")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_carrier_receipt_without_carrier(tmp_path, load_danfe):
    """
    Without a carrier informed in the NF-e, only the regular receipt is
    printed, even with carrier_receipt enabled.
    """
    danfe = load_danfe("nfe_test_1.xml", config=DanfeConfig(carrier_receipt=True))
    assert danfe.receipt_kinds == ["default"]
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_default")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


# --- Fonte Helvetica/Arial (acrescentada neste fork; o upstream só tem Times e Courier) ---

HELVETICA_CASES = [
    "nfe_test_1.xml",
    "nfe_rtc.xml",
    "nfe_overload.xml",
    "nfe_multi_page_products_landscape.xml",
    "nfe_reforma_tributaria.xml",
    "nfe_retirada_entrega.xml",
    "nfe_test_sn.xml",
]


@pytest.mark.parametrize("filename", HELVETICA_CASES)
def test_danfe_helvetica_font(load_xml, filename):
    """Helvetica é a fonte do PDF e o leiaute segue com o mesmo número de páginas da Times."""
    xml = load_xml(f"danfe_nt2026/{filename}")
    helvetica = DanfeNt2026010(xml, config=DanfeConfig(font_type=FontType.HELVETICA))
    times = DanfeNt2026010(xml, config=DanfeConfig(font_type=FontType.TIMES))
    assert helvetica.default_font == "Helvetica"
    pdf = bytes(helvetica.output())
    assert b"/BaseFont /Helvetica" in pdf
    assert b"Times" not in pdf
    times.output()
    assert helvetica.page == times.page


def test_danfe_helvetica_rtc(tmp_path, load_danfe):
    danfe = load_danfe("nfe_rtc.xml", config=DanfeConfig(font_type=FontType.HELVETICA))
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_helvetica_rtc")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


def test_danfe_helvetica_overload(tmp_path, load_danfe):
    danfe = load_danfe(
        "nfe_overload.xml", config=DanfeConfig(font_type=FontType.HELVETICA)
    )
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_helvetica_overload")
    assert_pdf_equal(danfe, pdf_path, tmp_path)


# --- Orientação forçada (recurso deste fork, usado pela configuração de impressão do e-docs) ---


def test_danfe_forced_orientation(load_xml):
    retrato = load_xml("danfe_nt2026/nfe_test_1.xml")
    paisagem = load_xml("danfe_nt2026/nfe_rtc.xml")
    assert DanfeNt2026010(xml=retrato).orientation == "P"
    cfg = DanfeConfig(forced_orientation=ForcedOrientation.LANDSCAPE)
    assert DanfeNt2026010(xml=retrato, config=cfg).orientation == "L"
    cfg = DanfeConfig(forced_orientation=ForcedOrientation.PORTRAIT)
    land_xml = load_xml("danfe_nt2026/nfe_multi_page_products_landscape.xml")
    assert DanfeNt2026010(xml=land_xml).orientation == "L"
    assert DanfeNt2026010(xml=land_xml, config=cfg).orientation == "P"
    # AUTO (padrão) mantém a regra do XML
    assert DanfeNt2026010(xml=paisagem).orientation == "P"


def test_danfe_forced_orientation_accepts_int(load_xml):
    xml = load_xml("danfe_nt2026/nfe_test_1.xml")
    assert DanfeNt2026010(xml=xml, config=DanfeConfig(forced_orientation=2)).orientation == "L"
    assert DanfeNt2026010(xml=xml, config=DanfeConfig(forced_orientation=1)).orientation == "P"


def test_danfe_forced_landscape_renders(load_xml):
    xml = load_xml("danfe_nt2026/nfe_rtc.xml")
    cfg = DanfeConfig(
        forced_orientation=ForcedOrientation.LANDSCAPE, font_type=FontType.HELVETICA
    )
    pdf = DanfeNt2026010(xml=xml, config=cfg)
    pdf.output()
    assert pdf.w > pdf.h


# --- Fonte padrão do fork: Roboto Condensed empacotada (abrazilfiscalreport/fonts) ---


def test_default_font_is_bundled_roboto_condensed(load_xml):
    from abrazilfiscalreport.fonts import DEFAULT_FONT_NAME, default_font_files

    assert default_font_files() is not None
    danfe = DanfeNt2026010(xml=load_xml("danfe_nt2026/nfe_rtc.xml"))
    assert danfe.default_font == DEFAULT_FONT_NAME
    pdf = bytes(danfe.output())
    assert b"RobotoCondensed" in pdf
    assert b"Times" not in pdf


def test_default_font_falls_back_to_helvetica_without_files(load_xml, monkeypatch):
    monkeypatch.setattr(
        "abrazilfiscalreport.danfe_nt2026.danfe_nt_2026_010.default_font_files",
        lambda: None,
    )
    danfe = DanfeNt2026010(xml=load_xml("danfe_nt2026/nfe_rtc.xml"))
    assert danfe.default_font == "Helvetica"
    danfe.output()


def test_explicit_font_type_beats_default_font(load_xml):
    xml = load_xml("danfe_nt2026/nfe_rtc.xml")
    for font_type, name in ((FontType.TIMES, "Times"), (FontType.HELVETICA, "Helvetica")):
        assert DanfeNt2026010(xml=xml, config=DanfeConfig(font_type=font_type)).default_font == name


def test_custom_font_beats_everything(load_xml):
    from abrazilfiscalreport.danfe_nt2026 import CustomFont
    from abrazilfiscalreport.fonts import DEFAULT_BOLD, DEFAULT_REGULAR

    xml = load_xml("danfe_nt2026/nfe_rtc.xml")
    cfg = DanfeConfig(
        font_type=FontType.TIMES,
        custom_font=CustomFont("Minha", str(DEFAULT_REGULAR), str(DEFAULT_BOLD)),
    )
    assert DanfeNt2026010(xml=xml, config=cfg).default_font == "Minha"


def test_danfe_default_font_rtc(tmp_path, load_xml):
    danfe = DanfeNt2026010(xml=load_xml("danfe_nt2026/nfe_rtc.xml"))
    pdf_path = get_pdf_output_path("danfe_nt2026", "danfe_default_font_rtc")
    assert_pdf_equal(danfe, pdf_path, tmp_path)
