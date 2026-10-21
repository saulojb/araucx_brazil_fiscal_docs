"""Escolha do leiaute pela data de emissão (a NT 2026.010 vale a partir de 01/12/2026)."""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from ._utils import get_tag_text
from .danfe_conf import URL

BRASILIA = timezone(timedelta(hours=-3))
# Data de liberação em produção da NT 2026.010.
NT_2026_010_START = datetime(2026, 12, 1, tzinfo=BRASILIA)


def get_issue_datetime(xml):
    """
    Data de emissão da NF-e (ide/dhEmi, ou ide/dEmi antes do leiaute 3.10), ou
    None se ausente/inválida. Data sem fuso é tomada como horário de Brasília.
    """
    ide = ET.fromstring(xml).find(f"{URL}ide")
    text = get_tag_text(ide, URL, "dhEmi") or get_tag_text(ide, URL, "dEmi")
    try:
        issued = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=BRASILIA)
    return issued


def uses_nt_2026_010(xml):
    """
    True se a NF-e deve ser impressa no leiaute da NT 2026.010 (emitida a partir
    de 01/12/2026). Sem data de emissão, vale a data de impressão. O mesmo XML
    sempre dá o mesmo DANFE.
    """
    issued = get_issue_datetime(xml) or datetime.now(BRASILIA)
    return issued >= NT_2026_010_START
