"""Van beslissingen naar voorstellen (ADR-004): groepen, relaties en vragen.

- **Groepen**: union-find over de zelfde-betekenis-kandidaten met uitkomst *link*. Daarna per groep
  een controle: ligt er tussen twee leden een *non-link* (sterk tegenbewijs), dan wordt de groep
  niet stil geknipt maar geel voorgelegd, met het conflict erbij. Een optimale verdeling zoeken
  onder must- en cannot-links is in het algemeen NP-volledig, en de keuze hoort bij de jurist.
- **Relaties**: per hypothese en per paar *groepen* één voorstel. Een relatie vanuit twee leden
  van dezelfde groep (de definitie en haar mede-definitie) is dezelfde relatie; de kleinste
  element-id's blijven als representant.
- **Vragen**: zelfde-betekenis-kandidaten met uitkomst *possible link*, één per paar groepen. Een
  vraag vervalt als beide al in één groep staan, of als er tussen hun groepen al sterk tegenbewijs
  ligt: dan is de vraag beantwoord.

Een groep die alleen op een aanname rust (`AANNAMES`: dezelfde term in dezelfde bepaling), is geel:
sterke steun, maar niet doordat de wet het zegt.

Een link of non-link van het model (fase C, `verdieping.py`) loopt door dezelfde functie. Een groep
die op een model-link rust, is altijd geel: het model stelt voor, de jurist beslist.
"""
from __future__ import annotations

from collections import defaultdict

from .model import (
    Aandacht, Besluit, Beslissing, Betekenisgroep, Hypothese, Kandidaat, Polariteit, Relatie, Sterkte, Vraag,
)
from .uitleg import uitleg

VERSIE = "2"


# Codes die een groep vormen zonder dat de wet het verband legt.
AANNAMES = frozenset({"ZELFDE_BEPALING"})


def _op_aanname(k: Kandidaat) -> bool:
    """De link rust alleen op een aanname: geen sterke steun buiten `AANNAMES`."""
    sterk = {b.code for b in k.bewijs if b.polariteit is Polariteit.STEUN and b.sterkte is Sterkte.STERK}
    return bool(sterk) and sterk <= AANNAMES


class _UnionFind:
    def __init__(self, items: list[str]):
        self.ouder = {x: x for x in items}

    def wortel(self, x: str) -> str:
        while self.ouder[x] != x:
            self.ouder[x] = self.ouder[self.ouder[x]]
            x = self.ouder[x]
        return x

    def verbind(self, a: str, b: str) -> None:
        ra, rb = self.wortel(a), self.wortel(b)
        if ra != rb:
            self.ouder[max(ra, rb)] = min(ra, rb)        # deterministisch: kleinste id is wortel


def groepeer(element_ids: list[str], kandidaten: list[Kandidaat], beslissingen: dict[str, Beslissing]
             ) -> tuple[list[Betekenisgroep], list[Relatie], list[Vraag]]:
    uf = _UnionFind(sorted(element_ids))
    zelfde = [k for k in kandidaten if k.hypothese is Hypothese.ZELFDE_BETEKENIS]
    for k in zelfde:
        if beslissingen[k.id].besluit is Besluit.LINK:
            uf.verbind(*k.leden)

    leden: dict[str, list[str]] = defaultdict(list)
    for x in sorted(element_ids):
        leden[uf.wortel(x)].append(x)

    tegen = [k for k in zelfde if beslissingen[k.id].besluit is Besluit.NON_LINK]
    groepen = []
    for wortel, ids in sorted(leden.items()):
        if len(ids) < 2:
            continue
        links = [k for k in zelfde if beslissingen[k.id].besluit is Besluit.LINK
                 and uf.wortel(k.van) == wortel]
        conflicten = [k for k in tegen if uf.wortel(k.van) == wortel and uf.wortel(k.naar) == wortel]
        groepen.append(Betekenisgroep.maak(
            ids, [k.id for k in links], [k.id for k in conflicten],
            Aandacht.GEEL if conflicten or any(beslissingen[k.id].door == "model" or _op_aanname(k) for k in links)
            else Aandacht.GROEN,
            uitleg([*links, *conflicten], beslissingen)))

    # Relaties: één per (hypothese, groep van, groep naar).
    per_sleutel: dict[tuple, list[Kandidaat]] = defaultdict(list)
    for k in kandidaten:
        if k.hypothese is Hypothese.ZELFDE_BETEKENIS:
            continue
        if beslissingen[k.id].besluit is Besluit.NON_LINK:
            continue
        per_sleutel[(k.hypothese, uf.wortel(k.van), uf.wortel(k.naar))].append(k)
    relaties = []
    for (hyp, _, _), ks in sorted(per_sleutel.items(), key=lambda kv: (kv[0][0].value, kv[0][1], kv[0][2])):
        ks = sorted(ks, key=lambda k: (k.van, k.naar))
        groen = any(beslissingen[k.id].besluit is Besluit.LINK for k in ks)
        rep = next((k for k in ks if beslissingen[k.id].besluit is Besluit.LINK), ks[0])
        relaties.append(Relatie(kandidaat_id=rep.id, hypothese=hyp, van=rep.van, naar=rep.naar,
                                aandacht=Aandacht.GROEN if groen else Aandacht.GEEL,
                                uitleg=uitleg(ks, beslissingen)))

    # Vragen: één per paar groepen, niet als het al beantwoord is.
    beantwoord = {frozenset((uf.wortel(k.van), uf.wortel(k.naar))) for k in tegen}
    vragen: dict[frozenset, Vraag] = {}
    for k in sorted(zelfde, key=lambda k: (k.van, k.naar)):
        if beslissingen[k.id].besluit is not Besluit.POSSIBLE_LINK:
            continue
        paar = frozenset((uf.wortel(k.van), uf.wortel(k.naar)))
        if len(paar) == 1 or paar in beantwoord or paar in vragen:
            continue
        vragen[paar] = Vraag(kandidaat_id=k.id, van=k.van, naar=k.naar,
                             regel=beslissingen[k.id].regel, uitleg=uitleg([k], beslissingen))
    return groepen, relaties, sorted(vragen.values(), key=lambda v: (v.van, v.naar))
