"""Afleidingsregels: opslag, dragers met bewijsstand, de poort, de hiërarchie en parameterwaarden (ADR-018, R1).

Het patroon is dat van de begrippen (`begrip_store`), met dezelfde bouwstenen in plaats van een tweede set:

- **Eén schrijfpad** (`_gewijzigd_in`): eerst het rij-slot op het werkgebied, dan op de regel. `verwachte_revisie` → 412,
  daarna revisie +1, een volledige kopie in `regel_revisies` en een regel in `werkgebied_audit` (acties `regel-*`).
- **Een geaccordeerde regel die verandert, is weer een concept.** Alleen accorderen zet de status hoger.
- **De grondslag is verplicht** (ADR-018 §2): een drager met rol `grondslag` op een Afleidingsregel, een
  Rechtsbetrekking of een Tijdsaanduiding, of op een passage die het uitvoerbegrip aanduidt. Zonder: 422.
- **Een drager draagt zijn bewijsstand** (`begrip_store.bewijzen`); de actualiteit komt bij het lezen uit Postgres
  (`begrip_store.actualiteit`), zoals bij een begripskoppeling.
- **De regeltekst rekent de server** (`regeltekst.py`); de client typt hem niet.
- **De poort** (`poort`) staat bij elke GET: beoordeelde begrippen, een beoordeelde actuele grondslag en een beoordeeld
  voorbeeld per geval (besluit gebruiker 19 nov 2026). Wat open blijft maar niet blokkeert, staat in `signalen`.
- **De hiërarchie wordt afgeleid**, niet opgeslagen: een regel volgt op een andere als zijn invoer de uitvoer daarvan is.
- **De volledigheidstoets** (ADR-018 besluit 7.6): elke regel draagt `gaten`, met de code, plek en melding uit de skill
  (`regelgaten.json`, gegenereerd in `jas_regelgaten`). Het skelet rekent `regelskelet.gaten`; hier de gaten van het
  regelobject (`regel_gaten`, uit gegevens die `_gatgegevens` in één keer leest), en in de keten die van de regels samen.
  Een gat is een signaal, geen poort.
"""
from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, insert, select, update

from . import begrip_store, db
from .begrip_store import Resolver
from .regel_contracts import (
    DragerInvoer, DragersToevoegen, DragerWijziging, ParameterWaardeInvoer, RegelAanmaak, RegelWijziging,
)
from .jas_regelgaten import gat
from .regeltekst import genoemde_begrippen, regeltekst
from .werkgebied_store import _audit as werkgebied_audit, toets_revisie, werkgebied_rij

#: De klassen die zelf een grondslag zijn (ADR-018 §2). Een andere klasse mag alleen als de passage het uitvoerbegrip
#: aanduidt: dan is het de formulering van het afgeleide begrip.
GRONDSLAG_KLASSEN = ("Afleidingsregel", "Rechtsbetrekking", "Tijdsaanduiding")
GEACCORDEERD = ("geaccordeerd", "geaccordeerd_als_beleidsregel")


def _meervoud(n: int, een: str, meer: str) -> str:
    return een if n == 1 else meer.format(n=n)


def _iso(t) -> str | None:
    return db.aware(t).isoformat() if t else None


# --- lezen -------------------------------------------------------------------------------------------

def _drager(row) -> dict:
    return {"id": row.id, "element_id": row.element_id, "rol": row.rol, "geval": row.geval, "bewijs": row.bewijs,
            "beoordeling": row.beoordeling, "beoordeeld_door": row.beoordeeld_door,
            "beoordeeld_op": _iso(row.beoordeeld_op), "toegevoegd_door": row.toegevoegd_door,
            "toegevoegd": _iso(row.toegevoegd), "bevestigingen": []}


async def _dragers_van(conn, werkgebied_id: str, regel_ids: list[str]) -> dict[str, list[dict]]:
    if not regel_ids:
        return {}
    d = db.regel_dragers
    rows = (await conn.execute(select(d).where(d.c.werkgebied_id == werkgebied_id, d.c.regel_id.in_(regel_ids),
                                               d.c.verwijderd.is_(None)).order_by(d.c.toegevoegd, d.c.id))).all()
    huidig = await begrip_store._huidige_elementen(conn, {r.element_id for r in rows})
    uit: dict[str, list[dict]] = {}
    for r in rows:
        uit.setdefault(r.regel_id, []).append(begrip_store.actualiteit(_drager(r), huidig.get(r.element_id)))
    return uit


async def _begrippen(conn, werkgebied_id: str, ids: set[str]) -> dict[str, dict]:
    """Naam en status van de begrippen die regels noemen, zoals dit werkgebied ze ziet (ook gebruikte generieke)."""
    if not ids:
        return {}
    b = db.begrippen
    rows = (await conn.execute(select(b.c.id, b.c.status, b.c.inhoud).where(
        b.c.id.in_(sorted(ids)), begrip_store.in_werkgebied(werkgebied_id)))).all()
    return {r.id: {"id": r.id, "naam": (r.inhoud or {}).get("naam", ""), "status": r.status,
                   "definitie": (r.inhoud or {}).get("definitie", "")} for r in rows}


#: De soorten open punt die een keuze vragen vóór de regel geaccordeerd wordt (ADR-018 besluit 2 en 7.13): een
#: interpretatiekeuze en ontbrekend uitvoeringsbeleid. Een onderzoekspunt of een gat in de annotatie is een signaal.
KEUZE_SOORTEN = ("interpretatiekeuze", "ontbrekend_uitvoeringsbeleid")


def poort(inhoud: dict, dragers: list[dict], begrippen: dict[str, dict], open_punten: list[dict] | None = None) -> dict:
    """Mag deze regel geaccordeerd worden (besluit gebruiker 19 nov 2026, ADR-018 besluit 2), en wat er nog openstaat.
    `open_punten`: de punten die aan de regel of een van zijn gevallen hangen (lessenbundel 4, R3)."""
    redenen: list[str] = []
    ontbreekt = [i for i in genoemde_begrippen(inhoud) if i not in begrippen]
    if ontbreekt:
        redenen.append(_meervoud(len(ontbreekt), "1 genoemd begrip bestaat niet (meer) in dit werkgebied.",
                                 "{n} genoemde begrippen bestaan niet (meer) in dit werkgebied."))
    niet_geacc = [begrippen[i]["naam"] or i for i in genoemde_begrippen(inhoud)
                  if i in begrippen and begrippen[i]["status"] != "geaccordeerd"]
    if niet_geacc:
        redenen.append("Nog niet geaccordeerd: " + ", ".join(niet_geacc) + ".")
    grondslag = [d for d in dragers if d["rol"] == "grondslag" and d["beoordeling"] != "afgewezen"]
    if not grondslag:
        redenen.append("Er is geen grondslag meer: geen dragende formulering die niet is afgewezen.")
    elif not any(d["beoordeling"] == "akkoord" and d["actualiteit"] == "actueel" for d in grondslag):
        redenen.append("De grondslag is nog niet beoordeeld, of de passage is gewijzigd, verworpen of verdwenen.")
    keuzes = [p for p in open_punten or [] if p["status"] == "open" and p["soort"] in KEUZE_SOORTEN]
    if keuzes:
        redenen.append(_meervoud(len(keuzes), "1 keuze is nog niet genomen: ", "{n} keuzes zijn nog niet genomen: ")
                       + "; ".join(p["vraag"].rstrip(".?") for p in keuzes) + ".")
    beoordeeld = {(v.get("geval") or "") for v in inhoud.get("voorbeelden", []) if v.get("oordeel", "open") != "open"}
    if len(inhoud["gevallen"]) == 1:
        if not beoordeeld:
            redenen.append("Er is nog geen beoordeeld voorbeeld.")
    else:
        zonder = [g["label"] for g in inhoud["gevallen"] if g["label"] not in beoordeeld]
        if zonder:
            redenen.append("Nog geen beoordeeld voorbeeld bij geval " + ", ".join(zonder) + ".")
    return {"mag": not redenen, "redenen": redenen}


def signalen(inhoud: dict, dragers: list[dict], open_punten: list[dict] | None = None) -> list[str]:
    """Wat aandacht vraagt zonder accorderen te blokkeren (het skelet is een signaal, besluit 2)."""
    uit: list[str] = []
    rest = [p for p in open_punten or [] if p["status"] == "open" and p["soort"] not in KEUZE_SOORTEN]
    if rest:
        uit.append(_meervoud(len(rest), "1 onderzoekspunt of gat in de annotatie staat nog open.",
                             "{n} onderzoekspunten of gaten in de annotatie staan nog open."))
    open_ = sum(d["beoordeling"] == "open" and d["rol"] != "grondslag" for d in dragers)
    if open_:
        uit.append(_meervoud(open_, "1 andere dragende formulering is nog niet beoordeeld.",
                             "{n} andere dragende formuleringen zijn nog niet beoordeeld."))
    weg = sum(d["actualiteit"] != "actueel" and d["beoordeling"] != "afgewezen" for d in dragers)
    if weg:
        uit.append(_meervoud(weg, "1 dragende passage is gewijzigd, verworpen of verdwenen.",
                             "{n} dragende passages zijn gewijzigd, verworpen of verdwenen."))
    onjuist = sum(v.get("oordeel") in ("onjuist",) for v in inhoud.get("voorbeelden", []))
    if onjuist:
        uit.append(_meervoud(onjuist, "1 voorbeeld geeft een onjuiste uitkomst.",
                             "{n} voorbeelden geven een onjuiste uitkomst."))
    return uit


#: Een waarde in een definitie: een getal, een bedrag of een percentage (M04 H2 *Parameter*: de waarde is een eigen begrip).
_WAARDE = re.compile(r"\d|€|%|\bprocent\b", re.IGNORECASE)
#: Het regelbegrip heet "bepalen <uitvoer>" (M01 h.3 stap 3b; skill, *Eén regel per uitvoer*).
_BEPALEN = re.compile(r"^\s*(?:het\s+)?bepalen\b", re.IGNORECASE)
#: De rollen waarmee een begrip op een formulering rust (niet `afgeleid` en niet `context`).
_OP_FORMULERING = ("duiding", "definitie")


def regel_gaten(inhoud: dict, dragers: list[dict], begrippen: dict[str, dict], g: dict) -> list[dict]:
    """De gaten van het regelobject (plek `regel` in de skill). `g` komt uit `_gatgegevens`: welke elementen een begrip
    dragen, met welke rol de begrippen rusten, de parameterwaarden, de contextbronnen, de operatoren in de grondslag en
    de uitvoeren van de andere regels. Alleen lezen; geen oordeel over de inhoud."""
    uit: list[dict] = []
    actief = [d for d in dragers if d["beoordeling"] != "afgewezen"]
    if any(d["rol"] == "uitvoer" and d["element_id"] not in g["met_begrip"] for d in actief):
        uit.append(gat("uitvoer_zonder_begrip"))
    naam = begrippen.get(inhoud["regelbegrip_id"], {}).get("naam", "")
    if naam and not _BEPALEN.match(naam):
        uit.append(gat("regelbegrip_zonder_bepalen"))
    for i in inhoud.get("invoer", []):
        b = begrippen.get(i["begrip_id"], {})
        if i.get("rol") == "parameter":
            if not any(w.get("geldig_vanaf") for w in g["waarden"].get(i["begrip_id"], [])):
                uit.append(gat("parameter_zonder_tijdvak", naam=b.get("naam") or i["begrip_id"]))
            if _WAARDE.search(b.get("definitie") or ""):
                uit.append(gat("parameterwaarde_in_definitie", naam=b.get("naam") or i["begrip_id"]))
        elif (i["begrip_id"] not in g["uitvoeren"]
              and not g["rollen"].get(i["begrip_id"], set()) & set(_OP_FORMULERING)):
            uit.append(gat("impliciete_invoer", naam=b.get("naam") or i["begrip_id"]))
    context = sorted({c for d in actief for c in g["context"]
                      if (d.get("bewijs") or {}).get("eigenaar_iri", "").startswith(c)})
    if context:
        uit.append(gat("rust_op_contextbron", bron=", ".join(g["labels"].get(c, c) for c in context)))
    grondslag = {d["element_id"] for d in actief if d["rol"] == "grondslag"}
    for op in g["operatoren"]:
        if op["binnen"] & grondslag and op["id"] not in g["met_begrip"]:
            uit.append(gat("operator_zonder_begrip", tekst=op["tekst"]))
    return uit


def _binnen(ankers: list[dict], om: list[dict]) -> bool:
    return any(a.get("bron_iri") == o.get("bron_iri") and o.get("start", 0) <= a.get("start", -1)
               and a.get("eind", 0) <= o.get("eind", -1) for a in ankers for o in om)


async def _gatgegevens(conn, werkgebied_id: str, rows, dragers: dict[str, list[dict]]) -> dict:
    """Alles wat `regel_gaten` leest, in een paar queries voor alle regels samen."""
    alle_dragers = [d for ds in dragers.values() for d in ds]
    # De operatoren in de laag van een grondslag, binnen haar span (alleen de lagen die geraakt zijn: geïndexeerd).
    grond = [d for d in alle_dragers if d["rol"] == "grondslag"]
    lagen = {(d.get("bewijs") or {}).get("laag_id") for d in grond} - {None, ""}
    operatoren = []
    if lagen:
        e = db.annotatie_v2_elementen
        for r in (await conn.execute(select(e.c.id, e.c.inhoud).where(e.c.laag_id.in_(sorted(lagen))))).all():
            el = r.inhoud or {}
            if el.get("klasse") != "Operator" or el.get("lifecycle") in ("rejected", "vervangen"):
                continue
            binnen = {d["element_id"] for d in grond if _binnen(el.get("ankers") or [], (d.get("bewijs") or {}).get("ankers") or [])}
            if binnen:
                operatoren.append({"id": r.id, "tekst": el.get("tekst", ""), "binnen": binnen})
    elementen = {d["element_id"] for d in alle_dragers} | {o["id"] for o in operatoren}
    invoer = {i["begrip_id"] for r in rows for i in r.inhoud.get("invoer", [])}
    k = db.begrip_koppelingen
    koppel = (await conn.execute(select(k.c.element_id, k.c.begrip_id, k.c.rol).where(
        k.c.werkgebied_id == werkgebied_id, k.c.verwijderd.is_(None),
        (k.c.element_id.in_(sorted(elementen)) | k.c.begrip_id.in_(sorted(invoer)))))).all() if elementen or invoer else []
    rollen: dict[str, set[str]] = {}
    for x in koppel:
        rollen.setdefault(x.begrip_id, set()).add(x.rol)
    w = db.parameter_waarden
    waarden: dict[str, list[dict]] = {}
    for x in (await conn.execute(select(w.c.parameter_begrip_id, w.c.geldig_vanaf).where(
            w.c.werkgebied_id == werkgebied_id, w.c.verwijderd.is_(None)))).all():
        waarden.setdefault(x.parameter_begrip_id, []).append({"geldig_vanaf": x.geldig_vanaf})
    s = db.werkgebied_bronselecties
    ctx = (await conn.execute(select(s.c.bron_iri, s.c.label).where(
        s.c.werkgebied_id == werkgebied_id, s.c.rol == "context"))).all()
    r = db.regels
    uitvoeren = {x.inhoud["uitvoer_begrip_id"] for x in (await conn.execute(select(r.c.inhoud, r.c.status).where(
        r.c.werkgebied_id == werkgebied_id))).all() if x.status not in ("vervangen", "afgewezen")}
    return {"met_begrip": {x.element_id for x in koppel}, "rollen": rollen, "waarden": waarden,
            "context": [c.bron_iri for c in ctx], "labels": {c.bron_iri: c.label or c.bron_iri for c in ctx},
            "operatoren": operatoren, "uitvoeren": uitvoeren}


def _regel(row, dragers: list[dict], begrippen: dict[str, dict], open_punten: list[dict] | None = None,
           gaten: list[dict] | None = None) -> dict:
    namen = {i: b["naam"] for i, b in begrippen.items()}
    inhoud = row.inhoud
    return {"id": row.id, "werkgebied_id": row.werkgebied_id, "status": row.status, "revisie": row.revisie,
            "herkomst": row.herkomst, "opvolger_van": row.opvolger_van, "inhoud": inhoud,
            "naam": namen.get(inhoud["regelbegrip_id"], ""), "uitvoer": namen.get(inhoud["uitvoer_begrip_id"], ""),
            "regeltekst": regeltekst(inhoud, namen),
            "begrippen": {i: begrippen[i] for i in genoemde_begrippen(inhoud) if i in begrippen},
            "dragers": dragers, "accorderen": poort(inhoud, dragers, begrippen, open_punten),
            "signalen": signalen(inhoud, dragers, open_punten), "gaten": gaten or [],
            "open_punten": {"open": sum(p["status"] == "open" for p in open_punten or []), "totaal": len(open_punten or [])},
            "aangemaakt_door": row.aangemaakt_door, "aangemaakt": _iso(row.aangemaakt), "gewijzigd": _iso(row.gewijzigd),
            "geaccordeerd_door": row.geaccordeerd_door, "geaccordeerd_op": _iso(row.geaccordeerd_op),
            "geaccordeerd_revisie": row.geaccordeerd_revisie}


async def _open_punten_van(conn, werkgebied_id: str, regel_ids: list[str]) -> dict[str, list[dict]]:
    """Per regel de open punten die eraan of aan een van zijn gevallen hangen (het object van lessenbundel 4), licht:
    soort, status en vraag. Alleen lezen; het object en zijn besluitroute zijn van `open_punt_store`."""
    if not regel_ids:
        return {}
    t = db.open_punten
    rows = (await conn.execute(select(t.c.id, t.c.status, t.c.inhoud).where(t.c.werkgebied_id == werkgebied_id)
                               .order_by(t.c.aangemaakt, t.c.id))).all()
    uit: dict[str, list[dict]] = {}
    for x in rows:
        regels = {a["id"] for a in x.inhoud.get("hangt_aan", []) if a.get("soort") in ("regel", "geval")}
        for rid in regels & set(regel_ids):
            uit.setdefault(rid, []).append({"id": x.id, "status": x.status, "soort": x.inhoud["soort"],
                                            "vraag": x.inhoud.get("vraag", "")})
    return uit


async def _lees(conn, werkgebied_id: str, rows) -> list[dict]:
    dragers = await _dragers_van(conn, werkgebied_id, [r.id for r in rows])
    ids = {i for r in rows for i in genoemde_begrippen(r.inhoud)}
    begrippen = await _begrippen(conn, werkgebied_id, ids)
    punten = await _open_punten_van(conn, werkgebied_id, [r.id for r in rows])
    g = await _gatgegevens(conn, werkgebied_id, rows, dragers)
    return [_regel(r, dragers.get(r.id, []), begrippen, punten.get(r.id, []),
                   regel_gaten(r.inhoud, dragers.get(r.id, []), begrippen, g)) for r in rows]


def _niet_gevonden() -> HTTPException:
    return HTTPException(404, {"fout": "niet_gevonden", "melding": "Deze afleidingsregel bestaat niet (meer)."})


async def haal(werkgebied_id: str, regel_id: str) -> dict:
    r = db.regels
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        row = (await conn.execute(select(r).where(r.c.id == regel_id, r.c.werkgebied_id == werkgebied_id))).first()
        if row is None:
            raise _niet_gevonden()
        return (await _lees(conn, werkgebied_id, [row]))[0]


async def lijst(werkgebied_id: str) -> list[dict]:
    r = db.regels
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        rows = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id)
                                   .order_by(r.c.aangemaakt, r.c.id))).all()
        return await _lees(conn, werkgebied_id, rows)


STATUS_VOLGORDE = {"concept": 0, "geaccordeerd": 1, "geaccordeerd_als_beleidsregel": 1, "afgewezen": 2, "vervangen": 3}


async def overzicht(q: str = "", status: list[str] | None = None, werkgebied_id: str | None = None,
                    door: str | None = None) -> dict:
    """De regels van alle werkgebieden als lichte rij, voor het overzicht in de zijbalk (zoals `GET /v1/begrippen`).
    Zoeken op de naam, de uitvoer en de regeltekst; `door` beperkt tot regels waarvan deze gebruiker een revisie maakte
    (*Door mij bewerkt*). De tellers per status gelden voor dezelfde filters zonder het statusfilter."""
    from .begrippen_overzicht import normaal
    r, w, b, rev = db.regels, db.werkgebieden, db.begrippen, db.regel_revisies
    sel = select(r, w.c.naam.label("wg_naam")).join_from(r, w, r.c.werkgebied_id == w.c.id)
    if werkgebied_id:
        sel = sel.where(r.c.werkgebied_id == werkgebied_id)
    if door:
        sel = sel.where(r.c.id.in_(select(rev.c.regel_id).where(rev.c.actor == door)))
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(sel.order_by(r.c.gewijzigd.desc(), r.c.id))).all()
        ids = {i for x in rows for i in genoemde_begrippen(x.inhoud)}
        namen = {x.id: (x.inhoud or {}).get("naam", "") for x in (await conn.execute(
            select(b.c.id, b.c.inhoud).where(b.c.id.in_(sorted(ids))))).all()} if ids else {}
    rijen = []
    for x in rows:
        tekst = regeltekst(x.inhoud, namen)["tekst"]
        rijen.append({"id": x.id, "werkgebied_id": x.werkgebied_id, "werkgebied_naam": x.wg_naam or "",
                      "naam": namen.get(x.inhoud["regelbegrip_id"], ""), "uitvoer": namen.get(x.inhoud["uitvoer_begrip_id"], ""),
                      "status": x.status, "revisie": x.revisie, "soort": x.inhoud["soort"],
                      "brontype": x.inhoud.get("brontype", "wet"), "gevallen": len(x.inhoud["gevallen"]),
                      "regeltekst": tekst, "herkomst": x.herkomst, "gewijzigd": _iso(x.gewijzigd)})
    vraag = normaal(q)
    gevonden = [x for x in rijen if not vraag or all(
        woord in normaal(" ".join([x["naam"], x["uitvoer"], x["regeltekst"]])) for woord in vraag.split())]
    per_status: dict[str, int] = {}
    for x in gevonden:
        per_status[x["status"]] = per_status.get(x["status"], 0) + 1
    if status:
        gevonden = [x for x in gevonden if x["status"] in status]
    gevonden.sort(key=lambda x: (STATUS_VOLGORDE.get(x["status"], 9), normaal(x["naam"]), x["id"]))
    return {"resultaten": gevonden, "totaal": len(gevonden), "per_status": per_status}


def keten(regels: list[dict]) -> dict:
    """De afleidingshiërarchie (ADR-018 §3, D2), afgeleid. Pijlen van de regel die een begrip afleidt naar de regel die
    het gebruikt; de volgorde van onder naar boven; basisgegevens (invoer zonder regel) en signalen."""
    actief = [x for x in regels if x["status"] not in ("vervangen", "afgewezen")]
    door: dict[str, list[str]] = {}
    for x in actief:
        door.setdefault(x["inhoud"]["uitvoer_begrip_id"], []).append(x["id"])
    pijlen, basis, sig = [], {}, []
    for x in actief:
        for i in x["inhoud"].get("invoer", []):
            bronnen = door.get(i["begrip_id"], [])
            for van in bronnen:
                pijlen.append({"van": van, "naar": x["id"], "begrip_id": i["begrip_id"]})
            if not bronnen and i.get("rol", "invoer") == "invoer":
                basis.setdefault(i["begrip_id"], x["begrippen"].get(i["begrip_id"], {}).get("naam", ""))
    for uitvoer, ids in door.items():
        if len(ids) > 1:
            g = gat("zelfde_uitvoer")
            sig.append({"soort": "zelfde_uitvoer", "code": g["code"], "regel_ids": ids, "begrip_id": uitvoer,
                        "melding": g["tekst"]})
    # L-3a-1: één regelbegrip voor regels met verschillende uitvoeren. Het omgekeerde (twee regelbegrippen voor één
    # uitvoer) is `zelfde_uitvoer` hierboven: dan zijn het twee regels.
    per_begrip: dict[str, set[str]] = {}
    for x in actief:
        per_begrip.setdefault(x["inhoud"]["regelbegrip_id"], set()).add(x["inhoud"]["uitvoer_begrip_id"])
    for begrip, uitvoeren in per_begrip.items():
        if len(uitvoeren) > 1:
            g = gat("regelbegrip_meer_uitvoeren")
            sig.append({"soort": "regelbegrip_meer_uitvoeren", "code": g["code"], "begrip_id": begrip,
                        "regel_ids": [x["id"] for x in actief if x["inhoud"]["regelbegrip_id"] == begrip],
                        "melding": g["tekst"]})
    # Van onder naar boven: een regel komt na alles waar hij op volgt (Kahn); wat overblijft zit in een kring.
    na = {x["id"]: {p["van"] for p in pijlen if p["naar"] == x["id"] and p["van"] != x["id"]} for x in actief}
    volgorde: list[str] = []
    rest = dict(na)
    while rest:
        klaar = sorted((i for i, v in rest.items() if not (v - set(volgorde))),
                       key=lambda i: next(n for n, x in enumerate(actief) if x["id"] == i))
        if not klaar:
            sig.append({"soort": "kring", "regel_ids": sorted(rest),
                        "melding": "Deze regels leiden elkaars invoer af: een kring."})
            volgorde += sorted(rest)
            break
        volgorde += klaar
        for i in klaar:
            rest.pop(i)
    return {"regels": [{"id": x["id"], "naam": x["naam"], "uitvoer": x["uitvoer"], "status": x["status"],
                        "soort": x["inhoud"]["soort"], "gevallen": len(x["inhoud"]["gevallen"]),
                        "brontype": x["inhoud"].get("brontype", "wet")} for x in actief],
            "volgorde": volgorde, "pijlen": pijlen,
            "basisgegevens": [{"begrip_id": k, "naam": v} for k, v in basis.items()], "signalen": sig}


async def hierarchie(werkgebied_id: str) -> dict:
    return keten(await lijst(werkgebied_id))


async def revisies(werkgebied_id: str, regel_id: str, limit: int = 100) -> list[dict]:
    await haal(werkgebied_id, regel_id)
    t = db.regel_revisies
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(t).where(t.c.regel_id == regel_id).order_by(t.c.revisie.desc())
                                   .limit(limit))).all()
    return [{"revisie": r.revisie, "actie": r.actie, "detail": r.detail, "status": r.status, "inhoud": r.inhoud,
             "actor": r.actor, "tijdstip": _iso(r.tijdstip)} for r in rows]


# --- toetsen -----------------------------------------------------------------------------------------

async def _toets_begrippen(conn, werkgebied_id: str, inhoud: dict) -> None:
    ids = set(genoemde_begrippen(inhoud))
    gevonden = await _begrippen(conn, werkgebied_id, ids)
    onbekend = sorted(ids - set(gevonden))
    if onbekend:
        raise HTTPException(422, {"fout": "begrip_onbekend", "begrip_ids": onbekend,
                                  "melding": "Niet elk genoemd begrip bestaat in dit werkgebied."})
    vervangen = [gevonden[i]["naam"] for i in sorted(ids) if gevonden[i]["status"] == "vervangen"]
    if vervangen:
        raise HTTPException(409, {"fout": "vervangen", "melding": "Een regel noemt geen vervangen begrip: "
                                  + ", ".join(vervangen) + ". Gebruik de opvolger."})


async def _toets_grondslag(conn, werkgebied_id: str, inhoud: dict, dragers: list[DragerInvoer],
                           bewijs: dict[str, dict], al: list[dict] | None = None) -> None:
    """Minstens één grondslag (nieuw of al aanwezig), en elke nieuwe grondslag is er een (ADR-018 §2)."""
    nieuw = [d for d in dragers if d.rol.value == "grondslag"]
    bestaand = [d for d in (al or []) if d["rol"] == "grondslag" and d["beoordeling"] != "afgewezen"]
    if not nieuw and not bestaand:
        raise HTTPException(422, {"fout": "geen_grondslag", "melding": "Een regel rust op een formulering in de tekst: "
                                  "geef minstens één drager met de rol grondslag."})
    k = db.begrip_koppelingen
    duidend = set((await conn.execute(select(k.c.element_id).where(
        k.c.werkgebied_id == werkgebied_id, k.c.begrip_id == inhoud["uitvoer_begrip_id"], k.c.rol == "duiding",
        k.c.verwijderd.is_(None), k.c.beoordeling != "afgewezen"))).scalars().all())
    fout = [d.element_id for d in nieuw
            if bewijs[d.element_id].get("klasse") not in GRONDSLAG_KLASSEN and d.element_id not in duidend]
    if fout:
        raise HTTPException(422, {"fout": "geen_grondslag", "element_ids": fout,
                                  "melding": "Een grondslag is een Afleidingsregel, een Rechtsbetrekking of een "
                                             "Tijdsaanduiding, of een passage die het afgeleide begrip aanduidt."})


def _toets_gevallen(inhoud: dict, dragers: list[DragerInvoer]) -> None:
    labels = {g["label"] for g in inhoud["gevallen"]}
    fout = sorted({d.geval for d in dragers if d.geval and d.geval not in labels}
                  | {v["geval"] for v in inhoud.get("voorbeelden", []) if v.get("geval") and v["geval"] not in labels})
    if fout:
        raise HTTPException(422, {"fout": "geval_onbekend", "gevallen": fout,
                                  "melding": "Een drager of voorbeeld noemt een geval dat de regel niet heeft."})


# --- schrijven ---------------------------------------------------------------------------------------

async def _revisieregel(conn, regel_id, revisie, actie, detail, status, inhoud, actor, tijdstip):
    await conn.execute(insert(db.regel_revisies).values(
        regel_id=regel_id, revisie=revisie, actie=actie, detail=detail, status=status, inhoud=inhoud, actor=actor,
        tijdstip=tijdstip))


async def _voeg_dragers_toe(conn, werkgebied_id: str, regel_id: str, dragers: list[DragerInvoer],
                            bewijs: dict[str, dict], actor: str) -> list[str]:
    """Voegt de dragers toe die er nog niet zijn (element, rol, geval); geeft hun element-id's."""
    d = db.regel_dragers
    al = {(r.element_id, r.rol, r.geval) for r in (await conn.execute(select(d).where(
        d.c.regel_id == regel_id, d.c.verwijderd.is_(None)))).all()}
    nieuw, nu = [], db.utcnow()
    for x in dragers:
        sleutel = (x.element_id, x.rol.value, x.geval)
        if sleutel in al:
            continue
        al.add(sleutel)
        await conn.execute(insert(d).values(
            id=str(uuid.uuid4()), regel_id=regel_id, werkgebied_id=werkgebied_id, element_id=x.element_id,
            rol=x.rol.value, geval=x.geval, bewijs=bewijs[x.element_id], beoordeling="open", toegevoegd_door=actor,
            toegevoegd=nu))
        nieuw.append(x.element_id)
    return nieuw


async def maak(werkgebied: dict, invoer: RegelAanmaak, actor: str, resolve: Resolver) -> dict:
    inhoud = invoer.inhoud.model_dump(mode="json")
    _toets_gevallen(inhoud, invoer.dragers)
    bewijs = await begrip_store.bewijzen(werkgebied, [d.element_id for d in invoer.dragers], resolve)
    wid, rid, nu = werkgebied["id"], str(uuid.uuid4()), db.utcnow()
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, wid, slot=True)
        await _toets_begrippen(conn, wid, inhoud)
        await _toets_grondslag(conn, wid, inhoud, invoer.dragers, bewijs)
        await conn.execute(insert(db.regels).values(
            id=rid, werkgebied_id=wid, status="concept", revisie=1, inhoud=inhoud, herkomst=invoer.herkomst,
            aangemaakt_door=actor, aangemaakt=nu, gewijzigd=nu))
        nieuw = await _voeg_dragers_toe(conn, wid, rid, invoer.dragers, bewijs, actor)
        detail = {"regelbegrip_id": inhoud["regelbegrip_id"], "uitvoer_begrip_id": inhoud["uitvoer_begrip_id"],
                  "element_ids": nieuw, "herkomst": invoer.herkomst}
        await _revisieregel(conn, rid, 1, "regel-aangemaakt", detail, "concept", inhoud, actor, nu)
        await werkgebied_audit(conn, wid, actor, "regel-aangemaakt", {**detail, "regel_id": rid, "regel_revisie": 1})
    return await haal(wid, rid)


@asynccontextmanager
async def _gewijzigd_in(conn, werkgebied_id: str, regel_id: str, verwacht: int, actor: str, actie: str, detail: dict):
    """Werkgebiedslot, regelslot, revisietoets; daarna revisie +1, revisiekopie en audit. De aanroeper muteert via
    `stand` (`inhoud`, `status`, `waarden`, `geen_wijziging`); `detail` wordt pas ná het blok gelezen."""
    r = db.regels
    await werkgebied_rij(conn, werkgebied_id, slot=True)
    row = (await conn.execute(select(r).where(r.c.id == regel_id, r.c.werkgebied_id == werkgebied_id)
                              .with_for_update())).first()
    if row is None:
        raise _niet_gevonden()
    if row.status == "vervangen":
        raise HTTPException(409, {"fout": "vervangen", "melding": "Deze regel is vervangen en alleen nog te lezen."})
    toets_revisie(row.revisie, verwacht, "deze regel")
    stand = {"inhoud": row.inhoud, "status": None, "waarden": {}, "geen_wijziging": False}
    yield row, stand
    if stand["geen_wijziging"]:
        return
    status = stand["status"] or ("concept" if row.status in GEACCORDEERD else row.status)
    nieuw, nu = row.revisie + 1, db.utcnow()
    await conn.execute(update(r).where(r.c.id == regel_id).values(
        revisie=nieuw, gewijzigd=nu, status=status, inhoud=stand["inhoud"], **stand["waarden"]))
    await _revisieregel(conn, regel_id, nieuw, actie, detail, status, stand["inhoud"], actor, nu)
    await werkgebied_audit(conn, werkgebied_id, actor, actie, {**detail, "regel_id": regel_id, "regel_revisie": nieuw})


async def _huidige_dragers(conn, werkgebied_id: str, regel_id: str) -> list[dict]:
    return (await _dragers_van(conn, werkgebied_id, [regel_id])).get(regel_id, [])


async def wijzig(werkgebied_id: str, regel_id: str, w: RegelWijziging, actor: str) -> dict:
    nieuw = w.inhoud.model_dump(mode="json")
    detail: dict = {}
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, regel_id, w.verwachte_revisie, actor, "regel-gewijzigd",
                                 detail) as (row, stand):
            if nieuw == row.inhoud:
                stand["geen_wijziging"] = True
            else:
                await _toets_begrippen(conn, werkgebied_id, nieuw)
                dragers = await _huidige_dragers(conn, werkgebied_id, regel_id)
                labels = {g["label"] for g in nieuw["gevallen"]}
                if any(d["geval"] and d["geval"] not in labels for d in dragers):
                    raise HTTPException(422, {"fout": "geval_onbekend", "melding": "Een drager hoort bij een geval dat "
                                              "niet meer bestaat. Haal die drager eerst weg."})
                _toets_gevallen(nieuw, [])
                detail["velden"] = sorted(k for k in nieuw if nieuw.get(k) != row.inhoud.get(k))
                stand["inhoud"] = nieuw
    return await haal(werkgebied_id, regel_id)


async def voeg_dragers_toe(werkgebied: dict, regel_id: str, w: DragersToevoegen, actor: str, resolve: Resolver) -> dict:
    bewijs = await begrip_store.bewijzen(werkgebied, [d.element_id for d in w.dragers], resolve)
    wid = werkgebied["id"]
    detail: dict = {}
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, wid, regel_id, w.verwachte_revisie, actor, "drager-toegevoegd",
                                 detail) as (row, stand):
            _toets_gevallen(row.inhoud, w.dragers)
            if any(d.rol.value == "grondslag" for d in w.dragers):
                await _toets_grondslag(conn, wid, row.inhoud, [d for d in w.dragers if d.rol.value == "grondslag"],
                                       bewijs, await _huidige_dragers(conn, wid, regel_id))
            nieuw = await _voeg_dragers_toe(conn, wid, regel_id, w.dragers, bewijs, actor)
            if not nieuw:
                stand["geen_wijziging"] = True
            detail["element_ids"] = nieuw
    return await haal(wid, regel_id)


async def wijzig_drager(werkgebied_id: str, regel_id: str, drager_id: str, w: DragerWijziging, actor: str) -> dict:
    d = db.regel_dragers
    detail: dict = {"drager_id": drager_id, "beoordeling": w.beoordeling.value}
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, regel_id, w.verwachte_revisie, actor, "drager-beoordeeld",
                                 detail) as (_, stand):
            rij = (await conn.execute(select(d).where(d.c.id == drager_id, d.c.regel_id == regel_id,
                                                      d.c.verwijderd.is_(None)))).first()
            if rij is None:
                raise HTTPException(404, {"fout": "niet_gevonden", "melding": "Deze drager bestaat niet (meer)."})
            if rij.beoordeling == w.beoordeling.value:
                stand["geen_wijziging"] = True
            else:
                await conn.execute(update(d).where(d.c.id == drager_id).values(
                    beoordeling=w.beoordeling.value, beoordeeld_door=actor, beoordeeld_op=db.utcnow()))
    return await haal(werkgebied_id, regel_id)


async def verwijder_drager(werkgebied_id: str, regel_id: str, drager_id: str, verwacht: int, actor: str) -> dict:
    d = db.regel_dragers
    detail: dict = {"drager_id": drager_id}
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, regel_id, verwacht, actor, "drager-verwijderd", detail) as (_, __):
            rij = (await conn.execute(select(d).where(d.c.id == drager_id, d.c.regel_id == regel_id,
                                                      d.c.verwijderd.is_(None)))).first()
            if rij is None:
                raise HTTPException(404, {"fout": "niet_gevonden", "melding": "Deze drager bestaat niet (meer)."})
            rest = [x for x in await _huidige_dragers(conn, werkgebied_id, regel_id)
                    if x["id"] != drager_id and x["rol"] == "grondslag" and x["beoordeling"] != "afgewezen"]
            if rij.rol == "grondslag" and not rest:
                raise HTTPException(409, {"fout": "laatste_grondslag", "melding": "Dit is de laatste grondslag van de "
                                          "regel. Voeg eerst een andere toe."})
            await conn.execute(update(d).where(d.c.id == drager_id).values(verwijderd=db.utcnow()))
            detail["element_id"] = rij.element_id
    return await haal(werkgebied_id, regel_id)


async def accordeer(werkgebied_id: str, regel_id: str, verwacht: int, reden: str, actor: str) -> dict:
    reden = reden.strip()
    detail = {"reden": reden}
    p: dict = {}
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, regel_id, verwacht, actor, "regel-geaccordeerd",
                                 detail) as (row, stand):
            dragers = await _huidige_dragers(conn, werkgebied_id, regel_id)
            punten = (await _open_punten_van(conn, werkgebied_id, [regel_id])).get(regel_id, [])
            p = poort(row.inhoud, dragers, await _begrippen(conn, werkgebied_id, set(genoemde_begrippen(row.inhoud))),
                      punten)
            if not reden:
                p = {"mag": False, "redenen": [*p["redenen"], "De reden van het accorderen ontbreekt."]}
            if not p["mag"]:
                stand["geen_wijziging"] = True
            else:
                beleid = row.inhoud.get("brontype") == "beleid"
                stand["status"] = "geaccordeerd_als_beleidsregel" if beleid else "geaccordeerd"
                stand["waarden"] = {"geaccordeerd_door": actor, "geaccordeerd_op": db.utcnow(),
                                    "geaccordeerd_revisie": row.revisie + 1}
    if not p["mag"]:
        raise HTTPException(409, {"fout": "poort", "redenen": p["redenen"],
                                  "melding": "Nog niet te accorderen: " + " ".join(p["redenen"])})
    return await haal(werkgebied_id, regel_id)


async def heropen(werkgebied_id: str, regel_id: str, verwacht: int, actor: str) -> dict:
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, regel_id, verwacht, actor, "regel-heropend", {}) as (row, stand):
            if row.status not in GEACCORDEERD:
                raise HTTPException(409, {"fout": "niet_geaccordeerd", "melding": "De regel is niet geaccordeerd."})
            stand["status"] = "concept"
    return await haal(werkgebied_id, regel_id)


async def wijs_af(werkgebied_id: str, regel_id: str, verwacht: int, reden: str, actor: str) -> dict:
    """Een regel afwijzen bewaart hem met de reden (ADR-018 §8); hij doet niet meer mee in de keten."""
    if not reden.strip():
        raise HTTPException(422, {"fout": "reden", "melding": "Geef de reden van het afwijzen."})
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, regel_id, verwacht, actor, "regel-afgewezen",
                                 {"reden": reden.strip()}) as (row, stand):
            if row.status == "afgewezen":
                stand["geen_wijziging"] = True
            stand["status"] = "afgewezen"
    return await haal(werkgebied_id, regel_id)


async def verwijder(werkgebied_id: str, regel_id: str, verwacht: int, actor: str) -> dict:
    """Echt wissen, zoals een begrip: de regel, zijn revisies en dragers. De audit blijft."""
    r = db.regels
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(r).where(r.c.id == regel_id, r.c.werkgebied_id == werkgebied_id)
                                  .with_for_update())).first()
        if row is None:
            raise _niet_gevonden()
        toets_revisie(row.revisie, verwacht, "deze regel")
        await conn.execute(delete(db.regel_dragers).where(db.regel_dragers.c.regel_id == regel_id))
        await conn.execute(delete(db.regel_revisies).where(db.regel_revisies.c.regel_id == regel_id))
        await conn.execute(delete(r).where(r.c.id == regel_id))
        await werkgebied_audit(conn, werkgebied_id, actor, "regel-verwijderd",
                               {"regel_id": regel_id, "regelbegrip_id": row.inhoud.get("regelbegrip_id", "")})
    return {"verwijderd": regel_id}


# --- parameterwaarden --------------------------------------------------------------------------------

def _waarde(row) -> dict:
    return {"id": row.id, "parameter_begrip_id": row.parameter_begrip_id, "waarde_begrip_id": row.waarde_begrip_id or "",
            "waarde": row.waarde, "eenheid": row.eenheid, "geldig_vanaf": row.geldig_vanaf or "",
            "geldig_tot": row.geldig_tot or "", "element_id": row.element_id or "", "getoetst": row.getoetst,
            "door": row.door, "op": _iso(row.op)}


async def parameterwaarden(werkgebied_id: str) -> list[dict]:
    t = db.parameter_waarden
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        rows = (await conn.execute(select(t).where(t.c.werkgebied_id == werkgebied_id, t.c.verwijderd.is_(None))
                                   .order_by(t.c.parameter_begrip_id, t.c.geldig_vanaf, t.c.id))).all()
    return [_waarde(r) for r in rows]


async def voeg_parameterwaarde_toe(werkgebied_id: str, w: ParameterWaardeInvoer, actor: str) -> dict:
    """De waarde van een parameter in een tijdvak. Het parameterbegrip (en een waardebegrip) bestaan in het werkgebied."""
    if w.geldig_vanaf and w.geldig_tot and w.geldig_tot < w.geldig_vanaf:
        raise HTTPException(422, {"fout": "tijdvak", "melding": "Het tijdvak eindigt vóór het begint."})
    t, wid, nu = db.parameter_waarden, str(uuid.uuid4()), db.utcnow()
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        ids = {w.parameter_begrip_id} | ({w.waarde_begrip_id} if w.waarde_begrip_id else set())
        onbekend = sorted(ids - set(await _begrippen(conn, werkgebied_id, ids)))
        if onbekend:
            raise HTTPException(422, {"fout": "begrip_onbekend", "begrip_ids": onbekend,
                                      "melding": "Niet elk genoemd begrip bestaat in dit werkgebied."})
        await conn.execute(insert(t).values(
            id=wid, werkgebied_id=werkgebied_id, parameter_begrip_id=w.parameter_begrip_id,
            waarde_begrip_id=w.waarde_begrip_id or None, waarde=w.waarde, eenheid=w.eenheid,
            geldig_vanaf=w.geldig_vanaf or None, geldig_tot=w.geldig_tot or None, element_id=w.element_id or None,
            getoetst=w.getoetst, door=actor, op=nu))
        await werkgebied_audit(conn, werkgebied_id, actor, "parameterwaarde-toegevoegd",
                               {"parameterwaarde_id": wid, "parameter_begrip_id": w.parameter_begrip_id})
        row = (await conn.execute(select(t).where(t.c.id == wid))).first()
    return _waarde(row)


async def verwijder_parameterwaarde(werkgebied_id: str, waarde_id: str, actor: str) -> dict:
    t = db.parameter_waarden
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(t).where(t.c.id == waarde_id, t.c.werkgebied_id == werkgebied_id,
                                                  t.c.verwijderd.is_(None)))).first()
        if row is None:
            raise HTTPException(404, {"fout": "niet_gevonden", "melding": "Deze parameterwaarde bestaat niet (meer)."})
        await conn.execute(update(t).where(t.c.id == waarde_id).values(verwijderd=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, "parameterwaarde-verwijderd",
                               {"parameterwaarde_id": waarde_id, "parameter_begrip_id": row.parameter_begrip_id})
    return {"verwijderd": waarde_id}
