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
from .model import Bron, Fragment, Manifest, Taalanalyse, fragment_id

VERSIE = "1"

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


def alle(manifest: Manifest) -> dict[str, Fragment]:
    """Alle fragmenten van het manifest op id – de vaste ruimte waarbinnen een id geldig is."""
    return {f.id: f for b in manifest.bronnen for f in knip(b)}


def voor_groep(manifest: Manifest, taal: dict[str, Taalanalyse], leden: tuple[str, ...],
               wts: list[definities.WettelijkeTerm], maximum: int = 40) -> list[Fragment]:
    """De fragmenten waar een definitie van deze groep op mag rusten: de bronnen van de leden, en de
    begripsbepalingen in het manifest van een term die een lid draagt."""
    termen = {taal[e].term for e in leden if e in taal}
    iris = list(dict.fromkeys(
        [manifest.formulering(e).bron_iri for e in leden]
        + [w.bron_iri for w in wts if w.term in termen and w.soort in ("definitie", "mede")]))
    # Een fragment dat alleen de term zelf is ("aanslagbiljet" vóór de dubbele punt) definieert niets.
    kaal = termen | {" ".join(manifest.formulering(e).tekst.lower().split()) for e in leden}
    uit = [f for iri in iris for f in knip(manifest.bron(iri)) if " ".join(f.tekst.lower().split()) not in kaal]
    return uit[:maximum]
