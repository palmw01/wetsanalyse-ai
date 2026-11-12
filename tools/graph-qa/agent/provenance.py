"""
Bron-provenance uit de tool-executietrace.

Kern van de juridische betrouwbaarheid: bronnen komen uit wat de graaf
daadwerkelijk terugstuurde, NIET uit de prozatekst van het model. Zo passeert een
gehallucineerde citatie niet als "bron", en gaat een echte vindplaats niet verloren
als het model de IRI parafraseert zonder hem uit te typen.

De citatie-herkenning (`iter_refs`) wordt gedeeld met `agent/grounding.py`, dat
dezelfde patronen op de antwoordtekst toepast om niet-onderbouwde verwijzingen te
markeren. We herkennen:
  - document-IRI's in de eigen graafruimte  (zie `agent/namespace.py`)
  - jci-vindplaatsstrings                    (jci1.3:c:BWBR....)
  - kale BWB-id's                            (BWBR\\d+), alleen als losse bron
  - externe identifiers (ADR-013)            kst-/stb-/stcrt-…, ECLI, CELEX, ELI (`bronmodel.extern`)
De vocabulaire-namespace (`ONTOLOGIE`) valt er bewust buiten:
dat zijn predicaten, geen vindplaatsen.
"""
from __future__ import annotations

import re
from typing import Any
from collections.abc import Iterable, Iterator

from bronmodel.connectors import CONNECTORS
from bronmodel.extern import ExterneVindplaats, externe_verwijzingen, externe_vindplaats
from bronmodel.vindplaats import vindplaats

from .models import Source
from .resultaat import is_contract, is_fout, is_foutresultaat, waarden
from .namespace import vindplaats_patroon
from .tools.begrip_tools import AFGELEIDE_TOOL_NAMEN

# Backslash uitgesloten uit de char-class zodat een naijlende escape (bv. "...g=2026-07-01\\")
# niet mee in de IRI/jci wordt gezogen; een backtick of sterretje ook niet: het model zet een IRI in
# Markdown (`` `urn:bwb:…` ``, **…**), en dan stond er "urn:bwb:BWBR0004770:artikel:9`" als vindplaats.
_IRI_RE = re.compile(vindplaats_patroon())
_JCI_RE = re.compile(r"jci[\d.]+:c:BWBR\d+[^\s\"'<>)\]}\\`*]*")
_BWB_RE = re.compile(r"\bBWBR\d+\b")
# De JAS-annotatielagen (`urn:jas:…`, door de api in de graaf gezet) dragen het BWB-id in hun IRI:
# `urn:jas:annotatie:BWBR0004770:artikel:9:e1`. Een annotatie is afgeleide duiding, geen vindplaats –
# telde dat id als losse bron, dan leek een annotatie de wettekst te onderbouwen terwijl er geen
# wettekst was opgehaald. Die IRI's worden daarom weggelaten vóór het zoeken.
_AFGELEID_RE = re.compile(r"urn:jas[:\-][^\s\"'<>)\]}\\`*]*")


#: De tools van een connector die wettekst buiten de kennisgraaf leest (`wettekst_live`). Hun rijen dragen BWB-id's en
#: jci's van een toestand die niet in de graaf staat; telde `iter_refs` die, dan stond er een graafbron in de lijst die de
#: werkplek uit de graaf opent (en daar niet vindt). Van zo'n tool telt alleen het gelezen stuk, onder zijn eigen id.
LIVE_WETTEKST_TOOLS: frozenset[str] = frozenset(
    t for c in CONNECTORS.values() if c.brontype == "wettekst_live" for t in c.tools)


def _gelezen_live(text: str) -> ExterneVindplaats | None:
    stuk = (is_contract(text) or {}).get("stuk")
    vp = externe_vindplaats(str(stuk.get("id") or "")) if isinstance(stuk, dict) else None
    return vp if vp is not None and vp.brontype == "wettekst_live" else None


def _clean(uri: str) -> str:
    return uri.rstrip(".,;\\")


def first_bwb(text: str) -> str | None:
    """Eerste BWB-id in een tekst/citatie, of None."""
    m = _BWB_RE.search(text)
    return m.group(0) if m else None


def iter_refs(text: str) -> Iterator[tuple[str, str | None, str | None]]:
    """Yield (uri, iri, jci) voor elke vindplaats-verwijzing in de tekst (ontdubbeld).

    Een kale BWB-id levert alleen een verwijzing op als hij niet al binnen een
    gevonden IRI/jci valt.
    """
    seen: set[str] = set()
    text = _AFGELEID_RE.sub(" ", text)

    def emit(uri: str, *, iri: str | None = None, jci: str | None = None):
        uri = _clean(uri)
        if uri and uri not in seen:
            seen.add(uri)
            return (uri, iri, jci)
        return None

    for m in _IRI_RE.finditer(text):
        r = emit(m.group(0), iri=_clean(m.group(0)))
        if r:
            yield r
    for m in _JCI_RE.finditer(text):
        r = emit(m.group(0), jci=_clean(m.group(0)))
        if r:
            yield r
    for m in _BWB_RE.finditer(text):
        bwb = m.group(0)
        if any(bwb in u for u in seen):
            continue
        r = emit(bwb)
        if r:
            yield r
    # Een externe bron (een Kamerstuk, een uitspraak, EU-recht) staat onder zijn canonieke id.
    for ext in externe_verwijzingen(text):
        r = emit(ext.id)
        if r:
            yield r


def citations_in(text: str) -> list[str]:
    """Platte lijst van vindplaats-verwijzingen in de tekst (voor grounding)."""
    return [uri for uri, _, _ in iter_refs(text)]


def _labels(text: str) -> dict[str, str]:
    """IRI → label uit de rijen van een contractresultaat. Een wet-lokale `id:`-node (een divisie van de
    Leidraad) heeft geen label in zijn IRI, maar de tool die hem vond wél: zonder dit stond hij in de
    bronnenlijst als `urn:bwb:BWBR0024096:id:…divisie26.5`."""
    # Ook een fout kan een stuk dragen (`alleen_pdf`, een buitenlandse ECLI): dat label hoort mee, anders stond het stuk
    # met zijn kale id in de bronnenlijst ("kst-1278484", meting Kamerstukken ronde 3, K12).
    data = is_contract(text) or is_foutresultaat(text)
    uit: dict[str, str] = {}
    # Het gelezen stuk van een leestool draagt het label van de bron zelf ("Stb. 2010, 185 (herdruk)"); het label uit het
    # id kent alleen "versie n1" (meting bekendmakingen B12).
    stuk = (data or {}).get("stuk")
    if isinstance(stuk, dict) and isinstance(stuk.get("id"), str) and isinstance(stuk.get("label"), str) and stuk["label"]:
        uit[stuk["id"]] = stuk["label"]
    for rij in (data or {}).get("resultaten", []):
        if isinstance(rij, dict) and isinstance(rij.get("label"), str) and rij["label"]:
            for veld in ("node", "iri", "id"):
                if isinstance(rij.get(veld), str):
                    uit.setdefault(rij[veld], rij["label"])
    return uit


def _met_titel(label: str, uit_tool: str) -> str:
    """"Hoofdstuk II" + "Hoofdstuk II – Invordering in eerste aanleg" → het label mét titel.

    Een structuurdeel heet in de vindplaats alleen naar zijn nummer; het antwoord noemt het juist naar
    zijn titel. Met de titel erbij is de bronnenlijst leesbaar en herkent de werkplek het deel in de
    tekst (de 3D-knop opent zo de hoofdstukken die het antwoord noemt). Alleen als het toollabel
    hetzelfde deel aanduidt als het laatste segment van de vindplaats."""
    kop, streep, titel = uit_tool.partition(" – ")
    laatste = label.rsplit(", ", 1)[-1]
    if streep and titel and " – " not in label and kop.strip().lower() == laatste.strip().lower():
        return f"{label} – {titel.strip()}"
    return label


#: De tools die regelingen opsommen in plaats van bepalingen te zoeken.
REGELINGTOOLS = frozenset({"list_regelingen", "zoek_regelingen"})


def alleen_genoemde_regelingen(sources: list[Any], tekst: str) -> list[Any]:
    """Een regeling uit een overzicht of een zoekresultaat is alleen een bron als het antwoord haar noemt, bij naam,
    afkorting of BWB-id. Twee gevallen, één regel:

    - een regeling uit een tool die regelingen opsomt (`REGELINGTOOLS`; wetgeving_live ronde 5, I20: de zeven regelingen
      van `list_regelingen` bij een antwoord over een andere wet). "Welke regelingen zitten erin?" noemt ze, en daar
      blijven ze staan;
    - een bepaling die alleen een zoektool vond (`_zoektools`), uit een regeling die de beurt verder niet las (Staatsblad
      ronde 5, I04: acht Awb-bepalingen uit één `semantic_search` bij een arrest uit 1959). Noemt het antwoord het
      artikel zelf ("artikel 9"), dan blijft ze ook staan.

    Na `met_regelingnamen`: dan draagt de bron haar naam en afkortingen."""
    laag = (tekst or "").lower()
    zoek = _zoektools()
    gelezen = {getattr(s, "bwb_id", "") for s in sources if getattr(s, "origin_tool", "") not in zoek | REGELINGTOOLS}

    def genoemd(naam: str) -> bool:
        return bool(naam) and re.search(rf"(?<!\w){re.escape(naam.lower())}(?!\w)", laag) is not None

    def regeling_genoemd(s: Any) -> bool:
        return any(genoemd(n) for n in (s.regeling or "", s.bwb_id or "", *(s.afkortingen or [])))

    def weg(s: Any) -> bool:
        tool, soort = getattr(s, "origin_tool", ""), getattr(s, "soort", "")
        if tool in REGELINGTOOLS and soort == "regeling":
            return not (regeling_genoemd(s) or genoemd(s.label or ""))
        if tool in zoek and soort and soort != "regeling" and s.bwb_id and s.bwb_id not in gelezen:
            artikel = re.match(r"(?:Artikel|Bepaling|Divisie)\s+([\w:.]+)", s.label or "")
            return not (regeling_genoemd(s) or (artikel and genoemd(f"artikel {artikel.group(1)}")))
        return False

    return [s for s in sources if not weg(s)]


def _zoektools() -> frozenset[str]:
    """De tools die zoeken in plaats van lezen, uit het register van wat Lex raadpleegt (`spoorbronnen`)."""
    from .spoorbronnen import bronnen

    # Een tool die regelingen opsomt, levert juist regelingen als antwoord ("welke regelingen zitten er in de
    # kennisgraaf?"): die regelingen zijn de bron.
    return frozenset(t for b in bronnen() for t in b.zoektools) - REGELINGTOOLS


def collect_sources(entries: Iterable[tuple[str, str]]) -> list[Source]:
    """Bouw een ontdubbelde bronnenlijst uit (tool_naam, resultaat_tekst)-paren.

    Ontdubbeld op de bronnode (`bronmodel.vindplaats`), niet op de string: een zoektool levert per
    treffer de graaf-IRI én de jci, en die waren twee bronnen met elk hun eigen label. Nu één, met
    `uri` = de graaf-IRI, beide vormen in `iri`/`jci` en een leesbaar label. Een verwijzing zonder
    vindplaats blijft zoals hij was, als vangnet.
    """
    sources: list[Source] = []
    per_node: dict[str, Source] = {}

    for tool, text in entries:
        # Een foutresultaat zonder stuk is geen bron: zijn voorbeeld ({"bwb_id": "BWBR0004770", …}) zette de Invorderingswet in de
        # bronnenlijst bij een ECLI die niet bestaat (meting Rechtspraak R14, 11 nov 2026).
        if not text or tool in AFGELEIDE_TOOL_NAMEN or (is_fout(text) and '"stuk"' not in text):
            continue
        labels = _labels(text)
        if tool in LIVE_WETTEKST_TOOLS:
            if (ext := _gelezen_live(text)) is not None and ext.id not in per_node:
                bron = Source(label=labels.get(ext.id) or ext.label, uri=ext.id, origin_tool=tool,
                              brontype=ext.brontype, link=ext.uri or None)
                per_node[ext.id] = bron
                sources.append(bron)
            continue
        # De waarden van een contractresultaat (`resultaat.waarden`), niet zijn JSON-tekst.
        for uri, iri, jci in iter_refs(waarden(text)):
            if (ext := externe_vindplaats(uri)) is not None:
                if ext.id not in per_node:
                    bron = Source(label=labels.get(ext.id) or ext.label, uri=ext.id, origin_tool=tool,
                                  brontype=ext.brontype, link=ext.uri or None)
                    per_node[ext.id] = bron
                    sources.append(bron)
                continue
            vp = vindplaats(uri)
            # Een regeling die alleen in een zoekresultaat staat (het BWB-id bij een treffer, een lijst regelingen), is
            # niet gelezen en dus geen bron; een bepaling die de zoektool vond, wel (search_wetgeving geeft haar tekst).
            # Meting wetgeving_live ronde 2, I03/I20: de Awb, AWR en Awir in de bronnenlijst na alleen een zoekvraag.
            if vp is not None and vp.soort == "regeling" and tool in _zoektools():
                continue
            sleutel = vp.bron_iri if vp else uri
            if (bestaand := per_node.get(sleutel)) is not None:
                bestaand.iri = bestaand.iri or iri
                bestaand.jci = bestaand.jci or jci
                continue
            if vp is None:
                bron = Source(label=uri, uri=uri, iri=iri, jci=jci, origin_tool=tool)
            else:
                # Een regeling heeft geen label in de verwijzing (de naam komt in finalize); een
                # wet-lokale `id:`-node ook niet: die krijgt het label uit het toolresultaat, en
                # houdt alleen zonder dat zijn IRI.
                label = vp.label or (vp.bwb_id if vp.soort == "regeling"
                                     else labels.get(vp.bron_iri) or labels.get(uri) or vp.bron_iri)
                label = _met_titel(label, labels.get(vp.bron_iri) or labels.get(uri) or "")
                bron = Source(label=label, uri=vp.bron_iri, iri=iri, jci=jci,
                              origin_tool=tool, bron_iri=vp.bron_iri, bwb_id=vp.bwb_id, soort=vp.soort)
            per_node[sleutel] = bron
            sources.append(bron)

    return sources
