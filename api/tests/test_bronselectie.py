"""De bronselectie per deelvraag (spoor J): voortgang, besluiten per deelvraag, de volgende deelvraag en
het overzicht. Het scenario uit de opdracht staat hier op api-niveau: vier deelvragen, van 1 naar 2, naar 4
springen, en de voortgang van 2 blijft staan."""
from __future__ import annotations

from app import bronselectie, db
from sqlalchemy import select
from gedeelde_bron import ART, ONE, TWO
from test_bronnen_runs import LID3, _start, _uitkomst
from test_werkgebied_deelvragen import _dv, _patch
from gedeelde_bron import ART2, _nieuw, client, database, graaf  # noqa: F401

VRAGEN = ["Welke algemene betalingstermijn geldt?", "Welke termijnen gelden voor voorlopige aanslagen?",
          "Welke afwijkende betalingstermijnen bestaan er?", "Wanneer wordt iedere afzonderlijke termijn invorderbaar?"]


def _kd(iri: str, rol: str, *, deelvragen=(), vanuit: str = "", methode: str = "") -> dict:
    bewijs = [{"methode": "deelvraag", "vanuit": "", "detail": {"deelvraag_id": d, "vraag": "…"}} for d in deelvragen]
    if vanuit or methode:
        bewijs.append({"methode": methode or "verwijzing_uit", "vanuit": vanuit, "detail": {}})
    return {"bron_iri": iri, "label": iri.rsplit(":", 1)[-1], "rol": rol, "bwb_id": iri.split(":")[2], "bewijs": bewijs}


async def _vier(client):
    wg = await _nieuw(client)
    for v in VRAGEN:
        wg = await _dv(client, wg, v)
    return wg, [d["id"] for d in wg["deelvragen"]]


async def _met_kandidaten(client, wg, kandidaten, **extra):
    run = await _start(client, wg, 201)
    r = await _uitkomst(client, wg, run, kandidaten, **extra)
    assert r.status_code == 200, r.text


async def _overzicht(client, wg, **params) -> dict:
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/bronselectie", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def _status(client, wg, did, actie, verwacht=200, **velden) -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronselectie/{did}/status", json={"actie": actie, **velden})
    assert r.status_code == verwacht, r.text
    return r.json()


async def _besluit(client, wg, did, kid, besluit, verwacht=200, **velden) -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronselectie/{did}/kandidaten/{kid}",
                          json={"besluit": besluit, **velden})
    assert r.status_code == verwacht, r.text
    return r.json()


def _dq(ov, did) -> dict:
    return next(d for d in ov["deelvragen"] if d["id"] == did)


def _kid(dq, iri) -> dict:
    return next(k for k in dq["kandidaten"] if k["bron_iri"] == iri)


async def test_vier_deelvragen_van_1_naar_2_springen_naar_4_en_2_blijft_staan(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]), _kd(ONE, "kern", deelvragen=[ids[1]]),
                                       _kd(ART2, "kern", deelvragen=[ids[3]])])
    ov = await _overzicht(client, wg)
    assert ov["modus"] == "deelvragen" and [d["nr"] for d in ov["deelvragen"]] == [1, 2, 3, 4]
    assert {d["status"] for d in ov["deelvragen"]} == {"niet_gestart"}
    assert (ov["actief"], ov["volgende"]) == (None, ids[0])

    # Deelvraag 1: openen, de kandidaat opnemen, voorlopig afronden → de code stelt 2 voor.
    ov = await _status(client, wg, ids[0], "openen")
    assert (ov["actief"], _dq(ov, ids[0])["status"]) == (ids[0], "in_behandeling")
    k1 = _kid(_dq(ov, ids[0]), ART)
    assert (k1["stand"], k1["bewijs_soorten"]) == ("voorgesteld", ["tekst"])
    ov = await _besluit(client, wg, ids[0], k1["id"], "opnemen", verwachte_revisie=ov["revisie"])
    assert _kid(_dq(ov, ids[0]), ART)["stand"] == "opgenomen"
    ov = await _status(client, wg, ids[0], "afronden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    assert _dq(ov, ids[0])["status"] == "voorlopig_afgerond" and ov["volgende"] == ids[1]

    # Deelvraag 2: het kernkaartje beantwoorden zonder iets aan te vinken – dan is het voorstel niet gekozen.
    ov = await _status(client, wg, ids[1], "openen")
    assert _kid(_dq(ov, ids[1]), ONE)["stand"] == "voorgesteld"
    ov = await _status(client, wg, ids[1], "fase", fase="afhankelijkheden", verwachte_revisie=_dq(ov, ids[1])["revisie"])
    assert _kid(_dq(ov, ids[1]), ONE)["stand"] == "niet_gekozen" and _dq(ov, ids[1])["telling"]["niet_gekozen"] == 1

    # Springen naar 4 zonder 2 af te ronden.
    ov = await _status(client, wg, ids[3], "openen")
    assert ov["actief"] == ids[3]
    assert _dq(ov, ids[1])["status"] == "in_behandeling" and _kid(_dq(ov, ids[1]), ONE)["stand"] == "niet_gekozen"
    # De vragen opnieuw doorlopen maakt er weer een keuze van.
    terug = await _status(client, wg, ids[1], "fase", fase="kern", verwachte_revisie=_dq(ov, ids[1])["revisie"])
    assert _kid(_dq(terug, ids[1]), ONE)["stand"] == "voorgesteld"
    ov = await _status(client, wg, ids[3], "openen")
    # Na 4 komt de eerste die niet klaar is: vooraan verder, en 1 is klaar → 2.
    assert ov["volgende"] == ids[1]

    # Herladen = opnieuw lezen: alles staat er nog, ook vanuit een ander gesprek of een collega.
    later = await _overzicht(client, wg)
    assert later["actief"] == ids[3] and _dq(later, ids[0])["klaar"]
    assert [b["bron_iri"] for b in _dq(later, ids[0])["bronnen"]] == [ART]


async def test_zonder_deelvragen_is_de_analysevraag_het_vertrekpunt(client):
    wg = await _nieuw(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", methode="overzicht")])
    ov = await _overzicht(client, wg)
    assert ov["modus"] == "analysevraag" and [d["id"] for d in ov["deelvragen"]] == ["analysevraag"]
    dq = ov["deelvragen"][0]
    assert dq["vraag"] == "Wanneer?" and [k["bron_iri"] for k in dq["kandidaten"]] == [ART]
    await _status(client, wg, "analysevraag", "openen")
    ov = await _besluit(client, wg, "analysevraag", dq["kandidaten"][0]["id"], "opnemen", verwachte_revisie=wg["revisie"])
    dq = ov["deelvragen"][0]
    assert [b["bron_iri"] for b in dq["bronnen"]] == [ART] and not dq["beoordelen"]["mag"]
    ov = await _status(client, wg, "analysevraag", "fase", fase="afronden", verwachte_revisie=dq["revisie"])
    dq = ov["deelvragen"][0]
    assert dq["beoordelen"]["mag"]
    ov = await _status(client, wg, "analysevraag", "beoordelen", verwachte_revisie=dq["revisie"])
    assert ov["deelvragen"][0]["status"] == "beoordeeld" and ov["alle_klaar"] and ov["volgende"] is None
    # Met deelvragen bestaat de analysevraag als eenheid niet meer.
    await _dv(client, ov | {"id": wg["id"], "revisie": ov["revisie"]}, VRAGEN[0])
    await _status(client, wg, "analysevraag", "openen", verwacht=409)


async def test_een_bron_bij_twee_deelvragen_is_een_selectie_met_een_rol_per_deelvraag(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0], ids[2]])])
    ov = await _overzicht(client, wg)
    kid = _kid(_dq(ov, ids[0]), ART)["id"]
    ov = await _besluit(client, wg, ids[0], kid, "opnemen", verwachte_revisie=ov["revisie"], rol="analyseren")
    # Bij 3 is hij nog een voorstel, wel al in het werkgebied.
    k3 = _kid(_dq(ov, ids[2]), ART)
    assert (k3["stand"], k3["elders_opgenomen"]) == ("voorgesteld", True)
    ov = await _besluit(client, wg, ids[2], kid, "opnemen", verwachte_revisie=ov["revisie"], rol="context")
    assert [b["rol"] for b in _dq(ov, ids[0])["bronnen"]] == ["analyseren"]
    assert [b["rol"] for b in _dq(ov, ids[2])["bronnen"]] == ["context"]
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    assert [b["bron_iri"] for b in wg["bronnen"]] == [ART]                     # één selectie, geen duplicaat
    # Nog eens dezelfde klik: geen revisiesprong.
    ov2 = await _besluit(client, wg, ids[2], kid, "opnemen", verwachte_revisie=wg["revisie"], rol="context")
    assert ov2["revisie"] == wg["revisie"]
    # Loskoppelen bij 3 laat de selectie en de koppeling bij 1 staan.
    ov = await _besluit(client, wg, ids[2], kid, "loskoppelen", verwachte_revisie=wg["revisie"])
    assert _dq(ov, ids[2])["bronnen"] == [] and len(_dq(ov, ids[0])["bronnen"]) == 1


async def test_uitsluiten_bij_een_deelvraag_raakt_de_andere_niet_en_overal_wel(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0], ids[2]]),
                                       _kd(ONE, "kern", deelvragen=[ids[0], ids[2]])])
    ov = await _overzicht(client, wg)
    art, one = _kid(_dq(ov, ids[0]), ART)["id"], _kid(_dq(ov, ids[0]), ONE)["id"]
    await _besluit(client, wg, ids[0], art, "uitsluiten", verwacht=422)            # reden verplicht
    ov = await _besluit(client, wg, ids[0], art, "uitsluiten", reden="Gaat over aanslagen, niet over termijnen.")
    assert _kid(_dq(ov, ids[0]), ART)["stand"] == "uitgesloten"
    assert _kid(_dq(ov, ids[2]), ART)["stand"] == "voorgesteld"
    ov = await _besluit(client, wg, ids[0], one, "uitsluiten", reden="Buiten de afbakening.", overal=True)
    assert all(_kid(_dq(ov, d), ONE)["stand"] == "uitgesloten" and _kid(_dq(ov, d), ONE)["overal"]
               for d in (ids[0], ids[2]))
    ov = await _besluit(client, wg, ids[0], art, "heropenen")
    assert _kid(_dq(ov, ids[0]), ART)["stand"] == "voorgesteld"
    ov = await _besluit(client, wg, ids[2], one, "heropenen")
    assert _kid(_dq(ov, ids[2]), ONE)["stand"] == "uitgesloten"                 # werkgebiedbreed: alleen met overal
    ov = await _besluit(client, wg, ids[2], one, "heropenen", overal=True)
    assert _kid(_dq(ov, ids[0]), ONE)["stand"] == "voorgesteld"


async def test_beoordeeld_alleen_door_de_poort_en_een_dubbele_klik_is_geen_conflict(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    ov = await _status(client, wg, ids[0], "openen")
    rev = _dq(ov, ids[0])["revisie"]
    await _status(client, wg, ids[0], "afronden", verwacht=422)                 # zonder revisie
    r = await _status(client, wg, ids[0], "beoordelen", verwacht=409, verwachte_revisie=rev)
    assert r["detail"]["fout"] == "poort" and r["detail"]["redenen"] == [
        "De vragen bij deze deelvraag zijn nog niet doorlopen.", "Er is nog geen bron opgenomen bij deze deelvraag."]
    # Zonder bron om te analyseren is een deelvraag nog open (dekking): eerst opnemen.
    ov = await _overzicht(client, wg)
    ov = await _besluit(client, wg, ids[0], _kid(_dq(ov, ids[0]), ART)["id"], "opnemen", verwachte_revisie=ov["revisie"])
    rev = _dq(ov, ids[0])["revisie"]
    # Een onderzoekspunt is een open punt (lessenbundel 4) aan de deelvraag; de statusroute kent het oude veld niet meer.
    await _status(client, wg, ids[0], "afronden", verwacht=422, verwachte_revisie=rev,
                  open_punten=[{"tekst": "oud"}])
    punt = await client.post(f"/v1/werkgebieden/{wg['id']}/open-punten", json={"inhoud": {
        "soort": "onderzoekspunt", "vraag": "Bijzondere invorderbaarheid nog niet onderzocht.",
        "hangt_aan": [{"soort": "deelvraag", "id": ids[0]}]}})
    assert punt.status_code == 201, punt.text
    punt = punt.json()
    # Voorlopig afronden mag met open punten; een tweede klik met de oude revisie is geen 412.
    ov = await _status(client, wg, ids[0], "afronden", verwachte_revisie=rev)
    assert _dq(ov, ids[0])["status"] == "voorlopig_afgerond"
    assert _dq(ov, ids[0])["open_punten"] == [{"id": punt["id"], "tekst": "Bijzondere invorderbaarheid nog niet onderzocht.",
                                               "status": "open"}]
    ov = await _status(client, wg, ids[0], "afronden", verwachte_revisie=rev)
    rev = _dq(ov, ids[0])["revisie"]
    # Een opgenomen bron en geen onderzoekspunt: dan pas beoordeeld.
    assert _kid(_dq(ov, ids[0]), ART)["stand"] == "opgenomen"
    await _besluit(client, wg, ids[0], _kid(_dq(ov, ids[0]), ART)["id"], "later", verwacht=422)    # bestaat niet meer
    r = await _status(client, wg, ids[0], "beoordelen", verwacht=409, verwachte_revisie=rev)
    assert r["detail"]["redenen"] == ["Er staan nog onderzoekspunten open."]
    # Het punt oplossen (de keuze van de jurist, met de motivering hoe het verder gaat) haalt het uit de poort.
    b = await client.post(f"/v1/werkgebieden/{wg['id']}/open-punten/{punt['id']}/besluit",
                          json={"verwachte_revisie": 1, "motivering": "Valt buiten deze deelvraag."})
    assert b.status_code == 200, b.text
    ov = await _status(client, wg, ids[0], "beoordelen", verwachte_revisie=rev)
    assert _dq(ov, ids[0])["status"] == "beoordeeld" and _dq(ov, ids[0])["open_punten"] == []
    # Een collega met een oude stand krijgt 412.
    r = await _status(client, wg, ids[0], "heropenen", verwacht=412, verwachte_revisie=rev)
    assert r["detail"]["fout"] == "revisie_conflict"
    ov = await _status(client, wg, ids[0], "heropenen", verwachte_revisie=rev + 1)
    assert _dq(ov, ids[0])["status"] == "in_behandeling"
    await _status(client, wg, ids[1], "afronden", verwacht=409, verwachte_revisie=0)   # niet gestart


async def test_een_besluit_start_de_deelvraag_en_wordt_geaudit(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[1]])])
    ov = await _overzicht(client, wg)
    ov = await _besluit(client, wg, ids[1], _kid(_dq(ov, ids[1]), ART)["id"], "uitsluiten", reden="Niet bij deze vraag.")
    assert _dq(ov, ids[1])["status"] == "in_behandeling"
    acties = [a["actie"] for a in (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]]
    assert "bronselectie-uitgesloten" in acties and "bronselectie-gestart" in acties


async def test_een_oud_besluit_later_wordt_bij_het_opstarten_een_voorstel(client):
    """Er is geen *later* meer: `reconcile_schema` maakt van een oude rij een voorstel, en de code kent de waarde
    daarna niet meer."""
    from sqlalchemy import update
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.bron_kandidaten).where(db.bron_kandidaten.c.werkgebied_id == wg["id"])
                           .values(status="later", besloten_door="jurist-a"))
    await db.reconcile_schema()
    async with db.get_engine().connect() as conn:
        [status] = (await conn.execute(select(db.bron_kandidaten.c.status).where(
            db.bron_kandidaten.c.werkgebied_id == wg["id"]))).scalars().all()
    assert status == "voorgesteld"
    k = _kid(_dq(await _overzicht(client, wg), ids[0]), ART)
    assert (k["stand"], k["overal"]) == ("voorgesteld", False)


async def test_een_gewijzigde_scope_zet_een_afronding_op_opnieuw_bekijken(client):
    wg, ids = await _vier(client)
    ov = await _status(client, wg, ids[0], "openen")
    ov = await _status(client, wg, ids[0], "afronden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    assert _dq(ov, ids[0])["klaar"] and ov["volgende"] == ids[1]
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    wg = await _patch(client, wg, ids[0], vraag="Welke algemene betalingstermijn geldt voor een aanslag?")
    ov = await _overzicht(client, wg, na=ids[3])
    dq = _dq(ov, ids[0])
    assert (dq["status"], dq["opnieuw_bekijken"], dq["klaar"]) == ("voorlopig_afgerond", True, False)
    assert dq["opnieuw_reden"] == "tekst"
    assert ov["volgende"] == ids[0]                                         # vooraan verder: 1 telt weer
    r = await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": wg["revisie"], "afbakening": "Alleen IW 1990."})
    assert r.status_code == 200, r.text


async def test_een_verbeterde_deelvraag_erft_de_voortgang(client):
    wg, ids = await _vier(client)
    ov = await _status(client, wg, ids[0], "openen")
    await _status(client, wg, ids[0], "afronden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen/voorstellen",
                          json={"vragen": ["Welke betalingstermijn geldt voor een aanslag?"], "model": "t",
                                "vervangt": ids[0]})
    assert r.status_code == 200, r.text
    nieuw = r.json()["nieuw"][0]
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    wg = await _patch(client, wg, nieuw, status="actief")
    ov = await _overzicht(client, wg)
    assert ov["deelvragen"][0]["id"] == nieuw
    assert (ov["deelvragen"][0]["status"], ov["deelvragen"][0]["opnieuw_bekijken"]) == ("voorlopig_afgerond", True)


async def test_zoekdekking_meldt_een_afgekapte_methode(client):
    wg, ids = await _vier(client)
    ov = await _overzicht(client, wg)
    assert ov["zoekdekking"]["gezocht"] is False
    await _met_kandidaten(client, wg, [_kd(LID3, "aanverwant", methode="overzicht")],
                          meting={"deelvraag": {"aantal": 8, "volledig": False, "ms": 3},
                                  "verwijzing_uit": {"aantal": 0, "volledig": True, "ms": 1}})
    ov = await _overzicht(client, wg)
    z = ov["zoekdekking"]
    assert z["gezocht"] and not z["volledig"] and z["onvolledig"] == ["deelvraag"]
    # Wat bij geen enkele deelvraag hoort, valt niet stil weg.
    assert [k["bron_iri"] for k in ov["zonder_deelvraag"]] == [LID3]


async def test_een_afhankelijkheid_van_een_opgenomen_bron_hoort_bij_die_deelvraag(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]),
                                       _kd(ART2, "afhankelijkheid", vanuit=ART, methode="definitie")])
    ov = await _overzicht(client, wg)
    assert [k["bron_iri"] for k in _dq(ov, ids[0])["kandidaten"]] == [ART]
    ov = await _besluit(client, wg, ids[0], _kid(_dq(ov, ids[0]), ART)["id"], "opnemen", verwachte_revisie=ov["revisie"])
    k = _kid(_dq(ov, ids[0]), ART2)
    assert (k["rol"], k["bewijs_soorten"]) == ("afhankelijkheid", ["definitie"])
    assert all(ART2 not in [x["bron_iri"] for x in _dq(ov, d)["kandidaten"]] for d in ids[1:])


async def test_verwijderen_van_het_werkgebied_wist_de_voortgang(client):
    wg, ids = await _vier(client)
    await _status(client, wg, ids[0], "openen")
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    async with db.get_engine().connect() as conn:
        assert (await conn.execute(select(db.bronselectie_voortgang))).all() == []


def test_een_kaartje_van_de_bronselectie_houdt_zijn_deelvraag_en_de_intake_verandert_niet():
    from app.gesprek_contracts import Artefact, IntakeAntwoord, Vraagkaart

    basis = {"intake_id": "bs-wg1", "stap": "bs_bepalingen", "nr": 2, "totaal": 4, "vraag": "Welke bepalingen?"}
    k = Vraagkaart(**basis, modus="bronselectie", deelvraag_id="d2").model_dump()
    assert (k["modus"], k["deelvraag_id"]) == ("bronselectie", "d2")
    intake = Vraagkaart(intake_id="i1", stap="naam", nr=1, totaal=10, vraag="Hoe heet het?").model_dump()
    assert "deelvraag_id" not in intake
    assert IntakeAntwoord(intake_id="bs-wg1", stap="bs_kies", deelvraag_id="d1").model_dump()["deelvraag_id"] == "d1"
    assert "deelvraag_id" not in IntakeAntwoord(intake_id="i1", stap="naam").model_dump()
    assert Artefact(soort="bronselectie", ref={"werkgebied_id": "wg1"}).soort == "bronselectie"


async def _praktijk(client, wg, tekst: str) -> dict:
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    r = await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": wg["revisie"],
                                                                 "praktijkvoorbeeld": tekst})
    assert r.status_code == 200, r.text
    return r.json()


async def test_na_een_dossierwijziging_telt_alleen_wat_de_nieuwe_zoekopdracht_vond(client):
    """Een voorstel dat de nieuwe zoekopdracht niet meer vindt, verdwijnt; een besluit (uitgesloten) blijft."""
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]), _kd(ONE, "kern", deelvragen=[ids[0]]),
                                       _kd(ART2, "kern", deelvragen=[ids[0]])])
    ov = await _overzicht(client, wg)
    weg = _kid(_dq(ov, ids[0]), ART2)["id"]
    await _besluit(client, wg, ids[0], weg, "uitsluiten", reden="Buiten de afbakening.")
    wg = await _praktijk(client, wg, "Een ondernemer betaalt zijn aanslag te laat.")
    assert (await _overzicht(client, wg))["zoekdekking"]["verouderd"] is True
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]), _kd(LID3, "kern", deelvragen=[ids[0]])])
    ov = await _overzicht(client, wg)
    assert ov["zoekdekking"]["verouderd"] is False
    standen = {k["bron_iri"]: k["stand"] for k in _dq(ov, ids[0])["kandidaten"]}
    assert standen == {ART: "voorgesteld", LID3: "voorgesteld", ART2: "uitgesloten"}
    assert _dq(ov, ids[0])["telling"]["voorgesteld"] == 2
    lijst = {k["bron_iri"]: k for k in (await client.get(f"/v1/werkgebieden/{wg['id']}/kandidaten")).json()["kandidaten"]}
    assert lijst[ONE]["vervallen"] is True and lijst[ART]["vervallen"] is False


async def test_heen_en_terug_wijzigen_is_niet_verouderd(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    wg = await _praktijk(client, wg, "Een ondernemer betaalt te laat.")
    await _met_kandidaten(client, wg, [_kd(ONE, "kern", deelvragen=[ids[0]])])
    wg = await _praktijk(client, wg, "")
    # Dezelfde invoer als de eerste run, maar die is niet meer de nieuwste: Lex zoekt opnieuw.
    run = await _start(client, wg, 201)
    r = await _uitkomst(client, wg, run, [_kd(ART, "kern", deelvragen=[ids[0]])])
    assert r.status_code == 200, r.text
    ov = await _overzicht(client, wg)
    assert ov["zoekdekking"]["verouderd"] is False and ov["zoekdekking"]["run_id"] == run["id"]
    assert {k["bron_iri"] for k in _dq(ov, ids[0])["kandidaten"]} == {ART}


async def test_een_afronding_gaat_alleen_open_als_de_voorstellen_veranderen(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    ov = await _status(client, wg, ids[0], "openen")
    ov = await _status(client, wg, ids[0], "afronden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    assert _dq(ov, ids[0])["klaar"]
    wg = await _praktijk(client, wg, "Een tikfout in het voorbeeld.")
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])      # hetzelfde gevonden
    assert _dq(await _overzicht(client, wg), ids[0])["klaar"]
    wg = await _praktijk(client, wg, "Een ondernemer met een naheffingsaanslag.")
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]), _kd(ONE, "kern", deelvragen=[ids[0]])])
    dq = _dq(await _overzicht(client, wg), ids[0])
    assert (dq["status"], dq["opnieuw_bekijken"], dq["klaar"]) == ("voorlopig_afgerond", True, False)


async def test_de_uitkomst_van_een_ingehaalde_zoekopdracht_overschrijft_niets(client):
    wg, ids = await _vier(client)
    oud = await _start(client, wg, 201)
    wg = await _praktijk(client, wg, "Een ondernemer betaalt te laat.")
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    r = await _uitkomst(client, wg, oud, [_kd(ONE, "kern", deelvragen=[ids[0]])])  # komt te laat binnen
    assert r.status_code == 200 and r.json()["status"] == "klaar"
    ov = await _overzicht(client, wg)
    assert {k["bron_iri"] for k in _dq(ov, ids[0])["kandidaten"]} == {ART}
    assert ov["zoekdekking"]["verouderd"] is False


async def _noem(client, wg, did, iri, verwacht=200, **velden) -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronselectie/{did}/voorstellen",
                          json={"bron_iri": iri, **velden})
    assert r.status_code == verwacht, r.text
    return r.json()


async def test_een_zelf_genoemde_bepaling_is_een_voorstel_in_het_paneel(client):
    """4 nov 2026: wat de analist zelf noemt, staat als voorstel bij de deelvraag – naast die van Lex, en daar
    besluit hij. Het bewijs is `genoemd`; de deelvraag gaat in behandeling; nog eens noemen verandert niets."""
    wg, ids = await _vier(client)
    ov = await _noem(client, wg, ids[1], ONE, tekst="artikel 9 lid 1 Iw 1990")
    d = _dq(ov, ids[1])
    k = _kid(d, ONE)
    assert (k["stand"], k["rol"], k["bewijs_soorten"]) == ("voorgesteld", "kern", ["genoemd"])
    assert "bewijs" not in k and d["status"] == "in_behandeling"
    assert [x["bron_iri"] for x in _dq(ov, ids[0])["kandidaten"]] == [], "alleen bij de deelvraag waar het genoemd is"
    ov = await _noem(client, wg, ids[1], ONE)
    assert len(_dq(ov, ids[1])["kandidaten"]) == 1
    # Opnemen in het paneel, zoals elk voorstel; daarna nog eens noemen is 409 (staat er al).
    ov = await _besluit(client, wg, ids[1], k["id"], "opnemen", verwachte_revisie=ov["revisie"])
    assert _kid(_dq(ov, ids[1]), ONE)["stand"] == "opgenomen"
    await _noem(client, wg, ids[1], ONE, 409)
    audit = (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]
    assert any(a["actie"] == "kandidaat-genoemd" for a in audit)


async def test_een_genoemd_voorstel_vervalt_niet_en_overleeft_een_nieuwe_zoekopdracht(client):
    """Een zoekopdracht die de bepaling niet vindt, laat het genoemde voorstel staan; een die haar wel vindt, voegt
    haar bewijs toe zonder het genoemde te wissen. Na het fase-wisselen blijft het open (geen *niet gekozen*)."""
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    await _noem(client, wg, ids[0], ONE, rol="afhankelijkheid")
    wg = await _praktijk(client, wg, "Een ondernemer betaalt te laat.")
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    ov = await _overzicht(client, wg)
    assert {k["bron_iri"]: k["stand"] for k in _dq(ov, ids[0])["kandidaten"]} == {ART: "voorgesteld", ONE: "voorgesteld"}
    wg = await _praktijk(client, wg, "Een ondernemer betaalt veel te laat.")
    await _met_kandidaten(client, wg, [_kd(ONE, "kern", deelvragen=[ids[2]])])
    ov = await _overzicht(client, wg)
    k = _kid(_dq(ov, ids[0]), ONE)
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/kandidaten")
    [volledig] = [x for x in r.json()["kandidaten"] if x["bron_iri"] == ONE]
    assert sorted(b["methode"] for b in volledig["bewijs"]) == ["deelvraag", "genoemd"]
    assert k["rol"] == "kern" and ONE in [x["bron_iri"] for x in _dq(ov, ids[2])["kandidaten"]]
    ov = await _status(client, wg, ids[0], "fase", fase="afronden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    assert _kid(_dq(ov, ids[0]), ONE)["stand"] == "voorgesteld"
    # Werkgebiedbreed uitgesloten: noemen is 409.
    ov = await _besluit(client, wg, ids[0], k["id"], "uitsluiten", reden="Valt erbuiten.", overal=True)
    await _noem(client, wg, ids[1], ONE, 409)


async def test_het_overzicht_noemt_de_zoekvragen_maar_herhaalt_het_bewijs_niet(client):
    """Het bewijs per kandidaat, herhaald per deelvraag, maakte dit het grootste antwoord van de api. Wie het nodig heeft
    leest `GET …/kandidaten`; hier staan de soorten en de zoekvragen."""
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=ids[:2])])
    kandidaten = (await client.get(f"/v1/werkgebieden/{wg['id']}/kandidaten")).json()["kandidaten"]
    ov = await _overzicht(client, wg)
    k = _kid(_dq(ov, ids[0]), ART)
    assert "bewijs" not in k and k["bewijs_soorten"] and "_bewijzen" not in k
    assert k["zoekvragen"] == sorted(k["zoekvragen"])
    assert any(x["bewijs"] for x in kandidaten)


def test_zoekvragen_uit_het_bewijs():
    assert bronselectie.zoekvragen([{"detail": {"zoekvraag": "b"}}, {"detail": {"zoekvraag": "a"}}, {"detail": {"zoekvraag": "a"}},
                                    {"detail": {"zoekvraag": "x"}}, {"detail": None}, {}]) == ["a", "b"]


async def test_een_bronbesluit_bewaart_reden_besluiter_en_wie_voorstelde(client):
    """WA TRM H1 (8 nov 2026): het rapport schreef "Voorgesteld door Lex" bij bronnen die de jurist zelf koos, en de
    kandidaat droeg na opnemen een lege reden en `besloten_door: null`. Nu: de reden is wat de analist schreef (per
    deelvraag), wie besloot staat bij de deelvraag, en wie voorstelde volgt uit het bewijs."""
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0], ids[2]])])
    ov = await _noem(client, wg, ids[1], ONE, tekst="artikel 9 lid 1 Iw 1990")
    # Zelf genoemd, opgenomen zonder reden: geen verzonnen reden, wel de jurist als besluiter.
    ov = await _besluit(client, wg, ids[1], _kid(_dq(ov, ids[1]), ONE)["id"], "opnemen", verwachte_revisie=ov["revisie"])
    k = _kid(_dq(ov, ids[1]), ONE)
    assert (k["stand"], k["reden"], k["besloten_door"]) == ("opgenomen", "", "jurist-a")
    [b] = _dq(ov, ids[1])["bronnen"]
    assert (b["reden"], b["besloten_door"], b["voorgesteld_door"]) == ("", "jurist-a", "analist")
    # Een zoektreffer van Lex, opgenomen met reden bij deelvraag 1, en met een andere reden bij deelvraag 3.
    kid = _kid(_dq(ov, ids[0]), ART)["id"]
    ov = await _besluit(client, wg, ids[0], kid, "opnemen", verwachte_revisie=ov["revisie"], reden="de hoofdregel")
    ov = await _besluit(client, wg, ids[2], kid, "opnemen", verwachte_revisie=ov["revisie"], reden="ook hier nodig")
    assert _kid(_dq(ov, ids[0]), ART)["reden"] == "de hoofdregel"
    assert _kid(_dq(ov, ids[2]), ART)["reden"] == "ook hier nodig"
    assert [(b["reden"], b["voorgesteld_door"]) for b in _dq(ov, ids[2])["bronnen"]] == [("ook hier nodig", "lex")]
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    assert {b["bron_iri"]: b["voorgesteld_door"] for b in wg["bronnen"]} == {ONE: "analist", ART: "lex"}


async def test_een_lid_van_een_artikelkandidaat_is_apart_op_te_nemen(client):
    """WA TRM H1 (8 nov 2026): IW 9 kon alleen als heel artikel. Nu kiest `bron_iri` een lid of onderdeel van de
    kandidaat; het overzicht zegt welk deel, een lid onder een artikel dat hier al staat is 409, en een bepaling die
    niet onder de kandidaat valt 422."""
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0], ids[2]])])
    ov = await _overzicht(client, wg)
    kid = _kid(_dq(ov, ids[0]), ART)["id"]
    await _besluit(client, wg, ids[0], kid, "opnemen", 422, verwachte_revisie=ov["revisie"], bron_iri=ART2)
    ov = await _besluit(client, wg, ids[0], kid, "opnemen", verwachte_revisie=ov["revisie"], bron_iri=ONE)
    k = _kid(_dq(ov, ids[0]), ART)
    assert k["stand"] == "opgenomen" and [d["bron_iri"] for d in k["opgenomen_delen"]] == [ONE]
    assert [b["bron_iri"] for b in _dq(ov, ids[0])["bronnen"]] == [ONE]
    # Bij deelvraag 3 eerst het hele artikel; een lid erbij is dan dubbelop.
    ov = await _besluit(client, wg, ids[2], kid, "opnemen", verwachte_revisie=ov["revisie"])
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronselectie/{ids[2]}/kandidaten/{kid}",
                          json={"besluit": "opnemen", "verwachte_revisie": ov["revisie"], "bron_iri": TWO})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "valt_onder"
    # Een tweede lid bij deelvraag 1 mag, naast het eerste.
    ov = await _besluit(client, wg, ids[0], kid, "opnemen", verwachte_revisie=ov["revisie"], bron_iri=TWO)
    assert sorted(b["bron_iri"] for b in _dq(ov, ids[0])["bronnen"]) == [ONE, TWO]
    # Loskoppelen haalt alles van deze kandidaat bij deze deelvraag weg; de selecties en deelvraag 3 blijven.
    ov = await _besluit(client, wg, ids[0], kid, "loskoppelen", verwachte_revisie=ov["revisie"])
    assert _dq(ov, ids[0])["bronnen"] == [] and [b["bron_iri"] for b in _dq(ov, ids[2])["bronnen"]] == [ART]
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    assert sorted(b["bron_iri"] for b in wg["bronnen"]) == sorted([ONE, TWO, ART])


async def test_een_lid_als_selectie_weghalen_maakt_de_kandidaat_weer_een_voorstel(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    ov = await _overzicht(client, wg)
    kid = _kid(_dq(ov, ids[0]), ART)["id"]
    await _besluit(client, wg, ids[0], kid, "opnemen", verwachte_revisie=ov["revisie"], bron_iri=ONE)
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    [sel] = wg["bronnen"]
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}/bronnen/{sel['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    assert _kid(_dq(await _overzicht(client, wg), ids[0]), ART)["stand"] == "voorgesteld"


async def test_wat_een_latere_zoekopdracht_vindt_is_niet_ongezien_niet_gekozen(client):
    """Acceptatie 18 nov 2026: na *Klaar* bij de kernbepalingen zocht Lex opnieuw, en drie nieuwe kernkandidaten (en een
    voorstel dat kern werd) stonden meteen op *niet gekozen*, zonder dat de jurist ze ooit als kern zag. Alleen wat
    openstond toen de fase sloot, is niet gekozen; de rest blijft een voorstel tot de volgende fase sluit."""
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]),
                                       _kd(ART2, "afhankelijkheid", deelvragen=[ids[0]])])
    ov = await _status(client, wg, ids[0], "openen")
    ov = await _status(client, wg, ids[0], "fase", fase="afhankelijkheden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    assert {k["bron_iri"]: k["stand"] for k in _dq(ov, ids[0])["kandidaten"]} == {ART: "niet_gekozen", ART2: "voorgesteld"}

    # Een nieuwe zoekopdracht: ART2 is nu een kernbepaling, ONE is nieuw.
    wg = await _praktijk(client, wg, "Een ondernemer betaalt te laat.")
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]), _kd(ART2, "kern", deelvragen=[ids[0]]),
                                       _kd(ONE, "kern", deelvragen=[ids[0]])])
    ov = await _overzicht(client, wg)
    assert {k["bron_iri"]: k["stand"] for k in _dq(ov, ids[0])["kandidaten"]} == {
        ART: "niet_gekozen", ART2: "voorgesteld", ONE: "voorgesteld"}

    # De volgende fase sluit: wat toen openstond, is niet gekozen.
    ov = await _status(client, wg, ids[0], "fase", fase="afronden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    assert {k["stand"] for k in _dq(ov, ids[0])["kandidaten"]} == {"niet_gekozen"}
    # De vragen opnieuw doorlopen maakt er weer een keuze van.
    ov = await _status(client, wg, ids[0], "fase", fase="kern", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    assert {k["stand"] for k in _dq(ov, ids[0])["kandidaten"]} == {"voorgesteld"}


async def test_een_oude_rij_zonder_gezien_houdt_de_regel_van_de_fase(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    ov = await _status(client, wg, ids[0], "openen")
    v = db.bronselectie_voortgang
    async with db.get_engine().begin() as conn:
        await conn.execute(v.update().where(v.c.deelvraag_id == ids[0]).values(gezien=None))
    ov = await _status(client, wg, ids[0], "fase", fase="afhankelijkheden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    wg = await _praktijk(client, wg, "Een ondernemer betaalt te laat.")
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]), _kd(ONE, "kern", deelvragen=[ids[0]])])
    ov = await _overzicht(client, wg)
    assert {k["stand"] for k in _dq(ov, ids[0])["kandidaten"]} == {"niet_gekozen"}
    async with db.get_engine().connect() as conn:
        assert (await conn.execute(select(v.c.gezien).where(v.c.deelvraag_id == ids[0]))).scalar() is None


def test_gezien_bij_legt_vast_wat_openstond_toen_de_fase_sloot():
    huidig = {"kandidaten": [{"id": "a", "rol": "kern", "stand": "voorgesteld"},
                             {"id": "b", "rol": "afhankelijkheid", "stand": "voorgesteld"},
                             {"id": "c", "rol": "kern", "stand": "opgenomen"}]}
    open_, kern, alles = ({"kern": False, "rest": False}, {"kern": True, "rest": False}, {"kern": True, "rest": True})
    assert bronselectie.gezien_bij(huidig, {}, open_, kern) == {"kern": ["a"]}
    assert bronselectie.gezien_bij(huidig, {"kern": ["x"]}, kern, alles) == {"kern": ["x"], "rest": ["a", "b"]}
    assert bronselectie.gezien_bij(huidig, {"kern": ["x"], "rest": ["y"]}, alles, open_) == {}
    assert bronselectie.niet_gekozen("x", "kern", alles, {"rest": ["x"]})
    assert not bronselectie.niet_gekozen("x", "kern", kern, {"kern": []})
    assert bronselectie.niet_gekozen("x", "kern", kern, None)


async def test_een_zoekronde_voor_een_andere_deelvraag_heropent_een_afronding_niet(client):
    """Termijnen, 18 nov 2026: elke werkgebiedbrede zoekronde zette een beoordeelde deelvraag terug op *opnieuw
    bekijken*, ook als er voor haar niets nieuws te beslissen viel. Een voorstel voor een andere deelvraag, een
    afhankelijkheid via een bron, of een voorstel dat de nieuwste run niet meer vond, heropent niets."""
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    ov = await _status(client, wg, ids[0], "openen")
    ov = await _status(client, wg, ids[0], "afronden", verwachte_revisie=_dq(ov, ids[0])["revisie"])
    assert _dq(ov, ids[0])["klaar"]
    wg = await _praktijk(client, wg, "Een tweede zoekronde, voor deelvraag 2.")
    await _met_kandidaten(client, wg, [_kd(ONE, "kern", deelvragen=[ids[1]]),
                                       _kd(TWO, "afhankelijkheid", vanuit=ART)])
    assert _dq(await _overzicht(client, wg), ids[0])["klaar"]
    # Een nieuw voorstel voor deze deelvraag zelf heropent wel.
    wg = await _praktijk(client, wg, "Een derde zoekronde.")
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]), _kd(ONE, "kern", deelvragen=[ids[0]])])
    dq = _dq(await _overzicht(client, wg), ids[0])
    assert (dq["opnieuw_bekijken"], dq["klaar"]) == (True, False)
    assert dq["opnieuw_reden"] == "voorstel"


def test_een_onderdeel_van_een_id_bepaling_valt_onder_haar_artikel():
    """Een Leidraad-artikel draagt zijn onderdelen URL-gecodeerd in de IRI; per onderdeel opnemen gaf 422
    `niet_onder_kandidaat` (Termijnen, 18 nov 2026)."""
    art = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie1%2FCirculaire.divisie1.1%2FCirculaire.divisie1.1.2"
    assert bronselectie.onder(art + "%2FTekst%2FOnderdeel._10", art)
    assert bronselectie.onder("urn:bwb:BWBR0004770:artikel:24:lid:1", "urn:bwb:BWBR0004770:artikel:24")
    assert not bronselectie.onder(art + "0", art)                              # divisie 1.1.20 is geen deel van 1.1.2
    assert not bronselectie.onder("urn:bwb:BWBR0004770:artikel:240", "urn:bwb:BWBR0004770:artikel:24")
