"""Eén antwoord op "welke bronnode is dit?" voor een graaf-IRI, een jci of een kaal BWB-id.

Dezelfde vraag werd op drie plekken verschillend beantwoord: de importer (welke IRI schrijft hij),
de werkplek (`bronDoel` in frontend/lib/samenhang.ts) en de agent (zijn bronnenlijst). Liepen ze
uiteen, dan stond één bepaling twee keer in de bronnen (als IRI én als jci), viel een hoofdstuk samen
met de hele regeling, of opende de 3D-graaf een node die niet bestaat.

De regels zijn die van de importer (`jci_node_ref_key` + `Vocab.by_ref_key` in tools/bwb-import):

- met een artikel: `artikel` (het laatste), `lid` (het laatste) en elke `o`; het structuurpad
  ernaartoe hoort er níét in, want een artikel is binnen de regeling al uniek;
- zonder artikel: het volledige structuurpad (hoofdstuk, titeldeel, afdeling, paragraaf), want
  "afdeling 1" komt in elk hoofdstuk terug;
- zonder artikel én zonder structuur (alleen `&bijlage=1&o=a`) wijst een jci geen eigen node aan:
  geen vindplaats, in plaats van stil de hele regeling.

`frontend/lib/jci-vectoren.json` is de gedeelde vectorset; alle drie de kanten toetsen ertegen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, unquote

_BWB = re.compile(r"^BWB[RV]\d+$")
_JCI = re.compile(r"^jci[\d.]+:c:(BWB[RV]\d+)(.*)$", re.I)
_KAPOTTE_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
STRUCTUUR = ("hoofdstuk", "titeldeel", "afdeling", "paragraaf")
_SOORT = {"o": "onderdeel", **{s: s for s in (*STRUCTUUR, "artikel", "lid")}}


@dataclass(frozen=True)
class Vindplaats:
    """`soort` is `regeling`, een structuursoort, `artikel`, `lid`, `onderdeel` of `node` (een
    wet-lokale `id:`-IRI, herkend maar zonder leesbaar label). `label` is leeg voor een regeling:
    haar naam staat in de graaf, niet in de verwijzing."""

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
        pad = tuple(zip(rest[::2], rest[1::2]))
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
