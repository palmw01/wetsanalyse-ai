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


async def _begrip(client, wg, naam, eid=None, rol="duiding") -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen",
                          json={"inhoud": {"naam": naam, **DEF}, "element_ids": [eid] if eid else [], "rol": rol})
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


async def _beoordeel(client, wg, regel, oordeel="juist") -> dict:
    """Elk open voorbeeld beoordelen, via de eigen route (B4: de PATCH zet geen oordeel)."""
    for nr, v in enumerate(regel["inhoud"]["voorbeelden"], start=1):
        if v["oordeel"] == "open":
            r = await client.post(_url(wg, regel["id"], "voorbeelden", str(nr), "oordeel"),
                                  json={"verwachte_revisie": regel["revisie"], "oordeel": oordeel})
            assert r.status_code == 200, r.text
            regel = r.json()
    return regel


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

    # De poort zegt wat er openstaat, ook de dragers die nog niet beoordeeld zijn (B2).
    redenen = " ".join(regel["accorderen"]["redenen"])
    for stuk in ("Nog niet geaccordeerd: bepalen van het termijnbedrag, termijnbedrag, aantal termijnen",
                 "grondslag is nog niet beoordeeld", "2 dragende formuleringen zijn nog niet beoordeeld",
                 "geen beoordeeld voorbeeld"):
        assert stuk in redenen, redenen
    assert regel["signalen"] == []
    r = await client.post(_url(wg, regel["id"], "accorderen"), json={"verwachte_revisie": 1, "reden": "Getoetst"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "poort"

    # Begrippen accorderen, de grondslag beoordelen, een voorbeeld beoordelen: dan mag het.
    for eid in ids.values():
        await _keur_goed(eid)
    for x in b.values():
        await _accordeer_begrip(client, wg, (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/{x['id']}")).json())
    for d in regel["dragers"]:
        regel = (await client.patch(_url(wg, regel["id"], "dragers", d["id"]),
                                    json={"verwachte_revisie": regel["revisie"], "beoordeling": "akkoord"})).json()
    # Een oordeel in de PATCH telt niet: het voorbeeld is open tot iemand het beoordeelt (B4).
    met_vb = _inhoud(b, voorbeelden=[{"invoer": "bedrag 1200, aantal termijnen 12", "uitkomst": "100", "oordeel": "juist"}])
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                             "inhoud": met_vb})).json()
    assert regel["inhoud"]["voorbeelden"][0]["oordeel"] == "open"
    assert "Voorbeeld 1 is nog niet beoordeeld." in regel["accorderen"]["redenen"]
    regel = await _beoordeel(client, wg, regel)
    assert regel["accorderen"] == {"mag": True, "redenen": [], "vraagt": ["reden"]}
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


async def _klaar_voor_accorderen(client, wg, ids, b) -> dict:
    """Een regel waarvan alles beoordeeld is: begrippen geaccordeerd, grondslag akkoord, een beoordeeld voorbeeld."""
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    for eid in ids.values():
        await _keur_goed(eid)
    for x in b.values():
        await _accordeer_begrip(client, wg, (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/{x['id']}")).json())
    grond = regel["dragers"][0]
    regel = (await client.patch(_url(wg, regel["id"], "dragers", grond["id"]),
                                json={"verwachte_revisie": regel["revisie"], "beoordeling": "akkoord"})).json()
    met_vb = _inhoud(b, voorbeelden=[{"invoer": "1200 en 12", "uitkomst": "100"}])
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                             "inhoud": met_vb})).json()
    regel = await _beoordeel(client, wg, regel)
    assert regel["accorderen"]["mag"], regel["accorderen"]
    return regel


async def test_de_poort_telt_de_genomen_keuzes(client):
    """R3 (ADR-018 besluit 2 en 7.13): een open interpretatiekeuze of ontbrekend beleid op de regel of een van zijn
    gevallen houdt het accorderen tegen, en sinds 20 nov 2026 ook een open onderzoekspunt ("Ja, blokkeren"). Het besluit valt via de ene route van
    het open punt (lessenbundel 4), en dan mag het weer."""
    wg, ids, b = await _opzet(client)
    regel = await _klaar_voor_accorderen(client, wg, ids, b)
    punten = f"/v1/werkgebieden/{wg['id']}/open-punten"
    keuze = (await client.post(punten, json={"inhoud": {
        "soort": "interpretatiekeuze", "vraag": "Telt een gedeeltelijke betaling als termijn?",
        "hangt_aan": [{"soort": "geval", "id": regel["id"], "geval": "1"}],
        "lezingen": [{"label": "A", "omschrijving": "Ja"}, {"label": "B", "omschrijving": "Nee"}]}})).json()
    onderzoek = (await client.post(punten, json={"inhoud": {
        "soort": "onderzoekspunt", "vraag": "Wat zegt de Leidraad?", "hangt_aan": [{"soort": "regel", "id": regel["id"]}],
        "te_toetsen": [{"bronsoort": "beleid", "omschrijving": "Leidraad Invordering"}]}})).json()

    regel = (await client.get(_url(wg, regel["id"]))).json()
    assert regel["accorderen"] == {"mag": False, "vraagt": ["reden"], "redenen": [
        f"2 open punten zijn nog niet besloten: interpretatiekeuze {keuze['id'][:8]} (geval 1): Telt een gedeeltelijke "
        f"betaling als termijn; onderzoekspunt {onderzoek['id'][:8]}: Wat zegt de Leidraad."]}
    assert regel["open_punten"] == {"open": 2, "totaal": 2, "bij_voorganger": 0}
    r = await client.post(_url(wg, regel["id"], "accorderen"), json={"verwachte_revisie": regel["revisie"], "reden": "x"})
    assert r.status_code == 409 and "open punten zijn nog niet besloten" in r.json()["detail"]["melding"]
    # De punten op deze regel, ook die op een geval ervan.
    lijst = (await client.get(punten, params={"aan": "regel", "aan_id": regel["id"]})).json()
    assert {p["id"] for p in (lijst["open_punten"] if isinstance(lijst, dict) else lijst)} == {keuze["id"], onderzoek["id"]}

    # De jurist kiest; het onderzoekspunt houdt het accorderen nog tegen tot het ook besloten is (20 nov 2026).
    r = await client.post(f"{punten}/{keuze['id']}/besluit", json={"verwachte_revisie": keuze["revisie"], "gekozen": "B",
                                                                   "motivering": "Volgt uit lid 2.", "methode": "grammaticaal"})
    assert r.status_code == 200, r.text
    regel = (await client.get(_url(wg, regel["id"]))).json()
    assert regel["accorderen"]["redenen"] == [
        f"1 open punt is nog niet besloten: onderzoekspunt {onderzoek['id'][:8]}: Wat zegt de Leidraad."]
    assert regel["open_punten"] == {"open": 1, "totaal": 2, "bij_voorganger": 0}
    r = await client.post(f"{punten}/{onderzoek['id']}/besluit",
                          json={"verwachte_revisie": onderzoek["revisie"], "motivering": "De Leidraad zegt niets anders."})
    assert r.status_code == 200, r.text
    regel = (await client.get(_url(wg, regel["id"]))).json()
    assert regel["accorderen"] == {"mag": True, "redenen": [], "vraagt": ["reden"]}
    assert regel["open_punten"] == {"open": 0, "totaal": 2, "bij_voorganger": 0}
    r = await client.post(_url(wg, regel["id"], "accorderen"), json={"verwachte_revisie": regel["revisie"], "reden": "Getoetst"})
    assert r.status_code == 200 and r.json()["status"] == "geaccordeerd"


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
    # Een begrip rust altijd op een passage (#1760). De aanduiding van deze elementen is al van een ander begrip, dus
    # dragen ze deze twee als definitie.
    regel_b = await _begrip(client, wg, "bepalen van het aantal termijnen", ids["ar"], rol="definitie")
    jaar = await _begrip(client, wg, "jaar", ids["var"], rol="definitie")
    eerst = (await client.post(_url(wg), json={"inhoud": {
        "soort": "rekenregel", "regelbegrip_id": regel_b["id"], "uitvoer_begrip_id": b["in"]["id"],
        "invoer": [{"begrip_id": jaar["id"]}], "gevallen": [{"uitkomst": [{"soort": "begrip", "begrip_id": jaar["id"]}]}]},
        "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    daarna = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                                "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    h = (await client.get(_url(wg, "hierarchie"))).json()
    assert h["volgorde"] == [eerst["id"], daarna["id"]]
    assert h["pijlen"] == [{"van": eerst["id"], "naar": daarna["id"], "begrip_id": b["in"]["id"], "via": "invoer"}]
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

async def test_een_tussenresultaat_rust_op_dezelfde_afleidingsregel_als_zijn_regel(client):
    """#1760 en R1 wijzen naar hetzelfde: een tussenresultaat (koppelrol `afgeleid`) rust op de Afleidingsregel-markering,
    en de regel die het afleidt heeft die markering als grondslag. Het begrip rust op de annotatie, niet op het
    regelobject; de regel en het begrip ontmoeten elkaar in het element."""
    wg, ids, b = await _opzet(client)
    tussen = await _begrip(client, wg, "termijnbedrag vóór afronding", ids["ar"], rol="afgeleid")
    assert [k["rol"] for k in tussen["koppelingen"]] == ["afgeleid"]
    r = await client.post(_url(wg), json={"inhoud": {**_inhoud(b), "uitvoer_begrip_id": tussen["id"]},
                                          "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})
    assert r.status_code == 201, r.text
    assert r.json()["dragers"][0]["element_id"] == tussen["koppelingen"][0]["element_id"]
    # Op een passage die geen afleidingsregel is, weigert #1760 de rol `afgeleid`; de regel volgt dan de grondslagtoets.
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen",
                          json={"inhoud": {"naam": "x", **DEF}, "element_ids": [ids["rs"]], "rol": "afgeleid"})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "geen_afleidingsregel"


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


# --- de e2e-run van Termijnen, 20 nov 2026 ---------------------------------------------------------

def _twee_gevallen(b, **extra) -> dict:
    uit = [{"soort": "begrip", "begrip_id": b["in"]["id"]}]
    return {**_inhoud(b), "gevallen": [{"label": "a", "uitkomst": uit}, {"label": "b", "uitkomst": uit}], **extra}


async def test_de_poort_vraagt_per_geval_een_beoordeelde_grondslag(client):
    """B2: bij R1 ging de poort open na één van de drie grondslagen. Nu vraagt elk geval een beoordeelde, actuele
    grondslag; een grondslag zonder geval geldt voor de hele regel, met een signaal."""
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _twee_gevallen(b), "dragers": [
        {"element_id": ids["ar"], "rol": "grondslag", "geval": "a"},
        {"element_id": ids["var"], "rol": "grondslag", "geval": "b"}]})).json()
    a = next(d for d in regel["dragers"] if d["geval"] == "a")
    regel = (await client.patch(_url(wg, regel["id"], "dragers", a["id"]),
                                json={"verwachte_revisie": regel["revisie"], "beoordeling": "akkoord",
                                      "motivering": "Letterlijk op de plek van het anker."})).json()
    redenen = regel["accorderen"]["redenen"]
    assert "Geval b heeft nog geen beoordeelde, actuele grondslag." in redenen
    assert "1 dragende formulering is nog niet beoordeeld." in redenen
    assert next(d for d in regel["dragers"] if d["id"] == a["id"])["motivering"] == "Letterlijk op de plek van het anker."
    # De motivering staat in de revisie en de audit.
    [rev] = [x for x in (await client.get(_url(wg, regel["id"], "revisies"))).json()["revisies"]
             if x["actie"] == "drager-beoordeeld"]
    assert rev["detail"]["motivering"] == "Letterlijk op de plek van het anker."
    # Een grondslag voor de hele regel dekt elk geval, maar de regel noemt het.
    regel = (await client.post(_url(wg, regel["id"], "dragers"), json={
        "verwachte_revisie": regel["revisie"], "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    heel = next(d for d in regel["dragers"] if d["geval"] == "" and d["rol"] == "grondslag")
    regel = (await client.patch(_url(wg, regel["id"], "dragers", heel["id"]),
                                json={"verwachte_revisie": regel["revisie"], "beoordeling": "akkoord"})).json()
    assert not any("heeft nog geen beoordeelde" in x for x in regel["accorderen"]["redenen"])
    assert not any("rust alleen op een grondslag" in x for x in regel["signalen"])
    b_ = next(d for d in regel["dragers"] if d["geval"] == "b")
    regel = (await client.delete(_url(wg, regel["id"], "dragers", b_["id"]),
                                 params={"verwachte_revisie": regel["revisie"]})).json()
    assert not any("heeft nog geen beoordeelde" in x for x in regel["accorderen"]["redenen"])
    assert "Geval b rust alleen op een grondslag voor de hele regel: toets of die grondslag dit geval ook draagt." \
        in regel["signalen"]


async def test_een_voorwaarde_maakt_een_drager_en_een_afgewezen_drager_houdt_tegen(client):
    """B3: een markering in een voorwaarde wordt een drager, zodat ze beoordeeld wordt. B2: een voorwaarde die op een
    afgewezen drager rust, houdt het accorderen tegen."""
    wg, ids, b = await _opzet(client)
    inhoud = {**_inhoud(b), "gevallen": [{**_inhoud(b)["gevallen"][0], "voorwaarden": {
        "verband": "alle", "delen": [{"tekst": "het bedrag is niet negatief", "element_ids": [ids["rs"]]}]}}]}
    regel = (await client.post(_url(wg), json={"inhoud": inhoud,
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    assert {(d["element_id"], d["rol"]) for d in regel["dragers"]} == {(ids["ar"], "grondslag"), (ids["rs"], "voorwaarde")}
    v = next(d for d in regel["dragers"] if d["rol"] == "voorwaarde")
    regel = (await client.patch(_url(wg, regel["id"], "dragers", v["id"]),
                                json={"verwachte_revisie": regel["revisie"], "beoordeling": "afgewezen"})).json()
    assert any("rust op een afgewezen drager" in x for x in regel["accorderen"]["redenen"])
    # Een wijziging met een nieuwe markering in een voorwaarde maakt ook een drager.
    inhoud["gevallen"][0]["voorwaarden"]["delen"].append({"tekst": "de variabele", "element_ids": [ids["var"]]})
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                             "inhoud": inhoud})).json()
    assert (ids["var"], "voorwaarde") in {(d["element_id"], d["rol"]) for d in regel["dragers"]}


async def test_een_voorbeeld_beoordeel_je_apart(client):
    """B4: de PATCH zet geen oordeel; een oordeel gaat via de eigen route, met wie het gaf. Beoordeelt de maker zijn
    eigen voorbeeld, dan zegt de regel dat."""
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b, voorbeelden=[
        {"invoer": "1200 en 12", "uitkomst": "100", "oordeel": "juist"}]),
        "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    [v] = regel["inhoud"]["voorbeelden"]
    assert (v["oordeel"], v["door"], v["beoordeeld_door"]) == ("open", "jurist-a", "")
    r = await client.post(_url(wg, regel["id"], "voorbeelden", "2", "oordeel"),
                          json={"verwachte_revisie": regel["revisie"], "oordeel": "juist"})
    assert r.status_code == 404
    r = await client.post(_url(wg, regel["id"], "voorbeelden", "1", "oordeel"),
                          json={"verwachte_revisie": regel["revisie"], "oordeel": "juist", "besluit": "x"})
    assert r.status_code == 422, "een onbekend veld is een 422"
    r = await client.post(_url(wg, regel["id"], "voorbeelden", "1", "oordeel"),
                          json={"verwachte_revisie": regel["revisie"], "oordeel": "juist", "toelichting": "Klopt."})
    assert r.status_code == 200, r.text
    regel = r.json()
    [v] = regel["inhoud"]["voorbeelden"]
    assert (v["oordeel"], v["beoordeeld_door"], v["toelichting"]) == ("juist", "jurist-a", "Klopt.")
    assert "1 voorbeeld is beoordeeld door wie het maakte." in regel["signalen"]
    # Een PATCH met hetzelfde voorbeeld laat het oordeel staan; een gewijzigde uitkomst maakt het weer open.
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"], "inhoud": _inhoud(
        b, voorbeelden=[{"invoer": "1200 en 12", "uitkomst": "100", "toelichting": "Klopt."}])})).json()
    assert regel["inhoud"]["voorbeelden"][0]["oordeel"] == "juist"
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"], "inhoud": _inhoud(
        b, voorbeelden=[{"invoer": "1200 en 12", "uitkomst": "101", "oordeel": "juist"}])})).json()
    assert regel["inhoud"]["voorbeelden"][0]["oordeel"] == "open"


async def test_de_compacte_vorm_en_de_smalle_routes(client):
    """B1: een drager-PATCH gaf de hele regel terug (13k–53k tekens). `?vorm=kort` geeft de stand, en de dragers en de
    poort zijn apart te lezen."""
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    [d] = regel["dragers"]
    r = await client.patch(_url(wg, regel["id"], "dragers", d["id"]), params={"vorm": "kort"},
                           json={"verwachte_revisie": regel["revisie"], "beoordeling": "akkoord"})
    kort = r.json()
    assert set(kort) == {"id", "revisie", "status", "vervangen_door", "accorderen", "signalen", "open_punten", "drager"}
    assert kort["drager"]["beoordeling"] == "akkoord" and "bewijs" not in kort["drager"]
    assert kort["drager"]["tekst"] == "Alfa"
    dragers = (await client.get(_url(wg, regel["id"], "dragers"))).json()
    assert dragers["revisie"] == kort["revisie"] and [x["id"] for x in dragers["dragers"]] == [d["id"]]
    poort_ = (await client.get(_url(wg, regel["id"], "poort"))).json()
    assert poort_["accorderen"] == kort["accorderen"] and "gaten" in poort_ and "inhoud" not in poort_
    lijst = (await client.get(_url(wg), params={"vorm": "kort"})).json()["regels"]
    assert [x["id"] for x in lijst] == [regel["id"]] and "dragers" not in lijst[0]


async def test_vervangen_en_open_punten_omhangen(client):
    """A2: drie regels werden één beslistabel, maar hun open punten bleven aan de oude hangen, en de poort van de nieuwe
    zag ze niet. Afwijzen met een opvolger maakt de oude `vervangen`; de poort van de opvolger telt de open keuzes van
    de voorganger tot ze zijn omgehangen, en omhangen wijzigt alleen `hangt_aan`."""
    wg, ids, b = await _opzet(client)
    oud = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                            "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    nieuw = (await client.post(_url(wg), json={"inhoud": _twee_gevallen(b), "herkomst": "regelspecialist",
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    assert nieuw["herkomst"] == "regelspecialist"
    punten = f"/v1/werkgebieden/{wg['id']}/open-punten"
    keuze = (await client.post(punten, json={"inhoud": {
        "soort": "interpretatiekeuze", "vraag": "Geldt de termijn per termijn?", "hangt_aan": [{"soort": "regel", "id": oud["id"]}],
        "lezingen": [{"label": "A", "omschrijving": "Ja"}, {"label": "B", "omschrijving": "Nee"}],
        "toelichting": "Blijft staan bij omhangen."}})).json()

    r = await client.post(_url(wg, oud["id"], "afwijzen"), json={"verwachte_revisie": oud["revisie"], "reden": "x",
                                                                 "opvolger_id": oud["id"]})
    assert r.status_code == 422
    r = await client.post(_url(wg, oud["id"], "afwijzen"), json={"verwachte_revisie": oud["revisie"],
                                                                 "reden": "Samengevoegd", "opvolger_id": nieuw["id"]})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["vervangen_door"]) == ("vervangen", nieuw["id"])
    nieuw = (await client.get(_url(wg, nieuw["id"]))).json()
    assert nieuw["opvolger_van"] == oud["id"] and nieuw["open_punten"]["bij_voorganger"] == 1
    assert any("hangt nog aan de regel die deze vervangt" in x for x in nieuw["accorderen"]["redenen"])

    # Omhangen naar een geval dat de opvolger niet heeft: 422. Naar een geval dat hij wel heeft: alleen `hangt_aan`.
    r = await client.post(f"{punten}/{keuze['id']}/omhangen", json={
        "verwachte_revisie": keuze["revisie"], "hangt_aan": [{"soort": "geval", "id": nieuw["id"], "geval": "c"}]})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "geval_onbekend"
    r = await client.post(f"{punten}/{keuze['id']}/omhangen", json={
        "verwachte_revisie": keuze["revisie"], "hangt_aan": [{"soort": "geval", "id": nieuw["id"], "geval": "a"}]})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["inhoud"]["toelichting"] == "Blijft staan bij omhangen." and p["revisie"] == keuze["revisie"] + 1
    [rev] = [x for x in (await client.get(f"{punten}/{p['id']}/revisies")).json()["revisies"]
             if x["actie"] == "open-punt-omgehangen"]
    assert rev["detail"]["toen"][0]["id"] == oud["id"] and rev["detail"]["nu"][0]["geval"] == "a"
    nieuw = (await client.get(_url(wg, nieuw["id"]))).json()
    assert nieuw["open_punten"]["bij_voorganger"] == 0
    assert f"1 open punt is nog niet besloten: interpretatiekeuze {keuze['id'][:8]} (geval a): Geldt de termijn per " \
        "termijn." in nieuw["accorderen"]["redenen"]


def test_een_waarde_in_een_definitie():
    """C: `parameterwaarde_in_definitie` sloeg aan op elk cijfer, ook op "art. 9 lid 1"."""
    from app.regel_store import _noemt_waarde
    assert not _noemt_waarde("De termijn bedoeld in art. 9 lid 1 IW.", [])
    for tekst in ("Een termijn van zes weken.", "De termijn van 6 weken.", "Een bedrag van € 49.", "Een rente van 4%."):
        assert _noemt_waarde(tekst, []), tekst
    assert _noemt_waarde("De termijn van twee maanden na de dagtekening.", [])
    assert _noemt_waarde("Het drempelbedrag, nu 49 euro.", [])
    assert _noemt_waarde("De drempel van 49.", [{"waarde": "49", "eenheid": ""}])
    assert not _noemt_waarde("De drempel voor uitbetaling.", [{"waarde": "49", "eenheid": "euro"}])


def test_afgeleid_mag_op_elke_grondslagklasse():
    """A3: het regelbegrip van een beslisregel op een Rechtsbetrekking (R8) kon geen grondslag krijgen."""
    import pytest
    from fastapi import HTTPException

    from app.begrip_store import toets_afgeleid
    for klasse in ("Afleidingsregel", "Rechtsbetrekking", "Tijdsaanduiding"):
        toets_afgeleid([{"klasse": klasse}])
    with pytest.raises(HTTPException) as e:
        toets_afgeleid([{"klasse": "Rechtssubject"}])
    assert e.value.detail["fout"] == "geen_afleidingsregel"


async def test_een_gewijzigde_drager_houdt_tegen_en_ververs_je(client):
    """Vervolgronde 20 nov 2026: de poort stond open terwijl een drager op "gewijzigd" stond, en een drager verversen
    kon alleen door hem weg te halen en opnieuw toe te voegen. Nu houdt een gewijzigde dragende passage het accorderen
    tegen, en `…/verversen` zet het bewijs op de markering van nu."""
    wg, ids, b = await _opzet(client)
    regel = await _klaar_voor_accorderen(client, wg, ids, b)
    [d] = regel["dragers"]
    # De markering verandert (een andere klasse): de drager draagt het bewijs van toen.
    snap = snapshot()
    for soort, extra in (("heropen", {}), ("edit", {"wijziging": {"klasse": "Rechtsbetrekking"}})):
        view = await store.weergave(snap)
        revs = {l["bron_iri"]: l["revisie"] for l in view["lagen"]}
        await store.beslis(ids["ar"], Beslissing(type=soort, snapshot_id=snap["snapshot_id"], verwachte_revisies=revs,
                                                 **extra), snap, "jurist-a")
    regel = (await client.get(_url(wg, regel["id"]), params={"vorm": "stand"})).json()
    assert "dragers" not in regel, "vorm=stand is de compacte vorm"
    assert regel["accorderen"]["mag"] is False
    assert any("gewijzigd, verworpen of verdwenen: ververs" in x for x in regel["accorderen"]["redenen"])
    r = await client.post(_url(wg, regel["id"], "dragers", d["id"], "verversen"), params={"vorm": "kort"},
                          json={"verwachte_revisie": regel["revisie"], "beoordeling": "akkoord",
                                "motivering": "Nieuwe klasse gezien; draagt de regel nog."})
    assert r.status_code == 200, r.text
    kort = r.json()
    assert (kort["drager"]["actualiteit"], kort["drager"]["beoordeling"], kort["drager"]["klasse"]) == \
        ("actueel", "akkoord", "Rechtsbetrekking")
    assert kort["accorderen"]["mag"] is True, kort["accorderen"]
    # Nog eens hetzelfde verandert niets.
    r = await client.post(_url(wg, regel["id"], "dragers", d["id"], "verversen"),
                          json={"verwachte_revisie": kort["revisie"], "beoordeling": "akkoord"})
    assert r.json()["revisie"] == kort["revisie"]


async def test_open_punten_per_regel_en_een_te_lang_tekstdeel(client):
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    punten = f"/v1/werkgebieden/{wg['id']}/open-punten"
    await client.post(punten, json={"inhoud": {"soort": "onderzoekspunt", "vraag": "Elders?",
                                               "hangt_aan": [{"soort": "markering", "id": ids["rs"]}]}})
    hier = (await client.post(punten, json={"inhoud": {"soort": "onderzoekspunt", "vraag": "Hier?",
                                                       "hangt_aan": [{"soort": "regel", "id": regel["id"]}]}})).json()
    lijst = (await client.get(punten, params={"regel_id": regel["id"]})).json()["open_punten"]
    assert [p["id"] for p in lijst] == [hier["id"]]
    # De grens van een tekstdeel staat in het schema en in de melding.
    lang = _inhoud(b)
    lang["gevallen"][0]["uitkomst"][0]["tekst"] = "x" * 501
    r = await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"], "inhoud": lang})
    assert r.status_code == 422 and "hoogstens 500 tekens (dit deel heeft er 501)" in r.text
    from app.regel_contracts import Term
    assert Term.model_json_schema()["properties"]["tekst"]["maxLength"] == 500


async def test_een_onjuist_voorbeeld_houdt_tegen_met_nummers(client):
    """Vervolgronde 20 nov 2026: een onjuist voorbeeld was een signaal; de redenen noemden geen nummer, en er was geen
    smalle route op de voorbeelden. `motivering` bij accorderen gaf een 422."""
    wg, ids, b = await _opzet(client)
    regel = await _klaar_voor_accorderen(client, wg, ids, b)
    voorbeelden = [{"invoer": "1200 en 12", "uitkomst": "100"}, {"invoer": "0 en 12", "uitkomst": "0"},
                   {"invoer": "1200 en 0", "uitkomst": "deling door nul"}]
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                             "inhoud": _inhoud(b, voorbeelden=voorbeelden)})).json()
    assert "De voorbeelden 2 en 3 zijn nog niet beoordeeld." in regel["accorderen"]["redenen"]
    smal = (await client.get(_url(wg, regel["id"], "voorbeelden"))).json()
    assert [(v["nr"], v["oordeel"]) for v in smal["voorbeelden"]] == [(1, "juist"), (2, "open"), (3, "open")]
    assert smal["revisie"] == regel["revisie"] and "inhoud" not in smal
    for nr, oordeel in ((2, "juist"), (3, "onjuist")):
        regel = (await client.post(_url(wg, regel["id"], "voorbeelden", str(nr), "oordeel"),
                                   json={"verwachte_revisie": regel["revisie"], "oordeel": oordeel})).json()
    assert regel["accorderen"]["mag"] is False
    assert regel["accorderen"]["redenen"] == [
        "Voorbeeld 3 geeft een onjuiste uitkomst: pas de regel of het voorbeeld aan."]
    regel = (await client.post(_url(wg, regel["id"], "voorbeelden", "3", "oordeel"),
                               json={"verwachte_revisie": regel["revisie"], "oordeel": "kan_niet"})).json()
    assert regel["accorderen"] == {"mag": True, "redenen": [], "vraagt": ["reden"]}
    # `motivering` is hetzelfde veld als `reden`.
    r = await client.post(_url(wg, regel["id"], "accorderen"),
                          json={"verwachte_revisie": regel["revisie"], "motivering": "Getoetst aan lid 1."})
    assert r.status_code == 200 and r.json()["status"] == "geaccordeerd", r.text


async def test_het_oordeel_draagt_een_reden_en_een_keuze_moet_haar_geval_dragen(client):
    """Laatste ronde, 20 nov 2026: de oordeelroute nam geen grond aan, en een keuze op geval a waarvan de lezing op een
    markering rust die alleen geval b draagt, ging stil door."""
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _twee_gevallen(b, voorbeelden=[
        {"geval": "a", "invoer": "1200", "uitkomst": "100"}]), "dragers": [
        {"element_id": ids["ar"], "rol": "grondslag", "geval": "a"},
        {"element_id": ids["var"], "rol": "grondslag", "geval": "b"}]})).json()
    r = await client.post(_url(wg, regel["id"], "voorbeelden", "1", "oordeel"),
                          json={"verwachte_revisie": regel["revisie"], "oordeel": "juist", "motivering": "Nagerekend."})
    assert r.status_code == 200, r.text
    regel = r.json()
    v = regel["inhoud"]["voorbeelden"][0]
    assert (v["reden"], v["beoordeeld_door"]) == ("Nagerekend.", "jurist-a")
    assert (await client.get(_url(wg, regel["id"], "voorbeelden"))).json()["voorbeelden"][0]["reden"] == "Nagerekend."
    # Terug naar open wist de grond.
    regel = (await client.post(_url(wg, regel["id"], "voorbeelden", "1", "oordeel"),
                               json={"verwachte_revisie": regel["revisie"], "oordeel": "open"})).json()
    assert regel["inhoud"]["voorbeelden"][0]["reden"] == ""

    punten = f"/v1/werkgebieden/{wg['id']}/open-punten"
    p = (await client.post(punten, json={"inhoud": {
        "soort": "interpretatiekeuze", "vraag": "Geldt dit ook bij a?", "hangt_aan": [{"soort": "geval", "id": regel["id"], "geval": "a"}],
        "lezingen": [{"label": "A", "omschrijving": "Ja", "grondslag": [{"soort": "markering", "id": ids["var"]}]},
                     {"label": "B", "omschrijving": "Nee"}]}})).json()
    await client.post(f"{punten}/{p['id']}/besluit", json={"verwachte_revisie": 1, "gekozen": "A", "motivering": "x",
                                                         "methode": "systematisch"})
    regel = (await client.get(_url(wg, regel["id"]))).json()
    assert any("Keuze A is genomen voor geval a" in s and "dragen geval a niet" in s for s in regel["signalen"]), \
        regel["signalen"]
    # Draagt de markering van de lezing het geval wel (een drager voor de hele regel), dan geen signaal.
    regel = (await client.post(_url(wg, regel["id"], "dragers"), json={
        "verwachte_revisie": regel["revisie"], "dragers": [{"element_id": ids["var"], "rol": "invoer"}]})).json()
    assert not any("Keuze A is genomen" in s for s in regel["signalen"])


async def test_een_reden_aanvullen_houdt_het_moment_van_het_oordeel(client):
    """Laatste ronde, 20 nov 2026: wie een reden aanvulde, postte het oordeel opnieuw en `beoordeeld_op` schoof op."""
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b, voorbeelden=[{"invoer": "1200", "uitkomst": "100"}]),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    url = _url(wg, regel["id"], "voorbeelden", "1", "oordeel")
    regel = (await client.post(url, json={"verwachte_revisie": regel["revisie"], "oordeel": "juist",
                                          "reden": "Nagerekend."})).json()
    [v] = regel["inhoud"]["voorbeelden"]
    regel = (await client.post(url, json={"verwachte_revisie": regel["revisie"], "oordeel": "juist",
                                          "reden": "Ook getoetst aan lid 5.", "reden_aanvullen": True})).json()
    [na] = regel["inhoud"]["voorbeelden"]
    assert na["reden"] == "Nagerekend.\njurist-a: Ook getoetst aan lid 5."
    assert (na["beoordeeld_op"], na["beoordeeld_door"]) == (v["beoordeeld_op"], v["beoordeeld_door"])
    [rev] = [x for x in (await client.get(_url(wg, regel["id"], "revisies"))).json()["revisies"]][:1]
    assert rev["detail"]["reden_voor"] == "Nagerekend."
    # Een ander oordeel is een nieuw moment.
    regel = (await client.post(url, json={"verwachte_revisie": regel["revisie"], "oordeel": "onjuist", "reden": "x"})).json()
    assert regel["inhoud"]["voorbeelden"][0]["beoordeeld_op"] != v["beoordeeld_op"]
