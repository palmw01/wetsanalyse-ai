"""Het resultaatcontract van de graaftools: begrensd in de tool, nooit afgeknipt daarna.

Een graaftool leverde ruwe SPARQL-TSV en de uitvoeringsgrens knipte die op 8000 tekens af – midden
in de data, in IRI-volgorde, met een aanwijzing (`offset`) die de meeste tools niet kenden. Het model
kreeg zo een willekeurige greep uit een inhoudsopgave en vulde de gaten met "…".

Nu levert elke graaftool dezelfde vorm als de annotatie-leestools:

    {"status": "ok", "volledig": true|false, "aantal": n, "totaal"?: m,
     "vervolg"?: {"tool": …, "args": {…}}, "resultaten": [ … ], "toelichting"?: "…"}

- **`volledig`** betekent: alles wat binnen de scope van déze aanroep valt, staat erin. Niet "alles
  over de bron". Een inhoudsopgave met ingeklapte delen is volledig zolang elk deel genoemd of geteld
  is; zo'n deel draagt een eigen `openen`-aanroep (verdieping, buiten de scope).
- **`vervolg`** is er als, en alleen als, `volledig` false is: de aanroep die dezelfde resultaatset
  aanvult. Dat mag een ándere tool zijn (`get_artikel` → `get_lid` voor de rest); de argumenten zijn
  geldig tegen het schema van `vervolg.tool`. `ok` + `volledig: false` zonder `vervolg` bestaat niet.
- **`aantal`** is altijd `len(resultaten)` van deze respons. Tellingen die iets anders tellen staan op
  de rij zelf (`bepalingen`) of in een eigen veld (`telling`).
- **`status`**: `ok`, of `error` met een `reden` (`resultaatcontract_overschreden`,
  `ondeelbare_eenheid_te_groot`, …). Geen derde "gedeeltelijk": dat is `ok` + `volledig: false`.
- **De tool begrenst, op een natuurlijke grens** (een rij, een lid, een structuurniveau). Past een rij
  niet meer binnen `BUDGET`, dan stopt hij vóór die rij en zet hij `vervolg`. Niets wordt doorgeknipt.
- Rijen zijn compact: lege velden gaan eruit. Elke rij houdt haar vindplaats (graaf-IRI en/of jci),
  zodat bronnen en grounding blijven werken – die lezen vindplaatsen uit de tekst van het resultaat.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

# Eén begroting per toolresultaat, in tekens van de JSON zoals het model hem krijgt.
BUDGET = 8000


def compact(rij: dict[str, Any]) -> dict[str, Any]:
    """Een rij zonder lege velden: een lege OPTIONAL is geen informatie, wel ruis."""
    return {k: v for k, v in rij.items() if v not in ("", None, [], {})}


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def resultaat(
    resultaten: Sequence[dict[str, Any]],
    *,
    volledig: bool = True,
    vervolg: dict[str, Any] | None = None,
    totaal: int | None = None,
    toelichting: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """Het contract als JSON-tekst. `vervolg` = {"tool": naam, "args": {...}}."""
    data: dict[str, Any] = {"status": "ok", "volledig": volledig, "aantal": len(resultaten)}
    if totaal is not None:
        data["totaal"] = totaal
    if vervolg is not None:
        data["vervolg"] = vervolg
    if extra:
        data.update(extra)
    if toelichting:
        data["toelichting"] = toelichting
    data["resultaten"] = list(resultaten)
    return _json(data)


def passend(
    rijen: Sequence[dict[str, Any]],
    maak: Callable[[Sequence[dict[str, Any]]], str],
    budget: int = BUDGET,
) -> tuple[int, str]:
    """Hoeveel rijen (vanaf het begin) passen binnen de begroting, en het resultaat daarmee.

    `maak(rijen[:k])` bouwt het volledige contract voor k rijen – mét de `vervolg` die bij k hoort –
    zodat de meting over precies de tekst gaat die het model krijgt. Groeit lineair; de lijsten zijn
    begrensd (≤ 200 rijen), dus zoeken is niet nodig. Geeft (0, maak([])) als zelfs één rij niet past:
    dan is de rij zelf te groot en moet de tool haar vorm herzien, niet hier knippen.
    """
    beste = maak(rijen[:0])
    k = 0
    for i in range(1, len(rijen) + 1):
        tekst = maak(rijen[:i])
        if len(tekst) > budget:
            break
        k, beste = i, tekst
    return k, beste


def pagina(
    rijen_plus_een: Sequence[dict[str, Any]],
    *,
    tool: str,
    args: dict[str, Any],
    limit: int,
    offset: int,
    toelichting: str = "",
    extra: dict[str, Any] | None = None,
    budget: int = BUDGET,
) -> str:
    """Een pagina van een gerangschikte lijst. De query vraagt `limit + 1` rijen op: de extra rij
    bewijst dat er meer is, zonder een tweede telquery."""
    meer = len(rijen_plus_een) > limit
    rijen = [compact(r) for r in rijen_plus_een[:limit]]

    def maak(deel: Sequence[dict[str, Any]]) -> str:
        volledig = not meer and len(deel) == len(rijen)
        vervolg = None if volledig else {"tool": tool, "args": {**args, "offset": offset + len(deel)}}
        return resultaat(deel, volledig=volledig, vervolg=vervolg, toelichting=toelichting, extra=extra)

    k, tekst = passend(rijen, maak, budget)
    if rijen and k == 0:
        # Een vervolg met dezelfde offset zou een lus zijn. Eén rij groter dan de begroting is een
        # fout in de vorm van die tool (`tests/test_resultaatcontract.py` vangt hem), geen datazaak.
        raise TeGroot(f"{tool}: één rij is groter dan de begroting van {budget} tekens",
                      omvang=len(maak(rijen[:1])))
    return tekst


def per_eenheid(
    eenheden: Sequence[dict[str, Any]],
    *,
    tool: str,
    args: dict[str, Any],
    offset: int,
    toelichting: str = "",
    extra: dict[str, Any] | None = None,
    budget: int = BUDGET,
) -> str:
    """Pagineer over eenheden die al compleet zijn opgehaald (de leden van één artikel, de onderdelen
    van één lid): vanaf `offset` zoveel hele eenheden als passen, met `vervolg` naar de volgende."""
    rest = list(eenheden[offset:])
    return pagina(rest, tool=tool, args=args, limit=len(rest), offset=offset, toelichting=toelichting,
                  extra=extra, budget=budget)


def geheel(
    rijen: Sequence[dict[str, Any]],
    *,
    tool: str,
    toelichting: str = "",
    extra: dict[str, Any] | None = None,
    budget: int = BUDGET,
) -> str:
    """Een resultaat dat van aard begrensd is (één regeling, één bepaling): alles, of een fout."""
    tekst = resultaat([compact(r) for r in rijen], toelichting=toelichting, extra=extra)
    if len(tekst) > budget:
        raise TeGroot(f"{tool}: het resultaat is groter dan de begroting van {budget} tekens", omvang=len(tekst))
    return tekst


class TeGroot(ValueError):
    """Een ondeelbare eenheid (één rij, één lid, één structuurdeel) is groter dan de begroting.

    Knippen mag niet. `dispatch` maakt hier een foutresultaat van (`ondeelbare_eenheid_te_groot`);
    de tool moet zijn vorm herzien (fijner pagineren), niet de data inkorten."""

    def __init__(self, melding: str, *, omvang: int | None = None):
        super().__init__(melding)
        self.omvang = omvang


def voorproef(tekst: str, maximum: int) -> tuple[str, bool]:
    """Het begin van een tekst voor een LIJST-rij, en of het de hele tekst is.

    Een zoektreffer is een aanwijzing, geen bron om uit te citeren: de rij zegt expliciet
    `tekst_volledig: false` en de vindplaats staat erbij, zodat de volledige tekst één gerichte
    aanroep verder ligt. Afgebroken op een woordgrens."""
    if len(tekst) <= maximum:
        return tekst, True
    kort = tekst[:maximum]
    spatie = kort.rfind(" ")
    return (kort[:spatie] if spatie > maximum // 2 else kort), False


def fout(reden: str, melding: str, **velden: Any) -> str:
    """Een foutresultaat in contractvorm: liever zichtbaar geen resultaat dan stil een half."""
    return _json({"status": "error", "reden": reden, "melding": melding, **velden})


def waarden(tekst: str) -> str:
    """De inhoud van een toolresultaat zoals een controle hem moet lezen.

    Brongetrouwheid en bronnen werkten op de ruwe tooltekst. Bij een contract is dat JSON: een
    newline staat er als `\n`, een aanhalingsteken als `\"`, en een letterlijk citaat over zo'n grens
    zou als afwijking uit de bus komen. Daarom de waarden zelf, gedecodeerd, elk op een eigen regel.
    Geen contract: de tekst ongewijzigd."""
    data = is_contract(tekst)
    if data is None:
        return tekst
    uit: list[str] = []

    def loop(v: Any) -> None:
        if isinstance(v, str):
            uit.append(v)
        elif isinstance(v, dict):
            for w in v.values():
                loop(w)
        elif isinstance(v, list):
            for w in v:
                loop(w)

    loop({k: v for k, v in data.items() if k not in ("status", "volledig", "aantal", "toelichting")})
    return "\n".join(uit)


def is_contract(tekst: str) -> dict[str, Any] | None:
    """Het geparste contract, of None als de tekst er geen is."""
    try:
        data = json.loads(tekst)
    except (TypeError, ValueError):
        return None
    if isinstance(data, dict) and data.get("status") == "ok" and "volledig" in data and "resultaten" in data:
        return data
    return None


def is_foutresultaat(tekst: str) -> dict[str, Any] | None:
    try:
        data = json.loads(tekst)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("status") == "error" and "reden" in data else None
