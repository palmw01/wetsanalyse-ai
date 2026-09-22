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
        return "Ik heb de opgeslagen annotaties niet kunnen raadplegen; ik kan daarom geen zoekuitkomst geven."
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
    q = question.casefold()
    # Een leesvraag mag niet door een modelrouter in een schrijfactie veranderen.
    onderwerp = re.search(r"\b(annotaties?|markeringen?|geannoteerd|annotatiedekking)\b", q)
    lezen = re.search(r"\b(zoek|vind|toon|bekijk|laat|zien|welke?|wat|waar|hoe|hoeveel|bestaande|opgeslagen|al|dekking)\b", q)
    schrijven = re.search(r"\b(annoteer|annoteren|herannoteer|maak|maken|voeg|toevoegen|wijzig|wijzigen|verwijder|verwijderen|corrigeer|corrigeren)\b", q)
    return bool(onderwerp and lezen and not schrijven)


def schema(name, description, properties, required=()):
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": properties,
                             "required": list(required), "additionalProperties": False}}


S = {"type": "string"}
SS = {"type": "array", "items": S, "maxItems": 30}
ANNOTATIE_TOOLS = [
    schema("search_annotaties", "Zoek opgeslagen JAS-annotaties, niet de wettekst. Filters zijn "
           "letterlijk en worden gecombineerd. Onvolledig/onbeschikbaar is geen bewijs dat er "
           "geen annotaties bestaan. Geen semantische fallback. Resultaten zijn afgeleide duiding.",
           {"bron_iri": S, "bwb_id": S, "klasse": S, "jas_klassen": SS, "tekst": S,
            "lifecycle": SS, "laagstatus": SS, "bronversie": S,
            "tekstveld": {"type": "string", "enum": ["citaat", "toelichting", "beide"]},
            "match": {"type": "string", "enum": ["exact", "bevat"]},
            "scope": {"type": "string", "enum": ["node", "subtree"]},
            "inclusief_verouderd": {"type": "boolean"}, "cursor": S,
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0}}),
    schema("get_annotatie", "Lees één opgeslagen annotatie inclusief eigenaar, alle lokale "
           "ankers en beoordeling. Dit is duiding; haal de bron apart op voor juridische claims.",
           {"id": S}, ("id",)),
    schema("get_annotatiedekking", "Controleer of een bronnode/subtree daadwerkelijk geannoteerd "
           "is; aanwezigheid van enkele elementen bewijst geen volledige dekking.",
           {"bron_iri": S, "bwb_id": S, "artikel": S, "lid": S}),
]


def dispatch_annotatie(name: str, args: dict[str, Any], port) -> str:
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
    return json.dumps({"bewijssoort": "annotatie", **result}, ensure_ascii=False)
