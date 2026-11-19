"""Afleidingsregels in de api (ADR-018, R1): de grondslag, dragers met bewijsstand, de poort, revisies, de hiërarchie,
parameterwaarden en het wissen met het werkgebied."""
from __future__ import annotations

from sqlalchemy import func, select

from app import annotatie_v2_store as store, db
from app.annotatie_v2_contracts import Beslissing
from gedeelde_bron import ART, ONE, TWO, element, request, snapshot
from gedeelde_bron import _bron, _nieuw, client, database, graaf  # noqa: F401

DEF = {"definitie": "Een definitie.", "context": "Een toelichting."}


def _als(el: dict, klasse: str) -> dict:
    return {**el, "klasse": klasse}


async def _annoteer() -> dict[str, str]:
    """Lid 1 ("😀 Alfa Alfa"): een Afleidingsregel en een Variabele; lid 2 ("Beta"): een Rechtssubject."""
    snap = snapshot()
    uit = await store.batch(request(snap, [_als(element(snap, ONE, 2, 6), "Afleidingsregel"),
                                           _als(element(snap, ONE, 7, 11), "Variabele en variabelewaarde"),
                                           element(snap, TWO, 0, 4)]), snap, "lex")
    per = {(e["klasse"]): e["id"] for e in uit["elementen"]}
    return {"ar": per["Afleidingsregel"], "var": per["Variabele en variabelewaarde"], "rs": per["Rechtssubject"]}


async def _keur_goed(eid: str):
    snap = snapshot()
    view = await store.weergave(snap)
    revs = {l["bron_iri"]: l["revisie"] for l in view["lagen"]}
    await store.beslis(eid, Beslissing(type="approve", snapshot_id=snap["snapshot_id"], verwachte_revisies=revs),
                       snap, "jurist-a")


async def _begrip(client, wg, naam, eid=None) -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen",
                          json={"inhoud": {"naam": naam, **DEF}, "element_ids": [eid] if eid else [], "rol": "duiding"})
    assert r.status_code == 201, r.text
    return r.json()


async def _accordeer_begrip(client, wg, b):
    url = f"/v1/werkgebieden/{wg['id']}/begrippen/{b['id']}"
    for k in b["koppelingen"]:
        b = (await client.patch(f"{url}/koppelingen/{k['id']}",
                                json={"verwachte_revisie": b["revisie"], "beoordeling": "akkoord"})).json()
    r = await client.post(f"{url}/accorderen", json={"verwachte_revisie": b["revisie"], "reden": "Getoetst"})
    assert r.status_code == 200, r.text


async def _opzet(client):
    ids = await _annoteer()
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    begrippen = {"regel": await _begrip(client, wg, "bepalen van het termijnbedrag", ids["ar"]),
                 "uit": await _begrip(client, wg, "termijnbedrag", ids["var"]),
                 "in": await _begrip(client, wg, "aantal termijnen", ids["rs"])}
    return wg, ids, begrippen


def _inhoud(begrippen, **extra) -> dict:
    return {"soort": "rekenregel", "regelbegrip_id": begrippen["regel"]["id"], "uitvoer_begrip_id": begrippen["uit"]["id"],
            "lidwoord": "het", "invoer": [{"begrip_id": begrippen["in"]["id"]}],
            "gevallen": [{"uitkomst": [{"soort": "tekst", "tekst": "het bedrag gedeeld door het"},
                                       {"soort": "begrip", "begrip_id": begrippen["in"]["id"]}]}], **extra}


def _url(wg, *rest) -> str:
    return "/".join([f"/v1/werkgebieden/{wg['id']}/regels", *rest])


async def test_een_regel_zonder_grondslag_bestaat_niet(client):
    wg, ids, b = await _opzet(client)
    # Geen drager met rol grondslag.
    r = await client.post(_url(wg), json={"inhoud": _inhoud(b), "dragers": [{"element_id": ids["ar"], "rol": "context"}]})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "geen_grondslag"
    # Een Rechtssubject dat het uitvoerbegrip niet aanduidt, is geen grondslag.
    r = await client.post(_url(wg), json={"inhoud": _inhoud(b), "dragers": [{"element_id": ids["rs"], "rol": "grondslag"}]})
    assert r.status_code == 422 and r.json()["detail"]["element_ids"] == [ids["rs"]]
    # De passage die het afgeleide begrip aanduidt wel, ook al is ze geen Afleidingsregel (ADR-018 §2).
    r = await client.post(_url(wg), json={"inhoud": _inhoud(b), "dragers": [{"element_id": ids["var"], "rol": "grondslag"}]})
    assert r.status_code == 201, r.text
    # Een begrip dat niet in het werkgebied staat, kan de regel niet noemen.
    r = await client.post(_url(wg), json={"inhoud": _inhoud(b, uitvoer_begrip_id="bestaat-niet"),
                                          "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "begrip_onbekend"


async def test_van_aanmaken_tot_accorderen(client):
    wg, ids, b = await _opzet(client)
    r = await client.post(_url(wg), json={"inhoud": _inhoud(b), "herkomst": "lex",
                                          "dragers": [{"element_id": ids["ar"], "rol": "grondslag"},
                                                      {"element_id": ids["rs"], "rol": "invoer"}]})
    assert r.status_code == 201, r.text
    regel = r.json()
    assert (regel["status"], regel["revisie"], regel["herkomst"]) == ("concept", 1, "lex")
    assert regel["naam"] == "bepalen van het termijnbedrag" and regel["uitvoer"] == "termijnbedrag"
    assert regel["regeltekst"]["tekst"] == ("Het termijnbedrag moet berekend worden als het bedrag gedeeld door het "
                                            "aantal termijnen.")
    assert {d["rol"]: d["bewijs"]["tekst"] for d in regel["dragers"]} == {"grondslag": "Alfa", "invoer": "Beta"}
    assert {d["actualiteit"] for d in regel["dragers"]} == {"actueel"}

    # De poort zegt wat er openstaat.
    redenen = " ".join(regel["accorderen"]["redenen"])
    for stuk in ("Nog niet geaccordeerd: bepalen van het termijnbedrag, termijnbedrag, aantal termijnen",
                 "grondslag is nog niet beoordeeld", "geen beoordeeld voorbeeld"):
        assert stuk in redenen, redenen
    assert regel["signalen"] == ["1 andere dragende formulering is nog niet beoordeeld."]
    r = await client.post(_url(wg, regel["id"], "accorderen"), json={"verwachte_revisie": 1, "reden": "Getoetst"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "poort"

    # Begrippen accorderen, de grondslag beoordelen, een voorbeeld beoordelen: dan mag het.
    for eid in ids.values():
        await _keur_goed(eid)
    for x in b.values():
        await _accordeer_begrip(client, wg, (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/{x['id']}")).json())
    grond = next(d for d in regel["dragers"] if d["rol"] == "grondslag")
    regel = (await client.patch(_url(wg, regel["id"], "dragers", grond["id"]),
                                json={"verwachte_revisie": regel["revisie"], "beoordeling": "akkoord"})).json()
    met_vb = _inhoud(b, voorbeelden=[{"invoer": "bedrag 1200, aantal termijnen 12", "uitkomst": "100", "oordeel": "juist"}])
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                             "inhoud": met_vb})).json()
    assert regel["accorderen"] == {"mag": True, "redenen": []}
    r = await client.post(_url(wg, regel["id"], "accorderen"), json={"verwachte_revisie": regel["revisie"], "reden": ""})
    assert r.status_code == 409, "zonder reden geen akkoord"
    r = await client.post(_url(wg, regel["id"], "accorderen"),
                          json={"verwachte_revisie": regel["revisie"], "reden": "Getoetst"})
    assert r.status_code == 200, r.text
    regel = r.json()
    assert (regel["status"], regel["geaccordeerd_door"]) == ("geaccordeerd", "jurist-a")

    # Een wijziging maakt hem weer een concept; een oude revisie is 412.
    r = await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": 1, "inhoud": met_vb})
    assert r.status_code == 412
    beleid = {**met_vb, "brontype": "beleid"}
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                             "inhoud": beleid})).json()
    assert regel["status"] == "concept"
    regel = (await client.post(_url(wg, regel["id"], "accorderen"),
                               json={"verwachte_revisie": regel["revisie"], "reden": "Beleid getoetst"})).json()
    assert regel["status"] == "geaccordeerd_als_beleidsregel"

    # De revisies bewaren elke stand, de audit noemt de regel.
    revs = (await client.get(_url(wg, regel["id"], "revisies"))).json()["revisies"]
    assert [x["actie"] for x in revs][-1] == "regel-aangemaakt" and revs[0]["status"] == "geaccordeerd_als_beleidsregel"
    async with db.get_engine().connect() as conn:
        acties = (await conn.execute(select(db.werkgebied_audit.c.actie).where(
            db.werkgebied_audit.c.werkgebied_id == wg["id"]))).scalars().all()
    assert {"regel-aangemaakt", "drager-beoordeeld", "regel-gewijzigd", "regel-geaccordeerd"} <= set(acties)


async def test_de_laatste_grondslag_blijft(client):
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                               "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    [d] = regel["dragers"]
    r = await client.delete(_url(wg, regel["id"], "dragers", d["id"]), params={"verwachte_revisie": regel["revisie"]})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "laatste_grondslag"
    regel = (await client.post(_url(wg, regel["id"], "dragers"), json={
        "verwachte_revisie": regel["revisie"], "dragers": [{"element_id": ids["var"], "rol": "grondslag"}]})).json()
    r = await client.delete(_url(wg, regel["id"], "dragers", d["id"]), params={"verwachte_revisie": regel["revisie"]})
    assert r.status_code == 200 and len(r.json()["dragers"]) == 1


async def test_hierarchie_en_afwijzen(client):
    wg, ids, b = await _opzet(client)
    regel_b = await _begrip(client, wg, "bepalen van het aantal termijnen")
    jaar = await _begrip(client, wg, "jaar")
    eerst = (await client.post(_url(wg), json={"inhoud": {
        "soort": "rekenregel", "regelbegrip_id": regel_b["id"], "uitvoer_begrip_id": b["in"]["id"],
        "invoer": [{"begrip_id": jaar["id"]}], "gevallen": [{"uitkomst": [{"soort": "begrip", "begrip_id": jaar["id"]}]}]},
        "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    daarna = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                                "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    h = (await client.get(_url(wg, "hierarchie"))).json()
    assert h["volgorde"] == [eerst["id"], daarna["id"]]
    assert h["pijlen"] == [{"van": eerst["id"], "naar": daarna["id"], "begrip_id": b["in"]["id"]}]
    assert h["basisgegevens"] == [{"begrip_id": jaar["id"], "naam": "jaar"}]
    # Afwijzen bewaart de regel met de reden; hij doet niet meer mee in de keten.
    r = await client.post(_url(wg, eerst["id"], "afwijzen"), json={"verwachte_revisie": eerst["revisie"], "reden": ""})
    assert r.status_code == 422
    r = await client.post(_url(wg, eerst["id"], "afwijzen"),
                          json={"verwachte_revisie": eerst["revisie"], "reden": "Geen afleiding"})
    assert r.json()["status"] == "afgewezen"
    assert [x["id"] for x in (await client.get(_url(wg, "hierarchie"))).json()["regels"]] == [daarna["id"]]


async def test_het_overzicht_over_werkgebieden_heen(client):
    """`GET /v1/regels`, het overzicht in de zijbalk: zoeken in naam, uitvoer en regeltekst, filteren op status en
    werkgebied, *Door mij bewerkt*, en de tellers per status zonder het statusfilter."""
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    alles = (await client.get("/v1/regels")).json()
    rij = next(x for x in alles["resultaten"] if x["id"] == regel["id"])
    assert rij["naam"] == "bepalen van het termijnbedrag" and rij["uitvoer"] == "termijnbedrag"
    assert rij["werkgebied_id"] == wg["id"] and rij["werkgebied_naam"] == wg["naam"]
    assert rij["regeltekst"].startswith("Het termijnbedrag moet berekend worden als")
    assert alles["per_status"].get("concept", 0) >= 1
    # Zoeken in de regeltekst, met diakrieten en hoofdletters gelijk.
    assert [x["id"] for x in (await client.get("/v1/regels", params={"q": "GEDEELD aantal"})).json()["resultaten"]] == [regel["id"]]
    assert (await client.get("/v1/regels", params={"q": "bestaat-niet"})).json()["totaal"] == 0
    # Het statusfilter laat de tellers staan.
    geen = (await client.get("/v1/regels", params={"status": "geaccordeerd", "werkgebied_id": wg["id"]})).json()
    assert geen["totaal"] == 0 and geen["per_status"] == {"concept": 1}
    assert (await client.get("/v1/regels", params={"werkgebied_id": "onbekend"})).json()["totaal"] == 0
    assert regel["id"] in [x["id"] for x in (await client.get("/v1/regels", params={"mijn": "true"})).json()["resultaten"]]
    assert (await client.get("/v1/regels", params={"status": "onzin"})).status_code == 422


async def test_parameterwaarden_per_tijdvak(client):
    wg, _, b = await _opzet(client)
    url = f"/v1/werkgebieden/{wg['id']}/parameterwaarden"
    r = await client.post(url, json={"parameter_begrip_id": b["in"]["id"], "waarde": "6", "eenheid": "weken",
                                     "geldig_vanaf": "2026-10-01", "geldig_tot": "2025-01-01"})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "tijdvak"
    r = await client.post(url, json={"parameter_begrip_id": b["in"]["id"], "waarde": "6", "eenheid": "weken",
                                     "geldig_vanaf": "2025-01-01", "getoetst": "toestand 1 jan 2025 gelezen"})
    assert r.status_code == 201, r.text
    [w] = (await client.get(url)).json()["parameterwaarden"]
    assert (w["waarde"], w["eenheid"], w["geldig_tot"]) == ("6", "weken", "")
    assert (await client.delete(f"{url}/{w['id']}")).status_code == 200
    assert (await client.get(url)).json()["parameterwaarden"] == []


async def test_een_werkgebied_wissen_wist_zijn_regels(client):
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                               "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    async with db.get_engine().connect() as conn:
        for t, k in ((db.regels, "id"), (db.regel_revisies, "regel_id"), (db.regel_dragers, "regel_id")):
            assert (await conn.execute(select(func.count()).select_from(t).where(t.c[k] == regel["id"]))).scalar() == 0
