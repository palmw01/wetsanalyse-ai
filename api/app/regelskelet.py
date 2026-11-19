"""Het regelskelet van een afleidingsregel: haar opbouw uit de relaties van ADR-011 (deelactiviteit 2c, de grondstof
voor 3b). Eén berekening voor het rapport (`werkgebied_export`), de compacte weergave (`GET weergave?vorm=skelet`) en
wat er later op bouwt. Wie het skelet anders uitrekent, krijgt twee antwoorden op één vraag.

`opbouw` kent alleen de relaties zoals `annotatie_v2_relaties.beschrijf` ze geeft; hoe een eindpunt getoond wordt,
beslist de aanroeper met `deel`. `gaten` zegt in woorden wat ontbreekt, met de regels van de catalogus en de methode
(`references/afleidingsregels.md`): precies één uitvoer, invoer met volgorde, en een rechtsobject is geen waarde.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, TypeVar

T = TypeVar("T")

#: Een deel van het skelet maken: (relatie, kant van het eindpunt, inkomend) → wat de aanroeper toont.
Deel = Callable[[dict, str, bool], T]

PARAMETER = "Parameter en parameterwaarde"
WAARDEN = frozenset({"Variabele en variabelewaarde", PARAMETER, "Tijdsaanduiding"})


def _is(ep: dict, id_: str) -> bool:
    return ep["soort"] == "element" and ep["id"] == id_


def _op_volgorde(lijst: list[dict]) -> list[dict]:
    return sorted(lijst, key=lambda r: (r.get("volgorde") is None, r.get("volgorde") or 0, r["id"]))


def opbouw(regel_id: str, relaties: Iterable[dict], deel: Deel) -> dict[str, Any]:
    """Uitvoer, invoer op volgorde, operatoren met hun operanden, voorwaarden, parameters met hun waarde, tijd,
    uitzonderingen en toepassing. `relaties` zijn de geldende: de aanroeper kiest of afgewezen relaties meetellen."""
    relaties = list(relaties)

    def van_type(code: str) -> list[dict]:
        return [r for r in relaties if r["type"] == code]
    invoer = _op_volgorde([r for r in van_type("invoer") if _is(r["naar"], regel_id)])
    operatoren = [r for r in van_type("operator_in") if _is(r["naar"], regel_id) and r["van"]["soort"] == "element"]
    operanden = {o["van"]["id"]: _op_volgorde([r for r in van_type("operand") if _is(r["naar"], o["van"]["id"])])
                 for o in operatoren}
    parameters: dict[str, dict] = {}
    for r in [*invoer, *(x for o in operatoren for x in operanden[o["van"]["id"]])]:
        if r["van"]["soort"] == "element" and r["van"].get("klasse") == PARAMETER:
            parameters.setdefault(r["van"]["id"], r)

    def beide(code: str) -> list:
        return [deel(r, "naar", False) if _is(r["van"], regel_id) else deel(r, "van", True)
                for r in van_type(code) if _is(r["van"], regel_id) or _is(r["naar"], regel_id)]
    return {
        "uitvoer": [deel(r, "naar", False) for r in van_type("uitvoer") if _is(r["van"], regel_id)],
        "invoer": [deel(r, "van", False) for r in invoer],
        "operatoren": [{"operator": deel(o, "van", False),
                        "operanden": [deel(r, "van", False) for r in operanden[o["van"]["id"]]]} for o in operatoren],
        "voorwaarden": [deel(r, "naar", False) for r in van_type("voorwaarde") if _is(r["van"], regel_id)],
        "parameters": [{"parameter": deel(r, "van", False),
                        "waarden": [deel(w, "van", False) for w in van_type("waarde") if _is(w["naar"], pid)]}
                       for pid, r in parameters.items()],
        "tijd": [deel(r, "naar", False) for r in van_type("tijd") if _is(r["van"], regel_id)],
        "uitzonderingen": beide("uitzondering_op"),
        "toepassing": beide("toepassing"),
    }


def gaten(regel_id: str, relaties: Iterable[dict]) -> list[str]:
    """Wat het skelet mist, in woorden, voor de jurist en de agent. Geen oordeel over de inhoud: alleen de vorm."""
    relaties = list(relaties)
    uitvoer = [r for r in relaties if r["type"] == "uitvoer" and _is(r["van"], regel_id)]
    invoer = [r for r in relaties if r["type"] == "invoer" and _is(r["naar"], regel_id)]
    uit = []
    if not uitvoer:
        uit.append("Er is geen uitvoer: welk begrip leidt deze regel af?")
    elif len(uitvoer) > 1:
        uit.append(f"Er zijn {len(uitvoer)} uitvoeren; een afleidingsregel heeft er precies één.")
    if not invoer:
        uit.append("Er is geen invoer.")
    zonder = [r for r in invoer if r.get("volgorde") is None]
    if len(invoer) > 1 and zonder:
        uit.append(f"{len(zonder)} van de {len(invoer)} invoeren hebben geen volgorde.")
    objecten = [r for r in invoer if r["van"].get("klasse") == "Rechtsobject"]
    if objecten and not any(r["van"].get("klasse") in WAARDEN for r in invoer):
        uit.append("De invoer is alleen een rechtsobject; een regel rekent met een waarde ervan (een variabele, "
                   "parameter of tijdsaanduiding, met een relatie kenmerk naar het object).")
    return uit


#: Zoveel tekens van een eindpunt in de skeletweergave; de hele tekst staat in de gewone weergave.
TEKST = 120
ONGELDIG = frozenset({"rejected", "vervangen"})


def _kort(r: dict, kant: str, inkomend: bool) -> dict:
    ep = r[kant]
    tekst = ep.get("tekst") or ""
    return {"relatie_id": r["id"], "soort": ep["soort"], "id": ep["id"], "klasse": ep.get("klasse") or "",
            "tekst": tekst if len(tekst) <= TEKST else tekst[:TEKST - 1] + "…",
            **({"volgorde": r["volgorde"]} if r.get("volgorde") is not None else {}),
            **({"inkomend": True} if inkomend else {}), "lifecycle": r["lifecycle"]}


def weergave(view: dict) -> dict:
    """`GET weergave?vorm=skelet`: per afleidingsregel van de bepaling haar skelet en wat het mist, zonder segmenten,
    bewijs of de andere elementen. Afgewezen en vervangen relaties tellen niet mee. Voor wie een regel opstelt of
    beoordeelt (een agent, de acceptatie-MCP); de volledige stand staat in de gewone weergave."""
    relaties = [r for r in view.get("relaties") or [] if r.get("lifecycle") not in ONGELDIG]
    regels = []
    for e in view["elementen"]:
        if e.get("klasse") != "Afleidingsregel" or e.get("lifecycle") == "rejected":
            continue
        regels.append({"id": e["id"], "laag_id": e.get("laag_id"), "tekst": e.get("tekst", ""),
                       "lifecycle": e.get("lifecycle"), **opbouw(e["id"], relaties, _kort),
                       "gaten": gaten(e["id"], relaties)})
    return {"schema_versie": view["schema_versie"], "vorm": "skelet", "doel": view["doel"],
            "snapshot_id": view["snapshot_id"],
            "lagen": [{k: laag[k] for k in ("id", "bron_iri", "revisie", "status") if k in laag} for laag in view["lagen"]],
            "regels": regels}
