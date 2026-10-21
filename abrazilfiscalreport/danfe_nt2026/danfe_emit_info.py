from ._pdf_element import Element


class DanfeEmitInfo(Element):
    def __init__(self, emit: str, address, logo_image=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emit = emit
        self.logo_image = logo_image
        self.address = address

    def render(self):
        super().render()
        h_field_name = 10
        h_logo = 20
        w_logo = 30
        y_address = self.y + h_field_name

        if self.logo_image:
            self.pdf.image(
                name=self.logo_image,
                x=self.x + 2,
                y=y_address,
                w=w_logo,
                h=h_logo,
                keep_aspect_ratio=True,
            )
            x_address = self.x + w_logo + 2
            w_address = self.w - w_logo - 3
        else:
            w_address = self.w
            x_address = self.x + 2
        self.pdf.set_font(self.pdf.default_font, "B", 12)
        self.pdf.set_xy(x=self.x, y=self.y + 1)
        self.pdf.multi_cell(w=self.w, h=None, text=self.emit, border=0, align="C")
        self.pdf.set_font(self.pdf.default_font, "", 8)
        self.pdf.set_xy(x=self.x + w_logo + 1, y=self.y + h_field_name + 2)
        self.pdf.text_box(
            text=self.address,
            text_align="C",
            h_line=3,
            x=x_address,
            y=y_address,
            w=w_address,
            h=self.h - h_field_name,
            border=False,
        )
