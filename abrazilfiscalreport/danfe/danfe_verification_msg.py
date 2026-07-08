from ..pdf_element import Element


class DanfeVerificationMsg(Element):
    def render(self):
        super().render()
        pdf = self.pdf
        pdf.set_font(pdf.default_font, "", 10)
        pdf.set_xy(x=self.x + 0.5, y=self.y + 2.5)
        text = (
            "Consulta de autenticidade no portal nacional da NF-e "
            "www.nfe.fazenda.gov.br/portal ou no site da "
            "Sefaz autorizadora"
        )
        pdf.multi_cell(w=self.w - 1, h=None, text=text, border=0, align="C")
