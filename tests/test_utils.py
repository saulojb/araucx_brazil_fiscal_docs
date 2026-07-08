import unittest

from abrazilfiscalreport import utils


class TestUtils(unittest.TestCase):
    def setUp(self):
        super().setUp()

    def test_format_cpf_cnpj(self):
        cpf = utils.format_cpf_cnpj("76586507812")
        self.assertEqual("765.865.078-12", cpf)

    def test_format_number(self):
        number = utils.format_number("19500")
        self.assertEqual("19.500", number)
