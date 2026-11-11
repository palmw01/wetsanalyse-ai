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

_NIET_BEREIKBAAR = "niet bereikbaar"
_NIET_BESCHIKBAAR = "niet beschikbaar in deze omgeving"
_TE_GROOT = "gaf meer dan Lex in één keer kan verwerken"
_VRAAG_KLOPTE_NIET = "de zoekvraag klopte niet"

#: Wat een `reden` (of de `foutcode` van `tool_execution`) betekent, in de woorden van de jurist: het denkproces zegt
#: zo wat er ontbrak, zonder code (`spoorbronnen.uitkomstregel`). Voer je een nieuwe reden in, zet hem hier;
#: `tests/test_spoorbronnen.py` zoekt elke reden in de code op. Een onbekende reden heet "gaf een fout".
REDEN_ZIN: dict[str, str] = {
    "bron_onbereikbaar": _NIET_BEREIKBAAR, "graaf_onbereikbaar": _NIET_BEREIKBAAR,
    "annotatie_api_onbereikbaar": _NIET_BEREIKBAAR, "begrippen_api_onbereikbaar": _NIET_BEREIKBAAR,
    "annotatie_api_niet_ingesteld": _NIET_BESCHIKBAAR, "begrippen_api_niet_ingesteld": _NIET_BESCHIKBAAR,
    "annotatie_gebruikerscontext_ontbreekt": _NIET_BESCHIKBAAR,
    "begrippen_gebruikerscontext_ontbreekt": _NIET_BESCHIKBAAR,
    "connector_uit": "staat uit in dit gesprek",
    "tool_mislukt": "mislukt",
    "tool_resultaat_te_groot": _TE_GROOT, "resultaatcontract_overschreden": _TE_GROOT,
    "resultaat_te_groot": _TE_GROOT, "ondeelbare_eenheid_te_groot": _TE_GROOT,
    "ongeldige_argumenten": _VRAAG_KLOPTE_NIET, "ongeldig_id": _VRAAG_KLOPTE_NIET,
    "ongeldige_tabel": _VRAAG_KLOPTE_NIET, "ongeldig_dossier": _VRAAG_KLOPTE_NIET,
    "limit_te_hoog": _VRAAG_KLOPTE_NIET, "limit_ontbreekt": _VRAAG_KLOPTE_NIET, "alleen_select": _VRAAG_KLOPTE_NIET,
    "is_een_id": _VRAAG_KLOPTE_NIET, "eigen_waarden": _VRAAG_KLOPTE_NIET,
    "ongeldig_aantal": _VRAAG_KLOPTE_NIET, "ongeldig_nummer": _VRAAG_KLOPTE_NIET,
    "ongeldig_vergaderjaar": _VRAAG_KLOPTE_NIET, "ongeldige_datum": _VRAAG_KLOPTE_NIET,
    "ongeldige_kamer": _VRAAG_KLOPTE_NIET, "ongeldige_tekst": _VRAAG_KLOPTE_NIET,
    "ongeldige_volgorde": _VRAAG_KLOPTE_NIET,
    "zoekvraag_geweigerd": "de bron weigerde de zoekvraag",
    "niet_gevonden": "het stuk is niet gevonden",
    "alleen_pdf": "het stuk is er alleen als pdf",
    "buiten_bereik": "dit stuk valt buiten de bron",
    "onleesbaar_document": "het stuk is niet te lezen",
    "overzicht_niet_opgebouwd": "het overzicht kon niet worden opgebouwd",
    "onvolledig_antwoord": "gaf een onvolledig antwoord",
    "in_graaf": "staat in de kennisgraaf; daar gelezen",
    "niet_in_graaf": "staat niet in de kennisgraaf",
    "toestand_onvolledig": "de tekst is niet volledig te lezen",
}


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
    zonder_herhaling: Sequence[str] = (),
) -> str:
    """Een pagina van een gerangschikte lijst. De query vraagt `limit + 1` rijen op: de extra rij
    bewijst dat er meer is, zonder een tweede telquery.

    `zonder_herhaling`: velden die een rij alleen draagt als ze anders zijn dan op de rij ervoor op déze pagina (de kop
    van een alinea in een lang stuk). De eerste rij van elke pagina draagt ze altijd, dus een lezer vult ze per pagina
    aan (`stuk_tekst.aangevuld`)."""
    meer = len(rijen_plus_een) > limit
    rijen = [compact(r) for r in rijen_plus_een[:limit]]

    def maak(deel: Sequence[dict[str, Any]]) -> str:
        volledig = not meer and len(deel) == len(rijen)
        vervolg = None if volledig else {"tool": tool, "args": {**args, "offset": offset + len(deel)}}
        return resultaat(_zonder_herhaling(deel, zonder_herhaling), volledig=volledig, vervolg=vervolg,
                         toelichting=toelichting, extra=extra)

    k, tekst = passend(rijen, maak, budget)
    if rijen and k == 0:
        # Een vervolg met dezelfde offset zou een lus zijn. Eén rij groter dan de begroting is een
        # fout in de vorm van die tool (`tests/test_resultaatcontract.py` vangt hem), geen datazaak.
        raise TeGroot(f"{tool}: één rij is groter dan de begroting van {budget} tekens",
                      omvang=len(maak(rijen[:1])))
    return tekst


def _zonder_herhaling(rijen: Sequence[dict[str, Any]], velden: Sequence[str]) -> list[dict[str, Any]]:
    if not velden:
        return list(rijen)
    uit: list[dict[str, Any]] = []
    vorige: dict[str, Any] = {}
    for r in rijen:
        r = dict(r)
        for v in velden:
            if v in r and r[v] == vorige.get(v):
                del r[v]
            elif v in r:
                vorige[v] = r[v]
            else:
                vorige.pop(v, None)
        uit.append(r)
    return uit


def per_eenheid(
    eenheden: Sequence[dict[str, Any]],
    *,
    tool: str,
    args: dict[str, Any],
    offset: int,
    toelichting: str = "",
    extra: dict[str, Any] | None = None,
    budget: int = BUDGET,
    zonder_herhaling: Sequence[str] = (),
) -> str:
    """Pagineer over eenheden die al compleet zijn opgehaald (de leden van één artikel, de onderdelen
    van één lid): vanaf `offset` zoveel hele eenheden als passen, met `vervolg` naar de volgende."""
    rest = list(eenheden[offset:])
    return pagina(rest, tool=tool, args=args, limit=len(rest), offset=offset, toelichting=toelichting,
                  extra=extra, budget=budget, zonder_herhaling=zonder_herhaling)


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


def is_fout(raw: str) -> bool:
    """Is dit toolresultaat een fout? De ene toets: voor `is_error` naar het model én in de MCP-server.

    Een tool werpt niet: `dispatch` geeft een fout terug als tekst met uitleg, of als JSON met een status
    (`fout`, en `unavailable`/`invalid_request` van de leestools)."""
    if raw.startswith(("Fout bij tool", "Onbekende tool")):
        return True
    try:
        data = json.loads(raw)
    except ValueError:
        return False
    return isinstance(data, dict) and data.get("status") in {"error", "unavailable", "invalid_request"}


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


#: Het resultaatcontract als JSON Schema, voor de `outputSchema` van de MCP-server (review ADR-013). Eén schema voor
#: elke tool met het contract: een externe client kan `volledig` en `vervolg` zo valideren in plaats van tekst te lezen.
#: Bij `status: ok` zijn `volledig`, `aantal` en `resultaten` verplicht, en `vervolg` alleen als `volledig` onwaar is;
#: een fout draagt `reden`. Andere velden (`stuk`, `totaal`, `volgorde` …) mogen: die horen bij de tool.
CONTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ok", "error"]},
        "volledig": {"type": "boolean", "description": "Alles binnen de scope van déze aanroep staat erin."},
        "aantal": {"type": "integer", "minimum": 0},
        "totaal": {"type": "integer", "minimum": 0},
        "vervolg": {"type": "object", "properties": {"tool": {"type": "string"}, "args": {"type": "object"}},
                    "required": ["tool", "args"],
                    "description": "De aanroep die dezelfde set aanvult; alleen als volledig onwaar is."},
        "resultaten": {"type": "array", "items": {"type": "object"}},
        "toelichting": {"type": "string"},
        "reden": {"type": "string"},
    },
    "required": ["status"],
    "allOf": [
        {"if": {"properties": {"status": {"const": "ok"}}},
         "then": {"required": ["volledig", "aantal", "resultaten"]}},
        {"if": {"properties": {"status": {"const": "ok"}, "volledig": {"const": True}}, "required": ["volledig"]},
         "then": {"not": {"required": ["vervolg"]}}},
        {"if": {"properties": {"status": {"const": "ok"}, "volledig": {"const": False}}, "required": ["volledig"]},
         "then": {"required": ["vervolg"]}},
        {"if": {"properties": {"status": {"const": "error"}}}, "then": {"required": ["reden"]}},
    ],
}


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
