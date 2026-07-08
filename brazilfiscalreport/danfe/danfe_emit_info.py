from ..pdf_element import Element


class DanfeEmitInfo(Element):
    def __init__(self, emit: str, address, logo_image=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emit = emit
        self.logo_image = logo_image
        self.address = address

    def render(self):
        super().render()
        logo_h = 8

        if self.logo_image:
            self.pdf.image(
                name=self.logo_image,
                x=self.x + 2,
                y=self.y + 1,
                w=self.w - 4,
                h=logo_h,
                keep_aspect_ratio=True,
            )
            y_emit = self.y + logo_h + 2
        else:
            y_emit = self.y + 1

        self.pdf.set_font(self.pdf.default_font, "B", 12)
        self.pdf.set_xy(x=self.x, y=y_emit)
        self.pdf.multi_cell(w=self.w, h=None, text=self.emit, border=0, align="C")
        self.pdf.set_font(self.pdf.default_font, "", 8)
        y_address = self.pdf.get_y() + 0.5
        self.pdf.text_box(
            text=self.address,
            text_align="C",
            h_line=3,
            x=self.x + 2,
            y=y_address,
            w=self.w - 4,
            h=self.h - (y_address - self.y),
            border=False,
        )
