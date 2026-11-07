"""Het detail van één bepaling voor het paneel naast het gesprek: wat de graaf er verder over weet (ADR-008, *Detail bij een antwoord*).

Een antwoord van Lex draagt `doelen`; het paneel haalt per doel hier de feiten op. Zonder model en zonder de trace van de beurt:
elke waarde is een triple uit de graaf, en wat de graaf niet heeft blijft leeg. De vorm staat in `bepaling_graaf_contract`, dat
het werkgebiedrapport deelt.

`detail_uit` is puur (te testen zonder graaf); `bepaling_detail` haalt de rijen op. Een haperende graaf geeft
`beschikbaar: false`, nooit een leeg detail dat leest als "hier is niets bekend".
"""
from __future__ import annotations

import logging
import re

import httpx
from bronmodel.antwoord import Vindplaats
from bronmodel.vindplaats import vindplaats as bron_vindplaats

from . import graaf as graaf_mod
from .bepaling_graaf import _IN, _UIT, _tellingen, aantallen_uit
from .bepaling_graaf_contract import MAX_UITGAAND, MAX_VOORBEELDEN, BepalingDetail, Structuurdeel, Telling, Verwijzing
from .graaf_client import sparql_select
from .knoopinfo import BWB, MAX_TRIPLES, _regeling_geldigheid, _uitgaand
from .samenhang import _IRI, _PREFIXES

log = logging.getLogger(__name__)

_BWB_ID = re.compile(r"urn:bwb:(BWB[RV]\d+)")
#: Een bovengrens op de verwijzingsquery: een artikel met veel leden wordt door de Leidraad vaak honderden keren genoemd.
MAX_VERWIJZINGSRIJEN = 1000


def _verwijzingen(iri: str, richting: str) -> str:
    """De verwijzingen vanuit de bepaling en haar leden en onderdelen (`uit`), of die ernaar (`in`): verwijzingen hangen aan het
    lid, niet aan het artikel (graph-qa CLAUDE.md). Met de vindplaats van beide kanten, zoals de graaf hem noemt. Elke richting
    heeft een eigen begrenzing: honderden verwijzingen uit de Leidraad mogen de uitgaande niet verdringen. Een verwijzing binnen
    de bepaling zelf telt niet als "verwezen door"."""
    patroon = (_UIT if richting == "uit" else _IN).format(iri=iri)
    return _PREFIXES + f"""SELECT ?richting ?van ?naar ?anker ?vanLabel ?naarLabel ?naarInGraaf WHERE {{
  BIND("{richting}" AS ?richting) {patroon}
  OPTIONAL {{ ?van bwb:vindplaats ?vanLabel }}
  OPTIONAL {{ ?naar bwb:vindplaats ?naarLabel }}
  BIND(EXISTS {{ ?naar bwb:nummer ?n }} || EXISTS {{ ?naar bwb:citeertitel ?c }} AS ?naarInGraaf)
}} LIMIT {MAX_VERWIJZINGSRIJEN}"""


def _titels(iris: list[str]) -> str:
    waarden = " ".join(f"<{i}>" for i in iris if _IRI.fullmatch(i))
    return _PREFIXES + f"SELECT ?d ?titel WHERE {{ VALUES ?d {{ {waarden} }} ?d bwb:titel ?titel }}"


def _citeertitels(bwb_ids: list[str]) -> str:
    waarden = " ".join(f"<urn:bwb:{b}>" for b in bwb_ids if re.fullmatch(r"BWB[RV]\d+", b))
    return _PREFIXES + f"SELECT ?r ?titel WHERE {{ VALUES ?r {{ {waarden} }} ?r bwb:citeertitel ?titel }}"


def _bwb(iri: str) -> str:
    m = _BWB_ID.match(iri or "")
    return m.group(1) if m else ""


def _natuurlijk(tekst: str) -> tuple:
    return tuple((0, int(d), "") if d.isdigit() else (1, 0, d) for d in re.findall(r"\d+|\D+", tekst.casefold()))


def _vindplaats(iri: str, label: str, titels: dict[str, str]) -> Vindplaats:
    """De vindplaats zoals de werkplek hem elders toont: het label uit `bronmodel` (de IRI-vorm, voor een wet), anders wat de
    graaf zegt (een Leidraad-divisie heeft een `id:`-IRI), en de citeertitel van de regeling."""
    vp = bron_vindplaats(iri)
    regeling = titels.get(_bwb(iri), "")
    # Een regeling zelf heeft geen label in `bronmodel`: dan haar citeertitel, en kent de graaf die niet (een regeling die niet
    # is geïmporteerd), dan het BWB-id – nooit de kale IRI.
    eigen = (vp.label if vp else "") or label or regeling or _bwb(iri) or iri
    if eigen == regeling:  # een verwijzing naar de regeling zelf: geen "Invorderingswet 1990, Invorderingswet 1990"
        regeling = ""
    return Vindplaats(iri=iri, label=eigen, regeling=regeling)


def _telling(rijen: list[dict], predicaat: str, aantal: int | None, afgekapt: bool) -> Telling:
    """De eerste voorbeelden uit de rijen, het aantal uit de telquery. Faalde die, dan het aantal rijen, en `volledig: false`
    als de rijen op hun grens stonden: dan is het "minstens", nooit een stil te laag getal."""
    gezien: dict[str, str] = {}
    for r in rijen:
        if r.get("p") == predicaat and r.get("o") and r.get("isIri") == "true":
            gezien.setdefault(r["o"], r.get("naam") or "")
    items = sorted(gezien.items(), key=lambda kv: _natuurlijk(kv[1] or kv[0]))
    return Telling(aantal=aantal if aantal is not None else len(items), volledig=aantal is not None or not afgekapt,
                   items=[Vindplaats(iri=i, label=n or _bwb(i) or i) for i, n in items[:MAX_VOORBEELDEN]])


def _eerste(rijen: list[dict], predicaat: str) -> str:
    return next((r.get("o", "") for r in rijen if r.get("p") == predicaat and r.get("o")), "")


def detail_uit(iri: str, uit: list[dict], reg: list[dict], verw: list[dict], plaats: dict,
               titels: dict[str, str], citeertitels: dict[str, str], aantallen: dict[str, int] | None = None) -> BepalingDetail:
    """Het detail uit de rijen van de graaf. `plaats` is één uitkomst van `graaf.plaatsen`; `titels` de opschriften van de
    delen daarin; `citeertitels` per BWB-id; `aantallen` de uitkomst van de telquery (leeg als die faalde)."""
    aantallen = aantallen or {}
    eigen_bwb = _bwb(iri)
    pad = [p for p in (plaats or {}).get("pad") or [] if p.get("iri") != iri]
    structuur = [Structuurdeel(soort=(p.get("type") or "").lower(), nummer=p.get("nummer") or "", titel=titels.get(p["iri"], ""),
                               iri=p["iri"]) for p in pad if p.get("iri")]

    uitgaand: dict[tuple[str, str, str], Verwijzing] = {}
    inkomend: dict[str, str] = {}
    for r in verw:
        van, naar = r.get("van", ""), r.get("naar", "")
        if not van or not naar:
            continue
        if r.get("richting") == "uit":
            sleutel = (van, naar, r.get("anker", ""))
            if sleutel not in uitgaand:
                doel = bron_vindplaats(naar)
                label = r.get("naarLabel") or (r.get("anker", "") if not (doel and doel.label) else "")
                uitgaand[sleutel] = Verwijzing(van=_vindplaats(van, r.get("vanLabel", ""), citeertitels),
                                               naar=_vindplaats(naar, label, citeertitels), anker=r.get("anker", ""),
                                               in_graaf=r.get("naarInGraaf") != "false")
        elif r.get("richting") == "in" and not van.startswith(iri + ":") and van != iri:
            inkomend.setdefault(van, r.get("vanLabel", ""))  # een verwijzing binnen de bepaling zelf telt niet als "verwezen door"

    def volgorde_uit(v: Verwijzing) -> tuple:
        return (_natuurlijk(v.van.label), _bwb(v.naar.iri) != eigen_bwb, _natuurlijk(v.naar.label))

    def volgorde_in(kv: tuple[str, str]) -> tuple:
        return (_bwb(kv[0]) != eigen_bwb, citeertitels.get(_bwb(kv[0]), ""), _natuurlijk(kv[1] or kv[0]))

    rijen_uit = sum(1 for r in verw if r.get("richting") == "uit")
    rijen_in = sum(1 for r in verw if r.get("richting") == "in")
    uit_lijst = sorted(uitgaand.values(), key=volgorde_uit)
    aantal_uit = aantallen.get("uit", len(uit_lijst))
    triples_afgekapt = len(uit) >= MAX_TRIPLES
    in_lijst = sorted(inkomend.items(), key=volgorde_in)
    regeling_iri = f"urn:bwb:{eigen_bwb}" if eigen_bwb else ""
    return BepalingDetail(
        bron_iri=iri,
        vindplaats=_vindplaats(iri, _eerste(uit, BWB + "vindplaats"), citeertitels),
        plaats=structuur,
        status=_eerste(uit, BWB + "status"),
        inwerking=_eerste(uit, BWB + "inwerking") or None,
        terugwerkend_tot=_eerste(uit, BWB + "terugwerkendTot") or None,
        gewijzigd_bij=_eerste(uit, BWB + "bron"),
        geldig_vanaf=_eerste(reg if iri != regeling_iri else uit, BWB + "geldigVanaf") or None,
        geldig_tot=_eerste(reg if iri != regeling_iri else uit, BWB + "geldigTot") or None,
        toestand_url=_eerste(reg if iri != regeling_iri else uit, BWB + "toestandUrl"),
        verwijst_naar=uit_lijst[:MAX_UITGAAND],
        verwijst_naar_aantal=aantal_uit,
        verwijst_naar_volledig=aantal_uit <= MAX_UITGAAND and ("uit" in aantallen or rijen_uit < MAX_VERWIJZINGSRIJEN),
        verwezen_door=Telling(aantal=aantallen.get("in", len(in_lijst)), volledig="in" in aantallen or rijen_in < MAX_VERWIJZINGSRIJEN,
                              items=[_vindplaats(i, label, citeertitels) for i, label in in_lijst[:MAX_VOORBEELDEN]]),
        grondslag_voor=_telling(uit, BWB + "grondslagVoor", aantallen.get("grondslagVoor"), triples_afgekapt),
        bevoegdheid_voor=_telling(uit, BWB + "bevoegdheidVoor", aantallen.get("bevoegdheidVoor"), triples_afgekapt),
        genoemd_in=_telling(uit, BWB + "verwijzingDoor", aantallen.get("verwijzingDoor"), triples_afgekapt),
        definieert=sorted({r["o"] for r in uit if r.get("p") == BWB + "definieertBegrip" and r.get("o")}, key=str.casefold),
    )


async def bepaling_detail(iri: str) -> BepalingDetail:
    """Het detail van `iri` uit de graaf. `ValueError` bij een IRI die geen bronknoop kan zijn: hij gaat een query in."""
    if not _IRI.fullmatch(iri or ""):
        raise ValueError("Ongeldige bron-IRI.")
    eigen_bwb = _bwb(iri)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            uit = await sparql_select(client, _uitgaand(iri))
            regeling = f"urn:bwb:{eigen_bwb}"
            reg = await sparql_select(client, _regeling_geldigheid(regeling)) if eigen_bwb and regeling != iri else []
            verw = [*await sparql_select(client, _verwijzingen(iri, "uit")), *await sparql_select(client, _verwijzingen(iri, "in"))]
            try:
                aantallen = aantallen_uit(await sparql_select(client, _tellingen(iri)))
            except (httpx.HTTPError, ConnectionError) as exc:  # vangnet: dan de rijen, met "minstens" waar ze op hun grens staan
                log.warning("bepaling_detail: telling mislukt", extra={"bron_iri": iri, "fout": type(exc).__name__})
                aantallen = {}
            plaats = (await graaf_mod.plaatsen([iri]))[0] if eigen_bwb else {}
            pad_iris = [p["iri"] for p in plaats.get("pad") or [] if p.get("iri")]
            titels = {r["d"]: r["titel"] for r in await sparql_select(client, _titels(pad_iris)) if r.get("titel")} if pad_iris else {}
            bwbs = sorted({b for b in [eigen_bwb, *(_bwb(r.get("van", "")) for r in verw), *(_bwb(r.get("naar", "")) for r in verw)] if b})
            citeertitels = {_bwb(r["r"]): r["titel"] for r in await sparql_select(client, _citeertitels(bwbs)) if r.get("titel")} if bwbs else {}
    except (httpx.HTTPError, ConnectionError) as exc:
        log.warning("bepaling_detail: graaf niet bereikbaar", extra={"bron_iri": iri, "fout": type(exc).__name__})
        vp = bron_vindplaats(iri)
        return BepalingDetail(bron_iri=iri, beschikbaar=False, vindplaats=Vindplaats(iri=iri, label=(vp.label if vp else "") or iri))
    return detail_uit(iri, uit, reg, verw, plaats, titels, citeertitels, aantallen)
