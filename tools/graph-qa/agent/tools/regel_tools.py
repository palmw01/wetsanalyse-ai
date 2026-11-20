"""Leestools voor afleidingsregels (ADR-018; regels herleidbaar, 20 nov 2026, stap 7).

Een afleidingsregel is een analyse-uitkomst van juristen in een werkgebied (activiteit 3b), geen wettekst. Lex leest
de regels altijd bij de api (`agent/regel_read.py`): Postgres is de waarheid, en de poort, de gaten en de toets van de
voorbeelden rekent alleen de api. Het resultaat is afgeleide duiding (`AFGELEIDE_TOOL_NAMEN`): nooit een bron, nooit
grounding. De wettekst waarop een regel rust, staat per drager als vindplaats met de jci of het anker; citeren doet
Lex pas na het ophalen van die bepaling met een brontool.

Alleen lezen: Lex stelt geen regel voor en accordeert niets (R5+ van het bouwplan staat op HOLD).
"""
from __future__ import annotations

import json
import re
from typing import Any

from .annotatie_tools import _d, schema

REGEL_TOOL_NAMEN = frozenset({"search_regels", "get_regel"})
STATUSSEN = ("concept", "geaccordeerd", "geaccordeerd_als_beleidsregel", "afgewezen", "vervangen")
MAX_RESULTATEN = 50
TOELICHTING = ("Afleidingsregels zijn analyse-uitkomsten van juristen binnen een werkgebied, geen wettekst. Noem bij "
               "elke regel de status en het werkgebied; een concept is nog niet beoordeeld. Citeer de wettekst waarop een "
               "regel rust pas nadat je die bepaling met een brontool hebt opgehaald.")

S = {"type": "string"}

REGEL_TOOLS = [
    schema("search_regels", "Zoek afleidingsregels die juristen in werkgebieden vastlegden (activiteit 3b): op naam, "
           "uitvoer of regeltekst, over alle werkgebieden of in één. Een regel is een analyse-uitkomst met een status "
           "(concept, geaccordeerd, geaccordeerd als beleidsregel, afgewezen, vervangen), geen wettekst. Nul treffers "
           "is geen bewijs dat een regel ontbreekt. GEEFT TERUG: per regel id, naam, uitvoer, status, soort, werkgebied, "
           "aantal gevallen en de regeltekst (ingekort). Gebruik get_regel voor de gevallen, de dragers en de poort.",
           {"zoekterm": _d(S, "Woord of woorden uit naam, uitvoer of regeltekst; leeg = alles."),
            "status": {"type": "array", "items": {"type": "string", "enum": list(STATUSSEN)}, "maxItems": 5,
                       "description": "Alleen deze statussen (meerdere = of)."},
            "werkgebied_id": _d(S, "Alleen regels uit dit werkgebied; leeg = het werkgebied van het gesprek, of alle."),
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_RESULTATEN}}),
    schema("get_regel", "Lees één afleidingsregel: de regeltekst per geval, de invoer, de dragers (de markeringen "
           "waarop de regel rust, met rol, geval, beoordeling, de letterlijke passage en de vindplaats met jci of "
           "anker), de voorbeelden met de toets of ze bij hun geval passen, wat nog openstaat voor accorderen, de "
           "signalen en de gaten. Analyse-uitkomst; haal de wettekst apart op.",
           {"werkgebied_id": _d(S, "Het werkgebied van de regel, uit search_regels."),
            "regel_id": _d(S, "Het id van de regel, uit search_regels.")}, ("werkgebied_id", "regel_id")),
]


def _kort(tekst: str, n: int) -> str:
    tekst = " ".join((tekst or "").split())
    return tekst if len(tekst) <= n else tekst[: n - 1].rstrip() + "…"


def _rij(r: dict[str, Any]) -> dict[str, Any]:
    return {"id": r.get("id", ""), "naam": r.get("naam", ""), "uitvoer": r.get("uitvoer", ""),
            "regel_status": r.get("status", ""), "soort": r.get("soort", ""), "brontype": r.get("brontype", ""),
            "werkgebied": r.get("werkgebied_naam", ""), "werkgebied_id": r.get("werkgebied_id", ""),
            "gevallen": r.get("gevallen", 0), "regeltekst": _kort(r.get("regeltekst", ""), 600)}


def zoek(args: dict[str, Any], port) -> dict[str, Any]:
    wg = str(args.get("werkgebied_id") or "") or (getattr(port, "werkgebied_id", "") or "")
    limit = int(args.get("limit") or 25)
    antwoord = port.zoek(str(args.get("zoekterm") or ""), list(args.get("status") or []), wg)
    if antwoord.get("status") != "ok":
        return {k: antwoord[k] for k in ("status", "volledig", "reden", "detail") if k in antwoord}
    rijen = antwoord.get("resultaten") or []
    return {"status": "ok", "volledig": len(rijen) <= limit, "aantal": min(len(rijen), limit),
            "resultaten": [_rij(r) for r in rijen[:limit]], "per_status": antwoord.get("per_status") or {},
            **({"werkgebied_id": wg} if wg else {}), "toelichting": TOELICHTING}


def _drager(d: dict[str, Any]) -> dict[str, Any]:
    b, bron = d.get("bewijs") or {}, d.get("bron") or {}
    uit = {"rol": d.get("rol", ""), "geval": d.get("geval", ""), "beoordeling": d.get("beoordeling", ""),
           "actualiteit": d.get("actualiteit", ""), "klasse": b.get("klasse", ""), "passage": _kort(b.get("tekst", ""), 300),
           "vindplaats": b.get("vindplaats") or bron.get("vindplaats") or bron.get("label", "")}
    if bron.get("bron_iri") or b.get("eigenaar_iri"):
        uit["bron_iri"] = bron.get("bron_iri") or b.get("eigenaar_iri")
    if bron.get("jci"):
        uit["jci"] = bron["jci"]
    elif bron.get("bron_url") or bron.get("url"):
        uit["anker"] = bron.get("bron_url") or bron.get("url")
    return uit


def compact_regel(r: dict[str, Any]) -> dict[str, Any]:
    i, namen = r.get("inhoud") or {}, {k: v.get("naam", "") for k, v in (r.get("begrippen") or {}).items()}
    uit: dict[str, Any] = {
        "status": "ok", "volledig": True, "id": r.get("id", ""), "regel_status": r.get("status", ""),
        "revisie": r.get("revisie"), "naam": r.get("naam", ""), "uitvoer": r.get("uitvoer", ""),
        "soort": i.get("soort", ""), "brontype": i.get("brontype", ""), "werkgebied_id": r.get("werkgebied_id", ""),
        "regeltekst": [{"geval": g.get("label", ""), "tekst": g.get("tekst", "")}
                       for g in (r.get("regeltekst") or {}).get("gevallen") or []]
                      or (r.get("regeltekst") or {}).get("tekst", ""),
        "invoer": [{"begrip": namen.get(x["begrip_id"], x["begrip_id"]), "rol": x.get("rol", "invoer")}
                   for x in i.get("invoer") or []],
        "dragers": [_drager(d) for d in (r.get("dragers") or [])[:40]],
        "voorbeelden": [{"nr": n, "geval": v.get("geval", ""), "invoer": _kort(v.get("invoer", ""), 300),
                         "uitkomst": _kort(v.get("uitkomst", ""), 300), "oordeel": v.get("oordeel", "open"),
                         **({"waarden": [{"begrip": namen.get(w["begrip_id"], w["begrip_id"]), "waarde": w["waarde"]}
                                         for w in v["waarden"]]} if v.get("waarden") else {})}
                        for n, v in enumerate((i.get("voorbeelden") or [])[:20], start=1)],
        "accorderen": r.get("accorderen") or {}, "signalen": r.get("signalen") or [],
        "gaten": [g.get("tekst", "") for g in r.get("gaten") or []], "open_punten": r.get("open_punten") or {},
        "toelichting": TOELICHTING}
    # De opvolging met de namen (herhaalmeting na #1796): de namen van voorgangers en opvolger staan zo letterlijk in het
    # toolresultaat, en het antwoord mag ze noemen. Een oudere api stuurt alleen de id's.
    o = r.get("opvolging") or {}
    if o.get("vervangen_door"):
        uit["vervangen_door"] = o["vervangen_door"]
    elif r.get("vervangen_door"):
        uit["vervangen_door"] = {"id": r["vervangen_door"], "naam": ""}
    vervangt = o.get("vervangt") or ([{"id": r["opvolger_van"], "naam": ""}] if r.get("opvolger_van") else [])
    if vervangt:
        uit["vervangt"] = vervangt
    return uit


def dispatch_regel(name: str, args: dict[str, Any], port) -> str:
    definition = next(t for t in REGEL_TOOLS if t["name"] == name)["input_schema"]
    if set(args) - set(definition["properties"]) or any(k not in args for k in definition["required"]):
        raise ValueError("Ongeldige argumenten voor regeltool")
    for key, value in args.items():
        if key == "limit":
            if type(value) is not int or not 1 <= value <= MAX_RESULTATEN:
                raise ValueError("Ongeldige limit")
        elif key == "status":
            if not isinstance(value, list) or len(value) > 5 or set(value) - set(STATUSSEN):
                raise ValueError("Onbekende status")
        elif not isinstance(value, str) or len(value) > 200:
            raise ValueError(f"Ongeldige waarde voor {key}")
    if port is None:
        result: dict[str, Any] = {"status": "unavailable", "volledig": False, "reden": "regels_api_niet_ingesteld"}
    elif name == "search_regels":
        result = zoek(args, port)
    else:
        antwoord = port.regel(args["werkgebied_id"], args["regel_id"])
        result = compact_regel(antwoord["regel"]) if antwoord.get("status") == "ok" else antwoord
    return json.dumps({"bewijssoort": "regel", **result}, ensure_ascii=False)


# --- herkennen (ADR-010: routering in code) -------------------------------------------------------------------------
# Een vraag over de vastgelegde afleidingsregels gaat zonder model naar de leesroute (`nodes/regels_lezen.py`): de code
# zoekt eerst, en een klein profiel formuleert (lichte meting #1792, 20 nov 2026: "Welke afleidingsregels bepalen de
# vervaldag van een termijn, en op welke artikelen rusten ze?" ging naar de centrale agent, die de regeltools achter
# `meer_tools` niet gebruikte en uit de wettekst antwoordde).
#
# "Afleidingsregel" is ook een JAS-klasse: een vraag naar markeringen of annotaties van die klasse is een leesvraag over
# annotaties, geen vraag over het regelobject. Een opdracht (opstellen, accorderen) is ook geen leesvraag.
_REGEL = re.compile(r"\b(afleidingsregels?|rekenregels?|beslisregels?|regelkaarten?|afleidingshi[eë]rarchie)\b")
_ANNOTATIE = re.compile(r"\b(markering\w*|gemarkeerd\w*|annota\w*|geannoteerd\w*|klasse|jas)\b")
_REGEL_SCHRIJVEN = re.compile(r"\b(stel\w*|maak|maken|formuleer\w*|accordeer\w*|wijzig\w*|verwijder\w*|wijs\b|afwijzen"
                              r"|keur\w*|beoordeel\w*|annoteer\w*|markeer\w*)\b")
# Het onderwerp van de regel ("bepalen de vervaldag", "voor het termijnbedrag", "over de verrekening").
_ONDERWERP = re.compile(r"\b(?:bepal\w*|voor|over|van|berekenen|berekent)\s+(?:de|het|een)\s+([a-zà-ÿ\- ]+?)"
                        r"(?=\s+(?:van|in|bij|en|op|uit|met|dat|die)\b|\s*[?.!,;:]|\s*$)")


# "Regel(s)" alleen samen met de stand of de opvolging van een regelobject ("welke regels zijn vervangen, en door
# welke regel?", herhaalmeting na #1796, run 9b6d4e23: 262k via de centrale agent). Een kale "regel" is meestal wettekst
# ("welke regels gelden voor …"), en een vraag die een artikel, lid of regeling noemt ook ("welke regels van de
# Invorderingswet zijn vervangen?").
_REGELWOORD = re.compile(r"\bregels?\b")
_STAND = re.compile(r"\b(vervangen|vervangt|opvolger\w*|voorganger\w*|afgewezen|geaccordeerd\w*|concept(en)?"
                    r"|beleidsregel\w*|status|stand)\b")
_WETTEKST = re.compile(r"\b(artikel\w*|art\.|lid|leden|\w*wet(?:ten|boek)?|\w*regeling\w*|bwbr\d+|leidraad|\w*besluit\w*)\b")


def is_regel_leesvraag(vraag: str) -> bool:
    q = (vraag or "").casefold()
    if _ANNOTATIE.search(q) or _REGEL_SCHRIJVEN.search(q):
        return False
    if _REGEL.search(q):
        return True
    return bool(_REGELWOORD.search(q) and _STAND.search(q) and not _WETTEKST.search(q))


def zoekterm_regel(vraag: str) -> str:
    """Het onderwerp van de regel als zoekterm ("vervaldag"), of leeg: dan zoekt de route alle regels van het werkgebied.
    Een verkeerd geraden term levert stil te weinig op, dus alleen na een vast patroon; het model verfijnt daarna zelf."""
    q = (vraag or "").casefold()
    na = _REGEL.search(q) or _REGELWOORD.search(q)
    if m := _ONDERWERP.search(q[na.end():] if na else q):
        woorden = [w for w in m.group(1).split() if w not in {"regel", "regels", "afleidingsregel", "afleidingsregels"}]
        return " ".join(woorden[:3])
    return ""
