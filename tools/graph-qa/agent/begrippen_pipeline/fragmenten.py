"""Letterlijke fragmenten van de brontekst (spoor D, fase C): wat het model op id mag kiezen.

Het model typt geen brontekst over. Code knipt elke bron in zinnen en zinsdelen, geeft elk stuk een
id dat uit bron en offsets volgt (`model.fragment_id`), en het model noemt alleen die id's. Een
samengestelde definitie bestaat dus per constructie uit letterlijke tekst.

Knippen gebeurt op `;`, op `:` gevolgd door witruimte (de term van een begripsbepaling wordt zo een
eigen fragment) en op een punt gevolgd door witruimte en een hoofdletter, zodat "art." of "o.a."
een zin niet breken. Witruimte en het scheidingsteken zelf vallen buiten het fragment.
"""
from __future__ import annotations

import re

from . import definities
from .model import Bron, Fragment, Manifest, Onderzoek, Reden, Taalanalyse, fragment_id

VERSIE = "2"

_GRENS = re.compile(r";|:(?=\s)|\.(?=\s+[A-Z])")
_MIN = 3


def knip(bron: Bron) -> list[Fragment]:
    uit: list[Fragment] = []
    begin = 0
    for m in [*_GRENS.finditer(bron.tekst), None]:
        eind = m.start() if m else len(bron.tekst)
        stuk = bron.tekst[begin:eind]
        links = len(stuk) - len(stuk.lstrip())
        s, e = begin + links, begin + len(stuk.rstrip())
        if e > s and e - s >= _MIN:
            if (e - s) and bron.tekst[e - 1] == "." and m is None:
                e -= 1                                   # de slotpunt hoort niet bij de definitie
            uit.append(Fragment(id=fragment_id(bron.bron_iri, s, e), bron_iri=bron.bron_iri, start=s, eind=e,
                                tekst=bron.tekst[s:e]))
        begin = m.end() if m else len(bron.tekst)
    return uit


def alle(manifest: Manifest, onderzoek: Onderzoek | None = None) -> dict[str, Fragment]:
    """Alle fragmenten van het manifest (en de contextbronnen van het onderzoek) op id – de vaste ruimte
    waarbinnen een id geldig is. Het id volgt uit bron en offsets, dus een fragment van het manifest
    houdt zijn id, met of zonder onderzoek."""
    bronnen = [*manifest.bronnen, *(onderzoek.bronnen if onderzoek else ())]
    return {f.id: f for b in bronnen for f in knip(b)}


def _norm(tekst: str) -> str:
    return " ".join(tekst.lower().split())


# De volgorde waarin contextbronnen meegaan, na de definities in de context en de eigen bronnen.
_REDENVOLGORDE = (Reden.ZELFDE_ARTIKEL, Reden.VERWIJZING, Reden.CONTEXTSELECTIE)


def onderzoeksfragmenten(manifest: Manifest, onderzoek: Onderzoek | None, eigen_iris: list[str],
                         termen: set[str], kaal: set[str], maximum: int = 40) -> list[Fragment]:
    """De fragmenten waar een definitie (of een kaartactie) op mag rusten, in een vaste volgorde:

    1. begripsbepalingen in de context die een van de `termen` definiëren;
    2. de eigen bronnen (`eigen_iris`: de bronnen van de leden en de begripsbepalingen in het manifest);
    3. de andere leden van hetzelfde artikel;
    4. de bronnen waarnaar verwezen wordt;
    5. de contextselecties zonder annotaties.

    Een fragment dat alleen de term zelf is (`kaal`, genormaliseerd), definieert niets en valt weg.
    Zonder onderzoek is dit precies de oude ruimte: alleen stap 2.
    """
    contextdef: list[str] = []
    rest: list[str] = []
    if onderzoek is not None:
        for b in onderzoek.bronnen:
            if termen & set(definities.gedefinieerde_termen(b)):
                contextdef.append(b.bron_iri)
        for reden in _REDENVOLGORDE:
            rest += [b.bron_iri for b in onderzoek.bronnen if b.reden is reden and b.bron_iri not in contextdef]
    def bron(iri: str) -> Bron:
        return onderzoek.bron(iri) if iri not in {b.bron_iri for b in manifest.bronnen} else manifest.bron(iri)
    iris = list(dict.fromkeys([*contextdef, *eigen_iris, *rest]))
    uit = [f for iri in iris for f in knip(bron(iri)) if _norm(f.tekst) not in kaal]
    return uit[:maximum]


def voor_groep(manifest: Manifest, taal: dict[str, Taalanalyse], leden: tuple[str, ...],
               wts: list[definities.WettelijkeTerm], maximum: int = 40,
               onderzoek: Onderzoek | None = None) -> list[Fragment]:
    """De fragmenten waar een definitie van deze groep op mag rusten: de bronnen van de leden, de
    begripsbepalingen in het manifest van een term die een lid draagt, en – met een onderzoek – de
    context (`onderzoeksfragmenten`)."""
    termen = {taal[e].term for e in leden if e in taal}
    iris = list(dict.fromkeys(
        [manifest.formulering(e).bron_iri for e in leden]
        + [w.bron_iri for w in wts if w.term in termen and w.soort in ("definitie", "mede")]))
    # Een fragment dat alleen de term zelf is ("aanslagbiljet" vóór de dubbele punt) definieert niets.
    kaal = termen | {_norm(manifest.formulering(e).tekst) for e in leden}
    return onderzoeksfragmenten(manifest, onderzoek, iris, termen, kaal, maximum)
