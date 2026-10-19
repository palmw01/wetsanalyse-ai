"""Begrippen lezen (spoor D, fase F4): wat juristen in een werkgebied als begrip vastlegden.

Een begrip is een **analyse-uitkomst**, geen wettelijke definitie en geen vindplaats. Daarom staan deze
tools naast de annotatie-leestools in `AFGELEIDE_TOOL_NAMEN`: hun resultaten tellen niet als bron en
niet als grounding (`provenance`, `grounding`, `bronregister`).

`search_begrippen` zoekt zoals `search_annotaties`: kandidaten uit de graaf (de NL-SBB-projectie van
fase F3, per werkgebied een named graph `urn:wa:graph:werkgebied:<id>`), daarna bevestigd door de api
(`POST /v1/begrippen/verifieer`), want Postgres is de waarheid. Wat er intussen veranderde, telt zoals
de api het zegt; loopt de projectie van een werkgebied achter (de hash in het register wijkt af van
wat de api nu zou projecteren), dan is het resultaat `volledig: false`. `get_begrip` leest altijd bij
de api: koppelingen, actualiteit en relaties staan niet allemaal in de graaf.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from ..graph.queries import _lit
from ..graph.results import parse_select
from .annotatie_tools import ANNOTATIE_TOOL_NAMEN, _d, schema, vindplaats_label

BEGRIP_TOOL_NAMEN = frozenset({"search_begrippen", "get_begrip"})
#: Tools waarvan het resultaat afgeleide duiding is: nooit een bron, nooit grounding.
AFGELEIDE_TOOL_NAMEN = ANNOTATIE_TOOL_NAMEN | BEGRIP_TOOL_NAMEN

STATUSSEN = ("concept", "geaccordeerd", "vervangen")
STATUS_VOLGORDE = {"geaccordeerd": 0, "concept": 1, "vervangen": 2}
#: Zoveel kandidaten laat de api hoogstens per keer bevestigen (`BegripVerificatie.ids`).
MAX_KANDIDATEN = 50

WA = "urn:wa-ns:"
GRAPH_PREFIX = "urn:wa:graph:werkgebied:"
REGISTER = "urn:wa:graph:register:begrippen"
_PREFIX = "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"

TOELICHTING = ("Begrippen zijn analyse-uitkomsten van juristen binnen een werkgebied, geen wettelijke "
               "definities. Noem bij elk begrip de status en het werkgebied; citeer wettekst alleen nadat "
               "je de bepaling met een brontool hebt opgehaald.")

S = {"type": "string"}

BEGRIP_TOOLS = [
    schema("search_begrippen", "Zoek begrippen die juristen in werkgebieden vastlegden (activiteit 3): "
           "op naam, alternatieve term of definitie, over alle werkgebieden, het werkgebied van het gesprek "
           "eerst. Een begrip is een analyse-uitkomst met een status (concept, geaccordeerd, vervangen), "
           "geen wettelijke definitie – daarvoor is zoek_definitie. Zonder zoekterm: alle begrippen "
           "(eventueel per status of werkgebied). Onvolledig is geen bewijs dat een begrip ontbreekt. "
           "GEEFT TERUG: status en volledig, dan per begrip id, naam, status, werkgebied, definitie (ingekort), "
           "alternatieve termen, aantal dragende passages en bij een vervangen begrip de opvolger. Gebruik "
           "get_begrip voor de passages en relaties van één begrip.",
           {"zoekterm": _d(S, "Woord of woorden uit naam, alternatieve term of definitie; leeg = alles."),
            "status": {"type": "array", "items": {"type": "string", "enum": list(STATUSSEN)}, "maxItems": 3,
                       "description": "Alleen deze statussen (meerdere = of)."},
            "werkgebied_id": _d(S, "Alleen begrippen uit dit werkgebied."),
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_KANDIDATEN}}),
    schema("get_begrip", "Lees één begrip: inhoud (definitie met herkomst, context, uitleg, voorbeelden), status, "
           "werkgebied, de passages waarop het rust (rol, beoordeling, of de passage nog actueel is, vindplaats) "
           "en de vastgelegde relaties met andere begrippen. Analyse-uitkomst; haal de wettekst apart op.",
           {"begrip_id": _d(S, "Het id van een begrip, uit search_begrippen.")}, ("begrip_id",)),
]


# Een leesvraag over begrippen noemt wat er al ligt: "welke begrippen hebben we al geaccordeerd?",
# "staat termijn als begrip in het werkgebied?". Zonder zo'n aanwijzing is "welke begrippen zitten
# hierin?" een vraag om voorstellen (`begrippen_beurt.is_begrippenvraag`), en "wat betekent het begrip
# X?" een definitievraag over de wet (de definitie-specialist, die deze tools ook heeft).
_BEGRIP = re.compile(r"\b(begrip|begrippen|begripskaart|begripskaarten)\b")
_AL_VASTGELEGD = re.compile(r"\b(al|reeds|vastgelegd\w*|geaccordeerd\w*|bestaande?|opgeslagen|status|concept\w*"
                            r"|vervangen|hebben we|kennen we|staan er|staat er|zijn er|ons|onze|overzicht|lijst"
                            r"|als begrip|begripskaart\w*)\b")
_BEGRIP_SCHRIJVEN = re.compile(r"\b(stel|voorstel\w*|maak|maken|formuleer\w*|herken|bepaal|accordeer\w*|koppel\w*"
                               r"|wijzig\w*|verwijder\w*|denk|annoteer\w*|scherper|aanscherp\w*|voorbeeld\w*"
                               r"|brondefinitie)\b")


def is_begrip_leesvraag(vraag: str) -> bool:
    q = (vraag or "").casefold()
    return bool(_BEGRIP.search(q) and _AL_VASTGELEGD.search(q) and not _BEGRIP_SCHRIJVEN.search(q))


def normaal(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst or "")
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).casefold().split())


def _woorden(zoekterm: str) -> list[str]:
    return [w for w in (zoekterm or "").casefold().split() if w][:8]


def q_begrippen(zoekterm: str, statussen: list[str], werkgebied_id: str, limit: int) -> str:
    """Kandidaten uit de projectie. Alleen id's en werkgebied: wat telt, zegt de api daarna."""
    tekst = ""
    if woorden := _woorden(zoekterm):
        bevat = " && ".join(f"CONTAINS(LCASE(STR(?t)), {_lit(w)})" for w in woorden)
        tekst = ("{ ?c skos:prefLabel ?t } UNION { ?c skos:altLabel ?t } UNION { ?c skos:definition ?t }\n"
                 f"    FILTER({bevat})")
    filters = [f"STRSTARTS(STR(?g), {_lit(GRAPH_PREFIX)})"]
    if statussen:
        filters.append(f"?status IN ({', '.join(_lit(s) for s in statussen)})")
    if werkgebied_id:
        filters.append(f"?wid = {_lit(werkgebied_id)}")
    return _PREFIX + f"""SELECT DISTINCT ?c ?wid WHERE {{
  GRAPH ?g {{
    ?c a skos:Concept ; skos:inScheme ?k ; <{WA}status> ?status .
    ?k <{WA}werkgebiedId> ?wid .
    {tekst}
  }}
  FILTER({' && '.join(filters)})
}} LIMIT {limit + 1}"""


Q_REGISTER = f"""SELECT ?wid ?hash WHERE {{ GRAPH <{REGISTER}> {{
  ?k <{WA}werkgebiedId> ?wid ; <{WA}projectieHash> ?hash }} }} LIMIT 500"""


def treffer(zoekterm: str, rij: dict[str, Any]) -> int:
    """Dezelfde rangorde als de api (`begrippen_overzicht.treffer`), lager is beter."""
    q = normaal(zoekterm)
    if not q:
        return 0
    naam, termen = normaal(rij.get("naam", "")), [normaal(t) for t in rij.get("alternatieve_termen") or []]
    if naam == q:
        return 0
    if q in termen:
        return 1
    if q in naam:
        return 2
    if any(q in t for t in termen):
        return 3
    return 4


def _kort(tekst: str, n: int = 400) -> str:
    tekst = " ".join((tekst or "").split())
    return tekst if len(tekst) <= n else tekst[:n] + "…"


def _rij(r: dict[str, Any]) -> dict[str, Any]:
    uit = {"id": r["id"], "naam": r.get("naam", ""), "status": r.get("status", ""),
           "werkgebied": r.get("werkgebied_naam", ""), "werkgebied_id": r.get("werkgebied_id", "")}
    if r.get("definitie"):
        uit["definitie"] = _kort(r["definitie"])
        uit["definitie_herkomst"] = r.get("definitie_herkomst") or ""
    if r.get("alternatieve_termen"):
        uit["alternatieve_termen"] = r["alternatieve_termen"]
    uit["aantal_dragend"] = r.get("aantal_dragend", 0)
    if r.get("vervangen_door"):
        uit["vervangen_door"] = r["vervangen_door"]
    return uit


def zoek(args: dict[str, Any], graph, port) -> dict[str, Any]:
    zoekterm, statussen = str(args.get("zoekterm") or ""), list(args.get("status") or [])
    wg, limit = str(args.get("werkgebied_id") or ""), int(args.get("limit") or 25)
    eerst = getattr(port, "werkgebied_id", "") or ""
    try:
        kandidaten = parse_select(graph.sparql(q_begrippen(zoekterm, statussen, wg, MAX_KANDIDATEN)))
        register = {r["wid"]: r["hash"] for r in parse_select(graph.sparql(Q_REGISTER))}
    except Exception:  # noqa: BLE001 – een haperende graaf is een onvolledig antwoord, geen leeg
        return {"status": "unavailable", "volledig": False, "reden": "graaf_onbereikbaar"}
    te_veel = len(kandidaten) > MAX_KANDIDATEN
    ids = list(dict.fromkeys(str(r["c"]).removeprefix("urn:wa:begrip:") for r in kandidaten))[:MAX_KANDIDATEN]
    werkgebieden = sorted(set(register) | ({eerst} if eerst else set()))[:MAX_KANDIDATEN]
    bevestigd = port.verifieer(ids, werkgebieden)
    if bevestigd.get("status") != "ok":
        return {k: bevestigd[k] for k in ("status", "volledig", "reden", "detail") if k in bevestigd}
    # De api is de waarheid: wat er niet meer is valt af, en status en werkgebied gelden zoals ze nu zijn.
    rijen = [r for r in (bevestigd.get("begrippen") or {}).values() if isinstance(r, dict)
             and (not statussen or r.get("status") in statussen) and (not wg or r.get("werkgebied_id") == wg)]
    rijen.sort(key=lambda r: (treffer(zoekterm, r), bool(eerst) and r.get("werkgebied_id") != eerst,
                              STATUS_VOLGORDE.get(r.get("status", ""), 9), normaal(r.get("naam", "")), r["id"]))
    achter = sorted(wid for wid, v in (bevestigd.get("werkgebieden") or {}).items()
                    if (v or {}).get("projectie_hash") and v["projectie_hash"] != register.get(wid))
    volledig = not te_veel and not achter and len(rijen) <= limit
    uit: dict[str, Any] = {"status": "ok" if not achter else "partial", "volledig": volledig,
                           "aantal": min(len(rijen), limit), "resultaten": [_rij(r) for r in rijen[:limit]],
                           "toelichting": TOELICHTING}
    if achter:
        uit["achterstand"] = ("De graaf liep voor een of meer werkgebieden achter op de laatste wijzigingen; "
                              "recente begrippen kunnen ontbreken.")
    if eerst:
        uit["werkgebied_gesprek"] = eerst
    return uit


def _koppeling(k: dict[str, Any]) -> dict[str, Any]:
    b = k.get("bewijs") or {}
    uit = {"rol": k.get("rol", ""), "beoordeling": k.get("beoordeling", ""), "actualiteit": k.get("actualiteit", ""),
           "tekst": _kort(b.get("tekst", ""), 300), "klasse": b.get("klasse", "")}
    iri = b.get("eigenaar_iri") or ""
    if iri:
        uit["bron_iri"] = iri
        uit["vindplaats"] = b.get("vindplaats") or vindplaats_label(iri)
    return uit


def compact_begrip(result: dict[str, Any]) -> dict[str, Any]:
    b, wg = result.get("begrip") or {}, result.get("werkgebied") or {}
    i = b.get("inhoud") or {}
    velden = ("naam", "alternatieve_termen", "begripstype", "definitie", "definitie_herkomst", "definitie_door",
              "context", "uitleg", "geldigheid", "jas_klasse")
    uit: dict[str, Any] = {"status": "ok", "volledig": True, "id": b.get("id", ""), "begrip_status": b.get("status", ""),
                           "revisie": b.get("revisie"), "werkgebied": wg.get("naam", ""), "werkgebied_id": wg.get("id", ""),
                           **{k: i[k] for k in velden if i.get(k)}}
    if i.get("voorbeelden"):
        uit["voorbeelden"] = [{"tekst": _kort(v.get("tekst", ""), 300), "oordeel": v.get("oordeel", "")}
                              for v in i["voorbeelden"][:10]]
    if b.get("geaccordeerd_op"):
        uit["geaccordeerd_op"] = b["geaccordeerd_op"]
    if b.get("aandachtspunten"):
        uit["aandachtspunten"] = b["aandachtspunten"]
    for k in ("vervangen_door", "vervangt"):
        if b.get(k):
            uit[k] = b[k]
    uit["passages"] = [_koppeling(k) for k in (b.get("koppelingen") or [])[:30]]
    uit["relaties"] = [{"type": r.get("type", ""), "van": r.get("van_naam", ""), "naar": r.get("naar_naam", ""),
                        **({"toelichting": r["toelichting"]} if r.get("toelichting") else {})}
                       for r in (result.get("relaties") or [])[:30]]
    uit["toelichting"] = TOELICHTING
    return uit


def dispatch_begrip(name: str, args: dict[str, Any], graph, port) -> str:
    definition = next(t for t in BEGRIP_TOOLS if t["name"] == name)["input_schema"]
    if set(args) - set(definition["properties"]) or any(k not in args for k in definition["required"]):
        raise ValueError("Ongeldige argumenten voor begrippentool")
    for key, value in args.items():
        if key == "limit":
            if type(value) is not int or not 1 <= value <= MAX_KANDIDATEN:
                raise ValueError("Ongeldige limit")
        elif key == "status":
            if not isinstance(value, list) or len(value) > 3 or set(value) - set(STATUSSEN):
                raise ValueError("Onbekende status")
        elif not isinstance(value, str) or len(value) > 200:
            raise ValueError(f"Ongeldige waarde voor {key}")
    if port is None:
        result: dict[str, Any] = {"status": "unavailable", "volledig": False, "reden": "begrippen_api_niet_ingesteld"}
    elif name == "search_begrippen":
        result = zoek(args, graph, port)
    else:
        antwoord = port.begrip(args["begrip_id"])
        result = compact_begrip(antwoord) if antwoord.get("status") == "ok" else antwoord
    return json.dumps({"bewijssoort": "begrip", **result}, ensure_ascii=False)


def begrens_begrippen_antwoord(answer: str, trace) -> str:
    """Een zoekstoring mag nooit "er zijn geen begrippen" worden (de tweeling van `begrens_antwoord`)."""
    antwoorden = []
    for name, text in trace:
        if name in BEGRIP_TOOL_NAMEN:
            try:
                value = json.loads(text)
                antwoorden.append(value if isinstance(value, dict) else {"status": "unavailable"})
            except ValueError:
                antwoorden.append({"status": "unavailable"})
    if not antwoorden:
        return ("Er is bij deze beurt niet in de vastgelegde begrippen gezocht, dus dit is geen uitspraak over "
                "welke begrippen er zijn. Stel de vraag opnieuw.")
    if not any(r.get("status") in {"ok", "partial"} for r in antwoorden):
        return "De vastgelegde begrippen zijn nu niet betrouwbaar te raadplegen. Dit betekent niet dat er geen begrippen zijn."
    if any(r.get("status") != "ok" or r.get("volledig") is False for r in antwoorden):
        return answer + "\n\nDeze zoekuitkomst is onvolledig; ontbrekende begrippen zijn niet uitgesloten."
    return answer
