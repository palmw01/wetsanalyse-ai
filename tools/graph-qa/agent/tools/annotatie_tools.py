"""Getypeerde leesoperaties: geen schrijfbevoegdheid en geen wetgevingsfallback."""
from __future__ import annotations

import json
import re
from typing import Any

ANNOTATIE_TOOL_NAMEN = frozenset({"search_annotaties", "overzicht_annotaties", "get_annotatie",
                                  "get_annotatiedekking"})


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


def _d(basis: dict, beschrijving: str) -> dict:
    return {**basis, "description": beschrijving}


def _klassen() -> dict:
    from ..jas_klassen import JAS_KLASSEN_VOLGORDE
    return _d(keuzes(*JAS_KLASSEN_VOLGORDE), "JAS-klassen, exact zoals hier gespeld (meerdere = of).")


BRON_IRI = _d(S, "Een bronnode, bv. 'urn:bwb:BWBR0004770:artikel:9:lid:1' (artikel: zonder ':lid:…').")
BWB_ID = _d(S, "Alleen annotaties binnen deze regeling, bv. 'BWBR0004770'.")

ANNOTATIE_TOOLS = [
    schema("search_annotaties", "Zoek opgeslagen JAS-annotaties, niet de wettekst. Filters zijn "
           "letterlijk en worden gecombineerd. Onvolledig/onbeschikbaar is geen bewijs dat er "
           "geen annotaties bestaan. Geen semantische fallback. Resultaten zijn afgeleide duiding. "
           "Herkomstfilters: `herkomst` (agent = voorstel van Lex, mens = door een jurist gemarkeerd), "
           "`aandacht` (geel = keuze voor de jurist, groen = bevestigd door review), `subtype`, "
           "`beslist_door` (regel/model/specificiteit/terugval) en `met_twijfel`. "
           "GEEFT TERUG: status en volledig, dan per treffer id, klasse, tekst, vindplaats, bron_iri, "
           "aandacht, lifecycle, alternatieven en een ingekorte toelichting; plus paginatie "
           "(volgende_offset/cursor). Wil je weten WELKE teksten van een klasse er zijn, gebruik dan "
           "overzicht_annotaties; voor het volledige spoor van één treffer get_annotatie.",
           {"bron_iri": BRON_IRI, "bwb_id": BWB_ID,
            "klasse": _d(S, "Eén JAS-klasse; liever jas_klassen."), "jas_klassen": _klassen(),
            "tekst": _d(S, "Zoektekst in het citaat en/of de toelichting (zie tekstveld en match)."),
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
           {"id": _d(S, "Het id van een annotatie, uit een zoekresultaat of de GESPREKSCONTEXT.")}, ("id",)),
    schema("get_annotatiedekking", "Controleer of een bronnode/subtree daadwerkelijk geannoteerd "
           "is; aanwezigheid van enkele elementen bewijst geen volledige dekking. Geef bron_iri, of "
           "bwb_id met artikel (en eventueel lid). GEEFT TERUG: status, voltooid, bereik (de "
           "geannoteerde bronnodes) en peilmoment.",
           {"bron_iri": BRON_IRI, "bwb_id": BWB_ID, "artikel": _d(S, "Artikelnummer, bij bwb_id."),
            "lid": _d(S, "Lidnummer, optioneel.")}),
    schema("overzicht_annotaties", "Overzicht van wat er al gemarkeerd is, per klasse: de "
           "verschillende teksten met hoe vaak en waar ze voorkomen. Voor vragen als 'welke "
           "rechtssubjecten kennen we al' of 'welke voorwaarden staan er nog meer in andere "
           "annotaties'. Met uitgezonderd_bron_iri laat je de bepaling waar het gesprek over gaat "
           "buiten beschouwing. GEEFT TERUG: status, volledig, het aantal bekeken markeringen en per "
           "groep klasse, tekst, aantal, vindplaatsen en een voorbeeld-id (voor get_annotatie). "
           "Leest via dezelfde gecontroleerde zoekroute als search_annotaties.",
           {"jas_klassen": _klassen(), "bwb_id": BWB_ID, "bron_iri": BRON_IRI,
            "uitgezonderd_bron_iri": _d(S, "Laat annotaties op deze bronnode (en eronder) weg."),
            "max_groepen": {"type": "integer", "minimum": 1, "maximum": 100,
                            "description": "Hoeveel groepen hoogstens (standaard 40)."}}),
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


#: Zoveel markeringen leest een overzicht hoogstens (pagina's van 100). Daarboven zegt hij dat hij
#: onvolledig is in plaats van stil een deel te laten zien.
OVERZICHT_PAGINAS = 5


def overzicht(args: dict[str, Any], port) -> dict[str, Any]:
    """Groepeer de markeringen per klasse en (genormaliseerde) tekst.

    "Welke rechtssubjecten kennen we al" is geen zoekvraag naar 25 losse records in willekeurige
    volgorde, maar een vraag naar de verschillende teksten. Die groepering gebeurt hier, over
    dezelfde gecontroleerde zoekroute als `search_annotaties` – geen eigen SPARQL, geen tweede
    waarheid."""
    filters = {k: args[k] for k in ("jas_klassen", "bwb_id", "bron_iri") if args.get(k)}
    if filters.get("bron_iri"):
        filters["scope"] = "subtree"
    uitgezonderd = str(args.get("uitgezonderd_bron_iri") or "")
    elementen: list[dict[str, Any]] = []
    volledig, status, offset = True, "ok", 0
    for _ in range(OVERZICHT_PAGINAS):
        pagina = port.zoeken({**filters, "limit": 100, "offset": offset})
        if pagina.get("status") not in ("ok", "partial"):
            return {k: pagina[k] for k in ("status", "volledig", "reden", "detail") if k in pagina}
        if pagina.get("status") != "ok" or pagina.get("volledig") is False:
            volledig, status = False, "partial"
        elementen += [e for e in pagina.get("resultaten") or [] if isinstance(e, dict)]
        offset = pagina.get("volgende_offset")
        if not offset:
            break
    else:
        volledig, status = False, "partial"

    from ..jas_klassen import JAS_KLASSEN_VOLGORDE
    groepen: dict[tuple[str, str], dict[str, Any]] = {}
    for e in elementen:
        iri = e.get("eigenaar_iri") or (e.get("bronverwijzing") or {}).get("bron_iri") or ""
        if uitgezonderd and (iri == uitgezonderd or iri.startswith(uitgezonderd + ":")):
            continue
        tekst = " ".join(str(e.get("tekst") or "").split())
        sleutel = (str(e.get("klasse") or ""), tekst.casefold())
        g = groepen.setdefault(sleutel, {"klasse": sleutel[0], "tekst": tekst, "aantal": 0,
                                         "vindplaatsen": [], "voorbeeld_id": e.get("id", "")})
        g["aantal"] += 1
        plek = vindplaats_label(iri)
        if plek and plek not in g["vindplaatsen"] and len(g["vindplaatsen"]) < 5:
            g["vindplaatsen"].append(plek)
    volgorde = {k: i for i, k in enumerate(JAS_KLASSEN_VOLGORDE)}
    lijst = sorted(groepen.values(), key=lambda g: (volgorde.get(g["klasse"], 99), -g["aantal"], g["tekst"]))
    maximum = int(args.get("max_groepen") or 40)
    return {"status": status, "volledig": volledig and len(lijst) <= maximum,
            "bekeken": len(elementen), "uitgezonderd": uitgezonderd or None,
            "groepen": lijst[:maximum], "meer_groepen": max(0, len(lijst) - maximum)}


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
        elif definition["properties"][key]["type"] == "integer":
            prop = definition["properties"][key]
            if type(value) is not int or not prop.get("minimum", 0) <= value <= prop.get("maximum", 10**6):
                raise ValueError(f"Ongeldige waarde voor {key}")
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
    elif name == "overzicht_annotaties":
        result = overzicht(args, port)
    else:
        if not args.get("bron_iri") and not (args.get("bwb_id") and args.get("artikel")):
            raise ValueError("Geef een bronnode of regeling en bepaling")
        result = port.dekking(args)
    return json.dumps({"bewijssoort": "annotatie", **compacte_uitkomst(name, result)}, ensure_ascii=False)
