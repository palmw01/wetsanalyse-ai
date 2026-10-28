"""De onderzoeksstand van de begrippenketen (spoor M): de context naast het manifest.

Het manifest bevat alleen bronnodes waarop een geannoteerde formulering staat. Een begrip lees je
echter in zijn context (Wetsanalyse, stap 3a): de andere leden van het artikel, een begripsbepaling
elders in de regeling, een bepaling waarnaar verwezen wordt, een contextselectie zonder annotaties.
Deze module verzamelt die context **deterministisch**, in een vaste prioriteit en binnen een vast
budget, en legt vast wat er níét onderzocht is (`ontbrekend`, met een reden).

De vorm volgt `tools/graph-qa/agent/begrippen_pipeline/model.py` (`Contextbron`, `Onderzoek`); het
id rekent hier op dezelfde manier (`onderzoek_id`), en `test_begrippen_onderzoek_drift` aan de kant
van graph-qa bewaakt dat.

Prioriteit (binnen elke stap op documentvolgorde):

1. **zelfde artikel**: de leden en onderdelen van het artikel van elk anker;
2. **definities in de geselecteerde regelingen**: een begripsbepaling of kwalificatie ("verstaan
   onder", "geldt als", "wordt aangemerkt als") die een formuleringstekst bevat;
3. **verwijzingen**, één stap uitgaand vanaf de ankers; een doel buiten de graaf is `niet_in_graaf`;
4. **contextselecties** zonder annotaties.

Daarnaast **vergelijkingsbegrippen**: de begrippen van dit werkgebied en, met een exact gelijke naam
of alternatieve term, die van andere werkgebieden. Nooit een bron, nooit bewijs.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Awaitable, Callable

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from . import annotatie_v2_store as store, db
from .begrip_manifest import _vindplaats, bouw_met_bronbomen
from .werkgebied_inventaris import bwb_van, nodes_met_titel

logger = logging.getLogger(__name__)

Resolver = Callable[[dict], Awaitable[dict]]
Verwijzingen = Callable[[list[str]], Awaitable["list[tuple[str, str]] | None"]]

VERSIE = "2"

MAX_ZELFDE_ARTIKEL = 12
"""Leden en onderdelen van hetzelfde artikel: een artikel met meer leden is zeldzaam, en wat erbuiten
valt staat als `budget` in `ontbrekend`."""
MAX_DEFINITIES = 6
"""Begripsbepalingen en kwalificaties met een formuleringstekst erin."""
MAX_VERWIJZINGEN = 6
"""Bronnodes waarnaar de ankers verwijzen (één stap)."""
MAX_CONTEXTSELECTIE = 6
"""Nodes uit contextselecties zonder annotaties."""
MAX_BRONNEN = 24
"""Alle contextbronnen samen; daarboven groeit de prompt zonder dat het oordeel beter wordt."""
MAX_TEKENS = 40_000
"""Alle contexttekst samen."""
MAX_VERGELIJKING_ELDERS = 5
"""Begrippen uit andere werkgebieden met dezelfde naam."""

_PER_REDEN = {"zelfde_artikel": MAX_ZELFDE_ARTIKEL, "definitie_in_regeling": MAX_DEFINITIES,
              "verwijzing": MAX_VERWIJZINGEN, "contextselectie": MAX_CONTEXTSELECTIE}

# Een begripsbepaling of kwalificatie in de bepaling zelf, of een aanhef die de definities eronder
# inleidt ("In deze wet wordt verstaan onder:").
_DEFINITIE = re.compile(r"\bverstaan\s+onder\b|\bverstaat\b[^.]{0,60}\bonder\b|\bgeldt\s+als\b|\bgelden\s+als\b"
                        r"|\b(?:wordt|worden)\s+(?:mede\s+)?aangemerkt\s+als\b", re.IGNORECASE)
_AANHEF = re.compile(r"\b(?:verstaat|wordt|worden)\s+(?:(?:mede|niet)\s+)?(?:verstaan\s+)?onder\s*:?\s*$",
                     re.IGNORECASE)
_ARTIKEL = {"Artikel", "Divisie"}


def _norm(t: str) -> str:
    return " ".join((t or "").lower().split())


def _hash(*delen: str) -> str:
    return hashlib.sha256("\x1f".join(delen).encode()).hexdigest()


def onderzoek_id(manifest_id: str, bronnen: list[dict], begrippen: list[dict], ontbrekend: list[dict] = (),
                 versie: str = VERSIE) -> str:
    """Zelfde rekenwijze als `Onderzoek.id` in de keten: inhoud, geen moment. Wat niet onderzocht is
    telt mee, want het komt in de prompt en de toetsen (`CONTEXT_NIET_ONDERZOCHT`)."""
    delen = [manifest_id, versie]
    delen += sorted(f"{b['bron_iri']}@{b['bron_hash']}" for b in bronnen)
    delen += sorted(f"{x['id']}|{x.get('status', '')}|{_hash(x['naam'], x.get('definitie', ''))[:12]}"
                    for x in begrippen)
    delen += sorted({f"{o['wat']}|{o['reden']}" for o in ontbrekend})
    return "O" + _hash(*delen)[:16]


def _bevat(tekst: str, term: str) -> bool:
    return bool(term) and re.search(rf"(?<!\w){re.escape(term)}(?!\w)", _norm(tekst)) is not None


async def _graaf_verwijzingen(iris: list[str]) -> list[tuple[str, str]] | None:
    """Uitgaande verwijzingen vanaf deze nodes, één stap; None als de graaf niet antwoordt."""
    from .graaf_projectie_v2 import _select
    from .samenhang import _uitgaand
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            rijen = await _select(client, _uitgaand(iris))
    except (httpx.HTTPError, ConnectionError, ValueError) as exc:
        logger.warning("verwijzingen voor het begripsonderzoek niet beschikbaar", extra={"fout": type(exc).__name__})
        return None
    return sorted({(r["van"], r["naar"]) for r in rijen if r.get("van") and r.get("naar")})


def _keten(nodes: dict[str, dict], iri: str) -> list[str]:
    uit: list[str] = []
    while iri in nodes and iri not in uit:
        uit.append(iri)
        iri = nodes[iri].get("parent_iri") or ""
    return uit


def _onder(nodes: dict[str, dict], wortel: str) -> list[str]:
    """De nodes onder `wortel` (inclusief), op documentvolgorde."""
    return sorted((i for i in nodes if wortel in _keten(nodes, i)),
                  key=lambda i: (nodes[i].get("volgorde", 1 << 30), i))


def _scopes(werkgebied: dict, per_bwb: dict[str, dict]) -> dict[str, str]:
    """Per bronnode de rol van de selectie die hem dekt (analyseren wint van context)."""
    rol: dict[str, str] = {}
    for sel in werkgebied.get("bronnen") or []:
        snap = per_bwb.get(bwb_van(sel))
        if snap is None or sel["bron_iri"] not in store.nodes_van(snap):
            continue
        scope = store.bereik_van(snap, sel["bron_iri"]) if sel.get("bereik") == "onderliggend" else {sel["bron_iri"]}
        for iri in scope:
            if rol.get(iri) != "analyseren":
                rol[iri] = sel["rol"]
    return rol


async def vergelijkingsbegrippen(werkgebied_id: str, namen: set[str]) -> list[dict]:
    """De begrippen van dit werkgebied, en die van andere werkgebieden met een gelijke naam of
    alternatieve term (hoogstens `MAX_VERGELIJKING_ELDERS`)."""
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(b.c.id, b.c.werkgebied_id, b.c.status, b.c.inhoud)
                                   .where(b.c.verwijderd.is_(None)).order_by(b.c.id))).all()
    eigen, elders = [], []
    for r in rows:
        inhoud = r.inhoud or {}
        termen = {_norm(inhoud.get("naam", ""))} | {_norm(t) for t in inhoud.get("alternatieve_termen") or []}
        rij = {"id": r.id, "naam": inhoud.get("naam", ""), "definitie": inhoud.get("definitie", ""),
               "status": r.status, "werkgebied_id": r.werkgebied_id, "eigen": r.werkgebied_id == werkgebied_id}
        if rij["eigen"]:
            eigen.append(rij)
        elif termen & namen:
            elders.append(rij)
    return eigen + elders[:MAX_VERGELIJKING_ELDERS]


async def bouw(werkgebied: dict, manifest: dict, manifest_id: str, per_bwb: dict[str, dict], resolve: Resolver,
               verwijzingen: Verwijzingen | None = None, begrippen: list[dict] | None = None) -> dict:
    """`{onderzoek: {manifest_id, bronnen, begrippen, ontbrekend, versie}, onderzoek_id}`.

    `per_bwb` zijn de bronbomen die het manifest al ophaalde. Een regeling die alleen via een
    verwijzing in beeld komt, haalt `resolve` erbij; lukt dat niet, dan is het doel `niet_in_graaf`.
    `begrippen` is er voor tests; anders komen ze uit Postgres.
    """
    verwijzingen = verwijzingen or _graaf_verwijzingen
    nodes: dict[str, dict] = {}
    for snap in per_bwb.values():
        nodes.update(nodes_met_titel(snap))
    rollen = _scopes(werkgebied, per_bwb)
    in_manifest = {b["bron_iri"] for b in manifest["bronnen"]}
    ankers = sorted(in_manifest, key=lambda i: (nodes.get(i, {}).get("volgorde", 1 << 30), i))
    per_anker: dict[str, list[str]] = {}
    for f in manifest["formuleringen"]:
        per_anker.setdefault(f["bron_iri"], []).append(f["element_id"])
    termen = {f["element_id"]: _norm(f["tekst"]) for f in manifest["formuleringen"]}

    kandidaten: list[tuple[str, str, list[str]]] = []   # (reden, iri, voor), in prioriteitsvolgorde
    ontbrekend: list[dict] = []

    # 1. Zelfde artikel.
    for anker in ankers:
        artikel = next((i for i in _keten(nodes, anker) if nodes[i].get("type") in _ARTIKEL), "")
        for iri in _onder(nodes, artikel) if artikel else []:
            kandidaten.append(("zelfde_artikel", iri, per_anker.get(anker, [])))

    # 2. Definities en kwalificaties in de geladen regelingen die een formuleringstekst dragen.
    for iri in sorted(nodes, key=lambda i: (bwb_van({"bwb_id": nodes[i].get("bwb_id", ""), "bron_iri": i}),
                                             nodes[i].get("volgorde", 1 << 30), i)):
        n = nodes[iri]
        tekst = n.get("tekst") or ""
        aanhef = (nodes.get(n.get("parent_iri") or "", {}).get("tekst") or "")
        if not tekst or not (_DEFINITIE.search(tekst) or _AANHEF.search(aanhef)):
            continue
        voor = sorted(e for e, t in termen.items() if _bevat(tekst, t))
        if voor:
            kandidaten.append(("definitie_in_regeling", iri, voor))

    # 3. Verwijzingen, één stap vanaf de ankers.
    rijen = await verwijzingen(ankers) if ankers else []
    if rijen is None:
        ontbrekend.append({"wat": "verwijzingen vanaf de passages", "reden": "onbereikbaar"})
        rijen = []
    for van, naar in rijen:
        if naar not in nodes and naar.startswith("urn:bwb:BWB"):
            try:
                nodes.update(nodes_met_titel(await resolve({"bron_iri": naar})))
            except (HTTPException, ConnectionError, ValueError, httpx.HTTPError):
                pass
        if naar not in nodes:
            ontbrekend.append({"wat": naar, "reden": "niet_in_graaf"})
            continue
        for iri in _onder(nodes, naar):
            kandidaten.append(("verwijzing", iri, per_anker.get(van, [van])))

    # 4. Contextselecties.
    for sel in werkgebied.get("bronnen") or []:
        if sel.get("rol") != "context" or sel["bron_iri"] not in nodes:
            continue
        wortel = sel["bron_iri"]
        for iri in _onder(nodes, wortel) if sel.get("bereik") == "onderliggend" else [wortel]:
            kandidaten.append(("contextselectie", iri, [sel["bron_iri"]]))

    # Toelaten in prioriteitsvolgorde: elke node één keer (de eerste reden wint, `voor` groeit mee),
    # alleen met eigen tekst, nooit een manifestbron, binnen het budget per reden en in totaal.
    gekozen: dict[str, dict] = {}
    per_reden: dict[str, int] = {}
    tekens = 0
    for reden, iri, voor in kandidaten:
        n = nodes.get(iri) or {}
        if iri in in_manifest or not (n.get("tekst") or "").strip():
            continue
        if iri in gekozen:
            gekozen[iri]["voor"] = sorted(set(gekozen[iri]["voor"]) | set(voor))
            continue
        if any(o["wat"] == iri for o in ontbrekend):
            continue
        if (per_reden.get(reden, 0) >= _PER_REDEN[reden] or len(gekozen) >= MAX_BRONNEN
                or tekens + len(n["tekst"]) > MAX_TEKENS):
            ontbrekend.append({"wat": iri, "reden": "budget"})
            continue
        per_reden[reden] = per_reden.get(reden, 0) + 1
        tekens += len(n["tekst"])
        ouder = nodes.get(n.get("parent_iri") or "", {})
        gekozen[iri] = {"bron_iri": iri, "tekst": n["tekst"], "bron_hash": n["bron_hash"],
                        "label": _vindplaats(nodes, iri), "aanhef": ouder.get("tekst") or "",
                        "regeling": n.get("bwb_id") or iri.split(":")[2],
                        "rol": rollen.get(iri, "onderzoek"), "reden": reden, "voor": sorted(set(voor))}

    if begrippen is None:
        namen = set(termen.values())
        begrippen = await vergelijkingsbegrippen(werkgebied["id"], namen)
    bronnen = list(gekozen.values())
    onderzoek = {"manifest_id": manifest_id, "bronnen": bronnen, "begrippen": begrippen,
                 "ontbrekend": ontbrekend, "versie": VERSIE}
    return {"onderzoek": onderzoek, "onderzoek_id": onderzoek_id(manifest_id, bronnen, begrippen, ontbrekend)}


async def manifest_en_onderzoek(werkgebied: dict, resolve: Resolver) -> dict:
    """Manifest en onderzoeksstand samen, met één keer de bronbomen: `{manifest, manifest_id,
    overgeslagen, volledig, onderzoek, onderzoek_id}`."""
    m, per_bwb = await bouw_met_bronbomen(werkgebied, resolve)
    return {**m, **await bouw(werkgebied, m["manifest"], m["manifest_id"], per_bwb, resolve)}
