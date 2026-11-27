"""Eén antwoord op "welke bronnode is dit?" voor een graaf-IRI, een jci of een kaal BWB-id.

Dezelfde vraag werd op drie plekken verschillend beantwoord: de importer (welke IRI schrijft hij),
de werkplek (`bronDoel` in frontend/lib/samenhang.ts) en de agent (zijn bronnenlijst). Liepen ze
uiteen, dan stond één bepaling twee keer in de bronnen (als IRI én als jci), viel een hoofdstuk samen
met de hele regeling, of opende de 3D-graaf een node die niet bestaat.

De regels zijn die van de importer (`jci_node_ref_key` + `Vocab.by_ref_key` in tools/bwb-import):

- met een artikel: `artikel` (het laatste), `lid` (het laatste) en elke `o`; het structuurpad
  ernaartoe hoort er níét in, want een artikel is binnen de wettekst al uniek;
- zonder artikel: het volledige structuurpad (hoofdstuk, titeldeel, afdeling, paragraaf), want
  "afdeling 1" komt in elk hoofdstuk terug;
- een jci met `&bijlage=` wijst geen node aan die hieruit valt af te leiden: wat in een bijlage staat
  heeft een wet-lokale `id:`-IRI. Geen vindplaats, in plaats van stil de hele regeling of, erger,
  het hoofdstuk of artikel met hetzelfde nummer in de wet zelf.

`frontend/lib/jci-vectoren.json` is de gedeelde vectorset; alle drie de kanten toetsen ertegen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import parse_qsl, quote, unquote

_BWB = re.compile(r"^BWB[RV]\d+$")
_JCI = re.compile(r"^jci[\d.]++:c:(BWB[RV]\d++)(.*)$", re.I)
_KAPOTTE_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
STRUCTUUR = ("hoofdstuk", "titeldeel", "afdeling", "paragraaf")
_SOORT = {"o": "onderdeel", **{s: s for s in (*STRUCTUUR, "artikel", "lid")}}


@dataclass(frozen=True)
class Vindplaats:
    """`soort` is `regeling`, een structuursoort, `artikel`, `lid`, `onderdeel` of `node` (een
    wet-lokale `id:`-IRI, herkend maar zonder leesbaar label). `label` is leeg voor een regeling:
    haar naam staat in de graaf, niet in de verwijzing. Een vindplaats buiten de wettekst is een
    `extern.ExterneVindplaats`; `brontype` maakt de twee vergelijkbaar."""

    brontype: ClassVar[str] = "wettekst"
    bron_iri: str
    bwb_id: str
    pad: tuple[tuple[str, str], ...]
    soort: str
    label: str


def _segment(waarde: str) -> str:
    return quote(waarde, safe="")


def _label(pad: tuple[tuple[str, str], ...]) -> str:
    delen, onderdelen = [], [v for k, v in pad if k == "o"]
    for k, v in pad:
        if k == "o":
            continue
        delen.append(f"{k} {v}")
    if onderdelen:
        delen.append("onderdeel " + ", ".join(onderdelen))
    tekst = ", ".join(delen)
    return tekst[:1].upper() + tekst[1:]


def _soort(pad: tuple[tuple[str, str], ...]) -> str:
    return _SOORT.get(pad[-1][0], "node") if pad else "regeling"


def _jci_pad(paren: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    if any(k == "bijlage" for k, _ in paren):
        return ()
    # Een sub-paragraaf is een geneste paragraaf, zoals de importer haar schrijft (`references._SEGMENTNAAM`).
    paren = [("paragraaf" if k == "sub-paragraaf" else k, v) for k, v in paren]

    def laatste(sleutel: str) -> str | None:
        waarden = [v for k, v in paren if k == sleutel]
        return waarden[-1] if waarden else None

    artikel = laatste("artikel")
    if artikel:
        lid = laatste("lid")
        return (("artikel", artikel), *((("lid", lid),) if lid else ()),
                *((k, v) for k, v in paren if k == "o"))
    return tuple((k, v) for k, v in paren if k in STRUCTUUR)


def vindplaats(ref: str) -> Vindplaats | None:
    """De bronnode van een verwijzing, of None als hij er geen aanwijst."""
    ref = (ref or "").strip().rstrip(".,;\\")
    if _BWB.fullmatch(ref):
        return Vindplaats(f"urn:bwb:{ref}", ref, (), "regeling", "")
    if ref.startswith("urn:bwb:"):
        # Een kapotte escape weigeren, zoals `decodeURIComponent` in de werkplek: `unquote` laat
        # hem stil staan en levert dan een IRI op die de importer nooit schrijft.
        if _KAPOTTE_ESCAPE.search(ref):
            return None
        try:
            delen = [unquote(d, errors="strict") for d in ref[len("urn:bwb:"):].split(":")]
        except UnicodeDecodeError:
            return None
        bwb, rest = delen[0], delen[1:]
        if not _BWB.fullmatch(bwb) or len(rest) % 2 or any(not d for d in rest):
            return None
        pad = tuple(zip(rest[::2], rest[1::2], strict=True))
        if any(k == "id" for k, _ in pad):
            return Vindplaats(ref, bwb, pad, "node", "")
        if any(k not in _SOORT for k, _ in pad):
            return None
    elif m := _JCI.match(ref):
        bwb = m.group(1).upper()
        paren = [(k.lower(), v) for k, v in parse_qsl(m.group(2).lstrip("&"), keep_blank_values=True)
                 if k.lower() not in {"z", "g"}]
        if any(not v for _, v in paren):
            return None
        pad = _jci_pad(paren)
        if paren and not pad:
            return None
    else:
        return None
    iri = f"urn:bwb:{bwb}" + "".join(f":{k}:{_segment(v)}" for k, v in pad)
    return Vindplaats(iri, bwb, pad, _soort(pad), _label(pad))


# ---------------------------------------------------------------------------------------------
# Het label van een bepaling (één regel voor heel Lex)
# ---------------------------------------------------------------------------------------------
#
# Een onderdeel zonder eigen nummer heet in de graaf "Onderdeel –" (het opsommingsstreepje is zijn `bwb:nummer`), een
# lettered onderdeel van de Leidraad "Onderdeel c.". Los gezegd zegt dat niets: drie keer "Onderdeel –" onder elkaar, of
# een letter zonder het artikel eromheen. Zo'n onderdeel heeft een wet-lokale `id:`-IRI, met het knoop-id van
# wetten.overheid.nl erin ("BWBR0024096/Circulaire.divisie25/…/Circulaire.divisie25.3a.1/Tekst/Onderdeel._1"): daar
# staat wél waar het staat. `bepaling_label` maakt daarvan "Artikel 25.3a.1, 1e streepje". De spiegel in de werkplek is
# `frontend/lib/bepalingLabel.ts`; `frontend/lib/bepalingLabel.vectoren.json` toetst beide kanten.

#: De tekens waarmee een ongenummerd onderdeel in de graaf "genummerd" is.
OPSOMMINGSTEKENS = frozenset("–—-•·●▪")

_KNOOPSTAP = re.compile(
    r"(Circulaire\.divisie|Divisie|Hoofdstuk|Titeldeel|Afdeling|Paragraaf|Artikel|Lid|Onderdeel|Slottekst|Bijlage)(.*)")
_STRUCTUURSTAP = {"Divisie": "divisie", "Hoofdstuk": "hoofdstuk", "Titeldeel": "titeldeel", "Afdeling": "afdeling",
                  "Paragraaf": "paragraaf"}
# Een kaal label: alleen een soortwoord met een nummer of opsommingsteken ("Onderdeel –", "Onderdeel c.", "Lid 2", "–").
_KAAL = re.compile(r"^(?:(?:onderdeel|lid|sub|punt|slottekst)\b\.?\s*)?([^\s,]{0,4}?)\.?$", re.I)


def _stap(soort: str, waarde: str) -> str:
    """Eén stap uit een knoop-id in woorden: "lid 2", "onderdeel c", "1e streepje", "slottekst"."""
    waarde = waarde.strip().lstrip(".")
    if soort == "Onderdeel":
        if waarde.startswith("_") and waarde[1:].isdigit():
            return f"{int(waarde[1:])}e streepje"
        return f"onderdeel {waarde}" if waarde else "onderdeel"
    if soort == "Slottekst":
        return "slottekst"  # het volgnummer is een telling van de importer, geen vindplaats
    if soort == "Bijlage":
        return f"bijlage {waarde}" if waarde else "bijlage"
    woord = "artikel" if soort in ("Artikel", "Circulaire.divisie") else soort.lower()
    return f"{woord} {waarde}" if waarde else woord


def knoop_label(knoop_id: str) -> str:
    """Waar een node staat, uit zijn knoop-id: "Artikel 25.3a.1, 1e streepje", "Artikel 9, lid 1, onderdeel e, 2,
    1e streepje", "Bijlage 3, artikel 2, onderdeel d". Leeg als er niets herkenbaars in staat.

    Zelfde vorm als `vindplaats` (`_label`): het structuurpad boven een artikel valt weg, want een artikel is in de
    wettekst al uniek; in een bijlage blijft het staan, daar niet. Een divisie van een beleidsregel heet "Artikel", zoals
    de importer haar vindplaats schrijft en de Leidraad naar haar eigen divisies verwijst ("artikel 28.2 van deze
    leidraad")."""
    stappen = [(m.group(1), m.group(2)) for deel in (knoop_id or "").split("/")[1:]
               if (m := _KNOOPSTAP.fullmatch(deel))]
    if not stappen:
        return ""
    in_bijlage = any(s == "Bijlage" for s, _ in stappen)
    artikel = max((i for i, (s, _) in enumerate(stappen) if s in ("Artikel", "Circulaire.divisie")), default=-1)
    if artikel >= 0:
        # Van geneste divisies telt de diepste: haar nummer draagt het hele pad al ("25.3a.1").
        if stappen[artikel][0] == "Circulaire.divisie":
            stappen = [st for i, st in enumerate(stappen) if st[0] != "Circulaire.divisie" or i == artikel]
            artikel = next(i for i, (s, _) in enumerate(stappen) if s == "Circulaire.divisie")
        boven = stappen[:artikel] if in_bijlage else []
        stappen = [*boven, *stappen[artikel:]]
    delen: list[str] = []
    for soort, waarde in stappen:
        tekst = _stap(soort, waarde)
        # Opeenvolgende onderdelen in één aanduiding, zoals `vindplaats`: "onderdeel e, 2".
        if soort == "Onderdeel" and tekst.startswith("onderdeel ") and delen and delen[-1].startswith("onderdeel "):
            delen[-1] += ", " + tekst[len("onderdeel "):]
        else:
            delen.append(tekst)
    tekst = ", ".join(delen)
    return tekst[:1].upper() + tekst[1:]


def knoop_id_van(iri: str) -> str:
    """Het knoop-id in een wet-lokale `id:`-IRI ("urn:bwb:BWBR…:id:BWBR…%2F…"), anders leeg."""
    vp = vindplaats(iri)
    if vp is None or vp.soort != "node":
        return ""
    return next((v for k, v in vp.pad if k == "id"), "")


def plek_label(iri: str) -> str:
    """Waar een bepaling staat, alleen uit haar IRI of jci: de vindplaats, of bij een `id:`-node zijn knoop-id."""
    vp = vindplaats(iri)
    if vp is None:
        return ""
    return knoop_label(knoop_id_van(iri)) if vp.soort == "node" else vp.label


def kaal_label(label: str) -> bool:
    """Of een label alleen een soortwoord met een nummer of streepje is ("Onderdeel –", "Onderdeel c.", "Lid 2"): het
    zegt dan niet waar de bepaling staat."""
    return bool(_KAAL.match((label or "").strip()))


def bepaling_label(iri: str, gegeven: str = "") -> str:
    """Het label van een bepaling, overal in Lex hetzelfde. Een eigen naam (een divisie van de Leidraad, "Voorwaarden
    standaardbetalingsregeling") blijft staan; een kaal label of de staart van het pad ("Lid 2", "Onderdeel –",
    "Onderdeel c.") wordt de plek uit de IRI ("Artikel 9, lid 2", "Artikel 25.3a.1, 1e streepje"). Zonder plek blijft
    wat er gegeven is; zonder beide leeg, zodat de aanroeper zijn eigen terugval kiest."""
    g = (gegeven or "").strip()
    plek = plek_label(iri)
    if not plek:
        return g
    if not g or kaal_label(g):
        return plek
    kort, lang = g.lower().rstrip("."), plek.lower()
    return plek if lang == kort or lang.endswith(f" {kort}") or lang.endswith(f", {kort}") else g
