"""De werkplaats (ADR-016 deel B): één levenscyclus voor alles wat de gebruiker maakt.

Een **onderdeel** is een skill, een agentprofiel of (later) een MCP-server. Een **versie** is een volledige snapshot:
alle bestanden van het onderdeel als afbeelding van pad naar tekst, met één hash. Een profiel is een snapshot met één
bestand (`<naam>.md`), een skill een map. Zo is er één vorm voor elke soort.

Dit bestand is het register van de soorten: per soort de toets (poort 1 van §B2, met de validatoren van `bronmodel.skill`
en `bronmodel.agentprofiel`) en het lege begin. Een nieuwe soort is een regel hier, geen tabel en geen route. Het staat
in het bronmodel omdat de api (het register), graph-qa (wat er in het image zit, de proef) en de werkplek dezelfde hash
en dezelfde toets nodig hebben.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from . import agentprofiel, skill
from .validatie import Bevinding, ValidatieFout

#: De soorten onderdelen, in de volgorde van de werkplek.
SOORTEN: tuple[str, ...] = ("skill", "agentprofiel", "mcp")

#: Een pad binnen een onderdeel: relatief, met gewone tekens, zonder `..`.
PAD = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*")
MAX_PAD = 200

#: De grenzen van een versie en van het register. Een onderdeel gaat als tekst in de context van een model, en een
#: register dat alleen aangroeit, heeft een plafond nodig.
MAX_BESTANDEN = skill.MAX_BESTANDEN
MAX_TEKENS_BESTAND = skill.MAX_TEKENS_BESTAND
MAX_TEKENS = skill.MAX_TEKENS_SKILL
MAX_VERSIES = 200
MAX_ONDERDELEN = 50


def hash_van(bestanden: Mapping[str, str]) -> str:
    """De hash van een snapshot: sha256 over de paden in volgorde, elk met zijn tekst. De volgorde waarin de bestanden
    binnenkomen, telt niet. Dezelfde rekenregel voor een versie in het register en voor wat er in het image zit: daaraan
    is te zien of een versie *actief* is."""
    reeks = json.dumps(sorted(bestanden.items()), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(reeks.encode("utf-8")).hexdigest()


def weiger(bestanden: Mapping[str, str]) -> list[Bevinding]:
    """Wat het register nooit bewaart, ook niet als concept: een pad dat geen pad is, en een snapshot boven de grens.
    Iets anders dan een ongeldige inhoud: die wordt bewaard, met haar bevindingen."""
    uit = []
    if not bestanden:
        uit.append(Bevinding("leeg", "een versie heeft minstens één bestand"))
    if len(bestanden) > MAX_BESTANDEN:
        uit.append(Bevinding("omvang", f"meer dan {MAX_BESTANDEN} bestanden"))
    for pad, tekst in bestanden.items():
        if not isinstance(pad, str) or len(pad) > MAX_PAD or not PAD.fullmatch(pad) or ".." in pad.split("/"):
            uit.append(Bevinding("pad", "geen geldig pad binnen het onderdeel", str(pad)[:MAX_PAD]))
        elif not isinstance(tekst, str):
            uit.append(Bevinding("tekst", "het bestand is geen tekst", pad))
        elif len(tekst) > MAX_TEKENS_BESTAND:
            uit.append(Bevinding("omvang", f"langer dan {MAX_TEKENS_BESTAND} tekens", pad))
    if sum(len(t) for t in bestanden.values() if isinstance(t, str)) > MAX_TEKENS:
        uit.append(Bevinding("omvang", f"de versie is langer dan {MAX_TEKENS} tekens"))
    return uit


def _toets_skill(naam: str, bestanden: Mapping[str, str]) -> list[Bevinding]:
    """De Agent Skills-specificatie en de regels van Lex. De basis-skill vult alle rollen. Wat alleen over de skills
    heen te toetsen is (een sectie-id en een broncode zijn van één skill), toetst wie de andere skills kent."""
    return skill.toets(naam, bestanden, basis=naam == skill.BASIS)[1]


def _toets_agentprofiel(naam: str, bestanden: Mapping[str, str]) -> list[Bevinding]:
    """De vorm van het profiel: één bestand `<naam>.md` met de velden van §A2. De grenzen (bestaat de tool, het
    sjabloon, de connector) toetst wie de registers kent: graph-qa bij het laden en in de proef."""
    pad = f"{naam}.md"
    uit = [Bevinding("bestand", f"een agentprofiel is één bestand, {pad}", p) for p in sorted(set(bestanden) - {pad})]
    if pad not in bestanden:
        return [*uit, Bevinding("bestand", "ontbreekt", pad)]
    try:
        agentprofiel.uit_markdown(naam, bestanden[pad])
    except ValidatieFout as fout:
        uit += [Bevinding(b.code, b.melding, pad) for b in fout.bevindingen]
    return uit


def _begin_skill(naam: str) -> dict[str, str]:
    return {
        skill.HOOFDBESTAND: (
            f"---\nname: {naam}\ndescription: >-\n  Beschrijf wat deze skill doet en wanneer Lex hem gebruikt.\n"
            'metadata:\n  methode_versie: "0.1"\n  lex_soort: "methode"\n'
            f'  lex_label: "{naam}"\n  lex_herkomst: "eigen tekst"\n  lex_licentie: "repo"\n  lex_letterlijk: "nee"\n'
            f"---\n\n# {naam}\n"),
        skill.ROLBESTAND: json.dumps({"secties": {}, "rollen": {}}, indent=2) + "\n",
        skill.BRONREGISTER: "# Bronnen\n\n| Code | Bron |\n|---|---|\n",
    }


def _begin_agentprofiel(naam: str) -> dict[str, str]:
    return {f"{naam}.md": (
        f"---\nname: {naam}\ndescription: Beschrijf wanneer de centrale agent dit profiel kiest.\n"
        "methoderol: agent\ntools: []\n---\n\nBeschrijf wat de agent doet en hoe hij afrondt.\n")}


@dataclass(frozen=True)
class Soort:
    naam: str
    label: str
    #: De vorm van een naam van deze soort (ook de map- of bestandsnaam).
    naamvorm: re.Pattern[str]
    max_naam: int
    #: `(naam, bestanden) -> bevindingen`: poort 1.
    toets: Callable[[str, Mapping[str, str]], list[Bevinding]]
    #: `(naam) -> bestanden`: waarmee *Nieuw* begint, met de verplichte velden.
    begin: Callable[[str], dict[str, str]]


#: De soorten die open staan. `mcp` staat in `SOORTEN` maar hier niet: die soort wacht op het besluit van ADR-007.
REGISTER: dict[str, Soort] = {s.naam: s for s in (
    Soort("skill", "Skill", skill.NAAM, skill.MAX_NAAM, _toets_skill, _begin_skill),
    Soort("agentprofiel", "Agentprofiel", re.compile(agentprofiel.NAAM), agentprofiel.MAX_NAAM, _toets_agentprofiel,
          _begin_agentprofiel),
)}


def naam_fout(soort: str, naam: str) -> str:
    """Waarom `naam` geen naam van deze soort is, of leeg. Een onbekende of gesloten soort is ook een fout."""
    s = REGISTER.get(soort)
    if s is None:
        return f"de soort {soort!r} staat niet open" if soort in SOORTEN else f"onbekende soort {soort!r}"
    if not isinstance(naam, str) or len(naam) > s.max_naam or not s.naamvorm.fullmatch(naam):
        return f"geen geldige naam voor een {s.label.lower()}"
    return ""


def _over_skills_heen(naam: str, bestanden: Mapping[str, str], andere: Mapping[str, Mapping[str, str]]) -> list[Bevinding]:
    """Wat alleen over de skills heen te toetsen is: een sectie-id en een broncode zijn van één skill. `andere` zijn de
    andere skills (naam → bestanden), bijvoorbeeld die in het image; een versie van dezelfde skill telt niet mee, want
    het concept vervangt haar. Een andere skill die zelf niet geldig is, doet niet mee."""
    eigen, _ = skill.toets(naam, bestanden, basis=naam == skill.BASIS)
    if eigen is None:
        return []
    rest = [s for n, b in sorted(andere.items()) if n != naam
            and (s := skill.toets(n, b, basis=n == skill.BASIS)[0]) is not None]
    return skill.toets_samen([*rest, eigen])


def toets(soort: str, naam: str, bestanden: Mapping[str, str], *,
          andere: Mapping[str, Mapping[str, str]] | None = None) -> list[Bevinding]:
    """Poort 1 voor een versie van een onderdeel: alle bevindingen. Een lege lijst betekent: geldig.

    Met `andere` (de andere skills, naam → bestanden) toetst een skill ook wat alleen over de skills heen te toetsen
    is. Zonder: alleen het onderdeel op zichzelf."""
    if fout := naam_fout(soort, naam):
        return [Bevinding("naam", fout)]
    uit = [*weiger(bestanden), *REGISTER[soort].toets(naam, bestanden)]
    if soort == "skill" and andere and not uit:
        uit += _over_skills_heen(naam, bestanden, andere)
    return uit


def pakkethash(hashes: Mapping[str, str]) -> str:
    """De identiteit van een pakket onderdelen (`<soort>/<naam>` → hash): één hash over alle hashes. Graph-qa rekent
    hem bij het genereren van zijn bronpakket, de api bij een melding: verandert één bestand, dan verandert hij."""
    return hashlib.sha256(json.dumps(dict(hashes), sort_keys=True).encode()).hexdigest()


def begin(soort: str, naam: str) -> dict[str, str]:
    """De bestanden waarmee een nieuw onderdeel begint. Gooit `ValueError` bij een ongeldige soort of naam."""
    if fout := naam_fout(soort, naam):
        raise ValueError(fout)
    return REGISTER[soort].begin(naam)
