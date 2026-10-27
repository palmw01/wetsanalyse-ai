"""B1-toetsen op een uitleg van een begrip (spoor I2).

NL-SBB vraagt bij een begrip een uitleg (`rdfs:comment`) in eenvoudige taal, op taalniveau B1. Lex
schrijft die uitleg met het model; of ze B1 is, beslist het model niet. Deze toetsen staan in code
(de houding van ADR-001: kennis die te toetsen is, hoort niet alleen in een prompt) en leveren
aandachtspunten op, geen weigering – de analist beslist.

- `B1_LANGE_ZIN`: een zin van meer dan `MAX_WOORDEN` woorden.
- `B1_TE_LANG`: meer dan `MAX_ZINNEN` zinnen; een uitleg is één korte alinea.
- `B1_LIJDENDE_VORM`: een lijdende vorm. Met de parser (ADR-002) is dat een hulpwerkwoord met relatie
  `aux:pass` ("wordt … vastgesteld"); zonder parser een vorm van *worden* met verderop in de zin een
  woord dat eindigt als een voltooid deelwoord (-d, -t of -en).
- `B1_MOEILIJK_WOORD`: een woord uit `b1_woorden.yaml`, dat een gewoner woord heeft.
- `B1_VAKTERM_ONVERKLAARD`: een lang woord uit de definitie (een vakterm) staat in de uitleg zonder dat
  een zin het uitlegt ("<term> is …", "dat betekent", "wil zeggen", een dubbele punt of haakjes).
- `B1_HERHAALT_DEFINITIE`: de uitleg herhaalt de definitie (bijna) woord voor woord.

De teksten bij de codes staan in `kaartacties.TEKST`, de bron die de werkplek meeleest.
"""
from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from ..jas_pipeline.taal.model import LinguisticAnalysis
from ..jas_pipeline.taal.provider import TaalProvider, maak_provider

MAX_WOORDEN = 20
MAX_ZINNEN = 5
VAKTERM_LENGTE = 12            # vanaf zoveel letters telt een woord uit de definitie als vakterm
HERHALING = 0.8                # aandeel inhoudswoorden van de definitie dat ook in de uitleg staat

CODES = ("B1_LANGE_ZIN", "B1_TE_LANG", "B1_LIJDENDE_VORM", "B1_MOEILIJK_WOORD", "B1_VAKTERM_ONVERKLAARD",
         "B1_HERHAALT_DEFINITIE")

_WOORD = re.compile(r"[A-Za-zÀ-ÿ][\wÀ-ÿ'-]*")
_WORDEN = re.compile(r"\b(?:word|wordt|worden|werd|werden)\b[^.!?;]*?\b\w{3,}(?:d|t|en)\b", re.IGNORECASE)
_UITLEG = re.compile(r"\b(?:betekent|dat is|dit is|wil zeggen|met andere woorden|bijvoorbeeld)\b|[:(]", re.IGNORECASE)
_LIDWOORDEN = {"de", "het", "een", "van", "en", "of", "die", "dat", "dit", "deze", "voor", "met", "door", "aan",
               "op", "in", "bij", "als", "is", "zijn", "wordt", "worden", "niet", "tot", "naar", "over", "om"}


@cache
def woordenlijst() -> dict[str, str]:
    pad = Path(__file__).with_name("b1_woorden.yaml")
    return {str(k).lower(): str(v) for k, v in (yaml.safe_load(pad.read_text(encoding="utf-8")) or {}).items()}


@cache
def standaard_provider() -> TaalProvider:
    return maak_provider("spacy")


def _woorden(tekst: str) -> list[str]:
    return [w.lower() for w in _WOORD.findall(tekst)]


def _zinnen(a: LinguisticAnalysis) -> list[str]:
    return [a.tekst[z.start:z.eind] for z in a.zinnen] or [a.tekst]


def moeilijke_woorden(tekst: str) -> list[tuple[str, str]]:
    """(woord, vervanger) in de volgorde van de tekst; een woordgroep telt als geheel."""
    laag = " " + " ".join(_woorden(tekst)) + " "
    return [(w, v) for w, v in woordenlijst().items() if f" {w} " in laag]


def lijdende_vorm(a: LinguisticAnalysis) -> bool:
    if not a.gedegradeerd:
        return any(t.deprel == "aux:pass" for t in a.tokens)
    return bool(_WORDEN.search(a.tekst))


def vaktermen(definitie: str) -> list[str]:
    return list(dict.fromkeys(w for w in _woorden(definitie) if len(w) >= VAKTERM_LENGTE))


def onverklaarde_vaktermen(uitleg: str, definitie: str, a: LinguisticAnalysis) -> list[str]:
    zinnen = _zinnen(a)
    uit = []
    for term in vaktermen(definitie):
        met = [z for z in zinnen if term in _woorden(z)]
        uitgelegd = re.compile(rf"\b{re.escape(term)}\s+(?:is|zijn|betekent|heet)\b", re.IGNORECASE)
        if met and not any(_UITLEG.search(z) or uitgelegd.search(z) for z in met):
            uit.append(term)
    return uit


def herhaalt_definitie(uitleg: str, definitie: str) -> bool:
    inhoud = {w for w in _woorden(definitie) if w not in _LIDWOORDEN and len(w) > 3}
    if len(inhoud) < 4:
        return " ".join(_woorden(definitie)) in " ".join(_woorden(uitleg)) if definitie.strip() else False
    return len(inhoud & set(_woorden(uitleg))) / len(inhoud) >= HERHALING


def toets(uitleg: str, definitie: str = "", provider: TaalProvider | None = None) -> list[str]:
    """De aandachtspunten bij een uitleg, in de volgorde van `CODES`."""
    a = (provider or standaard_provider()).analyseer(uitleg)
    zinnen = _zinnen(a)
    gevonden = {
        "B1_LANGE_ZIN": any(len(_woorden(z)) > MAX_WOORDEN for z in zinnen),
        "B1_TE_LANG": len(zinnen) > MAX_ZINNEN,
        "B1_LIJDENDE_VORM": lijdende_vorm(a),
        "B1_MOEILIJK_WOORD": bool(moeilijke_woorden(uitleg)),
        "B1_VAKTERM_ONVERKLAARD": bool(definitie and onverklaarde_vaktermen(uitleg, definitie, a)),
        "B1_HERHAALT_DEFINITIE": bool(definitie and herhaalt_definitie(uitleg, definitie)),
    }
    return [c for c in CODES if gevonden[c]]
