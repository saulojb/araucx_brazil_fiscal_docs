import pytest
from click.testing import CliRunner

from abrazilfiscalreport.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_generate_dacce(runner):
    xml_path = "tests/fixtures/dacce/xml_cce_1.xml"
    result = runner.invoke(cli, ["dacce", xml_path])
    assert result.exit_code == 0, result.output


def test_generate_danfe(runner):
    xml_path = "tests/fixtures/danfe/nfe_test_1.xml"
    result = runner.invoke(cli, ["danfe", xml_path])
    assert result.exit_code == 0, result.output


def test_generate_dacte(runner):
    xml_path = "tests/fixtures/dacte/dacte_test_1.xml"
    result = runner.invoke(cli, ["dacte", xml_path])
    assert result.exit_code == 0, result.output


def test_generate_damdfe(runner):
    xml_path = "tests/fixtures/damdfe/mdf-e_test_1.xml"
    result = runner.invoke(cli, ["damdfe", xml_path])
    assert result.exit_code == 0, result.output
