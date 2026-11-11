"""Het Staatsblad en de Staatscourant uit de officiële publicaties van KOOP – een dunne laag op `sru_koop.SruKoop`
(ADR-013).

Transport, cache en recordvorm zijn gedeeld met Kamerstukken (`sru_koop.py`). Hier staat alleen wat een bekendmaking
eigen is: het filter, en hoe een id dat KOOP niet kent alsnog te vinden is (op publicatieblad, jaargang en nummer: een
herdruk of een herplaatsing draagt een eigen id). De query bouwt `agent/tools/bekendmaking_tools.py`.
"""
from __future__ import annotations

import logging
import re

from .sru_koop import KoopFout, Record, SruKoop

#: Het filter op het Staatsblad en de Staatscourant; `tools/bekendmaking_tools.py` bouwt er de zoekvragen op.
BEKENDMAKING = ("c.product-area==officielepublicaties AND "
                "(w.publicatienaam==Staatsblad OR w.publicatienaam==Staatscourant)")
_BLAD = {"stb": "Staatsblad", "stcrt": "Staatscourant"}
_JAAR_NUMMER_RE = re.compile(r"^(stb|stcrt)-(\d{4})-(\d{1,6})(?:-n\d+)?$")


def blad_jaar_nummer(ident: str) -> tuple[str, str, str] | None:
    """(publicatieblad, jaargang, nummer) uit stb-2010-176 of stcrt-2026-37344-n1; None voor een oud Stcrt-id
    (stcrt-2008-122-p18-SC86213: één uitgave met veel items, het nummer wijst geen stuk aan)."""
    m = _JAAR_NUMMER_RE.match(ident or "")
    return (_BLAD[m.group(1)], m.group(2), m.group(3)) if m else None


class SruBekendmakingen(SruKoop):
    """De echte bron; tests gebruiken een nep met dezelfde twee methoden."""

    SOORT = "bekendmaking"
    FOUT = KoopFout
    _logger = logging.getLogger("graph_qa.bekendmakingen")

    def _terugval(self, ident: str) -> list[Record]:
        return self.versies(ident)

    def versies(self, ident: str) -> list[Record]:
        """Elke publicatie met hetzelfde blad, dezelfde jaargang en hetzelfde nummer: het stuk zelf, een herdruk, een
        tweede versie, een verbeterblad (een eigen id met `-n1`, ook bij KOOP). Leeg voor een id zonder nummer. Zo ziet
        Lex dat er een andere versie is (iteratie bekendmakingen ronde 1, B25: "kent geen meerdere versies", terwijl
        stcrt-2024-20015-n1 bestaat)."""
        if (bjn := blad_jaar_nummer(ident)) is None:
            return []
        blad, jaar, nummer = bjn
        _, records = self.zoek(f'c.product-area==officielepublicaties AND w.publicatienaam=={blad} AND '
                               f'w.jaargang=="{jaar}" AND w.publicatienummer=="{nummer}"', maximum=10)
        return [r for r in records if r.jaargang == jaar and r.publicatienummer == nummer]
