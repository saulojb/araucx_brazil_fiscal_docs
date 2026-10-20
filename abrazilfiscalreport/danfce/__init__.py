"""
DANFCe (DANFE NFC-e, modelo 65).

Código trazido do upstream Engenere/BrazilFiscalReport (``brazilfiscalreport.danfce``,
LGPL-3.0) e adaptado a este fork: imports renomeados, anotações compatíveis com
Python 3.8+ e dependências do upstream que o fork não tem isoladas em ``_support``.
Módulo aditivo: não altera nenhum dos demais documentos do pacote.
"""

from .config import DanfceConfig, DecimalConfig, FontType, Margins
from .danfce import Danfce

__all__ = ["Danfce", "DanfceConfig", "DecimalConfig", "FontType", "Margins"]
