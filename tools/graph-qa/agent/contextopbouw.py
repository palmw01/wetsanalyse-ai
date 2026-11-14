"""De contextopbouw van een beurt: per agent de context, en het verbruik van de hele beurt (plan contextweergave).

Twee dingen die niet hetzelfde getal zijn:

- **context**: hoe het verzoek van een agent met een toollus was opgebouwd. Het laatste verzoek van de lus is het volste
  (de lopende beurt krimpt nooit, ADR-015) en is dus de context; het eerste zegt of de beurt warm of koud begon;
- **verbruik**: wat alle modelaanroepen van de beurt samen kostten, per rol, ook de losse stappen.

Alles komt uit de `Verbruiksmeter` aan het eind van de beurt, zonder extra modelaanroep. Hetzelfde verzoek met dezelfde
`usage` geeft altijd dezelfde verdeling, ook op een andere replica.

**Telwijze** (`verdeel`):

- het totaal is exact: `invoer + cache_lees + cache_schrijf` uit `usage`;
- het voorvoegsel (tools + systeem) is exact zodra een verzoek van de lus het schreef: het cachepunt op de systeemprompt
  houdt een uur, de punten op de berichten 5 minuten, dus `usage.cache_creation.ephemeral_1h_input_tokens` is dan
  precies de omvang van tools + systeem (het **anker**). Het geldt voor elk verzoek van die rol met dezelfde
  `tools_hash` en `system_hash`. Zonder schrijfbeurt in deze beurt (een warm begin) is er geen anker;
- de rest gaat naar tekens (`verzoekopbouw.samenstelling`), afgerond met de grootste-rest-methode: de som van de delen
  is precies het totaal.

Geen veld heet `token`: de logredactie (`observability.GEHEIME_VELDEN`) laat een veld met die naam weg. Het contract
bij de api is `gesprek_contracts.Contextopbouw`; `tests/test_contextopbouw.py` vergelijkt beide kanten.
"""
from __future__ import annotations

from typing import Any

from .contextdelen import HISTORIE, IDS, OVERIG, VOORVOEGSEL
from .modelvenster import modelvenster

VERSIE = 1

#: De rol van een aanroep die niet langs de gedeelde modelstap kwam. Hoort niet voor te komen
#: (`tests/test_methoderollen.py`), maar het verbruik telt dan nog steeds mee.
ONBEKEND = "onbekend"


def grootste_rest(gewichten: dict[str, int], totaal: int) -> dict[str, int]:
    """Verdeel `totaal` over de sleutels naar gewicht, in hele getallen, zodat de som precies `totaal` is. Bij gelijke
    rest wint de volgorde van de sleutels: dezelfde invoer geeft altijd dezelfde uitkomst."""
    som = sum(gewichten.values())
    if totaal <= 0 or som <= 0:
        return {k: 0 for k in gewichten}
    uit = {k: totaal * g // som for k, g in gewichten.items()}
    resten = sorted(gewichten, key=lambda k: -(totaal * gewichten[k] % som))  # stabiel: gelijke rest in volgorde
    for k in resten[: totaal - sum(uit.values())]:
        uit[k] += 1
    return uit


def totaal_van(aanroep: dict[str, Any]) -> int:
    """Het promptvolume van één verzoek: alles wat het model las, uit de cache of niet. Uitvoer telt niet mee."""
    return int(aanroep.get("invoer", 0)) + int(aanroep.get("cache_lees", 0)) + int(aanroep.get("cache_schrijf", 0))


def verdeel(aanroep: dict[str, Any], anker: int | None = None) -> dict[str, Any]:
    """De delen van één verzoek: per categorie de omvang, met het totaal en het voorvoegsel.

    `anker` is de exacte omvang van tools + systeem, als een verzoek met dit voorvoegsel het in deze beurt schreef.
    Past het anker niet (groter dan het totaal, of geen tekens in het voorvoegsel), dan telt het niet."""
    totaal = totaal_van(aanroep)
    tekens = {c: int(n) for c, n in (aanroep.get("samenstelling") or {}).items() if c in IDS and int(n) > 0}
    if not tekens:
        tekens = {OVERIG: 1}  # niet in te delen: alles is `overig`, en de som klopt nog
    voor = {c: n for c, n in tekens.items() if c in VOORVOEGSEL}
    rest = {c: n for c, n in tekens.items() if c not in VOORVOEGSEL}
    exact = bool(anker and voor and 0 < anker <= totaal)
    if exact:
        na = totaal - int(anker or 0)
        if na and not rest:
            rest = {OVERIG: 1}  # de API telde meer dan Lex na het cachepunt stuurde
        omvang = {**grootste_rest(voor, int(anker or 0)), **grootste_rest(rest, na)}
    else:
        omvang = grootste_rest(tekens, totaal)
    return {
        "delen": [{"categorie": c, "omvang": omvang[c]} for c in IDS if c in omvang],
        "totaal": totaal,
        "voorvoegsel": {"omvang": sum(n for c, n in omvang.items() if c in VOORVOEGSEL), "exact": exact},
        "cache": _cache(aanroep),
    }


def _cache(aanroep: dict[str, Any]) -> dict[str, int]:
    return {"lees": int(aanroep.get("cache_lees", 0)), "schrijf": int(aanroep.get("cache_schrijf", 0)),
            "nieuw": int(aanroep.get("invoer", 0))}


def _sleutel(aanroep: dict[str, Any]) -> tuple[str, str]:
    return str(aanroep.get("tools_hash", "")), str(aanroep.get("system_hash", ""))


def _historiegrens(laatste: dict[str, Any], delen: dict[str, Any], grens_tekens: int) -> int | None:
    """`MAX_HISTORY_CHARS` in de eenheid van de delen. De grens telt in tekens van de berichten (`_msg_lengte`), dus de
    omrekening gebruikt de historie van dit verzoek zelf; zonder historie de verhouding van het hele verzoek."""
    if grens_tekens <= 0:
        return None
    historie = next((d["omvang"] for d in delen["delen"] if d["categorie"] == HISTORIE), 0)
    tekens = int(laatste.get("historie_tekens", 0))
    if historie > 0 and tekens > 0:
        return round(grens_tekens * historie / tekens)
    alles = sum(int(n) for n in (laatste.get("samenstelling") or {}).values())
    return round(grens_tekens * delen["totaal"] / alles) if alles > 0 and delen["totaal"] > 0 else None


def _venster_beurten(telling: dict[str, Any]) -> dict[str, int] | None:
    """Uit `berichten.venster_telling`: de beurten die in het venster staan (met de lopende), de toolresultaten die
    ingekort of weggelaten zijn, en de beurten die er niet meer in staan."""
    if not telling:
        return None
    in_venster = int(telling.get("beurten_venster", 0))
    return {"in_venster": in_venster, "gekrompen": int(telling.get("ingekort", 0)),
            "weggevallen": max(0, int(telling.get("beurten_historie", 0)) - in_venster)}


def _agent(rol: str, lus: dict[str, Any]) -> dict[str, Any]:
    begin, laatste, kader = lus["begin"], lus["laatste"], lus.get("kader") or {}
    delen = verdeel(laatste, (lus.get("ankers") or {}).get(_sleutel(laatste)))
    model = str(laatste.get("model", ""))
    return {
        "rol": rol,
        "model": model,
        "venster": modelvenster(model),
        "laatste": delen,
        "begin": {"totaal": totaal_van(begin), "cache": _cache(begin),
                  "tools_hash": _sleutel(begin)[0], "system_hash": _sleutel(begin)[1]},
        "historiegrens": _historiegrens(laatste, delen, int(kader.get("historiegrens_tekens") or 0)),
        "venster_beurten": _venster_beurten(kader.get("venster_telling") or {}),
        # Het profiel waarmee deze agent draaide (ADR-016 §A3): de agentvorm zet het in het kader van elke ronde.
        "profiel_id": str(kader.get("profiel_id") or ""),
        "profiel_versie": str(kader.get("profiel_versie") or ""),
    }


def _regel(aanroep: dict[str, Any]) -> dict[str, Any]:
    """Eén modelaanroep in het detail: tellingen en vingerafdrukken."""
    return {"rol": aanroep.get("rol") or ONBEKEND, "totaal": totaal_van(aanroep),
            "cache_lees": int(aanroep.get("cache_lees", 0)), "cache_schrijf": int(aanroep.get("cache_schrijf", 0)),
            "invoer": int(aanroep.get("invoer", 0)), "uitvoer": int(aanroep.get("uitvoer", 0)),
            "ms": int(aanroep.get("ms", 0)), "tools_hash": _sleutel(aanroep)[0], "system_hash": _sleutel(aanroep)[1],
            # Het profiel van de agent die aanriep (ADR-016 §A3); een losse stap heeft er geen en draagt het veld niet.
            **{veld: str(aanroep[veld]) for veld in ("profiel_id", "profiel_versie") if aanroep.get(veld)},
            # Een aanroep die mislukte en niets kostte (de lichte modelklasse die de omgeving niet heeft, ADR-016 §A2):
            # het model en de reden. Alleen dan, zodat een gewone regel gelijk blijft.
            **({"mislukt": str(aanroep["mislukt"]), "model": str(aanroep.get("model") or ""),
                **({"http_status": int(aanroep["http_status"])} if aanroep.get("http_status") is not None else {})}
               if aanroep.get("mislukt") else {})}


def contextopbouw(meter: Any, *, run_id: str = "", ouder_run_id: str = "", profiel_id: str = "",
                  profiel_versie: str = "") -> dict[str, Any] | None:
    """De contextopbouw van de beurt die `meter` telde, of `None` als de beurt geen model gebruikte.

    `agenten` heeft een rij per rol met een toollus; een beurt met alleen losse stappen heeft verbruik, maar geen
    context. `laatste`, `begin` en de sommen komen uit alle aanroepen, ook voorbij `MAX_AANROEPEN`; alleen de lijst
    `aanroepen` is begrensd. `som` is wat dezelfde meter aan `/v1/verbruik` meldt."""
    if meter is None:
        return None
    stand = meter.stand()
    if not stand["calls"]:
        return None
    return {
        "versie": VERSIE,
        "run_id": run_id or "",
        "ouder_run_id": ouder_run_id or "",
        "profiel_id": profiel_id or "",
        "profiel_versie": profiel_versie or "",
        "agenten": [_agent(rol, lus) for rol, lus in stand["lussen"].items()],
        "verbruik": [{"rol": rol, **v} for rol, v in stand["per_rol"].items()],
        "som": {k: stand[k] for k in ("invoer", "cache_lees", "cache_schrijf", "uitvoer")},
        "aanroepen": [_regel(a) for a in stand["aanroepen"]],
    }
