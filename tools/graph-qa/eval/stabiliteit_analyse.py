"""Reproduceerbaarheid over herhaalde runs: waar wisselt de keten tussen runs?

Rekenfuncties die `eval/compare_pipelines.py` per casus gebruikt: de elementen van alle runs
worden uitgelijnd op hun positie in de casustekst, en per cluster telt `analyseer_casus` in hoeveel
runs het voorkomt, of de span gelijk is en of de klasse gelijk is.

Dit is een reproduceerbaarheidsmeting, geen kwaliteitsoordeel: een keten kan heel stabiel
dezelfde fout maken. Hoge overeenstemming is dus nooit op zichzelf bewijs van verbetering.
"""
from __future__ import annotations

import re
from collections import Counter
from itertools import combinations
from statistics import mean, pstdev
from typing import Any

Span = tuple[int, int]
_CONTEXT = 16


def _zoek_tekst(tekst: str, fragment: str) -> list[Span]:
    """Alle voorkomens van `fragment`, witruimte-ongevoelig (het model normaliseert die soms)."""
    woorden = fragment.split()
    if not woorden:
        return []
    patroon = r'\s+'.join(re.escape(w) for w in woorden)
    return [(m.start(), m.end()) for m in re.finditer(patroon, tekst)]


def _plaats_anker(tekst: str, anker: dict[str, Any]) -> Span | None:
    """Positie van een anker via zijn context; offsets zelf kunnen op een ander corpus slaan."""
    lengte = int(anker.get('eind', 0)) - int(anker.get('start', 0))
    voor = (anker.get('voor') or '')[-_CONTEXT:]
    na = (anker.get('na') or '')[:_CONTEXT]
    if lengte <= 0 or not (voor or na):
        return None
    raak = [p for p in range(len(tekst) - lengte + 1)
            if tekst[:p].endswith(voor) and tekst[p + lengte:].startswith(na)]
    return (raak[0], raak[0] + lengte) if len(raak) == 1 else None


def plaats(element: dict[str, Any], tekst: str) -> tuple[Span | None, bool]:
    """(span, ambigu). Eerst via de ankers, anders via de tekst; `None` als het niet te plaatsen is.

    Bij meerdere ankers (een element uit losse fragmenten) telt de omhullende span.
    """
    ankers = [s for s in (_plaats_anker(tekst, a) for a in element.get('ankers') or []) if s]
    if ankers and len(ankers) == len(element.get('ankers') or []):
        return (min(s for s, _ in ankers), max(e for _, e in ankers)), False
    raak = _zoek_tekst(tekst, element.get('tekst', ''))
    if not raak:
        return None, False
    return raak[0], len(raak) > 1


def iou(a: Span, b: Span) -> float:
    doorsnede = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    vereniging = max(a[1], b[1]) - min(a[0], b[0])
    return doorsnede / vereniging if vereniging else 0.0


# Onder deze overlap is een ander element waarschijnlijker dan een verschoven span. Bij een
# andere klasse ligt de lat hoger: verschoven én anders geklasseerd is meestal een ander element.
MIN_IOU_ZELFDE_KLASSE = 0.4
MIN_IOU_ANDERE_KLASSE = 0.8


def cluster(per_run: list[list[tuple[Span, str]]]) -> list[dict[int, tuple[Span, str]]]:
    """Lijn elementen over runs uit: elk cluster bevat per run hooguit één element.

    Per run in twee stappen. Eerst sluit elk element aan bij een cluster met exact dezelfde span.
    Daarna gaat de rest, grootste eerst, naar het vrije cluster met de meeste overlap boven de
    drempel; anders begint het een nieuw cluster. Zonder die volgorde kaapt een lang omhullend
    element ("Tot de weerlegging … de bestuurder die …") het cluster van een genest element, schuift
    alles een plek op en lijkt een stabiele annotatie vol klassewissels te zitten.
    """
    clusters: list[dict[int, tuple[Span, str]]] = []
    for run, elementen in enumerate(per_run):
        rest = []
        for span, klasse in elementen:
            gelijk = next((c for c in clusters if run not in c
                           and any(span == s for s, _ in c.values())), None)
            if gelijk is None:
                rest.append((span, klasse))
            else:
                gelijk[run] = (span, klasse)
        for span, klasse in sorted(rest, key=lambda x: (x[0][0] - x[0][1], x[0][0])):
            beste, score = None, 0.0
            for c in clusters:
                if run in c:
                    continue
                for andere, k in c.values():
                    drempel = MIN_IOU_ZELFDE_KLASSE if k == klasse else MIN_IOU_ANDERE_KLASSE
                    s = iou(span, andere)
                    if s >= drempel and s > score:
                        beste, score = c, s
            if beste is None:
                clusters.append({run: (span, klasse)})
            else:
                beste[run] = (span, klasse)
    return sorted(clusters, key=lambda c: min(s[0] for s, _ in c.values()))


def _paarsgewijs(waarden: list[Any], gelijk) -> float | None:
    paren = list(combinations(waarden, 2))
    return sum(gelijk(a, b) for a, b in paren) / len(paren) if paren else None


def analyseer_casus(tekst: str, runs: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Stabiliteitsmaten voor één casus en één fase; `runs` = elementlijst per run."""
    n = len(runs)
    per_run: list[list[tuple[Span, str]]] = []
    onplaatsbaar = ambigu = 0
    for elementen in runs:
        geplaatst = []
        for e in elementen:
            span, dubbel = plaats(e, tekst)
            if span is None:
                onplaatsbaar += 1
                continue
            ambigu += dubbel
            geplaatst.append((span, e.get('klasse', '')))
        per_run.append(geplaatst)

    clusters = cluster(per_run)
    aantallen = [len(r) for r in runs]
    in_alle = sum(1 for c in clusters if len(c) == n)
    meervoudig = [c for c in clusters if len(c) >= 2]
    paren: Counter[tuple[str, str]] = Counter()
    voorbeelden: dict[str, str] = {}
    detail = []
    for c in clusters:
        spans = [s for s, _ in c.values()]
        klassen = [k for _, k in c.values()]
        eerste = spans[0]
        fragment = tekst[eerste[0]:eerste[1]]
        for a, b in combinations(klassen, 2):
            if a != b:
                paar = tuple(sorted((a, b)))
                paren[paar] += 1
                voorbeelden.setdefault(' ↔ '.join(paar), fragment)
        detail.append({
            'fragment': fragment, 'runs': sorted(c), 'aanwezig': len(c),
            'klassen': dict(Counter(klassen)), 'spans_gelijk': len(set(spans)) == 1,
        })

    def gemiddeld(waarden: list[float | None]) -> float | None:
        w = [x for x in waarden if x is not None]
        return round(mean(w), 3) if w else None

    return {
        'runs': n,
        'elementen_per_run': aantallen,
        'elementen_gemiddeld': round(mean(aantallen), 2) if aantallen else 0,
        'elementen_spreiding': round(pstdev(aantallen), 2) if aantallen else 0,
        'onplaatsbaar': onplaatsbaar, 'ambigu_geplaatst': ambigu,
        'clusters': len(clusters),
        'detectie_stabiel': round(in_alle / len(clusters), 3) if clusters else None,
        'span_exact': gemiddeld([1.0 if len({s for s, _ in c.values()}) == 1 else 0.0 for c in meervoudig]),
        'span_iou': gemiddeld([_paarsgewijs([s for s, _ in c.values()], iou) for c in meervoudig]),
        'klasse_unaniem': gemiddeld([1.0 if len({k for _, k in c.values()}) == 1 else 0.0 for c in meervoudig]),
        'klasse_paarsgewijs': gemiddeld([_paarsgewijs([k for _, k in c.values()], lambda a, b: a == b)
                                         for c in meervoudig]),
        'klasseparen': {' ↔ '.join(p): k for p, k in paren.most_common()},
        'voorbeelden': voorbeelden,
        'detail': detail,
    }












