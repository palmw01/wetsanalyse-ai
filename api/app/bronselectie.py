"""De bronselectie per deelvraag (spoor J): voortgang, besluiten per deelvraag en het overzicht.

Lex begeleidt de bronselectie in het gesprek, maar de applicatie onthoudt waar de analist is – hier, niet
in de gesprek-checkpointer. Zo staat de voortgang er ook na herladen, in een ander gesprek of bij een
collega.

- **Voortgang per deelvraag** (`bronselectie_voortgang`): `niet_gestart` (geen rij) → `in_behandeling` →
  `voorlopig_afgerond` (de analist sluit af, open punten mogen blijven) → `beoordeeld` (alleen door de
  poort: de vragen zijn doorlopen en er staat geen onderzoekspunt open). Een werkgebied zonder deelvragen heeft één rij onder
  `ANALYSEVRAAG`. Elke rij draagt een eigen revisie (412); `openen` is navigeren en draagt er geen.
- **Wat is afgerond, staat op een scope.** `scope_stand` is de hash van analysevraag, afbakening, de
  tekst van de deelvraag en de kandidaten bij die deelvraag, bij het afronden. Wijkt die nu af, dan staat de
  afronding op `opnieuw_bekijken` en telt ze niet meer als klaar; er wordt niets gewist. Een ander dossier
  (context, praktijkvoorbeeld) heropent dus pas iets als de nieuwe zoekopdracht er iets anders door vindt.
- **Wat er ligt, is wat de laatste zoekopdracht vond.** Een open voorstel (voorgesteld, niet gekozen) telt
  alleen als de laatste klare run het vond (`bronnen_run_store.vervallen`); een besluit blijft staan.
- **Eén bron, meer deelvragen.** Een bronselectie is één rij per werkgebied; opnemen bij een deelvraag is
  een koppeling (met een eigen rol), geen tweede selectie. Een besluit *uitgesloten* hoort bij
  één deelvraag (`bron_kandidaat_deelvragen`); het besluit op `bron_kandidaten` blijft het
  werkgebiedbrede besluit en geldt voor elke deelvraag. Bestaande uitsluitingen blijven dus wat ze waren.
- **Kiezen is het besluit.** Wie het kaartje van een deelvraag beantwoordt, kiest; wat niet aangevinkt is, heet
  daarna `niet_gekozen` (afgeleid uit de fase, niet bewaard). Er is geen *later*. Een bepaling die er niet bij stond, noemt de analist zelf (`noem`), en de vragen
  opnieuw doorlopen maakt van *niet gekozen* weer een keuze.
- **De volgende deelvraag kiest de code** (`volgende`): na de gegeven deelvraag de eerste in de volgorde
  die niet klaar is, en anders vooraan verder. Het model kiest hier niets.
"""
from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import delete, insert, select, update

from . import bronnen_run_store, db, werkgebied_deelvragen, werkgebied_store
from .bronnen_run_contracts import ROL_VOLGORDE, Opnemen
from .bronselectie_contracts import ANALYSEVRAAG, Fase, KandidaatBesluit, StatusActie, Voortgang
from .werkgebied_contracts import DeelvraagStatus
from .werkgebied_store import _audit, _gewijzigd

KLAAR = (Voortgang.voorlopig_afgerond.value, Voortgang.beoordeeld.value)
#: Hoe een voorstel bij een deelvraag ervoor staat (naast `opgenomen`, dat de bronnen telt).
STANDEN_TELLING = ("voorgesteld", "niet_gekozen", "uitgesloten")

#: Wat voor bewijs een methode levert. Een tekstuele overeenkomst is geen bewijs van juridische noodzaak;
#: een verwijzing of definitie in de graaf is een aantoonbare relatie.
BEWIJS_SOORT = {"verwijzing_uit": "verwijzing", "verwijzing_in": "verwijzing", "definitie": "definitie",
                "opbouw": "structuur", "overzicht": "tekst", "deelvraag": "tekst", "gelijkenis": "gelijkenis",
                "grondslag": "grondslag", "genoemd": "genoemd"}
#: De grondslag (zoekvraag a: waar de gekozen gebeurtenis haar bestaansrecht krijgt) staat vooraan: zij is het
#: vertrekpunt van de andere zoekvragen.
BEWIJS_VOLGORDE = {"grondslag": -1, "genoemd": -0.5, "verwijzing": 0, "definitie": 1, "structuur": 2, "tekst": 3, "gelijkenis": 4}


ZOEKVRAGEN = ("a", "b", "c", "d")


def scope_stand(werkgebied: dict, vraag: str, kandidaten: list[str]) -> str:
    """De stand waarop een afronding rust. `kandidaten`: de ids die bij de deelvraag in de lijst staan (besluiten
    én de voorstellen van de laatste run), zodat een zoekopdracht die er iets anders vindt de afronding heropent."""
    data = {"analysevraag": " ".join((werkgebied.get("analysevraag") or "").split()),
            "afbakening": " ".join((werkgebied.get("afbakening") or "").split()),
            "vraag": werkgebied_deelvragen.normaliseer(vraag), "kandidaten": sorted(set(kandidaten))}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def bewijs_soorten(bewijs: list[dict]) -> list[str]:
    soorten = {BEWIJS_SOORT.get(b.get("methode", ""), "tekst") for b in bewijs}
    return sorted(soorten, key=lambda s: BEWIJS_VOLGORDE.get(s, 9))


def zoekvragen(bewijs: list[dict]) -> list[str]:
    """De zoekvragen (a–d) die dit voorstel vonden. Het bewijs zelf staat in `GET …/kandidaten`: per deelvraag herhaald
    was het overzicht het grootste antwoord van de api (760 KB in de e2e-wetsanalyse), terwijl niemand het hier las."""
    return sorted({z for x in bewijs if (z := str((x.get("detail") or {}).get("zoekvraag", ""))) in ZOEKVRAGEN})


def _actief(werkgebied: dict) -> list[dict]:
    return [d for d in werkgebied["deelvragen"] if d["status"] == DeelvraagStatus.actief.value]


def _vragen(werkgebied: dict) -> list[dict]:
    """De eenheden van de bronselectie: de actieve deelvragen, of anders de analysevraag."""
    actief = _actief(werkgebied)
    if actief:
        return [{"id": d["id"], "vraag": d["vraag"]} for d in actief]
    return [{"id": ANALYSEVRAAG, "vraag": werkgebied.get("analysevraag") or werkgebied["naam"]}]


def _toets_deelvraag(werkgebied: dict, deelvraag_id: str) -> dict:
    vragen = _vragen(werkgebied)
    for v in vragen:
        if v["id"] == deelvraag_id:
            return v
    if deelvraag_id == ANALYSEVRAAG:
        raise HTTPException(409, {"fout": "heeft_deelvragen",
                                  "melding": "Dit werkgebied heeft deelvragen; kies een deelvraag."})
    alle = {d["id"]: d for d in werkgebied["deelvragen"]}
    if deelvraag_id in alle:
        raise HTTPException(409, {"fout": "niet_actief", "melding": "Deze deelvraag is (nog) niet actief."})
    raise HTTPException(404, "Deelvraag bestaat niet.")


def _rij(row) -> dict:
    return {"status": row.status, "fase": row.fase, "open_punten": row.open_punten or [], "revisie": row.revisie,
            "scope_stand": row.scope_stand, "gewijzigd_door": row.gewijzigd_door,
            "gewijzigd": db.aware(row.gewijzigd).isoformat(), "geopend": db.aware(row.geopend).isoformat()}


async def _lees(werkgebied: dict) -> dict:
    wid = werkgebied["id"]
    v, b, k = db.bronselectie_voortgang, db.bron_kandidaat_deelvragen, db.bron_kandidaten
    kp, s = db.werkgebied_deelvraag_koppelingen, db.werkgebied_bronselecties
    vragen = _vragen(werkgebied)
    ids = [x["id"] for x in vragen]
    async with db.get_engine().connect() as conn:
        rijen = {r.deelvraag_id: r for r in (await conn.execute(select(v).where(v.c.werkgebied_id == wid))).all()}
        besluiten = (await conn.execute(select(b).where(b.c.werkgebied_id == wid))).all()
        kandidaten = (await conn.execute(select(k).where(k.c.werkgebied_id == wid))).all()
        selecties = {r.id: r for r in (await conn.execute(select(s).where(
            s.c.werkgebied_id == wid, s.c.verwijderd.is_(None)))).all()}
        koppelingen = (await conn.execute(select(kp).where(kp.c.deelvraag_id.in_(ids), kp.c.soort == "bron"))).all()
        voorgangers = await werkgebied_deelvragen.voorgangers_in(conn, wid)
        basis = await bronnen_run_store.basis_run_id(conn, wid)
    return {"vragen": vragen, "rijen": rijen, "besluiten": besluiten, "kandidaten": kandidaten,
            "selecties": selecties, "koppelingen": koppelingen, "voorgangers": voorgangers, "basis": basis}


def _hoort_bij(kandidaat, did: str, eigen: set[str], kern_iris: set[str]) -> bool:
    """Deterministisch: gevonden bij deze deelvraag (of een voorganger), of een afhankelijkheid van een
    bron die al bij deze deelvraag hoort."""
    for x in kandidaat.bewijs or []:
        # Elk bewijs dat bij een deelvraag hoort (gevonden bij haar, of door de analist bij haar genoemd).
        if str((x.get("detail") or {}).get("deelvraag_id", "")) in eigen:
            return True
        if x.get("vanuit") and x.get("vanuit") in kern_iris:
            return True
    return False


def _per_vraag(werkgebied: dict, lees: dict) -> list[dict]:
    selecties, kandidaten = lees["selecties"], lees["kandidaten"]
    sel_per_iri = {r.bron_iri: r for r in selecties.values()}
    gekoppeld: dict[str, dict[str, str]] = {}            # deelvraag → selectie-id → rol
    for x in lees["koppelingen"]:
        if x.doel_id in selecties:
            gekoppeld.setdefault(x.deelvraag_id, {})[x.doel_id] = x.rol or ""
    besluit = {(x.kandidaat_id, x.deelvraag_id): x for x in lees["besluiten"]}
    uit = []
    for nr, vraag in enumerate(lees["vragen"], start=1):
        did = vraag["id"]
        alleen = did == ANALYSEVRAAG
        hier = gekoppeld.get(did, {})
        if alleen:
            hier = {sid: "" for sid in selecties}
        bronnen = [{"selectie_id": sid, "bron_iri": selecties[sid].bron_iri, "label": selecties[sid].label,
                    "rol": rol or selecties[sid].rol, "rol_selectie": selecties[sid].rol}
                   for sid, rol in hier.items()]
        bronnen.sort(key=lambda x: (x["rol"] != "analyseren", x["label"], x["bron_iri"]))
        iris_hier = {x["bron_iri"] for x in bronnen}
        eigen = {did} | lees["voorgangers"].get(did, set())
        r = lees["rijen"].get(did)
        voortgang = _rij(r) if r is not None else {
            "status": Voortgang.niet_gestart.value, "fase": Fase.kern.value, "open_punten": [], "revisie": 0,
            "scope_stand": "", "gewijzigd_door": None, "gewijzigd": None, "geopend": None}
        # Het kaartje beantwoorden is het besluit: wat er toen niet aangevinkt werd, is niet gekozen. Dat volgt
        # uit de fase (de kernbepalingen zijn gehad zodra de deelvraag voorbij `kern` is, de rest bij `afronden`)
        # en wordt niet bewaard; de vragen opnieuw doorlopen maakt er weer een keuze van.
        gehad = {"kern": voortgang["status"] in KLAAR or voortgang["fase"] != Fase.kern.value,
                 "rest": voortgang["status"] in KLAAR or voortgang["fase"] == Fase.afronden.value}
        lijst = []
        for kd in kandidaten:
            if not alleen and not ((kd.id, did) in besluit or kd.bron_iri in iris_hier
                                   or _hoort_bij(kd, did, eigen, iris_hier)):
                continue
            rij = besluit.get((kd.id, did))
            elders = kd.bron_iri in sel_per_iri and kd.bron_iri not in iris_hier
            if kd.bron_iri in iris_hier:
                stand, overal = "opgenomen", False
            elif kd.status == "uitgesloten":
                stand, overal = "uitgesloten", True
            elif rij is not None and rij.status == "uitgesloten":
                stand, overal = "uitgesloten", False
            # Wat de laatste zoekopdracht niet meer vond (het dossier of de selectie veranderde), is geen voorstel meer.
            elif bronnen_run_store.vervallen(kd.status, kd.run_id, lees["basis"], kd.bewijs):
                continue
            # Een zelf genoemd voorstel blijft open tot er een besluit is: de analist vroeg er zelf om.
            elif gehad["kern" if kd.rol == "kern" else "rest"] and not bronnen_run_store.genoemd(kd.bewijs):
                stand, overal = "niet_gekozen", False
            else:
                stand, overal = "voorgesteld", False
            uitgesloten_hier = rij is not None and stand == "uitgesloten" and not overal
            lijst.append({"id": kd.id, "bron_iri": kd.bron_iri, "label": kd.label, "bwb_id": kd.bwb_id,
                          "rol": kd.rol, "bewijs_soorten": bewijs_soorten(kd.bewijs or []), "zoekvragen": zoekvragen(kd.bewijs or []),
                          "_bewijzen": len(kd.bewijs or []),
                          "stand": stand, "overal": overal, "elders_opgenomen": elders,
                          "reden": rij.reden if uitgesloten_hier else kd.reden if overal else "",
                          "besloten_door": rij.besloten_door if uitgesloten_hier else kd.besloten_door if overal else None})
        lijst.sort(key=lambda x: (ROL_VOLGORDE.get(x["rol"], 9), BEWIJS_VOLGORDE.get(
            (x["bewijs_soorten"] or ["tekst"])[0], 9), -x.pop("_bewijzen"), x["label"], x["bron_iri"]))
        telling = {st: sum(1 for x in lijst if x["stand"] == st) for st in STANDEN_TELLING}
        telling["opgenomen"] = len(bronnen)
        stand_nu = scope_stand(werkgebied, vraag["vraag"] if not alleen else "", [x["id"] for x in lijst])
        opnieuw = voortgang["status"] in KLAAR and voortgang["scope_stand"] != stand_nu
        redenen = []
        if not gehad["rest"]:
            redenen.append("De vragen bij deze deelvraag zijn nog niet doorlopen.")
        if voortgang["open_punten"]:
            redenen.append("Er staan nog onderzoekspunten open.")
        # Dekking (skill, deelvragen en bronnen): een deelvraag zonder bron om te analyseren is nog open. Voorlopig
        # afronden kan; als beoordeeld vastleggen niet, anders zegt de status meer dan er ligt.
        if not bronnen:
            redenen.append("Er is nog geen bron opgenomen bij deze deelvraag.")
        uit.append({"id": did, "nr": nr, "vraag": vraag["vraag"], **voortgang, "opnieuw_bekijken": opnieuw,
                    "klaar": voortgang["status"] in KLAAR and not opnieuw,
                    "bronnen": bronnen, "kandidaten": lijst, "telling": telling, "_scope_nu": stand_nu,
                    "beoordelen": {"mag": not redenen, "redenen": redenen}})
    return uit


def volgende(vragen: list[dict], na: str | None) -> str | None:
    """De eerste niet-klare deelvraag ná `na` in de volgorde; anders vooraan verder; anders geen."""
    ids = [v["id"] for v in vragen]
    start = ids.index(na) + 1 if na in ids else 0
    for v in vragen[start:] + vragen[:start]:
        if not v["klaar"] and v["id"] != na:
            return v["id"]
    return None


def _zoekdekking(run: dict | None) -> dict:
    """Wat er over het zoeken te zeggen is, los van wat de analist besloot. Een onvolledige methode
    (plafond, haperende graaf) of een mislukte run is een open punt, nooit een stil kleinere lijst."""
    if run is None:
        return {"gezocht": False, "run_id": None, "status": None, "verouderd": False, "volledig": False,
                "onvolledig": [], "reden": "", "methoden": {}, "zoekversie": ""}
    meting = run.get("meting") or {}
    onvolledig = sorted(m for m, x in meting.items() if not (x or {}).get("volledig", True))
    return {"gezocht": run["status"] == "klaar", "run_id": run["id"], "status": run["status"],
            "verouderd": bool(run.get("verouderd")), "volledig": run["status"] == "klaar" and not onvolledig,
            "onvolledig": onvolledig, "reden": run.get("reden", ""), "methoden": meting,
            "zoekversie": run.get("zoekversie", "")}


async def overzicht(werkgebied_id: str, na: str | None = None) -> dict:
    wg = await werkgebied_store.haal(werkgebied_id)
    lees = await _lees(wg)
    vragen = _per_vraag(wg, lees)
    zonder_deelvraag = []
    if vragen and vragen[0]["id"] != ANALYSEVRAAG:
        # Wat bij geen enkele deelvraag hoort, valt niet stil weg: het staat apart.
        bij = {k["id"] for v in vragen for k in v["kandidaten"]}
        zonder_deelvraag = [{"id": kd.id, "bron_iri": kd.bron_iri, "label": kd.label, "rol": kd.rol,
                             "stand": kd.status, "bewijs_soorten": bewijs_soorten(kd.bewijs or [])}
                            for kd in lees["kandidaten"] if kd.id not in bij and kd.status == "voorgesteld"
                            and not bronnen_run_store.vervallen(kd.status, kd.run_id, lees["basis"], kd.bewijs)
                            and kd.bron_iri not in {r.bron_iri for r in lees["selecties"].values()}]
    in_behandeling = [v for v in vragen if v["status"] == Voortgang.in_behandeling.value and v["geopend"]]
    actief = max(in_behandeling, key=lambda v: v["geopend"])["id"] if in_behandeling else None
    run = await bronnen_run_store.laatste(wg)
    for v in vragen:
        v.pop("_scope_nu", None)                     # intern: de stand voor `zet_status`, geen contract
    return {"werkgebied_id": wg["id"], "naam": wg["naam"], "analysevraag": wg.get("analysevraag", ""),
            "gebeurtenis": wg.get("gebeurtenis", ""), "revisie": wg["revisie"], "modus": "analysevraag" if vragen[0]["id"] == ANALYSEVRAAG else "deelvragen",
            "deelvragen": vragen, "actief": actief, "volgende": volgende(vragen, na or actief),
            "alle_klaar": all(v["klaar"] for v in vragen), "zonder_deelvraag": zonder_deelvraag,
            "zoekdekking": _zoekdekking(run)}


# --- voortgang -------------------------------------------------------------------------------

async def _slot(conn, werkgebied_id: str) -> None:
    await werkgebied_store.werkgebied_rij(conn, werkgebied_id, slot=True)


async def _start_in(conn, werkgebied_id: str, deelvraag_id: str, actor: str):
    """De rij van deze deelvraag; bestond ze niet, dan wordt ze `in_behandeling`. Onder het werkgebiedslot."""
    v = db.bronselectie_voortgang
    q = select(v).where(v.c.werkgebied_id == werkgebied_id, v.c.deelvraag_id == deelvraag_id)
    row = (await conn.execute(q.with_for_update())).first()
    if row is not None:
        return row, False
    nu = db.utcnow()
    await conn.execute(insert(v).values(werkgebied_id=werkgebied_id, deelvraag_id=deelvraag_id,
                                        status=Voortgang.in_behandeling.value, fase=Fase.kern.value,
                                        open_punten=[], scope_stand="", revisie=1, gewijzigd_door=actor,
                                        gewijzigd=nu, geopend=nu))
    await _audit(conn, werkgebied_id, actor, "bronselectie-gestart", {"deelvraag": deelvraag_id})
    return (await conn.execute(q)).first(), True


async def zet_status(werkgebied_id: str, deelvraag_id: str, req: StatusActie, actor: str) -> None:
    """De stand van één deelvraag. Geeft niets terug: de router leest het overzicht ná de commit."""
    wg = await werkgebied_store.haal(werkgebied_id)
    _toets_deelvraag(wg, deelvraag_id)
    huidig = next(x for x in _per_vraag(wg, await _lees(wg)) if x["id"] == deelvraag_id)
    v = db.bronselectie_voortgang
    async with db.get_engine().begin() as conn:
        await _slot(conn, werkgebied_id)
        if req.actie == "openen":
            row, nieuw = await _start_in(conn, werkgebied_id, deelvraag_id, actor)
            if not nieuw:
                await conn.execute(update(v).where(v.c.werkgebied_id == werkgebied_id, v.c.deelvraag_id == deelvraag_id)
                                   .values(geopend=db.utcnow()))
            return
        row = (await conn.execute(select(v).where(v.c.werkgebied_id == werkgebied_id, v.c.deelvraag_id == deelvraag_id)
                                  .with_for_update())).first()
        status = row.status if row is not None else Voortgang.niet_gestart.value
        doel = {"afronden": Voortgang.voorlopig_afgerond.value, "beoordelen": Voortgang.beoordeeld.value,
                "heropenen": Voortgang.in_behandeling.value, "fase": status}[req.actie]
        punten = [p.model_dump() for p in req.open_punten] if req.open_punten is not None else None
        stand = huidig["_scope_nu"]
        # Al waar de actie heen wil: niets te doen, ook geen revisietoets (een dubbele klik is geen conflict).
        if row is not None and status == doel and (req.actie != "fase" or row.fase == req.fase.value) \
                and (punten is None or punten == (row.open_punten or [])) \
                and (req.actie not in ("afronden", "beoordelen") or row.scope_stand == stand):
            return
        if row is None:
            raise HTTPException(409, {"fout": "niet_gestart", "melding": "Begin eerst aan deze deelvraag."})
        werkgebied_store.toets_revisie(row.revisie, req.verwachte_revisie,
                                       melding="Iemand anders werkte intussen aan deze deelvraag; laad haar opnieuw.")
        toegestaan = {"afronden": (Voortgang.in_behandeling.value, Voortgang.voorlopig_afgerond.value),
                      "beoordelen": (Voortgang.in_behandeling.value, Voortgang.voorlopig_afgerond.value,
                                     Voortgang.beoordeeld.value),
                      "heropenen": KLAAR, "fase": (Voortgang.in_behandeling.value,)}[req.actie]
        if status not in toegestaan:
            melding = {"heropenen": "Deze deelvraag is nog niet afgerond.",
                       "fase": "Heropen de deelvraag eerst.",
                       "afronden": "Deze deelvraag is al beoordeeld; heropen haar eerst."}.get(req.actie, "")
            raise HTTPException(409, {"fout": "status", "status": status, "melding": melding})
        if req.actie == "beoordelen":
            redenen = list(huidig["beoordelen"]["redenen"])
            if punten is not None:
                redenen = [r for r in redenen if "onderzoekspunten" not in r] + (
                    ["Er staan nog onderzoekspunten open."] if punten else [])
            if redenen:
                raise HTTPException(409, {"fout": "poort", "redenen": redenen,
                                          "melding": " ".join(redenen) + " Rond de deelvraag voorlopig af, of "
                                                     "doorloop eerst de vragen en los de onderzoekspunten op."})
        waarden: dict = {"status": doel, "revisie": row.revisie + 1, "gewijzigd_door": actor,
                         "gewijzigd": db.utcnow()}
        if req.actie == "fase":
            waarden["fase"] = req.fase.value
        if req.actie in ("afronden", "beoordelen"):
            waarden["scope_stand"] = stand
            waarden["fase"] = Fase.afronden.value
        if punten is not None:
            waarden["open_punten"] = punten
        await conn.execute(update(v).where(v.c.werkgebied_id == werkgebied_id, v.c.deelvraag_id == deelvraag_id)
                           .values(**waarden))
        await _audit(conn, werkgebied_id, actor, f"bronselectie-{req.actie}",
                     {"deelvraag": deelvraag_id, "status": doel, "revisie": row.revisie + 1,
                      **({"fase": req.fase.value} if req.fase else {}),
                      **({"open_punten": len(punten)} if punten is not None else {})})


# --- besluiten per deelvraag -----------------------------------------------------------------

async def besluit(werkgebied_id: str, deelvraag_id: str, kandidaat_id: str, req: KandidaatBesluit, bron: dict,
                  actor: str) -> None:
    """Een besluit over één kandidaat bij één deelvraag. `bron` komt uit de resolver (alleen nodig als de
    bepaling nog niet in het werkgebied staat). Start de deelvraag als dat nog niet gebeurd was."""
    wg = await werkgebied_store.haal(werkgebied_id)
    _toets_deelvraag(wg, deelvraag_id)
    alleen = deelvraag_id == ANALYSEVRAAG
    k, b, kp, s = db.bron_kandidaten, db.bron_kandidaat_deelvragen, db.werkgebied_deelvraag_koppelingen, \
        db.werkgebied_bronselecties
    async with db.get_engine().connect() as conn:
        kd = (await conn.execute(select(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kandidaat_id))).first()
        if kd is None:
            raise HTTPException(404, "Kandidaat bestaat niet.")
        sid = (await conn.execute(select(s.c.id).where(s.c.werkgebied_id == werkgebied_id, s.c.bron_iri == kd.bron_iri,
                                                       s.c.verwijderd.is_(None)))).scalar()
        koppeling = None if alleen or not sid else (await conn.execute(select(kp).where(
            kp.c.deelvraag_id == deelvraag_id, kp.c.soort == "bron", kp.c.doel_id == sid))).first()
        rij = (await conn.execute(select(b).where(b.c.werkgebied_id == werkgebied_id, b.c.kandidaat_id == kandidaat_id,
                                                  b.c.deelvraag_id == deelvraag_id))).first()
    detail = {"deelvraag": deelvraag_id, "kandidaat": kandidaat_id, "bron_iri": kd.bron_iri}

    async def wis_besluit(conn) -> None:
        await conn.execute(delete(b).where(b.c.werkgebied_id == werkgebied_id, b.c.kandidaat_id == kandidaat_id,
                                           b.c.deelvraag_id == deelvraag_id))

    if req.besluit == "opnemen":
        if kd.status == "uitgesloten":
            raise HTTPException(409, {"fout": "status", "status": "uitgesloten",
                                      "melding": "Deze bepaling is voor het hele werkgebied uitgesloten; heropen haar eerst."})
        if sid is None:
            # Nog niet in het werkgebied: opnemen zoals altijd, gekoppeld aan alleen deze deelvraag.
            await bronnen_run_store.opnemen(
                werkgebied_id, kandidaat_id,
                Opnemen(verwachte_revisie=req.verwachte_revisie, rol=req.rol, reden=req.reden), bron, actor,
                deelvraag_ids=[] if alleen else [deelvraag_id], koppel_rol=req.rol or "", binnen=wis_besluit)
        elif not alleen:
            await _koppel(werkgebied_id, deelvraag_id, sid, req.rol or "", req.verwachte_revisie, actor, detail,
                          koppeling, binnen=wis_besluit)
    elif req.besluit == "loskoppelen":
        if alleen:
            raise HTTPException(422, {"fout": "geen_deelvraag",
                                      "melding": "Zonder deelvragen haal je een bron weg op de tab Bronnen."})
        if koppeling is not None:
            async with _gewijzigd(werkgebied_id, req.verwachte_revisie, actor, "bronselectie-losgekoppeld",
                                  detail) as (conn, _):
                await conn.execute(delete(kp).where(kp.c.deelvraag_id == deelvraag_id, kp.c.soort == "bron",
                                                    kp.c.doel_id == sid))
    elif req.besluit == "uitsluiten":
        if koppeling is not None or (alleen and sid):
            raise HTTPException(409, {"fout": "status", "status": "opgenomen",
                                      "melding": "Deze bepaling is bij deze deelvraag opgenomen; koppel haar eerst los."})
        naar = "uitgesloten"
        reden = req.reden.strip()
        async with db.get_engine().begin() as conn:
            await _slot(conn, werkgebied_id)
            if alleen or (req.overal and naar == "uitgesloten"):
                if kd.status != naar or kd.reden != reden:
                    nu = db.utcnow()
                    await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kandidaat_id)
                                       .values(status=naar, reden=reden, besloten_door=actor, besloten_op=nu,
                                               gewijzigd=nu))
                    await _audit(conn, werkgebied_id, actor, f"kandidaat-{naar}",
                                 {**detail, **({"reden": reden} if reden else {})})
            elif rij is None or rij.status != naar or rij.reden != reden:
                await wis_besluit(conn)
                await conn.execute(insert(b).values(werkgebied_id=werkgebied_id, kandidaat_id=kandidaat_id,
                                                    deelvraag_id=deelvraag_id, status=naar, reden=reden,
                                                    besloten_door=actor, besloten_op=db.utcnow()))
                await _audit(conn, werkgebied_id, actor, f"bronselectie-{naar}",
                             {**detail, **({"reden": reden} if reden else {})})
    elif req.besluit == "heropenen":
        async with db.get_engine().begin() as conn:
            await _slot(conn, werkgebied_id)
            if rij is not None:
                await wis_besluit(conn)
                await _audit(conn, werkgebied_id, actor, "bronselectie-heropend", detail)
            if (alleen or req.overal) and kd.status == "uitgesloten":
                await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kandidaat_id)
                                   .values(status="voorgesteld", reden="", besloten_door=None, besloten_op=None,
                                           gewijzigd=db.utcnow()))
                await _audit(conn, werkgebied_id, actor, "kandidaat-voorgesteld", detail)
    # Wie over een kandidaat beslist, werkt aan deze deelvraag.
    async with db.get_engine().begin() as conn:
        await _slot(conn, werkgebied_id)
        await _start_in(conn, werkgebied_id, deelvraag_id, actor)


async def _koppel(werkgebied_id: str, deelvraag_id: str, sid: str, rol: str, verwacht: int, actor: str,
                  detail: dict, koppeling, binnen=None) -> None:
    """Een bronselectie die al in het werkgebied staat aan deze deelvraag koppelen, met haar rol hier. Dezelfde
    koppeling met dezelfde rol nog eens: niets, ook geen revisie."""
    if koppeling is not None and (not rol or (koppeling.rol or "") == rol):
        return
    kp = db.werkgebied_deelvraag_koppelingen
    async with _gewijzigd(werkgebied_id, verwacht, actor, "bronselectie-opgenomen", {**detail, "rol": rol}) as (conn, _):
        await conn.execute(delete(kp).where(kp.c.deelvraag_id == deelvraag_id, kp.c.soort == "bron", kp.c.doel_id == sid))
        await conn.execute(insert(kp).values(deelvraag_id=deelvraag_id, soort="bron", doel_id=sid, rol=rol,
                                             gekoppeld_door=actor, gekoppeld=db.utcnow()))
        if binnen is not None:
            await binnen(conn)


async def noem(werkgebied_id: str, deelvraag_id: str, req, bron: dict, actor: str) -> None:
    """Een bepaling die de analist zelf noemt, als **voorstel** bij één deelvraag: in het paneel naast de voorstellen
    van Lex, met de wettekst en *Opnemen* / *Uitsluiten* (4 nov 2026: het paneel beslist, ook hierover). Het bewijs is
    `genoemd`, met de deelvraag en de tekst zoals de analist hem typte; zo'n voorstel vervalt niet bij een nieuwe
    zoekopdracht. Idempotent: dezelfde bepaling bij dezelfde deelvraag nog eens verandert niets. Een uitsluiting bij
    deze deelvraag vervalt (de analist vraagt er opnieuw om); al opgenomen of werkgebiedbreed uitgesloten: 409.
    De deelvraag is daarna in behandeling. `bron` komt uit de resolver."""
    wg = await werkgebied_store.haal(werkgebied_id)
    _toets_deelvraag(wg, deelvraag_id)
    k, b = db.bron_kandidaten, db.bron_kandidaat_deelvragen
    iri, kid = bron["bron_iri"], bronnen_run_store.kandidaat_id(bron["bron_iri"])
    bewijs = {"methode": "genoemd", "vanuit": "", "detail": {"deelvraag_id": deelvraag_id, "tekst": req.tekst.strip(),
                                                             "door": actor}}
    async with db.get_engine().begin() as conn:
        await _slot(conn, werkgebied_id)
        s, kp = db.werkgebied_bronselecties, db.werkgebied_deelvraag_koppelingen
        sid = (await conn.execute(select(s.c.id).where(s.c.werkgebied_id == werkgebied_id, s.c.bron_iri == iri,
                                                       s.c.verwijderd.is_(None)))).scalar()
        hier = sid is not None and (deelvraag_id == ANALYSEVRAAG or (await conn.execute(select(kp.c.doel_id).where(
            kp.c.deelvraag_id == deelvraag_id, kp.c.soort == "bron", kp.c.doel_id == sid))).first() is not None)
        if hier:
            raise HTTPException(409, {"fout": "status", "status": "opgenomen",
                                      "melding": "Deze bepaling is bij deze deelvraag al opgenomen."})
        oud = (await conn.execute(select(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kid))).first()
        if oud is not None and oud.status == "uitgesloten":
            raise HTTPException(409, {"fout": "status", "status": "uitgesloten",
                                      "melding": "Deze bepaling is voor het hele werkgebied uitgesloten; heropen haar eerst."})
        nu = db.utcnow()
        if oud is None:
            await conn.execute(insert(k).values(werkgebied_id=werkgebied_id, id=kid, bron_iri=iri, label=bron.get("label") or "",
                                                bwb_id=bron.get("bwb_id") or "", rol=req.rol, bewijs=[bewijs], run_id="",
                                                status="voorgesteld", reden="", voorgesteld=nu, gewijzigd=nu))
        else:
            eerder = [x for x in oud.bewijs or [] if not (x.get("methode") == "genoemd" and
                                                          (x.get("detail") or {}).get("deelvraag_id") == deelvraag_id)]
            rol = req.rol if ROL_VOLGORDE.get(req.rol, 9) < ROL_VOLGORDE.get(oud.rol, 9) else oud.rol
            await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kid)
                               .values(bewijs=[*eerder, bewijs], rol=rol, gewijzigd=nu))
        await conn.execute(delete(b).where(b.c.werkgebied_id == werkgebied_id, b.c.kandidaat_id == kid,
                                           b.c.deelvraag_id == deelvraag_id))
        await _audit(conn, werkgebied_id, actor, "kandidaat-genoemd", {"deelvraag": deelvraag_id, "bron_iri": iri,
                                                                       "rol": req.rol})
        await _start_in(conn, werkgebied_id, deelvraag_id, actor)


async def erf_in(conn, werkgebied_id: str, oud_id: str, nieuw_id: str) -> None:
    """Een verbetering van een deelvraag overgenomen: de opvolger erft de voortgang en de besluiten. De
    `scope_stand` blijft die van de oude tekst, dus een afronding staat daarna op *opnieuw bekijken*."""
    v, b = db.bronselectie_voortgang, db.bron_kandidaat_deelvragen
    oud = (await conn.execute(select(v).where(v.c.werkgebied_id == werkgebied_id, v.c.deelvraag_id == oud_id))).first()
    al = (await conn.execute(select(v.c.deelvraag_id).where(v.c.werkgebied_id == werkgebied_id,
                                                            v.c.deelvraag_id == nieuw_id))).first()
    if oud is not None and al is None:
        await conn.execute(insert(v).values({**oud._asdict(), "deelvraag_id": nieuw_id}))
    bestaand = set((await conn.execute(select(b.c.kandidaat_id).where(
        b.c.werkgebied_id == werkgebied_id, b.c.deelvraag_id == nieuw_id))).scalars())
    for r in (await conn.execute(select(b).where(b.c.werkgebied_id == werkgebied_id, b.c.deelvraag_id == oud_id))).all():
        if r.kandidaat_id not in bestaand:
            await conn.execute(insert(b).values({**r._asdict(), "deelvraag_id": nieuw_id}))
