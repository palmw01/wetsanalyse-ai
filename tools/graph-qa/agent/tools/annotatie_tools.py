"""Getypeerde leesoperaties: geen schrijfbevoegdheid en geen wetgevingsfallback."""
from __future__ import annotations

import json
import re
from typing import Any

ANNOTATIE_TOOL_NAMEN = frozenset({"search_annotaties", "get_annotatie", "get_annotatiedekking"})


def begrens_antwoord(answer: str, trace) -> str:
    """Een zoekstoring mag in een modelantwoord nooit 'er bestaan geen annotaties' worden."""
    responses = []
    for name, text in trace:
        if name in ANNOTATIE_TOOL_NAMEN:
            try:
                value = json.loads(text)
                responses.append(value if isinstance(value, dict) else {"status": "unavailable"})
            except ValueError:
                responses.append({"status": "unavailable"})
    if not responses:
        # Hoort in de leesroute niet meer voor te komen: die zoekt zelf vóór de eerste LLM-call
        # (`nodes/annotatie_lezen.py`). Blijft staan als vangnet, met een tekst die zegt wat er
        # werkelijk aan de hand is in plaats van te suggereren dat het zoeken mislukte.
        return ("Er is bij deze beurt niet in de opgeslagen annotaties gezocht, dus dit is geen "
                "uitspraak over wat er wel of niet is vastgelegd. Stel de vraag opnieuw.")
    if all(r.get("status") == "invalid_request" for r in responses):
        return "De annotatiezoekvraag is niet uitgevoerd: controleer de filters of begin opnieuw als de zoekresultaten zijn gewijzigd."
    if not any(r.get("status") in {"ok", "partial"} for r in responses):
        return "De opgeslagen annotaties zijn nu niet betrouwbaar te raadplegen. Dit betekent niet dat er geen annotaties zijn."
    if any(r.get("status") != "ok" or r.get("volledig") is False for r in responses):
        return answer + "\n\nDeze zoekuitkomst is onvolledig; ontbrekende treffers zijn niet uitgesloten."
    return answer


def is_leesvraag(question: str, modus: str = "auto") -> bool:
    if modus == "annotaties_lezen":
        return True
    if modus == "advies":
        # Een vraag bij één aangewezen markering ("Welke klasse past het best bij dit fragment?")
        # gaat over dát element en hoort bij de duiding-specialist. Als leesvraag gelezen kwam hij
        # in de leesroute, die de adviescontext niet kent en de tools beperkt.
        return False
    q = question.casefold()
    # Een leesvraag mag niet door een modelrouter in een schrijfactie veranderen.
    # Let op de groepering: `markeringen?` maakt alleen de slot-n optioneel en matcht dus
    # "markeringe", nooit het enkelvoud "markering". Verkeerd gegroepeerd gaat "welke markering is
    # een Rechtssubject?" langs de zoektool heen.
    onderwerp = re.search(r"\b(annotatie(s)?|markering(en)?|element(en)?|klasse(n)?|jas-klasse(n)?"
                          r"|gemarkeerd|geannoteerd|geclassificeerd|annotatiedekking)\b", q)
    lezen = re.search(r"\b(zoek|vind|toon|bekijk|laat|zien|welke?|wat|waar|hoe|hoeveel|bestaande|opgeslagen|al|dekking)\b", q)
    # `markeer`/`classificeer` horen hier ook: "markeer de JAS-elementen in artikel 9" is een opdracht
    # om te annoteren, geen vraag naar wat er al staat.
    schrijven = re.search(r"\b(annoteer|annoteren|herannoteer|markeer|markeren|classificeer|classificeren"
                          r"|maak|maken|voeg|toevoegen|wijzig|wijzigen|verwijder|verwijderen|corrigeer|corrigeren)\b", q)
    return bool(onderwerp and lezen and not schrijven)


def schema(name, description, properties, required=()):
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": properties,
                             "required": list(required), "additionalProperties": False}}


S = {"type": "string"}
SS = {"type": "array", "items": S, "maxItems": 30}


def keuzes(*waarden: str) -> dict:
    return {"type": "array", "items": {"type": "string", "enum": list(waarden)}, "maxItems": 30}
ANNOTATIE_TOOLS = [
    schema("search_annotaties", "Zoek opgeslagen JAS-annotaties, niet de wettekst. Filters zijn "
           "letterlijk en worden gecombineerd. Onvolledig/onbeschikbaar is geen bewijs dat er "
           "geen annotaties bestaan. Geen semantische fallback. Resultaten zijn afgeleide duiding. "
           "Herkomstfilters: `herkomst` (agent = voorstel van Lex, mens = door een jurist gemarkeerd), "
           "`aandacht` (geel = keuze voor de jurist, groen = bevestigd door review), `subtype`, "
           "`beslist_door` (regel/model/specificiteit/terugval) en `met_twijfel`.",
           {"bron_iri": S, "bwb_id": S, "klasse": S, "jas_klassen": SS, "tekst": S,
            "lifecycle": SS, "laagstatus": SS, "bronversie": S,
            "tekstveld": {"type": "string", "enum": ["citaat", "toelichting", "beide"]},
            "match": {"type": "string", "enum": ["exact", "bevat"]},
            "scope": {"type": "string", "enum": ["node", "subtree"]},
            "inclusief_verouderd": {"type": "boolean"}, "cursor": S,
            "herkomst": keuzes("agent", "mens"), "aandacht": keuzes("groen", "geel"),
            "subtype": keuzes("variabele", "variabelewaarde", "parameter", "parameterwaarde",
                              "delegatiebevoegdheid", "delegatie-invulling"),
            "beslist_door": keuzes("regel", "model", "specificiteit", "terugval"),
            "met_twijfel": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0}}),
    schema("get_annotatie", "Lees één opgeslagen annotatie inclusief eigenaar, alle lokale "
           "ankers en beoordeling. Dit is duiding; haal de bron apart op voor juridische claims.",
           {"id": S}, ("id",)),
    schema("get_annotatiedekking", "Controleer of een bronnode/subtree daadwerkelijk geannoteerd "
           "is; aanwezigheid van enkele elementen bewijst geen volledige dekking.",
           {"bron_iri": S, "bwb_id": S, "artikel": S, "lid": S}),
]


def _normaliseer_klassen(args: dict[str, Any]) -> dict[str, Any]:
    """Klassenamen naar hun canonieke spelling ("rechtssubjecten" → "Rechtssubject").

    De api filtert exact en geeft op een onbekende naam een 422. Het model schrijft klassen zoals
    juristen ze zeggen; dat mag geen fout worden die het met een andere zoekpoging moet raden.
    Een naam die nergens op lijkt blijft staan: die hoort de api wél te weigeren."""
    from ..jas_klassen import klassen_in_tekst

    def canoniek(naam: Any) -> Any:
        if not isinstance(naam, str):
            return naam
        gevonden = klassen_in_tekst(naam)
        return gevonden[0] if len(gevonden) == 1 else naam

    uit = dict(args)
    if isinstance(uit.get("jas_klassen"), list):
        uit["jas_klassen"] = [canoniek(k) for k in uit["jas_klassen"]]
    if "klasse" in uit:
        uit["klasse"] = canoniek(uit["klasse"])
    return uit


def vindplaats_label(iri: str) -> str:
    """"urn:bwb:BWBR0004770:artikel:9:lid:1" → "BWBR0004770 art. 9 lid 1".

    Leesbaar voor het model en de jurist; de IRI zelf blijft ernaast staan."""
    if not iri.startswith("urn:bwb:"):
        return iri
    delen = iri[len("urn:bwb:"):].split(":")
    woorden = {"artikel": "art.", "lid": "lid", "onderdeel": "onderdeel", "bepaling": "bepaling"}
    uit = [delen[0]]
    for i in range(1, len(delen) - 1, 2):
        uit.append(f"{woorden.get(delen[i], delen[i])} {delen[i + 1]}")
    return " ".join(uit)


# Wat het model van een gevonden element ziet. Niet het hele record: elk element droeg de volledige
# `geproduceerd_door` (de run van zijn batch, mét `instellingen.meting`) mee, en 25 treffers werden zo
# tientallen tot honderden kB. Dat duwde het resultaat door het historievenster heen en verdrong de
# rest van het gesprek. Wat een jurist vraagt – welke klasse, welke tekst, waar, hoe zeker, waarom –
# staat hier; het volledige record blijft via `get_annotatie` op te vragen.
_ZOEKVELDEN = ("id", "klasse", "tekst", "jas_subtype", "aandacht", "lifecycle", "verouderd", "soort")
_TEKSTVELDEN = {"toelichting": 300, "review_uitleg": 300}


def _compact(e: dict[str, Any]) -> dict[str, Any]:
    uit = {k: e[k] for k in _ZOEKVELDEN if e.get(k) not in (None, "", [], {})}
    for k, maximum in _TEKSTVELDEN.items():
        if isinstance(e.get(k), str) and e[k].strip():
            uit[k] = e[k] if len(e[k]) <= maximum else e[k][:maximum] + "…"
    if e.get("alternatieven"):
        uit["alternatieven"] = e["alternatieven"]
    iri = e.get("eigenaar_iri") or (e.get("bronverwijzing") or {}).get("bron_iri") or ""
    if iri:
        uit["bron_iri"] = iri
        uit["vindplaats"] = vindplaats_label(iri)
    if isinstance(e.get("laag"), dict) and e["laag"].get("status"):
        uit["laagstatus"] = e["laag"]["status"]
    return uit


def compacte_uitkomst(name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Status en volledigheid vóórop, dan de compacte treffers. Wie alleen het begin leest – een
    model met een krap venster – ziet zo eerst óf het resultaat te vertrouwen is."""
    kop = {k: result[k] for k in ("status", "volledig", "reden", "detail") if k in result}
    rest = {k: v for k, v in result.items() if k not in kop}
    if name == "search_annotaties" and isinstance(rest.get("resultaten"), list):
        rest["resultaten"] = [_compact(e) for e in rest["resultaten"] if isinstance(e, dict)]
    elif name == "get_annotatie" and isinstance(rest.get("element"), dict):
        # Eén element: het spoor (`trace`) blijft, dat is het antwoord op "waarom deze klasse?".
        # Alleen de run van de hele batch gaat eruit.
        rest["element"] = {k: v for k, v in rest["element"].items() if k != "geproduceerd_door"}
    return {**kop, **rest}


def dispatch_annotatie(name: str, args: dict[str, Any], port) -> str:
    args = _normaliseer_klassen(args)
    definition = next(t for t in ANNOTATIE_TOOLS if t["name"] == name)["input_schema"]
    if set(args) - set(definition["properties"]) or any(k not in args for k in definition["required"]):
        raise ValueError("Ongeldige argumenten voor annotatiezoektool")
    for key, value in args.items():
        if key in ("limit", "offset"):
            if type(value) is not int or value < (1 if key == "limit" else 0):
                raise ValueError("Ongeldige paginatie")
            if key == "limit" and value > 100:
                raise ValueError("Maximaal 100 resultaten per pagina")
        elif definition["properties"][key]["type"] == "array":
            if not isinstance(value, list) or len(value) > 30 or any(not isinstance(v, str) or len(v) > 200 for v in value):
                raise ValueError("Ongeldige filterlijst")
            toegestaan = definition["properties"][key]["items"].get("enum")
            if toegestaan and set(value) - set(toegestaan):
                raise ValueError("Onbekende filterkeuze")
        elif definition["properties"][key]["type"] == "boolean":
            if type(value) is not bool:
                raise ValueError("Ongeldige boolean")
        elif not isinstance(value, str) or len(value) > (2048 if key == "cursor" else 2000):
            raise ValueError("Ongeldige filterwaarde")
        if "enum" in definition["properties"][key] and value not in definition["properties"][key]["enum"]:
            raise ValueError("Onbekende filterkeuze")
    if port is None:
        result = {"status": "unavailable", "volledig": False, "reden": "annotatie_api_niet_ingesteld"}
    elif name == "search_annotaties":
        result = port.zoeken(args)
    elif name == "get_annotatie":
        result = port.element(args["id"])
    else:
        if not args.get("bron_iri") and not (args.get("bwb_id") and args.get("artikel")):
            raise ValueError("Geef een bronnode of regeling en bepaling")
        result = port.dekking(args)
    return json.dumps({"bewijssoort": "annotatie", **compacte_uitkomst(name, result)}, ensure_ascii=False)
