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
| `lid_verwijzing` | een ander lid van hetzelfde artikel dat een kernlid noemt ("in afwijking van het derde lid") of dat het kernlid noemt; de graaf kent die verwijzingen binnen een artikel niet – standaard uit (meting) | afhankelijkheid |
| `opschrift` | een artikel in dezelfde regeling waarvan het opschrift ("Voorschot op tegemoetkoming") met zijn eerste woorden in de tekst van de kern staat | afhankelijkheid |
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
from contextvars import ContextVar
from typing import Any, Callable

from .graph import queries
from .graph.queries import BEVAT, NS, PREFIXES, STRUCTUUR, _iri_veilig, _lit
from .bepaling_namen import _benoem, bwb_van as _bwb, rijen as _rijen
from .deelvraag_zoeken import STANDAARD_PROFIEL, Zoekprofiel, bepaling_opties
from bronmodel.taal import RANGTELWOORDEN, rangnummers

from .ports import GraphPort
from .zoektermen import buiten_stammen, zoektermen

logger = logging.getLogger(__name__)

METHODEN = ("overzicht", "deelvraag", "verwijzing_uit", "verwijzing_in", "definitie", "opschrift", "lid_verwijzing",
            "beleidsregel", "artikelleden", "opbouw", "gelijkenis", "grondslag")
#: Wat standaard draait als er een kern is – gekozen op de meting van 15 okt 2026
#: (`docs/architectuur/metingen/bronselectie-2026-10-15/`): met een kern voegde het overzicht geen
#: recall toe maar wel 36 onbeoordeelde "kern"-kandidaten, en `verwijzing_in` leverde alle uitgesloten
#: bepalingen (rente, verrekening) voor één aanverwant Leidraad-onderdeel. `gelijkenis` voegde niets toe.
#: Een methode die niet aantoonbaar helpt, staat niet standaard aan.
#: `opschrift` kwam erbij na de bronnenrun op acceptatie van 18 nov 2026 (LB-08): de kern ("Indien voorschotten zijn
#: verleend …", "een herziening van een tegemoetkoming") verwees nergens naar, en artikel 16 ("Voorschot op
#: tegemoetkoming") en 20 ("Herziening tegemoetkoming …") vond geen methode.
#: `lid_verwijzing` kwam erbij na de meting van de afhankelijkheden van 18 nov 2026
#: (`docs/architectuur/metingen/bronselectie-2026-11-18-afhankelijkheden/`): vijf nodige bepalingen meer voor 37
#: kandidaten meer, op geen set slechter. `verwijzing_in` vond er vier, voor 77 kandidaten meer, en blijft uit.
#: `beleidsregel` kwam erbij na de meting van 18 nov 2026 (`bronselectie-2026-11-18-beleidsregel/`): zes nodige
#: bepalingen meer (de Leidraad bij het kernartikel) voor 46 kandidaten meer, op geen set slechter.
STANDAARD = ("verwijzing_uit", "definitie", "opschrift", "lid_verwijzing", "beleidsregel", "opbouw")
#: Zonder kern is de analysevraag het enige vertrekpunt: dan het overzicht.
ZONDER_KERN = ("overzicht",)


#: Het zoekprofiel van deze run (`vind(profiel=)`); de methoden lezen het met `_profiel()`. Zo meet de eval een vlag op
#: een hele run, en draait de dienst het standaardprofiel.
_PROFIEL: ContextVar[Zoekprofiel] = ContextVar("bronnen_zoekprofiel", default=STANDAARD_PROFIEL)


def _profiel() -> Zoekprofiel:
    return _PROFIEL.get()


#: Het model van deze run voor `Zoekprofiel.model_kiest` (`vind(llm=, model=)`): `(llm, model, meting)`, of None. Zonder
#: model kiest de code, zoals vóór de proef: een run zonder llm (een test, de eval zonder `--model-kiest`) verandert niet.
_MODEL: ContextVar[tuple[Any, str, dict[str, Any]] | None] = ContextVar("bronnen_model", default=None)
#: Kiest het model één keer voor het hele werkgebied (`vind(per_werkgebied=)`)? None = de instelling
#: `deelvraag_keuze.PER_WERKGEBIED` (standaard uit).
_PER_WERKGEBIED: ContextVar[bool | None] = ContextVar("bronnen_per_werkgebied", default=None)


def standaard_voor(invoer: dict[str, Any]) -> tuple[str, ...]:
    """Met deelvragen (optioneel, ze staan alleen in de invoer als het werkgebied ze heeft) zoekt Lex
    ook per deelvraag: de analist vroeg er zelf om, en de dekkingscheck meet ertegen. Met een gekozen
    gebeurtenis (`dossier.gebeurtenis`) zoekt hij de grondslag erbij, om dezelfde reden: de analist koos haar."""
    basis = STANDAARD if invoer.get("kern") else ZONDER_KERN
    if _profiel().overzicht_streng and invoer.get("deelvragen"):
        # Met deelvragen zijn die het vertrekpunt: het overzicht op de naam of de analysevraag gaf alleen ruis zonder
        # deelvraag (Termijnen, 16 nov 2026: 40 Awb-artikelen over beslistermijnen als kern).
        basis = tuple(m for m in basis if m != "overzicht")
    if invoer.get("deelvragen"):
        basis += ("deelvraag",)
    if ((invoer.get("dossier") or {}).get("gebeurtenis") or "").strip():
        basis += ("grondslag",)
    return basis

MAX_PER_METHODE = 60
MAX_OVERZICHT = 40
MAX_OPBOUW_PER_KERN = 30
MAX_GELIJKENIS = 10
#: Hoeveel opschriften de methode `opschrift` per run leest (de Leidraad heeft er ruim duizend).
MAX_OPSCHRIFTEN = 3000
#: Hoeveel woorden van een opschrift in de kern moeten staan: de eerste twee inhoudswoorden, of het ene.
OPSCHRIFT_WOORDEN = 2
#: Een woord van het opschrift telt vanaf zoveel letters ("Partner", "Verrekening"; niet "Kind" of "late").
MIN_OPSCHRIFT_WOORD = 5
#: Een kop die bij meer artikelen past, is niet onderscheidend ("Herziening tegemoetkoming" past bij 20, 21 en 21a).
MAX_PER_KOP = 3
#: Hoeveel onderdelen van één beleidsregel de methode `beleidsregel` per kern voorstelt (de Leidraad bij artikel 49 van
#: de Invorderingswet 1990 heeft er dertig).
MAX_PER_BELEIDSREGEL = 6
#: Hoeveel andere leden van het artikel van een kernlid de methode `artikelleden` voorstelt.
MAX_ARTIKELLEDEN = 12
#: Hoeveel onderdelen van beleidsregels de methode per run leest.
MAX_BELEIDSONDERDELEN = 2000

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


def q_opschriften(bwb_ids: list[str]) -> str:
    filters = " || ".join(f'STRSTARTS(STR(?artikel), {_lit(NS + b + ":")})' for b in sorted(set(bwb_ids)))
    return PREFIXES + f"""SELECT DISTINCT ?artikel ?titel ?label WHERE {{
  ?artikel a bwb:Artikel ; bwb:titel ?titel .
  FILTER({filters})
  OPTIONAL {{ ?artikel rdfs:label ?label }}
}} ORDER BY ?artikel LIMIT {MAX_OPSCHRIFTEN + 1}"""


def q_beleidsregels(artikelen: list[str], kern: list[str]) -> str:
    """De beleidsregels bij de kern en hun onderdelen (standaard aan sinds de meting van 18 nov 2026). Een beleidsregel is een knoop met onderdelen (`heeftDivisie`) die
    zelf naar het artikel van de kern verwijst ("In aansluiting op artikel 49 van de wet beschrijft dit artikel het
    beleid over:"), of het artikel van een beleidsregel waarin de kern zelf staat. Per onderdeel de titel, en of het naar
    een kernbepaling verwijst (`?naar`)."""
    return PREFIXES + f"""SELECT DISTINCT ?regel ?onderdeel ?titel ?label ?naar WHERE {{
  {{ VALUES ?artikel {{ {_waarden(artikelen)} }}
     ?regel bwb:verwijstNaar ?artikel ; bwb:heeftDivisie ?eerste . }}
  UNION
  {{ VALUES ?k {{ {_waarden(kern)} }}
     ?regel bwb:heeftDivisie+ ?k .
     FILTER(CONTAINS(STR(?regel), ":artikel:")) }}
  ?regel bwb:heeftDivisie+ ?onderdeel .
  OPTIONAL {{ ?onderdeel bwb:titel ?titel }}
  OPTIONAL {{ ?onderdeel rdfs:label ?label }}
  OPTIONAL {{ VALUES ?naar {{ {_waarden(kern)} }}
              ?onderdeel bwb:heeftVerwijzing ?v . ?v bwb:naar ?naar . }}
}} ORDER BY ?regel ?onderdeel LIMIT {MAX_BELEIDSONDERDELEN + 1}"""


def q_leden(artikelen: list[str]) -> str:
    """De leden van deze artikelen met hun eigen tekst (een lid zonder eigen tekst staat er ook, met lege tekst)."""
    return PREFIXES + f"""SELECT ?artikel ?lid ?tekst WHERE {{
  VALUES ?artikel {{ {_waarden(artikelen)} }}
  ?artikel bwb:heeftLid ?lid .
  OPTIONAL {{ ?lid bwb:tekst ?tekst }}
}} ORDER BY ?artikel ?lid"""


def q_lid_onderdelen(artikelen: list[str]) -> str:
    """De tekst van de onderdelen onder de leden van deze artikelen: een verwijzing staat vaak in een onderdeel."""
    return PREFIXES + f"""SELECT ?lid ?tekst WHERE {{
  VALUES ?artikel {{ {_waarden(artikelen)} }}
  ?artikel bwb:heeftLid ?lid .
  ?lid bwb:heeftOnderdeel+ ?o .
  ?o bwb:tekst ?tekst .
}} ORDER BY ?lid ?o"""


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
    naam_telt = not _profiel().overzicht_streng or len(zoektermen(naam)) > 1
    onderwerp = (onderwerp_uit(vraag) if vraag else "") or (naam if naam_telt else "") or vraag
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
            if v.voeg(b["iri"], rol="aanverwant" if _profiel().overzicht_streng else "kern", methode="overzicht", label=b.get("label") or b.get("naam", ""),
                      detail={"onderwerp": ov.get("onderwerp_tekst") or onderwerp}):
                n += 1
    return n, volledig


def _deelvraag(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    """Per deelvraag de gerichte bepalingen, binnen het zoekbereik. Een treffer bij een deelvraag is een kernbepaling
    van díé deelvraag – ook als er elders al bronnen zijn opgenomen (4 nov 2026: voorheen werd hij dan `aanverwant`,
    viel hij buiten het kernkaartje en zei Lex "geen kernbepalingen"). De analist beslist in het paneel.

    Met een gekozen gebeurtenis (zoekvragen a–d, PR 5) komen ze uit de pool vanaf de gebeurtenis
    (`zoekvragen.pool`, één keer per run): wat een inhoudswoord van de deelvraag raakt, met de zoekvraag die de
    vraagvorm aanwijst als voorkeur (`zoekvragen.opties_bij_deelvraag`). Levert de pool te weinig, dan vult het
    zoeken op de woorden van de deelvraag (`bepaling_opties`) aan. Zonder gebeurtenis alleen dat laatste, zoals
    voorheen. Zonder gekozen regelingen zijn de regelingen van de gebeurtenis het bereik, niet de hele graaf."""
    from .deelvraag_zoeken import MAX_PER_DEELVRAAG
    from .zoekvragen import PLAATSEN_WOORDEN, opties_bij_deelvraag, pool, samen_met_woorden

    rol = "kern"
    profiel = _profiel()
    regelingen = regelingen_van_invoer(invoer)
    dossier = {"naam": invoer.get("naam", ""), "analysevraag": invoer.get("analysevraag", ""),
               **(invoer.get("dossier") or {}),
               # Alleen gelezen met `Zoekprofiel.onderscheidend` (B-2, standaard uit).
               "deelvragen": [str(d.get("vraag") or "") for d in invoer.get("deelvragen") or []]}
    buiten = buiten_stammen(dossier, dossier.get("deelvragen"), profiel.afbakening_onderdelen)
    gebeurtenis = (dossier.get("gebeurtenis") or "").strip()
    p = pool(graph, gebeurtenis=gebeurtenis, regelingen=regelingen, buiten=buiten) if gebeurtenis else None
    if p is not None and not regelingen:
        regelingen = p["regelingen"]
    n_totaal, volledig = 0, p is None or p["volledig"]
    deelvragen = invoer.get("deelvragen") or []
    # De wetstermen één keer per deelvraag (`Zoekprofiel.wetstermen`), voor de keuze per werkgebied en per deelvraag.
    wetten = [_wetstermen(graph, d.get("vraag", ""), regelingen, dossier) for d in deelvragen]
    per_werkgebied = _werkgebied_kiest(graph, deelvragen, regelingen, dossier, buiten, p, gebeurtenis, wetten)
    for i, d in enumerate(deelvragen):
        basis = {"deelvraag_id": d.get("id", ""), "vraag": d.get("vraag", "")}
        wet = wetten[i]
        if wet:
            basis["wetstermen"] = wet
        if per_werkgebied is not None:
            for k in per_werkgebied[i]:
                gevonden_bij = [deelvragen[j].get("id", "") for j in k.get("gevonden_bij", [])]
                n_totaal += v.voeg(k["bron_iri"], rol=k["rol"], methode="deelvraag", label=k["label"],
                                   detail={**basis, "route": "model_werkgebied", "bron": k["bron"],
                                           "gevonden_bij": gevonden_bij})
            continue
        gekozen = _model_kiest(graph, d.get("vraag", ""), regelingen, dossier, buiten, p, gebeurtenis, wet)
        if gekozen is not None:
            for k in gekozen:
                n_totaal += v.voeg(k["bron_iri"], rol=k["rol"], methode="deelvraag", label=k["label"],
                                   detail={**basis, "route": "model", "bron": k["bron"]})
            continue
        woorden = bepaling_opties(graph, regelingen=regelingen, deelvraag=d.get("vraag", ""), dossier=dossier,
                                  buiten=buiten, profiel=profiel, wetstermen=wet)
        uit_pool: list[dict[str, Any]] = []
        if p is not None:
            plaatsen = MAX_PER_DEELVRAAG - min(PLAATSEN_WOORDEN, len([b for b in woorden if not b["buiten"]]))
            uit_pool = opties_bij_deelvraag(p["kandidaten"], d.get("vraag", ""), gebeurtenis=gebeurtenis,
                                            limit=MAX_PER_DEELVRAAG if profiel.woorden_voor_pool else plaatsen,
                                            dossier=dossier, profiel=profiel, wetstermen=wet)
        for k in samen_met_woorden(uit_pool, woorden, limit=MAX_PER_DEELVRAAG,
                                   woorden_voor_pool=profiel.woorden_voor_pool):
            if k["bron"] == "pool":
                nieuw = v.voeg(k["bron_iri"], rol=rol, methode="deelvraag",
                               detail={**basis, "raakt": k["geraakt"], "zoekvraag": k["zoekvraag"],
                                       "signaal": k["signaal"], "route": "zoekvragen"})
            else:
                nieuw = v.voeg(k["bron_iri"], rol=rol, methode="deelvraag", label=k["label"],
                               detail={**basis, "raakt": k["geraakt"], **({"buiten": True} if k["buiten"] else {}),
                                       **({"route": "woorden"} if p else {})})
            n_totaal += nieuw
    return n_totaal, volledig


def _wetstermen(graph: GraphPort, vraag: str, regelingen: list[str], dossier: dict[str, Any]) -> list[str]:
    """De zoektermen in de taal van de wet bij één deelvraag (`Zoekprofiel.wetstermen`, `wetstermen.wetstermen`). Leeg
    als de vlag uit staat of de run geen model heeft: dan zoekt de code alleen op de woorden van de deelvraag."""
    model = _MODEL.get()
    if not _profiel().wetstermen or model is None:
        return []
    from .wetstermen import wetstermen

    llm, modelnaam, meting = model
    return wetstermen(graph, llm, modelnaam, vraag, dossier, regelingen, meting)


def _model_kiest(graph: GraphPort, vraag: str, regelingen: list[str], dossier: dict[str, Any], buiten: list[str],
                 p: dict[str, Any] | None, gebeurtenis: str,
                 wetstermen: list[str] | None = None) -> list[dict[str, Any]] | None:
    """Een model kiest de bepalingen bij één deelvraag (`Zoekprofiel.model_kiest`, meting
    `bronselectie-2026-11-17-model`): de code verzamelt de kandidaten uit de pool en de woordenroute, ruimer dan het
    kaartje, het model wijst er hoogstens `MAX_PER_DEELVRAAG` aan met hun rol. None als de vlag uit staat, de run geen
    model heeft of het model geen bruikbaar antwoord gaf: dan kiest de code."""
    from . import deelvraag_keuze

    model = _MODEL.get()
    if not _profiel().model_kiest or model is None:
        return None
    llm, modelnaam, meting = model
    kand = _kandidaten_bij(graph, vraag, regelingen, dossier, buiten, p, gebeurtenis, wetstermen)
    return deelvraag_keuze.kies(llm, modelnaam, vraag, dossier, kand, meting)


def _kandidaten_bij(graph: GraphPort, vraag: str, regelingen: list[str], dossier: dict[str, Any], buiten: list[str],
                    p: dict[str, Any] | None, gebeurtenis: str,
                    wetstermen: list[str] | None = None) -> list[dict[str, Any]]:
    """De kandidaten voor het model bij één deelvraag (`deelvraag_keuze.kandidaten`): de woordenroute en de pool rond de
    gebeurtenis, elk tot `MAX_KANDIDATEN`, om de beurt. `wetstermen` zoeken mee (`Zoekprofiel.wetstermen`)."""
    from dataclasses import replace

    from . import deelvraag_keuze
    from .zoekvragen import opties_bij_deelvraag

    # De verwijzingen hoeven hier niet mee: het model kiest uit wat de deelvraag zelf vindt.
    ruim = replace(_profiel(), verwijzingen=False)
    woorden = bepaling_opties(graph, regelingen=regelingen, deelvraag=vraag, dossier=dossier, buiten=buiten,
                              limit=deelvraag_keuze.MAX_KANDIDATEN, profiel=ruim, met_tekst=True,
                              wetstermen=wetstermen)
    uit_pool = opties_bij_deelvraag(p["kandidaten"], vraag, gebeurtenis=gebeurtenis,
                                    limit=deelvraag_keuze.MAX_KANDIDATEN, dossier=dossier,
                                    profiel=ruim, wetstermen=wetstermen) if p is not None else []
    return deelvraag_keuze.kandidaten(uit_pool, woorden, menging=ruim.menging)


def _werkgebied_kiest(graph: GraphPort, deelvragen: list[dict[str, Any]], regelingen: list[str],
                      dossier: dict[str, Any], buiten: list[str], p: dict[str, Any] | None,
                      gebeurtenis: str, wetten: list[list[str]] | None = None) -> list[list[dict[str, Any]]] | None:
    """Eén keuze voor alle deelvragen (`deelvraag_keuze.PER_WERKGEBIED`, of `vind(per_werkgebied=)`): de kandidaten van
    elke deelvraag samen, en het model zet elke bepaling bij de deelvraag die ze beantwoordt. Per deelvraag de gekozen
    kandidaten met hun rol, of None als de vorm uit staat, de run geen model heeft of het model geen bruikbaar antwoord
    gaf: dan kiest het model per deelvraag, zoals zonder de vlag."""
    from . import deelvraag_keuze

    model = _MODEL.get()
    aan = _PER_WERKGEBIED.get()
    if aan is None:
        aan = deelvraag_keuze.PER_WERKGEBIED
    if not aan or not _profiel().model_kiest or model is None or not deelvragen:
        return None
    llm, modelnaam, meting = model
    wetten = wetten or [[] for _ in deelvragen]
    per = [_kandidaten_bij(graph, d.get("vraag", ""), regelingen, dossier, buiten, p, gebeurtenis, wet)
           for d, wet in zip(deelvragen, wetten)]
    kand = deelvraag_keuze.kandidaten_werkgebied(per)
    return deelvraag_keuze.kies_werkgebied(llm, modelnaam, [d.get("vraag", "") for d in deelvragen], dossier, kand,
                                           meting)


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
    buiten = buiten_stammen({"naam": invoer.get("naam", ""), "analysevraag": invoer.get("analysevraag", ""), **dossier},
                            invoer.get("deelvragen"), _profiel().afbakening_onderdelen)
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


def opschrift_kop(titel: str) -> tuple[str, ...]:
    """De woorden van een opschrift die in de kern moeten staan: de eerste `OPSCHRIFT_WOORDEN` inhoudswoorden van
    minstens `MIN_OPSCHRIFT_WOORD` letters ("Voorschot op tegemoetkoming" → voorschot, tegemoetkoming; "Partner" →
    partner). Leeg als het opschrift niets onderscheidends draagt ("Kind")."""
    woorden = [w for w in zoektermen(titel) if not w.isdigit() and len(w) >= MIN_OPSCHRIFT_WOORD]
    return tuple(woorden[:OPSCHRIFT_WOORDEN])


def opschriften_in(teksten: list[dict[str, Any]], opschriften: list[dict[str, Any]], kern: list[str],
                   buiten: list[str]) -> list[dict[str, Any]]:
    """De artikelen waarvan de kop van het opschrift (`opschrift_kop`) in een tekst van de kern staat, elk woord op zijn
    stam (`raakt_heel`: "voorschot" raakt "voorschotten"). Niet het artikel van de kern zelf, niet een opschrift dat
    buiten de afbakening valt, en niet een kop die bij meer dan `MAX_PER_KOP` artikelen past. Zonder model, zoals de
    andere methoden: het bewijs is de kop en de tekst waarin hij staat."""
    from .zoektermen import raakt_heel, valt_buiten

    per_kop: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for o in opschriften:
        kop = opschrift_kop(o.get("titel", ""))
        if kop and not valt_buiten(o.get("titel", ""), buiten):
            per_kop.setdefault(kop, []).append(o)
    uit: list[dict[str, Any]] = []
    gezien: set[str] = set()
    for kop, artikelen in per_kop.items():
        if len(artikelen) > MAX_PER_KOP:
            continue
        waar = next((t for t in teksten if all(raakt_heel(w, (t.get("tekst") or "").casefold()) for w in kop)), None)
        if waar is None:
            continue
        for o in artikelen:
            a = o["artikel"]
            if a in gezien or any(_binnen(k, a) for k in kern):
                continue
            gezien.add(a)
            uit.append({"artikel": a, "titel": o.get("titel", ""), "label": o.get("label", ""),
                        "kop": " ".join(kop), "deel": waar.get("deel", "")})
    return uit


def _opschrift(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    kern = [k["bron_iri"] for k in invoer.get("kern", [])]
    bwb_ids = sorted({_bwb(k) for k in kern if _bwb(k)})
    if not kern or not bwb_ids:
        return 0, True
    opschriften = _rijen(graph, q_opschriften(bwb_ids))
    buiten = buiten_stammen({"naam": invoer.get("naam", ""), "analysevraag": invoer.get("analysevraag", ""),
                             **(invoer.get("dossier") or {})}, invoer.get("deelvragen"),
                            _profiel().afbakening_onderdelen)
    gevonden = opschriften_in(_rijen(graph, q_teksten(kern)), opschriften[:MAX_OPSCHRIFTEN], kern, buiten)
    n = 0
    for o in gevonden[:MAX_PER_METHODE]:
        n += v.voeg(o["artikel"], rol="afhankelijkheid", methode="opschrift", vanuit=o["deel"], label=o["label"],
                    detail={"opschrift": o["titel"], "kop": o["kop"]})
    return n, len(opschriften) <= MAX_OPSCHRIFTEN and len(gevonden) <= MAX_PER_METHODE


def artikel_van(iri: str) -> str:
    """Het artikel van een bepaling in de IRI-vorm (`…:artikel:24:lid:3` → `…:artikel:24`); anders de iri zelf."""
    m = re.match(r"^(.+?:artikel:[^:]+)(?::.*)?$", iri)
    return m.group(1) if m and ":id:" not in iri else iri


def beleidsonderdelen(rijen: list[dict[str, Any]], teksten: list[dict[str, Any]], kern: list[str],
                      buiten: list[str]) -> list[dict[str, Any]]:
    """Welke onderdelen van een beleidsregel bij de kern horen (`q_beleidsregels`): een onderdeel dat een kernbepaling
    noemt ("bedoeld in artikel 9, vijfde lid, van de wet"), en een onderdeel waarvan de kop van het opschrift
    (`opschrift_kop`) in een tekst van de kern staat ("Wanneer in gebreke" bij "in gebreke is met de betaling"). Van een
    onderdeel en een onderdeel daarbinnen dat ook past, blijft het binnenste; per beleidsregel hoogstens
    `MAX_PER_BELEIDSREGEL`, de genoemde eerst. Niet de kern zelf of wat de kern omvat, niet wat buiten de afbakening
    valt."""
    from .zoektermen import raakt_heel, valt_buiten

    per_onderdeel: dict[str, dict[str, Any]] = {}
    for r in rijen:
        d = r["onderdeel"]
        if d in kern or any(_binnen(k, d) or _binnen(d, k) for k in kern):
            continue
        o = per_onderdeel.setdefault(d, {"onderdeel": d, "regel": r["regel"], "titel": r.get("titel", ""),
                                         "label": r.get("label", ""), "noemt": ""})
        if r.get("naar") and not o["noemt"]:
            o["noemt"] = r["naar"]
    gekozen: list[dict[str, Any]] = []
    for o in per_onderdeel.values():
        if o["noemt"]:
            gekozen.append({**o, "grond": "noemt de kern", "deel": o["noemt"]})
            continue
        kop = opschrift_kop(o["titel"])
        if not kop or valt_buiten(o["titel"], buiten):
            continue
        waar = next((t for t in teksten if all(raakt_heel(w, (t.get("tekst") or "").casefold()) for w in kop)), None)
        if waar is not None:
            gekozen.append({**o, "grond": "opschrift", "kop": " ".join(kop), "deel": waar.get("deel", "")})
    iris = [g["onderdeel"] for g in gekozen]
    binnenste = [g for g in gekozen if not any(i != g["onderdeel"] and _binnen(i, g["onderdeel"]) for i in iris)]
    uit: list[dict[str, Any]] = []
    per_regel: dict[str, int] = {}
    for g in sorted(binnenste, key=lambda g: g["grond"] != "noemt de kern"):
        if per_regel.get(g["regel"], 0) >= MAX_PER_BELEIDSREGEL:
            continue
        per_regel[g["regel"]] = per_regel.get(g["regel"], 0) + 1
        uit.append(g)
    return uit


def _beleidsregel(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    """De onderdelen van de beleidsregel bij het artikel van de kern (de Leidraad Invordering bij de Invorderingswet).
    Bronnenrun op acceptatie, 18 nov 2026: de beleidsregels bij een kernartikel waren de grootste groep die geen methode
    vond (Leidraad 9.1–9.3, 24.6.3, 26.2.1, 49.3.1). Ze verwijzen naar het artikel, niet naar de kern, en `verwijzing_in`
    bracht de hele Leidraad mee."""
    kern = [k["bron_iri"] for k in invoer.get("kern", [])]
    if not kern:
        return 0, True
    artikelen = sorted({artikel_van(k) for k in kern})
    rijen = _rijen(graph, q_beleidsregels(artikelen, kern))
    if not rijen:
        return 0, True
    buiten = buiten_stammen({"naam": invoer.get("naam", ""), "analysevraag": invoer.get("analysevraag", ""),
                             **(invoer.get("dossier") or {})}, invoer.get("deelvragen"),
                            _profiel().afbakening_onderdelen)
    gevonden = beleidsonderdelen(rijen[:MAX_BELEIDSONDERDELEN], _rijen(graph, q_teksten(kern)), kern, buiten)
    n = 0
    for o in gevonden:
        detail = {"beleidsregel": o["regel"], "grond": o["grond"], **({"opschrift": o["titel"], "kop": o["kop"]}
                                                                       if o["grond"] == "opschrift" else {})}
        n += v.voeg(o["onderdeel"], rol="afhankelijkheid", methode="beleidsregel", vanuit=o["deel"], label=o["label"],
                    detail=detail)
    return n, len(rijen) <= MAX_BELEIDSONDERDELEN


_RANG = rangnummers(len(RANGTELWOORDEN))
_RANGWOORD = "|".join(sorted(_RANG, key=len, reverse=True))
#: Een of meer rangtelwoorden vóór "lid" of "leden": "het derde lid", "het eerste of tweede lid", "het derde tot en met
#: vijfde lid".
_LEDEN = re.compile(rf"\b((?:(?:{_RANGWOORD})(?:\s*,\s*|\s+en\s+|\s+of\s+|\s+tot\s+en\s+met\s+))*(?:{_RANGWOORD}))"
                    r"\s+(?:lid|leden)\b", re.I)
#: Een lid van een ánder artikel: "artikel 25, derde lid", "het derde lid van artikel 7", "… lid, van de Algemene wet".
_ANDER_ARTIKEL_VOOR = re.compile(r"\bartikel(?:en)?\s+[0-9][\w:.]*\s*,?\s*(?:\w+\s*,\s*)*$", re.I)
_ANDER_ARTIKEL_NA = re.compile(r"^\s*,?\s*(?:\w+\s+)?(?:van|uit)\s+(?:artikel|de|het|die|deze)\b(?!\s+artikel\b)", re.I)
_DIT_ARTIKEL_NA = re.compile(r"^\s*,?\s*(?:van|uit)\s+dit\s+artikel\b", re.I)


def lid_verwijzingen(tekst: str) -> dict[int, str]:
    """De leden van hetzelfde artikel die een tekst noemt, met het stuk tekst dat ze noemt: "In afwijking van het derde
    lid" → {3: "het derde lid"}. Niet een lid van een ander artikel ("artikel 25, derde lid", "het eerste lid van artikel
    7", "het vierde lid van de Algemene wet …"). Zonder graaf: de graaf kent deze verwijzingen binnen een artikel niet."""
    uit: dict[int, str] = {}
    for m in _LEDEN.finditer(tekst or ""):
        voor, na = tekst[max(0, m.start() - 40):m.start()], tekst[m.end():m.end() + 40]
        if _ANDER_ARTIKEL_VOOR.search(voor) or (_ANDER_ARTIKEL_NA.search(na) and not _DIT_ARTIKEL_NA.search(na)):
            continue
        woorden = re.findall(_RANGWOORD, m.group(1), re.I)
        nummers = [_RANG[w.lower()] for w in woorden]
        if re.search(r"tot\s+en\s+met", m.group(1), re.I) and len(nummers) == 2:
            nummers = list(range(nummers[0], nummers[1] + 1))
        for n in nummers:
            uit.setdefault(n, m.group(0))
    return uit


_KERNLID = re.compile(r"^(?P<artikel>.+:artikel:[^:]+):lid:(?P<lid>\d+)$")


def _artikelleden(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    """De andere leden van het artikel van een kernlid, als aanverwant: een artikel leest de jurist als geheel. Meting
    18 nov 2026 (plaatsdiagnose): van de 45 nodige bepalingen die niet bij de 80 kandidaten kwamen, stond bij 22 een
    ander lid van hetzelfde artikel wél op de lijst (Iw 24, Awb 4:15, Awir 24, AWR 67e)."""
    kern = [(m["artikel"], k["bron_iri"]) for k in invoer.get("kern", []) if (m := _KERNLID.match(k["bron_iri"]))]
    if not kern:
        return 0, True
    per_artikel: dict[str, list[str]] = {}
    for r in _rijen(graph, q_leden(sorted({a for a, _ in kern}))):
        per_artikel.setdefault(r["artikel"], []).append(r["lid"])
    n, volledig = 0, True
    for artikel, kern_iri in kern:
        leden = sorted((lid for lid in per_artikel.get(artikel, []) if lid != kern_iri and _KERNLID.match(lid)),
                       key=lambda lid: int(_KERNLID.match(lid)["lid"]))
        if len(leden) > MAX_ARTIKELLEDEN:
            volledig = False
        for lid in leden[:MAX_ARTIKELLEDEN]:
            n += v.voeg(lid, rol="aanverwant", methode="artikelleden", vanuit=kern_iri, detail={"artikel": artikel})
    return n, volledig


def _lid_verwijzing(graph: GraphPort, invoer: dict[str, Any], v: Verzameling) -> tuple[int, bool]:
    """De andere leden van het artikel van een kernlid die naar dat kernlid verwijzen ("in afwijking van het derde lid",
    een uitzondering of aanvulling) of waarnaar het kernlid verwijst ("bedoeld in het eerste lid"). Bronnenrun op
    acceptatie, 18 nov 2026: Iw 24 lid 4 en AWR 67n lid 3 noemen hun kernlid, en geen methode vond ze, omdat de graaf
    alleen verwijzingen naar andere artikelen kent."""
    kern = [(m["artikel"], int(m["lid"]), k["bron_iri"]) for k in invoer.get("kern", [])
            if (m := _KERNLID.match(k["bron_iri"]))]
    if not kern:
        return 0, True
    artikelen = sorted({a for a, _, _ in kern})
    teksten: dict[str, list[str]] = {}
    per_artikel: dict[str, list[str]] = {}
    for r in _rijen(graph, q_leden(artikelen)):
        per_artikel.setdefault(r["artikel"], []).append(r["lid"])
        teksten.setdefault(r["lid"], []).append(r.get("tekst", ""))
    for r in _rijen(graph, q_lid_onderdelen(artikelen)):
        teksten.setdefault(r["lid"], []).append(r.get("tekst", ""))
    n = 0
    for artikel, nummer, kern_iri in kern:
        kern_noemt = lid_verwijzingen(" ".join(teksten.get(kern_iri, [])))
        for lid in per_artikel.get(artikel, []):
            m = _KERNLID.match(lid)
            if not m or lid == kern_iri:
                continue
            eigen = int(m["lid"])
            noemt = lid_verwijzingen(" ".join(teksten.get(lid, [])))
            if nummer in noemt:
                n += v.voeg(lid, rol="afhankelijkheid", methode="lid_verwijzing", vanuit=kern_iri,
                            detail={"anker": noemt[nummer], "richting": "noemt de kern"})
            elif eigen in kern_noemt:
                n += v.voeg(lid, rol="afhankelijkheid", methode="lid_verwijzing", vanuit=kern_iri,
                            detail={"anker": kern_noemt[eigen], "richting": "de kern noemt het"})
            if n >= MAX_PER_METHODE:
                return n, False
    return n, True


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
    "definitie": _definitie, "opschrift": _opschrift, "lid_verwijzing": _lid_verwijzing,
    "beleidsregel": _beleidsregel, "artikelleden": _artikelleden, "opbouw": _opbouw, "gelijkenis": _gelijkenis, "grondslag": _grondslag,
}


def vind(graph: GraphPort, invoer: dict[str, Any], methoden: tuple[str, ...] | None = None,
         melding: Callable[[str, int, bool, int], None] | None = None,
         profiel: Zoekprofiel | None = None, llm: Any = None, model: str = "",
         modelmeting: dict[str, Any] | None = None, per_werkgebied: bool | None = None) -> dict[str, Any]:
    """De methoden op de invoer van een bronnenrun (`api/app/bronnen_run_store.invoer_van`); zonder
    `methoden` de standaard voor die invoer (`standaard_voor`). `profiel` is voor de meting; de dienst draait het
    standaardprofiel. Met `llm` kiest een model de bepalingen per deelvraag (`Zoekprofiel.model_kiest`); zonder kiest
    de code. `per_werkgebied` zet de keuze voor het hele werkgebied aan of uit (None: `deelvraag_keuze.PER_WERKGEBIED`).

    Een methode die faalt, laat de rest niet vallen: haar meting zegt `volledig: false`."""
    teken = _PROFIEL.set(profiel or STANDAARD_PROFIEL)
    teken_model = _MODEL.set((llm, model, modelmeting if modelmeting is not None else {}) if llm is not None else None)
    teken_wg = _PER_WERKGEBIED.set(per_werkgebied)
    try:
        return _vind(graph, invoer, methoden, melding)
    finally:
        _PER_WERKGEBIED.reset(teken_wg)
        _MODEL.reset(teken_model)
        _PROFIEL.reset(teken)


class _Teller:
    """De graaf voor één methode, met het aantal vragen dat ze stelde: een methode die niets te doen had (geen kernlid,
    geen gebeurtenis) stelt er geen, en telt bij totale uitval niet als bewijs dat de graaf bereikbaar is."""

    def __init__(self, graph: GraphPort) -> None:
        self._graph = graph
        self.vragen = 0

    def __getattr__(self, naam: str) -> Any:
        waarde = getattr(self._graph, naam)
        if not callable(waarde):
            return waarde

        def geteld(*a: Any, **k: Any) -> Any:
            self.vragen += 1
            return waarde(*a, **k)
        return geteld


def _vind(graph: GraphPort, invoer: dict[str, Any], methoden: tuple[str, ...] | None,
          melding: Callable[[str, int, bool, int], None] | None) -> dict[str, Any]:
    methoden = methoden or standaard_voor(invoer)
    selectie = [b["bron_iri"] for b in invoer.get("kern", []) + invoer.get("context", [])]
    v = Verzameling(selectie)
    meting: dict[str, dict[str, Any]] = {}
    for m in methoden:
        t0 = time.monotonic()
        fout = False
        teller = _Teller(graph)
        try:
            aantal, volledig = UITVOERING[m](teller, invoer, v)
        except Exception:  # noqa: BLE001 – een haperende query is een onvolledige methode, geen crash
            logger.warning("bronmethode faalde", extra={"categorie": "technisch", "methode": m}, exc_info=True)
            aantal, volledig, fout = 0, False, True
        ms = int((time.monotonic() - t0) * 1000)
        # `fout` en `zonder_vraag` zijn intern (de run maakt er bij totale uitval een storing van; een methode die niets te
        # doen had, zegt niets over de graaf); de api krijgt ze niet.
        meting[m] = {"aantal": aantal, "volledig": volledig, "ms": ms, **({"fout": True} if fout else {}),
                     **({"zonder_vraag": True} if not fout and not teller.vragen else {})}
        if melding:
            melding(m, aantal, volledig, ms)
    kandidaten = v.lijst()
    _benoem(graph, kandidaten)
    return {"kandidaten": kandidaten, "meting": meting}
