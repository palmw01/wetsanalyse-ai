"""De bronconnector Staatsblad en Staatscourant (ADR-013): de officiële bekendmakingen.

Twee getypeerde tools, met het resultaatcontract van de graaftools:

- `zoek_bekendmakingen`: per bepaling de publicaties die de BWB bij haar huidige tekst noemt (de laatste wijziging en
  het inwerkingtredingsbesluit, uit de graaf), of bekendmakingen op titel, tekst, soort, blad, datum, jaargang,
  ministerie en Kamerdossier;
- `get_bekendmaking`: de tekst van één publicatie, per alinea met de kop erboven, in documentvolgorde; met `artikel`
  alleen de wijzigingsonderdelen die dat artikel wijzigen.

Een bekendmaking is een **bron, geen geldende wettekst**: de vindplaats is haar id (`stb-2010-176`, `bronmodel.extern`),
de grounding toetst een citaat letterlijk, en wat de wet nu zegt onderbouwt ze niet. De rijen dragen hun tekst onder
`id`, nooit onder `iri`/`uri`. Transport, zoekvragen en lezer zijn gedeeld met Kamerstukken (`adapters/sru_koop.py`,
`sru_zoeken.py`, `op_xml.py`).
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Protocol

from bronmodel.connectors import BEKENDMAKINGEN
from bronmodel.extern import bwb_bron_van, externe_vindplaats, koop_id_uit_bron

from ..graph import queries
from ..graph.results import parse_select
from ..resultaat import compact, fout, per_eenheid
from .op_xml import lees
from .sru_zoeken import LIMIT, MAX_WOORDEN, OP_VOLGORDE, cql_woorden, per_record, tekst_cql, tekst_woorden, zoekvraag
from .stuk_tekst import INHOUD_ARG, inhoudpagina, tekstpagina
from .zoekfilters import datum

logger = logging.getLogger("graph_qa.bekendmakingen")

#: Uit de beschrijving (`bronmodel.connectors`); de poorttest toetst dat `BEKENDMAKING_TOOLS` precies deze namen heeft.
BEKENDMAKING_TOOL_NAMEN = BEKENDMAKINGEN.tools
CONNECTOR = BEKENDMAKINGEN.naam

_BLADEN = {"Staatsblad": "stb", "Staatscourant": "stcrt"}
_BASIS = "c.product-area==officielepublicaties"
_DOSSIER_RE = re.compile(r"^\d{4,6}(?:-[A-Z0-9]{1,6})?$")
_JAAR_RE = re.compile(r"^(?:18|19|20)\d{2}$")
_BWB_RE = re.compile(r"^BWB[RV]\d{7}$")
_ARTIKEL_RE = re.compile(r"^[0-9A-Za-z:.]{1,20}$")
#: Hoogstens zo veel ids in één zoekvraag naar KOOP (`dt.identifier==… OR …`).
_PER_VRAAG = 40
#: Hoogstens zo veel publicaties per regeling; daarboven zegt de tool dat het er meer zijn.
MAX_BIJ_REGELING = 200
#: De soorten in de Staatscourant die regelgeving, beleid of de wetgevingsprocedure zijn (`dt.type`, live 10 nov 2026).
#: De Staatscourant draagt ook deurwaardersexploten, faillissementen, curatele en vergunningen, met namen van
#: particulieren: die zoekt Lex niet en leest hij niet. "Overig" (vóór 2009 had de Staatscourant geen fijnere soorten,
#: ook de Leidraad Invordering 2008 niet) telt alleen bij een gerichte zoekvraag (woorden, tekst of dossier).
REGELGEVENDE_SOORTEN = ("algemeen verbindend voorschrift (ministeriële regeling)", "beleidsregel",
                        "ander besluit van algemene strekking", "circulaire", "interne regeling", "advies Raad van State")
_OUDE_SOORT = "Overig"


def _blad_cql(publicatie: str, gericht: bool) -> str:
    """Het filter op het blad: het Staatsblad helemaal, de Staatscourant alleen in de regelgevende soorten."""
    soorten = [*REGELGEVENDE_SOORTEN, *((_OUDE_SOORT,) if gericht else ())]
    stcrt = "(w.publicatienaam==Staatscourant AND (" + " OR ".join(f'dt.type=="{t}"' for t in soorten) + "))"
    if publicatie == "Staatsblad":
        return f"{_BASIS} AND w.publicatienaam==Staatsblad"
    if publicatie == "Staatscourant":
        return f"{_BASIS} AND {stcrt}"
    return f"{_BASIS} AND (w.publicatienaam==Staatsblad OR {stcrt})"


def binnen_bereik(rec: Any) -> bool:
    """Valt dit record binnen de bron? Het Staatsblad altijd; de Staatscourant alleen in de regelgevende soorten of
    "Overig" (`REGELGEVENDE_SOORTEN`)."""
    if getattr(rec, "publicatienaam", "") != "Staatscourant":
        return True
    return getattr(rec, "type", "") in (*REGELGEVENDE_SOORTEN, _OUDE_SOORT, "")


#: Een soort dat niet in `dt.type` staat maar in de titel ("tot vaststelling van het tijdstip van inwerkingtreding").
_SOORT_IN_TITEL = {"inwerkingtredingsbesluit": "inwerkingtreding"}
#: Hoe de BWB een publicatie aan een tekstdeel koppelt, in de woorden van de jurist.
KOPPELING = {"wijziging": "laatste wijziging", "inwerkingtreding": "inwerkingtreding"}


class BekendmakingBron(Protocol):
    def zoek(self, cql: str, *, start: int = 1, maximum: int = 50) -> tuple[int, list[Any]]: ...
    def document(self, ident: str) -> Any: ...


_CONTRACT = (
    "\nResultaatcontract: {status, volledig, aantal, totaal?, vervolg?, resultaten}. Is `volledig` false, roep "
    "dan `vervolg` aan voor de rest."
)
_UITLEG = (
    " Een bekendmaking laat zien wanneer en hoe een tekst is vastgesteld, gewijzigd of in werking trad; ze is niet de "
    "geldende tekst. Noem haar met haar id (stb-…, stcrt-…) en zeg wat de wet nu zegt alleen op grond van de opgehaalde "
    "bepaling."
)

BEKENDMAKING_TOOLS: list[dict[str, Any]] = [
    {
        "name": "zoek_bekendmakingen",
        "description": (
            "Zoek officiële bekendmakingen: het Staatsblad (wetten, wijzigingswetten, AMvB's, inwerkingtredingsbesluiten) "
            "en de Staatscourant (ministeriële regelingen, beleidsregels zoals de wijzigingen van de Leidraad "
            "Invordering). Twee wegen. MET 'bwb_id' (en 'artikel'): de publicaties die de BWB bij de huidige tekst van "
            "die bepaling noemt – de laatste wijziging en het besluit waarmee die in werking trad – of, zonder artikel, "
            "die van alle bepalingen van de regeling; alleen de toestand die Lex leest, geen eerdere wijzigingen. "
            "ZONDER bwb_id: combineer 'publicatie' (Staatsblad of Staatscourant), 'woorden' in de titel, 'tekst' in de "
            "hele tekst, 'soort', 'orgaan' (het ministerie), 'dossier' (het Kamerdossier van een wet), een periode "
            "('vanaf', 'tot') of 'jaar' (de jaargang). Kies de 'volgorde': 'nieuwste' of 'oudste' (op de datum), of "
            "'relevantie' bij woorden of tekst. Uit de Staatscourant komen alleen regelgeving, beleid en adviezen van de Raad "
            "van State, geen aankondigingen over personen." + _UITLEG + "\n"
            "GEEFT TERUG per publicatie: id, label (zoals 'Stb. 2010, 176'), publicatie, soort (zoals 'Wet', 'AMvB' of "
            "'beleidsregel'), titel, datum, ondertekend, jaar, nummer, orgaan, reeks (het Kamerdossier), samenvatting "
            "en link, en leesbaar: false als er alleen een PDF is. Met bwb_id ook 'wetsverwijzing' (laatste wijziging of "
            "inwerkingtreding van de bepaling, bij een regeling van hoeveel bepalingen) en 'inwerking' (de datum uit de "
            "BWB). "
            "Daarnaast 'zoekvraag' en 'totaal'. Geef gevonden publicaties als lijst in het veld 'stukken' van je "
            "antwoordsjabloon, niet in je eigen tekst." + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bwb_id": {"type": "string", "description": "BWB-id van de regeling, bijvoorbeeld 'BWBR0004770'."},
                "artikel": {"type": "string", "description": "Het artikel, bijvoorbeeld '36' of '25.1'; alleen met "
                                                             "'bwb_id'."},
                "publicatie": {"type": "string", "enum": list(_BLADEN),
                               "description": "Alleen het Staatsblad of alleen de Staatscourant."},
                "woorden": {"type": "string", "description": "Woorden uit de titel, bijvoorbeeld 'Leidraad "
                                                             "Invordering'. Een verzamelwet (Belastingplan, Overige "
                                                             "fiscale maatregelen) noemt de wetten die ze wijzigt niet "
                                                             "in de titel: zoek die met 'bwb_id' of 'tekst'."},
                "tekst": {"type": "string", "description": "Waar de publicatie over gaat, gezocht in de hele tekst. Zet "
                                                           "een vaste term tussen dubbele aanhalingstekens; hoogstens "
                                                           "zes woorden."},
                "soort": {"type": "string", "description": "Het soort, bijvoorbeeld 'wet', 'amvb', 'klein koninklijk "
                                                           "besluit', 'beleidsregel', 'verbeterblad' of "
                                                           "'inwerkingtredingsbesluit'. Een besluit van een "
                                                           "bewindspersoon dat beleid wijzigt (zoals de Leidraad "
                                                           "Invordering) heet bij KOOP meestal 'ander besluit van "
                                                           "algemene strekking', geen 'beleidsregel': laat 'soort' dan "
                                                           "weg."},
                "orgaan": {"type": "string", "description": "Het ministerie, bijvoorbeeld 'Financiën'."},
                "dossier": {"type": "string", "description": "Het Kamerdossier van de wet, bijvoorbeeld '33755'."},
                "vanaf": {"type": "string", "description": "Vanaf deze datum: JJJJ-MM-DD, JJJJ-MM of JJJJ."},
                "tot": {"type": "string", "description": "Tot en met deze datum, in dezelfde vorm."},
                "jaar": {"type": "string", "description": "De jaargang van het blad, bijvoorbeeld '2010'."},
                "volgorde": {"type": "string", "enum": list(BEKENDMAKINGEN.volgordes),
                             "description": "relevantie (bij woorden of tekst), nieuwste of oudste (op de datum)."},
                "aantal": {"type": "integer", "description": f"Hoeveel publicaties per pagina, 1 tot {LIMIT}."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_bekendmaking",
        "description": (
            "De tekst van één bekendmaking, per alinea in documentvolgorde, met de kop erboven (het artikel, het lid of "
            "het wijzigingsonderdeel, zoals 'Artikel I – Wijziging › A'). Gebruik het id uit zoek_bekendmakingen of uit "
            "geldigheid. Met 'artikel' alleen de wijzigingsonderdelen die dat artikel wijzigen (\"In artikel 1.1.5 "
            "worden …\"): zo lees je wat een wijzigingsbesluit aan één bepaling veranderde. Met 'regeling' alleen de "
            "artikelen die die regeling wijzigen: zo lees je wat een verzamelwet aan één wet veranderde, zonder haar door "
            "te bladeren." + _UITLEG + " Citeer letterlijk uit 'tekst'. Op de eerste pagina van een lange publicatie "
            "staat 'inhoud': per kop de offset, en bij een artikel zijn korte aanhef ('begint'); daaruit lees je welke "
            "regelingen een verzamelwet wijzigt.\n"
            "GEEFT TERUG: het stuk (id, label, publicatie, soort, titel, datum, ondertekend, jaar, nummer, orgaan, reeks, "
            "link, bron_hash, de stand bij KOOP en 'versies': de andere versies met hetzelfde nummer, zoals een herdruk, een "
            "tweede versie of een verbeterblad, met id, label en datum) en per alinea nr, kop en tekst (de kop alleen waar hij verandert). "
            "Noem de datum en het soort uit 'stuk', niet uit de tekst. Een voetnoot is een eigen rij na zijn alinea; een "
            "tabel is één rij met 'openen' (haal hem op met tabel=<nr>). Illustraties en ondertekeningen staan er niet "
            "in; de telling staat in 'overgeslagen'. Staat er gevalideerd: false, dan kon de nieuwste versie niet "
            "worden gecontroleerd." + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Het id, bijvoorbeeld 'stb-2010-176' of 'stcrt-2026-37344'."},
                "artikel": {"type": "string", "description": "Alleen de wijzigingsonderdelen die dit artikel wijzigen, "
                                                             "bijvoorbeeld '1.1.5' of '25'."},
                "regeling": {"type": "string", "description": "Alleen de artikelen van een wijzigingswet of verzamelwet "
                                                              "die deze regeling wijzigen (hun aanhef noemt haar: \"De "
                                                              "Invorderingswet 1990 wordt als volgt gewijzigd:\"), "
                                                              "bijvoorbeeld 'Invorderingswet 1990'. Samen met 'artikel' "
                                                              "kan ook."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
                "tabel": {"type": "integer", "description": "Het nr van een rij met soort 'tabel': dan de tabel zelf."},
                "inhoud": INHOUD_ARG,
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
]


# --- metadata ------------------------------------------------------------------------------------------------------

def label_van(rec: Any, vp: Any) -> str:
    """"Stb. 2010, 176" uit blad, jaargang en nummer van KOOP; zonder die velden het label van het id."""
    blad, jaar, nr = getattr(rec, "publicatienaam", ""), getattr(rec, "jaargang", ""), getattr(rec, "publicatienummer", "")
    if blad in _BLADEN and jaar and nr and vp.id.split("-")[1:3] == [jaar, nr]:
        afk = "Stb." if blad == "Staatsblad" else "Stcrt."
        versie = (getattr(rec, "versie", "") or "").strip()
        # Een kale versie ("n1") is "versie n1", zoals het label uit het id; "Herdruk" en "Verbeterblad n1" zeggen het zelf.
        versie = f"versie {versie}" if re.fullmatch(r"n\d+", versie) else versie
        return f"{afk} {jaar}, {nr}" + (f" ({versie.lower()})" if versie else "")
    return vp.label


def metadata(rec: Any, vp: Any) -> dict[str, Any]:
    """De metadata van een publicatie in de vaste sleutels (`bronmodel.connectors.METADATA_SLEUTELS`), uit het record
    van KOOP. De publicatiedatum alleen als die afwijkt; `leesbaar` alleen als het niet kan."""
    datum_, gepubliceerd = rec.datum or "", getattr(rec, "gepubliceerd", "") or ""
    return compact({
        "label": label_van(rec, vp), "publicatie": getattr(rec, "publicatienaam", ""), "soort": getattr(rec, "type", ""),
        "titel": rec.titel, "datum": datum_, "gepubliceerd": gepubliceerd if gepubliceerd != datum_ else "",
        "ondertekend": getattr(rec, "ondertekend", ""), "jaar": getattr(rec, "jaargang", ""),
        "nummer": getattr(rec, "publicatienummer", ""), "orgaan": getattr(rec, "kamer", ""),
        "reeks": list(getattr(rec, "behandeld_dossiers", ()) or ()), "samenvatting": getattr(rec, "samenvatting", ""),
        "versie": getattr(rec, "versie", ""),
        **({"leesbaar": False} if getattr(rec, "xml_url", "x") == "" else {})})


def _vp(ident: str) -> Any:
    vp = externe_vindplaats((ident or "").strip())
    return vp if vp is not None and vp.brontype == "bekendmaking" and vp.id.startswith(BEKENDMAKINGEN.id_prefixen) else None


def _rij(rec: Any, bij: dict[str, str] | None = None) -> dict[str, Any] | None:
    vp = _vp(rec.id)
    if vp is None or not binnen_bereik(rec):
        return None
    return compact({"id": vp.id, **metadata(rec, vp), "link": vp.uri, "wetsverwijzing": (bij or {}).get(vp.id, "")})


# --- zoeken bij een bepaling (de graaf) ----------------------------------------------------------------------------

def _q_bij_artikel(bwb_id: str, artikel: str) -> str:
    """De publicaties die de BWB bij een bepaling noemt. Bij een lid of onderdeel staan ze op het artikel erboven (de
    "drager", zoals in `queries.geldigheid`); een eigen waarde van het tekstdeel gaat voor."""
    return queries.PREFIXES + f"""SELECT ?waarde ?rol (MAX(?inw) AS ?inwerking) (COUNT(DISTINCT ?node) AS ?aantal) WHERE {{
  {queries.node_patroon(bwb_id, artikel)}
  OPTIONAL {{ ?artikel (bwb:heeftLid|bwb:heeftOnderdeel)+ ?node . ?artikel a bwb:Artikel . }}
  BIND(COALESCE(?artikel, ?node) AS ?drager)
  VALUES (?p ?rol) {{ (bwb:bron "wijziging") (bwb:inwerkingtredingsbron "inwerkingtreding") }}
  {{ ?node ?p ?waarde }} UNION {{ FILTER NOT EXISTS {{ ?node ?p ?eigen }} ?drager ?p ?waarde }}
  OPTIONAL {{ ?node bwb:inwerking ?inwNode }}
  OPTIONAL {{ ?drager bwb:inwerking ?inwDrager }}
  BIND(COALESCE(?inwNode, ?inwDrager) AS ?inw)
}} GROUP BY ?waarde ?rol LIMIT 50"""


def _q_bij_regeling(bwb_id: str) -> str:
    """De publicaties die de BWB bij de tekstdelen van een regeling noemt, met hoeveel tekstdelen elk."""
    iri = queries.regeling_iri(bwb_id)
    return queries.PREFIXES + f"""SELECT ?waarde ?rol (MAX(?inw) AS ?inwerking) (COUNT(DISTINCT ?node) AS ?aantal) WHERE {{
  VALUES (?p ?rol) {{ (bwb:bron "wijziging") (bwb:inwerkingtredingsbron "inwerkingtreding") }}
  ?node ?p ?waarde . FILTER(STRSTARTS(STR(?node), "{iri}:"))
  OPTIONAL {{ ?node bwb:inwerking ?inw }}
}} GROUP BY ?waarde ?rol ORDER BY DESC(?inwerking) ?waarde LIMIT {MAX_BIJ_REGELING + 1}"""


def _koppelingen(graph: Any, bwb_id: str, artikel: str) -> list[dict[str, Any]]:
    """Per publicatie (id) wat de BWB erover zegt: de koppelingen, de laatste inwerkingsdatum en hoeveel bepalingen."""
    rijen = parse_select(graph.sparql(_q_bij_artikel(bwb_id, artikel) if artikel else _q_bij_regeling(bwb_id)))
    per_id: dict[str, dict[str, Any]] = {}
    for r in rijen:
        ident = koop_id_uit_bron(r.get("waarde", ""))
        if ident is None:
            continue
        k = per_id.setdefault(ident, {"id": ident, "koppeling": [], "inwerking": "", "bepalingen": 0})
        if (rol := KOPPELING.get(r.get("rol", ""))) and rol not in k["koppeling"]:
            k["koppeling"].append(rol)
        k["inwerking"] = max(k["inwerking"], (r.get("inwerking") or "")[:10])
        k["bepalingen"] = max(k["bepalingen"], int(r.get("aantal") or 0))
    return list(per_id.values())


def _wetsverwijzing(k: dict[str, Any], bepaling: str | None) -> str:
    """"laatste wijziging en inwerkingtreding van artikel 36 van BWBR0004770", of bij een regeling "laatste wijziging
    van 12 bepalingen"."""
    rol = " en ".join(k["koppeling"]) or "genoemd"
    if bepaling:
        return f"{rol} van {bepaling}"
    n = k["bepalingen"]
    return f"{rol} van {n} {'bepaling' if n == 1 else 'bepalingen'}"


def _q_regelingen_bij(bronnen: list[str]) -> str:
    """Bij welke regelingen de BWB deze publicaties noemt (in de vorm "Stb.2009-610"), met hoeveel tekstdelen."""
    waarden = " ".join(queries._lit(b) for b in bronnen)
    return queries.PREFIXES + f"""SELECT ?waarde ?rol ?bwb (SAMPLE(?ct) AS ?titel) (COUNT(DISTINCT ?node) AS ?aantal) WHERE {{
  VALUES ?waarde {{ {waarden} }}
  VALUES (?p ?rol) {{ (bwb:bron "wijziging") (bwb:inwerkingtredingsbron "inwerkingtreding") }}
  ?node ?p ?waarde . FILTER(STRSTARTS(STR(?node), "{queries.NS}"))
  BIND(REPLACE(STR(?node), "^{queries.NS}(BWB[RV][0-9]+).*$", "$1") AS ?bwb)
  OPTIONAL {{ ?reg a bwb:Regeling ; bwb:bwbId ?bwb ; bwb:citeertitel ?ct }}
}} GROUP BY ?waarde ?rol ?bwb ORDER BY ?waarde ?rol ?bwb LIMIT 200"""


def regelingen_bij(graph: Any, ids: list[str]) -> dict[str, str]:
    """Per publicatie wat ze volgens de BWB aan de regelingen in de graaf doet: "wijzigt Invorderingswet 1990 (3
    bepalingen)", "inwerkingtreding van …". Alleen de toestand die Lex leest; zonder graaf of bij een storing leeg
    (de metadata van KOOP blijft dan staan, alleen deze regel ontbreekt)."""
    bronnen = {b: i for i in ids if (b := bwb_bron_van(i))}
    if graph is None or not bronnen:
        return {}
    try:
        rijen = parse_select(graph.sparql(_q_regelingen_bij(list(bronnen))))
    except Exception:  # noqa: BLE001 – een haperende graaf kost alleen deze regel
        return {}
    delen: dict[str, list[str]] = {}
    for r in rijen:
        ident = bronnen.get(r.get("waarde", ""))
        if ident is None:
            continue
        n = int(r.get("aantal") or 0)
        naam = r.get("titel") or r.get("bwb", "")
        wat = "wijzigt" if r.get("rol") == "wijziging" else "inwerkingtreding van"
        delen.setdefault(ident, []).append(f"{wat} {naam} ({n} {'bepaling' if n == 1 else 'bepalingen'})")
    return {i: "; ".join(d) for i, d in delen.items()}


class _MetRegelingen:
    """De bron, met per opgehaalde pagina de koppeling naar de regelingen uit de graaf (één query per pagina)."""

    def __init__(self, bron: BekendmakingBron, graph: Any) -> None:
        self._bron, self._graph, self.bij = bron, graph, {}

    def zoek(self, cql: str, *, start: int = 1, maximum: int = 50) -> tuple[int, list[Any]]:
        totaal, records = self._bron.zoek(cql, start=start, maximum=maximum)
        self.bij = regelingen_bij(self._graph, [r.id for r in records])
        return totaal, records


def _records(bron: BekendmakingBron, ids: list[str]) -> dict[str, Any]:
    """De records van KOOP voor deze ids, in vragen van hoogstens `_PER_VRAAG`."""
    uit: dict[str, Any] = {}
    for i in range(0, len(ids), _PER_VRAAG):
        deel = ids[i:i + _PER_VRAAG]
        _, records = bron.zoek(f"{_BASIS} AND ({' OR '.join(f'dt.identifier=={x}' for x in deel)})",
                               maximum=len(deel))
        uit.update({r.id: r for r in records if r.id in deel})
    return uit


def _past(rij: dict[str, Any], na: dict[str, str]) -> bool:
    """Valt een rij bij een bepaling binnen blad, soort, jaargang en periode (op de datum van KOOP of de inwerking)?"""
    datum_ = rij.get("datum") or rij.get("inwerking") or ""
    return ((not na.get("publicatie") or rij.get("publicatie") == na["publicatie"])
            and (not na.get("soort") or na["soort"].lower()[:12] in (rij.get("soort", "") + " " + rij.get("titel", "")).lower())
            and (not na.get("jaar") or rij.get("jaar") == na["jaar"])
            and (not na.get("vanaf") or datum_ >= na["vanaf"]) and (not na.get("tot") or datum_[:10] <= na["tot"]))


def _bij_bepaling(bron: BekendmakingBron, graph: Any, bwb_id: str, artikel: str, args: dict[str, Any], offset: int,
                  volgorde: str, na: dict[str, str] | None = None) -> str:
    if graph is None:
        return fout("graaf_onbereikbaar", "Zonder de kennisgraaf weet ik niet welke publicaties bij deze bepaling horen. "
                    "Zoek op woorden, bijvoorbeeld {\"woorden\": \"Invorderingswet 1990\"}.")
    koppelingen = _koppelingen(graph, bwb_id, artikel)
    wat = f"artikel {artikel} van {bwb_id}" if artikel else bwb_id
    if not koppelingen:
        return per_eenheid([], tool="zoek_bekendmakingen", args=args, offset=0,
                           toelichting=f"De BWB noemt bij {wat} geen publicatie in het Staatsblad of de Staatscourant.")
    meer = len(koppelingen) > MAX_BIJ_REGELING
    koppelingen = koppelingen[:MAX_BIJ_REGELING]
    records = _records(bron, [k["id"] for k in koppelingen])
    rijen: list[dict[str, Any]] = []
    for k in koppelingen:
        vp = _vp(k["id"])
        if vp is None:
            continue
        rec = records.get(k["id"])
        meta = metadata(rec, vp) if rec is not None else {"label": vp.label, "leesbaar": False}
        rijen.append(compact({"id": vp.id, **meta, "link": vp.uri,
                              "wetsverwijzing": _wetsverwijzing(k, wat if artikel else None),
                              "inwerking": k["inwerking"]}))
    if na:
        rijen = [r for r in rijen if _past(r, na)]
    if volgorde in {"nieuwste", "oudste"} or not artikel:
        rijen.sort(key=lambda r: (r.get("datum") or r.get("inwerking") or "", r["id"]), reverse=volgorde != "oudste")
    elif artikel:
        rijen.sort(key=lambda r: (not r.get("wetsverwijzing", "").startswith("laatste wijziging"), r["id"]))
    onbekend = [r["id"] for r in rijen if r["id"] not in records]
    toelichting = (f"Volgens de BWB, voor de toestand die Lex leest: de publicatie die de huidige tekst van {wat} gaf en "
                   "het besluit waarmee die in werking trad. Eerdere wijzigingen staan in eerdere toestanden en zijn "
                   "hier niet te zien.")
    if artikel:
        # Ronde 4, B24: de BWB legt de laatste wijziging bij het artikel vast, ook als die alleen één lid raakte, en het
        # model schreef het hele artikel aan die wet toe.
        toelichting += (f" Welk deel van {wat} de wijziging raakte, zegt de BWB hier niet; schrijf het hele artikel er "
                        "niet aan toe. Lees het met get_bekendmaking en het argument artikel: dan staan alleen de "
                        "wijzigingsopdrachten voor dit artikel er.")
    if onbekend:
        toelichting += f" Niet gevonden bij KOOP: {', '.join(onbekend)}."
    if meer:
        toelichting += f" De regeling noemt meer dan {MAX_BIJ_REGELING} publicaties; zoek per artikel."
    if not artikel:
        toelichting += (" Een wijziging die bij geen bepaling meer de laatste is, staat hier niet: zoek daarvoor ook op de "
                        "citeertitel in de titel, bijvoorbeeld {\"woorden\": \"Invorderingswet 1990\", \"vanaf\": \"2024\"}.")
    return per_eenheid(rijen, tool="zoek_bekendmakingen", args=args, offset=offset, toelichting=toelichting,
                       extra={"totaal": len(rijen), "zoekvraag": zoekvraag(args, volgorde or "koppeling"),
                              **({"volledig_bij_koop": False} if onbekend else {})})


# --- zoeken bij KOOP -----------------------------------------------------------------------------------------------

def _woorden_cql(index: str, waarde: str) -> str:
    woorden = list(dict.fromkeys(w.lower() for w in re.findall(r"[0-9A-Za-zÀ-ÿ]{2,}", waarde)))[:MAX_WOORDEN]
    if not woorden:
        raise ValueError(index)
    return f' AND {index} all "{" ".join(woorden)}"'


def _zoek(bron: BekendmakingBron, graph: Any, a: dict[str, Any]) -> str:
    for veld in ("woorden", "dossier", "tekst"):
        if (vp := _vp(a.get(veld) or "")) is not None:
            return fout("is_een_id", f"'{vp.id}' is het id van één publicatie: lees haar met "
                        f"get_bekendmaking(id='{vp.id}').")
    w = {k: str(a.get(k) or "").strip() for k in ("bwb_id", "artikel", "publicatie", "woorden", "tekst", "soort",
                                                   "orgaan", "dossier", "vanaf", "tot", "jaar", "volgorde")}
    offset = max(int(a.get("offset") or 0), 0)
    if w["artikel"] and not w["bwb_id"]:
        return fout("ongeldige_argumenten", "een artikel hoort bij een regeling, bijvoorbeeld "
                    "{\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\"}.")
    if w["bwb_id"] and not _BWB_RE.fullmatch(w["bwb_id"]):
        return fout("ongeldige_argumenten", f"'{w['bwb_id']}' is geen BWB-id, bijvoorbeeld {{\"bwb_id\": \"BWBR0004770\"}}.")
    if w["artikel"] and not _ARTIKEL_RE.fullmatch(w["artikel"]):
        return fout("ongeldige_argumenten", "geef het nummer van het artikel, bijvoorbeeld {\"artikel\": \"36\"}.")
    if w["publicatie"] and w["publicatie"] not in _BLADEN:
        return fout("ongeldige_argumenten", "kies 'Staatsblad' of 'Staatscourant', bijvoorbeeld "
                    "{\"publicatie\": \"Staatscourant\"}.")
    if w["dossier"]:
        w["dossier"] = w["dossier"].upper().replace(" ", "")
        if not _DOSSIER_RE.fullmatch(w["dossier"]):
            return fout("ongeldig_dossier", f"'{w['dossier']}' is geen Kamerdossier, bijvoorbeeld {{\"dossier\": \"33755\"}}.")
    if w["jaar"] and not _JAAR_RE.fullmatch(w["jaar"]):
        return fout("ongeldige_datum", "een jaargang is een jaartal, bijvoorbeeld {\"jaar\": \"2010\"}.")
    try:
        vanaf = datum(w["vanaf"], eind=False) if w["vanaf"] else ""
        tot = datum(w["tot"], eind=True) if w["tot"] else ""
    except ValueError:
        return fout("ongeldige_datum", "geef een datum als JJJJ-MM-DD, JJJJ-MM of JJJJ, bijvoorbeeld "
                    "{\"vanaf\": \"2024\", \"tot\": \"2024-06-30\"}.")
    if vanaf and tot and vanaf > tot:
        return fout("ongeldige_datum", "'vanaf' ligt na 'tot'; bijvoorbeeld {\"vanaf\": \"2023\", \"tot\": \"2024\"}.")
    volgorde = w["volgorde"]
    if volgorde and volgorde not in BEKENDMAKINGEN.volgordes:
        return fout("ongeldige_volgorde", "kies relevantie, nieuwste of oudste, bijvoorbeeld {\"volgorde\": \"nieuwste\"}.")
    aantal = a.get("aantal")
    if aantal is not None and (not isinstance(aantal, int) or isinstance(aantal, bool) or not 1 <= aantal <= LIMIT):
        return fout("ongeldig_aantal", f"'aantal' is een getal van 1 tot {LIMIT}, bijvoorbeeld {{\"aantal\": 10}}.")
    if w["tekst"] and not 0 < tekst_woorden(w["tekst"]) <= MAX_WOORDEN:
        return fout("ongeldige_tekst", f"geef één tot {MAX_WOORDEN} woorden van minstens drie letters, bijvoorbeeld "
                    "{\"tekst\": \"leidraad invordering\"}.")
    filters = {k: w[k] for k in ("publicatie", "woorden", "tekst", "soort", "orgaan", "dossier", "jaar")}
    filters.update(vanaf=vanaf, tot=tot)
    if w["bwb_id"]:
        if any(filters[k] for k in ("woorden", "tekst", "orgaan", "dossier")):
            return fout("ongeldige_argumenten", "bij een bepaling filtert alleen op blad, soort, jaar en periode; zoek "
                        "anders zonder bwb_id, bijvoorbeeld {\"bwb_id\": \"BWBR0004770\", \"vanaf\": \"2024\"}.")
        if volgorde == "relevantie":
            return fout("ongeldige_volgorde", "relevantie gaat over woorden; kies bij een bepaling nieuwste of oudste, "
                        "bijvoorbeeld {\"bwb_id\": \"BWBR0004770\", \"volgorde\": \"nieuwste\"}.")
        na = {k: filters[k] for k in ("publicatie", "soort", "jaar", "vanaf", "tot") if filters[k]}
        args = {k: v for k, v in (("bwb_id", w["bwb_id"]), ("artikel", w["artikel"]), *na.items(),
                                  ("volgorde", volgorde)) if v}
        return _bij_bepaling(bron, graph, w["bwb_id"], w["artikel"], args, offset, volgorde, na)
    if not any(filters.values()) and volgorde not in {"nieuwste", "oudste"}:
        return fout("ongeldige_argumenten", "geef een bepaling, woorden, een soort, een blad of een periode, of vraag de "
                    "nieuwste, bijvoorbeeld {\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\"} of "
                    "{\"publicatie\": \"Staatscourant\", \"woorden\": \"Leidraad Invordering\"}.")
    gezocht = bool(w["woorden"] or w["tekst"])
    volgorde = volgorde or ("relevantie" if gezocht else "nieuwste")
    if volgorde == "relevantie" and not gezocht:
        return fout("ongeldige_volgorde", "relevantie gaat over woorden: geef 'woorden' of 'tekst', of kies een datum, "
                    "bijvoorbeeld {\"volgorde\": \"nieuwste\"}.")
    args = {**{k: v for k, v in filters.items() if v}, **({"volgorde": a["volgorde"]} if a.get("volgorde") else {}),
            **({"aantal": aantal} if aantal is not None else {})}
    try:
        cql = _blad_cql(w["publicatie"], gericht=bool(w["woorden"] or w["tekst"] or w["dossier"]))
        cql += (" AND " + cql_woorden(w["woorden"])) if w["woorden"] else ""
        cql += tekst_cql(w["tekst"]) if w["tekst"] else ""
        titelsoort = next((t for k, t in _SOORT_IN_TITEL.items() if k[:12] in w["soort"].lower()), "")
        cql += (_woorden_cql("dt.title", titelsoort) if titelsoort else _woorden_cql("dt.type", w["soort"])
                if w["soort"] else "")
        cql += _woorden_cql("dt.creator", w["orgaan"]) if w["orgaan"] else ""
    except ValueError:
        return fout("ongeldige_argumenten", "geef woorden van minstens drie letters, bijvoorbeeld "
                    "{\"woorden\": \"Leidraad Invordering\"}.")
    cql += f' AND w.behandeldDossier=="{w["dossier"]}"' if w["dossier"] else ""
    cql += f' AND w.jaargang=="{w["jaar"]}"' if w["jaar"] else ""
    cql += (f" AND dt.date>={vanaf}" if vanaf else "") + (f" AND dt.date<={tot}" if tot else "")
    verrijkt = _MetRegelingen(bron, graph)
    return per_record(verrijkt, cql + OP_VOLGORDE.get(volgorde, ""), args, offset, tool="zoek_bekendmakingen",
                      rij=lambda rec: _rij(rec, verrijkt.bij),
                      maximum=aantal or LIMIT, extra={"volgorde": volgorde, "zoekvraag": zoekvraag(args, volgorde)},
                      leeg="Geen bekendmakingen die aan de zoekvraag voldoen.")


# --- lezen ---------------------------------------------------------------------------------------------------------

#: Wat een gefilterde lezing zegt over de rest van de publicatie (`stuk_tekst.tekstpagina`, `publicatie`).
_REST = ("'inhoud_publicatie' noemt de delen van de hele publicatie met hun offset (de inwerkingtreding, de toelichting): "
         "lees daar gericht verder met id en offset, zonder artikel of regeling.")


def _opsomming(delen: list[str]) -> str:
    return delen[0] if len(delen) == 1 else ", ".join(delen[:-1]) + " en " + delen[-1]


def _andere_versies(bron: Any, ident: str) -> list[dict[str, str]]:
    """De andere versies van een publicatie (`SruBekendmakingen.versies`): id, label en datum, oudste eerst. Een bron
    zonder die methode (een nep) of een storing geeft niets; de lezing zelf gaat dan gewoon door, want de versies zijn
    een aanvulling op het stuk."""
    if not callable(getattr(bron, "versies", None)):
        return []
    try:
        records = bron.versies(ident)
    except RuntimeError:  # KoopFout: een storing kost alleen de versies
        logger.info("bekendmaking_versies_onbekend", extra={"categorie": "functioneel", "id": ident})
        return []
    uit = [compact({"id": r.id, "label": label_van(r, vp), "datum": r.datum or ""})
           for r in records if r.id != ident and (vp := _vp(r.id)) is not None]
    return sorted(uit, key=lambda v: (v.get("datum", ""), v["id"]))


def _noemt_artikel(tekst: str, artikel: str) -> bool:
    """Noemt de wijzigingsopdracht dit artikel ("In artikel 1.1.5 worden …", "Artikel 25 wordt als volgt gewijzigd",
    "In de artikelen 24 en 25 …")? Een langer nummer telt niet: 1.1.5 is niet 1.1.5b, 25 is niet 25a of 25.1."""
    nr = re.escape(artikel.rstrip("."))
    return bool(re.search(rf"\bartikel(?:en)?\s+(?:[0-9][0-9A-Za-z:.]*\s*(?:,|en|tot\s+en\s+met)\s*)*{nr}"
                          rf"(?![0-9A-Za-z]|\.[0-9A-Za-z])", tekst, re.IGNORECASE))


def _get(bron: BekendmakingBron, a: dict[str, Any], graph: Any = None) -> str:
    vp = _vp(a.get("id") or "")
    if vp is None:
        return fout("ongeldig_id", "geef het id van een bekendmaking, bijvoorbeeld 'stb-2010-176' of 'stcrt-2026-37344'")
    artikel = str(a.get("artikel") or "").strip()
    if artikel and not _ARTIKEL_RE.fullmatch(artikel):
        return fout("ongeldige_argumenten", "geef het nummer van het artikel, bijvoorbeeld {\"artikel\": \"1.1.5\"}; "
                    "een wet geef je als {\"regeling\": \"Invorderingswet 1990\"}.")
    regeling = " ".join(str(a.get("regeling") or "").split())
    doc = bron.document(vp.id)
    try:
        kop, rijen, overgeslagen, tabellen = lees(doc.xml, met_onderdeel=bool(artikel))
    except (ET.ParseError, ValueError) as exc:
        return fout("onleesbaar_document", f"{vp.id} kon niet worden gelezen: {exc}")
    echt = _vp(getattr(doc, "id", "") or vp.id) or vp
    rec = getattr(doc, "record", None)
    if rec is not None and not binnen_bereik(rec):
        return fout("buiten_bereik", f"{echt.id} is een {rec.type or 'publicatie'} in de Staatscourant: een aankondiging "
                    "die over personen of één geval kan gaan, geen regelgeving of beleid. Die lees ik niet; noem alleen "
                    f"de link {echt.uri}. Zoek regelgeving, bijvoorbeeld {{\"publicatie\": \"Staatscourant\", "
                    "\"soort\": \"beleidsregel\"}.")
    meta = {k: v for k, v in metadata(rec, echt).items() if k != "leesbaar"} if rec is not None else {"label": echt.label}
    stuk = compact({"id": echt.id, **meta, "titel": kop["documenttitel"] or meta.get("titel", ""), "link": echt.uri,
                    "wetsverwijzing": regelingen_bij(graph, [echt.id]).get(echt.id, ""),
                    "bron_hash": doc.hash, "gewijzigd": getattr(doc, "gewijzigd", ""),
                    "versie": getattr(doc, "versie", ""),
                    **({"gevalideerd": False} if getattr(doc, "gevalideerd", True) is False else {})})
    toelichting = (f"{vp.id} staat bij KOOP als {echt.id} ({stuk['label']}): noem en citeer dat id."
                   if echt.id != vp.id else "")
    offset = max(int(a.get("offset") or 0), 0)
    if offset == 0 and a.get("tabel") is None and (andere := _andere_versies(bron, echt.id)):
        stuk = {**stuk, "versies": andere}
        # In de toelichting, niet alleen in het veld: wie vroeg wat er in het stuk staat, las `stuk.versies` niet
        # (iteratie ronde 2, B12; in B25, waar naar de versies gevraagd werd, wel).
        toelichting = (toelichting + " " if toelichting else "") + (
            "Van deze publicatie bestaat ook " + _opsomming([f"{v['label']} ({v['datum']})" if v.get("datum")
                                                            else v["label"] for v in andere])
            + ": noem dat in je antwoord, met het id van de versie die je las.")
    if a.get("tabel") is not None:
        gevonden = tabellen.get(int(a["tabel"])) if str(a["tabel"]).lstrip("-").isdigit() else None
        if gevonden is None:
            return fout("ongeldige_tabel", f"{echt.id} heeft geen tabel met nr {a['tabel']}: geef het nr van een rij met "
                        f"soort 'tabel', bijvoorbeeld {{\"id\": \"{echt.id}\", \"tabel\": {next(iter(tabellen), 1)}}}.")
        tabelrijen, samen = gevonden
        return per_eenheid(tabelrijen, tool="get_bekendmaking", args={"id": echt.id, "tabel": int(a["tabel"])},
                           offset=offset, extra={"stuk": stuk, "totaal": len(tabelrijen),
                                                 **({"samengevoegd": samen} if samen else {})})
    if a.get("inhoud"):
        return inhoudpagina(rijen, tool="get_bekendmaking", args={"id": echt.id}, offset=offset, stuk=stuk)
    args: dict[str, Any] = {"id": echt.id}
    publicatie = rijen if (regeling or artikel) else None
    if regeling:
        # Per artikel van de wijzigingswet (het eerste deel van de kop) telt de eerste rij: de aanhef.
        aanhef: dict[str, str] = {}
        for r in rijen:
            aanhef.setdefault(str(r.get("kop") or "").split(" › ")[0], str(r.get("tekst") or ""))
        naam = re.compile(rf"(?<![0-9A-Za-zÀ-ÿ]){re.escape(regeling)}(?![0-9A-Za-zÀ-ÿ])", re.IGNORECASE)
        raak = {k for k, t in aanhef.items() if k and naam.search(t)}
        rijen = [r for r in rijen if str(r.get("kop") or "").split(" › ")[0] in raak]
        args["regeling"] = regeling
        toelichting = (toelichting + " " if toelichting else "") + (
            ("Alleen het artikel" if len(raak) == 1 else f"Alleen de {len(raak)} artikelen")
            + f" waarvan de aanhef {regeling} noemt; de rest staat er niet bij. {_REST}" if raak else
            f"Geen artikel van {echt.id} noemt {regeling} in zijn aanhef. Kijk in 'inhoud' van de hele publicatie, "
            f"bijvoorbeeld {{\"id\": \"{echt.id}\"}}.")
    if artikel:
        # Per wijzigingsonderdeel telt de eerste rij: daar staat de opdracht ("In artikel 1.1.5 worden …").
        eerste: dict[str, str] = {}
        for r in rijen:
            if (o := r.get("onderdeel")):
                eerste.setdefault(o, r.get("tekst", ""))
        raak = {o for o, t in eerste.items() if _noemt_artikel(t, artikel)}
        rijen = [{k: v for k, v in r.items() if k != "onderdeel"} for r in rijen if r.get("onderdeel") in raak]
        args["artikel"] = artikel
        if not rijen:
            toelichting = (f"Geen wijzigingsonderdeel van {echt.id} noemt artikel {artikel} in zijn opdracht"
                           f"{'' if eerste else ' (de publicatie heeft geen wijzigingsonderdelen)'}. Lees de hele "
                           f"publicatie, bijvoorbeeld {{\"id\": \"{echt.id}\"}}.")
        else:
            toelichting = (toelichting + " " if toelichting else "") + (
                f"Alleen de {len(raak)} wijzigingsonderdeel{'en' if len(raak) != 1 else ''} die artikel {artikel} "
                f"noemen; de rest staat er niet bij. {_REST}")
    rijen = [{**r, "openen": {"tool": "get_bekendmaking", "args": {"id": echt.id, "tabel": r["nr"]}}}
             if r.get("soort") == "tabel" else r for r in rijen]
    return tekstpagina(rijen, tool="get_bekendmaking", args=args, offset=offset, stuk=stuk, publicatie=publicatie,
                       extra={"overgeslagen": overgeslagen} if overgeslagen else None,
                       toelichting=toelichting or ("" if rijen else "Deze publicatie heeft geen lopende tekst in de XML."))


#: De reden in het foutresultaat per code van de adapter (`KoopFout.code`).
FOUTREDEN = {"onbereikbaar": "bron_onbereikbaar", "geweigerd": "zoekvraag_geweigerd", "niet_gevonden": "niet_gevonden",
             "alleen_pdf": "alleen_pdf"}


def fout_van(exc: Any) -> str:
    """Het foutresultaat bij een `KoopFout`. Een publicatie die alleen als PDF bestaat, bestaat: het resultaat noemt
    haar metadata, zodat Lex datum en soort uit de code noemt in plaats van "bestaat mogelijk niet"."""
    code = getattr(exc, "code", "onbereikbaar")
    rec = getattr(exc, "record", None)
    if code == "alleen_pdf" and rec is not None and (vp := _vp(rec.id)) is not None:
        meta = metadata(rec, vp)
        wat = ", ".join(x for x in (meta.get("soort"), meta.get("datum")) if x)
        return fout("alleen_pdf", (
            f"{meta['label']} ({vp.id}{', ' + wat if wat else ''}) bestaat, maar staat bij KOOP alleen als PDF: de tekst "
            f"kan ik niet lezen. Zeg dat, met de datum en de link {vp.uri}, en citeer er niet uit."),
            stuk={"id": vp.id, **meta, "link": vp.uri})
    if code == "niet_gevonden":
        return fout("niet_gevonden", f"{exc}, ook niet op blad, jaargang en nummer. Controleer het id, of zoek de "
                    "publicatie met zoek_bekendmakingen, bijvoorbeeld {\"woorden\": \"Invorderingswet 1990\"}.")
    return fout(FOUTREDEN.get(code, "bron_onbereikbaar"), str(exc))


def dispatch_bekendmaking(name: str, args: dict[str, Any], bron: BekendmakingBron | None, graph: Any) -> str:
    if bron is None:
        return fout("connector_uit", "De bron Staatsblad en Staatscourant staat uit. Zeg dat, en antwoord niet uit eigen "
                    "kennis.")
    if name == "zoek_bekendmakingen":
        return _zoek(bron, graph, args)
    if name == "get_bekendmaking":
        return _get(bron, args, graph)
    raise KeyError(name)
