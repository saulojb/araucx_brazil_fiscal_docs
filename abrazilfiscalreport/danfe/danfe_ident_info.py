from ..pdf_element import Element


class DanfeIdentInfo(Element):
    def __init__(self, serie_nf, nr_nota, tp_nf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serie_nf = serie_nf
        self.nr_nota = nr_nota
        self.tp_nf = tp_nf

    def render(self):
        super().render()
        self.pdf.set_xy(x=self.x, y=self.y)
        self.pdf.set_font(self.pdf.default_font, "B", 12)
        self.pdf.cell(
            self.w,
            None,
            "DANFE",
            new_x="LEFT",
            new_y="NEXT",
            align="C",
        )
        self.pdf.set_font(self.pdf.default_font, "", 7)
        self.pdf.cell(
            self.w, None, "DOCUMENTO AUXILIAR", new_x="LEFT", new_y="NEXT", align="C"
        )
        self.pdf.cell(
            self.w, None, "DA NOTA FISCAL", new_x="LEFT", new_y="NEXT", align="C"
        )
        self.pdf.cell(self.w, None, "ELETRÔNICA", new_x="LEFT", new_y="NEXT", align="C")

        self.pdf.set_font(self.pdf.default_font, "", 8)
        pos_x = self.pdf.get_x() + 1
        pos_y = self.pdf.get_y() + 1

        self.pdf.set_xy(x=pos_x, y=pos_y)

        self.pdf.cell(self.w, 3, "0-ENTRADA", new_x="LEFT", new_y="NEXT", align="L")
        self.pdf.cell(self.w, 3, "1-SAÍDA", new_x="LEFT", new_y="NEXT", align="L")
        pos_x2 = self.pdf.get_x()
        pos_y2 = self.pdf.get_y() + 0.5

        self.pdf.set_font(self.pdf.default_font, "B", 10)
        self.pdf.text_box(
            text=self.tp_nf,
            text_align="C",
            h_line=4,
            x=pos_x + 25,
            y=pos_y,
            w=5,
            h=5,
            border=1,
        )

        self.pdf.set_font(self.pdf.default_font, "B", 10)
        self.pdf.set_xy(x=pos_x2, y=pos_y2)
        nf = f"{int(self.nr_nota):011,}".replace(",", ".")
        self.pdf.cell(self.w, 5, f"Nº {nf}", new_x="LEFT", new_y="NEXT", align="L")
        self.pdf.set_font(self.pdf.default_font, "B", 8)
        self.pdf.cell(
            self.w,
            None,
            f"SÉRIE {self.serie_nf}",
            new_x="LEFT",
            new_y="NEXT",
            align="L",
        )
        self.pdf.cell(self.w, None, f"FOLHA {self.pdf.page_no()}/{{nb}}", align="L")
