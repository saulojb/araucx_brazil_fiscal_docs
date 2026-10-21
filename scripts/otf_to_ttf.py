#!/usr/bin/env python3
"""
Converte uma fonte OpenType com contornos CFF (.otf) em TrueType (.ttf).

O fpdf2 embute .otf CFF declarando TrueType, o que gera PDF fora da especificação
(o Poppler avisa "Mismatch between font type and embedded font file"). Converter para
TTF de verdade resolve. Uso:  python scripts/otf_to_ttf.py entrada.otf saida.ttf [erro_max]
"""

import sys

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable


def otf_to_ttf(src, dst, max_err=1.0):
    font = TTFont(src)
    order = font.getGlyphOrder()
    font["loca"] = newTable("loca")
    font["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = {}
    glyph_set = font.getGlyphSet()
    for name in order:
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, max_err, reverse_direction=True))
        glyf[name] = pen.glyph()
    font["head"].glyphDataFormat = 0
    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    for attr, value in (
        ("maxZones", 1),
        ("maxTwilightPoints", 0),
        ("maxStorage", 0),
        ("maxFunctionDefs", 0),
        ("maxInstructionDefs", 0),
        ("maxStackElements", 0),
        ("maxSizeOfInstructions", 0),
        ("maxPoints", 0),
        ("maxContours", 0),
        ("maxCompositePoints", 0),
        ("maxCompositeContours", 0),
        ("maxComponentDepth", 0),
    ):
        setattr(maxp, attr, value)
    maxp.maxComponentElements = max(
        (len(getattr(g, "components", []) or []) for g in glyf.glyphs.values()),
        default=0,
    )
    for table in ("CFF ", "VORG"):
        if table in font:
            del font[table]
    font.sfntVersion = "\x00\x01\x00\x00"
    post = font["post"]
    post.formatType = 2.0
    post.extraNames = []
    post.mapping = {}
    post.glyphOrder = order
    font.save(dst)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    otf_to_ttf(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 1.0)
