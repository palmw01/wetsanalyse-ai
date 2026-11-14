"""De bronconnector Kennisgroepstandpunten (plan-connector-kennisgroepen.md, stap 4).

Twee getypeerde tools, met het resultaatcontract van de graaftools:

- `zoek_standpunten`: de gepubliceerde standpunten van de kennisgroepen van de Belastingdienst, uit de index in de graaf
  (`bwb-import --kennisgroepen`): per wetsartikel, op woorden, kennisgroep, middel, rubriek, periode, status, of op een
  stuk dat ze noemen (een ECLI, een Kamerstuk, een ander standpunt);
- `get_standpunt`: de tekst van één standpunt, live bij de Belastingdienst, per alinea met de kop (Aanleiding, Vraag,
  Antwoord, Beschouwing).

**Beleid, geen wet.** Een standpunt bindt de inspecteur, niet de rechter of de belastingplichtige. Het onderbouwt nooit
wat de wet zegt; dat doet de opgehaalde bepaling. De vindplaats is het kenmerk (`kg:013:2026:4`, `bronmodel.extern`), de
rijen dragen hun tekst onder `id`, nooit onder `iri`/`uri`. **Standaard alleen geldende standpunten** (besluit V5): een
ingetrokken of vervallen standpunt alleen op verzoek (`status`), of als het bij naam gelezen wordt; dan zegt het stuk
het, met het standpunt dat het verving.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from bronmodel.connectors import KENNISGROEPEN
from bronmodel.extern import externe_vindplaats
from bronmodel.kennisgroepen import STATUSSEN

from ..adapters.kennisgroepen_bron import Gelezen, KennisgroepenBron, KennisgroepenFout, Zoekvraag
from ..graph.results import parse_select
from ..resultaat import compact, fout, pagina
from .stuk_tekst import INHOUD_ARG, inhoudpagina, tekstpagina
from .zoekfilters import datum as _datum

logger = logging.getLogger(__name__)

CONNECTOR = KENNISGROEPEN.naam
LIMIT = 25
STANDAARD = 10
MAX_WOORDEN = 6
MAX_NOEMT = 40

_CONTRACT = (
    "\nResultaatcontract: {status, volledig, aantal, totaal?, vervolg?, resultaten}. Is `volledig` false, roep "
    "dan `vervolg` aan voor de rest."
)
_BELEID = (
    " Een kennisgroepstandpunt is beleid van de Belastingdienst, bindend voor de inspecteur: geen wet en geen "
    "rechtspraak. Noem eerst de bepaling uit de wet, dan het standpunt met zijn kenmerk en datum, en zeg dat het beleid is. "
    "Een ingetrokken of vervallen standpunt is geen geldend beleid. Of iemand zich op een standpunt kan beroepen, "
    "beoordeel je niet."
)

KENNISGROEP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "zoek_standpunten",
        "description": (
            "Kennisgroepstandpunten van de Belastingdienst zoeken (de gepubliceerde, vanaf 2022). MET 'bwb_id' en "
            "'artikel' (en eventueel 'lid'): de standpunten die dat artikel noemen, via een link van de Belastingdienst of "
            "herkend in de tekst (artikel plus regelingnaam); 'wetsverwijzing' zegt welke. Ook op 'woorden' (in onderwerp "
            "en tekst, alle woorden), 'kennisgroep' (bijvoorbeeld 'Invordering' of 'Formeel Recht'), 'middel' "
            "(bijvoorbeeld 'loonheffingen' of 'omzetbelasting'), 'rubriek', een periode ('vanaf', 'tot'), en 'noemt': een "
            "ECLI, Kamerstuk, bekendmaking of ander standpunt dat het standpunt noemt. Standaard alleen geldende "
            "standpunten; 'status' 'ingetrokken', 'vervallen' of 'alle' als de vraag daarom vraagt. Volgorde 'nieuwste' "
            "(standaard) of 'oudste'. Niet elk standpunt wordt gepubliceerd: geen treffer betekent niet dat er geen "
            "standpunt is." + _BELEID + "\n"
            "GEEFT TERUG per standpunt: id (kg:…), label (het kenmerk), titel (het onderwerp), datum, status, orgaan "
            "(de kennisgroep), rechtsgebied (middel en belastingsoort), reeks (rubrieken), link, vervangt en "
            "vervangen_door, en met een artikel wetsverwijzing en tekststand ('eerdere tekst' als het artikel sinds het "
            "standpunt is gewijzigd). Daarnaast 'zoekvraag', 'totaal', 'per_status' (ook de ingetrokken en vervallen, "
            "die standaard niet getoond worden), 'per_belastingsoort', 'per_middel' en 'per_kennisgroep' (de verdeling van "
            "het totaal, geteld in de index; belastingsoort en middel zijn twee indelingen van de site, voeg ze niet samen: "
            "gebruik die voor een telvraag, en blader niet door de pagina's) en met een artikel "
            "'koppelingen' (via link, via tekst). Lees een standpunt met get_standpunt voor je zegt wat het "
            "inhoudt." + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bwb_id": {"type": "string", "description": "BWB-id van de regeling, bijvoorbeeld 'BWBR0004770'."},
                "artikel": {"type": "string", "description": "Het artikelnummer, bijvoorbeeld '36' of '3.111'."},
                "lid": {"type": "string", "description": "Het lid als getal, bijvoorbeeld '2'; een standpunt dat het "
                                                         "hele artikel noemt, telt ook."},
                "woorden": {"type": "string", "description": f"Hoogstens {MAX_WOORDEN} woorden, allemaal in het "
                                                            "onderwerp of de tekst, bijvoorbeeld 'betalingsregeling'."},
                "kennisgroep": {"type": "string", "description": "Een deel van de naam van de kennisgroep, bijvoorbeeld "
                                                                 "'Invordering', 'Formeel Recht' of 'IB-NW'."},
                "middel": {"type": "string", "description": "Het belastingmiddel of de belastingsoort, bijvoorbeeld "
                                                            "'loonheffingen' of 'Vennootschapsbelasting'."},
                "rubriek": {"type": "string", "description": "Een rubriek van de site, bijvoorbeeld 'Eigenwoningschuld'."},
                "noemt": {"type": "string", "description": "Een id dat het standpunt noemt: een ECLI, 'kst-…', "
                                                           "'stcrt-…' of een ander kenmerk 'KG:…'."},
                "vanaf": {"type": "string", "description": "Vanaf deze datum: JJJJ-MM-DD, JJJJ-MM of JJJJ."},
                "tot": {"type": "string", "description": "Tot en met deze datum, in dezelfde vorm."},
                "status": {"type": "string", "enum": [*STATUSSEN, "alle"],
                           "description": "Standaard 'geldend'; de andere alleen als de vraag erom vraagt."},
                "volgorde": {"type": "string", "enum": list(KENNISGROEPEN.volgordes),
                             "description": "nieuwste of oudste (op de datum van het standpunt)."},
                "aantal": {"type": "integer", "description": f"Hoeveel per pagina, 1 tot {LIMIT}."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_standpunt",
        "description": (
            "De tekst van één kennisgroepstandpunt, live bij de Belastingdienst, per alinea in documentvolgorde met de "
            "kop (Aanleiding, Vraag, Antwoord, Beschouwing, Voetnoten; 'Let op! Intrekking' als het een ouder standpunt "
            "intrekt). Gebruik het kenmerk uit zoek_standpunten of uit de vraag." + _BELEID +
            " Citeer letterlijk uit 'tekst'. Voor 'wat is het standpunt' volstaan Vraag en Antwoord.\n"
            "GEEFT TERUG: het stuk (id, label, titel, datum, gepubliceerd, vastgesteld, gewijzigd, status, orgaan, "
            "rechtsgebied, reeks, vervangt, vervangen_door, noemt, bijlagen, gebeurtenissen, link, bron_hash, en "
            "'tekststanden': per genoemd artikel in de kennisgraaf sinds wanneer de tekst van het ARTIKEL geldt en of het "
            "artikel gewijzigd is na dit standpunt; vergelijk zelf geen datums. Dat zegt niets over één lid: noemt de vraag "
            "een lid, zeg dan dat het artikel wijzigde en lees het lid op beide data (geldigheid met peildatum) voor je zegt "
            "dat het lid wijzigde) en per alinea nr, kop, "
            "soort (alinea, voetnoot, tabel, tabelrij) en tekst. Noem de datum en de status uit 'stuk'. Staat het "
            "kenmerk niet bij de gepubliceerde standpunten maar trekt een ander het in, dan geeft de fout "
            "'vervangen_door'."
            + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Het kenmerk, bijvoorbeeld 'KG:013:2026:4' of 'kg:013:2026:4'."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
                "inhoud": INHOUD_ARG,
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
]


def _wetsverwijzing(a: dict[str, Any], herkomsten: str) -> str:
    plek = f"artikel {a['artikel']}" + (f", lid {a['lid']}" if a.get("lid") else "") if a.get("artikel") else "de regeling"
    soorten = set(filter(None, (herkomsten or "").split("|")))
    hoe = {"link": "een link van de Belastingdienst", "tekst": "in de tekst herkend"}
    return f"noemt {plek} ({' en '.join(hoe[s] for s in sorted(soorten) if s in hoe) or 'onbekend'})"


def _q_inwerking(bwb_id: str, artikel: str) -> str:
    return ("PREFIX bwb: <urn:bwb-ns:>\nSELECT ?inwerking WHERE { "
            f"<urn:bwb:{bwb_id}:artikel:{artikel}> bwb:inwerking ?inwerking }} LIMIT 1")


def _q_inwerkingen(paren: list[tuple[str, str]]) -> str:
    waarden = " ".join(f"<urn:bwb:{b}:artikel:{a}>" for b, a in paren)
    return ("PREFIX bwb: <urn:bwb-ns:>\nSELECT ?a ?inwerking WHERE { VALUES ?a { " + waarden + " } "
            "?a bwb:inwerking ?inwerking }")


_JCI_RE = re.compile(r"^jci1\.3:c:(BWB[RV]\d{7})(?:&[^&=]+=[^&]*)*?&artikel=([0-9A-Za-z.:]+)")


def tekststanden(graph: Any, noemt: list[str], datum: str) -> list[dict[str, str]]:
    """Per artikel dat het standpunt noemt en dat in de graaf staat: sinds wanneer de tekst geldt en of die tekst van na
    het standpunt is. Uit de code, zodat het model geen datums vergelijkt (meting 14 nov 2026, vraag 13: "1 oktober 2026
    ligt in de toekomst" op 14 november 2026)."""
    paren = list(dict.fromkeys(m.groups() for j in noemt if (m := _JCI_RE.match(j or ""))))[:MAX_NOEMT]
    if graph is None or not paren or not datum:
        return []
    try:
        rijen = parse_select(graph.sparql(_q_inwerkingen(paren)))
    except Exception:  # noqa: BLE001 - de stand is een extra, geen voorwaarde
        return []
    sinds = {str(r.get("a") or ""): str(r.get("inwerking") or "")[:10] for r in rijen if r.get("inwerking")}
    uit = []
    for bwb, artikel in paren:
        if not (vanaf := sinds.get(f"urn:bwb:{bwb}:artikel:{artikel}")):
            continue
        # De graaf kent de inwerking per artikel, niet per lid. Een artikel dat na het standpunt wijzigde, kan het lid dat
        # het standpunt noemt ongewijzigd laten (meting ronde 2, vraag 13: art. 25 Iw gewijzigd, lid 17 woordelijk gelijk).
        uit.append({"bwb_id": bwb, "artikel": artikel, "tekst_vanaf": vanaf, "niveau": "artikel",
                    "tekststand": ("het artikel is gewijzigd na dit standpunt; of het genoemde lid anders luidt, zegt dit "
                                   "niet" if vanaf > datum else "het artikel is ongewijzigd sinds dit standpunt")})
    return uit


def _inwerking(graph: Any, bwb_id: str, artikel: str) -> str:
    """Sinds wanneer de tekst van het artikel in de graaf geldt; leeg als de graaf het niet weet."""
    if graph is None or not re.fullmatch(r"[0-9A-Za-z.:]+", artikel or "") or not re.fullmatch(r"BWB[RV]\d+", bwb_id):
        return ""
    try:
        rij = next(iter(parse_select(graph.sparql(_q_inwerking(bwb_id, artikel)))), {})
    except Exception:  # noqa: BLE001 - de stand is een extra, geen voorwaarde
        return ""
    return str(rij.get("inwerking") or "")[:10]


def rij_van(r: dict[str, str], a: dict[str, Any], inwerking: str) -> dict[str, Any]:
    lijst = lambda k: [w for w in (r.get(k) or "").split("|") if w]  # noqa: E731
    rij = compact({
        "id": r.get("id", ""), "label": r.get("kenmerk", ""), "titel": r.get("titel", ""), "datum": r.get("datum", ""),
        "status": r.get("status", ""), "orgaan": r.get("kennisgroep", ""),
        "rechtsgebied": "; ".join(lijst("middelen")), "reeks": lijst("rubrieken"), "link": r.get("link", ""),
        "vervangt": lijst("vervangt"), "vervangen_door": lijst("vervangen_door"),
    })
    if a.get("bwb_id"):
        rij["wetsverwijzing"] = _wetsverwijzing(a, r.get("herkomsten", ""))
        if inwerking and rij.get("datum"):
            rij["tekststand"] = "eerdere tekst" if inwerking > rij["datum"] else "huidige tekst"
    return rij


def _zoekvraag_tekst(v: Zoekvraag) -> dict[str, Any]:
    return compact({"bwb_id": v.bwb_id, "artikel": v.artikel, "lid": v.lid, "woorden": " ".join(v.woorden),
                    "kennisgroep": v.kennisgroep, "middel": v.middel, "rubriek": v.rubriek, "noemt": v.noemt,
                    "vanaf": v.vanaf, "tot": v.tot, "status": v.status, "volgorde": v.volgorde})


def _vraag(a: dict[str, Any]) -> Zoekvraag | str:
    bwb = str(a.get("bwb_id") or "").strip().upper()
    artikel = str(a.get("artikel") or "").strip()
    lid = str(a.get("lid") or "").strip()
    if bwb and not re.fullmatch(r"BWB[RV]\d{7}", bwb):
        return fout("ongeldig_id", f"'{bwb}' is geen BWB-id; geef bijvoorbeeld {{\"bwb_id\": \"BWBR0004770\"}}")
    if (artikel or lid) and not bwb:
        return fout("ongeldige_argumenten", "een artikel hoort bij een regeling, bijvoorbeeld "
                    "{\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\"}")
    if lid and not artikel:
        return fout("ongeldige_argumenten", "een lid hoort bij een artikel, bijvoorbeeld {\"artikel\": \"36\", \"lid\": \"2\"}")
    woorden = tuple(w for w in re.split(r"\s+", str(a.get("woorden") or "").strip().lower()) if w)
    if len(woorden) > MAX_WOORDEN or any(len(w) < 3 for w in woorden):
        return fout("ongeldige_tekst", f"geef één tot {MAX_WOORDEN} woorden van minstens drie letters, bijvoorbeeld "
                    "{\"woorden\": \"betalingsregeling\"}")
    noemt = str(a.get("noemt") or "").strip()
    if noemt:
        vp = externe_vindplaats(noemt)
        if vp is None:
            return fout("ongeldig_id", f"'{noemt}' is geen ECLI, Kamerstuk, bekendmaking of kenmerk; bijvoorbeeld "
                        "{\"noemt\": \"ECLI:NL:HR:2013:64\"}")
        noemt = vp.id
    try:
        vanaf = _datum(str(a.get("vanaf") or ""), eind=False) if a.get("vanaf") else ""
        tot = _datum(str(a.get("tot") or ""), eind=True) if a.get("tot") else ""
    except (ValueError, TypeError):
        return fout("ongeldige_datum", "geef een datum als JJJJ-MM-DD, JJJJ-MM of JJJJ, bijvoorbeeld {\"vanaf\": \"2024\"}")
    status = str(a.get("status") or "geldend").strip().lower()
    if status not in (*STATUSSEN, "alle"):
        return fout("ongeldige_status", "kies geldend, ingetrokken, vervallen of alle, bijvoorbeeld {\"status\": \"alle\"}")
    volgorde = str(a.get("volgorde") or "nieuwste").strip().lower()
    if volgorde not in KENNISGROEPEN.volgordes:
        return fout("ongeldige_volgorde", "kies nieuwste of oudste, bijvoorbeeld {\"volgorde\": \"oudste\"}")
    v = Zoekvraag(bwb_id=bwb, artikel=artikel, lid=lid, woorden=woorden,
                  kennisgroep=str(a.get("kennisgroep") or "").strip(), middel=str(a.get("middel") or "").strip(),
                  rubriek=str(a.get("rubriek") or "").strip(), noemt=noemt, vanaf=vanaf, tot=tot, status=status,
                  volgorde=volgorde)
    if not any((v.bwb_id, v.woorden, v.kennisgroep, v.middel, v.rubriek, v.noemt, v.vanaf, v.tot)) and status == "geldend" \
            and not a.get("volgorde"):
        # Zonder filter: de nieuwste, zoals een lijstvraag ("de nieuwste standpunten").
        v.volgorde = "nieuwste"
    return v


def _zoek(bron: KennisgroepenBron, graph: Any, a: dict[str, Any]) -> str:
    v = _vraag(a)
    if isinstance(v, str):
        return v
    try:
        aantal = int(a.get("aantal") or STANDAARD)
        offset = max(int(a.get("offset") or 0), 0)
    except (TypeError, ValueError):
        return fout("ongeldig_aantal", f"'aantal' is een getal van 1 tot {LIMIT}, bijvoorbeeld {{\"aantal\": 10}}.")
    if not 1 <= aantal <= LIMIT:
        return fout("ongeldig_aantal", f"'aantal' is een getal van 1 tot {LIMIT}, bijvoorbeeld {{\"aantal\": 10}}.")
    gevonden = bron.zoek(graph, v, offset=offset, limit=aantal + 1)
    inwerking = _inwerking(graph, v.bwb_id, v.artikel) if v.artikel else ""
    rijen = [rij_van(r, a, inwerking) for r in gevonden.rijen]
    args = {k: a[k] for k in ("bwb_id", "artikel", "lid", "woorden", "kennisgroep", "middel", "rubriek", "noemt", "vanaf",
                              "tot", "status", "volgorde") if a.get(k)} | {"aantal": aantal}
    verborgen = sum(n for s, n in gevonden.per_status.items() if s != v.status) if v.status != "alle" else 0
    # Wat onder de lijst hoort te staan, in het blok zelf (`kanttekening`, zoals de andere connectors), niet alleen in de
    # toelichting voor het model: een lijst zonder model (de lijstroute) toonde anders niet dat er een ingetrokken
    # standpunt verborgen was, en niet hoe de koppeling met het artikel tot stand kwam (meting 14 nov 2026, vraag 2).
    kant = []
    if verborgen and v.status == "geldend":
        kant.append(f"Daarnaast {'is er' if verborgen == 1 else 'zijn er'} {verborgen} ingetrokken of vervallen "
                    f"{'standpunt' if verborgen == 1 else 'standpunten'} bij deze zoekvraag; "
                    f"{'dat is' if verborgen == 1 else 'die zijn'} geen geldend beleid.")
    if v.bwb_id and gevonden.totaal:
        hoe = {"link": "via een link van de Belastingdienst", "tekst": "in de tekst herkend"}
        delen = [f"{n} {hoe[h]}" for h, n in sorted(gevonden.per_herkomst.items()) if h in hoe]
        kant.append("Gekoppeld aan de bepaling" + (f": {', '.join(delen)}" if delen else "") + ". Dit zijn ten minste "
                    "de standpunten die de bepaling bij naam noemen; een standpunt dat haar anders aanduidt, ontbreekt.")
    if not gevonden.totaal:
        kant.append("Niet elk standpunt wordt gepubliceerd.")
    extra = compact({"zoekvraag": _zoekvraag_tekst(v), "totaal": gevonden.totaal, "per_status": gevonden.per_status,
                     "koppelingen": gevonden.per_herkomst, "per_belastingsoort": gevonden.per_belastingsoort,
                     "per_kennisgroep": gevonden.per_kennisgroep, "per_middel": gevonden.per_middel,
                     "kanttekening": " ".join(kant)})
    toelichting = [] if gevonden.totaal else [
        "Geen gepubliceerd kennisgroepstandpunt bij deze zoekvraag; dat betekent niet dat er geen standpunt is."]
    if gevonden.totaal > len(rijen):
        toelichting.append("Een telling of verdeling staat in totaal, per_status, per_belastingsoort, per_middel en "
                           "per_kennisgroep: blader daarvoor niet door de pagina's, en tel de verdelingen niet bij elkaar op.")
    return pagina(rijen, tool="zoek_standpunten", args=args, limit=aantal, offset=offset, extra=extra,
                  toelichting=" ".join(toelichting))


def stuk_van(g: Gelezen, graph: Any = None) -> dict[str, Any]:
    s, m = g.standpunt, g.standpunt.metadata
    noemt = [n["id"] for n in m.get("noemt", []) if n.get("soort") not in ("publicatie",)][:MAX_NOEMT]
    stuk = compact({
        "id": s.id or "", "label": s.kenmerk, "titel": s.titel, "soort": m.get("soort", ""), "datum": m.get("datum", ""),
        "gepubliceerd": m.get("gepubliceerd", ""), "vastgesteld": m.get("vastgesteld", ""),
        "gewijzigd": m.get("gewijzigd", ""), "status": s.status, "orgaan": m.get("orgaan", ""),
        "rechtsgebied": m.get("rechtsgebied", ""), "reeks": m.get("reeks", []), "nummer": m.get("nummer", ""),
        "jaar": m.get("jaar", ""), "vervangt": s.vervangt, "vervangen_door": g.vervangen_door, "noemt": noemt,
        "bijlagen": m.get("bijlagen", []), "gebeurtenissen": g.gebeurtenissen, "link": s.link, "bron_hash": s.bron_hash,
        "tekststanden": tekststanden(graph, [n["id"] for n in m.get("noemt", []) if n.get("soort") == "bepaling"],
                                     m.get("datum", "")),
    })
    if not g.gevalideerd:
        stuk["gevalideerd"] = False
    return stuk


def _get(bron: KennisgroepenBron, graph: Any, a: dict[str, Any]) -> str:
    vp = externe_vindplaats(str(a.get("id") or "").strip())
    if vp is None or vp.brontype != "standpunt":
        return fout("ongeldig_id", "geef het kenmerk van een kennisgroepstandpunt, bijvoorbeeld 'KG:013:2026:4'")
    try:
        gelezen = bron.publicatie(graph, vp.id)
    except KennisgroepenFout as exc:
        if exc.code != "niet_gevonden" or not (opvolgers := bron.opvolgers(graph, vp.id)):
            raise
        # Niet gepubliceerd, maar een gepubliceerd standpunt trekt het in: dat is het antwoord (meting 14 nov 2026, vraag
        # 10). Standpunten van vóór 2022 staan niet op de site; ze zijn alleen via een Woo-verzoek openbaar.
        door = ", ".join(f"{i.upper()} ({st})" if st else i.upper() for i, st in opvolgers)
        return fout("niet_gevonden", f"{vp.id.upper()} staat niet bij de gepubliceerde kennisgroepstandpunten (een "
                    f"standpunt van vóór 2022 is alleen via de Woo openbaar). Het is ingetrokken door {door}; lees dat "
                    f"met get_standpunt.", vervangen_door=[i for i, _ in opvolgers])
    stuk = stuk_van(gelezen, graph)
    rijen = [r.als_dict() for r in gelezen.standpunt.rijen]
    toelichting = []
    if gelezen.standpunt.status != "geldend":
        door = ", ".join(i.upper() for i in gelezen.vervangen_door)
        toelichting.append(f"Dit standpunt is {gelezen.standpunt.status} en is geen geldend beleid"
                           + (f"; het is ingetrokken door {door}." if door else "."))
    offset = max(int(a.get("offset") or 0), 0)
    if a.get("inhoud"):
        return inhoudpagina(rijen, tool="get_standpunt", args={"id": vp.id}, offset=offset, stuk=stuk)
    return tekstpagina(rijen, tool="get_standpunt", args={"id": vp.id}, offset=offset, stuk=stuk,
                       toelichting=" ".join(toelichting) if rijen else "Dit standpunt heeft geen tekst bij de bron.")


#: De reden in het foutresultaat per code van de adapter (`KennisgroepenFout.code`).
FOUTREDEN = {"onbereikbaar": "bron_onbereikbaar", "bezet": "bron_bezet", "verzoek_geweigerd": "zoekvraag_geweigerd",
             "niet_gevonden": "niet_gevonden", "geen_index": "bron_onbereikbaar"}


def fout_van(exc: Any) -> str:
    code = getattr(exc, "code", "onbereikbaar")
    if code == "niet_gevonden":
        return fout("niet_gevonden", f"{exc}. Controleer het kenmerk, of zoek met zoek_standpunten, bijvoorbeeld "
                    "{\"woorden\": \"betalingsregeling\"}.")
    if code == "geen_index":
        return fout("bron_onbereikbaar", f"{exc}. Zoeken kan nu niet; een standpunt bij naam lezen wel, bijvoorbeeld "
                    "get_standpunt {\"id\": \"KG:013:2026:4\"}.")
    return fout(FOUTREDEN.get(code, "bron_onbereikbaar"), str(exc))


def dispatch_kennisgroep(name: str, args: dict[str, Any], bron: KennisgroepenBron | None, graph: Any) -> str:
    if bron is None:
        return fout("connector_uit", "De bron Kennisgroepstandpunten staat uit. Zeg dat, en antwoord niet uit eigen kennis.")
    if name == "zoek_standpunten":
        return _zoek(bron, graph, args)
    if name == "get_standpunt":
        return _get(bron, graph, args)
    raise KeyError(name)


__all__ = ["CONNECTOR", "KENNISGROEP_TOOLS", "FOUTREDEN", "fout_van", "dispatch_kennisgroep", "KennisgroepenFout"]
