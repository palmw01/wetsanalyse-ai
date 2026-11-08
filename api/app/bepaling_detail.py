"""Het detail van één bepaling voor het paneel naast het gesprek: wat de graaf er verder over weet (ADR-008, *Detail bij een antwoord*).

Een antwoord van Lex draagt `doelen`; het paneel haalt per doel hier de feiten op. Zonder model en zonder de trace van de beurt:
elke waarde is een triple uit de graaf, en wat de graaf niet heeft blijft leeg. De vorm staat in `bepaling_graaf_contract`, dat
het werkgebiedrapport deelt.

`detail_uit` is puur (te testen zonder graaf); `bepaling_detail` haalt de rijen op. Een haperende graaf geeft
`beschikbaar: false`, nooit een leeg detail dat leest als "hier is niets bekend".

**Eén graaflezing met het rapport.** De opbouw (titels), de uitgaande verwijzingen en de tellingen komen uit
`bepaling_graaf.lees`, dezelfde lezer als het werkgebiedrapport (ADR-009 is eigenaar). Hier staat alleen wat het rapport niet
wil: de voorbeelden van wie ernaar verwijst, en grondslag, bevoegdheid en "genoemd in" per regeling (`knoopinfo`).
"""
from __future__ import annotations

import logging
import re

import httpx
from bronmodel.antwoord import Vindplaats
from bronmodel.vindplaats import vindplaats as bron_vindplaats

from . import graaf as graaf_mod
from . import bepaling_graaf
from .bepaling_graaf import _IN
from .bepaling_graaf_contract import MAX_UITGAAND, MAX_VOORBEELDEN, BepalingDetail, Structuurdeel, Telling, Verwijzing
from .graaf_client import sparql_select
from .knoopinfo import BWB, MAX_TRIPLES, _regeling_geldigheid, _uitgaand
from .samenhang import _IRI, _PREFIXES

log = logging.getLogger(__name__)

_BWB_ID = re.compile(r"urn:bwb:(BWB[RV]\d+)")
#: Een bovengrens op de inkomende verwijzingen: een artikel met veel leden wordt door de Leidraad vaak honderden keren genoemd.
MAX_VERWIJZINGSRIJEN = 1000
#: Een bovengrens op de leden en onderdelen onder een bepaling, waarvan `lees` de uitgaande verwijzingen leest.
MAX_ONDERDELEN = 500


def _inkomend(iri: str) -> str:
    """Wie naar de bepaling of haar leden en onderdelen verwijst, met zijn vindplaats zoals de graaf hem noemt. Begrensd: het
    aantal komt uit de telquery, de rijen dragen alleen de voorbeelden. Een verwijzing binnen de bepaling zelf telt niet."""
    return _PREFIXES + f"""SELECT ?van ?vanLabel WHERE {{ {_IN.format(iri=iri)}
  OPTIONAL {{ ?van bwb:vindplaats ?vanLabel }}
}} LIMIT {MAX_VERWIJZINGSRIJEN}"""


def _onderdelen(iri: str) -> str:
    """De leden en onderdelen onder de bepaling: verwijzingen hangen aan het lid, niet aan het artikel (graph-qa CLAUDE.md)."""
    return _PREFIXES + f"""SELECT DISTINCT ?x WHERE {{ <{iri}> (bwb:heeftLid|bwb:heeftOnderdeel)+ ?x }} LIMIT {MAX_ONDERDELEN}"""


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


def detail_uit(iri: str, uit: list[dict], reg: list[dict], inkomend_rijen: list[dict], plaats: dict, graaf: dict,
               citeertitels: dict[str, str]) -> BepalingDetail:
    """Het detail uit de rijen van de graaf. `plaats` is één uitkomst van `graaf.plaatsen`; `graaf` de uitkomst van
    `bepaling_graaf.lees` (structuur, uitgaande verwijzingen, `tellingen` per bronnode); `citeertitels` per BWB-id."""
    graaf = graaf or {}
    aantallen = (graaf.get("tellingen") or {}).get(iri) or {}
    titels = {k: v.get("titel", "") for k, v in (graaf.get("structuur") or {}).items()}
    eigen_bwb = _bwb(iri)
    pad = [p for p in (plaats or {}).get("pad") or [] if p.get("iri") != iri]
    structuur = [Structuurdeel(soort=(p.get("type") or "").lower(), nummer=p.get("nummer") or "", titel=titels.get(p["iri"], ""),
                               iri=p["iri"]) for p in pad if p.get("iri")]

    uitgaand: dict[tuple[str, str, str], Verwijzing] = {}
    for r in graaf.get("verwijzingen") or []:
        van, naar, anker = r.get("van", ""), r.get("naar", ""), r.get("anker", "")
        if not van or not naar or (van, naar, anker) in uitgaand:
            continue
        doel = bron_vindplaats(naar)
        # De importer zet bij een regeling die niet in de graaf staat het BWB-id als `doelLabel`: dat is geen naam. Dan wint
        # de citeertitel of het anker ("Algemene termijnenwet"), en pas daarna het BWB-id (`_vindplaats`).
        label = "" if r.get("label") == _bwb(naar) else r.get("label") or ""
        label = label or (anker if not (doel and doel.label) else "")
        regelingen = citeertitels | ({_bwb(naar): r["regeling"]} if r.get("regeling") and _bwb(naar) else {})
        uitgaand[(van, naar, anker)] = Verwijzing(van=_vindplaats(van, r.get("van_label", ""), citeertitels),
                                                  naar=_vindplaats(naar, label, regelingen), anker=anker,
                                                  in_graaf=bool(r.get("in_graaf")))
    inkomend: dict[str, str] = {}
    for r in inkomend_rijen:
        van = r.get("van", "")
        if van and van != iri and not van.startswith(iri + ":"):  # een verwijzing binnen de bepaling zelf telt niet
            inkomend.setdefault(van, r.get("vanLabel", ""))

    def volgorde_uit(v: Verwijzing) -> tuple:
        return (_natuurlijk(v.van.label), _bwb(v.naar.iri) != eigen_bwb, _natuurlijk(v.naar.label))

    def volgorde_in(kv: tuple[str, str]) -> tuple:
        return (_bwb(kv[0]) != eigen_bwb, citeertitels.get(_bwb(kv[0]), ""), _natuurlijk(kv[1] or kv[0]))

    rijen_in = len(inkomend_rijen)
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
        verwijst_naar_volledig=aantal_uit <= MAX_UITGAAND and bool(graaf.get("verwijzingen_volledig", True))
        and ("uit" in aantallen or bool(graaf.get("volledig", True))),
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
            inkomend = await sparql_select(client, _inkomend(iri))
            onder = [r["x"] for r in await sparql_select(client, _onderdelen(iri)) if r.get("x")]
            plaats = (await graaf_mod.plaatsen([iri]))[0] if eigen_bwb else {}
            pad_iris = [p["iri"] for p in plaats.get("pad") or [] if p.get("iri")]
            # De bepaling zelf mét de telquery; haar leden en onderdelen alleen voor hun uitgaande verwijzingen, zonder een
            # telquery per lid. `lees` vangt een haperende graaf zelf af (`volledig: false`): dan de rijen, met "minstens".
            graaf = await bepaling_graaf.lees([eigen_bwb], pad_iris, [iri], met_inkomend=True)
            if onder:
                leden = await bepaling_graaf.lees([], [], onder)
                graaf["verwijzingen"] = [*graaf["verwijzingen"], *leden["verwijzingen"]]
                for sleutel in ("volledig", "verwijzingen_volledig"):
                    graaf[sleutel] = graaf[sleutel] and leden[sleutel]
            if iri not in graaf.get("tellingen", {}):
                log.warning("bepaling_detail: telling mislukt", extra={"bron_iri": iri})
            bwbs = sorted({b for b in [eigen_bwb, *(_bwb(r.get("van", "")) for r in inkomend),
                                       *(_bwb(r.get("van", "")) for r in graaf["verwijzingen"])] if b})
            citeertitels = {_bwb(r["r"]): r["titel"] for r in await sparql_select(client, _citeertitels(bwbs)) if r.get("titel")} if bwbs else {}
    except (httpx.HTTPError, ConnectionError) as exc:
        log.warning("bepaling_detail: graaf niet bereikbaar", extra={"bron_iri": iri, "fout": type(exc).__name__})
        vp = bron_vindplaats(iri)
        return BepalingDetail(bron_iri=iri, beschikbaar=False, vindplaats=Vindplaats(iri=iri, label=(vp.label if vp else "") or iri))
    return detail_uit(iri, uit, reg, inkomend, plaats, graaf, citeertitels)
