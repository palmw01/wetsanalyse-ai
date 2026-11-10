"""De zoekvragen aan de SRU van KOOP, gedeeld door de connectors Kamerstukken en Staatsblad en Staatscourant (ADR-013).

De CQL bouwt de tool, nooit het model: woorden in de titel, een zinsdeel of woorden in de hele tekst, de volgorde op
de datum, en een pagina op records met een exact vervolg. Alleen `sortBy` in de CQL sorteert: de parameter `sortKeys`
negeert de dienst zonder melding (live, 9 nov 2026; opnieuw bevestigd 10 nov 2026 voor het Staatsblad).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ..resultaat import BUDGET, TeGroot, compact, resultaat

WOORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]{3,}")
MAX_WOORDEN = 6
#: Hoogstens zo veel stukken per pagina.
LIMIT = 25
#: De volgordes op de documentdatum (`dt.date`). Het id als tweede sleutel maakt de volgorde bij dezelfde datum vast,
#: zodat pagineren stabiel is.
OP_VOLGORDE = {"nieuwste": " sortBy dt.date/sort.descending dt.identifier/sort.ascending",
               "oudste": " sortBy dt.date/sort.ascending dt.identifier/sort.ascending"}
_ZINSDEEL_RE = re.compile(r'"([^"]*)"|„([^”]*)”')


def cql_woorden(woorden: str, *, zonder: str = "geef woorden van minstens drie letters") -> str:
    """Elk woord (minstens drie letters, hoogstens `MAX_WOORDEN`) in de titel (`dt.title`)."""
    gevonden = list(dict.fromkeys(w.lower() for w in WOORD_RE.findall(woorden or "")))[:MAX_WOORDEN]
    if not gevonden:
        raise ValueError(zonder)
    return " AND ".join(f'dt.title any "{w}"' for w in gevonden)


def tekst_woorden(tekst: str) -> int:
    """Hoeveel verschillende woorden een tekstfilter telt."""
    return len(set(WOORD_RE.findall((tekst or "").lower())))


def tekst_cql(tekst: str) -> str:
    """De hele tekst van het stuk (`cql.textAndIndexes`): een zinsdeel tussen aanhalingstekens als zinsdeel (`adj`), de
    losse woorden allemaal (`all`). Live getoetst op 9 nov 2026: 'één bankrekeningnummer' vond de acht stukken uit het
    onderzoek naar één bankrekeningnummer, in de titel drie (meting kamerstukken-tekstzoeken-2026-11-09)."""
    zinsdelen = [" ".join(WOORD_RE.findall(a or b)).lower() for a, b in _ZINSDEEL_RE.findall(tekst)]
    los = list(dict.fromkeys(w.lower() for w in WOORD_RE.findall(_ZINSDEEL_RE.sub(" ", tekst))))
    delen, aantal = [], 0
    for z in (z for z in dict.fromkeys(zinsdelen) if z):
        delen.append(f'cql.textAndIndexes adj "{z}"')
        aantal += len(z.split())
    if aantal + len(los) > MAX_WOORDEN:
        # De tool weigert dit al met een invoerfout: hier nooit stil inkorten.
        raise ValueError(f"tekst: hoogstens {MAX_WOORDEN} woorden")
    if los:
        delen.append(f'cql.textAndIndexes all "{" ".join(los)}"')
    if not delen:
        raise ValueError("tekst")
    return " AND " + " AND ".join(delen)


def zoekvraag(args: dict[str, Any], volgorde: str) -> dict[str, Any]:
    """Wat er gezocht is, voor bij een lijst: de filters en de volgorde, zonder het vervolg."""
    return {**{k: v for k, v in args.items() if k not in {"offset", "volgorde"}}, "volgorde": volgorde}


def per_record(bron: Any, cql: str, args: dict[str, Any], offset: int, *, tool: str,
               rij: Callable[[Any], dict[str, Any] | None], toelichting: str = "", leeg: str = "",
               extra: dict[str, Any] | None = None, extra_van: Callable[[list[Any]], dict[str, Any]] | None = None,
               maximum: int = LIMIT) -> str:
    """Een pagina in de volgorde van de zoekdienst. Per record één rij of niets; het vervolg telt in records, zoals de
    zoekdienst, en `totaal` is het aantal records van de hele zoekvraag. Binnen de begroting op hele rijen."""
    totaal, deel = bron.zoek(cql, start=offset + 1, maximum=maximum)
    paren = [(i, r) for i, r in enumerate(rij(rec) for rec in deel) if r]
    erbij = extra_van(deel) if extra_van else {}

    def maak(k: int) -> str:
        gelezen = paren[k][0] if k < len(paren) else len(deel)
        meer = offset + gelezen < totaal
        return resultaat([r for _, r in paren[:k]], volledig=not meer, totaal=totaal,
                         vervolg={"tool": tool, "args": {**args, "offset": offset + gelezen}} if meer else None,
                         toelichting=toelichting if paren else (leeg or toelichting),
                         extra=compact({**(extra or {}), **erbij}) or None)

    k = len(paren)
    while k > 0 and len(maak(k)) > BUDGET:
        k -= 1
    if paren and k == 0:
        raise TeGroot(f"{tool}: één rij is groter dan de begroting", omvang=len(maak(1)))
    return maak(k)
