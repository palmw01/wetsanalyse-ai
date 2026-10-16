"""Onderhoud van begrippen (spoor D, fase F1): herbeoordeling, herkoppeling en dekking.

Acceptatie: *een gewijzigde dragende passage verschijnt bij de geraakte begrippen; de oude bewijsstand
blijft.*

- **Herbeoordelingen** (`herbeoordelingen`) leggen per dragende koppeling de bewaarde stand naast de
  stand van nu. Twee bronnen van verandering: de annotatie (Postgres: `begrip_store.actualiteit`) en de
  wettekst onder het anker (de bronboom uit de graaf). Een nieuwe bronstand alleen is een signaal: is
  het gemarkeerde fragment er nog letterlijk, dan zegt de lijst dat ook (PLAN §D *Wijzigingen*).
- **Opvolgers** (`opvolgers`, zuiver): na herannotatie is er een nieuw element met een nieuw id. De
  kandidaten zijn de actuele elementen op dezelfde bronnode, met signalen met richting (klasse, tekst,
  plek, al elders primair) – geen score, en nooit een automatische herkoppeling.
- **Herkoppelen** maakt een nieuwe koppeling (rol van de oude, beoordeeld: de analist zag toen en nu
  naast elkaar) en haalt de oude weg met `vervangen_door`; haar bewijs blijft leesbaar.
  **Bevestigen** voegt een bewijsstand toe aan `bevestigingen`; `bewijs` verandert nooit.
- **Een geaccordeerd begrip blijft geaccordeerd** bij herkoppelen en bevestigen (besloten 16 okt 2026):
  de inhoud verandert niet, en zolang er iets open staat zegt de aandacht dat. Geen statuswijziging
  zonder handeling van een mens.
- **Dekking** (`dekking`): elk element van de inventaris één keer in `te_verwerken`, `voorstel`,
  `gekoppeld` (aan een geaccordeerd begrip) of `buiten_behandeling` (bewust, met reden), plus
  `nieuw_sinds_run` voor wat de laatste klare begrippenrun niet zag.
"""
from __future__ import annotations

import re
import uuid

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from . import begrip_relatie_store, begrip_store, begrippen_run_store, db
from .begrip_manifest import _vindplaats
from .begrip_onderhoud_contracts import Bevestiging, BuitenBehandeling, Herkoppeling
from .werkgebied_inventaris import Resolver, inventaris, inventaris_met_bronbomen, nodes_met_titel
from .werkgebied_store import _audit as werkgebied_audit

MAX_OPVOLGERS = 5


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _bwb(iri: str) -> str:
    delen = iri.split(":")
    return delen[2] if len(delen) > 2 else ""


def referentie_ankers(k: dict) -> list[dict]:
    """De ankers waartegen de wettekst wordt vergeleken: van de nieuwste bevestiging, anders het bewijs."""
    bev = k.get("bevestigingen") or []
    return (bev[-1].get("ankers") if bev else None) or k["bewijs"].get("ankers", [])


def bron_signalen(ankers: list[dict], nodes: dict[str, dict], opgehaald: set[str]) -> list[dict]:
    """Per anker: is de wettekst eronder veranderd, en staat het fragment er nog letterlijk?

    `stand`: `ongewijzigd`, `gewijzigd`, `weg` (de bronnode bestaat niet meer in de actuele stand) of
    `onbekend` (de regeling was niet op te halen – een open punt, geen conclusie)."""
    uit = []
    for a in ankers:
        iri = a.get("bron_iri", "")
        n = nodes.get(iri)
        regel = {"bron_iri": iri, "vindplaats": _vindplaats(nodes, iri) if n else "", "fragment": a.get("tekst", "")}
        if n is None:
            regel["stand"] = "weg" if _bwb(iri) in opgehaald else "onbekend"
        elif n.get("bron_hash") == a.get("bron_hash"):
            regel["stand"] = "ongewijzigd"
        else:
            tekst = n.get("tekst", "")
            regel.update(stand="gewijzigd", tekst_nu=tekst,
                         fragment_gelijk=tekst[a.get("start", 0):a.get("eind", 0)] == a.get("tekst", ""))
        uit.append(regel)
    return uit


def _redenen(k: dict, huidig: dict | None, bron: list[dict]) -> list[str]:
    uit = []
    if k["actualiteit"] == "verdwenen":
        uit.append("De annotatie bestaat niet meer.")
    elif k["actualiteit"] == "verworpen":
        uit.append("Een jurist verwierp de annotatie.")
    elif k["actualiteit"] == "gewijzigd":
        uit.append("De annotatie is verouderd: de wettekst onder het anker veranderde en de bepaling is opnieuw "
                   "geannoteerd." if (huidig or {}).get("verouderd")
                   else "De annotatie veranderde (klasse, tekst of anker).")
    for b in bron:
        plek = b["vindplaats"] or b["bron_iri"]
        if b["stand"] == "weg":
            uit.append(f"{plek} staat niet meer in de actuele wettekst.")
        elif b["stand"] == "onbekend":
            uit.append(f"De wettekst van {plek} was niet op te halen; of hij veranderde is onbekend.")
        elif b["stand"] == "gewijzigd":
            uit.append(f"De wettekst van {plek} veranderde; het gemarkeerde fragment staat er nog letterlijk."
                       if b["fragment_gelijk"] else
                       f"De wettekst van {plek} veranderde, ook op de gemarkeerde plek.")
    return uit


def opvolgers(ref: dict, oud_element_id: str, kandidaten: list[dict], primair: dict[str, dict],
              begrip_id: str, rol: str) -> list[dict]:
    """Elementen die de passage van een koppeling kunnen opvolgen, met signalen met richting.

    `ref` is de bewaarde stand (tekst, klasse, ankers, eigenaar). Kandidaat = een actueel element op een
    bronnode van de oude ankers, of met dezelfde eigenaar. Volgorde: eerst wie op dezelfde plek staat,
    dan wie dezelfde tekst draagt, dan de plek in de bepaling – geen gecombineerde score."""
    oude = {a["bron_iri"]: a for a in ref.get("ankers", [])}
    uit = []
    for e in kandidaten:
        if e["id"] == oud_element_id or e.get("verouderd") or e.get("lifecycle") == "rejected":
            continue
        ankers = e.get("ankers") or []
        if not (any(a["bron_iri"] in oude for a in ankers) or e.get("eigenaar_iri") == ref.get("eigenaar_iri")):
            continue
        signalen = []
        if e.get("klasse") == ref.get("klasse"):
            signalen.append({"richting": "steun", "uitleg": f"Zelfde JAS-klasse ({e.get('klasse') or 'geen'})."})
        else:
            signalen.append({"richting": "tegen",
                             "uitleg": f"Andere JAS-klasse: {ref.get('klasse') or 'geen'} → {e.get('klasse') or 'geen'}."})
        if e.get("tekst", "") == ref.get("tekst", ""):
            signalen.append({"richting": "steun", "uitleg": "Zelfde tekst."})
            zelfde_tekst = True
        elif _norm(e.get("tekst", "")) == _norm(ref.get("tekst", "")):
            signalen.append({"richting": "steun", "uitleg": "Zelfde tekst, op hoofdletters en spaties na."})
            zelfde_tekst = True
        elif _norm(ref.get("tekst", "")) in _norm(e.get("tekst", "")) or _norm(e.get("tekst", "")) in _norm(ref.get("tekst", "")):
            signalen.append({"richting": "onbeslist", "uitleg": "De teksten overlappen."})
            zelfde_tekst = False
        else:
            signalen.append({"richting": "tegen", "uitleg": "Andere tekst."})
            zelfde_tekst = False
        overlap = any(a["bron_iri"] in oude and a.get("start", 0) < oude[a["bron_iri"]].get("eind", 0)
                      and oude[a["bron_iri"]].get("start", 0) < a.get("eind", 0) for a in ankers)
        signalen.append({"richting": "steun", "uitleg": "Op dezelfde plek in de bepaling."} if overlap else
                        {"richting": "onbeslist", "uitleg": "Elders in dezelfde bepaling."})
        elders = primair.get(e["id"])
        if rol == "duiding" and elders and elders["begrip_id"] != begrip_id:
            signalen.append({"richting": "tegen",
                             "uitleg": f"Duidt al het begrip \"{elders['naam']}\" aan; als duiding kan het hier niet."})
        eerste = min(ankers, key=lambda a: a.get("start", 0)) if ankers else {}
        uit.append({"element_id": e["id"], "tekst": e.get("tekst", ""), "klasse": e.get("klasse", ""),
                    "lifecycle": e.get("lifecycle", ""),
                    "annotatie_beoordeeld": e.get("lifecycle") in begrip_store.BEOORDEELD,
                    "signalen": signalen, "_sleutel": (not overlap, not zelfde_tekst, eerste.get("start", 0), e["id"])})
    uit.sort(key=lambda x: x.pop("_sleutel"))
    return uit[:MAX_OPVOLGERS]


def _stand(bewijs: dict) -> dict:
    return {k: bewijs.get(k) for k in ("tekst", "klasse", "jas_subtype", "ankers", "vindplaats", "lifecycle",
                                        "snapshot_id", "eigenaar_iri")}


async def herbeoordelingen(werkgebied: dict, resolve: Resolver, begrip_id: str | None = None) -> dict:
    """De begrippen met een geraakte dragende passage, per koppeling met toen, nu, de bronsignalen, de
    opvolgers en wat de analist kan doen."""
    inv, per_bwb = await inventaris_met_bronbomen(werkgebied["bronnen"], resolve)
    nodes: dict[str, dict] = {}
    for snap in per_bwb.values():
        nodes.update(nodes_met_titel(snap))
    opgehaald = set(per_bwb)
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied["id"])
        q = select(b).where(b.c.werkgebied_id == werkgebied["id"], b.c.verwijderd.is_(None))
        if begrip_id:
            q = q.where(b.c.id == begrip_id)
        rows = (await conn.execute(q.order_by(b.c.aangemaakt, b.c.id))).all()
        if begrip_id and not rows:
            raise HTTPException(404, "Begrip bestaat niet.")
        koppelingen = await begrip_store._koppelingen_van(conn, werkgebied["id"], begrip_id)
        huidig = await begrip_store._huidige_elementen(conn, {k["element_id"] for k in koppelingen})
        # Doorwerking (fase F2): vastgelegde relaties waarvan de andere kant veranderde.
        relaties = begrip_relatie_store.doorwerking(await begrip_relatie_store._rijen(conn, werkgebied["id"]),
                                                    await begrip_relatie_store._begrippen(conn, werkgebied["id"]))
    primair = await begrip_store.primaire_duidingen(werkgebied["id"])
    uit = []
    for row in rows:
        if row.status == "vervangen":
            continue                                 # alleen-lezen; de opvolger draagt het werk
        geraakt = []
        for k in koppelingen:
            if k["begrip_id"] != row.id or k["rol"] not in begrip_store.DRAGEND or k["beoordeling"] == "afgewezen":
                continue
            h = huidig.get(k["element_id"])
            bron = bron_signalen(referentie_ankers(k), nodes, opgehaald)
            if k["actualiteit"] == "actueel" and all(x["stand"] == "ongewijzigd" for x in bron):
                continue
            ref = {**k["bewijs"], "ankers": referentie_ankers(k)}
            kan_opvolgen = k["actualiteit"] != "actueel" or (h or {}).get("verouderd")
            # Bevestigen: de annotatie bestaat nog, is niet verworpen of door herannotatie vervangen, en
            # elk fragment staat letterlijk op zijn plek – anders hoort de bepaling opnieuw geannoteerd.
            kan_bevestigen = (h is not None and h.get("lifecycle") != "rejected" and not h.get("verouderd")
                              and all(x["stand"] == "ongewijzigd" or (x["stand"] == "gewijzigd" and x["fragment_gelijk"])
                                      for x in bron_signalen(h.get("ankers", []), nodes, opgehaald)))
            opv = opvolgers(ref, k["element_id"], inv["elementen"], primair, row.id, k["rol"]) if kan_opvolgen else []
            opnieuw = sorted({x["bron_iri"] for x in bron if x["stand"] == "gewijzigd" and not x["fragment_gelijk"]})
            geraakt.append({
                "koppeling_id": k["id"], "element_id": k["element_id"], "rol": k["rol"],
                "actualiteit": k["actualiteit"], "redenen": _redenen(k, h, bron),
                "toen": _stand(k["bewijs"]), "bevestigingen": k.get("bevestigingen", []),
                "nu": ({"tekst": h.get("tekst", ""), "klasse": h.get("klasse", ""), "jas_subtype": h.get("jas_subtype", ""),
                        "ankers": h.get("ankers", []), "lifecycle": h.get("lifecycle", ""),
                        "verouderd": bool(h.get("verouderd"))} if h else None),
                "bron": bron, "opvolgers": opv,
                # Geen opvolger en de tekst op de gemarkeerde plek veranderde: eerst opnieuw annoteren.
                "opnieuw_annoteren": opnieuw if not opv else [],
                "acties": [a for a, mag in (("herkoppelen", bool(opv)), ("bevestigen", kan_bevestigen),
                                            ("loskoppelen", True)) if mag]})
        if geraakt or relaties.get(row.id):
            uit.append({"begrip_id": row.id, "naam": row.inhoud.get("naam", ""), "status": row.status,
                        "revisie": row.revisie, "koppelingen": geraakt, "relaties": relaties.get(row.id, [])})
    return {"werkgebied_id": werkgebied["id"], "begrippen": uit, "volledig": inv["volledig"],
            "open_punten": [{"bron_iri": s["bron_iri"], "label": s["label"], "melding": s["onbereikbaar"]}
                            for s in inv["selecties"] if s["onbereikbaar"]]}


async def _koppeling_rij(conn, begrip_id: str, koppeling_id: str):
    k = db.begrip_koppelingen
    row = (await conn.execute(select(k).where(k.c.id == koppeling_id, k.c.begrip_id == begrip_id,
                                              k.c.verwijderd.is_(None)))).first()
    if row is None:
        raise HTTPException(404, "Koppeling bestaat niet.")
    return row


async def herkoppel(werkgebied: dict, begrip_id: str, koppeling_id: str, h: Herkoppeling, actor: str,
                    resolve: Resolver) -> dict:
    await begrip_store.haal(werkgebied["id"], begrip_id)          # 404 vóór de graaf wordt gevraagd
    bewijs = await begrip_store.bewijzen(werkgebied, [h.element_id], resolve)
    k = db.begrip_koppelingen
    detail: dict = {"koppeling": koppeling_id, "element_id": h.element_id}
    async with begrip_store._gewijzigd(werkgebied["id"], begrip_id, h.verwachte_revisie, actor,
                                       "koppeling-herkoppeld", detail) as (conn, row, stand):
        oud = await _koppeling_rij(conn, begrip_id, koppeling_id)
        if oud.element_id == h.element_id:
            raise HTTPException(422, {"fout": "zelfde_passage",
                                      "melding": "Dit is dezelfde passage; bevestig haar als het begrip nog klopt."})
        nu = db.utcnow()
        bestaand = (await conn.execute(select(k.c.id).where(
            k.c.begrip_id == begrip_id, k.c.element_id == h.element_id, k.c.rol == oud.rol,
            k.c.verwijderd.is_(None)))).scalar()
        if bestaand:
            nieuw_id = bestaand
        else:
            if oud.rol == "duiding":
                await begrip_store._toets_primair(conn, werkgebied["id"], begrip_id, [h.element_id])
            nieuw_id = str(uuid.uuid4())
            # Beoordeeld: de analist zag toen en nu naast elkaar en koos deze passage.
            await conn.execute(insert(k).values(
                id=nieuw_id, begrip_id=begrip_id, werkgebied_id=werkgebied["id"], element_id=h.element_id,
                rol=oud.rol, motivatie=h.motivatie or oud.motivatie, bewijs=bewijs[h.element_id],
                beoordeling="akkoord", beoordeeld_door=actor, beoordeeld_op=nu, toegevoegd_door=actor, toegevoegd=nu))
        await conn.execute(update(k).where(k.c.id == koppeling_id).values(verwijderd=nu, vervangen_door=nieuw_id))
        detail.update(oud_element=oud.element_id, nieuwe_koppeling=nieuw_id, rol=oud.rol)
        if row.status == "geaccordeerd":
            stand["status"] = "geaccordeerd"
    return await begrip_store.haal(werkgebied["id"], begrip_id)


async def bevestig(werkgebied: dict, begrip_id: str, koppeling_id: str, bv: Bevestiging, actor: str,
                   resolve: Resolver) -> dict:
    await begrip_store.haal(werkgebied["id"], begrip_id)
    _, per_bwb = await inventaris_met_bronbomen(werkgebied["bronnen"], resolve)
    nodes: dict[str, dict] = {}
    for snap in per_bwb.values():
        nodes.update(nodes_met_titel(snap))
    detail: dict = {"koppeling": koppeling_id}
    async with begrip_store._gewijzigd(werkgebied["id"], begrip_id, bv.verwachte_revisie, actor,
                                       "koppeling-bevestigd", detail) as (conn, row, stand):
        oud = await _koppeling_rij(conn, begrip_id, koppeling_id)
        h = (await begrip_store._huidige_elementen(conn, {oud.element_id})).get(oud.element_id)
        if h is None or h.get("lifecycle") == "rejected" or h.get("verouderd"):
            raise HTTPException(422, {"fout": "niet_te_bevestigen",
                                      "melding": "Deze annotatie bestaat niet meer, is verworpen of door een nieuwe "
                                                 "annotatie vervangen; herkoppel of koppel los."})
        ankers = []
        for a in h.get("ankers", []):
            n = nodes.get(a["bron_iri"])
            if n is None or n.get("tekst", "")[a.get("start", 0):a.get("eind", 0)] != a.get("tekst", ""):
                raise HTTPException(422, {"fout": "fragment_weg",
                                          "melding": "Het gemarkeerde fragment staat niet meer op zijn plek in de "
                                                     "wettekst; laat de bepaling opnieuw annoteren."})
            ankers.append({**a, "bron_hash": n["bron_hash"]})
        k = {"bewijs": oud.bewijs, "bevestigingen": oud.bevestigingen or []}
        hash_nu = begrip_store.element_hash(h)
        if begrip_store.referentie_hash(k) == hash_nu and \
                [a["bron_hash"] for a in referentie_ankers(k)] == [a["bron_hash"] for a in ankers]:
            stand["geen_wijziging"] = True              # er is niets te bevestigen
        else:
            bevestiging = {"element_hash": hash_nu, "ankers": ankers, "tekst": h.get("tekst", ""),
                           "klasse": h.get("klasse", ""), "door": actor, "op": db.utcnow().isoformat(),
                           "motivatie": bv.motivatie}
            await conn.execute(update(db.begrip_koppelingen).where(db.begrip_koppelingen.c.id == koppeling_id)
                               .values(bevestigingen=[*k["bevestigingen"], bevestiging]))
            detail.update(element_id=oud.element_id, rol=oud.rol)
            if row.status == "geaccordeerd":
                stand["status"] = "geaccordeerd"
    return await begrip_store.haal(werkgebied["id"], begrip_id)


# --- dekking -----------------------------------------------------------------------------------

STANDEN = ("te_verwerken", "voorstel", "gekoppeld", "buiten_behandeling")


async def _besluiten(conn, werkgebied_id: str) -> dict[str, dict]:
    t = db.werkgebied_element_besluiten
    rows = (await conn.execute(select(t).where(t.c.werkgebied_id == werkgebied_id, t.c.verwijderd.is_(None)))).all()
    return {r.element_id: {"reden": r.reden, "door": r.besloten_door, "op": db.aware(r.besloten_op).isoformat()}
            for r in rows}


async def dekking(werkgebied: dict, resolve: Resolver) -> dict:
    """Elk element van de inventaris één keer. Volgorde van voorrang: gekoppeld (een dragende koppeling
    met een geaccordeerd begrip) → buiten behandeling → voorstel (een concept-begrip of een open groep)
    → te verwerken. De voortgang zegt niets over juridische dekking (PLAN §D)."""
    inv = await inventaris(werkgebied["bronnen"], resolve)
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied["id"])
        status = {r.id: (r.status, r.inhoud.get("naam", "")) for r in (await conn.execute(select(b.c.id, b.c.status, b.c.inhoud)
                  .where(b.c.werkgebied_id == werkgebied["id"], b.c.verwijderd.is_(None),
                         b.c.status != "vervangen"))).all()}
        koppelingen = await begrip_store._koppelingen_van(conn, werkgebied["id"])
        besluiten = await _besluiten(conn, werkgebied["id"])
        run = await begrippen_run_store._laatste_klare(conn, werkgebied["id"])
    groepen = (await begrippen_run_store.groepen(werkgebied["id"]))["groepen"] if run is not None else []
    in_groep = {p["element_id"] for g in groepen if g["besluit"] in ("open", "geparkeerd") for p in g["leden"]}
    gezien = ({f["element_id"] for f in run.manifest.get("formuleringen", [])}
              | {o["element_id"] for o in (run.overgeslagen or [])}) if run is not None else None
    per_element: dict[str, list[dict]] = {}
    for k in koppelingen:
        if k["beoordeling"] != "afgewezen" and k["begrip_id"] in status:
            per_element.setdefault(k["element_id"], []).append(k)
    elementen, totalen = [], dict.fromkeys(STANDEN, 0)
    for e in inv["elementen"]:
        ks = per_element.get(e["id"], [])
        begrippen = sorted({(k["begrip_id"], status[k["begrip_id"]][1], k["rol"]) for k in ks})
        if any(k["rol"] in begrip_store.DRAGEND and status[k["begrip_id"]][0] == "geaccordeerd" for k in ks):
            stand = "gekoppeld"
        elif e["id"] in besluiten:
            stand = "buiten_behandeling"
        elif ks or e["id"] in in_groep:
            stand = "voorstel"
        else:
            stand = "te_verwerken"
        totalen[stand] += 1
        elementen.append({"element_id": e["id"], "tekst": e.get("tekst", ""), "klasse": e.get("klasse", ""),
                          "rol": e["rol"], "stand": stand,
                          "begrippen": [{"begrip_id": i, "naam": n, "rol": r} for i, n, r in begrippen],
                          "buiten_behandeling": besluiten.get(e["id"]),
                          "nieuw_sinds_run": gezien is not None and e["id"] not in gezien})
    return {"werkgebied_id": werkgebied["id"], "totalen": totalen, "totaal": len(elementen),
            "nieuw_sinds_run": sum(x["nieuw_sinds_run"] for x in elementen),
            "laatste_run": run.id if run is not None else None,
            "elementen": elementen, "volledig": inv["volledig"]}


async def zet_buiten_behandeling(werkgebied: dict, bb: BuitenBehandeling, actor: str, resolve: Resolver) -> dict:
    inv = await inventaris(werkgebied["bronnen"], resolve)
    bekend = {e["id"] for e in inv["elementen"]}
    onbekend = [i for i in bb.element_ids if i not in bekend]
    if onbekend:
        raise HTTPException(422, {"fout": "element_buiten_werkgebied", "element_ids": onbekend,
                                  "melding": "Niet elk element valt binnen dit werkgebied."})
    t = db.werkgebied_element_besluiten
    async with db.get_engine().begin() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied["id"], slot=True)
        al = set(await _besluiten(conn, werkgebied["id"]))
        nieuw = [i for i in dict.fromkeys(bb.element_ids) if i not in al]
        nu = db.utcnow()
        for eid in nieuw:
            await conn.execute(insert(t).values(id=str(uuid.uuid4()), werkgebied_id=werkgebied["id"], element_id=eid,
                                                stand="buiten_behandeling", reden=bb.reden, besloten_door=actor,
                                                besloten_op=nu))
        if nieuw:
            await werkgebied_audit(conn, werkgebied["id"], actor, "element-buiten-behandeling",
                                   {"element_ids": nieuw, "reden": bb.reden})
    return {"element_ids": nieuw}


async def terug_in_behandeling(werkgebied_id: str, element_id: str, actor: str) -> dict:
    t = db.werkgebied_element_besluiten
    async with db.get_engine().begin() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied_id, slot=True)
        r = await conn.execute(update(t).where(t.c.werkgebied_id == werkgebied_id, t.c.element_id == element_id,
                                               t.c.verwijderd.is_(None)).values(verwijderd=db.utcnow()))
        if not r.rowcount:
            raise HTTPException(404, "Dit element staat niet buiten behandeling.")
        await werkgebied_audit(conn, werkgebied_id, actor, "element-in-behandeling", {"element_id": element_id})
    return {"element_id": element_id}
