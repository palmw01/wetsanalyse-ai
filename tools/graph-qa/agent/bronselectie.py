"""De bronselectie per deelvraag in het gesprek (spoor J): kaartjes uit de stand bij de api, en een klik
die een besluit of een stap wordt.

Lex begeleidt, de applicatie onthoudt. De stand – welke deelvraag actief is, in welke fase, wat er besloten
is – staat bij de api (`/v1/werkgebieden/{id}/bronselectie`), niet in de checkpointer: elke beurt leest hem
vers. Zo werkt hervatten na herladen, in een ander gesprek of bij een collega, en is een tussenvraag geen
onderbreking: de stand verandert er niet door. Er draait hier geen model. De volgorde is een vaste cyclus per
deelvraag, en de volgende deelvraag kiest de api:

- `bs_gebeurtenis` – om welke gebeurtenis het gaat, in de term van de wet ("kwijtschelding"): het vertrekpunt van
  de zoekvragen a–d (skill `references/zoekvragen-bronselectie.md`). Lex stelt voor uit de koppen van de regelingen
  (`zoekvragen.gebeurtenis_opties`, zonder model); de keuze staat op het werkgebied (`gebeurtenis`). Gevraagd bij het
  begin, als ze nog leeg is, of als de analist er zelf om vraagt ("bepaal de gebeurtenis");
- `bs_kies` – met welke deelvraag gaan we verder (de volgende staat aangevinkt);
- `bs_bepalingen` – fase A en B: de kernbepalingen bij deze deelvraag. Het kaartje is compact (3 nov 2026): het
  telt wat er ligt, de analist beslist in het paneel, en *Klaar* gaat verder;
- `bs_afhankelijkheden` – fase C: wat aan een opgenomen bron hangt (definitie, verwijzing, opbouw), als context;
- `bs_afronden` – fase D: wat er ligt en wat openstaat; voorlopig afronden, beoordelen, verder onderzoeken;
- `bs_verder` – *Hoe wil je verder?*: de volgende deelvraag, deze verder onderzoeken of het overzicht.

Kiezen is het besluit: wat bij *Klaar* onbeslist is, is niet gekozen (de api leidt dat af uit de fase), en er is geen
*later*. Een eigen tekst op een bepalingenkaartje is een bepaling die de analist zelf toevoegt ("artikel 25 lid 2
Invorderingswet 1990": artikel en lid uit de tekst, de regeling uit de tekst of – als er één is – uit het
werkgebied); op het afrondkaartje is het een onderzoekspunt, dat de deelvraag uit *beoordeeld* houdt. Iets
toevoegen kan later altijd: de vragen van de deelvraag opnieuw doorlopen.

Een besluit is idempotent bij de api, dus een dubbele klik doet geen kwaad: Lex verwerkt het op de stand van nu
en toont het kaartje dat daarbij hoort.
"""
from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Any, Awaitable, Callable

ANALYSEVRAAG = "analysevraag"

KAARTSTAPPEN = ("bs_gebeurtenis", "bs_kies", "bs_bepalingen", "bs_afhankelijkheden", "bs_afronden", "bs_verder")
FASE_STAP = {"kern": "bs_bepalingen", "afhankelijkheden": "bs_afhankelijkheden", "afronden": "bs_afronden"}

STAND_TEKST = {"niet_gestart": "nog niet gestart", "in_behandeling": "in behandeling",
               "voorlopig_afgerond": "voorlopig afgerond", "beoordeeld": "beoordeeld"}
SLOT = ("De bronselectie is beoordeeld binnen de vastgestelde afbakening en de beschikbare bronnen. "
        "Dat is geen oordeel dat de analyse juridisch volledig is; de vaststelling blijft aan jou.")

Zoek = Callable[[str], Awaitable[str]]
#: De gebeurtenissen die Lex voorstelt bij een werkgebied en zijn regelingen (`zoekvragen.gebeurtenis_opties`).
StelVoor = Callable[[dict[str, Any], list[str]], list[dict[str, Any]]]
#: De woordenkloof en het voorwerp toetsen (`zoekvragen.ontbrekende_woorden`, `is_voorwerp`, `brugtermen`): het
#: werkgebied, zijn regelingen, de woorden en of het voorwerp getoetst moet worden → `{voorwerp, ontbrekend, brug}`.
Toets = Callable[[dict[str, Any], list[str], list[str], bool], dict[str, Any]]
#: De toets van deze beurt: gezet door `start` en `verwerk`, gelezen waar Lex zegt dat hij niets vond.
_TOETS: ContextVar[Toets | None] = ContextVar("bronselectie_toets", default=None)


def intake_id(werkgebied_id: str) -> str:
    """Eén reeks kaartjes per werkgebied, ook over gesprekken heen."""
    return f"bs-{werkgebied_id}"[:64]


def werkgebied_van(iid: str) -> str:
    return iid.removeprefix("bs-")


# "Help mij de bronnen bij dit werkgebied te bepalen", "verder met de bronselectie": een vaste vorm, dus geen model.
# Zonder deze regel nam het startzinpatroon van het samenstellen ("werkgebied … bepalen") de zin over.
# Sinds de losse zoekknop weg is, hoort ook "zoek bepalingen bij de deelvragen" hier (alleen binnen een werkgebied;
# "welke artikelen gaan over X?" noemt geen handeling en blijft het overzicht).
_HANDELING_BS = r"(?:bepalen|selecteren|kiezen|doorlopen|vaststellen|beoordelen|zoeken|zoek|vinden)"
_BRONSELECTIE = re.compile(
    rf"\bbronselectie\b"
    rf"|\b(?:bronnen|bepalingen)\b.*\b{_HANDELING_BS}\b"
    rf"|\b{_HANDELING_BS}\b.*\b(?:bronnen|bepalingen)\b", re.I)


def is_bronselectievraag(vraag: str) -> bool:
    return bool(_BRONSELECTIE.search(vraag or ""))


def deelvraag_nr_in(tekst: str) -> int | None:
    m = re.search(r"\bdeelvraag\s+(\d{1,2})\b", tekst or "", re.IGNORECASE)
    return int(m.group(1)) if m else None


def _kort(t: str, n: int) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _dq(ov: dict[str, Any], did: str) -> dict[str, Any] | None:
    return next((d for d in ov.get("deelvragen") or [] if d["id"] == did), None)


def _naam(d: dict[str, Any]) -> str:
    return "de analysevraag" if d["id"] == ANALYSEVRAAG else f"deelvraag {d['nr']}"


def stand_tekst(d: dict[str, Any]) -> str:
    t = d.get("telling") or {}
    delen = [STAND_TEKST.get(d["status"], d["status"]) + (" – opnieuw bekijken" if d.get("opnieuw_bekijken") else "")]
    if t.get("opgenomen"):
        delen.append(f"{t['opgenomen']} opgenomen")
    if t.get("voorgesteld"):
        delen.append(f"{t['voorgesteld']} open")
    if d.get("open_punten"):
        delen.append(f"{len(d['open_punten'])} onderzoekspunt{'en' if len(d['open_punten']) != 1 else ''}")
    return " · ".join(delen)


def beperkingen(ov: dict[str, Any]) -> list[str]:
    """Wat er over het zoeken te zeggen is. Een afgekapte of mislukte methode is een open punt, nooit een
    stil kleinere lijst."""
    z = ov.get("zoekdekking") or {}
    uit = []
    if not z.get("gezocht"):
        uit.append("Er is nog niet gezocht" + (f": {z['reden']}" if z.get("reden") else "") + ".")
    if z.get("verouderd"):
        uit.append("De laatste zoekopdracht hoort bij een eerdere stand van het werkgebied.")
    if z.get("onvolledig"):
        uit.append("Niet alles is doorzocht (" + ", ".join(z["onvolledig"]) + "): de lijst kan onvolledig zijn.")
    return uit


def _basis(werkgebied_id: str, stap: str, d: dict[str, Any] | None, ov: dict[str, Any]) -> dict[str, Any]:
    vragen = ov.get("deelvragen") or []
    nr = d["nr"] if d else 1
    return {"intake_id": intake_id(werkgebied_id), "modus": "bronselectie", "soort": "vraag", "stap": stap,
            "deelvraag_id": d["id"] if d else "", "nr": nr, "totaal": max(1, len(vragen)), "deel": None,
            "toelichting": "", "opties": [], "meerkeuze": False, "vrije_tekst": False, "meer_tekst": False,
            "overslaanbaar": False, "vooringevuld": [], "samenvatting": {}, "terug": False, "beantwoord": False}


def kaart_kies(werkgebied_id: str, ov: dict[str, Any]) -> dict[str, Any]:
    voorkeur = ov.get("actief") or ov.get("volgende")
    begonnen = any(d["status"] != "niet_gestart" for d in ov["deelvragen"])
    return {**_basis(werkgebied_id, "bs_kies", _dq(ov, voorkeur or "") , ov), "nr": 1, "totaal": 1,
            "vraag": "Met welke deelvraag gaan we verder?" if begonnen else "Met welke deelvraag beginnen we?",
            "opties": [{"label": _kort(f"{d['nr']}. {d['vraag']}", 300), "waarde": d["id"], "bron": {},
                        "omschrijving": _kort(stand_tekst(d), 300)} for d in ov["deelvragen"][:20]],
            "vooringevuld": [voorkeur] if voorkeur else [], "deelvraag_id": ""}


def kaart_gebeurtenis(werkgebied_id: str, ov: dict[str, Any], opties: list[dict[str, Any]],
                     deelvraag_id: str = "", voorwerp: bool = False) -> dict[str, Any]:
    """Om welke gebeurtenis gaat het? De opties uit de koppen van de regelingen, met de koppen als omschrijving;
    de huidige keuze (of anders de eerste) staat aangevinkt. Een eigen term mag; overslaan ook."""
    huidig = (ov.get("gebeurtenis") or "").strip()
    lijst = [{"label": _kort(o["gebeurtenis"], 300), "waarde": _kort(o["gebeurtenis"], 200), "bron": {},
              "omschrijving": _kort("; ".join(o.get("koppen") or []), 300)} for o in opties[:8]]
    if huidig and huidig.casefold() not in {o["waarde"].casefold() for o in lijst}:
        lijst.insert(0, {"label": huidig, "waarde": huidig, "bron": {}, "omschrijving": "nu gekozen"})
    toelichting = ("Ik zoek de bronnen vanaf de handeling zoals de wet haar noemt: eerst waar ze geregeld is, dan de "
                   "voorwaarden en de procedure, de gevolgen en de uitleg. De voorstellen komen uit de koppen van de "
                   "regelingen. Kies er één, of typ de term van de wet.")
    if voorwerp and huidig:
        onder = [o["gebeurtenis"] for o in opties if o.get("onder_voorwerp")][:3]
        toelichting = (f"‘{huidig}’ staat in geen kop van de regelingen: het is vermoedelijk een voorwerp, geen "
                       "handeling, en daarvan uit vind ik de bepalingen niet."
                       + (f" De bepalingen waarin het staat, vallen onder: {', '.join(onder)}." if onder else "")
                       + " Kies de handeling, of typ de term van de wet.")
    return {**_basis(werkgebied_id, "bs_gebeurtenis", None, ov), "nr": 1, "totaal": 1, "deelvraag_id": deelvraag_id,
            "vraag": "Om welke gebeurtenis gaat het?", "toelichting": toelichting, "opties": lijst,
            "vooringevuld": [huidig or lijst[0]["waarde"]] if lijst else [], "vrije_tekst": True, "overslaanbaar": True}


def _past(stap: str) -> Callable[[dict[str, Any]], bool]:
    """Welke kandidaten bij een fase horen: de kernbepalingen, of wat eraan hangt."""
    return (lambda k: k["rol"] == "kern") if stap == "bs_bepalingen" else (lambda k: k["rol"] != "kern")


def _telling(d: dict[str, Any], stap: str) -> tuple[int, int]:
    """(open, opgenomen) bij deze fase: open is voorgesteld of eerder niet gekozen. Een uitgesloten bepaling telt
    niet: ze komt niet terug."""
    past = _past(stap)
    open_ = sum(1 for k in d["kandidaten"] if k["stand"] in ("voorgesteld", "niet_gekozen") and past(k))
    aan = sum(1 for k in d["kandidaten"] if k["stand"] == "opgenomen" and past(k))
    return open_, aan


def kaart_bepalingen(werkgebied_id: str, ov: dict[str, Any], d: dict[str, Any], stap: str = "bs_bepalingen",
                     melding: str = "") -> dict[str, Any] | None:
    """Het kaartje van de kernbepalingen of van wat eraan hangt: compact (3 nov 2026, besluit gebruiker). Het
    gesprek blijft rustig, zoals een artefact bij Claude: het kaartje noemt hoeveel er ligt en verwijst naar het
    paneel (`weergave: paneel`), waar de jurist de tekst leest en per bepaling opneemt of uitsluit. *Klaar* (`actie:
    klaar`) raakt geen besluit; wat dan nog onbeslist is, is niet gekozen (de api leidt het af uit de fase).
    Een eigen tekst blijft een bepaling die de analist zelf toevoegt."""
    open_, aan = _telling(d, stap)
    if not open_ and not aan:
        return None
    kern = stap == "bs_bepalingen"
    wie = _naam(d)
    vraag = (f"De kernbepalingen bij {wie}" if kern else f"Wat hangt aan de bepalingen van {wie}?")
    if d["id"] != ANALYSEVRAAG and kern:
        vraag += f": {_kort(d['vraag'], 300)}"
    toelichting = [melding] if melding else []
    toelichting.append(
        f"Ik vond {open_} {'kandidaatbron' if open_ == 1 else 'kandidaatbronnen'}"
        + (f" en {aan} {'staat' if aan == 1 else 'staan'} al opgenomen" if aan else "")
        + ". Beoordeel ze in het paneel: lees de tekst en neem op of sluit uit. "
        + ("Klaar? Dan zoek ik wat eraan hangt." if kern else "Wat je opneemt, komt erbij als contextbron. "
           "Klaar? Dan ronden we af."))
    toelichting += beperkingen(ov)
    return {**_basis(werkgebied_id, stap, d, ov), "vraag": _kort(vraag, 500),
            "toelichting": _kort(" ".join(toelichting), 1000), "weergave": "paneel",
            "samenvatting": {"kandidaten": open_, "opgenomen": aan},
            "vrije_tekst": True, "overslaanbaar": False}


def afrond_tekst(d: dict[str, Any], ov: dict[str, Any]) -> str:
    t = d.get("telling") or {}
    delen = [f"Bij {_naam(d)} {'is' if t.get('opgenomen') == 1 else 'zijn'} {t.get('opgenomen', 0)} "
             f"{'bron' if t.get('opgenomen') == 1 else 'bronnen'} opgenomen"]
    if t.get("voorgesteld"):
        delen.append(f"{t['voorgesteld']} {'voorstel staat' if t['voorgesteld'] == 1 else 'voorstellen staan'} nog open")
    if t.get("niet_gekozen"):
        delen.append(f"{t['niet_gekozen']} niet gekozen")
    if t.get("uitgesloten"):
        delen.append(f"{t['uitgesloten']} uitgesloten")
    zin = ", ".join(delen) + "."
    if d.get("open_punten"):
        zin += " Onderzoekspunten: " + "; ".join(p["tekst"] for p in d["open_punten"]) + "."
    for b in beperkingen(ov):
        zin += " " + b
    return zin


def kaart_afronden(werkgebied_id: str, ov: dict[str, Any], d: dict[str, Any]) -> dict[str, Any]:
    opties = [{"label": "Voorlopig afronden", "waarde": "afronden", "bron": {},
               "omschrijving": "Wat openstaat blijft staan; de deelvraag telt als afgerond, niet als beoordeeld."}]
    if d["beoordelen"]["mag"]:
        opties.append({"label": "Als beoordeeld vastleggen", "waarde": "beoordelen", "bron": {},
                       "omschrijving": "Er staat niets meer open bij deze deelvraag."})
    opties += [{"label": "Verder onderzoeken", "waarde": "onderzoeken", "bron": {},
                "omschrijving": "Opnieuw zoeken en de voorstellen nog eens langs."},
               {"label": "Naar het overzicht van de deelvragen", "waarde": "overzicht", "bron": {},
                "omschrijving": "Kiezen waar we verder gaan."}]
    redenen = "" if d["beoordelen"]["mag"] else " Beoordelen kan nog niet: " + " ".join(d["beoordelen"]["redenen"])
    return {**_basis(werkgebied_id, "bs_afronden", d, ov), "vraag": f"Hoe rond je {_naam(d)} af?",
            "toelichting": _kort(afrond_tekst(d, ov) + redenen + " Een eigen tekst noteer ik als onderzoekspunt.", 1000),
            "opties": opties, "vrije_tekst": True, "vooringevuld": ["afronden"]}


def kaart_verder(werkgebied_id: str, ov: dict[str, Any], d: dict[str, Any]) -> dict[str, Any]:
    opties = []
    volgende = _dq(ov, ov.get("volgende") or "")
    if volgende:
        opties.append({"label": f"Verder met {_naam(volgende)}", "waarde": f"verder:{volgende['id']}", "bron": {},
                       "omschrijving": _kort(volgende["vraag"] + " · " + stand_tekst(volgende), 300)})
    if ov.get("alle_klaar"):
        opties.append({"label": "De bronselectie controleren", "waarde": "controle", "bron": {},
                       "omschrijving": "Zoekdekking, juridische dekking en wat nog niet beoordeeld is."})
    opties.append({"label": f"{_naam(d).capitalize()} verder onderzoeken", "waarde": f"heropen:{d['id']}", "bron": {},
                   "omschrijving": "De deelvraag weer in behandeling nemen."})
    if ov["modus"] == "deelvragen":
        opties.append({"label": "Terug naar het overzicht van de deelvragen", "waarde": "overzicht", "bron": {},
                       "omschrijving": "Zelf kiezen waar we verder gaan."})
    return {**_basis(werkgebied_id, "bs_verder", d, ov), "vraag": "Hoe wil je verder met de bronselectie?",
            "opties": opties, "vooringevuld": [opties[0]["waarde"]]}


def controle_tekst(ov: dict[str, Any]) -> str:
    """De overkoepelende controle, uit code: drie soorten dekking, elk apart. Nooit 'volledig'."""
    vragen = ov["deelvragen"]
    open_ = sum((d.get("telling") or {}).get("voorgesteld", 0) for d in vragen)
    punten = [p["tekst"] for d in vragen for p in d.get("open_punten") or []]
    zonder_bron = [_naam(d) for d in vragen if not d["bronnen"]]
    zonder_afh = [_naam(d) for d in vragen if d["bronnen"] and not any(k["rol"] != "kern" for k in d["kandidaten"])]
    regels = ["**Zoekdekking.** " + (" ".join(beperkingen(ov)) or "Alle zoekmethoden zijn uitgevoerd en niets was afgekapt.")]
    jur = []
    if zonder_bron:
        jur.append("geen bron bij " + ", ".join(zonder_bron))
    if zonder_afh:
        jur.append("geen definities of verwijzingen gevonden bij " + ", ".join(zonder_afh))
    regels.append("**Juridische dekking.** " + ("; ".join(jur).capitalize() + "." if jur else
                  "Elke deelvraag heeft een bron, en bij elke is naar afhankelijkheden gezocht.")
                  + " De functie van een verwijzing (uitzondering, delegatie, toepassing) leid ik af uit de tekst ervoor; "
                    "of ze echt nodig is, beoordeel je zelf.")
    beo = [f"{d['nr']}. {STAND_TEKST.get(d['status'], d['status'])}" for d in vragen if d["status"] != "beoordeeld"]
    regels.append("**Beoordelingsdekking.** " + (f"{open_} voorstel{'len' if open_ != 1 else ''} nog open. " if open_ else "")
                  + (f"Nog niet beoordeeld: {', '.join(beo)}. " if beo else "Elke deelvraag is beoordeeld. ")
                  + (f"Onderzoekspunten: {'; '.join(punten)}." if punten else ""))
    zonder = ov.get("zonder_deelvraag") or []
    if zonder:
        regels.append(f"{len(zonder)} voorstel{'len' if len(zonder) != 1 else ''} hoort bij geen enkele deelvraag; "
                      "die staan in het paneel.")
    regels.append(SLOT if not (open_ or beo or punten) else
                  "De bronselectie is nog niet beoordeeld binnen de afbakening; hierboven staat wat openstaat.")
    return "\n\n".join(regels)


# --- de beurt -----------------------------------------------------------------------------------

async def _open(api, wid: str, did: str) -> dict[str, Any]:
    return await api.zet_bronselectie_status(wid, did, {"actie": "openen"})


def _andere_zoekcode(z: dict[str, Any]) -> bool:
    """Of de laatste zoekopdracht met andere zoekcode liep dan die van nu (`bronnen_run.ZOEKVERSIE`). Een api die de
    versie niet meldt, telt niet als anders."""
    from .bronnen_run import ZOEKVERSIE

    return "zoekversie" in z and z["zoekversie"] != ZOEKVERSIE


async def _gezocht(api, wid: str, ov: dict[str, Any], zoek: Zoek | None, did: str, *, opnieuw: bool = False) -> tuple[dict, str]:
    """Zoek als er nog niet (op deze stand, met deze zoekcode) gezocht is; geeft het verse overzicht en een melding."""
    z = ov.get("zoekdekking") or {}
    if zoek is None or (z.get("gezocht") and not z.get("verouderd") and not _andere_zoekcode(z) and not opnieuw):
        return ov, ""
    melding = await zoek(did)
    return await api.haal_bronselectie(wid, na=did), melding


async def _fase(api, wid: str, ov: dict, did: str, fase: str) -> dict:
    d = _dq(ov, did)
    if d is None or d["status"] != "in_behandeling" or d["fase"] == fase:
        return ov
    return await api.zet_bronselectie_status(wid, did, {"actie": "fase", "fase": fase,
                                                         "verwachte_revisie": d["revisie"]})


async def _punt(api, wid: str, ov: dict, did: str, tekst: str) -> tuple[dict, bool]:
    """Een eigen tekst als onderzoekspunt bij een deelvraag in behandeling. (overzicht, vastgelegd)."""
    d = _dq(ov, did)
    tekst = " ".join((tekst or "").split())[:1000]
    if d is None or not tekst or d["status"] != "in_behandeling":
        return ov, False
    if any(p["tekst"] == tekst for p in d["open_punten"]):
        return ov, True
    punten = [*d["open_punten"], {"tekst": tekst}]
    return await api.zet_bronselectie_status(wid, did, {"actie": "fase", "fase": d["fase"],
                                                         "verwachte_revisie": d["revisie"], "open_punten": punten}), True


async def _toon_fase(api, wid: str, ov: dict, did: str, zoek: Zoek | None, zinnen: list[str],
                     *, opnieuw: bool = False) -> dict[str, Any]:
    """Het kaartje van de fase waar deze deelvraag staat; een lege fase slaat Lex over, met een zin."""
    ov, melding = await _gezocht(api, wid, ov, zoek, did, opnieuw=opnieuw)
    d = _dq(ov, did)
    if d is None:
        return {"kaart": kaart_kies(wid, ov), "zinnen": zinnen + ["Die deelvraag is er niet meer."]}
    if d["status"] in ("voorlopig_afgerond", "beoordeeld"):
        return {"kaart": kaart_verder(wid, ov, d), "zinnen": zinnen}
    if d["fase"] == "kern":
        k = kaart_bepalingen(wid, ov, d, "bs_bepalingen", melding=melding)
        if k:
            return {"kaart": k, "zinnen": zinnen}
        zinnen.append(f"Bij {_naam(d)} vond ik geen kernbepalingen" + (f" ({melding})" if melding else "") +
                      ". Je kunt er zelf een noemen; ik noteer het als onderzoekspunt.")
        from .zoekvragen import termen_van_deelvraag
        if d["id"] != ANALYSEVRAAG and (kloof := await _kloof(api, wid, ov, termen_van_deelvraag(d["vraag"]))):
            zinnen.append(kloof)
        ov = await _fase(api, wid, ov, did, "afhankelijkheden")
        d = _dq(ov, did) or d
    if d["fase"] == "afhankelijkheden":
        k = kaart_bepalingen(wid, ov, d, "bs_afhankelijkheden")
        if k:
            return {"kaart": k, "zinnen": zinnen}
        if d["bronnen"]:
            zinnen.append("Aan de opgenomen bepalingen hangt niets wat ik in de graaf kan aanwijzen.")
        ov = await _fase(api, wid, ov, did, "afronden")
        d = _dq(ov, did) or d
    return {"kaart": kaart_afronden(wid, ov, d), "zinnen": zinnen}


_OM_GEBEURTENIS = re.compile(r"\bgebeurtenis\b", re.I)


async def _vraag_gebeurtenis(api, wid: str, ov: dict[str, Any], stel_voor: StelVoor | None, vraag: str,
                             deelvraag_id: str) -> dict[str, Any] | None:
    """Het kaartje van de gebeurtenis, als het aan de orde is: ze is nog leeg en de analist begon nog niet aan een
    deelvraag, of hij vraagt er zelf om. Zonder voorstel (geen regeling, de graaf hapert) en zonder keuze vraagt
    Lex niets: hij zoekt dan zoals voorheen."""
    if stel_voor is None:
        return None
    gevraagd = bool(_OM_GEBEURTENIS.search(vraag or ""))
    begonnen = any(d["status"] != "niet_gestart" for d in ov["deelvragen"])
    gekozen = (ov.get("gebeurtenis") or "").strip()
    toets = _TOETS.get()
    if not gevraagd and (begonnen or gekozen) and not (gekozen and toets):
        return None
    wg = await api.haal_werkgebied(wid)
    regelingen = _regelingen(wg, ov)
    # Een gekozen gebeurtenis die in geen kop staat ("bankrekening"): het kaartje opnieuw, ook als de analist al
    # begon – de keten a–d vindt vanaf een voorwerp niets.
    voorwerp = bool(gekozen and toets and toets(wg, regelingen, [], True).get("voorwerp"))
    if not gevraagd and (begonnen or gekozen) and not voorwerp:
        return None
    opties = stel_voor(wg, regelingen)
    if not opties and not (gekozen or gevraagd):
        return None
    return kaart_gebeurtenis(wid, ov, opties, deelvraag_id, voorwerp=voorwerp)


def _regelingen(wg: dict[str, Any], ov: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys([b["bwb_id"] for b in wg.get("bronnen") or [] if b.get("bwb_id")] + regelingen_van(ov)))


async def _kloof(api, wid: str, ov: dict[str, Any], woorden: list[str]) -> str:
    """De zin over eigen woorden die in de regelingen niet voorkomen, met wat het dossier ernaast zet; leeg zonder
    toets of zonder zulke woorden. "Rekeningafspraak" is een begrip uit de uitvoering: zeg dat, in plaats van alleen
    "geen kernbepalingen"."""
    toets = _TOETS.get()
    if toets is None or not woorden:
        return ""
    wg = await api.haal_werkgebied(wid)
    t = toets(wg, _regelingen(wg, ov), woorden, False)
    zinnen = []
    for w in t.get("ontbrekend") or []:
        brug = (t.get("brug") or {}).get(w) or []
        zinnen.append(f"‘{w}’ staat niet in de regelingen van dit werkgebied: vermoedelijk een begrip uit de uitvoering."
                      + (f" In je dossier staat het naast {', '.join(brug)}; daarmee zoek ik." if brug else
                         " Noem in het dossier welke woorden van de wet erbij horen."))
    return " ".join(zinnen)


async def start(api, wid: str, zoek: Zoek | None, vraag: str = "", deelvraag_id: str = "",
                stel_voor: StelVoor | None = None, toets: Toets | None = None) -> dict[str, Any]:
    """Beginnen of hervatten: wat er ligt, en het kaartje waar de analist was. Een genoemde deelvraag
    ("deelvraag 4", of aangewezen in de werkplek) gaat voor.

    Heeft het werkgebied nog geen gebeurtenis en is de analist nog niet begonnen, dan eerst die vraag
    (`bs_gebeurtenis`); de aangewezen deelvraag reist mee op het kaartje.

    Is het werkgebied veranderd sinds de laatste zoekopdracht (het dossier, de selectie), dan zoekt Lex eerst
    opnieuw: pas daarna weet de api welke afgeronde deelvraag er door de nieuwe voorstellen weer open staat."""
    if toets is not None:
        _TOETS.set(toets)
    ov = await api.haal_bronselectie(wid)
    if (kaart := await _vraag_gebeurtenis(api, wid, ov, stel_voor, vraag, deelvraag_id)) is not None:
        return {"kaart": kaart, "zinnen": [f"*{ov['naam']}*: voor we de bronnen zoeken, eerst de gebeurtenis."]}
    melding = ""
    z = ov.get("zoekdekking") or {}
    if z.get("verouderd") or (z.get("gezocht") and _andere_zoekcode(z)):
        ov, melding = await _gezocht(api, wid, ov, zoek, "")
    vragen = ov["deelvragen"]
    nr = deelvraag_nr_in(vraag)
    if nr and ov["modus"] == "deelvragen" and 1 <= nr <= len(vragen):
        deelvraag_id = vragen[nr - 1]["id"]
    if ov["modus"] == "analysevraag":
        deelvraag_id = ANALYSEVRAAG
    klaar = sum(1 for d in vragen if d["klaar"])
    zinnen = []
    if ov["modus"] == "deelvragen":
        zinnen.append(f"*{ov['naam']}* heeft {len(vragen)} {'deelvraag' if len(vragen) == 1 else 'deelvragen'}"
                      + (f"; {klaar} {'is' if klaar == 1 else 'zijn'} afgerond." if klaar else "."))
    else:
        zinnen.append(f"*{ov['naam']}* heeft geen deelvragen; we zoeken de bronnen bij de analysevraag.")
    zinnen.append("Per deelvraag zoek ik de kernbepalingen, dan wat eraan hangt, en dan rond je af. "
                  "Je kunt tussendoor alles vragen; de stand blijft bewaard.")
    from .zoekvragen import termen_van_deelvraag
    from .zoektermen import zoektermen as _woorden

    # De vorm uit de vragen eerst ("rekeningafspraak"), de naam ("Rekeningafspraken") daarna.
    eigen = [w for d in vragen if d["id"] != ANALYSEVRAAG for w in termen_van_deelvraag(d["vraag"])] + \
        termen_van_deelvraag(ov.get("analysevraag") or "") + _woorden(ov.get("naam") or "")
    if (kloof := await _kloof(api, wid, ov, eigen)):
        zinnen.append(kloof)
    if melding:
        zinnen.append(f"Opnieuw zoeken lukte niet: {melding}.")
    if deelvraag_id and _dq(ov, deelvraag_id):
        ov = await _open(api, wid, deelvraag_id)
        d = _dq(ov, deelvraag_id)
        zinnen.append(f"We beginnen bij {_naam(d)}." if ov["modus"] == "deelvragen" else "")
        return await _toon_fase(api, wid, ov, deelvraag_id, zoek, [z for z in zinnen if z])
    if ov.get("actief"):
        d = _dq(ov, ov["actief"])
        zinnen.append(f"We waren bij {_naam(d)}: {d['vraag']}")
        ov = await _open(api, wid, d["id"])
        return await _toon_fase(api, wid, ov, d["id"], zoek, zinnen)
    if ov.get("alle_klaar"):
        zinnen.append("Alle deelvragen zijn afgerond.")
        return {"kaart": kaart_verder(wid, ov, vragen[-1]), "zinnen": zinnen}
    return {"kaart": kaart_kies(wid, ov), "zinnen": zinnen}


def regelingen_van(ov: dict[str, Any]) -> list[str]:
    """De BWB-id's waar dit werkgebied over gaat: van de opgenomen bronnen en de voorstellen."""
    iris = [b["bron_iri"] for d in ov["deelvragen"] for b in d["bronnen"]] + \
        [k["bron_iri"] for d in ov["deelvragen"] for k in d["kandidaten"]]
    return sorted({i.split(":")[2] for i in iris if i.startswith("urn:bwb:") and i.count(":") >= 2})


async def _zelf(api, wid: str, ov: dict, did: str, stap: str, tekst: str,
                vind: Callable[[str], list[str]] | None) -> tuple[dict, list[str], bool]:
    """Een eigen tekst op een bepalingenkaartje: de bepaling(en) toevoegen bij deze deelvraag. (overzicht,
    zinnen, gelukt) – niet gelukt laat het kaartje staan, zodat de analist het kan verbeteren."""
    from .wetsanalyse_api import WetsanalyseApiFout

    from .bepaling_namen import bepalingen_uit_tekst

    verzoeken = bepalingen_uit_tekst(tekst, vind or (lambda _t: []), regelingen_van(ov))
    if isinstance(verzoeken, str):
        return ov, [verzoeken], False
    if not verzoeken:
        return ov, ["Ik zie geen artikel in je tekst. Noem de bepaling, bijvoorbeeld ‘artikel 9 lid 2 Invorderingswet "
                    "1990’; een onderzoekspunt noteer je bij het afronden."], False
    rol = "analyseren" if stap == "bs_bepalingen" else "context"
    zinnen, gelukt = [], False
    for v in verzoeken:
        naam = f"artikel {v['artikel']}" + (f" lid {v['lid']}" if v.get("lid") else "")
        try:
            ov = await api.voeg_bepaling_toe(wid, did, {**v, "rol": rol, "verwachte_revisie": ov["revisie"]})
            zinnen.append(f"Zelf toegevoegd: {naam}.")
            gelukt = True
        except WetsanalyseApiFout as fout:
            if fout.status not in (409, 422):
                raise
            zinnen.append(f"{naam.capitalize()} kon ik niet toevoegen" + (
                ": die staat niet in de kennisgraaf." if fout.status == 422 else f" ({fout.reden or 'conflict'})."))
    return ov, zinnen, gelukt


async def _kies_gebeurtenis(api, wid: str, ov: dict[str, Any], actie: dict[str, Any], keuzes: list[str], tekst: str,
                            zoek: Zoek | None, stel_voor: StelVoor | None) -> dict[str, Any]:
    """Een klik op het kaartje van de gebeurtenis: opslaan op het werkgebied (een eigen tekst gaat voor de keuze), of
    overslaan. Daarna gewoon verder, met de deelvraag die op het kaartje meereisde. Opslaan verandert de invoer van
    de bronnenrun, dus het zoeken begint opnieuw."""
    did = actie.get("deelvraag_id") or ""
    if actie.get("actie") == "overslaan":
        uit = await start(api, wid, zoek, deelvraag_id=did)
        return {**uit, "zinnen": ["Dan zoek ik zonder gebeurtenis; je kunt haar later nog kiezen.", *uit["zinnen"]]}
    gebeurtenis = " ".join((tekst or (keuzes[0] if keuzes else "")).split())[:200]
    if not gebeurtenis:
        kaart = await _vraag_gebeurtenis(api, wid, ov, stel_voor, "gebeurtenis", did)
        return {"kaart": kaart, "zinnen": ["Kies een gebeurtenis, typ de term van de wet of sla over."]}
    if gebeurtenis != (ov.get("gebeurtenis") or ""):
        await api.wijzig_werkgebied(wid, {"verwachte_revisie": ov["revisie"], "gebeurtenis": gebeurtenis})
    uit = await start(api, wid, zoek, deelvraag_id=did)
    return {**uit, "zinnen": [f"De gebeurtenis is *{gebeurtenis}*. Ik zoek de bronnen vanaf haar grondslag.",
                              *uit["zinnen"]]}


async def verwerk(api, actie: dict[str, Any], zoek: Zoek | None,
                  vind: Callable[[str], list[str]] | None = None, stel_voor: StelVoor | None = None,
                  toets: Toets | None = None) -> dict[str, Any]:
    """Een klik op een kaartje van de bronselectie. Geeft `{kaart?, zinnen, artefact_deelvraag?}`."""
    if toets is not None:
        _TOETS.set(toets)
    wid = werkgebied_van(str(actie.get("intake_id", "")))
    stap = actie.get("stap", "")
    keuzes = [str(x) for x in actie.get("keuzes") or []]
    tekst = (actie.get("tekst") or "").strip()
    did = actie.get("deelvraag_id") or ""
    if actie.get("actie") == "afbreken":
        return {"zinnen": ["Ik zet de bronselectie even stil; de stand blijft bewaard. Kies *Verder met de "
                           "bronselectie* of vraag het me als je verder wilt."]}
    ov = await api.haal_bronselectie(wid)
    if stap == "bs_gebeurtenis":
        return await _kies_gebeurtenis(api, wid, ov, actie, keuzes, tekst, zoek, stel_voor)
    if ov["modus"] == "analysevraag" and stap != "bs_kies":
        did = ANALYSEVRAAG
    if stap == "bs_kies":
        did = keuzes[0] if keuzes else ""
        nr = deelvraag_nr_in(tekst)
        if not did and nr and 1 <= nr <= len(ov["deelvragen"]):
            did = ov["deelvragen"][nr - 1]["id"]
        if not _dq(ov, did):
            return {"kaart": kaart_kies(wid, ov), "zinnen": ["Kies een van de deelvragen."]}
        ov = await _open(api, wid, did)
        d = _dq(ov, did)
        return {**await _toon_fase(api, wid, ov, did, zoek, [f"Dan {_naam(d)}: {d['vraag']}"]), "deelvraag": did}
    if stap == "bs_verder":
        keuze = keuzes[0] if keuzes else ""
        if keuze.startswith("verder:") and _dq(ov, keuze[7:]):
            did = keuze[7:]
            ov = await _open(api, wid, did)
            d = _dq(ov, did)
            return {**await _toon_fase(api, wid, ov, did, zoek, [f"Dan {_naam(d)}: {d['vraag']}"]), "deelvraag": did}
        if keuze.startswith("heropen:") and _dq(ov, keuze[8:]):
            did = keuze[8:]
            d = _dq(ov, did)
            if d["status"] in ("voorlopig_afgerond", "beoordeeld"):
                ov = await api.zet_bronselectie_status(wid, did, {"actie": "heropenen", "verwachte_revisie": d["revisie"]})
            ov = await _open(api, wid, did)
            ov = await _fase(api, wid, ov, did, "kern")
            return {**await _toon_fase(api, wid, ov, did, zoek, [f"We kijken nog eens naar {_naam(d)}."],
                                       opnieuw=True), "deelvraag": did}
        if keuze == "controle":
            return {"zinnen": [controle_tekst(ov)], "kaart": kaart_kies(wid, ov) if ov["modus"] == "deelvragen" else None}
        return {"kaart": kaart_kies(wid, ov), "zinnen": []}
    d = _dq(ov, did)
    if d is None:
        return {"kaart": kaart_kies(wid, ov), "zinnen": ["Deze deelvraag is er niet meer (of niet meer actief)."]}
    if d["status"] == "niet_gestart":
        ov = await _open(api, wid, did)
    zinnen: list[str] = []
    if stap in ("bs_bepalingen", "bs_afhankelijkheden"):
        # *Klaar* (het compacte kaartje): de besluiten staan al bij de api, via het paneel. Een getypte bepaling
        # voegt de analist zelf toe; het kaartje blijft dan staan (hij beoordeelt verder in het paneel en zegt dan
        # *Klaar*), want een toegevoegde bepaling schuift de fase niet door.
        if tekst and actie.get("actie") != "klaar":
            ov, uit, _ = await _zelf(api, wid, ov, did, stap, tekst, vind)
            zinnen += uit
            k = kaart_bepalingen(wid, ov, _dq(ov, did), stap)
            if k:
                return {"kaart": k, "zinnen": zinnen, "deelvraag": did}
        volgende_fase = "afhankelijkheden" if stap == "bs_bepalingen" else "afronden"
        ov = await _fase(api, wid, ov, did, volgende_fase)
        # Met nieuwe bronnen in de selectie hoort er een nieuwe zoekopdracht bij: wat eraan hangt.
        return {**await _toon_fase(api, wid, ov, did, zoek, zinnen), "deelvraag": did}
    if stap == "bs_afronden":
        if tekst:
            ov, genoteerd = await _punt(api, wid, ov, did, tekst)
            zinnen.append(f"Genoteerd als onderzoekspunt: ‘{_kort(tekst, 200)}’." if genoteerd else
                          "Deze deelvraag is afgerond; heropen haar om een onderzoekspunt toe te voegen.")
        keuze = keuzes[0] if keuzes else ("" if tekst else "afronden")
        d = _dq(ov, did)
        if not keuze:
            return {"kaart": kaart_afronden(wid, ov, d), "zinnen": zinnen, "deelvraag": did}
        if keuze == "overzicht":
            return {"kaart": kaart_kies(wid, ov), "zinnen": zinnen}
        if keuze == "onderzoeken":
            ov = await _fase(api, wid, ov, did, "kern")
            return {**await _toon_fase(api, wid, ov, did, zoek, zinnen + ["We kijken nog eens."], opnieuw=True),
                    "deelvraag": did}
        if keuze == "beoordelen" and not d["beoordelen"]["mag"]:
            zinnen.append("Beoordelen kan nog niet: " + " ".join(d["beoordelen"]["redenen"]))
            return {"kaart": kaart_afronden(wid, ov, d), "zinnen": zinnen, "deelvraag": did}
        ov = await api.zet_bronselectie_status(wid, did, {"actie": "beoordelen" if keuze == "beoordelen" else "afronden",
                                                           "verwachte_revisie": d["revisie"]})
        d = _dq(ov, did)
        zinnen.append(f"{_naam(d).capitalize()} is {'beoordeeld' if keuze == 'beoordelen' else 'voorlopig afgerond'}.")
        if ov.get("alle_klaar"):
            zinnen.append("Alle deelvragen zijn nu afgerond. Ik kan de bronselectie als geheel controleren.")
        return {"kaart": kaart_verder(wid, ov, d), "zinnen": zinnen, "deelvraag": did}
    return {"kaart": kaart_kies(wid, ov), "zinnen": zinnen}
