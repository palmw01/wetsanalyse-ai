"""Het overzicht van een onderwerp: welke bepalingen gaan erover – deterministisch, uit de graaf.

Waarom dit bestaat. "Welke artikelen gaan over invordering?" liet de keten over aan het model: het koos
tool en zoekterm ("invordering" → 16 delen, "invordering van belastingen" → 0), stelde de opbouw zelf
samen (art. 31 en 63 Iw "buiten de hoofdstukken", terwijl de graaf H V en H VII zegt) en typte nummers
en titels over (bereiken als "28.1 t/m 28.7", die 28.3a verbergen). De bronnenlijst en de 3D-graaf
volgden uit die tekst. Dezelfde vraag gaf zo elke keer een ander antwoord, op deterministische tools.

Hier gebeurt alles wat feitelijk is in code, met vaste queries en een vaste ordening:

1. **Delen** – hoofdstukken, titeldelen, afdelingen, paragrafen en hoofddivisies met het onderwerp in
   hun opschrift (`queries.zoek_opbouw`), met hun bepalingen (`queries.bepalingen_in_delen`).
2. **Ook genoemd** – bepalingen die het onderwerp in hun tekst noemen (`queries.bepalingen_met_onderwerp`),
   opgetild naar artikel of hoofddivisie. Valt er een binnen een gevonden deel, dan staat hij daar al;
   anders krijgt hij zijn plek in de opbouw mee (`queries.plaats_in_opbouw`).
3. **Definitie** – waar de wet het begrip zelf definieert (`queries.definities_van`).
4. **Trefwoord** – regelingen waaraan de redactie dit trefwoord hangt (`queries.trefwoord_regelingen`):
   een redactionele indeling, geen wettelijke duiding.

Het model krijgt het overzicht en schrijft er een korte duiding bij; de werkplek toont het overzicht
zelf. Zo zijn lijst, bronnen en graaf bij dezelfde vraag dezelfde. `semantic_search` doet bewust niet
mee: die geeft altijd de k dichtstbijzijnde treffers, zonder ondergrens – een vaste maar willekeurige
staart.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import unquote

from .graph import queries
from .graph.results import parse_select
from .graph.structuur import natuurlijke_sleutel
from .ports import GraphPort
from .resultaat import BUDGET, TeGroot, compact, passend, resultaat

logger = logging.getLogger(__name__)

# Bovengrenzen: ruim boven wat de graaf nu oplevert (invordering: 16 delen, 112 bepalingen), zodat
# "volledig" in de praktijk waar is – en eerlijk false als een onderwerp toch breder is.
MAX_DELEN = 60
# Hoeveel definities en trefwoorden het model in de kop ziet (met het totaal erbij).
KOP = 5
MAX_BEPALINGEN = 300

# --- Herkennen --------------------------------------------------------------------------------------

_BEPALINGWOORD = r"(?:artikelen|artikels|bepalingen|hoofdstukken|afdelingen|paragrafen|onderdelen|delen|regels)"
_PATRONEN = (
    # "welke artikelen (in de Iw) gaan over X", "welke bepalingen hebben betrekking op X"
    re.compile(rf"^welke\s+{_BEPALINGWOORD}\b(?P<tussen>.{{0,60}}?)\s+(?:gaan|gaat|handelen|handelt)\s+over\s+(?P<o>.+)$"),
    re.compile(rf"^welke\s+{_BEPALINGWOORD}\b(?P<tussen>.{{0,60}}?)\s+(?:hebben|heeft)\s+betrekking\s+op\s+(?P<o>.+)$"),
    # "welke artikelen regelen X"
    re.compile(rf"^welke\s+{_BEPALINGWOORD}\s+(?:regelen|behandelen|betreffen)\s+(?P<o>.+)$"),
    # "waar is/wordt X geregeld (in de Awb)"
    re.compile(r"^waar\s+(?:is|wordt|staat|zijn|worden|staan)\s+(?P<o>.+?)\s+(?:geregeld|beschreven|vastgelegd)\b(?P<tussen>.*)$"),
    # "(geef een) overzicht van (de artikelen over) X"
    re.compile(rf"^(?:geef\s+(?:me\s+|mij\s+)?)?(?:een\s+)?overzicht\s+van\s+(?:de\s+|alle\s+)?(?:{_BEPALINGWOORD}\s+)?(?:over\s+|rond\s+|voor\s+)?(?P<o>.+)$"),
)
_LIDWOORD = re.compile(r"^(?:de|het|een)\s+")


def _normaliseer(vraag: str) -> str:
    return re.sub(r"\s+", " ", (vraag or "").strip().casefold()).rstrip("?.! ")


def _match(vraag: str) -> re.Match[str] | None:
    tekst = _normaliseer(vraag)
    for patroon in _PATRONEN:
        if m := patroon.match(tekst):
            return m
    return None


def is_overzichtsvraag(vraag: str) -> bool:
    """Een vraag naar wélke bepalingen over een onderwerp gaan – geen vraag naar wat er in één staat.

    Hard en uitlegbaar, net als `is_leesvraag`: een vaste vorm, geen modelkeuze. Een vraag die er niet
    in past, gaat de gewone antwoordroute; een te ruime herkenning zou een gewone vraag een lijst geven."""
    m = _match(vraag)
    return bool(m and onderwerp_uit(vraag))


def onderwerp_uit(vraag: str) -> str:
    """Het onderwerp uit een overzichtsvraag, zonder lidwoord; leeg als er geen is."""
    m = _match(vraag)
    if not m:
        return ""
    onderwerp = _LIDWOORD.sub("", m.group("o").strip())
    return onderwerp if queries.onderwerpwoorden(onderwerp) else ""


# --- Regeling in de vraag ---------------------------------------------------------------------------

_REGELINGEN_CACHE: list[dict[str, Any]] = []


def _regelingen(graph: GraphPort) -> list[dict[str, Any]]:
    """Citeertitels en afkortingen van alle regelingen; één query per proces (de graafstand wisselt
    alleen bij een herimport, en een verouderde naam kost hooguit een scope)."""
    if not _REGELINGEN_CACHE:
        rijen = parse_select(graph.sparql(queries.list_regelingen(limit=200)))
        for r in rijen:
            bwb = (r.get("regeling") or "").removeprefix(queries.NS)
            namen = {n.strip() for n in [r.get("citeertitel", ""), *(r.get("afkortingen", "") or "").split(" | ")]
                     if n and len(n.strip()) >= 2}
            # "Invorderingswet 1990" heet in een vraag vaak "de Invorderingswet".
            namen |= {re.sub(r"\s+\d{4}$", "", n) for n in namen if re.search(r"\s\d{4}$", n)}
            if bwb:
                _REGELINGEN_CACHE.append({"bwb_id": bwb, "soort": r.get("soort", ""),
                                          "namen": sorted(namen, key=len, reverse=True)})
    return _REGELINGEN_CACHE


def regelingen_in_vraag(graph: GraphPort, vraag: str) -> list[str]:
    """De BWB-id's van de regelingen die de vraag bij naam of afkorting noemt (woordgrens, hoofdletter-
    ongevoelig), in vaste volgorde. Een fout bij het ophalen kost alleen de afbakening."""
    tekst = _normaliseer(vraag)
    try:
        regelingen = _regelingen(graph)
    except Exception:  # noqa: BLE001 – zonder namenlijst geen afbakening, wel een overzicht
        logger.warning("regelingnamen voor de afbakening niet opgehaald", exc_info=True)
        return []
    gevonden = []
    for r in regelingen:
        for naam in r["namen"]:
            if re.search(rf"(?<![\w.]){re.escape(naam.casefold())}(?![\w])", tekst):
                gevonden.append(r["bwb_id"])
                break
    return sorted(set(gevonden))


def _zonder_regeling(onderwerp: str, graph: GraphPort, scope: list[str]) -> str:
    """"aansprakelijkheid in de invorderingswet" → "aansprakelijkheid": de regeling is de afbakening,
    geen zoekwoord."""
    if not scope:
        return onderwerp
    namen = [n for r in _regelingen(graph) if r["bwb_id"] in scope for n in r["namen"]]
    tekst = onderwerp
    for naam in sorted(namen, key=len, reverse=True):
        tekst = re.sub(rf"\s*(?:\b(?:in|van|uit|volgens)\s+)?(?:\b(?:de|het)\s+)?(?<![\w.]){re.escape(naam.casefold())}(?![\w])",
                       " ", tekst)
    tekst = re.sub(r"\s+", " ", tekst).strip()
    return tekst if queries.onderwerpwoorden(tekst) else onderwerp


# --- Bouwen ----------------------------------------------------------------------------------------

# De rang van een regeling: een wet vóór wat erop berust, een beleidsregel achteraan. Juridisch
# betekenisvol en onafhankelijk van zoekscores, dus een vaste volgorde.
RANG = {"wet": 0, "amvb": 1, "algemene-maatregel-van-bestuur": 1, "ministeriele-regeling": 2,
        "beleidsregel": 3, "circulaire": 3}

_DIEPTE = {"Paragraaf": 4, "Afdeling": 3, "Titeldeel": 2, "Hoofdstuk": 1, "Divisie": 0}


def _bwb(iri: str) -> str:
    return iri.removeprefix(queries.NS).split(queries.SEP, 1)[0]


def padsleutel(iri: str) -> tuple:
    """Documentvolgorde uit een bron-IRI: de nummers van het pad, natuurlijk gesorteerd (H II vóór
    H IX, 4.4.4 na 4.4.1, 28 vóór 28a). Een wet-lokale `id:`-node draagt zijn divisienummer in de id."""
    delen = iri.removeprefix(queries.NS).split(queries.SEP)[1:]
    waarden = []
    for sleutel, waarde in zip(delen[::2], delen[1::2]):
        waarde = unquote(waarde)
        if sleutel == "id":
            waarde = waarde.rsplit("divisie", 1)[-1]
        waarden.append(natuurlijke_sleutel(waarde))
    return tuple(waarden)


def _rijen(graph: GraphPort, query: str) -> list[dict[str, str]]:
    return parse_select(graph.sparql(query))


def _delen(graph: GraphPort, onderwerp: str, scope: list[str]) -> tuple[list[dict], bool]:
    """Delen met het onderwerp in hun opschrift, binnen de scope; alle pagina's tot `MAX_DELEN`."""
    delen: list[dict] = []
    offset, volledig = 0, True
    while True:
        pagina = _rijen(graph, queries.zoek_opbouw(onderwerp, limit=50, offset=offset, meer=True))
        delen += pagina[:50]
        if len(pagina) <= 50:
            break
        offset += 50
        if offset >= MAX_DELEN:
            volledig = False
            break
    return [d for d in delen if not scope or d.get("bwbId") in scope], volledig


def _treffers(graph: GraphPort, onderwerp: str, scope: list[str]) -> tuple[list[dict], bool]:
    """Bepalingen die het onderwerp in hun tekst noemen, binnen de scope."""
    treffers = _rijen(graph, queries.bepalingen_met_onderwerp(onderwerp, MAX_BEPALINGEN))
    volledig = len(treffers) <= MAX_BEPALINGEN
    return [t for t in treffers[:MAX_BEPALINGEN] if not scope or t.get("bwbId") in scope], volledig


def _met_terugval(woorden: list[str], zoek) -> tuple[str, list[dict], bool]:
    """Het langste begin van het onderwerp dat iets oplevert: alle woorden, dan zonder het laatste, tot
    het hoofdwoord. Vast en uitlegbaar – er wordt geen woord geraden of vervangen."""
    gebruikt, rijen, volledig = " ".join(woorden), [], True
    for n in range(len(woorden), 0, -1):
        gebruikt = " ".join(woorden[:n])
        rijen, volledig = zoek(gebruikt)
        if rijen:
            break
    return gebruikt, rijen, volledig


def bouw_overzicht(graph: GraphPort, vraag_of_onderwerp: str, *, onderwerp: str | None = None,
                   scope: list[str] | None = None) -> dict[str, Any]:
    """Het overzicht voor een vraag (of, met `onderwerp`, voor een kaal onderwerp).

    De opbouw en de tekst vallen elk apart terug op het langste begin van het onderwerp dat iets
    oplevert. "Invordering van belastingen" staat in geen enkel opschrift, wel in teksten: de delen
    komen dan van "invordering", de losse bepalingen van het hele onderwerp. Beide staan in het
    overzicht (`onderwerp_opbouw`, `onderwerp_tekst`), naast wat er gevraagd werd (`gevraagd`)."""
    gevraagd = onderwerp if onderwerp is not None else onderwerp_uit(vraag_of_onderwerp)
    if not gevraagd:
        raise ValueError("Geen onderwerp in de vraag.")
    scope = sorted(set(scope)) if scope is not None else regelingen_in_vraag(graph, vraag_of_onderwerp)
    gevraagd = _zonder_regeling(gevraagd, graph, scope)

    woorden = queries.onderwerpwoorden(gevraagd)
    in_opbouw, delen, volledig_delen = _met_terugval(woorden, lambda o: _delen(graph, o, scope))
    in_tekst, treffers, volledig_tekst = _met_terugval(woorden, lambda o: _treffers(graph, o, scope))
    volledig = volledig_delen and volledig_tekst
    # Alleen rijen met een echte bronnode: een rij zonder kan geen vindplaats zijn en zou een volgende
    # query openbreken.
    delen = [d for d in delen if queries.is_bron_iri(d.get("node", ""))]
    treffers = [t for t in treffers if queries.is_bron_iri(t.get("bepaling", ""))]

    # Geneste delen (paragraaf 4.4.4.2 in afdeling 4.4.4) horen bij hun ouder: hun bepalingen staan
    # daar al. De plaats komt uit de graaf, niet uit de IRI-vorm (Leidraad-divisies zijn `id:`-nodes).
    deel_iris = sorted({d["node"] for d in delen})
    plaats = _plaats(graph, deel_iris + sorted({t["bepaling"] for t in treffers}))
    gevonden = set(deel_iris)
    hoofddelen = [d for d in delen if not (plaats.get(d["node"], set()) & gevonden)]
    sub = {d["node"]: d for d in delen if d not in hoofddelen}

    inhoud: dict[str, list[dict]] = {}
    if hoofddelen:
        for r in _rijen(graph, queries.bepalingen_in_delen([d["node"] for d in hoofddelen])):
            if not (queries.is_bron_iri(r.get("bepaling", "")) and queries.is_bron_iri(r.get("deel", ""))):
                continue
            inhoud.setdefault(r["deel"], []).append(
                {"iri": r["bepaling"], "nummer": r.get("nummer", ""), "label": r.get("label", "")})
    binnen_delen = {b["iri"] for lijst in inhoud.values() for b in lijst} | gevonden

    regelingen: dict[str, dict[str, Any]] = {}

    try:
        soorten = {r["bwb_id"]: r["soort"] for r in _regelingen(graph)}
    except Exception:  # noqa: BLE001 – zonder soort alleen een minder fraaie volgorde
        logger.warning("soorten van regelingen niet opgehaald", exc_info=True)
        soorten = {}

    def regeling(bwb: str, naam: str) -> dict[str, Any]:
        return regelingen.setdefault(bwb, {"bwb_id": bwb, "citeertitel": naam or bwb, "soort": soorten.get(bwb, ""),
                                           "delen": [], "ook_genoemd": []})

    for d in sorted(hoofddelen, key=lambda d: (_bwb(d["node"]), padsleutel(d["node"]))):
        bepalingen = sorted({b["iri"]: b for b in inhoud.get(d["node"], [])}.values(),
                            key=lambda b: (natuurlijke_sleutel(b["nummer"]), b["iri"]))
        subdelen = sorted((s for s in sub if d["node"] in plaats.get(s, set())), key=padsleutel)
        regeling(_bwb(d["node"]), d.get("citeertitel", ""))["delen"].append({
            "iri": d["node"], "soort": d.get("soort", ""), "label": d.get("label", ""), "jci": d.get("jci", ""),
            "bepalingen": bepalingen,
            "subdelen": [{"iri": s, "label": sub[s].get("label", "")} for s in subdelen],
        })

    for t in treffers:
        iri = t["bepaling"]
        ouders = plaats.get(iri, set())
        if iri in binnen_delen or ouders & gevonden:
            continue
        in_deel = _diepste(ouders, plaats.soorten, plaats.labels)
        regeling(t.get("bwbId") or _bwb(iri), t.get("citeertitel", ""))["ook_genoemd"].append({
            "iri": iri, "nummer": t.get("nummer", ""), "label": t.get("label", ""), "jci": t.get("jci", ""),
            **({"in_deel": in_deel} if in_deel else {}),
        })
    for r in regelingen.values():
        r["ook_genoemd"].sort(key=lambda b: (natuurlijke_sleutel(b["nummer"]), b["iri"]))

    definities = [
        {"iri": r["node"], "begrip": r.get("begrip", ""), "label": r.get("label", ""), "tekst": r.get("tekst", ""),
         "jci": r.get("jci", ""), "bwb_id": r.get("bwbId", ""), "citeertitel": r.get("citeertitel", "")}
        for r in _rijen(graph, queries.definities_van(in_opbouw))
        if queries.is_bron_iri(r.get("node", "")) and (not scope or r.get("bwbId") in scope)
    ]
    trefwoorden: dict[str, dict[str, Any]] = {}
    for r in _rijen(graph, queries.trefwoord_regelingen(in_opbouw)):
        if not r.get("concept") or not r.get("bwbId") or (scope and r.get("bwbId") not in scope):
            continue
        tw = trefwoorden.setdefault(r["concept"], {"trefwoord": r.get("label", ""), "regelingen": []})
        tw["regelingen"].append({"bwb_id": r.get("bwbId", ""), "citeertitel": r.get("citeertitel", "")})

    def gewicht(r: dict[str, Any]) -> tuple:
        # Vaste volgorde zonder Lucene-scores: eerst naar rang (wet vóór beleidsregel), dan wie de meeste
        # bepalingen in gevonden delen heeft, dan wie het onderwerp het vaakst noemt, dan het BWB-id.
        in_delen = sum(len(d["bepalingen"]) for d in r["delen"])
        return (RANG.get(r["soort"], 9), -in_delen, -len(r["ook_genoemd"]), r["bwb_id"])

    return {
        "onderwerp": in_opbouw,
        "gevraagd": gevraagd,
        "onderwerp_opbouw": in_opbouw,
        "onderwerp_tekst": in_tekst,
        "scope": scope,
        "volledig": volledig,
        "definities": definities,
        "trefwoorden": list(trefwoorden.values()),
        "regelingen": sorted(regelingen.values(), key=gewicht),
    }


class _Plaats(dict):
    """bepaling → de delen erboven, plus soort en label van die delen."""

    def __init__(self) -> None:
        super().__init__()
        self.soorten: dict[str, str] = {}
        self.labels: dict[str, str] = {}


def _plaats(graph: GraphPort, iris: list[str]) -> _Plaats:
    uit = _Plaats()
    if not iris:
        return uit
    # In porties: een VALUES-blok van honderden IRI's is een geldige maar trage query.
    for i in range(0, len(iris), 100):
        for r in _rijen(graph, queries.plaats_in_opbouw(iris[i:i + 100])):
            if not (queries.is_bron_iri(r.get("bepaling", "")) and queries.is_bron_iri(r.get("deel", ""))):
                continue
            uit.setdefault(r["bepaling"], set()).add(r["deel"])
            uit.soorten[r["deel"]] = r.get("soort", "")
            uit.labels[r["deel"]] = r.get("label", "")
    return uit


def _diepste(ouders: set[str], soorten: dict[str, str], labels: dict[str, str]) -> dict[str, str] | None:
    """Het meest specifieke deel waarin een bepaling staat (paragraaf vóór afdeling vóór hoofdstuk)."""
    if not ouders:
        return None
    iri = max(ouders, key=lambda o: (_DIEPTE.get(soorten.get(o, ""), -1), len(o), o))
    return {"iri": iri, "label": labels.get(iri, "")}


# --- Toetsen ---------------------------------------------------------------------------------------

_NUMMER = r"\d+[a-z]*(?::\d+[a-z]*)?(?:\.\d+[a-z]*)*"
# "artikel 4", "art. 4:94a", en een opsomming na "artikelen": "artikelen 8, 9 en 10".
_VERMELDING = re.compile(rf"\b(?:artikel|art\.)\s+({_NUMMER})\b|\bartikelen\s+({_NUMMER}(?:\s*(?:,|en|of)\s*{_NUMMER})*)",
                         re.IGNORECASE)


def nummers(ov: dict[str, Any]) -> set[str]:
    """Elk artikel- en bepalingnummer dat het overzicht kent, ook die van de definitie (art. 2)."""
    uit: set[str] = set()
    for r in ov.get("regelingen", []):
        for d in r["delen"]:
            uit |= {b["nummer"] for b in d["bepalingen"] if b.get("nummer")}
        uit |= {b["nummer"] for b in r["ook_genoemd"] if b.get("nummer")}
    for d in ov.get("definities", []):
        pad = d["iri"].removeprefix(queries.NS).split(queries.SEP)
        uit |= {unquote(pad[i + 1]) for i in range(len(pad) - 1) if pad[i] == "artikel"}
    return {n.casefold() for n in uit}


def vermeldingen(tekst: str) -> list[str]:
    """De artikelen die een tekst noemt, als "artikel N", in volgorde en zonder dubbelen."""
    uit: list[str] = []
    for m in _VERMELDING.finditer(tekst or ""):
        for nummer in re.findall(_NUMMER, m.group(1) or m.group(2) or ""):
            if f"artikel {nummer}" not in uit:
                uit.append(f"artikel {nummer}")
    return uit


def vermeldingen_buiten(tekst: str, ov: dict[str, Any]) -> list[str]:
    """De artikelen die de duiding noemt maar die niet in het overzicht staan.

    De duiding hoort het overzicht te duiden, niet aan te vullen met een bepaling die het model zelf
    bedacht of elders zag: zo'n vermelding is `ongegrond` en gaat de correctieronde in."""
    bekend = nummers(ov)
    return [v for v in vermeldingen(tekst) if v.removeprefix("artikel ").casefold() not in bekend]


# --- Weergaven -------------------------------------------------------------------------------------

def aantal_bepalingen(ov: dict[str, Any]) -> int:
    return sum(len(d["bepalingen"]) for r in ov["regelingen"] for d in r["delen"]) + \
        sum(len(r["ook_genoemd"]) for r in ov["regelingen"])


def voor_model(ov: dict[str, Any], *, offset: int = 0, args: dict[str, Any] | None = None) -> str:
    """Wat het model leest: de opbouw per regeling met tellingen, zonder de nummerlijsten – die toont de
    werkplek. Genoeg om te duiden ("vijf hoofdstukken van de Iw, afdeling 4.4.4 Awb"), te weinig om een
    lijst over te typen. Eén rij per deel plus per regeling één 'ook genoemd'-rij; past het niet binnen de
    begroting, dan met een `vervolg` naar `overzicht_onderwerp` vanaf de volgende rij (het contract:
    niets wordt afgeknipt)."""
    def rijen_van(r: dict[str, Any]) -> list[dict[str, Any]]:
        # Eén rij per deel, en per regeling één rij voor wat er verder over het onderwerp gaat: zo
        # pagineert het overzicht op een natuurlijke grens, ook bij een regeling met veel delen.
        uit = [compact({"regeling": r["citeertitel"], "bwb_id": r["bwb_id"], "deel": d["label"], "iri": d["iri"],
                        "bepalingen": len(d["bepalingen"]),
                        "waarin": [s["label"] for s in d["subdelen"]][:KOP]}) for d in r["delen"]]
        if r["ook_genoemd"]:
            per_deel: dict[str, int] = {}
            for b in r["ook_genoemd"]:
                naam = (b.get("in_deel") or {}).get("label", "") or "buiten de opbouw"
                per_deel[naam] = per_deel.get(naam, 0) + 1
            meest = sorted(per_deel.items(), key=lambda kv: (-kv[1], kv[0]))
            uit.append({"regeling": r["citeertitel"], "bwb_id": r["bwb_id"], "ook_genoemd": len(r["ook_genoemd"]),
                        "vooral_in": [naam for naam, _ in meest[:KOP]], "in_delen": len(meest)})
        return uit

    rijen = [rij for r in ov["regelingen"] for rij in rijen_van(r)][offset:]
    extra = {
        "onderwerp": ov["gevraagd"],
        "gezocht_in_opschriften": ov["onderwerp_opbouw"],
        "gezocht_in_tekst": ov["onderwerp_tekst"],
        **({"afgebakend_tot": ov["scope"]} if ov["scope"] else {}),
    }
    if not offset:
        # De kop draagt hoogstens vijf van elk, met het totaal: het model duidt, de werkplek toont alles.
        if ov["definities"]:
            extra["definities"] = [compact({"begrip": d["begrip"], "vindplaats": d["jci"] or d["iri"],
                                            "regeling": d["citeertitel"]}) for d in ov["definities"][:KOP]]
            extra["definities_totaal"] = len(ov["definities"])
        if ov["trefwoorden"]:
            extra["trefwoord_bij"] = [{"trefwoord": t["trefwoord"],
                                       "regelingen": [r["citeertitel"] for r in t["regelingen"]][:KOP]}
                                      for t in ov["trefwoorden"][:KOP]]
            extra["trefwoorden_totaal"] = len(ov["trefwoorden"])
    toelichting = (
        "Dit overzicht is al voor je opgebouwd uit de graaf en de werkplek toont het volledig, met alle "
        "nummers. Schrijf alleen een korte duiding (2–4 zinnen): waar het onderwerp vooral geregeld is en "
        "wat opvalt. Herhaal geen lijsten of nummers, en noem geen bepaling die hier niet in staat."
    )
    vervolg_args = args or {"onderwerp": ov["gevraagd"], **({"bwb_id": ov["scope"][0]} if len(ov["scope"]) == 1 else {})}

    if not ov["volledig"]:
        # Het overzicht raakte zijn plafond (MAX_DELEN/MAX_BEPALINGEN): dat is iets anders dan een
        # volgende pagina, dus een eigen veld – `volledig` gaat hier alleen over de paginering.
        extra["begrensd"] = True

    def maak(deel: list[dict[str, Any]]) -> str:
        vervolg = None if len(deel) == len(rijen) else {"tool": "overzicht_onderwerp",
                                                        "args": {**vervolg_args, "offset": offset + len(deel)}}
        return resultaat(deel, volledig=vervolg is None, vervolg=vervolg, extra=extra, toelichting=toelichting)

    k, tekst = passend(rijen, maak, BUDGET)
    if len(tekst) > BUDGET or (rijen and k == 0):
        raise TeGroot("overzicht_onderwerp: één rij is groter dan de begroting", omvang=len(maak(rijen[:1])))
    return tekst


def bronrijen(ov: dict[str, Any]) -> str:
    """Alle vindplaatsen van het overzicht als contractresultaat, voor `collect_sources`: de bronnen
    komen zo uit het overzicht en niet uit de proza (dezelfde labelregels: titel bij een deel, naam bij
    een `id:`-node)."""
    rijen: list[dict[str, Any]] = []
    for d in ov["definities"]:
        rijen.append({"node": d["iri"], "label": d["label"], "jci": d["jci"]})
    for r in ov["regelingen"]:
        for d in r["delen"]:
            rijen.append({"node": d["iri"], "label": d["label"], "jci": d["jci"]})
        for b in r["ook_genoemd"]:
            rijen.append({"node": b["iri"], "label": b["label"], "jci": b.get("jci", "")})
    return json.dumps({"status": "ok", "volledig": True, "aantal": len(rijen),
                       "resultaten": [{k: v for k, v in r.items() if v} for r in rijen]},
                      ensure_ascii=False, separators=(",", ":"))
