"""Het toetsrapport van de contenttoets (ADR-008; plan docs/architectuur/plan-contenttoets.md, C1).

De methode staat in de skill `contenttoets`: wat een toetsbare bewering is, de criteria J1–J7 en V1–V3 en de oordelen.
Hier vult de code het rapport, zoals bij elk sjabloon:

- het model wijst per bewering het **citaat uit de content** aan; de code zoekt het letterlijk op in de content (die staat
  in de trace als resultaat van `CONTENT_TOOL`, gezet door de route) en zet de plek erbij, in codepoints;
- het model wijst per bewering de **bronpassage** aan zoals in het duidingssjabloon (bepaling, eerste en laatste woorden);
  de code neemt de tekst letterlijk uit de rijen die de graaf in deze beurt teruggaf (`duiding._citaat`);
- het oordeel komt uit een gesloten lijst, het criterium moet bij het oordeel passen, en een oordeel over juistheid rust
  op een bronpassage. "Mogelijk onjuist" zonder passage bestaat niet: dan is het "niet in de bron";
- alleen een passage uit de kennisgraaf telt (`in_de_graaf`): geen connector, geen wettekst live van overheid.nl;
- de regelingen waartegen getoetst is, komen uit de vindplaatsen van de passages.

Het model levert alleen wat een oordeel of formulering vraagt: de samenvatting, de regels voor de redacteur, het oordeel,
de toelichting, de twijfel en het voorstel. Wat niet te tonen is, laat de code weg met een leemte, zolang er een bevinding
overblijft; anders gaat de aanroep terug als fout.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from bronmodel.antwoord import (Antwoord, Contenttoets, Leemte, Toelichting, ToetsBron, Toetsbevinding,
                                ToetsOntbreekt)
from bronmodel.contenttoets import CRITERIA, CRITERIA_BIJ, MET_BRON, OORDEEL_LABEL, OORDELEN

from ..annotatie import TYPOGRAFISCH
from .duiding import _binnen, _citaat, _lex, valuta_patroon
from .vullen import Onvulbaar, Trace, bron_rijen, ouders

logger = logging.getLogger(__name__)

NAAM = "antwoord_contenttoets"
#: De naam waaronder de route de content in de trace zet (geen graaftool: de code doet de aanroep zelf).
CONTENT_TOOL = "contenttoets_content"
#: Zoveel bevindingen toont het rapport hoogstens; een langere tekst toetst de gebruiker in delen.
MAX_BEVINDINGEN = 30
#: Zoveel bronpassages per bevinding.
MAX_BRONNEN = 3
#: Het voorvoegsel van een graafadres: alleen daartegen toetst de contenttoets.
GRAAF = "urn:bwb:"

_BRON = {
    "type": "object",
    "properties": {
        "bepaling": {"type": "string", "description": "De iri van de bepaling uit het toolresultaat."},
        "van": {"type": "string", "description": "De eerste drie tot acht woorden van de passage, letterlijk uit de "
                                                 "tekst van één lid, onderdeel of divisie. Leeg: vanaf het begin."},
        "tot": {"type": "string", "description": "De laatste drie tot acht woorden van de passage, letterlijk, na `van`. "
                                                 "Leeg: tot het eind van die tekst."},
    },
    "required": ["bepaling", "van", "tot"],
    "additionalProperties": False,
}

SCHEMA: dict[str, Any] = {
    "name": NAAM,
    "description": (
        "Rond een contenttoets af: het toetsrapport over de content die de gebruiker gaf, volgens de skill contenttoets. "
        "Per toetsbare bewering wijs je het citaat uit de content aan (letterlijk), kies je het oordeel en het criterium, "
        "en wijs je de bronpassage aan zoals in het duidingssjabloon (bepaling, eerste en laatste woorden). De werkplek "
        "toont de content, de plek van elke bewering en de letterlijke brontekst zelf: typ geen brontekst over. Een "
        "oordeel juist, mogelijk onjuist of onvolledig rust op een passage uit wat je in deze beurt las; vond je niets, "
        "dan is het oordeel niet_in_de_bron. Schrijf geen antwoord ernaast."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "kort_antwoord": {"type": "string", "description": "Twee tot vier zinnen: waartegen je toetste en wat de "
                                                               "belangrijkste bevindingen zijn."},
            "voor_redacteur": {"type": "array", "items": {"type": "string"},
                               "description": "Per punt dat om een wijziging vraagt één regel in gewone taal: wat er in de "
                                              "tekst moet veranderen. Begin met het nummer van de bevinding in je lijst "
                                              "'bevindingen' (de eerste is [1]), zoals [2]; de code nummert mee."},
            "bevindingen": {
                "type": "array",
                "description": "De toetsbare beweringen, in de volgorde van de content.",
                "items": {
                    "type": "object",
                    "properties": {
                        "citaat": {"type": "string", "description": "De bewering, letterlijk uit de content: zo kort als "
                                                                    "kan, zo lang als het oordeel nodig heeft."},
                        "oordeel": {"type": "string", "enum": list(OORDELEN)},
                        "criterium": {"type": "string", "enum": ["", *CRITERIA],
                                      "description": "J1–J7 bij mogelijk onjuist, J of V bij onvolledig; leeg mag bij "
                                                     "juist en niet_in_de_bron."},
                        "bron": {"type": "array", "items": _BRON,
                                 "description": "De passages waarop het oordeel rust. Leeg bij niet_in_de_bron."},
                        "toelichting": {"type": "string", "description": "Waarom dit oordeel, in twee of drie zinnen."},
                        "twijfel": {"type": "string", "description": "Twijfel of aanname, apart; leeg als er geen is."},
                        "voorstel": {"type": "string",
                                     "description": "Een betere zin in de taal van de content, of bij niet_in_de_bron een "
                                                    "vraag aan de redacteur. Leeg bij juist. Geen nieuwe bewering die de "
                                                    "bron niet draagt."},
                    },
                    "required": ["citaat", "oordeel", "criterium", "bron", "toelichting", "twijfel", "voorstel"],
                    "additionalProperties": False,
                },
            },
            "ontbreekt": {
                "type": "array",
                "description": "Wat de bron wezenlijk zegt en de content nergens noemt. Alleen wat de lezer nodig heeft.",
                "items": {
                    "type": "object",
                    "properties": {"wat": {"type": "string"}, "bron": {"type": "array", "items": _BRON}},
                    "required": ["wat", "bron"],
                    "additionalProperties": False,
                },
            },
            "niet_getoetst": {"type": "array", "items": {"type": "string"},
                              "description": "Wat geen bewering is (procesinformatie), kort."},
        },
        "required": ["kort_antwoord", "voor_redacteur", "bevindingen", "ontbreekt", "niet_getoetst"],
        "additionalProperties": False,
    },
}


def content_van(trace: Trace) -> dict[str, Any]:
    """De content en de peildatum zoals de route ze in de trace zette (de laatste), of leeg."""
    for naam, tekst in reversed(trace):
        if naam != CONTENT_TOOL:
            continue
        try:
            data = json.loads(tekst)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("content"), str):
            return data
    return {}


def content_resultaat(content: str, peildatum: str = "") -> str:
    """Het resultaat van `CONTENT_TOOL`: wat de route in de trace zet, in de vorm van het resultaatcontract."""
    return json.dumps({"status": "ok", "volledig": True, "aantal": 1, "content": content, "peildatum": peildatum,
                       "resultaten": []}, ensure_ascii=False)


def plek_in(citaat: str, content: str) -> tuple[int, int] | None:
    """Waar het citaat in de content staat, in codepoints van de content zoals de gebruiker hem gaf: witruimte- en
    typografie-ongevoelig (een aanhalingsteken of streepje telt als zijn gewone vorm). De eerste plek; None als het er
    niet staat. Na een valutateken mag de spatie ontbreken of staan ("€25" en "€ 25", ook een harde spatie)."""
    woorden = citaat.translate(TYPOGRAFISCH).split()
    if not woorden:
        return None
    patroon = valuta_patroon(r"\s+".join(re.escape(w) for w in woorden))
    m = re.search(patroon, content.translate(TYPOGRAFISCH))
    return (m.start(), m.end()) if m else None


def in_de_graaf(iri: str) -> bool:
    """Of een bepaling uit de kennisgraaf komt: een graafadres (`urn:bwb:`) of een jci, die de code naar de graaf
    vertaalt. De contenttoets toetst alleen tegen de graaf (besluit 26 nov 2026); een kennisgroepstandpunt, een stuk naast
    de wet of wettekst die live van overheid.nl komt, draagt geen bevinding."""
    return iri.startswith((GRAAF, "jci"))


def _bronnen(aanwijzingen: Any, rijen: dict[str, dict[str, Any]], trace: Trace, fouten: list[str]) -> list[ToetsBron]:
    uit: list[ToetsBron] = []
    for stuk in (aanwijzingen if isinstance(aanwijzingen, list) else [])[:MAX_BRONNEN]:
        if not isinstance(stuk, dict):
            continue
        iri = str(stuk.get("bepaling") or "").strip()
        if iri and not in_de_graaf(iri):
            fouten.append(f"{iri} staat niet in de kennisgraaf: de contenttoets toetst alleen tegen de wet- en regelgeving "
                          "in de graaf. Wijs een bepaling uit de graaf aan, of kies niet_in_de_bron")
            continue
        c = _citaat({**stuk, "waarom": ""}, rijen, trace, fouten)
        for x in (c if isinstance(c, list) else [c] if c else []):
            if in_de_graaf(x.vindplaats.iri):
                uit.append(ToetsBron(tekst=x.tekst, vindplaats=x.vindplaats))
            else:
                fouten.append(f"{x.vindplaats.iri} staat niet in de kennisgraaf; kies niet_in_de_bron")
    return uit


#: Een woord dat ruimte laat: de bron zegt dat iets kan, de tekst dat het gebeurt (J4).
_RUIMTE = re.compile(r"\b(kan|kunt|kunnen|mag|mogen|misschien|mogelijk|eventueel|bevoegd)\b", re.IGNORECASE)
#: Doelgroepen die een bepaling voor de een en niet de ander maken (Leidraad: particulieren tegenover ondernemers).
DOELGROEPEN = {"particulier": "particulieren", "ondernemer": "ondernemers", "natuurlijk persoon": "natuurlijke personen",
               "natuurlijke persoon": "natuurlijke personen", "natuurlijke personen": "natuurlijke personen",
               "rechtspersoon": "rechtspersonen", "rechtspersonen": "rechtspersonen", "werkgever": "werkgevers",
               "werknemer": "werknemers", "erfgenaam": "erfgenamen", "erfgenamen": "erfgenamen",
               "toeslaggerechtigde": "toeslaggerechtigden"}
_DOELGROEP = re.compile(r"\b(" + "|".join(sorted(map(re.escape, DOELGROEPEN), key=len, reverse=True)) + r")(?:en|s)?\b",
                        re.IGNORECASE)


def doelgroepen(tekst: str) -> set[str]:
    return {DOELGROEPEN[m.group(1).casefold()] for m in _DOELGROEP.finditer(tekst)}


def kanttekening_j4(citaat: str, content: str, bronnen: list[ToetsBron]) -> str:
    """De kanttekening bij een *juist* (criterium J4, modaliteit en doelgroep; meting C5): de code legt het citaat naast de
    passages waarop het steunt.

    - De bron laat ruimte ("kan … worden getroffen"), het citaat niet ("dan krijgt u kort uitstel").
    - De bepaling gaat over een doelgroep (in haar kop of tekst) die de content nergens noemt: de ondernemersbepaling als
      steun voor een tekst voor particulieren.

    Leeg als er niets te zeggen is. De code verandert het oordeel niet: een *juist* met deze kanttekening is een signaal
    voor de jurist, geen fout."""
    zinnen: list[str] = []
    met_ruimte = next((m.group(0) for br in bronnen if (m := _RUIMTE.search(br.tekst))), "")
    if met_ruimte and not _RUIMTE.search(citaat):
        zinnen.append(f"De bron laat ruimte (“{met_ruimte}”), de tekst zegt het stellig. Ga na of dat klopt (J4).")
    in_content = doelgroepen(content)
    for br in bronnen:
        anders = sorted(doelgroepen(f"{br.vindplaats.label} {br.tekst}") - in_content)
        if anders and not in_content & doelgroepen(f"{br.vindplaats.label} {br.tekst}"):
            zinnen.append(f"{br.vindplaats.label or 'De bepaling'} gaat over {' en '.join(anders)}, en de tekst noemt die "
                          "groep niet. Geldt de bepaling voor de lezer van deze tekst (J4)?")
            break
    return " ".join(zinnen)


def _bevinding(i: int, x: dict[str, Any], content: str, rijen: dict[str, dict[str, Any]], trace: Trace,
               fouten: list[str]) -> Toetsbevinding | None:
    citaat = str(x.get("citaat") or "").strip()
    oordeel = str(x.get("oordeel") or "")
    criterium = str(x.get("criterium") or "")
    naam = f"bevinding {i + 1}" + (f" (“{citaat[:40]}”)" if citaat else "")
    if oordeel not in OORDEEL_LABEL:
        fouten.append(f"{naam}: het oordeel is een van {', '.join(OORDELEN)}")
        return None
    if criterium not in CRITERIA_BIJ[oordeel]:
        fouten.append(f"{naam}: {criterium or 'geen criterium'} past niet bij {oordeel}; kies uit "
                      + ", ".join(c for c in CRITERIA_BIJ[oordeel] if c))
        return None
    plek = plek_in(citaat, content)
    if plek is None:
        fouten.append(f"{naam}: het citaat staat niet letterlijk in de content. Neem de woorden over zoals ze er staan")
        return None
    eigen: list[str] = []
    bronnen = _bronnen(x.get("bron"), rijen, trace, eigen) if oordeel in MET_BRON else []
    if oordeel in MET_BRON and not bronnen:
        fouten.append(f"{naam}: {OORDEEL_LABEL[oordeel].lower()} rust op een passage uit de bron, en die is niet te tonen"
                      + (" (" + "; ".join(eigen) + ")" if eigen else "")
                      + ". Wijs een passage aan uit wat je las, of kies niet_in_de_bron")
        return None
    twijfel = _lex(x.get("twijfel"), trace)
    if oordeel == "juist" and (kant := kanttekening_j4(content[plek[0]:plek[1]], content, bronnen)):
        twijfel = f"{twijfel} {kant}".strip()
    return Toetsbevinding(nr=0, citaat=content[plek[0]:plek[1]], begin=plek[0], eind=plek[1], oordeel=oordeel,
                          criterium=criterium, bronnen=bronnen, toelichting=_lex(x.get("toelichting"), trace),
                          twijfel=twijfel,
                          voorstel="" if oordeel == "juist" else str(x.get("voorstel") or "").strip())


def _getoetst_tegen(bevindingen: list[Toetsbevinding], ontbreekt: list[ToetsOntbreekt]) -> list[str]:
    namen = [br.vindplaats.regeling or br.vindplaats.label for b in [*bevindingen, *ontbreekt] for br in b.bronnen]
    return list(dict.fromkeys(n for n in namen if n))


#: Een zin met een voorwaarde, uitzondering of gevolg: wat een lezer van een publiekstekst moet weten (V1–V3). Een
#: gevolg of uitzondering (`_STERK`) gaat voor een voorwaarde: dat miste de meting (79.7 beëindiging, 25.3a.1 opsomming).
_STERK = re.compile(r"\b(tenzij|behalve|uitgezonderd|uitzondering|niet|geen|beëindigd|beëindigen|vervalt|vervallen|"
                    r"ingetrokken|afgewezen|wijst\s+\S+(?:\s+\S+){0,3}\s+af)\b", re.IGNORECASE)
_DRAGEND = re.compile(r"\b(als|indien|wanneer|mits|uitsluitend|alleen|voorwaarden?)\b", re.IGNORECASE)
#: Zoveel zinnen noemt de controle hoogstens; meer is geen controle meer maar de hele bepaling.
MAX_NA_TE_LOPEN = 5
_ZIN = re.compile(r"(?<=[.;:])\s+(?=[A-Z0-9–(])")
_WOORD = re.compile(r"[a-zà-ÿ0-9€]{5,}", re.IGNORECASE)


def _stam(woord: str) -> str:
    return woord.casefold()[:6]


def _noemt(content: str, zin: str) -> bool:
    """Noemt de content deze zin? Ten minste de helft van haar woorden van vijf letters of meer staat erin (op hun stam:
    "beëindigd" en "beëindiging"). Een grove toets: hij wijst aan wat de jurist moet nalopen, hij beslist niets."""
    woorden = {_stam(w) for w in _WOORD.findall(zin)}
    if not woorden:
        return True
    in_content = {_stam(w) for w in _WOORD.findall(content)}
    # Het gevolg of de uitzondering zelf ("beëindigd", "vervalt", "tenzij") in de content: dan noemt ze het, ook in
    # andere woorden eromheen. "niet" en "geen" zeggen daarvoor te weinig.
    kern = {_stam(m.group(0)) for m in _STERK.finditer(zin) if m.group(0).casefold() not in ("niet", "geen")}
    if kern and kern & in_content:
        return True
    return len(woorden & in_content) * 2 >= len(woorden)


def na_te_lopen(bevindingen: list[Toetsbevinding], ontbreekt: list[ToetsOntbreekt], content: str,
                rijen: dict[str, dict[str, Any]], trace: Trace) -> list[tuple[str, str]]:
    """De controlestap per gelezen bepaling (meting C5): in elke bepaling waaruit het rapport citeert, de zinnen met een
    voorwaarde, uitzondering of gevolg, en de onderdelen van een opsomming, die het rapport niet citeert en die de content
    niet noemt. Letterlijk uit de rijen van de graaf, als (label, zin). Bij 79.7 werd zo de beëindiging bij niet nakomen
    gemist, bij 25.3a.1 de uitzondering in de opsomming. De code beslist niet: de jurist loopt het na."""
    geciteerd = [br for b in [*bevindingen, *ontbreekt] for br in b.bronnen]
    citaten = [" ".join(br.tekst.split()) for br in geciteerd]
    label_van = {br.vindplaats.iri: br.vindplaats.label for br in geciteerd}
    lid_van = ouders(trace)
    uit: list[tuple[str, str]] = []
    for iri, label in label_van.items():
        onder = [(k, r) for k, r in rijen.items() if _binnen(k, iri) or lid_van.get(k) == iri]
        for k, r in onder:
            tekst = " ".join(str(r.get("tekst") or "").split())
            zinnen = [tekst] if r.get("onderdeel") and k != iri else _ZIN.split(tekst)
            for zin in zinnen:
                if not zin or not (r.get("onderdeel") or _STERK.search(zin) or _DRAGEND.search(zin)):
                    continue
                if any(zin in c or c in zin for c in citaten) or _noemt(content, zin):
                    continue
                if (label, zin) not in uit:
                    uit.append((label, zin))
    # Eerst de onderdelen en de gevolgen en uitzonderingen, dan de voorwaarden; binnen elk de volgorde van de bron.
    return sorted(uit, key=lambda p: 0 if _STERK.search(p[1]) or p[1] in _onderdelen(rijen) else 1)[:MAX_NA_TE_LOPEN]


def _onderdelen(rijen: dict[str, dict[str, Any]]) -> set[str]:
    return {" ".join(str(r.get("tekst") or "").split()) for r in rijen.values() if r.get("onderdeel")}


def na_te_lopen_tekst(punten: list[tuple[str, str]]) -> str:
    return ("Na te lopen: in de bepalingen waaruit het rapport citeert, staan voorwaarden, uitzonderingen of gevolgen "
            "die het rapport niet noemt en de tekst ook niet. Ga na of de lezer ze nodig heeft. "
            + " ".join(f"{label}: “{zin}”" for label, zin in punten))


_VERWIJZING = re.compile(r"\[(\d+)\]")


def voor_redacteur(regels: Any, nummers: dict[int, int]) -> list[str]:
    """De regels voor de redacteur, met elke verwijzing [n] naar het nummer dat de bevinding in het rapport kreeg.
    `nummers` gaat van het nummer in de lijst van het model naar dat in het rapport. Een regel die naar een bevinding
    verwijst die wegviel (het citaat of de bronpassage stond er niet letterlijk), valt mee weg: anders wees "[4]" naar
    een andere bevinding (meting C5, standaardregeling). Een regel zonder verwijzing blijft staan."""
    uit: list[str] = []
    for x in regels if isinstance(regels, list) else []:
        regel = str(x).strip()
        genoemd = [int(m) for m in _VERWIJZING.findall(regel)]
        if not regel or any(n not in nummers for n in genoemd):
            continue
        uit.append(_VERWIJZING.sub(lambda m: f"[{nummers[int(m.group(1))]}]", regel))
    return uit


def meld_weggevallen(fouten: list[str]) -> None:
    """Zet per weggevallen bevinding de reden in het denkproces (welk citaat, welke bronpassage), zodat de jurist en de
    meting zien waarom het rapport er een minder toont. De logregel telt alleen: de reden draagt tekst uit de content."""
    if not fouten:
        return
    from ..narratie import _stap
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
    except Exception:  # noqa: BLE001 – buiten een graaf (een test) is er geen stroom
        writer = None
    logger.info("contenttoets: bevinding weggevallen", extra={"categorie": "functioneel", "aantal": len(fouten)})
    if writer is not None:
        for f in fouten:
            _stap(writer, "Controle", "niet getoond – " + f)


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    gegeven = content_van(trace)
    content = gegeven.get("content", "")
    if not content.strip():
        raise Onvulbaar("Er is geen content om te toetsen in deze beurt. Dit sjabloon hoort bij /contenttoets.",
                        code="geen_content")
    kort = _lex(invoer.get("kort_antwoord"), trace)
    if not kort:
        raise Onvulbaar("Schrijf het korte antwoord: waartegen je toetste en wat de belangrijkste bevindingen zijn.",
                        code="kort_antwoord")
    aanwijzingen = [x for x in invoer.get("bevindingen") or [] if isinstance(x, dict)]
    if not aanwijzingen:
        raise Onvulbaar("Er staat geen bevinding in het rapport. Toets elke toetsbare bewering uit de content.",
                        code="geen_bevinding")
    rijen, fouten = bron_rijen(trace), []
    # Per bevinding het nummer zoals het model haar aanwees (1 = de eerste in zijn lijst), voor `voor_redacteur`.
    getoond = [(i + 1, b) for i, x in enumerate(aanwijzingen[:MAX_BEVINDINGEN])
               if (b := _bevinding(i, x, content, rijen, trace, fouten))]
    if not getoond:
        raise Onvulbaar("Niets te tonen. " + "; ".join(fouten) + ". Rond daarna opnieuw af.", code="niets_te_tonen")
    # In de volgorde van de content, één bevinding per plek, genummerd zoals de redacteur ze leest.
    plekken = sorted({(b.begin, b.eind) for _, b in getoond})
    nr_van_plek = {p: n for n, p in enumerate(plekken, 1)}
    uniek = {(b.begin, b.eind): b for _, b in sorted(getoond, key=lambda x: (x[1].begin, x[1].eind))}
    bevindingen = [b.model_copy(update={"nr": nr_van_plek[p]}) for p, b in uniek.items()]
    nummers = {eigen: nr_van_plek[(b.begin, b.eind)] for eigen, b in getoond}
    ontbreekt: list[ToetsOntbreekt] = []
    for o in invoer.get("ontbreekt") or []:
        if not isinstance(o, dict) or not (wat := _lex(o.get("wat"), trace)):
            continue
        eigen: list[str] = []
        if bronnen := _bronnen(o.get("bron"), rijen, trace, eigen):
            ontbreekt.append(ToetsOntbreekt(tekst=wat, bronnen=bronnen))
        else:
            fouten.append(f"ontbreekt (“{wat[:40]}”): zonder passage uit de bron niet te tonen")
    blok = Contenttoets(
        content=content, peildatum=str(gegeven.get("peildatum") or ""),
        getoetst_tegen=_getoetst_tegen(bevindingen, ontbreekt),
        voor_redacteur=voor_redacteur(invoer.get("voor_redacteur"), nummers),
        bevindingen=bevindingen, ontbreekt=ontbreekt,
        niet_getoetst=[r for x in invoer.get("niet_getoetst") or [] if (r := str(x).strip())])
    blokken: list[Any] = [Toelichting(kop="Kort antwoord", tekst=kort), blok]
    if punten := na_te_lopen(bevindingen, ontbreekt, content, rijen, trace):
        blokken.append(Leemte(tekst=na_te_lopen_tekst(punten)))
    if overgeslagen := len(aanwijzingen) - MAX_BEVINDINGEN:
        if overgeslagen > 0:
            blokken.append(Leemte(tekst=f"Het rapport toont de eerste {MAX_BEVINDINGEN} beweringen; {overgeslagen} "
                                        "verder niet. Toets de rest van de tekst apart."))
    if fouten:
        blokken.append(Leemte(tekst=f"{len(fouten)} {'bevinding is' if len(fouten) == 1 else 'bevindingen zijn'} niet "
                                    "getoond: het citaat of de bronpassage was niet letterlijk te vinden."))
    meld_weggevallen(fouten)
    doelen = {br.vindplaats.iri: br.vindplaats for b in [*bevindingen, *ontbreekt] for br in b.bronnen}
    return Antwoord(sjabloon="contenttoets", blokken=blokken, doelen=list(doelen.values()))
