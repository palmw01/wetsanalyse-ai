"""De bronconnector Kamerstukken (ADR-013, fase 1a): wetsgeschiedenis uit de officiële publicaties.

Twee getypeerde tools, met het resultaatcontract van de graaftools:

- `zoek_kamerstukken`: de stukken van een dossier (op nummer), of Kamerstukken waarvan de titel de woorden draagt;
- `get_kamerstuk`: de tekst van één stuk, per alinea, met de kop erboven, in documentvolgorde.

Een Kamerstuk is een **bron, geen wettekst**: de vindplaats is zijn id (`kst-36123-3`, `bronmodel.extern`), de
grounding toetst een citaat letterlijk, en wat de wet zegt onderbouwt het niet. De rijen dragen hun tekst daarom
onder `id`, nooit onder `iri`/`uri`: een sjabloon citeert alleen uit rijen met de iri van een bepaling.

De query bouwt deze module, het model kiest alleen dossier, woorden en het stuk. Staat de connector uit
(`Settings.connector_kamerstukken`), dan is elke aanroep een foutresultaat en biedt de toollaag de tools niet aan.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Protocol

from bronmodel.connectors import KAMERSTUKKEN
from bronmodel.extern import externe_vindplaats

from ..resultaat import compact, fout, per_eenheid
from .op_xml import alineas, lees  # noqa: F401 – de lezer van elke officiële publicatie
from .sru_zoeken import LIMIT, MAX_WOORDEN, OP_VOLGORDE, WOORD_RE as _WOORD_RE, per_record, tekst_cql as _tekst_cql
from .sru_zoeken import cql_woorden, tekst_woorden, zoekvraag as _zoekvraag
from .zoekfilters import datum as _datum
from .stuk_tekst import INHOUD_ARG, MAX_INHOUD, inhoud, inhoudpagina, tekstpagina  # noqa: F401 – gedeeld met elke leestool

#: Uit de beschrijving (`bronmodel.connectors`); de poorttest toetst dat `KAMERSTUK_TOOLS` precies deze namen heeft.
KAMERSTUK_TOOL_NAMEN = KAMERSTUKKEN.tools
CONNECTOR = KAMERSTUKKEN.naam

_DOSSIER_RE = re.compile(r"^\d{4,6}(?:-[A-Z0-9]{1,6})?$")
#: Tot zo veel stukken zet de tool een dossier zelf op nummer: ze haalt ze allemaal op. De zoekdienst sorteert
#: `w.ondernummer` als tekst ("10" vóór "2"), dus dat kan hij niet zelf. Een groter dossier staat op documentdatum
#: (`oudste`), per record gepagineerd met een exact vervolg: nooit afgekapt.
MAX_DOSSIER = 1000
#: Het oudste vergaderjaar in de zoekdienst van KOOP (gemeten 11 nov 2026: de oudste stukken zijn van 1994-1995). Een
#: lege uitkomst noemt die grens: in ronde 2 Kamerstukken gaf dossier 20588 (de Invorderingswet 1990) niets, en schreef
#: het model twee keer dat die stukken "alleen als PDF" bij KOOP staan (K16, K17). Ze staan er helemaal niet in.
EERSTE_VERGADERJAAR = "1994-1995"
GRENS = (f"De zoekdienst van KOOP heeft Kamerstukken vanaf het vergaderjaar {EERSTE_VERGADERJAAR}; wat ouder is, staat "
         "er niet in, ook niet als PDF.")
#: Records per aanroep bij het ophalen van een dossier (de zoekdienst staat er 1000 toe).
_STAP = 250
#: `dt.type==Kamerstuk` laat de bijlagen weg; `w.publicatienaam==Kamerstuk` alleen doet dat niet.
_BASIS = "c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk AND dt.type==Kamerstuk"
#: De volgordes op de documentdatum (`KAMERSTUKKEN.standaard_datum`, dt.date). Alleen `sortBy` in de CQL sorteert: de
#: parameter `sortKeys` negeert de dienst zonder melding (live, 9 nov 2026). Het id als tweede sleutel maakt de
#: volgorde bij dezelfde datum vast, zodat pagineren stabiel is.
_OP_VOLGORDE = OP_VOLGORDE
_OP_DATUM = _OP_VOLGORDE["oudste"]
_KAMERS = {"Tweede Kamer": "Tweede Kamer der Staten-Generaal", "Eerste Kamer": "Eerste Kamer der Staten-Generaal"}
_NUMMER_RE = re.compile(r"^[0-9A-Z]{1,6}$")
_JAAR_RE = re.compile(r"^(\d{4})\s*[-/]\s*(\d{4}|\d{2})$")


class KamerstukBron(Protocol):
    def zoek(self, cql: str, *, start: int = 1, maximum: int = 50) -> tuple[int, list[Any]]: ...
    def document(self, ident: str) -> Any: ...


_CONTRACT = (
    "\nResultaatcontract: {status, volledig, aantal, totaal?, vervolg?, resultaten}. Is `volledig` false, roep "
    "dan `vervolg` aan voor de rest."
)
_UITLEG = (
    " Een Kamerstuk is wetsgeschiedenis, geen wettekst: noem het met zijn id (kst-…) en zeg wat de wet zelf zegt "
    "alleen op grond van de opgehaalde bepaling."
)

KAMERSTUK_TOOLS: list[dict[str, Any]] = [
    {
        "name": "zoek_kamerstukken",
        "description": (
            "Zoek Kamerstukken (wetsgeschiedenis: voorstel van wet, memorie van toelichting, nota's, verslagen, moties, "
            "brieven, het advies van de Raad van State en het nader rapport) in de officiële publicaties. Combineer de "
            "filters: 'dossier' (en 'nummer' voor één stuk), 'woorden' in de titel, 'tekst' in de hele tekst van het "
            "stuk, 'soort', een periode op de datum van het stuk ('vanaf', 'tot'), 'vergaderjaar' en 'kamer'. Zoek op "
            "'tekst' als het onderwerp niet in de titel hoeft te staan: een brief over 'één bankrekeningnummer' heet "
            "vaak alleen 'Brief regering'. Kies de 'volgorde': 'nieuwste' of 'oudste' (op de datum van het stuk), "
            "'nummer' (binnen een dossier) of 'relevantie' (bij woorden of tekst); voor een tijdlijn 'oudste' met een "
            "periode. Zonder volgorde: een dossier op nummer (met een aantal de nieuwste), woorden of tekst op relevantie, de rest nieuwste eerst. Voor 'de laatste stukken van een "
            "dossier' of 'de 10 meest recente': volgorde 'nieuwste' met 'aantal', in één aanroep; blader niet door "
            "het hele dossier." + _UITLEG + "\n"
            "GEEFT TERUG per stuk: id (kst-…), label, soort (zoals 'Memorie van toelichting', 'Motie' of 'Brief "
            "regering'), titel, datum (van het stuk zelf), jaar (het vergaderjaar), orgaan (de Kamer), indieners en "
            "link; gepubliceerd alleen als dat later was dan de datum, reeks als het stuk in meer dossiers staat, status "
            "'Onopgemaakt' en leesbaar: false als er nog alleen een PDF is. Daarnaast 'zoekvraag' (de filters en de "
            "volgorde) en 'totaal' (hoeveel stukken er bij KOOP aan voldoen). Geef gevonden stukken als lijst in het "
            "veld 'stukken' van je antwoordsjabloon, niet in je eigen tekst: de code toont ze dan met de zoekvraag. Bij een "
            "dossier ook de dossiertitel. Op nummer staan letters (stukken van de Eerste Kamer) na de cijfers, dus "
            "'het laatste nummer' is niet 'het nieuwste stuk'. Een dossier boven "
            f"{MAX_DOSSIER} stukken staat op de oudste eerst." + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dossier": {"type": "string", "description": "Dossiernummer, bijvoorbeeld '33755' of '36200-IX'."},
                "nummer": {"type": "string", "description": "Het nummer van één stuk in het dossier, bijvoorbeeld "
                                                            "'342' of 'A'; alleen met 'dossier'."},
                "woorden": {"type": "string", "description": "Woorden uit de titel, bijvoorbeeld 'Invorderingswet'."},
                "tekst": {"type": "string", "description": "Waar het stuk over gaat, gezocht in de hele tekst. Zet een "
                                                           "vaste term tussen dubbele aanhalingstekens (\"één "
                                                           "bankrekeningnummer\"); losse woorden moeten er allemaal "
                                                           "in staan. Hoogstens zes woorden."},
                "soort": {"type": "string", "description": "Het soort stuk, bijvoorbeeld 'memorie van toelichting', "
                                                           "'motie', 'brief regering' of 'nota van wijziging'."},
                "vanaf": {"type": "string", "description": "Vanaf deze datum van het stuk: JJJJ-MM-DD, JJJJ-MM of "
                                                           "JJJJ, bijvoorbeeld '2024' of '2024-06-01'."},
                "tot": {"type": "string", "description": "Tot en met deze datum van het stuk, in dezelfde vorm."},
                "vergaderjaar": {"type": "string", "description": "Het vergaderjaar, bijvoorbeeld '2025-2026'."},
                "kamer": {"type": "string", "enum": list(_KAMERS), "description": "De Kamer die het stuk uitbracht."},
                "volgorde": {"type": "string", "enum": list(KAMERSTUKKEN.volgordes),
                             "description": "nieuwste of oudste (datum van het stuk), nummer (in een dossier) of "
                                            "relevantie (bij woorden of tekst)."},
                "aantal": {"type": "integer", "description": f"Hoeveel stukken per pagina, 1 tot {LIMIT}; bij "
                                                            "volgorde 'nummer' de eerste zoveel van het dossier."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_kamerstuk",
        "description": (
            "De tekst van één Kamerstuk, per alinea in documentvolgorde, met de kop van het deel erboven. Gebruik "
            "het id uit zoek_kamerstukken." + _UITLEG + " Citeer letterlijk uit 'tekst'. Op de eerste pagina van een "
            "stuk dat niet op één pagina past staat 'inhoud': per kop de offset waar dat deel begint. Ga met die offset naar het deel dat de vraag raakt (in de "
            "memorie van toelichting bijvoorbeeld de artikelsgewijze toelichting bij een artikel) in plaats van alles te "
            "lezen.\n"
            "GEEFT TERUG: het stuk (id, label, soort, titel, datum, jaar, orgaan, indieners, link, bron_hash en de stand "
            "bij KOOP: gewijzigd, status, versie) en per alinea nr, kop en tekst (de kop alleen waar hij verandert; hij "
            "geldt tot de volgende). Noem de datum en het soort uit 'stuk', "
            "niet uit de tekst. Een voetnoot staat als eigen rij direct na zijn alinea (soort "
            "'voetnoot', met noot en verwijst_naar: een ander stuk dat je met get_kamerstuk kunt lezen). Is de "
            "status 'Onopgemaakt', zeg dan dat de opgemaakte versie kan afwijken; staat er gevalideerd: false, "
            "dan kon de nieuwste versie niet worden gecontroleerd. Een tabel staat als één rij (soort 'tabel', met de titel "
            "en de omvang) met 'openen': haal hem op met tabel=<nr> om eruit te citeren; dan komen de kolommen en per rij "
            "de cellen. Illustraties staan er niet in; de telling staat in 'overgeslagen'." + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Het id van het stuk, bijvoorbeeld 'kst-33755-3'."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
                "tabel": {"type": "integer", "description": "Het nr van een rij met soort 'tabel': dan de tabel zelf, "
                                                            "per rij, om eruit te citeren."},

                "inhoud": INHOUD_ARG,
                "woorden": {"type": "string", "description": "Alleen de alinea's van dit stuk waarin elk van deze woorden "
                                                             "staat (een woord telt ook in een vervoeging of samenstelling: "
                                                             "'bestuurder' vindt 'bestuurders'), met hun offset. Gebruik het "
                                                             "om in een lang stuk de passages over een onderwerp te vinden, "
                                                             "in plaats van het met offsets door te bladeren."},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
]


def _ondersleutel(nummer: str) -> tuple:
    return tuple((0, int(x)) if x.isdigit() else (1, x) for x in re.findall(r"\d+|\D+", nummer or ""))


def _kamer(creator: str) -> str:
    """"Tweede Kamer der Staten-Generaal" → "Tweede Kamer"; iets anders blijft staan."""
    return next((k for k in ("Tweede Kamer", "Eerste Kamer") if k.lower() in (creator or "").lower()), creator or "")


def label_van(rec: Any, vp: Any) -> str:
    """Het label uit de metadata van KOOP, niet uit het id: een onopgemaakt stuk heeft een eigen id (kst-1278484 is
    32140 nr. 342) en een herdruk een achtervoegsel (kst-32740-1-n1). Zonder dossier en nummer het label van het id."""
    dossiers, nummer = tuple(getattr(rec, "dossiers", ()) or ()), getattr(rec, "ondernummer", "") or ""
    if not dossiers or not nummer:
        return vp.label
    versie = (getattr(rec, "versie", "") or "").strip()
    return (f"Kamerstukken {' '.join(dossiers[0].split('-')).upper()}, nr. {nummer}"
            + (f" ({versie.lower()})" if versie else ""))


def _soort_uit_titel(rec: Any) -> str:
    """Het soort uit de titel van KOOP: "<dossiertitel>; <soort>; <documenttitel>", of zonder documenttitel
    "<dossiertitel>; <soort>". Met de eigen velden afgeknipt, want ook een dossiertitel kan een puntkomma dragen."""
    titel = (rec.titel or "").strip()
    dossiertitel = (getattr(rec, "dossiertitel", "") or "").strip()
    documenttitel = (getattr(rec, "documenttitel", "") or "").strip()
    if dossiertitel and titel.startswith(dossiertitel + "; "):
        rest = titel[len(dossiertitel) + 2:]
        if documenttitel and rest.endswith("; " + documenttitel):
            rest = rest[:-len(documenttitel) - 2]
        return rest.strip()
    delen = titel.split("; ")
    return delen[1] if len(delen) >= 3 else delen[-1]


def _soort_en_titel(rec: Any) -> tuple[str, str]:
    """(soort, titel) uit de eigen velden van KOOP. Bij oudere stukken is `w.subrubriek` vaak "Overig" (kst-33755-3, de
    memorie van toelichting; live, 9 nov 2026): dan het soort uit de titel."""
    rubriek = (getattr(rec, "soort", "") or "").strip()
    soort = rubriek if rubriek.lower() not in {"", "overig"} else _soort_uit_titel(rec)
    eigen = (getattr(rec, "documenttitel", "") or "").strip()
    return soort, ("" if not eigen or eigen.lower() == soort.lower() else eigen)


def metadata(rec: Any, vp: Any) -> dict[str, Any]:
    """De metadata van een stuk in de vaste sleutels (`bronmodel.connectors.METADATA_SLEUTELS`), uit het record van
    KOOP. Wat de jurist alleen in een uitzondering nodig heeft, staat er alleen dan: de publicatiedatum als die afwijkt,
    het dossier als het stuk in meer dossiers staat, de status bij een onopgemaakt stuk, `leesbaar` als het niet kan."""
    soort, titel = _soort_en_titel(rec)
    dossiers = tuple(getattr(rec, "dossiers", ()) or ())
    datum, gepubliceerd = rec.datum or "", getattr(rec, "gepubliceerd", "") or ""
    status = getattr(rec, "documentstatus", "") or ""
    return compact({
        "label": label_van(rec, vp), "soort": soort, "titel": titel, "datum": datum,
        "gepubliceerd": gepubliceerd if gepubliceerd != datum else "", "jaar": rec.vergaderjaar,
        "orgaan": _kamer(getattr(rec, "kamer", "")), "indieners": list(getattr(rec, "indieners", ()) or ()),
        "reeks": list(dossiers) if len(dossiers) > 1 else [], "gezamenlijk": list(dossiers) if len(dossiers) > 1 else [],
        "status": status if status == "Onopgemaakt" else "",
        "versie": getattr(rec, "versie", ""),
        **({"leesbaar": False} if getattr(rec, "xml_url", "x") == "" else {})})


def _rij(rec: Any) -> dict[str, Any] | None:
    vp = externe_vindplaats(rec.id)
    if vp is None or vp.brontype != "kamerstuk" or not rec.id.startswith("kst-"):
        return None
    # De dossiertitel herhaalt zich per stuk en gaat één keer mee (`dossiertitel`).
    return {"id": vp.id, **metadata(rec, vp), "link": vp.uri}


def _dossiertitel(records: list[Any]) -> str:
    return next((getattr(r, "dossiertitel", "") or r.titel.rsplit("; ", 1)[0] for r in records
                 if getattr(r, "dossiertitel", "") or "; " in r.titel), "")


def _cql_woorden(woorden: str) -> str:
    return cql_woorden(woorden, zonder="geef woorden van minstens drie letters, of een dossiernummer")


def _per_record(bron: KamerstukBron, cql: str, args: dict[str, Any], offset: int, *, toelichting: str = "",
                leeg: str = "", extra: dict[str, Any] | None = None, dossier: bool = False, maximum: int = LIMIT) -> str:
    """Een pagina in de volgorde van de zoekdienst (`sru_zoeken.per_record`), met de dossiertitel bij een dossier."""
    return per_record(bron, cql, args, offset, tool="zoek_kamerstukken", rij=_rij, toelichting=toelichting, leeg=leeg,
                      extra=extra, maximum=maximum,
                      extra_van=(lambda deel: {"dossiertitel": _dossiertitel(deel)}) if dossier else None)


def _dossier(bron: KamerstukBron, dossier: str, cql: str, args: dict[str, Any], offset: int, *,
             aantal: int | None = None, toelichting: str = "") -> str:
    """De stukken van één dossier (of subdossier: `36200-IX` staat als eigen waarde in `w.dossiernummer`). Met `aantal`
    de eerste zoveel op nummer ("de eerste vijf stukken van dossier 33755"); eerst was dat een invoerfout, en het model
    probeerde het daarna anders (ronde 1 Kamerstukken, K07 en K17)."""
    totaal, _ = bron.zoek(cql, start=1, maximum=0)
    if totaal > MAX_DOSSIER:
        return _per_record(
            bron, cql + _OP_DATUM, args, offset, extra={"volgorde": "oudste", "zoekvraag": _zoekvraag(args, "oudste")},
            dossier=True, maximum=aantal or LIMIT,
            toelichting=(f"Het dossier {dossier} telt {totaal} stukken: te veel om op nummer te zetten, dus ze staan op "
                         "de datum van het stuk, de oudste eerst. Zoek gericht met dossier én soort, of met volgorde "
                         f"'nieuwste'. {toelichting}").strip())
    # Een dossier tot MAX_DOSSIER: alles ophalen en op nummer zetten, dan zelf pagineren op hele rijen.
    records: list[Any] = []
    while len(records) < totaal:
        _, deel = bron.zoek(cql + _OP_DATUM, start=len(records) + 1, maximum=_STAP)
        if not deel:
            break
        records += deel
    if len(records) < totaal:
        return fout("onvolledig_antwoord", f"De zoekdienst gaf {len(records)} van de {totaal} stukken van dossier "
                    f"{dossier}. Probeer het opnieuw; een onvolledige lijst noem ik niet volledig.")
    records.sort(key=lambda r: _ondersleutel(r.ondernummer))
    lijst = [r for r in (_rij(rec) for rec in records) if r]
    alle = len(lijst)
    if aantal is not None:
        # De eerste `aantal` vanaf de offset; `totaal` blijft het hele dossier, zodat de slotzin "5 van de 27" zegt.
        lijst = lijst[:offset + aantal]
    extra = compact({"totaal": alle, "volgorde": "nummer", "dossiertitel": _dossiertitel(records),
                     "zoekvraag": _zoekvraag(args, "nummer")})
    return per_eenheid(lijst, tool="zoek_kamerstukken", args=args, offset=offset,
                       toelichting=toelichting if lijst else f"Geen Kamerstukken in dossier {dossier}. {GRENS}",
                       extra=extra if lijst else None)


def _vergaderjaar(waarde: str) -> str | None:
    """'2025-2026', '2025/2026' of '2025-26' → '2025-2026'; None als het geen opeenvolgend paar jaren is."""
    m = _JAAR_RE.fullmatch(waarde)
    if not m:
        return None
    begin = int(m.group(1))
    eind = int(m.group(2)) if len(m.group(2)) == 4 else begin // 100 * 100 + int(m.group(2))
    return f"{begin}-{eind}" if eind == begin + 1 else None


#: Hoeveel stukken waarvan alleen de titel het soort draagt de tool zelf toetst; daarboven blijft de titel het filter.
MAX_SOORT_TITEL = 100


def _soort_in_titel(rec: Any, woorden: list[str]) -> bool:
    """Draagt een stuk zonder eigen rubriek het soort op zijn plek in de titel? Elk woord begint een woord van dat soort
    ("amendement" in "Amendement van het lid X"), zoals `all` in de zoekdienst ook een meervoud vindt."""
    if (getattr(rec, "soort", "") or "").strip().lower() not in {"", "overig"}:
        return False
    eigen = [w.lower() for w in _WOORD_RE.findall(_soort_uit_titel(rec))]
    return all(any(e.startswith(w) for e in eigen) for w in woorden)


def _soort_cql(bron: KamerstukBron, rest: str, soort: str) -> tuple[str, bool]:
    """Het soort als filter: (CQL, ruim). Een stuk met een rubriek telt op `w.subrubriek`; een ouder stuk heeft geen
    rubriek of "Overig", en dan staat het soort alleen in de titel (kst-33755-3, kst-30322-3; live, 9 en 11 nov 2026).

    Eerst stond er `w.subrubriek all … OR dt.title all …`, en dan kwam ook een brief met het woord in zijn titel mee
    ("Uitvoeringstoetsen aangenomen amendementen", ronde 1 Kamerstukken K10). De zoekdienst kan niet vragen naar een stuk
    zonder rubriek (`w.subrubriek=*` geeft niets). Daarom haalt de tool de stukken op waarvan alleen de titel het woord
    draagt, toetst ze (`_soort_in_titel`) en neemt de goede op id op. Zo blijven totaal, volgorde en vervolg die van de
    zoekdienst. Zijn het er meer dan `MAX_SOORT_TITEL`, dan blijft de titel het filter, en zegt de toelichting dat
    (`ruim`)."""
    woorden = list(dict.fromkeys(w.lower() for w in _WOORD_RE.findall(soort)))[:MAX_WOORDEN]
    if not woorden:
        raise ValueError("soort")
    term = " ".join(woorden)
    rubriek = f'w.subrubriek all "{term}"'
    totaal, deel = bron.zoek(f'{rest} AND dt.title all "{term}" NOT {rubriek}', start=1, maximum=MAX_SOORT_TITEL)
    if totaal > len(deel):
        return f' AND ({rubriek} OR dt.title all "{term}")', True
    ids = list(dict.fromkeys(r.id for r in deel if _soort_in_titel(r, woorden)))
    if not ids:
        return f" AND {rubriek}", False
    return f' AND ({rubriek} OR {" OR ".join(f"dt.identifier=={chr(34)}{i}{chr(34)}" for i in ids)})', False


def _zoek(bron: KamerstukBron, a: dict[str, Any]) -> str:
    for veld in ("dossier", "woorden"):
        if (vp := externe_vindplaats((a.get(veld) or "").strip())) is not None and vp.id.startswith("kst-"):
            # Een id is geen zoekterm: het stuk staat vast, lees het (acceptatie 8 nov 2026: eerst
            # ongeldige_argumenten, dan het hele dossier, en pas daarna het stuk).
            return fout("is_een_id", f"'{vp.id}' is het id van één stuk: lees het met get_kamerstuk(id='{vp.id}').")
    dossier = (a.get("dossier") or "").strip().upper().replace(" ", "")
    nummer = (a.get("nummer") or "").strip().upper().replace(" ", "")
    woorden = (a.get("woorden") or "").strip()
    tekst = (a.get("tekst") or "").strip()
    soort = (a.get("soort") or "").strip()
    offset = max(int(a.get("offset") or 0), 0)
    if dossier and not _DOSSIER_RE.fullmatch(dossier):
        return fout("ongeldig_dossier", f"'{dossier}' is geen dossiernummer (bijvoorbeeld '33755' of '36200-IX').")
    if nummer and (not dossier or not _NUMMER_RE.fullmatch(nummer)):
        return fout("ongeldig_nummer", "een nummer hoort bij een dossier, bijvoorbeeld "
                    "{\"dossier\": \"32140\", \"nummer\": \"342\"}.")
    try:
        vanaf = _datum((a.get("vanaf") or "").strip(), eind=False) if (a.get("vanaf") or "").strip() else ""
        tot = _datum((a.get("tot") or "").strip(), eind=True) if (a.get("tot") or "").strip() else ""
    except ValueError:
        return fout("ongeldige_datum", "geef een datum als JJJJ-MM-DD, JJJJ-MM of JJJJ, bijvoorbeeld "
                    "{\"vanaf\": \"2024\", \"tot\": \"2024-06-30\"}.")
    if vanaf and tot and vanaf > tot:
        return fout("ongeldige_datum", "'vanaf' ligt na 'tot'; bijvoorbeeld {\"vanaf\": \"2023\", \"tot\": \"2024\"}.")
    jaar = ""
    if (ruw := (a.get("vergaderjaar") or "").strip()):
        if (jaar := _vergaderjaar(ruw) or "") == "":
            return fout("ongeldig_vergaderjaar", "een vergaderjaar is een paar opeenvolgende jaren, bijvoorbeeld "
                        "{\"vergaderjaar\": \"2025-2026\"}.")
    kamer = (a.get("kamer") or "").strip()
    if kamer and kamer not in _KAMERS:
        return fout("ongeldige_kamer", "kies 'Tweede Kamer' of 'Eerste Kamer', bijvoorbeeld {\"kamer\": \"Eerste Kamer\"}.")
    volgorde = (a.get("volgorde") or "").strip()
    if volgorde and volgorde not in KAMERSTUKKEN.volgordes:
        return fout("ongeldige_volgorde", "kies nieuwste, oudste, nummer of relevantie, bijvoorbeeld "
                    "{\"volgorde\": \"nieuwste\"}.")
    aantal = a.get("aantal")
    if aantal is not None and (not isinstance(aantal, int) or isinstance(aantal, bool) or not 1 <= aantal <= LIMIT):
        return fout("ongeldig_aantal", f"'aantal' is een getal van 1 tot {LIMIT}, bijvoorbeeld {{\"aantal\": 10}}.")
    if tekst and not 0 < tekst_woorden(tekst) <= MAX_WOORDEN:
        return fout("ongeldige_tekst", f"geef één tot {MAX_WOORDEN} woorden van minstens drie letters, bijvoorbeeld "
                    "{\"tekst\": \"bankrekeningnummer toeslagen\"}.")
    filters = {"dossier": dossier, "nummer": nummer, "woorden": woorden, "tekst": tekst, "soort": soort,
               "vanaf": vanaf, "tot": tot, "vergaderjaar": jaar, "kamer": kamer}
    if volgorde == "nummer" and not dossier:
        return fout("ongeldige_volgorde", "op nummer kan alleen binnen een dossier, bijvoorbeeld "
                    "{\"dossier\": \"33755\", \"volgorde\": \"nummer\"}.")
    if not any(filters.values()) and volgorde not in {"nieuwste", "oudste"}:
        return fout("ongeldige_argumenten", "geef een dossiernummer, woorden uit de titel, een soort of een periode, of "
                    "vraag de nieuwste stukken, bijvoorbeeld {\"dossier\": \"33755\"} of "
                    "{\"volgorde\": \"nieuwste\", \"aantal\": 10}")
    alleen_dossier = bool(dossier) and not any(v for k, v in filters.items() if k != "dossier")
    gezocht = bool(woorden or tekst)
    # Een dossier met een aantal ("de 10 stukken van dossier 31066") is de nieuwste tien, geen pagina op nummer: op
    # acceptatie gaf dat eerst een invoerfout (9 nov 2026).
    volgorde = volgorde or ("nummer" if alleen_dossier and aantal is None
                            else "relevantie" if gezocht and not dossier else "nieuwste")
    if volgorde == "relevantie" and not gezocht:
        return fout("ongeldige_volgorde", "relevantie gaat over woorden: geef 'woorden' of 'tekst', of kies een datum, "
                    "bijvoorbeeld {\"volgorde\": \"nieuwste\"}.")
    args = {**{k: v for k, v in filters.items() if v}, **({"volgorde": a["volgorde"]} if a.get("volgorde") else {}),
            **({"aantal": aantal} if aantal is not None else {})}
    cql = _BASIS + (f' AND w.dossiernummer=="{dossier}"' if dossier else "")
    cql += f' AND w.ondernummer=="{nummer}"' if nummer else ""
    cql += (" AND " + _cql_woorden(woorden)) if woorden else ""
    cql += _tekst_cql(tekst) if tekst else ""
    cql += (f" AND dt.date>={vanaf}" if vanaf else "") + (f" AND dt.date<={tot}" if tot else "")
    cql += f' AND w.vergaderjaar=="{jaar}"' if jaar else ""
    cql += f' AND dt.creator=="{_KAMERS[kamer]}"' if kamer else ""
    ruim = False
    if soort:
        filter_, ruim = _soort_cql(bron, cql, soort)
        cql += filter_
    toelichting = (f"Bij oudere stukken staat het soort alleen in de titel, en er zijn er te veel om elk te toetsen: "
                   f"een stuk met '{soort}' elders in de titel kan ertussen staan. Kijk naar het soort per stuk."
                   if ruim else "")
    if volgorde == "nummer":
        return _dossier(bron, dossier, cql, args, offset, aantal=aantal, toelichting=toelichting)
    return _per_record(bron, cql + _OP_VOLGORDE.get(volgorde, ""), args, offset, dossier=bool(dossier),
                       maximum=aantal or LIMIT, extra={"volgorde": volgorde, "zoekvraag": _zoekvraag(args, volgorde)},
                       toelichting=toelichting, leeg=f"Geen Kamerstukken die aan de zoekvraag voldoen. {GRENS}")


def _get(bron: KamerstukBron, a: dict[str, Any]) -> str:
    vp = externe_vindplaats((a.get("id") or "").strip())
    if vp is None or not vp.id.startswith("kst-"):
        return fout("ongeldig_id", "geef het id van een Kamerstuk, bijvoorbeeld 'kst-33755-3'")
    doc = bron.document(vp.id)
    try:
        kop, rijen, overgeslagen, tabellen = lees(doc.xml)
    except (ET.ParseError, ValueError) as exc:
        return fout("onleesbaar_document", f"{vp.id} kon niet worden gelezen: {exc}")
    # Het id van KOOP: wie kst-32740-1 vraagt, leest de herdruk kst-32740-1-n1 (`SruKamerstukken.record`).
    echt = externe_vindplaats(getattr(doc, "id", "") or vp.id) or vp
    rec = getattr(doc, "record", None)
    meta = {k: v for k, v in metadata(rec, echt).items() if k != "leesbaar"} if rec is not None else {"label": echt.label}
    # De versie die Lex las (review ADR-013, punt 3): de hash van de XML en de stand bij KOOP. Een onopgemaakte versie
    # wordt later vervangen door de opgemaakte; `gevalideerd: false` als de dienst bij het valideren niet te bereiken was.
    stuk = compact({"id": echt.id, **meta, "titel": kop["documenttitel"] or meta.get("titel", ""), "link": echt.uri,
                    "bron_hash": doc.hash, "gewijzigd": getattr(doc, "gewijzigd", ""),
                    "status": getattr(doc, "documentstatus", ""), "versie": getattr(doc, "versie", ""),
                    **({"gevalideerd": False} if getattr(doc, "gevalideerd", True) is False else {})})
    toelichting = (f"{vp.id} staat bij KOOP als {echt.id} ({stuk['label']}): noem en citeer dat id."
                   if echt.id != vp.id else "")
    vp = echt
    offset = max(int(a.get("offset") or 0), 0)
    if a.get("tabel") is not None:
        gevonden = tabellen.get(int(a["tabel"])) if str(a["tabel"]).lstrip("-").isdigit() else None
        if gevonden is None:
            return fout("ongeldige_tabel", f"{vp.id} heeft geen tabel met nr {a['tabel']}: geef het nr van een rij met "
                        f"soort 'tabel', bijvoorbeeld {{\"id\": \"{vp.id}\", \"tabel\": "
                        f"{next(iter(tabellen), 1)}}}.")
        tabelrijen, samen = gevonden
        return per_eenheid(tabelrijen, tool="get_kamerstuk", args={"id": vp.id, "tabel": int(a["tabel"])},
                           offset=offset, extra={"stuk": stuk, "totaal": len(tabelrijen),
                                                 **({"samengevoegd": samen} if samen else {})})
    if a.get("inhoud"):
        return inhoudpagina(rijen, tool="get_kamerstuk", args={"id": vp.id}, offset=offset, stuk=stuk)
    if (woorden := str(a.get("woorden") or "").strip()):
        return _met_woorden(rijen, woorden, vp.id, offset, stuk)
    # Een tabel is één rij met `openen`: verdieping buiten de scope van deze pagina, geen onvolledigheid.
    rijen = [{**r, "openen": {"tool": "get_kamerstuk", "args": {"id": vp.id, "tabel": r["nr"]}}}
             if r.get("soort") == "tabel" else r for r in rijen]
    return tekstpagina(rijen, tool="get_kamerstuk", args={"id": vp.id}, offset=offset, stuk=stuk,
                       extra={"overgeslagen": overgeslagen} if overgeslagen else None,
                       toelichting=toelichting or ("" if rijen else "Dit stuk heeft geen lopende tekst in de XML."))


def _stammen(woorden: str) -> list[str]:
    """De woorden van een zoekvraag in een stuk als stam: de eerste zeven letters, zodat 'aansprakelijkheid' ook
    'aansprakelijk' vindt en 'bestuurder' 'bestuurders'. Woorden onder de drie letters tellen niet."""
    return [w[:7] for w in (w.lower() for w in _WOORD_RE.findall(woorden)) if len(w) >= 3]


def _met_woorden(rijen: list[dict[str, Any]], woorden: str, ident: str, offset: int, stuk: dict[str, Any]) -> str:
    """De alinea's van één stuk waarin elk woord staat (in de tekst of de kop), met hun offset in de tekst. In ronde 3
    van de Kamerstukken-iteratie (12 nov 2026, K07) zocht het model de passages over de bestuurder met tien offsets in drie
    stukken: 16 rondes, 779k tokens."""
    stammen = _stammen(woorden)
    if not stammen:
        return fout("ongeldige_argumenten", "geef woorden van minstens drie letters, bijvoorbeeld 'bestuurder loonbelasting'")

    def raakt(r: dict[str, Any]) -> bool:
        eigen = [w.lower() for w in _WOORD_RE.findall(f"{r.get('kop') or ''} {r.get('tekst') or ''}")]
        return all(any(stam in w for w in eigen) for stam in stammen)

    treffers = [{**r, "offset": i} for i, r in enumerate(rijen) if r.get("soort") != "tabelrij" and raakt(r)]
    lezen = f"lees verder vanaf 'offset' met {{\"id\": \"{ident}\", \"offset\": <offset>}}"
    extra: dict[str, Any] = {"stuk": stuk, "totaal": len(treffers), "alineas": len(rijen)}
    if treffers:
        toelichting = (f"{len(treffers)} van de {len(rijen)} alinea's noemen „{woorden}”; {lezen} voor de alinea's "
                       "eromheen. Citeer letterlijk uit 'tekst'.")
    else:
        toelichting = f"Geen alinea van dit stuk noemt „{woorden}” (elk woord). " + _zonder_treffer(rijen, stammen, extra)
    return per_eenheid(treffers, tool="get_kamerstuk", args={"id": ident, "woorden": woorden}, offset=offset,
                       extra=extra, toelichting=toelichting)


def _zonder_treffer(rijen: list[dict[str, Any]], stammen: list[str], extra: dict[str, Any]) -> str:
    """Bij nul treffers: in hoeveel alinea's elk woord los staat, zodat het model in één keer het woord laat vallen dat
    het stuk niet gebruikt. In ronde 4 van de Kamerstukken-iteratie (12 nov 2026, K07 en K16) gaf 'bestuurdersaansprakelijk-
    heid loonbelasting' of 'artikel 36 bestuurder aansprakelijk' vijf keer nul treffers, en raadde het model telkens
    opnieuw welk woord eruit moest."""
    if len(stammen) < 2:
        return "Probeer een ander woord, of lees de inhoud met inhoud: true."
    woorden_per_rij = [[w.lower() for w in _WOORD_RE.findall(f"{r.get('kop') or ''} {r.get('tekst') or ''}")]
                       for r in rijen if r.get("soort") != "tabelrij"]
    per_woord = {stam: sum(1 for eigen in woorden_per_rij if any(stam in w for w in eigen))
                 for stam in dict.fromkeys(stammen)}
    extra["per_woord"] = per_woord
    los = ", ".join(f"„{stam}…” {n}" for stam, n in per_woord.items())
    nul = [stam for stam, n in per_woord.items() if not n]
    raad = (f"laat {', '.join(f'„{s}…”' for s in nul)} weg" if nul and len(nul) < len(per_woord)
            else "geef minder woorden tegelijk")
    return (f"Per woord, in hoeveel alinea's het los staat: {los}. Samen staan ze in geen alinea; {raad}, of lees de "
            "inhoud met inhoud: true.")


#: De reden in het foutresultaat per code van de adapter (`KamerstukFout.code`).
FOUTREDEN = {"onbereikbaar": "bron_onbereikbaar", "geweigerd": "zoekvraag_geweigerd", "niet_gevonden": "niet_gevonden",
             "alleen_pdf": "alleen_pdf"}


def fout_van(exc: Any) -> str:
    """Het foutresultaat bij een `KamerstukFout`, met de reden en wat Lex ermee doet. Een stuk dat alleen als PDF
    bestaat, bestaat: het resultaat noemt zijn metadata uit KOOP, zodat Lex datum en soort uit de code noemt in plaats
    van "bestaat mogelijk niet" (acceptatie 9 nov 2026)."""
    code = getattr(exc, "code", "onbereikbaar")
    rec = getattr(exc, "record", None)
    if code == "alleen_pdf" and rec is not None and (vp := externe_vindplaats(rec.id)) is not None:
        meta = metadata(rec, vp)
        wat = ", ".join(x for x in (meta.get("soort"), meta.get("datum")) if x)
        return fout("alleen_pdf", (
            f"{meta['label']} ({vp.id}{', ' + wat if wat else ''}) bestaat, maar staat bij KOOP "
            f"{'nog onopgemaakt en ' if rec.documentstatus == 'Onopgemaakt' else ''}alleen als PDF: de tekst kan ik niet "
            f"lezen. Zeg dat, met de datum en de link {vp.uri}, en citeer er niet uit."),
            stuk={"id": vp.id, **meta, "link": vp.uri})
    if code == "niet_gevonden":
        return fout("niet_gevonden", f"{exc}, ook niet op dossier en nummer. Controleer het id, of zoek het stuk met "
                    "zoek_kamerstukken, bijvoorbeeld {\"dossier\": \"33755\"}.")
    return fout(FOUTREDEN.get(code, "bron_onbereikbaar"), str(exc))


def dispatch_kamerstuk(name: str, args: dict[str, Any], bron: KamerstukBron | None) -> str:
    if bron is None:
        return fout("connector_uit", "De bron Kamerstukken staat uit. Zeg dat, en antwoord niet uit eigen kennis.")
    if name == "zoek_kamerstukken":
        return _zoek(bron, args)
    if name == "get_kamerstuk":
        return _get(bron, args)
    raise KeyError(name)
