"""De Kamerstukken uit de officiële publicaties van KOOP – een dunne laag op `sru_koop.SruKoop` (ADR-013).

De transport, het cachebeleid en de recordvorm zijn gedeeld met Staatsblad en Staatscourant (`sru_koop.py`). Hier
staat alleen wat een Kamerstuk eigen is: het filter en hoe een id dat KOOP niet kent alsnog te vinden is (op dossier
en nummer: een herdruk heeft een eigen id, `kst-32740-1` → `kst-32740-1-n1`, en een onopgemaakt stuk ook, 32140 nr.
342 = `kst-1278484`). De query bouwt `agent/tools/kamerstuk_tools.py`.
"""
from __future__ import annotations

import logging
import re

from .sru_koop import _NS, FOUTCODES, SRU_URL, VERS_S, Document, KoopFout, Record, SruKoop, lees_records

__all__ = ["_NS", "FOUTCODES", "SRU_URL", "VERS_S", "Document", "KamerstukFout", "Record", "SruKamerstukken",
           "dossier_en_nummer", "lees_records"]

#: Dezelfde foutklasse als de andere KOOP-connectors; de naam blijft voor de aanroepers.
KamerstukFout = KoopFout

#: Het filter op Kamerstukken zonder bijlagen; `tools/kamerstuk_tools.py` bouwt er de zoekvragen op.
_KAMERSTUK = "c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk AND dt.type==Kamerstuk"
_DOSSIER_NUMMER_RE = re.compile(r"^kst-(\d{4,6}(?:-[0-9A-Za-z]{1,6})?)-([0-9A-Z]{1,6})(?:-n\d+)?$")


def dossier_en_nummer(ident: str) -> tuple[str, str] | None:
    """(dossier, nummer) uit een id als kst-36200-IX-2 of kst-32740-1-n1; None voor een id zonder die vorm
    (kst-1278484, het id van een onopgemaakt stuk)."""
    m = _DOSSIER_NUMMER_RE.match(ident or "")
    return (m.group(1), m.group(2)) if m else None


class SruKamerstukken(SruKoop):
    """De echte bron; tests gebruiken een nep met dezelfde twee methoden."""

    SOORT = "kamerstuk"
    FOUT = KamerstukFout
    _logger = logging.getLogger("graph_qa.kamerstukken")

    def _terugval(self, ident: str) -> list[Record]:
        if (dn := dossier_en_nummer(ident)) is None:
            return []
        _, records = self.zoek(f'{_KAMERSTUK} AND w.dossiernummer=="{dn[0]}" AND w.ondernummer=="{dn[1]}"', maximum=10)
        # Alleen een stuk waarvan dit het hoofddossier is: een motie in vier dossiers heeft één nummer, in het eerste.
        eigen = [r for r in records if r.dossiers[:1] == (dn[0],) and r.ondernummer == dn[1]]
        if eigen or not dn[1].isalpha():
            return eigen
        # Een lettercode van de Eerste Kamer (A, B, … L) geldt bij een gezamenlijke behandeling voor de hele reeks, en het
        # stuk heet naar het eerste dossier: wie kst-33755-L vraagt, bedoelt kst-33752-L (ronde 3 Kamerstukken, 12 nov
        # 2026, K22: de vervolgvraag op "het laatste stuk van dossier 33755" las "niet gevonden"). Een nummer in cijfers
        # hoort bij één dossier en valt hier niet onder. Alleen als het eenduidig is.
        reeks = [r for r in records if dn[0] in r.dossiers and r.ondernummer == dn[1]]
        return reeks if len(reeks) == 1 else []
