from abrazilfiscalreport.dacce import DaCCe
from tests.conftest import assert_pdf_equal, get_pdf_output_path


def test_dacce(tmp_path, load_xml, logo_path):
    emitente = {
        "nome": "EMPRESA LTDA",
        "cnpj": "11222333000181",
        "end": "AV. TEST, 100",
        "bairro": "TEST",
        "cep": "88888-88",
        "cidade": "SÃO PAULO",
        "uf": "SP",
        "fone": "(11) 1234-5678",
    }
    xm_content = load_xml("dacce/xml_cce_1.xml")

    pdf_cce = DaCCe(
        xml=xm_content,
        emitente=emitente,
        image=logo_path,
        destinatario_cnpj="99888777000166",
    )
    pdf_path = get_pdf_output_path("dacce", "cce")
    assert_pdf_equal(pdf_cce, pdf_path, tmp_path)


def test_dacce_without_emitente(tmp_path, load_xml):
    xm_content = load_xml("dacce/xml_cce_1.xml")

    pdf_cce = DaCCe(xml=xm_content)
    pdf_path = get_pdf_output_path("dacce", "cce_no_emitente")
    assert_pdf_equal(pdf_cce, pdf_path, tmp_path)


def test_dacce_cte(tmp_path, load_xml):
    """CC-e de CT-e: namespace cte: e lista de infCorrecao (sem xCorrecao)."""
    emitente = {
        "nome": "TRANSPORTADORA TESTE LTDA",
        "end": "Rua Teste, 123",
        "bairro": "Centro",
        "cidade": "Itajaí",
        "uf": "SC",
        "fone": "(47) 3333-4444",
    }
    xm_content = load_xml("dacce/xml_cce_cte_1.xml")

    pdf_cce = DaCCe(xml=xm_content, emitente=emitente)
    pdf_path = get_pdf_output_path("dacce", "cce_cte")
    assert_pdf_equal(pdf_cce, pdf_path, tmp_path)
