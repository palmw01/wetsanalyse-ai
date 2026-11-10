"""De bronconnector Rechtspraak (ADR-013, fase 1c): uitspraken die een wetsartikel noemen, en hun tekst.

Twee getypeerde tools, met het resultaatcontract van de graaftools:

- `zoek_uitspraken`: de uitspraken en conclusies die Linked Data Overheid (KOOP) aan een artikel koppelt, over alle
  versies van dat artikel, met instantie, datum en zaaknummer;
- `get_uitspraak`: de tekst van één Nederlandse uitspraak uit de open data van de Rechtspraak, per alinea.

**Een vermelding is geen uitleg.** LiDO koppelt een uitspraak aan een artikel als haar tekst het noemt; in de spike
(10 nov 2026) was dat in 30 van de 30 paren juist, maar in 4 noemde de uitspraak het artikel alleen terloops. De tool zegt
daarom "noemt", ordent naar instantie en datum en draagt `dekking: "ten minste"`: LiDO loopt achter op de wetgeving
en kan versies missen. **Een uitspraak is een bron, geen wettekst**: de vindplaats is de ECLI (`bronmodel.extern`),
de grounding toetst een citaat letterlijk, en wat de wet zegt onderbouwt ze niet. De rijen dragen hun tekst daarom
onder `id`, nooit onder `iri`/`uri`.

Het artikel zoekt de tool zelf op in de graaf (jci en label-id), zodat het model alleen regeling en artikel noemt.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Protocol

from bronmodel.connectors import INSTANTIES, RECHTSPRAAK
from bronmodel.extern import externe_vindplaats

from ..graph import queries
from ..graph.results import parse_select
from ..resultaat import compact, fout, pagina, per_eenheid

RECHTSPRAAK_TOOL_NAMEN = RECHTSPRAAK.tools
CONNECTOR = RECHTSPRAAK.naam

LIMIT = 25
STANDAARD = 10
#: Een alinea groter dan dit wordt op zinsgrenzen in delen geknipt (elk deel een eigen rij), zodat één rij binnen de
#: begroting blijft. Een deel draagt `deel` ("2/3").
MAX_ALINEA = 3000
_DATUM_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_TITEL_RE = re.compile(r"^\s*(ECLI:\S+)\s*-\s*(?P<orgaan>.+?),\s*(?P<d>\d{2})-(?P<m>\d{2})-(?P<j>\d{4})"
                       r"(?:\s*/\s*(?P<zaak>.+?))?\s*$")
_R = "{http://www.rechtspraak.nl/schema/rechtspraak-1.0}"
_RANG = {n: i for i, n in enumerate(INSTANTIES)}


class RechtspraakBron(Protocol):
    def koppelingen(self, bwb_id: str, artikel: str, jci: str = "") -> Any: ...
    def document(self, ecli: str) -> Any: ...


_CONTRACT = (
    "\nResultaatcontract: {status, volledig, aantal, totaal?, vervolg?, resultaten}. Is `volledig` false, roep "
    "dan `vervolg` aan voor de rest."
)
_UITLEG = (
    " Een uitspraak is rechtspraak, geen wettekst: noem haar met haar ECLI, zeg wat de wet zelf zegt alleen op grond "
    "van de opgehaalde bepaling, en zeg 'noemt het artikel', niet 'legt het uit', tot je de uitspraak hebt gelezen."
)

RECHTSPRAAK_TOOLS: list[dict[str, Any]] = [
    {
        "name": "zoek_uitspraken",
        "description": (
            "De uitspraken en conclusies die een wetsartikel noemen, volgens Linked Data Overheid (KOOP): over alle "
            "versies van het artikel, ook de oudere. Geef de regeling ('bwb_id') en het artikel; een lid kan niet, LiDO "
            "koppelt per artikel. Filter op 'instantie' (bijvoorbeeld 'Hoge Raad'), 'soort' (uitspraak of conclusie) en "
            "een periode ('vanaf', 'tot'). Volgorde 'nieuwste' (standaard) of 'oudste'." + _UITLEG + "\n"
            "GEEFT TERUG per uitspraak: id (de ECLI), label, soort, titel, datum (van de uitspraak), orgaan (het "
            "gerecht), nummer (het zaaknummer) en link; leesbaar: false als de tekst niet bij de Rechtspraak staat (een "
            "buitenlandse of Europese ECLI). Daarnaast 'bepaling', 'zoekvraag', 'totaal', 'per_instantie' (hoeveel "
            "uitspraken per soort gerecht), 'koppelingen' (hoeveel LiDO automatisch herkende en hoeveel een redactie "
            "legde) en 'dekking': "
            "altijd 'ten minste', met 'versies' (hoeveel versies van het artikel LiDO kende). Noem bij een lijst het "
            "totaal en dat het om vermeldingen gaat. Lees een uitspraak met get_uitspraak voor je zegt wat ze inhoudt."
            + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bwb_id": {"type": "string", "description": "BWB-id van de regeling, bijvoorbeeld 'BWBR0004770'."},
                "artikel": {"type": "string", "description": "Het artikelnummer, bijvoorbeeld '36' of '8:57'."},
                "instantie": {"type": "string", "enum": list(INSTANTIES),
                              "description": "Alleen uitspraken van dit soort gerecht."},
                "soort": {"type": "string", "enum": ["uitspraak", "conclusie"],
                          "description": "Een uitspraak of een conclusie van de advocaat-generaal."},
                "vanaf": {"type": "string", "description": "Vanaf deze datum van de uitspraak: JJJJ-MM-DD, JJJJ-MM of "
                                                           "JJJJ, bijvoorbeeld '2020'."},
                "tot": {"type": "string", "description": "Tot en met deze datum, in dezelfde vorm."},
                "volgorde": {"type": "string", "enum": list(RECHTSPRAAK.volgordes),
                             "description": "nieuwste of oudste (op de datum van de uitspraak)."},
                "aantal": {"type": "integer", "description": f"Hoeveel per pagina, 1 tot {LIMIT}."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
            },
            "required": ["bwb_id", "artikel"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_uitspraak",
        "description": (
            "De tekst van één Nederlandse uitspraak of conclusie uit de open data van de Rechtspraak, per alinea in "
            "documentvolgorde, met de inhoudsindicatie eerst. Gebruik de ECLI uit zoek_uitspraken." + _UITLEG +
            " Citeer letterlijk uit 'tekst'.\n"
            "GEEFT TERUG: het stuk (id, label, soort, titel, datum, orgaan, nummer, gepubliceerd, link, bron_hash, "
            "gewijzigd) en per alinea nr, kop en tekst; een lange alinea staat in delen ('deel'). Noem de datum en "
            "de instantie uit 'stuk', niet uit de tekst." + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "De ECLI, bijvoorbeeld 'ECLI:NL:HR:2022:50'."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
]


# --- de metadata van een uitspraak --------------------------------------------------------------------------------

def instantie(ecli: str) -> str:
    """De soort gerecht uit de code in de ECLI (`INSTANTIES`)."""
    delen = ecli.upper().split(":")
    land, code = (delen[1], delen[2]) if len(delen) > 2 else ("", "")
    if land == "CE":
        return "Europees Hof voor de Rechten van de Mens"
    if land == "EU":
        return "Hof van Justitie van de EU"
    if land != "NL":
        return "overig"
    vast = {"HR": "Hoge Raad", "PHR": "Parket bij de Hoge Raad", "RVS": "Raad van State",
            "CRVB": "Centrale Raad van Beroep", "CBB": "College van Beroep voor het bedrijfsleven"}
    if code in vast:
        return vast[code]
    if code.startswith("GH"):
        return "gerechtshof"
    if code.startswith("RB"):
        return "rechtbank"
    return "overig"


def soort_van(ecli: str) -> str:
    return "Conclusie" if ecli.upper().split(":")[2:3] == ["PHR"] else "Uitspraak"


def koppeling_van(soorten: set[str]) -> str:
    return "redactioneel" if any("Redactionele" in k for k in soorten) else "automatisch herkend"


def rij_van(ecli: str, titel: str) -> dict[str, Any]:
    """Eén uitspraak in de vaste metadatasleutels (`METADATA_SLEUTELS`), uit de ECLI en de titel die LiDO van de
    Rechtspraak overneemt. De soort gerecht (voor het filter) leidt `instantie` af uit de ECLI; die staat niet in de rij."""
    vp = externe_vindplaats(ecli)
    ident = vp.id if vp is not None else ecli
    m = _TITEL_RE.match(titel or "")
    datum = f"{m['j']}-{m['m']}-{m['d']}" if m else ""
    return compact({
        "id": ident, "label": vp.label if vp is not None else ident, "soort": soort_van(ident), "titel": titel,
        "datum": datum or (ident.split(":")[3] if ident.count(":") >= 3 else ""),
        "orgaan": (m["orgaan"].strip() if m else "") or instantie(ident),
        "nummer": (m["zaak"] or "").strip() if m else "",
        "link": vp.uri if vp is not None else "",
        **({"leesbaar": False} if not ident.upper().startswith("ECLI:NL:") else {})})


# --- zoeken --------------------------------------------------------------------------------------------------------

def _q_artikel(bwb_id: str, artikel: str) -> str:
    """De jci, de label-id en het soort van de bepaling, uit de graaf."""
    return queries.PREFIXES + f"""SELECT ?node ?jci ?labelId ?label ?soort WHERE {{
  {queries.node_patroon(bwb_id, artikel)}
  ?node a ?soort . FILTER(?soort IN (bwb:Artikel, bwb:Divisie))
  OPTIONAL {{ ?node bwb:jci ?jci }}
  OPTIONAL {{ ?node bwb:labelId ?labelId }}
  OPTIONAL {{ ?node rdfs:label ?label }}
}} LIMIT 2"""


def _datum(waarde: str, *, eind: bool) -> str:
    m = _DATUM_RE.match((waarde or "").strip())
    if not m:
        raise ValueError(waarde)
    j, mnd, d = m.group(1), m.group(2), m.group(3)
    if d:
        return f"{j}-{mnd}-{d}"
    if mnd:
        return f"{j}-{mnd}-31" if eind else f"{j}-{mnd}-01"
    return f"{j}-12-31" if eind else f"{j}-01-01"


def _zoek(bron: RechtspraakBron, graph: Any, a: dict[str, Any]) -> str:
    bwb_id, artikel = (a.get("bwb_id") or "").strip(), (a.get("artikel") or "").strip()
    if not re.fullmatch(r"BWB[RV]\d{7}", bwb_id) or not artikel:
        return fout("ongeldige_argumenten", "geef de regeling en het artikel, bijvoorbeeld "
                    "{\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\"}")
    volgorde = a.get("volgorde") or "nieuwste"
    if volgorde not in RECHTSPRAAK.volgordes:
        return fout("ongeldige_volgorde", f"de volgorde is 'nieuwste' of 'oudste', bijvoorbeeld "
                    f"{{\"volgorde\": \"oudste\"}}, niet {volgorde!r}")
    if a.get("instantie") and a["instantie"] not in INSTANTIES:
        return fout("ongeldige_argumenten", f"de instantie is een van {', '.join(INSTANTIES)}, bijvoorbeeld "
                    "'Hoge Raad'")
    try:
        vanaf = _datum(a["vanaf"], eind=False) if a.get("vanaf") else ""
        tot = _datum(a["tot"], eind=True) if a.get("tot") else ""
    except ValueError as exc:
        return fout("ongeldige_datum", f"een datum is JJJJ-MM-DD, JJJJ-MM of JJJJ, bijvoorbeeld '2020', niet {exc}")
    try:
        aantal = int(a.get("aantal") or STANDAARD)
    except (TypeError, ValueError):
        aantal = 0
    if not 1 <= aantal <= LIMIT:
        return fout("ongeldig_aantal", f"het aantal is 1 tot {LIMIT}, bijvoorbeeld {{\"aantal\": 10}}")
    offset = max(int(a.get("offset") or 0), 0)

    # Uit de graaf: de jci (de terugvalroute van LiDO, nodig voor de Awb), het label en of het een artikel is. Zonder
    # graaf (een MCP-client, de contractharnas) zoekt LiDO het artikel op bwb-id en nummer.
    rijen = (parse_select(graph.sparql(_q_artikel(bwb_id, artikel))) if graph is not None
             else [{"label": f"artikel {artikel}", "soort": "Artikel"}])
    if not rijen:
        return fout("niet_gevonden", f"artikel {artikel} van {bwb_id} staat niet in de graaf. Controleer het nummer, "
                    "bijvoorbeeld met get_artikel.")
    kop = rijen[0]
    label = kop.get("label") or f"artikel {artikel}"
    bepaling = {"bwb_id": bwb_id, "artikel": artikel, "label": label}
    if not str(kop.get("soort", "")).endswith("Artikel"):
        return pagina([], tool="zoek_uitspraken", args=a, limit=aantal, offset=offset,
                      toelichting=(f"{label} is een divisie van een beleidsregel. LiDO koppelt uitspraken alleen aan "
                                   "artikelen van wetten en regelingen; de divisies kent het niet."),
                      extra={"bepaling": bepaling, "dekking": "ten minste", "totaal": 0})
    k = bron.koppelingen(bwb_id, artikel, kop.get("jci") or "")

    # Eén rij per uitspraak, verenigd over de versies; de koppelingen (automatisch, redactioneel) samen.
    per: dict[str, tuple[str, set[str]]] = {}
    for ln in k.links:
        titel, soorten = per.get(ln.ecli, ("", set()))
        per[ln.ecli] = (titel or ln.titel, soorten | {ln.soort_link})
    alle = [rij_van(e, t) for e, (t, _) in per.items()]
    per_instantie: dict[str, int] = {}
    koppelingen: dict[str, int] = {}
    for e, (_, soorten) in per.items():
        per_instantie[instantie(e)] = per_instantie.get(instantie(e), 0) + 1
        koppelingen[koppeling_van(soorten)] = koppelingen.get(koppeling_van(soorten), 0) + 1
    lijst = [r for r in alle
             if (not a.get("instantie") or instantie(r["id"]) == a["instantie"])
             and (not a.get("soort") or r["soort"].lower() == a["soort"])
             and (not vanaf or r["datum"] >= vanaf) and (not tot or r["datum"][:10] <= tot)]
    # Op datum; bij dezelfde datum de hoogste instantie eerst, dan de ECLI (vast, dus dezelfde vraag dezelfde lijst).
    lijst.sort(key=lambda r: (_RANG.get(instantie(r["id"]), 99), r["id"]))
    lijst.sort(key=lambda r: r["datum"], reverse=volgorde == "nieuwste")
    toelichting = ""
    if k.onvolledig:
        toelichting = (f"Van {len(k.onvolledig)} van de {len(k.versies)} versies kwam niet alles binnen (plafond of een "
                       "afgebroken antwoord van LiDO); de lijst is daar korter dan wat LiDO kent.")
    elif not k.versies:
        toelichting = (f"LiDO kent {label} van {bwb_id} niet; dat zegt niet dat er geen uitspraken over zijn. Zoek "
                       "eventueel via een andere bron.")
    elif not lijst:
        toelichting = "LiDO noemt bij dit artikel geen uitspraken die aan de filters voldoen."
    extra = compact({
        "bepaling": bepaling, "totaal": len(lijst), "dekking": "ten minste", "versies": len(k.versies),
        "per_instantie": dict(sorted(per_instantie.items(), key=lambda x: _RANG.get(x[0], 99))),
        "koppelingen": koppelingen,
        "zoekvraag": {**{x: v for x, v in a.items() if x not in {"offset"} and v not in ("", None)},
                      "volgorde": volgorde},
    })
    return pagina(lijst[offset:offset + aantal + 1], tool="zoek_uitspraken", args={**a, "aantal": aantal},
                  limit=aantal, offset=offset, toelichting=toelichting, extra=extra)


# --- lezen ---------------------------------------------------------------------------------------------------------

def _tekst(e: ET.Element) -> str:
    return " ".join("".join(e.itertext()).split())


def _knip(tekst: str) -> list[str]:
    """Een lange alinea in delen op zinsgrenzen, elk hoogstens `MAX_ALINEA` tekens (een zin langer dan dat blijft heel
    en wordt op een spatie geknipt)."""
    if len(tekst) <= MAX_ALINEA:
        return [tekst]
    delen, huidig = [], ""
    for zin in re.split(r"(?<=[.;:])\s+", tekst):
        while len(zin) > MAX_ALINEA:
            knip = zin.rfind(" ", 0, MAX_ALINEA) or MAX_ALINEA
            delen.append((huidig + " " + zin[:knip]).strip() if huidig else zin[:knip])
            huidig, zin = "", zin[knip:].strip()
        if huidig and len(huidig) + 1 + len(zin) > MAX_ALINEA:
            delen.append(huidig)
            huidig = zin
        else:
            huidig = f"{huidig} {zin}".strip()
    if huidig:
        delen.append(huidig)
    return delen


def lees(xml: bytes) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """(metadata, rijen) uit een document van de Rechtspraak. Rijen in documentvolgorde: de inhoudsindicatie, dan de
    uitspraak of conclusie; een `title` is de kop van de alinea's erna. Lege alinea's tellen niet."""
    root = ET.fromstring(xml)
    meta: dict[str, str] = {}
    beschrijving = next((d for d in root.iter("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description")), None)
    if beschrijving is not None:
        for c in beschrijving:
            naam = c.tag.rsplit("}", 1)[-1]
            if naam in {"identifier", "date", "issued", "modified", "creator", "type", "zaaknummer", "title"} \
                    and naam not in meta:
                meta[naam] = (c.text or "").strip()
    rijen: list[dict[str, Any]] = []

    def voeg(tekst: str, kop: str) -> None:
        delen = _knip(tekst)
        for i, deel in enumerate(delen, 1):
            rijen.append(compact({"nr": len(rijen) + 1, "kop": kop, "tekst": deel,
                                  "deel": f"{i}/{len(delen)}" if len(delen) > 1 else ""}))

    def loop(e: ET.Element, kop: str) -> str:
        for c in e:
            naam = c.tag.replace(_R, "")
            if naam == "title":
                kop = _tekst(c) or kop
            elif naam == "para":
                if t := _tekst(c):
                    voeg(t, kop)
            else:
                kop = loop(c, kop)
        return kop

    for deel in root:
        naam = deel.tag.replace(_R, "")
        if naam == "inhoudsindicatie":
            loop(deel, "Inhoudsindicatie")
        elif naam in {"uitspraak", "conclusie"}:
            loop(deel, "Conclusie" if naam == "conclusie" else "Uitspraak")
    return meta, rijen


def _get(bron: RechtspraakBron, a: dict[str, Any]) -> str:
    vp = externe_vindplaats((a.get("id") or "").strip())
    if vp is None or vp.brontype != "uitspraak" or not vp.id.startswith(RECHTSPRAAK.id_prefixen):
        return fout("ongeldig_id", "geef de ECLI van een Nederlandse uitspraak, bijvoorbeeld 'ECLI:NL:HR:2022:50'")
    doc = bron.document(vp.id)
    try:
        meta, rijen = lees(doc.xml)
    except ET.ParseError as exc:
        return fout("onleesbaar_document", f"{vp.id} kon niet worden gelezen: {exc}")
    stuk = compact({
        "id": vp.id, "label": vp.label, "soort": meta.get("type") or soort_van(vp.id),
        "titel": meta.get("title", ""), "datum": meta.get("date", ""), "orgaan": meta.get("creator", ""),
        "nummer": meta.get("zaaknummer", ""), "gepubliceerd": meta.get("issued", ""), "link": vp.uri,
        "bron_hash": doc.hash, "gewijzigd": getattr(doc, "gewijzigd", "") or meta.get("modified", "")})
    if getattr(doc, "gevalideerd", True) is False:
        # De Rechtspraak was niet te bereiken: de bewaarde versie, en dat zegt het stuk (het bronvenster toont het).
        stuk["gevalideerd"] = False
    offset = max(int(a.get("offset") or 0), 0)
    return per_eenheid(rijen, tool="get_uitspraak", args={"id": vp.id}, offset=offset,
                       extra={"stuk": stuk, "totaal": len(rijen)},
                       toelichting="" if rijen else "Deze uitspraak heeft geen tekst in de open data.")


#: De reden in het foutresultaat per code van de adapter (`RechtspraakFout.code`).
FOUTREDEN = {"onbereikbaar": "bron_onbereikbaar", "geweigerd": "onleesbaar_document", "niet_gevonden": "niet_gevonden"}


def fout_van(exc: Any) -> str:
    code = getattr(exc, "code", "onbereikbaar")
    if code == "niet_gevonden":
        return fout("niet_gevonden", f"{exc}. Controleer de ECLI, of zoek uitspraken bij een artikel met "
                    "zoek_uitspraken, bijvoorbeeld {\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\"}.")
    return fout(FOUTREDEN.get(code, "bron_onbereikbaar"), str(exc))


def dispatch_rechtspraak(name: str, args: dict[str, Any], bron: RechtspraakBron | None, graph: Any) -> str:
    if bron is None:
        return fout("connector_uit", "De bron Rechtspraak staat uit. Zeg dat, en antwoord niet uit eigen kennis.")
    if name == "zoek_uitspraken":
        return _zoek(bron, graph, args)
    if name == "get_uitspraak":
        return _get(bron, args)
    raise KeyError(name)
