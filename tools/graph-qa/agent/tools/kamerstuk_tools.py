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

from ..resultaat import BUDGET, TeGroot, compact, fout, per_eenheid, resultaat

#: Uit de beschrijving (`bronmodel.connectors`); de poorttest toetst dat `KAMERSTUK_TOOLS` precies deze namen heeft.
KAMERSTUK_TOOL_NAMEN = KAMERSTUKKEN.tools
CONNECTOR = KAMERSTUKKEN.naam

_DOSSIER_RE = re.compile(r"^\d{4,6}(?:-[A-Z0-9]{1,6})?$")
_WOORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]{3,}")
MAX_WOORDEN = 6
LIMIT = 25
#: Tot zo veel stukken zet de tool een dossier zelf op nummer: ze haalt ze allemaal op. De zoekdienst sorteert
#: `w.ondernummer` als tekst ("10" vóór "2"), dus dat kan hij niet zelf. Een groter dossier staat op datum van
#: publicatie (`sortBy dt.available`), per record gepagineerd met een exact vervolg: nooit afgekapt.
MAX_DOSSIER = 1000
#: Records per aanroep bij het ophalen van een dossier (de zoekdienst staat er 1000 toe).
_STAP = 250
#: `dt.type==Kamerstuk` laat de bijlagen weg; `w.publicatienaam==Kamerstuk` alleen doet dat niet.
_BASIS = "c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk AND dt.type==Kamerstuk"
_OP_DATUM = " sortBy dt.available/sort.ascending"
#: Elementen die geen lopende tekst zijn; ze worden geteld en genoemd, nooit stil weggelaten.
_OVERGESLAGEN = {"tabel": "tabel", "illustratie": "illustratie", "noot": "voetnoot"}


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
            "Zoek Kamerstukken (wetsgeschiedenis: voorstel van wet, memorie van toelichting, nota's, verslagen, het "
            "advies van de Raad van State en het nader rapport) in de officiële publicaties. Met 'dossier' alle "
            "stukken van dat dossier op volgorde van nummer; met 'woorden' Kamerstukken waarvan de titel elk woord "
            "draagt (bijvoorbeeld de naam van een wet)." + _UITLEG + "\n"
            "GEEFT TERUG per stuk: id (kst-…), label, stuk (het soort, zoals 'Memorie van toelichting' of 'MvT'), "
            "datum, vergaderjaar en link; bij een dossier ook de dossiertitel en de volgorde: 'nummer' (tot "
            f"{MAX_DOSSIER} stukken) of 'datum' (een groter dossier). Zoek in een groot dossier gericht met dossier "
            "én woorden, bijvoorbeeld 'memorie van toelichting'." + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dossier": {"type": "string", "description": "Dossiernummer, bijvoorbeeld '33755' of '36200-IX'."},
                "woorden": {"type": "string", "description": "Woorden uit de titel, bijvoorbeeld 'Invorderingswet'."},
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
            "het id uit zoek_kamerstukken." + _UITLEG + " Citeer letterlijk uit 'tekst'.\n"
            "GEEFT TERUG: het stuk (id, label, titel, link, bron_hash en de stand bij KOOP: gewijzigd, documentstatus, "
            "versie) en per alinea nr, kop en tekst. Is de documentstatus 'Onopgemaakt', zeg dan dat de opgemaakte versie "
            "kan afwijken; staat er gevalideerd: false, dan kon de nieuwste versie niet worden gecontroleerd. Tabellen, "
            "illustraties en voetnoten staan er niet in; de telling ervan staat in 'overgeslagen'." + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Het id van het stuk, bijvoorbeeld 'kst-33755-3'."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
]


def _ondersleutel(nummer: str) -> tuple:
    return tuple((0, int(x)) if x.isdigit() else (1, x) for x in re.findall(r"\d+|\D+", nummer or ""))


def _rij(rec: Any) -> dict[str, Any] | None:
    vp = externe_vindplaats(rec.id)
    if vp is None or vp.brontype != "kamerstuk" or not rec.id.startswith("kst-"):
        return None
    # Het soort stuk staat achteraan de titel ("<dossiertitel>; Memorie van toelichting"); de dossiertitel herhaalt
    # zich per stuk en gaat één keer mee (`dossiertitel`).
    stuk = rec.titel.rsplit("; ", 1)[-1] if "; " in rec.titel else rec.titel
    return compact({"id": vp.id, "label": vp.label, "stuk": stuk, "datum": rec.datum,
                    "vergaderjaar": rec.vergaderjaar, "link": vp.uri, "versie": getattr(rec, "versie", "")})


def _dossiertitel(records: list[Any]) -> str:
    return next((r.titel.rsplit("; ", 1)[0] for r in records if "; " in r.titel), "")


def _cql_woorden(woorden: str) -> str:
    gevonden = list(dict.fromkeys(w.lower() for w in _WOORD_RE.findall(woorden or "")))[:MAX_WOORDEN]
    if not gevonden:
        raise ValueError("geef woorden van minstens drie letters, of een dossiernummer")
    return " AND ".join(f'dt.title any "{w}"' for w in gevonden)


def _per_record(bron: KamerstukBron, cql: str, args: dict[str, Any], offset: int, *, toelichting: str = "",
                leeg: str = "", extra: dict[str, Any] | None = None, dossier: bool = False) -> str:
    """Een pagina in de volgorde van de zoekdienst. Per record één rij of niets; het vervolg telt in records, zoals de
    zoekdienst, en `totaal` is het aantal records van de hele zoekvraag."""
    totaal, deel = bron.zoek(cql, start=offset + 1, maximum=LIMIT)
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
            bron, cql + _OP_DATUM, args, offset, extra={"volgorde": "datum"}, dossier=True,
            toelichting=(f"Het dossier {dossier} telt {totaal} stukken: te veel om op nummer te zetten, dus ze staan op "
                         "datum van publicatie. Zoek gericht met dossier én woorden, bijvoorbeeld 'memorie van "
                         "toelichting'."))
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
    extra = compact({"totaal": len(lijst), "volgorde": "nummer", "dossiertitel": _dossiertitel(records)})
    return per_eenheid(lijst, tool="zoek_kamerstukken", args=args, offset=offset,
                       toelichting="" if lijst else f"Geen Kamerstukken in dossier {dossier}.",
                       extra=extra if lijst else None)


def _zoek(bron: KamerstukBron, a: dict[str, Any]) -> str:
    dossier = (a.get("dossier") or "").strip().upper().replace(" ", "")
    offset = max(int(a.get("offset") or 0), 0)
    if dossier and not _DOSSIER_RE.fullmatch(dossier):
        return fout("ongeldig_dossier", f"'{dossier}' is geen dossiernummer (bijvoorbeeld '33755' of '36200-IX').")
    if not dossier and not (a.get("woorden") or "").strip():
        return fout("ongeldige_argumenten", "geef een dossiernummer of woorden uit de titel, bijvoorbeeld "
                    "{\"dossier\": \"33755\"} of {\"woorden\": \"Invorderingswet\"}")
    args = {k: v for k, v in (("dossier", dossier), ("woorden", (a.get("woorden") or "").strip())) if v}
    cql = _BASIS + (f' AND w.dossiernummer=="{dossier}"' if dossier else "")
    if args.get("woorden"):
        cql += " AND " + _cql_woorden(args["woorden"])
    if dossier and not args.get("woorden"):
        return _dossier(bron, dossier, cql, args, offset)
    # Met een dossier op datum, voor een vaste volgorde; alleen woorden houdt de rangschikking van de zoekdienst.
    return _per_record(bron, cql + (_OP_DATUM if dossier else ""), args, offset, dossier=bool(dossier),
                       leeg="Geen Kamerstukken met die woorden in de titel.")


def _platte_tekst(e: ET.Element, overgeslagen: dict[str, int]) -> str:
    delen: list[str] = [e.text or ""]
    for kind in e:
        if kind.tag in _OVERGESLAGEN:
            overgeslagen[_OVERGESLAGEN[kind.tag]] = overgeslagen.get(_OVERGESLAGEN[kind.tag], 0) + 1
        else:
            delen.append(_platte_tekst(kind, overgeslagen))
        delen.append(kind.tail or "")
    return "".join(delen)


def alineas(xml: bytes) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, int]]:
    """(kop van het stuk, alinea's in documentvolgorde, overgeslagen per soort) uit de XML van een Kamerstuk."""
    root = ET.fromstring(xml)
    stuk = root.find(".//stuk")
    if stuk is None:
        raise ValueError("geen stuk in het document")
    overgeslagen: dict[str, int] = {}
    uit: list[dict[str, Any]] = []

    def kop_van(divisie: ET.Element) -> str:
        kop = divisie.find("kop")
        if kop is None:
            return ""
        return " ".join(" ".join(_platte_tekst(k, {}).split()) for k in kop if k.tag in {"nr", "titel"}).strip()

    def loop(e: ET.Element, koppen: tuple[str, ...]) -> None:
        for kind in e:
            if kind.tag in _OVERGESLAGEN:
                overgeslagen[_OVERGESLAGEN[kind.tag]] = overgeslagen.get(_OVERGESLAGEN[kind.tag], 0) + 1
            elif kind.tag == "divisie":
                kop = kop_van(kind)
                loop(kind, (*koppen, kop) if kop else koppen)
            elif kind.tag == "al":
                tekst = " ".join(_platte_tekst(kind, overgeslagen).split())
                if tekst:
                    uit.append(compact({"nr": len(uit) + 1, "kop": " › ".join(koppen), "tekst": tekst}))
            elif kind.tag not in {"kop", "stuknr", "titel"}:
                loop(kind, koppen)

    loop(stuk, ())
    titel = " ".join(_platte_tekst(stuk.find("titel"), {}).split()) if stuk.find("titel") is not None else ""
    return {"documenttitel": titel}, uit, overgeslagen


def _get(bron: KamerstukBron, a: dict[str, Any]) -> str:
    vp = externe_vindplaats((a.get("id") or "").strip())
    if vp is None or not vp.id.startswith("kst-"):
        return fout("ongeldig_id", "geef het id van een Kamerstuk, bijvoorbeeld 'kst-33755-3'")
    doc = bron.document(vp.id)
    try:
        kop, rijen, overgeslagen = alineas(doc.xml)
    except (ET.ParseError, ValueError) as exc:
        return fout("onleesbaar_document", f"{vp.id} kon niet worden gelezen: {exc}")
    # De versie die Lex las (review ADR-013, punt 3): de hash van de XML en de stand bij KOOP. Een onopgemaakte versie
    # wordt later vervangen door de opgemaakte; `gevalideerd: false` als de dienst bij het valideren niet te bereiken was.
    stuk = compact({"id": vp.id, "label": vp.label, "titel": kop["documenttitel"], "link": vp.uri,
                    "bron_hash": doc.hash, "gewijzigd": getattr(doc, "gewijzigd", ""),
                    "documentstatus": getattr(doc, "documentstatus", ""), "versie": getattr(doc, "versie", ""),
                    **({"gevalideerd": False} if getattr(doc, "gevalideerd", True) is False else {})})
    extra = {"stuk": stuk, **({"overgeslagen": overgeslagen} if overgeslagen else {}), "totaal": len(rijen)}
    return per_eenheid(rijen, tool="get_kamerstuk", args={"id": vp.id}, offset=max(int(a.get("offset") or 0), 0),
                       extra=extra, toelichting="" if rijen else "Dit stuk heeft geen lopende tekst in de XML.")


def dispatch_kamerstuk(name: str, args: dict[str, Any], bron: KamerstukBron | None) -> str:
    if bron is None:
        return fout("connector_uit", "De bron Kamerstukken staat uit. Zeg dat, en antwoord niet uit eigen kennis.")
    if name == "zoek_kamerstukken":
        return _zoek(bron, args)
    if name == "get_kamerstuk":
        return _get(bron, args)
    raise KeyError(name)
