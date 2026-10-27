"""De bronselectie per deelvraag (spoor J): voortgang, besluiten per deelvraag, de volgende deelvraag en
het overzicht. Het scenario uit de opdracht staat hier op api-niveau: vier deelvragen, van 1 naar 2, naar 4
springen, en de voortgang van 2 blijft staan."""
from __future__ import annotations

from app import db
from sqlalchemy import select
from test_annotatie_v2 import ART, ONE
from test_bronnen_runs import LID3, _start, _uitkomst
from test_werkgebied_deelvragen import _dv, _koppel, _patch
from test_werkgebieden import ART2, _nieuw, client, database, graaf  # noqa: F401

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

    # Deelvraag 2: openen en de kandidaat voor later bewaren.
    ov = await _status(client, wg, ids[1], "openen")
    ov = await _besluit(client, wg, ids[1], _kid(_dq(ov, ids[1]), ONE)["id"], "later")
    assert _kid(_dq(ov, ids[1]), ONE)["stand"] == "later"

    # Springen naar 4 zonder 2 af te ronden.
    ov = await _status(client, wg, ids[3], "openen")
    assert ov["actief"] == ids[3]
    assert _dq(ov, ids[1])["status"] == "in_behandeling" and _kid(_dq(ov, ids[1]), ONE)["stand"] == "later"
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
    assert [b["bron_iri"] for b in dq["bronnen"]] == [ART] and dq["beoordelen"]["mag"]
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
    # De koppelingen opnieuw zetten (het deelvraagpaneel) laat de rol staan.
    wg = await _koppel(client, wg, ids[2], bronnen=[wg["bronnen"][0]["id"]])
    assert [b["rol"] for b in _dq(await _overzicht(client, wg), ids[2])["bronnen"]] == ["context"]
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
    assert r["detail"]["fout"] == "poort" and "1 voorstel open" in r["detail"]["redenen"][0]
    # Voorlopig afronden mag met open punten; een tweede klik met de oude revisie is geen 412.
    punten = [{"tekst": "Bijzondere invorderbaarheid nog niet onderzocht."}]
    ov = await _status(client, wg, ids[0], "afronden", verwachte_revisie=rev, open_punten=punten)
    assert _dq(ov, ids[0])["status"] == "voorlopig_afgerond" and _dq(ov, ids[0])["open_punten"] == punten
    ov = await _status(client, wg, ids[0], "afronden", verwachte_revisie=rev, open_punten=punten)
    rev = _dq(ov, ids[0])["revisie"]
    assert rev == 2
    ov = await _besluit(client, wg, ids[0], _kid(_dq(ov, ids[0]), ART)["id"], "later")
    r = await _status(client, wg, ids[0], "beoordelen", verwacht=409, verwachte_revisie=rev)
    assert r["detail"]["redenen"] == ["Er staan nog onderzoekspunten open."]
    ov = await _status(client, wg, ids[0], "beoordelen", verwachte_revisie=rev, open_punten=[])
    assert _dq(ov, ids[0])["status"] == "beoordeeld"
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
    ov = await _besluit(client, wg, ids[1], _kid(_dq(ov, ids[1]), ART)["id"], "later")
    assert _dq(ov, ids[1])["status"] == "in_behandeling"
    acties = [a["actie"] for a in (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]]
    assert "bronselectie-later" in acties and "bronselectie-gestart" in acties


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
