"""Bronnen vinden met Lex: de ontdekmethoden voor een werkgebied (spoor D, fase A).

Vanaf de selectie van een werkgebied (kern = bronselecties met rol *analyseren*) zoekt Lex bepalingen
die erbij kunnen horen. Elke methode is een graafquery, zonder model; elke kandidaat draagt per methode
zijn bewijs. De api voegt samen en bewaart de besluiten (`api/app/bronnen_run_store.py`).

Methoden, van sterk naar zwak bewijs (PLAN §D *Bronnen vinden*):

| methode | wat | rol |
|---|---|---|
| `overzicht` | het overzicht op de analysevraag (`overzicht.bouw_overzicht`); standaard alleen zonder kern | kern |
| `deelvraag` | het overzicht per actieve deelvraag van het werkgebied; alleen met deelvragen | kern zonder kern, anders aanverwant |
| `verwijzing_uit` | waar de kern naar verwijst, diepte 1 | afhankelijkheid bij een bekende functie, anders aanverwant |
| `verwijzing_in` | wat naar de kern verwijst, diepte 1 – standaard uit (meting) | aanverwant |
| `definitie` | waar de wet een term definieert die letterlijk in de kern staat | afhankelijkheid |
| `opbouw` | de andere artikelen in hetzelfde deel als een kernartikel | aanverwant |
| `gelijkenis` | `bwb_similarity` op de tekst van de kern – zwakste signaal, geen bewijs | aanverwant |

**Diepte 1**, volgens de skill (`references/verwijzingen-volgen.md`): blind verder uitbreiden langs de
graaf maakt een selectie aantoonbaar slechter. Elke methode heeft een plafond; raakt ze dat, of hapert
de graaf, dan staat `volledig: false` in haar meting – nooit stil een kortere lijst.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable

from .graph import queries
from .graph.queries import BEVAT, NS, PREFIXES, STRUCTUUR, _iri_veilig, _lit
from .graph.results import parse_select
from .ports import GraphPort

logger = logging.getLogger(__name__)

METHODEN = ("overzicht", "deelvraag", "verwijzing_uit", "verwijzing_in", "definitie", "opbouw", "gelijkenis")
#: Wat standaard draait als er een kern is – gekozen op de meting van 15 okt 2026
#: (`docs/architectuur/metingen/bronselectie-2026-10-15/`): met een kern voegde het overzicht geen
#: recall toe maar wel 36 onbeoordeelde "kern"-kandidaten, en `verwijzing_in` leverde alle uitgesloten
#: bepalingen (rente, verrekening) voor één aanverwant Leidraad-onderdeel. `gelijkenis` voegde niets toe.
#: Een methode die niet aantoonbaar helpt, staat niet standaard aan.
STANDAARD = ("verwijzing_uit", "definitie", "opbouw")
#: Zonder kern is de analysevraag het enige vertrekpunt: dan het overzicht.
ZONDER_KERN = ("overzicht",)


def standaard_voor(invoer: dict[str, Any]) -> tuple[str, ...]:
    """Met deelvragen (optioneel, ze staan alleen in de invoer als het werkgebied ze heeft) zoekt Lex
    ook per deelvraag: de analist vroeg er zelf om, en de dekkingscheck meet ertegen."""
    basis = STANDAARD if invoer.get("kern") else ZONDER_KERN
    return basis + ("deelvraag",) if invoer.get("deelvragen") else basis

MAX_PER_METHODE = 60
MAX_OVERZICHT = 40
MAX_OPBOUW_PER_KERN = 30
MAX_GELIJKENIS = 10
MAX_PER_DEELVRAAG = 15

ROL_VOLGORDE = {"kern": 0, "afhankelijkheid": 1, "aanverwant": 2}


# --- de functie van een verwijzing ----------------------------------------------------------------

_FUNCTIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("uitzondering", re.compile(r"\b(in afwijking van|met uitzondering van|behoudens|onverminderd)\s*$", re.I)),
    ("delegatie", re.compile(r"\b(bij of krachtens|krachtens|bij algemene maatregel van bestuur|bij ministeriële regeling"
                             r"|regels gesteld|nadere regels)\b[^.;]{0,80}$", re.I)),
    ("toepassing", re.compile(r"\b((als |zoals )?bedoeld in|overeenkomstige toepassing|is van toepassing|"
                              r"toepassing van|ingevolge|op grond van)\s*$", re.I)),
)

#: Functies die een verwijzing tot een afhankelijkheid maken: zonder het doel is de kern niet te
#: begrijpen of toe te passen.
AFHANKELIJK = {"definitie", "uitzondering", "delegatie", "toepassing"}


def verwijzingsfunctie(tekst: str, anker: str, definieert: bool = False) -> str:
    """De functie van een verwijzing, uit de tekst vóór haar anker. Deterministisch en uitlegbaar:
    een vast patroon direct vóór de verwijzing, anders `onbekend` – liever geen functie dan een
    geraden.

    - de bron definieert een begrip (`bwb:definieertBegrip`) → *definitie*;
    - "in afwijking van", "met uitzondering van", "behoudens", "onverminderd" → *uitzondering*;
    - "bij of krachtens", "bij algemene maatregel van bestuur", "regels gesteld" → *delegatie*;
    - "(als) bedoeld in", "overeenkomstige toepassing", "ingevolge", "op grond van" → *toepassing*.
    """
    if definieert:
        return "definitie"
    if not tekst or not anker:
        return "onbekend"
    plek = tekst.find(anker)
    if plek < 0:
        plek = tekst.lower().find(anker.lower())
    if plek < 0:
        return "onbekend"
    voor = tekst[max(0, plek - 120):plek].rstrip(" ,(")
    for functie, patroon in _FUNCTIES:
        if patroon.search(voor):
            return functie
    return "onbekend"


# --- hulpjes --------------------------------------------------------------------------------------

def _waarden(iris: list[str]) -> str:
    return " ".join(f"<{_iri_veilig(i)}>" for i in sorted(set(iris)))


def _bwb(iri: str) -> str:
    rest = iri[len(NS):] if iri.startswith(NS) else ""
    return rest.split(":", 1)[0]


def _binnen(iri: str, ander: str) -> bool:
    """Valt `iri` binnen `ander` (of is het `ander`)? Uit de IRI-vorm (`…:artikel:9:lid:1` hoort bij
    `…:artikel:9`); bij divisies van een beleidsregel (`id:`-knopen) geldt alleen gelijkheid."""
    return iri == ander or iri.startswith(ander + ":")


def in_selectie(iri: str, selectie: list[str]) -> bool:
    """Al gedekt door de selectie: gelijk, erbinnen, of het omvattende artikel ervan."""
    return any(_binnen(iri, s) or _binnen(s, iri) for s in selectie)


def _rijen(graph: GraphPort, query: str) -> list[dict[str, str]]:
    return parse_select(graph.sparql(query))


class Verzameling:
    """Kandidaten met bewijs, één per bepaling; de sterkste rol wint (zoals de api)."""

    def __init__(self, selectie: list[str]) -> None:
        self.selectie = selectie
        self.per_iri: dict[str, dict[str, Any]] = {}

    def voeg(self, iri: str, *, rol: str, methode: str, vanuit: str = "", label: str = "",
             detail: dict[str, Any] | None = None) -> bool:
        if not queries.is_bron_iri(iri) or in_selectie(iri, self.selectie):
            return False
        bewijs = {"methode": methode, "vanuit": vanuit, "detail": detail or {}}
        k = self.per_iri.get(iri)
        if k is None:
            self.per_iri[iri] = {"bron_iri": iri, "label": label, "bwb_id": _bwb(iri), "rol": rol, "bewijs": [bewijs]}
            return True
        if bewijs not in k["bewijs"]:
            k["bewijs"].append(bewijs)
        if ROL_VOLGORDE[rol] < ROL_VOLGORDE[k["rol"]]:
            k["rol"] = rol
        k["label"] = k["label"] or label
        return True

    def lijst(self) -> list[dict[str, Any]]:
        return sorted(self.per_iri.values(), key=lambda k: (ROL_VOLGORDE[k["rol"]], -len(k["bewijs"]), k["bron_iri"]))


# --- de methoden ----------------------------------------------------------------------------------

def q_uitgaand(kern: list[str], limit: int) -> str:
    return PREFIXES + f"""SELECT DISTINCT ?kern ?vanuit ?tekst ?anker ?naar ?label ?def WHERE {{
  VALUES ?kern {{ {_waarden(kern)} }}
  ?kern ({BEVAT})* ?vanuit .
  ?vanuit bwb:heeftVerwijzing ?v .
  ?v bwb:naar ?naar .
  FILTER(STRSTARTS(STR(?naar), "{NS}"))
  FILTER EXISTS {{ ?naar a ?type }}
  OPTIONAL {{ ?v bwb:ankerTekst ?anker }}
  OPTIONAL {{ ?vanuit bwb:tekst ?tekst }}
  OPTIONAL {{ ?vanuit bwb:definieertBegrip ?def }}
  OPTIONAL {{ ?naar rdfs:label ?label }}
}} ORDER BY ?kern ?vanuit ?naar LIMIT {limit + 1}"""


def q_inkomend(kern: list[str], limit: int) -> str:
    return PREFIXES + f"""SELECT DISTINCT ?kern ?doel ?bron ?tekst ?anker ?label ?def WHERE {{
  VALUES ?kern {{ {_waarden(kern)} }}
  ?kern ({BEVAT})* ?doel .
  ?v bwb:naar ?doel .
  ?bron bwb:heeftVerwijzing ?v .
  FILTER(STRSTARTS(STR(?bron), "{NS}"))
  OPTIONAL {{ ?v bwb:ankerTekst ?anker }}
  OPTIONAL {{ ?bron bwb:tekst ?tekst }}
  OPTIONAL {{ ?bron bwb:definieertBegrip ?def }}
  OPTIONAL {{ ?bron rdfs:label ?label }}
}} ORDER BY ?kern ?bron LIMIT {limit + 1}"""


def q_teksten(kern: list[str]) -> str:
    return PREFIXES + f"""SELECT ?kern ?deel ?tekst WHERE {{
  VALUES ?kern {{ {_waarden(kern)} }}
  ?kern ({BEVAT})* ?deel .
  ?deel bwb:tekst ?tekst .
}} ORDER BY ?kern ?deel"""


def q_definities(bwb_ids: list[str], limit: int) -> str:
    filters = " || ".join(f'STRSTARTS(STR(?node), {_lit(NS + b + ":")})' for b in sorted(set(bwb_ids)))
    return PREFIXES + f"""SELECT DISTINCT ?node ?begrip ?label WHERE {{
  ?node bwb:definieertBegrip ?begrip .
  FILTER({filters})
  OPTIONAL {{ ?node rdfs:label ?label }}
}} ORDER BY ?node ?begrip LIMIT {limit + 1}"""


def q_opbouw(kern: list[str]) -> str:
    return PREFIXES + f"""SELECT DISTINCT ?kern ?artikel ?ouder ?buur ?label WHERE {{
  VALUES ?kern {{ {_waarden(kern)} }}
  ?artikel ({BEVAT})* ?kern .
  ?artikel a bwb:Artikel .
  ?ouder ({STRUCTUUR}) ?artikel .
  ?ouder ({STRUCTUUR}) ?buur .
  ?buur a bwb:Artikel .
  FILTER(?buur != ?artikel)
  OPTIONAL {{ ?buur rdfs:label ?label }}
}} ORDER BY ?kern ?buur"""


def _overzicht(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    from .overzicht import bouw_overzicht, onderwerp_uit

    vraag = (invoer.get("analysevraag") or "").strip()
    naam = (invoer.get("naam") or "").strip()
    # Het onderwerp uit de analysevraag ("welke artikelen gaan over X?"); lukt dat niet ("Wanneer is een
    # aanslag invorderbaar?"), dan de naam van het werkgebied. De hele vraag als onderwerp leverde ruis
    # op (gemeten: `docs/architectuur/metingen/bronselectie-2026-10-15/`).
    onderwerp = (onderwerp_uit(vraag) if vraag else "") or naam or vraag
    vraag = vraag or naam
    if not onderwerp:
        return 0, True
    try:
        ov = bouw_overzicht(graph, vraag, onderwerp=onderwerp)
    except ValueError:                          # geen onderwerp te vinden: niets, maar wel volledig
        return 0, True
    n, volledig = 0, bool(ov.get("volledig", True))
    for r in ov.get("regelingen", []):
        bepalingen = [b for d in r.get("delen", []) for b in d.get("bepalingen", [])] + r.get("ook_genoemd", [])
        for b in bepalingen:
            if n >= MAX_OVERZICHT:
                return n, False
            if v.voeg(b["iri"], rol="kern", methode="overzicht", label=b.get("label") or b.get("naam", ""),
                      detail={"onderwerp": ov.get("onderwerp_tekst") or onderwerp}):
                n += 1
    return n, volledig


# "Wanneer is een aanslag invorderbaar?" noemt geen onderwerp in de vorm van een overzichtsvraag; het
# vraagwoord vooraan eraf laat "een aanslag invorderbaar" over, en `onderwerpwoorden` haalt de stopwoorden
# weg. Alleen vooraan: een vraagwoord midden in de zin kan bij het onderwerp horen.
_VRAAGBEGIN = re.compile(
    r"^\s*(?:in welke gevallen|onder welke voorwaarden|in hoeverre|op welke wijze|wanneer|wie|wat|welke?|hoe|"
    r"waar|waarom|waardoor|waarover|is|zijn|kan|kunnen|mag|mogen|moet|moeten|geldt|gelden)\b\s*", re.I)


def onderwerp_van_deelvraag(vraag: str) -> str:
    """Het zoekonderwerp van een deelvraag: als overzichtsvraag ("welke artikelen gaan over X?") het
    onderwerp, anders de vraag zonder vraagwoord vooraan; leeg als er niets zoekbaars overblijft."""
    from .overzicht import onderwerp_uit

    o = onderwerp_uit(vraag)
    if o:
        return o
    rest = vraag.strip()
    while (kaler := _VRAAGBEGIN.sub("", rest, count=1)) != rest:
        rest = kaler
    rest = rest.rstrip("?.! ")
    return rest if queries.onderwerpwoorden(rest) else ""


def _deelvraag(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    """Het overzicht per deelvraag. Zonder kern zijn de treffers kern (zoals het overzicht op de
    analysevraag); met een kern aanverwant: het overzicht naast een kern gaf in de meting van 15 okt
    2026 vooral onbeoordeelde ruis, en de analist beslist wat bij de deelvraag hoort."""
    from .overzicht import bouw_overzicht

    rol = "aanverwant" if invoer.get("kern") else "kern"
    n_totaal, volledig = 0, True
    for d in invoer.get("deelvragen") or []:
        onderwerp = onderwerp_van_deelvraag(d.get("vraag", ""))
        if not onderwerp:
            continue
        try:
            ov = bouw_overzicht(graph, d["vraag"], onderwerp=onderwerp)
        except ValueError:
            continue
        volledig = volledig and bool(ov.get("volledig", True))
        n = 0
        for r in ov.get("regelingen", []):
            for b in [b for deel in r.get("delen", []) for b in deel.get("bepalingen", [])] + r.get("ook_genoemd", []):
                if n >= MAX_PER_DEELVRAAG:
                    volledig = False
                    break
                if v.voeg(b["iri"], rol=rol, methode="deelvraag", label=b.get("label") or b.get("naam", ""),
                          detail={"deelvraag_id": d.get("id", ""), "vraag": d.get("vraag", ""),
                                  "onderwerp": ov.get("onderwerp_tekst") or onderwerp}):
                    n += 1
        n_totaal += n
    return n_totaal, volledig


def _verwijzing_uit(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    kern = [k["bron_iri"] for k in invoer.get("kern", [])]
    if not kern:
        return 0, True
    rijen = _rijen(graph, q_uitgaand(kern, MAX_PER_METHODE))
    n = 0
    for r in rijen[:MAX_PER_METHODE]:
        functie = verwijzingsfunctie(r.get("tekst", ""), r.get("anker", ""), definieert=bool(r.get("def")))
        rol = "afhankelijkheid" if functie in AFHANKELIJK else "aanverwant"
        n += v.voeg(r["naar"], rol=rol, methode="verwijzing_uit", vanuit=r.get("vanuit", ""), label=r.get("label", ""),
                    detail={"anker": r.get("anker", ""), "functie": functie})
    return n, len(rijen) <= MAX_PER_METHODE


def _verwijzing_in(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    kern = [k["bron_iri"] for k in invoer.get("kern", [])]
    if not kern:
        return 0, True
    rijen = _rijen(graph, q_inkomend(kern, MAX_PER_METHODE))
    n = 0
    for r in rijen[:MAX_PER_METHODE]:
        functie = verwijzingsfunctie(r.get("tekst", ""), r.get("anker", ""), definieert=bool(r.get("def")))
        n += v.voeg(r["bron"], rol="aanverwant", methode="verwijzing_in", vanuit=r.get("doel", ""),
                    label=r.get("label", ""), detail={"anker": r.get("anker", ""), "functie": functie})
    return n, len(rijen) <= MAX_PER_METHODE


def _term_in(term: str, tekst: str) -> bool:
    return bool(term) and re.search(rf"(?<!\w){re.escape(term)}(?!\w)", tekst, re.I) is not None


def _definitie(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    kern = [k["bron_iri"] for k in invoer.get("kern", [])]
    if not kern:
        return 0, True
    teksten = _rijen(graph, q_teksten(kern))
    bwb_ids = sorted({_bwb(k) for k in kern if _bwb(k)})
    if not bwb_ids:
        return 0, True
    defs = _rijen(graph, q_definities(bwb_ids, 500))
    n = 0
    for d in defs[:500]:
        term = d.get("begrip", "").strip()
        waar = next((t for t in teksten if _term_in(term, t.get("tekst", ""))), None)
        if waar is None or n >= MAX_PER_METHODE:
            continue
        n += v.voeg(d["node"], rol="afhankelijkheid", methode="definitie", vanuit=waar.get("deel", ""),
                    label=d.get("label", ""), detail={"begrip": term})
    return n, len(defs) <= 500 and n < MAX_PER_METHODE


def _opbouw(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    kern = [k["bron_iri"] for k in invoer.get("kern", [])]
    if not kern:
        return 0, True
    per_kern: dict[str, int] = {}
    n, volledig = 0, True
    for r in _rijen(graph, q_opbouw(kern)):
        teller = per_kern.get(r["kern"], 0)
        if teller >= MAX_OPBOUW_PER_KERN:
            volledig = False
            continue
        if v.voeg(r["buur"], rol="aanverwant", methode="opbouw", vanuit=r["kern"], label=r.get("label", ""),
                  detail={"deel": r.get("ouder", "")}):
            per_kern[r["kern"]] = teller + 1
            n += 1
    return n, volledig


def _gelijkenis(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    from .tools import _semantische_treffers

    kern = [k["bron_iri"] for k in invoer.get("kern", [])]
    if not kern:
        return 0, True
    teksten = _rijen(graph, q_teksten(kern))
    n = 0
    for k in kern:
        tekst = " ".join(t.get("tekst", "") for t in teksten if t.get("kern") == k)[:2000]
        if not tekst:
            continue
        for t in _semantische_treffers(graph.semantic_search(tekst, MAX_GELIJKENIS * 4))[:MAX_GELIJKENIS]:
            n += v.voeg(t["node"], rol="aanverwant", methode="gelijkenis", vanuit=k, label=t.get("label", ""),
                        detail={"score": t.get("score", "")})
    return n, True


UITVOERING: dict[str, Callable[[GraphPort, dict[str, Any], Verzameling], tuple[int, bool]]] = {
    "overzicht": _overzicht, "deelvraag": _deelvraag, "verwijzing_uit": _verwijzing_uit, "verwijzing_in": _verwijzing_in,
    "definitie": _definitie, "opbouw": _opbouw, "gelijkenis": _gelijkenis,
}


def vind(graph: GraphPort, invoer: dict[str, Any], methoden: tuple[str, ...] | None = None,
         melding: Callable[[str, int, bool, int], None] | None = None) -> dict[str, Any]:
    """De methoden op de invoer van een bronnenrun (`api/app/bronnen_run_store.invoer_van`); zonder
    `methoden` de standaard voor die invoer (`standaard_voor`).

    Een methode die faalt, laat de rest niet vallen: haar meting zegt `volledig: false`."""
    methoden = methoden or standaard_voor(invoer)
    selectie = [b["bron_iri"] for b in invoer.get("kern", []) + invoer.get("context", [])]
    v = Verzameling(selectie)
    meting: dict[str, dict[str, Any]] = {}
    for m in methoden:
        t0 = time.monotonic()
        fout = False
        try:
            aantal, volledig = UITVOERING[m](graph, invoer, v)
        except Exception:  # noqa: BLE001 – een haperende query is een onvolledige methode, geen crash
            logger.warning("bronmethode faalde", extra={"categorie": "technisch", "methode": m}, exc_info=True)
            aantal, volledig, fout = 0, False, True
        ms = int((time.monotonic() - t0) * 1000)
        # `fout` is intern (de run maakt er bij totale uitval een storing van); de api krijgt hem niet.
        meting[m] = {"aantal": aantal, "volledig": volledig, "ms": ms, **({"fout": True} if fout else {})}
        if melding:
            melding(m, aantal, volledig, ms)
    kandidaten = v.lijst()
    _benoem(graph, kandidaten)
    return {"kandidaten": kandidaten, "meting": meting}


def _benoem(graph: GraphPort, kandidaten: list[dict[str, Any]]) -> None:
    """"Artikel 30g, lid 2, onderdeel a – Algemene wet inzake rijksbelastingen" in plaats van het kale
    "Onderdeel a." uit de graaf. De vindplaats komt uit de IRI (`bronmodel.vindplaats`, dezelfde regels
    als de bronnenlijst); een divisie van een beleidsregel houdt haar eigen titel. Een naam die niet te
    halen is, breekt niets."""
    from .overzicht import definitie_vindplaats
    from .regelingnamen import regelingnamen

    namen = regelingnamen(graph, {k["bwb_id"] for k in kandidaten})
    for k in kandidaten:
        plek = definitie_vindplaats(k["bron_iri"]) or k["label"] or k["bron_iri"]
        k["label"] = f"{plek} – {namen[k['bwb_id']]}" if k["bwb_id"] in namen else plek
