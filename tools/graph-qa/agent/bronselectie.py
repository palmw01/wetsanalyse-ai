"""De bronselectie per deelvraag in het gesprek (spoor J): kaartjes uit de stand bij de api, en een klik
die een besluit of een stap wordt.

Lex begeleidt, de applicatie onthoudt. De stand – welke deelvraag actief is, in welke fase, wat er besloten
is – staat bij de api (`/v1/werkgebieden/{id}/bronselectie`), niet in de checkpointer: elke beurt leest hem
vers. Zo werkt hervatten na herladen, in een ander gesprek of bij een collega, en is een tussenvraag geen
onderbreking: de stand verandert er niet door. Er draait hier geen model. De volgorde is een vaste cyclus per
deelvraag, en de volgende deelvraag kiest de api:

- `bs_kies` – met welke deelvraag gaan we verder (de volgende staat aangevinkt);
- `bs_bepalingen` – fase A en B: de kernbepalingen bij deze deelvraag, meerkeuze voor *opnemen*;
- `bs_afhankelijkheden` – fase C: wat aan een opgenomen bron hangt (definitie, verwijzing, opbouw), als context;
- `bs_afronden` – fase D: wat er ligt en wat openstaat; voorlopig afronden, beoordelen, verder onderzoeken;
- `bs_verder` – *Hoe wil je verder?*: de volgende deelvraag, deze verder onderzoeken of het overzicht.

Kiezen is het besluit: wat niet aangevinkt is, is niet gekozen (de api leidt dat af uit de fase), en er is geen
*later*. Een eigen tekst op een bepalingenkaartje is een bepaling die de analist zelf toevoegt ("artikel 25 lid 2
Invorderingswet 1990": artikel en lid uit de tekst, de regeling uit de tekst of – als er één is – uit het
werkgebied); op het afrondkaartje is het een onderzoekspunt, dat de deelvraag uit *beoordeeld* houdt. Iets
toevoegen kan later altijd: de vragen van de deelvraag opnieuw doorlopen.

Een besluit is idempotent bij de api, dus een dubbele klik of een oud kaartje doet geen kwaad: Lex verwerkt het
op de stand van nu en toont het kaartje dat daarbij hoort.
"""
from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

ANALYSEVRAAG = "analysevraag"
#: Hoogstens zoveel open voorstellen op één kaartje; de rest staat in het paneel, en het kaartje zegt hoeveel.
MAX_OPTIES = 8

KAARTSTAPPEN = ("bs_kies", "bs_bepalingen", "bs_afhankelijkheden", "bs_afronden", "bs_verder")
FASE_STAP = {"kern": "bs_bepalingen", "afhankelijkheden": "bs_afhankelijkheden", "afronden": "bs_afronden"}

STAND_TEKST = {"niet_gestart": "nog niet gestart", "in_behandeling": "in behandeling",
               "voorlopig_afgerond": "voorlopig afgerond", "beoordeeld": "beoordeeld"}
BEWIJS_TEKST = {"verwijzing": "aantoonbare verwijzing in de wet", "definitie": "definitie van een term die erin staat",
                "structuur": "staat in hetzelfde deel", "tekst": "tekstuele overeenkomst",
                "gelijkenis": "lijkt op de tekst (zwak signaal)"}
ROL_TEKST = {"kern": "kernbepaling", "afhankelijkheid": "afhankelijkheid", "aanverwant": "mogelijk relevant"}
SLOT = ("De bronselectie is beoordeeld binnen de vastgestelde afbakening en de beschikbare bronnen. "
        "Dat is geen oordeel dat de analyse juridisch volledig is; de vaststelling blijft aan jou.")

Zoek = Callable[[str], Awaitable[str]]


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


def waarom(k: dict[str, Any]) -> str:
    """De tweede regel onder een voorstel: rol en soort bewijs, uit code. Een tekstuele overeenkomst heet
    zo, en niet 'relevant'."""
    soorten = k.get("bewijs_soorten") or []
    vanuit = next((b.get("vanuit") for b in k.get("bewijs") or [] if b.get("vanuit")), "")
    bewijs = BEWIJS_TEKST.get(soorten[0], "") if soorten else ""
    if vanuit and soorten and soorten[0] in ("verwijzing", "definitie", "structuur"):
        bewijs += f" (vanuit {vanuit.rsplit(':', 2)[-2]} {vanuit.rsplit(':', 1)[-1]})" if vanuit.count(":") >= 3 else ""
    delen = [ROL_TEKST.get(k.get("rol", ""), ""), bewijs]
    if k.get("elders_opgenomen"):
        delen.append("al opgenomen bij een andere deelvraag")
    if k.get("stand") == "niet_gekozen":
        delen.append("eerder niet gekozen")
    return _kort(" · ".join(x for x in delen if x), 300)


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


def _opties_voor(d: dict[str, Any], stap: str) -> tuple[list[dict], list[str], int]:
    """(opties, vooringevuld, niet getoond). Opgenomen bronnen staan aangevinkt; daaronder de voorstellen, en bij
    opnieuw doorlopen ook wat eerder niet gekozen werd. Hoogstens `MAX_OPTIES`. Een uitgesloten bepaling komt
    niet terug."""
    kern = stap == "bs_bepalingen"
    past = (lambda k: k["rol"] == "kern") if kern else (lambda k: k["rol"] != "kern")
    opgenomen = [k for k in d["kandidaten"] if k["stand"] == "opgenomen" and past(k)]
    open_ = [k for k in d["kandidaten"] if k["stand"] == "voorgesteld" and past(k)] \
        + [k for k in d["kandidaten"] if k["stand"] == "niet_gekozen" and past(k)]
    getoond = open_[:MAX_OPTIES]
    opties = [{"label": _kort(k["label"] or k["bron_iri"], 300), "waarde": k["id"],
               "bron": {"bwb_id": k.get("bwb_id", ""), "iri": k["bron_iri"], "label": k["label"]},
               "omschrijving": waarom(k)} for k in (opgenomen + getoond)[:20]]
    return opties, [k["id"] for k in opgenomen][:20], len(open_) - len(getoond)


def kaart_bepalingen(werkgebied_id: str, ov: dict[str, Any], d: dict[str, Any], stap: str = "bs_bepalingen",
                     melding: str = "") -> dict[str, Any] | None:
    opties, aan, rest = _opties_voor(d, stap)
    if not opties:
        return None
    toelichting = [melding] if melding else []
    if stap == "bs_bepalingen":
        vraag = f"Welke bepalingen regelen {_naam(d)} zelf?" if d["id"] == ANALYSEVRAAG else \
            f"Welke bepalingen regelen deelvraag {d['nr']} zelf? {_kort(d['vraag'], 300)}"
        toelichting.append("Aangevinkt is wat al is opgenomen. Wat je niet aanvinkt, neem je niet op; je kunt de "
                           "vragen later opnieuw doorlopen.")
    else:
        vraag = f"Wat hangt aan de opgenomen bepalingen van {_naam(d)}?"
        toelichting.append("Definities, verwijzingen en bepalingen uit hetzelfde deel. Wat je aanvinkt, komt erbij "
                           "als contextbron.")
    if rest:
        toelichting.append(f"Nog {rest} {'voorstel staat' if rest == 1 else 'voorstellen staan'} in het paneel.")
    toelichting += beperkingen(ov)
    toelichting.append("Staat een bepaling er niet bij, typ haar dan zelf, bijvoorbeeld ‘artikel 9 lid 2 "
                       "Invorderingswet 1990’.")
    return {**_basis(werkgebied_id, stap, d, ov), "vraag": _kort(vraag, 500),
            "toelichting": _kort(" ".join(toelichting), 1000), "opties": opties, "meerkeuze": True,
            "vrije_tekst": True, "overslaanbaar": True, "vooringevuld": aan}


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
                  + " De functie van een verwijzing (uitzondering, delegatie) leid ik nog niet af; die beoordeel je zelf.")
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

class Api:
    """Wat de beurt van de api nodig heeft (`WetsanalyseApi` levert het; tests een nepversie)."""

    async def haal_bronselectie(self, werkgebied_id: str, na: str = "") -> dict[str, Any]: ...
    async def zet_bronselectie_status(self, werkgebied_id: str, deelvraag_id: str, actie: dict) -> dict[str, Any]: ...
    async def besluit_bronselectie(self, werkgebied_id: str, deelvraag_id: str, kandidaat_id: str,
                                   besluit: dict) -> dict[str, Any]: ...


async def _open(api, wid: str, did: str) -> dict[str, Any]:
    return await api.zet_bronselectie_status(wid, did, {"actie": "openen"})


async def _gezocht(api, wid: str, ov: dict[str, Any], zoek: Zoek | None, did: str, *, opnieuw: bool = False) -> tuple[dict, str]:
    """Zoek als er nog niet (op deze stand) gezocht is; geeft het verse overzicht en een melding."""
    z = ov.get("zoekdekking") or {}
    if zoek is None or (z.get("gezocht") and not z.get("verouderd") and not opnieuw):
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


async def start(api, wid: str, zoek: Zoek | None, vraag: str = "", deelvraag_id: str = "") -> dict[str, Any]:
    """Beginnen of hervatten: wat er ligt, en het kaartje waar de analist was. Een genoemde deelvraag
    ("deelvraag 4", of aangewezen in de werkplek) gaat voor."""
    ov = await api.haal_bronselectie(wid)
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


async def _neem_op(api, wid: str, ov: dict, did: str, stap: str, gekozen: list[str]) -> tuple[dict, list[str]]:
    """De keuze op een bepalingen-kaartje: aangevinkt = opgenomen bij deze deelvraag; een opgenomen bron die
    niet meer aangevinkt is, wordt losgekoppeld (bij de analysevraag blijft hij: weghalen gaat op de tab)."""
    d = _dq(ov, did)
    if d is None:
        return ov, []
    opties, _, _ = _opties_voor(d, stap)
    zichtbaar = {o["waarde"] for o in opties}
    per_id = {k["id"]: k for k in d["kandidaten"]}
    gekozen = [g for g in dict.fromkeys(gekozen) if g in per_id]
    zinnen = []
    for kid in gekozen:
        k = per_id[kid]
        if k["stand"] == "opgenomen":
            continue
        rol = "analyseren" if stap == "bs_bepalingen" and k["rol"] == "kern" else "context"
        ov = await api.besluit_bronselectie(wid, did, kid, {"besluit": "opnemen", "rol": rol,
                                                           "verwachte_revisie": ov["revisie"]})
        zinnen.append(f"{k['label']} opgenomen" + (" als context" if rol == "context" else ""))
    if did != ANALYSEVRAAG:
        for kid in zichtbaar - set(gekozen):
            k = per_id.get(kid)
            if k and k["stand"] == "opgenomen":
                ov = await api.besluit_bronselectie(wid, did, kid, {"besluit": "loskoppelen",
                                                                   "verwachte_revisie": ov["revisie"]})
                zinnen.append(f"{k['label']} niet meer bij deze deelvraag")
    return ov, zinnen


def regelingen_van(ov: dict[str, Any]) -> list[str]:
    """De BWB-id's waar dit werkgebied over gaat: van de opgenomen bronnen en de voorstellen."""
    iris = [b["bron_iri"] for d in ov["deelvragen"] for b in d["bronnen"]] + \
        [k["bron_iri"] for d in ov["deelvragen"] for k in d["kandidaten"]]
    return sorted({i.split(":")[2] for i in iris if i.startswith("urn:bwb:") and i.count(":") >= 2})


_NIEUW_ARTIKEL = re.compile(r"(?=\bart(?:ikel(?:en)?|\.)\s*\d)", re.I)


def bepalingen_uit_tekst(tekst: str, vind: Callable[[str], list[str]] | list[str], regelingen: list[str]
                         ) -> list[dict[str, str]] | str:
    """Wat de analist zelf als keuze typte, ontleed tot verzoeken per artikel (en lid), die daarna in de graaf
    getoetst worden. Een tekst mag meer bepalingen in meer regelingen noemen ("artikel 9 lid 1 en 5
    Invorderingswet 1990 en artikel 4:86 Awb"): hij wordt geknipt vóór elk "artikel"/"art.", en elk stuk krijgt
    de regeling die het zelf noemt; anders de enige die de hele tekst noemt; anders de enige van het werkgebied.
    Geen artikel: een lege lijst; geen eenduidige regeling voor een stuk: de vraag om haar te noemen.

    `vind` geeft de regelingen die een tekst bij naam of afkorting noemt (`overzicht.regelingen_in_vraag`); een
    lijst is de uitkomst daarvan voor de hele tekst (oude aanroepers)."""
    from .aanwijzing import lees_aanwijzing
    from .werkgebied_intake import artikelen_in

    zoek = vind if callable(vind) else (lambda _t, _v=list(vind): _v)
    heel = zoek(tekst)
    stukken = [x.strip() for x in _NIEUW_ARTIKEL.split(tekst) if x.strip()]
    uit: list[dict[str, str]] = []
    for stuk in stukken:
        artikelen = artikelen_in(stuk)
        if not artikelen:
            continue
        eigen = zoek(stuk) if len(stukken) > 1 else heel
        bwb = eigen[0] if len(eigen) == 1 else heel[0] if not eigen and len(heel) == 1 \
            else regelingen[0] if not eigen and not heel and len(regelingen) == 1 else ""
        if not bwb:
            return ("Bij welke regeling hoort dat? Noem haar erbij, bijvoorbeeld ‘artikel 9 lid 2 Invorderingswet "
                    "1990’." if not eigen and not heel else
                    f"Ik weet niet bij welke regeling ‘{stuk[:80]}’ hoort; noem de regeling direct na het artikel.")
        leden = lees_aanwijzing(stuk).leden if len(artikelen) == 1 and re.search(r"\b(?:lid|leden)\b", stuk, re.I) else ()
        uit += [{"bwb_id": bwb, "artikel": artikelen[0], "lid": lid} for lid in leden] if leden \
            else [{"bwb_id": bwb, "artikel": a} for a in artikelen]
    # Twee keer dezelfde bepaling genoemd is één verzoek.
    return list({(v["bwb_id"], v["artikel"], v.get("lid", "")): v for v in uit}.values())


async def _zelf(api, wid: str, ov: dict, did: str, stap: str, tekst: str,
                vind: Callable[[str], list[str]] | None) -> tuple[dict, list[str], bool]:
    """Een eigen tekst op een bepalingenkaartje: de bepaling(en) toevoegen bij deze deelvraag. (overzicht,
    zinnen, gelukt) – niet gelukt laat het kaartje staan, zodat de analist het kan verbeteren."""
    from .wetsanalyse_api import WetsanalyseApiFout

    verzoeken = bepalingen_uit_tekst(tekst, vind or [], regelingen_van(ov))
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


async def verwerk(api, actie: dict[str, Any], zoek: Zoek | None,
                  vind: Callable[[str], list[str]] | None = None) -> dict[str, Any]:
    """Een klik op een kaartje van de bronselectie. Geeft `{kaart?, zinnen, artefact_deelvraag?}`."""
    wid = werkgebied_van(str(actie.get("intake_id", "")))
    stap = actie.get("stap", "")
    keuzes = [str(x) for x in actie.get("keuzes") or []]
    tekst = (actie.get("tekst") or "").strip()
    did = actie.get("deelvraag_id") or ""
    if actie.get("actie") == "afbreken":
        return {"zinnen": ["Ik zet de bronselectie even stil; de stand blijft bewaard. Kies *Verder met de "
                           "bronselectie* of vraag het me als je verder wilt."]}
    ov = await api.haal_bronselectie(wid)
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
        if actie.get("actie") != "overslaan":
            ov, gedaan = await _neem_op(api, wid, ov, did, stap, keuzes)
            if gedaan:
                zinnen.append("; ".join(gedaan) + ".")
            if tekst:
                ov, uit, gelukt = await _zelf(api, wid, ov, did, stap, tekst, vind)
                zinnen += uit
                if not gelukt:
                    # Het kaartje blijft: de analist verbetert zijn tekst, of verzendt zonder.
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
