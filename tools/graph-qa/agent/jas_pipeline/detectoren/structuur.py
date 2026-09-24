"""Structuurdetectoren: waar de vorm van de bron het signaal is (ADR-001 PR 6).

`DefinitieDetector` – een begripsbepalingenartikel heeft een aanhef ('In deze wet wordt verstaan
onder:') en onderdelen 'term: omschrijving' (H2:136). Het onderdeel is dan een kandidaat-
Brondefinitie; de dubbele punt alleen is dat níét ('Bij voetgangerslichten betekent: … groen
licht: …' is een betekenisregel, geen definitie). De aanhef mag in de eigen tekst staan of – bij
een onderdeel als eigen bronnode – in `BronTekst.context`.
"""
from __future__ import annotations

import re

from ..kandidaten import BronSpan, Candidate, DetectorResult, Evidence, SpanOption
from . import BronTekst

_AANHEF = re.compile(r"\bwordt\s+(?:in\s+[^:]{0,80}\s+)?verstaan\s+onder\s*:", re.IGNORECASE)
# Onderdeel: optioneel label ("a.", "1°.", "aa."), dan een term zonder dubbele punt, ': ', omschrijving.
_ONDERDEEL = re.compile(r"^[ \t]*(?:[a-z0-9]{1,3}°?\.[ \t]+)?(?P<term>[^:\n]{1,120}?):[ \t]+(?P<oms>[^\n]+?)[ \t]*$",
                        re.MULTILINE)
# Eén zin: 'Onder X wordt verstaan: Y.' / 'Onder X wordt verstaan Y.'
_ZIN = re.compile(r"\b[Oo]nder\s+[^.;:]{1,120}?\s+wordt\s+verstaan\s*:?\s*[^.;]+[.;]?")


class DefinitieDetector:
    naam = "definitie"
    versie = "1"
    REGEL_ONDERDEEL = "jas.definitie.onderdeel_term_dubbelepunt"
    REGEL_ZIN = "jas.definitie.verstaan_onder"

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        tekst = bron.tekst
        kandidaten: list[Candidate] = []
        aanhef = _AANHEF.search(tekst)
        if aanhef or _AANHEF.search(bron.context):
            begin = aanhef.end() if aanhef else 0
            for m in _ONDERDEEL.finditer(tekst, begin):
                s, e = m.start("term"), m.end("oms")
                kern_eind = e - 1 if tekst[e - 1] in ";." else e
                opties = [SpanOption(soort="kern", span=BronSpan.van(bron.span(s, kern_eind)))] if kern_eind != e else []
                kandidaten.append(Candidate.maak(
                    bron.span(s, e), ["Brondefinitie"],
                    [Evidence(detector=self.naam, code="DEFINITION_ITEM", regel=self.REGEL_ONDERDEEL,
                              detail=m.group("term"))], opties))
        for m in _ZIN.finditer(tekst):
            kandidaten.append(Candidate.maak(
                bron.span(*m.span()), ["Brondefinitie"],
                [Evidence(detector=self.naam, code="DEFINITION_SENTENCE", regel=self.REGEL_ZIN)]))
        return DetectorResult(detector=self.naam, versie=self.versie, bron_iri=bron.bron_iri,
                              kandidaten=tuple(kandidaten))
