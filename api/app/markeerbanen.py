"""Markeerbanen: overlappende markeringen zo tonen dat ze allemaal te zien zijn (optie B uit
`docs/architectuur/voorstel-markeringen-en-diagrammen.md`, besluit gebruiker 18 nov 2026).

Een markering die geen andere omvat, krijgt het **vlak** in haar JAS-kleur, zoals de jurist gewend is. Een markering die
andere omvat (meestal een rechtsbetrekking, voorwaarde of afleidingsregel over een hele zin) krijgt een **baan**: een streep
onder de tekst, op een vaste hoogte over haar hele lengte. Zo valt de kleinere markering niet meer weg in de grote, en
blijft van de grote te zien waar ze begint en eindigt.

Dit is de rekenkern. Hij kent geen tekst en geen eenheid: offsets zijn gehele getallen in de eenheid van de aanroeper
(codepoints in het rapport, UTF-16 of codepoints in de werkplek). De tweeling is `frontend/lib/markeerbanen.ts`; beide
toetsen tegen `frontend/lib/markeerbanen.vectoren.json`, zodat rapport en werkplek dezelfde banen tekenen.

De regels, deterministisch bij een gegeven volgorde van de invoer:

1. Een markering **omvat** een andere als ze haar helemaal bevat en langer is.
2. De markeringen die niets omvatten, krijgen in de volgorde (lengte, begin, invoer) het vlak, zolang ze geen vlak
   raken dat al vergeven is. Vlakken overlappen dus nooit; wie verliest (twee klassen op hetzelfde fragment, of twee
   kleine die elkaar half overlappen), krijgt een baan.
3. De rest krijgt in dezelfde volgorde de laagste baan waar ze niets raakt: kort dicht bij de tekst, lang eronder.
4. De tekst wordt geknipt op elke grens. Per stuk: het vlak, de banen erover (op baan) en de markeringen die er
   eindigen (in de volgorde van de invoer, voor het nummer in superscript).
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Hashable, Sequence


@dataclass(frozen=True)
class Stuk:
    start: int
    eind: int
    vlak: Hashable | None                          # de sleutel van de markering met het vlak, of geen
    banen: tuple[tuple[Hashable, int], ...]        # (sleutel, baan), op baan oplopend
    eindigt: tuple[Hashable, ...]                  # sleutels die aan het eind van dit stuk eindigen


@dataclass(frozen=True)
class Banen:
    stukken: tuple[Stuk, ...]
    aantal: int                                    # hoeveel banen er nodig zijn (0 als alles een vlak heeft)
    baan: dict                                     # sleutel → baan, alleen voor markeringen met een baan


def _raakt(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def markeerbanen(lengte: int, spans: Sequence[tuple[Hashable, int, int]]) -> Banen:
    """`spans` is een rij (sleutel, start, eind), eind exclusief. Een sleutel mag vaker voorkomen (een markering met meer
    ankers); elk anker telt dan los. Een anker buiten de tekst wordt afgekapt, een leeg anker telt niet."""
    norm = [(i, k, max(0, s), min(lengte, e)) for i, (k, s, e) in enumerate(spans)]
    norm = [x for x in norm if x[3] > x[2]]

    def orde(x):
        return (x[3] - x[2], x[2], x[0])

    omvat = {x[0] for x in norm
             if any(y[0] != x[0] and x[2] <= y[2] and y[3] <= x[3] and (x[3] - x[2]) > (y[3] - y[2]) for y in norm)}

    vlak: list[tuple] = []
    rest: list[tuple] = []
    for x in sorted((x for x in norm if x[0] not in omvat), key=orde):
        (rest if any(_raakt((x[2], x[3]), (v[2], v[3])) for v in vlak) else vlak).append(x)
    rest += [x for x in norm if x[0] in omvat]

    baan_van: dict[int, int] = {}
    bezet: list[list[tuple[int, int]]] = []
    for x in sorted(rest, key=orde):
        for j, lijst in enumerate(bezet):
            if not any(_raakt((x[2], x[3]), r) for r in lijst):
                lijst.append((x[2], x[3]))
                baan_van[x[0]] = j
                break
        else:
            bezet.append([(x[2], x[3])])
            baan_van[x[0]] = len(bezet) - 1

    vlak_ids = {v[0] for v in vlak}
    grenzen = sorted({0, lengte, *(x[2] for x in norm), *(x[3] for x in norm)})
    stukken: list[Stuk] = []
    for a, b in pairwise(grenzen):
        dekking = [x for x in norm if x[2] <= a and x[3] >= b]
        v = next((x[1] for x in dekking if x[0] in vlak_ids), None)
        banen = tuple((x[1], baan_van[x[0]]) for x in sorted((x for x in dekking if x[0] in baan_van),
                                                             key=lambda x: (baan_van[x[0]], x[0])))
        eindigt: list[Hashable] = []
        for x in norm:
            if x[3] == b and x[2] < b and x[1] not in eindigt:
                eindigt.append(x[1])
        stukken.append(Stuk(a, b, v, banen, tuple(eindigt)))
    return Banen(tuple(stukken), len(bezet), {x[1]: baan_van[x[0]] for x in norm if x[0] in baan_van})
