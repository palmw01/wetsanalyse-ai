"""De citaten bij een tekstantwoord dat per kop een gelezen bepaling uitlegt (agentset F05, A6 eind: "**24.1 – Wanneer
verrekening**" tot en met 24.6 goed samengevat, maar zonder één citaat). Zonder bron naast de wet vraagt de code bij een
tekstantwoord niet om het sjabloon, dus het model schreef de uitleg zonder passage. Bij elke kop die een gelezen
bepaling noemt, kiest de code uit de tekst van die bepaling de zin die het meest deelt met wat de alinea erover zegt: de
zin staat letterlijk in de bron, en de vindplaats komt uit de rij. Hetzelfde idee als `extern.aanvulling` bij een
rapport, nu voor wettekst uit de graaf.

Alleen een kop met een nummer dat bij precies één gelezen bepaling hoort, en alleen een zin die genoeg deelt
(`MIN_GEDEELD` stammen); anders geen citaat voor die kop. Nooit meer dan `MAX_CITATEN`.
"""
from __future__ import annotations

import re
from typing import Any

from bronmodel.antwoord import Citaat

#: Hoeveel citaten de code hoogstens aan één antwoord toevoegt.
MAX_CITATEN = 12
#: Hoeveel stammen een gekozen zin minstens deelt met de alinea onder zijn kop.
MIN_GEDEELD = 3

#: Een kop die een bepaling noemt: "**24.1 – Wanneer verrekening**", "**Artikel 11** – …", "### 22.8".
_KOP = re.compile(r"^\s*(?:#{1,4}\s*|\*\*\s*)(?:artikel\s+|onderdeel\s+)?(\d+[a-z]*(?:\.\d+[a-z]*)*)\b", re.I)
_ZIN = re.compile(r"(?<=[.;:])\s+")


def _per_nummer(trace: Any) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    from .sjablonen.vullen import bron_rijen

    uit: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for iri, rij in bron_rijen(trace).items():
        nummer = str(rij.get("nummer") or "").strip()
        # Een divisie ("24.1") of een heel artikel; een lid of onderdeel heeft een nummer dat in elk artikel terugkomt.
        if nummer and ("." in nummer or (":artikel:" in iri and ":lid:" not in iri and ":o:" not in iri)):
            uit.setdefault(nummer.casefold(), []).append((iri, rij))
    return uit


def _secties(tekst: str) -> list[tuple[str, str]]:
    """(nummer, de tekst onder de kop) per kop die een bepaling noemt, in volgorde."""
    secties: list[list[str]] = []
    for regel in (tekst or "").splitlines():
        if m := _KOP.match(regel):
            secties.append([m.group(1), regel])
        elif secties:
            secties[-1][1] += "\n" + regel
    return [(n, t) for n, t in secties]


def uit_tekst(tekst: str, trace: Any) -> list[Citaat]:
    """De citaten die de koppen van een tekstantwoord dragen, of leeg."""
    from .gelezen import _WOORD, _stammen
    from .sjablonen.vullen import vindplaats_van

    rijen = _per_nummer(trace)
    citaten: list[Citaat] = []
    for nummer, sectie in _secties(tekst):
        kandidaten = rijen.get(nummer.casefold()) or []
        if len(kandidaten) != 1:
            continue
        iri, rij = kandidaten[0]
        stammen = _stammen(_WOORD.findall(sectie.casefold()))
        zinnen = [z.strip() for z in _ZIN.split(" ".join(str(rij.get("tekst") or "").split())) if len(z.split()) >= 5]
        if not zinnen:
            continue
        gedeeld, zin = max(((len(_stammen(_WOORD.findall(z.casefold())) & stammen), z) for z in zinnen),
                           key=lambda x: x[0])
        if gedeeld < MIN_GEDEELD:
            continue
        citaten.append(Citaat(tekst=zin, vindplaats=vindplaats_van(iri, jci=str(rij.get("jci") or ""),
                                                                    label=str(rij.get("label") or ""))))
        if len(citaten) >= MAX_CITATEN:
            break
    return citaten
