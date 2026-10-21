"""
Fontes empacotadas com a biblioteca.

A fonte padrão dos DANFEs é a **Roboto Condensed** (regular + bold), TTF nativo, licenciada sob a
SIL Open Font License 1.1 (``OFL.txt``, Copyright 2011 The Roboto Project Authors,
https://github.com/googlefonts/roboto-classic), que permite embutir e redistribuir. Ela foi
escolhida num teste impresso contra Times, Helvetica, Helvetica Neue Condensed e Liberation Sans
Narrow: é condensada como a Times (cabem dois tributos por linha na tabela de itens da NT 2026.010)
e mais legível que ela. Se os arquivos não estiverem presentes, ``default_font_files()`` devolve
None e quem chama cai na Helvetica nativa do PDF.
"""

from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent
DEFAULT_FONT_NAME = "RobotoCondensed"
DEFAULT_REGULAR = FONTS_DIR / "RobotoCondensed-Regular.ttf"
DEFAULT_BOLD = FONTS_DIR / "RobotoCondensed-Bold.ttf"


def default_font_files():
    """(nome, regular, bold) da fonte padrão empacotada, ou None se faltar algum arquivo."""
    if DEFAULT_REGULAR.is_file() and DEFAULT_BOLD.is_file():
        return DEFAULT_FONT_NAME, str(DEFAULT_REGULAR), str(DEFAULT_BOLD)
    return None
