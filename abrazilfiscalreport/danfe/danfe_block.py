from typing import List

from fpdf import FPDF

from .danfe_basic_field import DanfeBasicField
from .danfe_conf import HEIGHT_FONT_BLOCK_DESC
from .models import BaseFieldInfo


class DanfeBlock:
    def __init__(
        self,
        pdf: FPDF,
        x: float = None,
        y: float = None,
        h: float = None,
        rows_heights: float = None,
        description: str = None,
        border: str = "",
    ):
        self.w = pdf.edw
        self.h = h
        if description:
            self.description = description
        else:
            self.description = None
        self.fields = []
        self.pdf = pdf
        self.border = border
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.rows_heights = rows_heights

        self.x = x if x else pdf.get_x()
        self.y = y if y else pdf.get_y()

        self.margin_top = 0

    def add_field(self, field: DanfeBasicField):
        self.fields.append(field)

    def add_fields(self, fields_list):
        for i, fields_line in enumerate(fields_list):
            fields = self.calculate_fields_width(fields_line)
            for field_info in fields:
                self.add_field(
                    DanfeBasicField(
                        w=field_info.w,
                        h=self.rows_heights[i],
                        description=field_info.description,
                        content=field_info.content,
                        type=field_info.type,
                        pdf=self.pdf,
                    )
                )

    def render(self):
        self.render_description()
        x = self.x + self.offset_x
        y = self.y + self.offset_y
        self.pdf.set_xy(x=x, y=y)
        for field in self.fields:
            if not field.x and not field.y:
                field.x = x
                field.y = y
            x, y = self.get_new_position(field)
            field.render()
            # set final position
            # necessary to know where the next block should start
            self.pdf.set_xy(x=x, y=y)

    def render_description(self):
        if self.description:
            self.pdf.set_font(self.pdf.default_font, "B", 6)
            self.pdf.set_xy(x=self.x, y=self.y + self.margin_top)
            self.pdf.cell(
                w=self.w, h=HEIGHT_FONT_BLOCK_DESC, text=self.description, align="L"
            )
            self.offset_y += HEIGHT_FONT_BLOCK_DESC + self.margin_top

    def get_new_position(self, field):
        new_pos_x = 0.0
        new_pos_y = 0.0

        # X Axis
        if field.new_x == "LEFT":
            new_pos_x = field.x
        if field.new_x == "RIGHT":
            # default
            new_pos_x = field.x + field.w
        if field.new_x == "L_BLOCK":
            new_pos_x = self.x
        if field.new_x == "R_BLOCK":
            new_pos_x = self.x + self.w

        # Y Axis
        if field.new_y == "TOP":
            # default
            new_pos_y = field.y
        if field.new_y == "BOTTOM":
            new_pos_y = field.y + field.h
        if field.new_x == "T_BLOCK":
            new_pos_y = self.y
        if field.new_x == "B_BLOCK":
            new_pos_y = self.y + self.h

        # fix outside position
        if new_pos_x >= (self.x + self.w - 1):
            new_pos_x = self.x
            new_pos_y = field.y + field.h

        return new_pos_x, new_pos_y

    def calculate_fields_width(self, fields: List[BaseFieldInfo]):
        all_adjusted_fields = []

        fixed_width = sum(f.w for f in fields if f.w > 0)
        num_zero_width_fields = sum(1 for f in fields if f.w == 0)
        remaining_width = self.w - fixed_width
        width_per_field = remaining_width / num_zero_width_fields
        adjusted_fields = []
        for field in fields:
            if field.w == 0:
                adjusted_fields.append(
                    BaseFieldInfo(
                        w=width_per_field,
                        description=field.description,
                        content=field.content,
                        type=field.type,
                    )
                )
            else:
                adjusted_fields.append(field)
        all_adjusted_fields.extend(adjusted_fields)
        return all_adjusted_fields
