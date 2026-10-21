from fpdf import FPDF


class Element:
    def __init__(
        self,
        h: float,
        pdf: FPDF,
        border: str = None,
        new_x: str = "RIGHT",
        new_y: str = "TOP",
        w: float = None,
        x: float = 0.0,
        y: float = 0.0,
    ):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.pdf = pdf
        self.border = border
        self.new_x = new_x
        self.new_y = new_y

    def render(self):
        self.pdf.rect(
            x=self.x,
            y=self.y,
            w=self.w,
            h=self.h,
        )
