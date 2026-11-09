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

import calendar
import json
import re
from datetime import date
import xml.etree.ElementTree as ET
from typing import Any, Protocol

from bronmodel.connectors import KAMERSTUKKEN
from bronmodel.extern import externe_vindplaats

from ..resultaat import BUDGET, TeGroot, compact, fout, per_eenheid, resultaat

#: Uit de beschrijving (`bronmodel.connectors`); de poorttest toetst dat `KAMERSTUK_TOOLS` precies deze namen heeft.
KAMERSTUK_TOOL_NAMEN = KAMERSTUKKEN.tools
CONNECTOR = KAMERSTUKKEN.naam

_DOSSIER_RE = re.compile(r"^\d{4,6}(?:-[A-Z0-9]{1,6})?$")
_WOORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]{3,}")
MAX_WOORDEN = 6
LIMIT = 25
#: Tot zo veel stukken zet de tool een dossier zelf op nummer: ze haalt ze allemaal op. De zoekdienst sorteert
#: `w.ondernummer` als tekst ("10" vóór "2"), dus dat kan hij niet zelf. Een groter dossier staat op documentdatum
#: (`oudste`), per record gepagineerd met een exact vervolg: nooit afgekapt.
MAX_DOSSIER = 1000
#: Records per aanroep bij het ophalen van een dossier (de zoekdienst staat er 1000 toe).
_STAP = 250
#: `dt.type==Kamerstuk` laat de bijlagen weg; `w.publicatienaam==Kamerstuk` alleen doet dat niet.
_BASIS = "c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk AND dt.type==Kamerstuk"
#: De volgordes op de documentdatum (`KAMERSTUKKEN.standaard_datum`, dt.date). Alleen `sortBy` in de CQL sorteert: de
#: parameter `sortKeys` negeert de dienst zonder melding (live, 9 nov 2026). Het id als tweede sleutel maakt de
#: volgorde bij dezelfde datum vast, zodat pagineren stabiel is.
_OP_VOLGORDE = {"nieuwste": " sortBy dt.date/sort.descending dt.identifier/sort.ascending",
                "oudste": " sortBy dt.date/sort.ascending dt.identifier/sort.ascending"}
_OP_DATUM = _OP_VOLGORDE["oudste"]
_KAMERS = {"Tweede Kamer": "Tweede Kamer der Staten-Generaal", "Eerste Kamer": "Eerste Kamer der Staten-Generaal"}
_NUMMER_RE = re.compile(r"^[0-9A-Z]{1,6}$")
_JAAR_RE = re.compile(r"^(\d{4})\s*[-/]\s*(\d{4}|\d{2})$")
_DATUM_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
#: Elementen die geen lopende tekst zijn; ze worden geteld en genoemd, nooit stil weggelaten.
#: De XML van KOOP gebruikt CALS-tabellen (`table`): zonder die sleutel kwamen tabelcellen als losse alinea's mee, zoals
#: de inhoudsopgave en de cijfers van een budgettabel zonder hun kolommen (acceptatie 8 nov 2026: 43 van de 63 alinea's
#: van kst-33755-3).
_OVERGESLAGEN = {"tabel": "tabel", "table": "tabel", "illustratie": "illustratie", "noot": "voetnoot"}
#: Zo veel koppen staan hoogstens in `inhoud` op de eerste pagina; meer en alleen de bovenste twee niveaus.
MAX_INHOUD = 40


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
                "aantal": {"type": "integer", "description": f"Hoeveel stukken per pagina, 1 tot {LIMIT}; niet bij "
                                                            "volgorde 'nummer'."},
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
            "het id uit zoek_kamerstukken." + _UITLEG + " Citeer letterlijk uit 'tekst'. Op de eerste pagina staat "
            "'inhoud': per kop de offset waar dat deel begint. Ga met die offset naar het deel dat de vraag raakt (in de "
            "memorie van toelichting bijvoorbeeld de artikelsgewijze toelichting bij een artikel) in plaats van alles te "
            "lezen.\n"
            "GEEFT TERUG: het stuk (id, label, soort, titel, datum, jaar, orgaan, indieners, link, bron_hash en de stand "
            "bij KOOP: gewijzigd, status, versie) en per alinea nr, kop en tekst. Noem de datum en het soort uit 'stuk', "
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
        "reeks": list(dossiers) if len(dossiers) > 1 else [], "status": status if status == "Onopgemaakt" else "",
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
    gevonden = list(dict.fromkeys(w.lower() for w in _WOORD_RE.findall(woorden or "")))[:MAX_WOORDEN]
    if not gevonden:
        raise ValueError("geef woorden van minstens drie letters, of een dossiernummer")
    return " AND ".join(f'dt.title any "{w}"' for w in gevonden)


def _per_record(bron: KamerstukBron, cql: str, args: dict[str, Any], offset: int, *, toelichting: str = "",
                leeg: str = "", extra: dict[str, Any] | None = None, dossier: bool = False, maximum: int = LIMIT) -> str:
    """Een pagina in de volgorde van de zoekdienst. Per record één rij of niets; het vervolg telt in records, zoals de
    zoekdienst, en `totaal` is het aantal records van de hele zoekvraag."""
    totaal, deel = bron.zoek(cql, start=offset + 1, maximum=maximum)
    paren = [(i, r) for i, r in enumerate(_rij(rec) for rec in deel) if r]
    titel = _dossiertitel(deel) if dossier else ""

    def maak(k: int) -> str:
        gelezen = paren[k][0] if k < len(paren) else len(deel)
        meer = offset + gelezen < totaal
        return resultaat([r for _, r in paren[:k]], volledig=not meer, totaal=totaal,
                         vervolg={"tool": "zoek_kamerstukken", "args": {**args, "offset": offset + gelezen}}
                         if meer else None,
                         toelichting=toelichting if paren else (leeg or toelichting),
                         extra=compact({**(extra or {}), "dossiertitel": titel}) or None)

    k = len(paren)
    while k > 0 and len(maak(k)) > BUDGET:
        k -= 1
    if paren and k == 0:
        raise TeGroot("zoek_kamerstukken: één rij is groter dan de begroting", omvang=len(maak(1)))
    return maak(k)


def _dossier(bron: KamerstukBron, dossier: str, cql: str, args: dict[str, Any], offset: int) -> str:
    """De stukken van één dossier (of subdossier: `36200-IX` staat als eigen waarde in `w.dossiernummer`)."""
    totaal, _ = bron.zoek(cql, start=1, maximum=0)
    if totaal > MAX_DOSSIER:
        return _per_record(
            bron, cql + _OP_DATUM, args, offset, extra={"volgorde": "oudste", "zoekvraag": _zoekvraag(args, "oudste")},
            dossier=True,
            toelichting=(f"Het dossier {dossier} telt {totaal} stukken: te veel om op nummer te zetten, dus ze staan op "
                         "de datum van het stuk, de oudste eerst. Zoek gericht met dossier én soort, of met volgorde "
                         "'nieuwste'."))
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
    extra = compact({"totaal": len(lijst), "volgorde": "nummer", "dossiertitel": _dossiertitel(records),
                     "zoekvraag": _zoekvraag(args, "nummer")})
    return per_eenheid(lijst, tool="zoek_kamerstukken", args=args, offset=offset,
                       toelichting="" if lijst else f"Geen Kamerstukken in dossier {dossier}.",
                       extra=extra if lijst else None)


def _zoekvraag(args: dict[str, Any], volgorde: str) -> dict[str, Any]:
    """Wat er gezocht is, voor bij een lijst: de filters en de volgorde, zonder het vervolg."""
    return {**{k: v for k, v in args.items() if k not in {"offset", "volgorde"}}, "volgorde": volgorde}


def _datum(waarde: str, *, eind: bool) -> str:
    """'2024' → 2024-01-01 (of 2024-12-31 als eind), '2024-06' → de eerste of laatste dag, '2024-06-01' blijft."""
    m = _DATUM_RE.fullmatch(waarde)
    if not m:
        raise ValueError(waarde)
    jaar, maand, dag = int(m.group(1)), m.group(2), m.group(3)
    if dag:
        return date(jaar, int(maand), int(dag)).isoformat()
    if maand:
        return date(jaar, int(maand), calendar.monthrange(jaar, int(maand))[1] if eind else 1).isoformat()
    return date(jaar, 12, 31).isoformat() if eind else date(jaar, 1, 1).isoformat()


def _vergaderjaar(waarde: str) -> str | None:
    """'2025-2026', '2025/2026' of '2025-26' → '2025-2026'; None als het geen opeenvolgend paar jaren is."""
    m = _JAAR_RE.fullmatch(waarde)
    if not m:
        return None
    begin = int(m.group(1))
    eind = int(m.group(2)) if len(m.group(2)) == 4 else begin // 100 * 100 + int(m.group(2))
    return f"{begin}-{eind}" if eind == begin + 1 else None


_ZINSDEEL_RE = re.compile(r'"([^"]*)"|„([^”]*)”')


def _tekst_cql(tekst: str) -> str:
    """De hele tekst van het stuk (`cql.textAndIndexes`): een zinsdeel tussen aanhalingstekens als zinsdeel (`adj`), de
    losse woorden allemaal (`all`). Live getoetst op 9 nov 2026: 'één bankrekeningnummer' vond de acht stukken uit het
    onderzoek naar één bankrekeningnummer, in de titel drie (meting kamerstukken-tekstzoeken-2026-11-09)."""
    zinsdelen = [" ".join(_WOORD_RE.findall(a or b)).lower() for a, b in _ZINSDEEL_RE.findall(tekst)]
    los = list(dict.fromkeys(w.lower() for w in _WOORD_RE.findall(_ZINSDEEL_RE.sub(" ", tekst))))
    delen, aantal = [], 0
    for z in (z for z in dict.fromkeys(zinsdelen) if z):
        delen.append(f'cql.textAndIndexes adj "{z}"')
        aantal += len(z.split())
    if aantal + len(los) > MAX_WOORDEN:
        # `_zoek` weigert dit al met een invoerfout: hier nooit stil inkorten.
        raise ValueError(f"tekst: hoogstens {MAX_WOORDEN} woorden")
    if los:
        delen.append(f'cql.textAndIndexes all "{" ".join(los)}"')
    if not delen:
        raise ValueError("tekst")
    return " AND " + " AND ".join(delen)


def _soort_cql(soort: str) -> str:
    """Het soort in `w.subrubriek` óf in de titel: bij oudere stukken is de rubriek 'Overig' en staat het soort alleen
    in de titel (kst-33755-3; live, 9 nov 2026)."""
    woorden = list(dict.fromkeys(w.lower() for w in _WOORD_RE.findall(soort)))[:MAX_WOORDEN]
    if not woorden:
        raise ValueError("soort")
    term = " ".join(woorden)
    return f' AND (w.subrubriek all "{term}" OR dt.title all "{term}")'


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
    if tekst and not 0 < len(set(_WOORD_RE.findall(tekst.lower()))) <= MAX_WOORDEN:
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
    if volgorde == "nummer" and aantal is not None:
        return fout("ongeldig_aantal", "op nummer komt het hele dossier op pagina's; laat 'aantal' weg, of kies "
                    "bijvoorbeeld {\"volgorde\": \"nieuwste\", \"aantal\": 10}.")
    args = {**{k: v for k, v in filters.items() if v}, **({"volgorde": a["volgorde"]} if a.get("volgorde") else {}),
            **({"aantal": aantal} if aantal is not None else {})}
    cql = _BASIS + (f' AND w.dossiernummer=="{dossier}"' if dossier else "")
    cql += f' AND w.ondernummer=="{nummer}"' if nummer else ""
    cql += (" AND " + _cql_woorden(woorden)) if woorden else ""
    cql += _tekst_cql(tekst) if tekst else ""
    cql += _soort_cql(soort) if soort else ""
    cql += (f" AND dt.date>={vanaf}" if vanaf else "") + (f" AND dt.date<={tot}" if tot else "")
    cql += f' AND w.vergaderjaar=="{jaar}"' if jaar else ""
    cql += f' AND dt.creator=="{_KAMERS[kamer]}"' if kamer else ""
    if volgorde == "nummer":
        return _dossier(bron, dossier, cql, args, offset)
    return _per_record(bron, cql + _OP_VOLGORDE.get(volgorde, ""), args, offset, dossier=bool(dossier),
                       maximum=aantal or LIMIT, extra={"volgorde": volgorde, "zoekvraag": _zoekvraag(args, volgorde)},
                       leeg="Geen Kamerstukken die aan de zoekvraag voldoen.")


def _platte_tekst(e: ET.Element, overgeslagen: dict[str, int], noten: list[ET.Element] | None = None) -> str:
    """De tekst van een element zonder opmaak. Een voetnoot gaat naar `noten` (als die er is), anders telt hij mee in
    `overgeslagen`: hij hoort niet in de lopende tekst, maar valt ook niet stil weg."""
    delen: list[str] = [e.text or ""]
    for kind in e:
        if kind.tag == "noot" and noten is not None:
            noten.append(kind)
        elif kind.tag in _OVERGESLAGEN:
            overgeslagen[_OVERGESLAGEN[kind.tag]] = overgeslagen.get(_OVERGESLAGEN[kind.tag], 0) + 1
        else:
            delen.append(_platte_tekst(kind, overgeslagen, noten))
        delen.append(kind.tail or "")
    return "".join(delen)


def _voetnoot(noot: ET.Element) -> tuple[str, str, list[str]]:
    """(nummer, tekst, verwijst_naar) van een `<noot>`. Alleen een `extref soort="document"` met een geldige externe
    vindplaats wordt een verwijzing (Lex kan die met de leestool volgen); een URL blijft tekst."""
    nr = " ".join((noot.findtext("noot.nr") or "").split())
    delen = list(noot.iter("noot.al")) or [k for k in noot if k.tag != "noot.nr"]
    tekst = " ".join(" ".join(_platte_tekst(a, {}).split()) for a in delen).strip()
    naar: list[str] = []
    for ref in noot.iter("extref"):
        vp = externe_vindplaats(ref.get("doc") or "") if ref.get("soort") == "document" else None
        if vp is not None and vp.id not in naar:
            naar.append(vp.id)
    return nr, tekst, naar


def _is_inhoudsopgave(tabel: ET.Element) -> bool:
    """De eigen inhoudsopgave van een stuk: een tabel zonder titel die met de cel "Inhoudsopgave" begint. Ze telt apart:
    `inhoud` doet hetzelfde werk, en haar regels zijn geen tekst van het stuk."""
    if tabel.find("title") is not None:
        return False
    eerste = next((" ".join(_platte_tekst(a, {}).split()) for a in tabel.iter("al")), "")
    return eerste.lower() == "inhoudsopgave"


def _cals(tabel: ET.Element, noten: list[ET.Element]) -> tuple[list[str], list[list[str]], int]:
    """(kolomkoppen, rijen met cellen, aantal samengevoegde cellen) van een CALS-tabel, zoals KOOP ze schrijft.

    Een cel die meer kolommen beslaat (`namest`/`nameend`) staat in haar eerste kolom, de rest blijft leeg; een cel die
    meer rijen beslaat (`morerows`) staat alleen in haar eerste rij. Een weergavekeuze, geen herinterpretatie: elke
    waarde staat er letterlijk en één keer, en het aantal samengevoegde cellen zegt het resultaat. Noten in een cel gaan
    naar `noten` (de tabelnoten komen na de rijen)."""
    kolommen: list[str] = []
    rijen: list[list[str]] = []
    samen = 0
    for groep in tabel.iter("tgroup"):
        specs = [c for c in groep if c.tag == "colspec"]
        n = max(int(groep.get("cols") or 0), len(specs))
        index = {c.get("colname"): i for i, c in enumerate(specs) if c.get("colname")}

        def rij_van(rij: ET.Element) -> list[str]:
            nonlocal samen
            cellen, vrij = [""] * n, 0
            for cel in (e for e in rij if e.tag == "entry"):
                begin = index.get(cel.get("namest") or cel.get("colname") or "", vrij)
                eind = index.get(cel.get("nameend") or "", begin)
                if eind > begin or (cel.get("morerows") or "0") != "0":
                    samen += 1
                if begin < n:
                    cellen[begin] = " ".join(_platte_tekst(cel, {}, noten).split())
                vrij = eind + 1
            return cellen

        kop = [rij_van(r) for d in groep if d.tag == "thead" for r in d if r.tag == "row"]
        if kop and not kolommen:
            kolommen = [" ".join(c for c in kolom if c) for kolom in zip(*kop)]
        rijen += [c for d in groep if d.tag == "tbody" for r in d if r.tag == "row" if any(c := rij_van(r))]
    return kolommen, rijen, samen


def alineas(xml: bytes) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, int]]:
    """(kop van het stuk, rijen in documentvolgorde, overgeslagen per soort) uit de XML van een Kamerstuk."""
    kop, rijen, overgeslagen, _ = lees(xml)
    return kop, rijen, overgeslagen


def lees(xml: bytes) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, int], dict[int, tuple[list[dict[str, Any]], int]]]:
    """(kop van het stuk, rijen in documentvolgorde, overgeslagen per soort, tabellen) uit de XML van een Kamerstuk.

    Een rij is een alinea, of een voetnoot direct na de alinea waar hij in staat (`soort: "voetnoot"`, met `noot` en
    `verwijst_naar`); de alinea zelf houdt haar letterlijke tekst en noemt haar noten (`noten`). Een tabel is één rij
    (`soort: "tabel"`, de titel als tekst, met de omvang); haar inhoud staat in `tabellen[nr]`: de kop (de titel met de
    kolommen als `cellen`), per tabelrij `{soort: "tabelrij", cellen, tekst}` en de tabelnoten, met het aantal
    samengevoegde cellen. Eén nummering per stuk (`nr`), want het blok `extern` voegt pagina's samen op `nr`."""
    root = ET.fromstring(xml)
    stuk = root.find(".//stuk")
    if stuk is None:
        raise ValueError("geen stuk in het document")
    overgeslagen: dict[str, int] = {}
    uit: list[dict[str, Any]] = []
    tabellen: dict[int, tuple[list[dict[str, Any]], int]] = {}
    teller = [0]

    def volgende() -> int:
        teller[0] += 1
        return teller[0]

    def voetnootrijen(noten: list[ET.Element], kop: str) -> list[dict[str, Any]]:
        rijen: list[dict[str, Any]] = []
        for nr, ntekst, naar in (_voetnoot(n) for n in noten):
            if not ntekst:  # een lege noot valt niet stil weg
                overgeslagen["voetnoot"] = overgeslagen.get("voetnoot", 0) + 1
            else:
                rijen.append(compact({"nr": volgende(), "soort": "voetnoot", "noot": nr, "kop": kop, "tekst": ntekst,
                                      "verwijst_naar": naar}))
        return rijen

    def kop_van(divisie: ET.Element) -> str:
        kop = divisie.find("kop")
        if kop is None:
            return ""
        return " ".join(" ".join(_platte_tekst(k, {}).split()) for k in kop if k.tag in {"nr", "titel"}).strip()

    def loop(e: ET.Element, koppen: tuple[str, ...]) -> None:
        # Een `tussenkop` ("Artikel I (artikel 30hb …)") geldt voor de alinea's die erna komen in dezelfde divisie: in de
        # artikelsgewijze toelichting zegt juist die kop bij welk artikel een alinea hoort. Eerst viel hij stil weg.
        tussen = ""
        for kind in e:
            hier = (*koppen, tussen) if tussen else koppen
            if kind.tag in {"table", "tabel"} and _is_inhoudsopgave(kind):
                overgeslagen["inhoudsopgave"] = overgeslagen.get("inhoudsopgave", 0) + 1
            elif kind.tag in {"table", "tabel"} and kind.find(".//tgroup") is not None:
                # Alleen een CALS-tabel (met `tgroup`) is te lezen als tabel; iets anders telt in `overgeslagen`.
                kop, nr, noten = " › ".join(hier), volgende(), []
                titel = (" ".join(_platte_tekst(kind.find("title"), {}).split()) if kind.find("title") is not None
                         else "") or "Tabel zonder titel"
                kolommen, cellen, samen = _cals(kind, noten)
                inhoud_t = [compact({"nr": nr, "soort": "tabel", "kop": kop, "tekst": titel, "cellen": kolommen})]
                inhoud_t += [{"nr": volgende(), "soort": "tabelrij", "cellen": c, "tekst": " | ".join(c)} for c in cellen]
                inhoud_t += voetnootrijen(noten, kop)
                tabellen[nr] = (inhoud_t, samen)
                breed = max([len(kolommen), *(len(c) for c in cellen)], default=0)
                # `tot_nr`: het laatste nr van de tabel; een passage over de tabel heen toont dan de titel, en wie de
                # rijen wil, opent de tabel.
                uit.append({"nr": nr, "soort": "tabel", **({"kop": kop} if kop else {}), "tekst": titel,
                            "tot_nr": teller[0],
                            "omvang": f"{len(cellen)} {'rij' if len(cellen) == 1 else 'rijen'}, {breed} "
                                      f"{'kolom' if breed == 1 else 'kolommen'}"})
            elif kind.tag in _OVERGESLAGEN:
                overgeslagen[_OVERGESLAGEN[kind.tag]] = overgeslagen.get(_OVERGESLAGEN[kind.tag], 0) + 1
            elif kind.tag == "tussenkop":
                tussen = " ".join(_platte_tekst(kind, overgeslagen).split())
            elif kind.tag == "divisie":
                kop = kop_van(kind)
                loop(kind, (*hier, kop) if kop else hier)
            elif kind.tag == "al":
                noten: list[ET.Element] = []
                tekst = " ".join(_platte_tekst(kind, overgeslagen, noten).split())
                kop = " › ".join(hier)
                gelezen = [_voetnoot(n) for n in noten]
                if tekst:
                    uit.append(compact({"nr": volgende(), "kop": kop, "tekst": tekst,
                                        "noten": [nr for nr, _, _ in gelezen if nr]}))
                uit.extend(voetnootrijen(noten, kop))
            elif kind.tag not in {"kop", "stuknr", "titel"}:
                loop(kind, hier)

    loop(stuk, ())
    titel = " ".join(_platte_tekst(stuk.find("titel"), {}).split()) if stuk.find("titel") is not None else ""
    return {"documenttitel": titel}, uit, overgeslagen, tabellen


def inhoud(rijen: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """De koppen van het stuk met de offset waar ze beginnen, voor de eerste pagina, en of dat alle koppen zijn. Zo springt
    Lex naar het deel dat de vraag raakt in plaats van het stuk pagina voor pagina te lezen (acceptatie 8 nov 2026: twee
    pagina's gelezen, de artikelsgewijze toelichting niet). Het diepste niveau dat helemaal past (hoogstens `MAX_INHOUD`
    koppen en een kwart van de begroting: de inhoud wijst de weg, de alinea's zijn de inhoud); past zelfs het bovenste
    niveau niet, dan het begin ervan, en dat zegt het resultaat (`inhoud_ingekort`). Leeg bij één kop."""
    def koppen(diepte: int | None) -> list[dict[str, Any]]:
        uit: list[dict[str, Any]] = []
        for i, r in enumerate(rijen):
            delen = r.get("kop", "").split(" › ")
            kop = " › ".join(delen[:diepte] if diepte else delen)
            if kop and all(u["kop"] != kop for u in uit):
                uit.append({"kop": kop, "offset": i})
        return uit

    def past(lijst: list[dict[str, Any]]) -> bool:
        return len(lijst) <= MAX_INHOUD and len(json.dumps(lijst, ensure_ascii=False)) <= BUDGET // 4

    for diepte in (None, 2, 1):
        if past(lijst := koppen(diepte)):
            return (lijst, True) if len(lijst) > 1 else ([], True)
    lijst = koppen(1)
    while lijst and not past(lijst):
        lijst = lijst[:-1]
    return lijst, False


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
    # Een tabel is één rij met `openen`: verdieping buiten de scope van deze pagina, geen onvolledigheid.
    rijen = [{**r, "openen": {"tool": "get_kamerstuk", "args": {"id": vp.id, "tabel": r["nr"]}}}
             if r.get("soort") == "tabel" else r for r in rijen]
    extra = {"stuk": stuk, **({"overgeslagen": overgeslagen} if overgeslagen else {}), "totaal": len(rijen)}
    if offset == 0:
        inh, alle = inhoud(rijen)
        if inh:
            extra["inhoud"] = inh
        if not alle:
            extra["inhoud_ingekort"] = True
    return per_eenheid(rijen, tool="get_kamerstuk", args={"id": vp.id}, offset=offset, extra=extra,
                       toelichting=toelichting or ("" if rijen else "Dit stuk heeft geen lopende tekst in de XML."))


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
