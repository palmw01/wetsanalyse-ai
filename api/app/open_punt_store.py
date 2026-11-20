"""Open punten: opslag, de keuze van de jurist, revisies en audit (L-X-1, ADR-018 §6).

Het patroon is dat van een afleidingsregel (`regel_store`), met dezelfde bouwstenen:

- **Eén schrijfpad** (`_gewijzigd_in`): het rij-slot op het werkgebied, dan op het punt. `verwachte_revisie` → 412,
  daarna revisie +1, een volledige kopie in `open_punt_revisies` en een regel in `werkgebied_audit` (acties
  `open-punt-*`).
- **Waar het aan hangt, bestaat.** Bij schrijven toetst de store elke aanhaking: een regel en een deelvraag van dit
  werkgebied, een begrip, een markering. Een onbekende is een 422. Bij lezen draagt elke aanhaking `bestaat`: een
  markering of regel kan later verdwijnen, en het punt blijft dan staan met de verwijzing (zoals een regeldrager).
- **De keuze is van de jurist** (`besluit`). De route staat niet in `agent_toegang.TOEGESTAAN`, dus het agent-token
  kan hem niet aanroepen, en de actor is het userid uit de sessie. Lex stelt lezingen voor, nooit de keuze.
- **De status volgt uit de keuze en de toetsen**: `open` zonder keuze, `gekozen` met een keuze, `getoetst` als ook
  alles wat te toetsen was, getoetst is. De client zet hem nooit zelf.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, insert, select, update

from . import db
from .open_punt_contracts import Besluit, Omhangen, OpenPuntAanmaak, OpenPuntWijziging, Soort, SOORT_NAMEN
from .werkgebied_store import _audit as werkgebied_audit, toets_revisie, werkgebied_rij

#: Zoveel open punten gaan mee in het werkgebied (de context van Lex); de rest staat in de lijst.
MAX_SAMENVATTING = 40


def _iso(t) -> str | None:
    return db.aware(t).isoformat() if t else None


def status_van(inhoud: dict, keuze: dict | None) -> str:
    if not keuze:
        return "open"
    if keuze.get("uitkomst") == "gesignaleerd":
        return "gesignaleerd"
    toetsen = inhoud.get("te_toetsen") or []
    return "getoetst" if toetsen and all(t.get("getoetst") for t in toetsen) else "gekozen"


# --- aanhakingen ---------------------------------------------------------------------------------------

async def _bestaande(conn, werkgebied_id: str, aanhakingen: list[dict]) -> set[tuple[str, str]]:
    """Welke (soort, id) er nu zijn. Een geval hoort bij een regel van dit werkgebied."""
    per: dict[str, set[str]] = {}
    for a in aanhakingen:
        per.setdefault("regel" if a["soort"] == "geval" else a["soort"], set()).add(a["id"])
    uit: set[tuple[str, str]] = set()

    async def ids(tabel, *voorwaarden) -> set[str]:
        return set((await conn.execute(select(tabel.c.id).where(*voorwaarden))).scalars().all())
    if per.get("regel"):
        r = db.regels
        uit |= {("regel", i) for i in await ids(r, r.c.werkgebied_id == werkgebied_id, r.c.id.in_(per["regel"]))}
    if per.get("deelvraag"):
        d = db.werkgebied_deelvragen
        uit |= {("deelvraag", i) for i in await ids(d, d.c.werkgebied_id == werkgebied_id, d.c.id.in_(per["deelvraag"]))}
    if per.get("begrip"):
        b = db.begrippen
        uit |= {("begrip", i) for i in await ids(b, b.c.id.in_(per["begrip"]))}
    if per.get("markering"):
        e = db.annotatie_v2_elementen
        uit |= {("markering", i) for i in await ids(e, e.c.id.in_(per["markering"]))}
    if werkgebied_id in per.get("werkgebied", set()):
        uit.add(("werkgebied", werkgebied_id))
    return uit


def _sleutel(a: dict) -> tuple[str, str]:
    return ("regel" if a["soort"] == "geval" else a["soort"], a["id"])


async def _toets_aanhakingen(conn, werkgebied_id: str, inhoud: dict) -> None:
    er = await _bestaande(conn, werkgebied_id, inhoud["hangt_aan"])
    onbekend = [a for a in inhoud["hangt_aan"] if _sleutel(a) not in er]
    if onbekend:
        raise HTTPException(422, {"fout": "onbekend", "aanhakingen": onbekend,
                                  "melding": "Het open punt hangt aan iets dat niet in dit werkgebied bestaat: "
                                             + ", ".join(f"{a['soort']} {a['id']}" for a in onbekend) + "."})


# --- lezen ---------------------------------------------------------------------------------------------

def _punt(row, er: set[tuple[str, str]]) -> dict:
    inhoud = row.inhoud
    return {"id": row.id, "werkgebied_id": row.werkgebied_id, "status": row.status, "revisie": row.revisie,
            "soort": inhoud["soort"], "soort_naam": SOORT_NAMEN[Soort(inhoud["soort"])],
            "inhoud": {**inhoud, "hangt_aan": [{**a, "bestaat": _sleutel(a) in er} for a in inhoud["hangt_aan"]]},
            "keuze": row.keuze, "herkomst": row.herkomst, "aangemaakt_door": row.aangemaakt_door,
            "aangemaakt": _iso(row.aangemaakt), "gewijzigd": _iso(row.gewijzigd)}


async def _lees(conn, werkgebied_id: str, rows) -> list[dict]:
    er = await _bestaande(conn, werkgebied_id, [a for r in rows for a in r.inhoud["hangt_aan"]])
    return [_punt(r, er) for r in rows]


def _niet_gevonden() -> HTTPException:
    return HTTPException(404, {"fout": "niet_gevonden", "melding": "Dit open punt bestaat niet (meer)."})


async def haal(werkgebied_id: str, punt_id: str) -> dict:
    t = db.open_punten
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        row = (await conn.execute(select(t).where(t.c.id == punt_id, t.c.werkgebied_id == werkgebied_id))).first()
        if row is None:
            raise _niet_gevonden()
        return (await _lees(conn, werkgebied_id, [row]))[0]


async def lijst(werkgebied_id: str, *, status: str | None = None, soort: str | None = None,
                hangt_aan: tuple[str, str] | None = None) -> list[dict]:
    """Alle open punten van het werkgebied, oudste eerst; te filteren op status, soort en waar het aan hangt
    (`hangt_aan=("regel", id)` vindt ook de punten op een geval van die regel)."""
    t = db.open_punten
    q = select(t).where(t.c.werkgebied_id == werkgebied_id)
    if status:
        q = q.where(t.c.status == status)
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        rows = (await conn.execute(q.order_by(t.c.aangemaakt, t.c.id))).all()
        if soort:
            rows = [r for r in rows if r.inhoud["soort"] == soort]
        if hangt_aan:
            rows = [r for r in rows if hangt_aan in {_sleutel(a) for a in r.inhoud["hangt_aan"]}]
        return await _lees(conn, werkgebied_id, rows)


def kort(p: dict) -> dict:
    """Een punt in één regel, voor het werkgebied (de context van Lex) en het rapport: wat open is, wat gekozen is."""
    keuze = p.get("keuze") or {}
    lezing = next((x for x in p["inhoud"].get("lezingen") or [] if x["label"] == keuze.get("gekozen")), None)
    return {"id": p["id"], "soort": p["soort"], "soort_naam": p["soort_naam"], "status": p["status"],
            "vraag": p["inhoud"]["vraag"],
            "hangt_aan": [{k: a[k] for k in ("soort", "id", "geval") if a.get(k)} for a in p["inhoud"]["hangt_aan"]],
            "gekozen": keuze.get("gekozen", ""), "gekozen_lezing": lezing["omschrijving"] if lezing else "",
            "methode": keuze.get("methode") or "",
            "nog_te_toetsen": [t["bronsoort"] for t in p["inhoud"].get("te_toetsen") or [] if not t.get("getoetst")]}


async def samenvatting(werkgebied_id: str) -> dict:
    """De open punten van het werkgebied in het kort, met een telling per status (de open eerst)."""
    punten = await lijst(werkgebied_id)
    volgorde = {"open": 0, "gesignaleerd": 1, "gekozen": 2, "getoetst": 3}
    punten.sort(key=lambda p: (volgorde.get(p["status"], 3), p["aangemaakt"] or "", p["id"]))
    telling = {s: sum(1 for p in punten if p["status"] == s) for s in volgorde}
    return {"telling": telling, "punten": [kort(p) for p in punten[:MAX_SAMENVATTING]],
            "afgekapt": max(0, len(punten) - MAX_SAMENVATTING)}


async def revisies(werkgebied_id: str, punt_id: str, limit: int = 100) -> list[dict]:
    await haal(werkgebied_id, punt_id)
    t = db.open_punt_revisies
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(t).where(t.c.open_punt_id == punt_id).order_by(t.c.revisie.desc())
                                   .limit(limit))).all()
    return [{"revisie": r.revisie, "actie": r.actie, "detail": r.detail, "status": r.status, "inhoud": r.inhoud,
             "keuze": r.keuze, "actor": r.actor, "tijdstip": _iso(r.tijdstip)} for r in rows]


# --- schrijven -----------------------------------------------------------------------------------------

async def _revisieregel(conn, werkgebied_id, punt_id, revisie, actie, detail, status, inhoud, keuze, actor, tijdstip):
    await conn.execute(insert(db.open_punt_revisies).values(
        open_punt_id=punt_id, revisie=revisie, werkgebied_id=werkgebied_id, actie=actie, detail=detail, status=status,
        inhoud=inhoud, keuze=keuze, actor=actor, tijdstip=tijdstip))


async def maak(werkgebied_id: str, invoer: OpenPuntAanmaak, actor: str) -> dict:
    inhoud = invoer.inhoud.model_dump(mode="json")
    pid, nu = str(uuid.uuid4()), db.utcnow()
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        await _toets_aanhakingen(conn, werkgebied_id, inhoud)
        await conn.execute(insert(db.open_punten).values(
            id=pid, werkgebied_id=werkgebied_id, status="open", revisie=1, inhoud=inhoud, keuze=None,
            herkomst=invoer.herkomst, aangemaakt_door=actor, aangemaakt=nu, gewijzigd=nu))
        detail = {"soort": inhoud["soort"], "herkomst": invoer.herkomst,
                  "hangt_aan": [_sleutel(a) for a in inhoud["hangt_aan"]]}
        await _revisieregel(conn, werkgebied_id, pid, 1, "open-punt-aangemaakt", detail, "open", inhoud, None, actor, nu)
        await werkgebied_audit(conn, werkgebied_id, actor, "open-punt-aangemaakt",
                               {**detail, "open_punt_id": pid, "open_punt_revisie": 1})
    return await haal(werkgebied_id, pid)


@asynccontextmanager
async def _gewijzigd_in(conn, werkgebied_id: str, punt_id: str, verwacht: int, actor: str, actie: str, detail: dict):
    """Werkgebiedslot, puntslot, revisietoets; daarna revisie +1, de status opnieuw afgeleid, revisiekopie en audit.
    De aanroeper muteert via `stand` (`inhoud`, `keuze`, `geen_wijziging`)."""
    t = db.open_punten
    await werkgebied_rij(conn, werkgebied_id, slot=True)
    row = (await conn.execute(select(t).where(t.c.id == punt_id, t.c.werkgebied_id == werkgebied_id)
                              .with_for_update())).first()
    if row is None:
        raise _niet_gevonden()
    toets_revisie(row.revisie, verwacht, "dit open punt")
    stand: dict[str, Any] = {"inhoud": row.inhoud, "keuze": row.keuze, "geen_wijziging": False}
    yield row, stand
    if stand["geen_wijziging"]:
        return
    status = status_van(stand["inhoud"], stand["keuze"])
    nieuw, nu = row.revisie + 1, db.utcnow()
    await conn.execute(update(t).where(t.c.id == punt_id).values(
        revisie=nieuw, gewijzigd=nu, status=status, inhoud=stand["inhoud"], keuze=stand["keuze"]))
    await _revisieregel(conn, werkgebied_id, punt_id, nieuw, actie, detail, status, stand["inhoud"], stand["keuze"],
                        actor, nu)
    await werkgebied_audit(conn, werkgebied_id, actor, actie,
                           {**detail, "status": status, "open_punt_id": punt_id, "open_punt_revisie": nieuw})


async def wijzig(werkgebied_id: str, punt_id: str, w: OpenPuntWijziging, actor: str) -> dict:
    """De inhoud wijzigen: de vraag, waar het aan hangt, de lezingen, wat te toetsen is (ook: een toets afvinken).
    Verdwijnt de gekozen lezing uit de lezingen, dan vervalt de keuze: wie de lezingen verandert, kiest opnieuw."""
    nieuw = w.inhoud.model_dump(mode="json")
    detail: dict = {}
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, punt_id, w.verwachte_revisie, actor, "open-punt-gewijzigd",
                                 detail) as (row, stand):
            if nieuw == row.inhoud:
                stand["geen_wijziging"] = True
            else:
                await _toets_aanhakingen(conn, werkgebied_id, nieuw)
                detail["velden"] = sorted(k for k in nieuw if nieuw.get(k) != row.inhoud.get(k))
                keuze = row.keuze or {}
                if keuze.get("gekozen") and keuze["gekozen"] not in {x["label"] for x in nieuw["lezingen"]}:
                    stand["keuze"] = None
                    detail["keuze_vervallen"] = keuze["gekozen"]
                stand["inhoud"] = nieuw
    return await haal(werkgebied_id, punt_id)


async def besluit(werkgebied_id: str, punt_id: str, b: Besluit, actor: str) -> dict:
    """De keuze van de jurist. Met lezingen: `gekozen` is het label van een lezing. Zonder lezingen: de motivering
    zegt hoe het verder gaat. Leeg (geen keuze en geen motivering) heropent een besloten punt; op een open punt is dat
    een 422, want er gebeurt dan niets (B5). Bij ontbrekend uitvoeringsbeleid zegt `uitkomst` of het beleid gevonden is
    (`gekozen`) of ontbreekt (`gesignaleerd`, met in de motivering wat er ontbreekt)."""
    gekozen, motivering = b.gekozen.strip(), b.motivering.strip()
    uitkomst = b.uitkomst.value if b.uitkomst else ""
    heropenen = not gekozen and not motivering and not uitkomst
    detail = {"gekozen": gekozen, "methode": b.methode.value if b.methode else "", "heropend": heropenen,
              **({"uitkomst": uitkomst} if uitkomst else {})}
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, punt_id, b.verwachte_revisie, actor,
                                 "open-punt-heropend" if heropenen else "open-punt-besloten", detail) as (row, stand):
            lezingen = {x["label"] for x in row.inhoud.get("lezingen") or []}
            beleid = row.inhoud["soort"] == Soort.ontbrekend_uitvoeringsbeleid.value
            if heropenen:
                if not row.keuze:
                    raise HTTPException(422, {"fout": "leeg_besluit", "melding": "Dit punt staat al open. Kies een "
                                              "lezing, of leg in de motivering vast hoe het verder gaat."})
                stand["keuze"] = None
            else:
                if uitkomst == "gesignaleerd":
                    # Het beleid ontbreekt: geen keuze tussen lezingen, wel vastleggen wat er ontbreekt.
                    if not beleid:
                        raise HTTPException(422, {"fout": "uitkomst", "melding": "Alleen ontbrekend uitvoeringsbeleid "
                                                  "wordt gesignaleerd; bij dit punt kies je."})
                    if gekozen:
                        raise HTTPException(422, {"fout": "uitkomst", "melding": "Een gesignaleerd punt kiest geen "
                                                  "lezing: het beleid ontbreekt."})
                    if not motivering:
                        raise HTTPException(422, {"fout": "motivering", "melding": "Zeg welk beleid ontbreekt."})
                else:
                    if lezingen and gekozen not in lezingen:
                        raise HTTPException(422, {"fout": "lezing_onbekend", "lezingen": sorted(lezingen),
                                                  "melding": "Kies een van de lezingen: " + ", ".join(sorted(lezingen))
                                                             + "."})
                    if not lezingen and gekozen:
                        raise HTTPException(422, {"fout": "geen_lezingen", "melding": "Dit punt heeft geen lezingen; "
                                                  "leg in de motivering vast hoe het verder gaat."})
                    if not lezingen and not motivering:
                        raise HTTPException(422, {"fout": "motivering", "melding": "Leg vast hoe het verder gaat."})
                    if beleid and not uitkomst and not (lezingen and gekozen):
                        raise HTTPException(422, {"fout": "uitkomst", "melding": "Zeg of het beleid gevonden is "
                                                  "(gekozen) of ontbreekt (gesignaleerd)."})
                stand["keuze"] = {"gekozen": gekozen, "motivering": motivering,
                                  "methode": b.methode.value if b.methode else "", "door": actor,
                                  "op": db.utcnow().isoformat(), "uitkomst": uitkomst or "gekozen"}
    return await haal(werkgebied_id, punt_id)


async def omhang(werkgebied_id: str, punt_id: str, w: Omhangen, actor: str) -> dict:
    """Alleen `hangt_aan` wijzigen (A2), met een revisie en de auditregel `open-punt-omgehangen` met toen en nu. De
    rest van de inhoud en de keuze blijven staan: anders vraagt omhangen de hele inhoud terug, en vallen er velden weg.
    Een geval moet bestaan in de regel waar het naar wijst."""
    nieuw = [a.model_dump(mode="json") for a in w.hangt_aan]
    detail: dict = {}
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, punt_id, w.verwachte_revisie, actor, "open-punt-omgehangen",
                                 detail) as (row, stand):
            oud = row.inhoud["hangt_aan"]
            if [_sleutel(a) + (a.get("geval", ""),) for a in nieuw] == [_sleutel(a) + (a.get("geval", ""),) for a in oud]:
                stand["geen_wijziging"] = True
            else:
                inhoud = {**row.inhoud, "hangt_aan": nieuw}
                await _toets_aanhakingen(conn, werkgebied_id, inhoud)
                await _toets_gevallen(conn, werkgebied_id, nieuw)
                detail.update(toen=oud, nu=nieuw)
                stand["inhoud"] = inhoud
    return await haal(werkgebied_id, punt_id)


async def _toets_gevallen(conn, werkgebied_id: str, aanhakingen: list[dict]) -> None:
    """Een geval noemt een label dat de regel heeft (422 `geval_onbekend`)."""
    gevallen = [a for a in aanhakingen if a["soort"] == "geval"]
    if not gevallen:
        return
    r = db.regels
    labels = {x.id: {g.get("label", "") for g in x.inhoud.get("gevallen", [])} for x in (await conn.execute(
        select(r.c.id, r.c.inhoud).where(r.c.werkgebied_id == werkgebied_id,
                                         r.c.id.in_(sorted({a["id"] for a in gevallen}))))).all()}
    fout = [a for a in gevallen if a["geval"] not in labels.get(a["id"], set())]
    if fout:
        raise HTTPException(422, {"fout": "geval_onbekend", "aanhakingen": fout,
                                  "melding": "Deze regel heeft dat geval niet: "
                                             + ", ".join(f"{a['geval']} ({a['id']})" for a in fout) + "."})


async def verwijder(werkgebied_id: str, punt_id: str, verwacht: int, actor: str) -> dict:
    """Echt wissen, zoals een regel: het punt en zijn revisies. De audit blijft."""
    t = db.open_punten
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(t).where(t.c.id == punt_id, t.c.werkgebied_id == werkgebied_id)
                                  .with_for_update())).first()
        if row is None:
            raise _niet_gevonden()
        toets_revisie(row.revisie, verwacht, "dit open punt")
        await conn.execute(delete(db.open_punt_revisies).where(db.open_punt_revisies.c.open_punt_id == punt_id))
        await conn.execute(delete(t).where(t.c.id == punt_id))
        await werkgebied_audit(conn, werkgebied_id, actor, "open-punt-verwijderd",
                               {"open_punt_id": punt_id, "soort": row.inhoud["soort"], "vraag": row.inhoud["vraag"]})
    return {"verwijderd": punt_id}
