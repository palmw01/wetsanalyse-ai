"""Bronnen vinden met Lex: de ontdekmethoden voor een werkgebied (spoor D, fase A).

Vanaf de selectie van een werkgebied (kern = bronselecties met rol *analyseren*) zoekt Lex bepalingen
die erbij kunnen horen. Elke methode is een graafquery, zonder model; elke kandidaat draagt per methode
zijn bewijs. De api voegt samen en bewaart de besluiten (`api/app/bronnen_run_store.py`).

Methoden, van sterk naar zwak bewijs (PLAN §D *Bronnen vinden*):

| methode | wat | rol |
|---|---|---|
| `overzicht` | het overzicht op de analysevraag (`overzicht.bouw_overzicht`); standaard alleen zonder kern | kern |
| `deelvraag` | per actieve deelvraag de gerichte leden (`bepaling_opties`, ook in de intake); alleen met deelvragen | kern zonder kern, anders aanverwant |
| `verwijzing_uit` | waar de kern naar verwijst, diepte 1 | afhankelijkheid bij een bekende functie, anders aanverwant |
| `verwijzing_in` | wat naar de kern verwijst, diepte 1 – standaard uit (meting) | aanverwant |
| `definitie` | waar de wet een term definieert die letterlijk in de kern staat | afhankelijkheid |
| `opbouw` | de andere artikelen in hetzelfde deel als een kernartikel | aanverwant |
| `gelijkenis` | `bwb_similarity` op de tekst van de kern – zwakste signaal, geen bewijs | aanverwant |
| `grondslag` | zoekvraag a: waar de gekozen gebeurtenis haar bestaansrecht krijgt (`zoekvragen.grondslag`); alleen met een gebeurtenis | kern |

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
from .bepaling_namen import _benoem, bwb_van as _bwb, rijen as _rijen
from .deelvraag_zoeken import bepaling_opties
from .ports import GraphPort
from .zoektermen import buiten_uit_afbakening, uitsluitstammen

logger = logging.getLogger(__name__)

METHODEN = ("overzicht", "deelvraag", "verwijzing_uit", "verwijzing_in", "definitie", "opbouw", "gelijkenis",
            "grondslag")
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
    ook per deelvraag: de analist vroeg er zelf om, en de dekkingscheck meet ertegen. Met een gekozen
    gebeurtenis (`dossier.gebeurtenis`) zoekt hij de grondslag erbij, om dezelfde reden: de analist koos haar."""
    basis = STANDAARD if invoer.get("kern") else ZONDER_KERN
    if invoer.get("deelvragen"):
        basis += ("deelvraag",)
    if ((invoer.get("dossier") or {}).get("gebeurtenis") or "").strip():
        basis += ("grondslag",)
    return basis

MAX_PER_METHODE = 60
MAX_OVERZICHT = 40
MAX_OPBOUW_PER_KERN = 30
MAX_GELIJKENIS = 10

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


def _binnen(iri: str, ander: str) -> bool:
    """Valt `iri` binnen `ander` (of is het `ander`)? Uit de IRI-vorm (`…:artikel:9:lid:1` hoort bij
    `…:artikel:9`). Een `id:`-knoop van een beleidsregel draagt zijn pad gecodeerd
    (`…divisie25.2%2FCirculaire.divisie25.2.1` hoort bij `…divisie25.2`). Een hoofddivisie heet echter
    `…:artikel:25`, en dat ze `…id:…divisie25%2F…` bevat zegt geen IRI: dat weet alleen de boom."""
    return iri == ander or iri.startswith(ander + ":") or (":id:" in ander and iri.startswith(ander + "%2F"))


def in_selectie(iri: str, selectie: list[str]) -> bool:
    """Al gedekt door de selectie: gelijk, erbinnen, of het omvattende artikel ervan."""
    return any(_binnen(iri, s) or _binnen(s, iri) for s in selectie)


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


def _deelvraag(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    """Per deelvraag de gerichte bepalingen, binnen de regelingen van de selectie. Zonder kern zijn de treffers kern;
    met een kern aanverwant: de analist beslist wat bij de deelvraag hoort.

    Met een gekozen gebeurtenis (zoekvragen a–d, PR 5) komen ze uit de pool vanaf de gebeurtenis
    (`zoekvragen.pool`, één keer per run): wat een inhoudswoord van de deelvraag raakt, met de zoekvraag die de
    vraagvorm aanwijst als voorkeur (`zoekvragen.opties_bij_deelvraag`). Levert de pool te weinig, dan vult het
    zoeken op de woorden van de deelvraag (`bepaling_opties`) aan. Zonder gebeurtenis alleen dat laatste, zoals
    voorheen. Zonder gekozen regelingen zijn de regelingen van de gebeurtenis het bereik, niet de hele graaf."""
    from .deelvraag_zoeken import MAX_PER_DEELVRAAG
    from .zoekvragen import PLAATSEN_WOORDEN, opties_bij_deelvraag, pool

    rol = "aanverwant" if invoer.get("kern") else "kern"
    regelingen = regelingen_van_invoer(invoer)
    dossier = {"naam": invoer.get("naam", ""), "analysevraag": invoer.get("analysevraag", ""),
               **(invoer.get("dossier") or {})}
    buiten = uitsluitstammen(buiten_uit_afbakening(dossier.get("afbakening", "")))
    gebeurtenis = (dossier.get("gebeurtenis") or "").strip()
    p = pool(graph, gebeurtenis=gebeurtenis, regelingen=regelingen, buiten=buiten) if gebeurtenis else None
    if p is not None and not regelingen:
        regelingen = p["regelingen"]
    n_totaal, volledig = 0, p is None or p["volledig"]
    for d in invoer.get("deelvragen") or []:
        basis = {"deelvraag_id": d.get("id", ""), "vraag": d.get("vraag", "")}
        woorden = bepaling_opties(graph, regelingen=regelingen, deelvraag=d.get("vraag", ""), dossier=dossier,
                                  buiten=buiten)
        uit_pool: list[dict[str, Any]] = []
        if p is not None:
            plaatsen = MAX_PER_DEELVRAAG - min(PLAATSEN_WOORDEN, len([b for b in woorden if not b["buiten"]]))
            uit_pool = opties_bij_deelvraag(p["kandidaten"], d.get("vraag", ""), gebeurtenis=gebeurtenis,
                                            limit=plaatsen, dossier=dossier)
        for k in uit_pool:
            if v.voeg(k["bron_iri"], rol=rol, methode="deelvraag",
                      detail={**basis, "raakt": k["geraakt"], "zoekvraag": k["zoekvraag"], "signaal": k["signaal"],
                              "route": "zoekvragen"}):
                n_totaal += 1
        al = {k["bron_iri"] for k in uit_pool}
        ruimte = MAX_PER_DEELVRAAG - len(uit_pool)
        for b in woorden:
            if b["bron_iri"] in al:
                continue
            if not b["buiten"]:
                if ruimte <= 0:
                    continue
                ruimte -= 1
            if v.voeg(b["bron_iri"], rol=rol, methode="deelvraag", label=b["label"],
                      detail={**basis, "raakt": b["geraakt"], **({"buiten": True} if b["buiten"] else {}),
                              **({"route": "woorden"} if p else {})}):
                n_totaal += 1
    return n_totaal, volledig


def _grondslag(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    """Zoekvraag a (`zoekvragen.grondslag`): waar de gebeurtenis die de analist koos haar bestaansrecht krijgt,
    binnen de regelingen van de selectie. Rol kern: het is het vertrekpunt van de keten a–d. Het bewijs draagt de
    zoekvraag, de gebeurtenis, het signaal en de kop waaronder de bepaling staat."""
    from .zoekvragen import MAX_GRONDSLAG, grondslag, regelingen_van_gebeurtenis

    dossier = invoer.get("dossier") or {}
    gebeurtenis = (dossier.get("gebeurtenis") or "").strip()
    if not gebeurtenis:
        return 0, True
    # Zonder gekozen regelingen: de regelingen waarvan een kop de gebeurtenis draagt, niet de hele graaf.
    regelingen = regelingen_van_invoer(invoer) or regelingen_van_gebeurtenis(graph, gebeurtenis)
    if not regelingen:
        return 0, True
    buiten = uitsluitstammen(buiten_uit_afbakening(dossier.get("afbakening", "")))
    gevonden = grondslag(graph, gebeurtenis=gebeurtenis, regelingen=regelingen, buiten=buiten)
    n = 0
    for k in gevonden:
        n += v.voeg(k["bron_iri"], rol="kern", methode="grondslag",
                    detail={"zoekvraag": "a", "gebeurtenis": gebeurtenis, "signaal": k["signaal"],
                            "zin": k["zin"], **({"kop": k["onder_kop"]} if k.get("onder_kop") else {})})
    return n, len(gevonden) < MAX_GRONDSLAG


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


def regelingen_van_invoer(invoer: dict[str, Any]) -> list[str]:
    """Het zoekbereik van een run: de regelingen die de analist koos (`werkgebied.regelingen`, 4 nov 2026), dan die
    van de selectie. Leeg = geen bereik gekozen; de methode kiest dan zelf (de gebeurtenis, of de hele graaf)."""
    return list(dict.fromkeys([*(invoer.get("regelingen") or []),
                               *(b["bwb_id"] for b in invoer.get("kern", []) + invoer.get("context", [])
                                 if b.get("bwb_id"))]))


def definities_in(graph: GraphPort, teksten: list[dict[str, Any]], bwb_ids: list[str],
                  limit: int = MAX_PER_METHODE) -> tuple[list[dict[str, Any]], bool]:
    """De begripsbepalingen (`bwb:definieertBegrip`) in deze regelingen waarvan de term letterlijk in een van de
    teksten staat (`{deel, tekst}`): per definitie de node, de term, het label en het deel waarin de term staat.
    Gedeeld door de methode `definitie` (de teksten van de kern) en de zoekvragen (zoekvraag d: de teksten van a–c).
    (lijst, volledig)."""
    if not bwb_ids or not teksten:
        return [], True
    defs = _rijen(graph, q_definities(sorted(set(bwb_ids)), 500))
    uit: list[dict[str, Any]] = []
    for d in defs[:500]:
        term = d.get("begrip", "").strip()
        waar = next((t for t in teksten if _term_in(term, t.get("tekst", ""))), None)
        if waar is None or len(uit) >= limit:
            continue
        uit.append({"node": d["node"], "begrip": term, "label": d.get("label", ""), "deel": waar.get("deel", "")})
    return uit, len(defs) <= 500 and len(uit) < limit


def _definitie(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    kern = [k["bron_iri"] for k in invoer.get("kern", [])]
    if not kern:
        return 0, True
    bwb_ids = sorted({_bwb(k) for k in kern if _bwb(k)})
    if not bwb_ids:
        return 0, True
    gevonden, volledig = definities_in(graph, _rijen(graph, q_teksten(kern)), bwb_ids)
    n = 0
    for d in gevonden:
        n += v.voeg(d["node"], rol="afhankelijkheid", methode="definitie", vanuit=d["deel"],
                    label=d["label"], detail={"begrip": d["begrip"]})
    return n, volledig and n < MAX_PER_METHODE


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
    "definitie": _definitie, "opbouw": _opbouw, "gelijkenis": _gelijkenis, "grondslag": _grondslag,
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
