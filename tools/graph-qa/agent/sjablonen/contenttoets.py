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
import re
from typing import Any

from bronmodel.antwoord import (Antwoord, Contenttoets, Leemte, Toelichting, ToetsBron, Toetsbevinding,
                                ToetsOntbreekt)
from bronmodel.contenttoets import CRITERIA, CRITERIA_BIJ, MET_BRON, OORDEEL_LABEL, OORDELEN

from ..annotatie import TYPOGRAFISCH
from .duiding import _citaat, _lex
from .vullen import Onvulbaar, Trace, bron_rijen

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
                                              "tekst moet veranderen. Begin met het nummer van de bevinding, zoals [2]."},
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
    niet staat."""
    woorden = citaat.translate(TYPOGRAFISCH).split()
    if not woorden:
        return None
    patroon = r"\s+".join(re.escape(w) for w in woorden)
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
    return Toetsbevinding(nr=0, citaat=content[plek[0]:plek[1]], begin=plek[0], eind=plek[1], oordeel=oordeel,
                          criterium=criterium, bronnen=bronnen, toelichting=_lex(x.get("toelichting"), trace),
                          twijfel=_lex(x.get("twijfel"), trace),
                          voorstel="" if oordeel == "juist" else str(x.get("voorstel") or "").strip())


def _getoetst_tegen(bevindingen: list[Toetsbevinding], ontbreekt: list[ToetsOntbreekt]) -> list[str]:
    namen = [br.vindplaats.regeling or br.vindplaats.label for b in [*bevindingen, *ontbreekt] for br in b.bronnen]
    return list(dict.fromkeys(n for n in namen if n))


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
    bevindingen = [b for i, x in enumerate(aanwijzingen[:MAX_BEVINDINGEN])
                   if (b := _bevinding(i, x, content, rijen, trace, fouten))]
    if not bevindingen:
        raise Onvulbaar("Niets te tonen. " + "; ".join(fouten) + ". Rond daarna opnieuw af.", code="niets_te_tonen")
    # In de volgorde van de content, één bevinding per plek, genummerd zoals de redacteur ze leest.
    uniek = {(b.begin, b.eind): b for b in sorted(bevindingen, key=lambda b: (b.begin, b.eind))}
    bevindingen = [b.model_copy(update={"nr": n}) for n, b in enumerate(uniek.values(), 1)]
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
        voor_redacteur=[r for x in invoer.get("voor_redacteur") or [] if (r := str(x).strip())],
        bevindingen=bevindingen, ontbreekt=ontbreekt,
        niet_getoetst=[r for x in invoer.get("niet_getoetst") or [] if (r := str(x).strip())])
    blokken: list[Any] = [Toelichting(kop="Kort antwoord", tekst=kort), blok]
    if overgeslagen := len(aanwijzingen) - MAX_BEVINDINGEN:
        if overgeslagen > 0:
            blokken.append(Leemte(tekst=f"Het rapport toont de eerste {MAX_BEVINDINGEN} beweringen; {overgeslagen} "
                                        "verder niet. Toets de rest van de tekst apart."))
    if fouten:
        blokken.append(Leemte(tekst=f"{len(fouten)} {'bevinding is' if len(fouten) == 1 else 'bevindingen zijn'} niet "
                                    "getoond: het citaat of de bronpassage was niet letterlijk te vinden."))
    doelen = {br.vindplaats.iri: br.vindplaats for b in [*bevindingen, *ontbreekt] for br in b.bronnen}
    return Antwoord(sjabloon="contenttoets", blokken=blokken, doelen=list(doelen.values()))
