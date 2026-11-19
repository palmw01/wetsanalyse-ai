"""Structuurdetectoren: waar de vorm van de bron het signaal is (ADR-001).

`DefinitieDetector` – een begripsbepalingenartikel heeft een aanhef ('In deze wet wordt verstaan
onder:') en onderdelen 'term: omschrijving' (H2:136). Het onderdeel is dan een kandidaat-
Brondefinitie; de dubbele punt alleen is dat níét ('Bij voetgangerslichten betekent: … groen
licht: …' is een betekenisregel, geen definitie). De aanhef mag in de eigen tekst staan of – bij
een onderdeel als eigen bronnode – in `BronTekst.context`.
"""
from __future__ import annotations

import re

from ..kandidaten import BronSpan, Candidate, DetectorResult, Evidence, SpanOption
from ..taal.structuur import herken_onderdelen
from . import BronTekst, resultaat

_AANHEF = re.compile(r"\bwordt\s+(?:in\s+[^:]{0,80}\s+)?verstaan\s+onder\s*:", re.IGNORECASE)
# Eén zin: 'Onder X wordt verstaan: Y.' / 'Onder X wordt verstaan Y.'
_ZIN = re.compile(r"\b[Oo]nder\s+[^.;:]{1,120}?\s+wordt\s+verstaan\s*:?\s*[^.;]+[.;]?")
# De benoemende formule ('Een voorlopige aanslag tot een negatief bedrag … wordt aangeduid als voorlopige teruggaaf.',
# AWR art. 13 lid 2; L-2-6): de hele zin, vanaf het begin, tot de term. Alleen 'wordt'/'worden' zonder modaal werkwoord ervoor: 'kan
# worden aangeduid als gevaarlijk' kwalificeert, en benoemt geen begrip. Zwak bewijs: het model bevestigt.
_AANGEDUID = re.compile(r"(?:^|(?<=[.;:]\s)|(?<=\n))(?P<zin>[^.;:\n]{1,300}?(?<!kan )(?<!kunnen )(?<!mag )(?<!mogen )(?<!zal )(?<!zullen )\b(?:wordt|worden)\s+"
                        r"(?:in\s+[^.;:\n]{0,80}?\s+)?(?:hierna\s+)?aangeduid\s+als\s+[^.;\n]+[.;]?)")


class DefinitieDetector:
    naam = "definitie"
    # 3: de benoemende formule 'wordt aangeduid als' (L-2-6)
    versie = "3"
    REGEL_ONDERDEEL = "jas.definitie.onderdeel_term_dubbelepunt"
    REGEL_ZIN = "jas.definitie.verstaan_onder"
    REGEL_AANGEDUID = "jas.definitie.aangeduid_als"
    REGELS = (REGEL_ONDERDEEL, REGEL_ZIN, REGEL_AANGEDUID)
    BEWIJS = {"DEFINITION_ITEM": ("sterk", "Brondefinitie"), "DEFINITION_SENTENCE": ("sterk", "Brondefinitie")}

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        tekst = bron.tekst
        kandidaten: list[Candidate] = []
        for onderdeel in herken_onderdelen(tekst, bron.context, _AANHEF):
            s, e = onderdeel.term.start, onderdeel.omschrijving.eind
            kern_eind = e - 1 if tekst[e - 1] in ";." else e
            opties = [SpanOption(soort="kern", span=BronSpan.van(bron.span(s, kern_eind)))] if kern_eind != e else []
            kandidaten.append(Candidate.maak(
                bron.span(s, e), ["Brondefinitie"],
                [Evidence(detector=self.naam, code="DEFINITION_ITEM", regel=self.REGEL_ONDERDEEL,
                          detail=tekst[onderdeel.term.start:onderdeel.term.eind])], opties))
        for m in _ZIN.finditer(tekst):
            kandidaten.append(Candidate.maak(
                bron.span(*m.span()), ["Brondefinitie"],
                [Evidence(detector=self.naam, code="DEFINITION_SENTENCE", regel=self.REGEL_ZIN)]))
        for m in _AANGEDUID.finditer(tekst):
            s, e = m.span("zin")
            while s < e and tekst[s].isspace():
                s += 1
            if s < e:
                kandidaten.append(Candidate.maak(
                    bron.span(s, e), ["Brondefinitie"],
                    [Evidence(detector=self.naam, code="DEFINITION_DESIGNATION", regel=self.REGEL_AANGEDUID)]))
        return resultaat(self, bron, kandidaten)


# 'Bij voetgangerslichten betekent: a. groen licht: voetgangers mogen oversteken;' en
# 'Geel knipperlicht betekent: gevaarlijk punt;'. De term is de situatie waaronder de betekenis
# geldt – een kandidaat-Voorwaarde, geen definitie (er staat geen 'wordt verstaan onder').
_BETEKENT = re.compile(r"\bbetekent\s*:", re.IGNORECASE)
_BETEKENT_ONDERWERP = re.compile(r"^[ \t]*(?P<term>[^:\n]{1,80}?)\s+betekent\s*:", re.IGNORECASE | re.MULTILINE)


class BetekenisDetector:
    naam = "betekenis"
    versie = "2"
    REGEL = "jas.voorwaarde.betekenis_term"
    REGELS = (REGEL,)

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        tekst = bron.tekst
        kandidaten: list[Candidate] = []
        for onderdeel in herken_onderdelen(tekst, bron.context, _BETEKENT):
            kandidaten.append(self._kandidaat(bron, onderdeel.term.start, onderdeel.term.eind))
        for m in _BETEKENT_ONDERWERP.finditer(tekst):
            if not re.match(r"(?i)bij\b", m.group("term")):          # 'Bij … betekent:' is een aanhef
                kandidaten.append(self._kandidaat(bron, m.start("term"), m.end("term")))
        return resultaat(self, bron, kandidaten)

    def _kandidaat(self, bron: BronTekst, s: int, e: int) -> Candidate:
        return Candidate.maak(bron.span(s, e), ["Voorwaarde", "Rechtsobject"], [Evidence(
            detector=self.naam, code="MEANING_TERM", regel=self.REGEL, detail=bron.tekst[s:e])])
