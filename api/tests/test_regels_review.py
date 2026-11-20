"""De code review van de afleidingsregelstapel (20 nov 2026): één test per bevinding, getoetst aan ADR-018 besluit 2
(de poort) en de besluiten van de gebruiker van 20 nov 2026, niet aan het gedrag van vóór de review.

De maat: een regel komt pas door de poort als alles waarop hij rust beoordeeld is en geen open punt hem tegenhoudt;
een geaccordeerde regel die een blokkerend punt krijgt, is weer een concept (bevinding 3, optie a); per geval telt
alleen een voorbeeld met het oordeel `juist` (bevinding 7)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import db, regel_contracts, regel_projectie, regel_store
from gedeelde_bron import client, database, graaf  # noqa: F401
from test_regels import _beoordeel, _inhoud, _klaar_voor_accorderen, _opzet, _twee_gevallen, _url


def _punten(wg) -> str:
    return f"/v1/werkgebieden/{wg['id']}/open-punten"


async def _accordeer(client, wg, regel) -> dict:
    r = await client.post(_url(wg, regel["id"], "accorderen"),
                          json={"verwachte_revisie": regel["revisie"], "reden": "Getoetst."})
    assert r.status_code == 200, r.text
    return r.json()


async def _acties(wg) -> list[str]:
    a = db.werkgebied_audit
    async with db.get_engine().connect() as conn:
        return list((await conn.execute(select(a.c.actie).where(a.c.werkgebied_id == wg["id"]))).scalars().all())


# --- 1 (hoog) --------------------------------------------------------------------------------------

async def test_1_een_voorwaarde_op_een_contextdrager_wordt_beoordeeld(client):
    """Een voorwaarde rust op een markering die de regel draagt, en die is beoordeeld. Een contextdrager draagt niets:
    staat zijn markering in een voorwaarde, dan komt er een dragende drager bij, en die houdt tegen tot hij akkoord is."""
    wg, ids, b = await _opzet(client)
    regel = await _klaar_voor_accorderen(client, wg, ids, b)
    regel = (await client.post(_url(wg, regel["id"], "dragers"), json={
        "verwachte_revisie": regel["revisie"], "dragers": [{"element_id": ids["rs"], "rol": "context"}]})).json()
    assert regel["accorderen"]["mag"], "een contextdrager houdt niets tegen"
    inhoud = {**_inhoud(b), "voorbeelden": regel["inhoud"]["voorbeelden"]}
    inhoud["gevallen"][0]["voorwaarden"] = {"verband": "alle", "delen": [{"tekst": "beta", "element_ids": [ids["rs"]]}]}
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"], "inhoud": inhoud})).json()
    assert {(d["element_id"], d["rol"]) for d in regel["dragers"]} >= {(ids["rs"], "context"), (ids["rs"], "voorwaarde")}
    assert regel["accorderen"]["mag"] is False
    assert "1 dragende formulering is nog niet beoordeeld." in regel["accorderen"]["redenen"]
    # De poort zelf, los van het aanmaken van de drager: een voorwaarde die alleen op een contextdrager rust, telt als
    # "geen drager".
    drager = {"element_id": "e", "rol": "context", "beoordeling": "akkoord", "geval": "", "actualiteit": "actueel"}
    inh = {"gevallen": [{"label": "", "voorwaarden": {"verband": "alle", "delen": [{"tekst": "x", "element_ids": ["e"]}]}}]}
    assert regel_store._rust_op(inh, [drager]) == ([], ["e"])


# --- 2 (hoog) --------------------------------------------------------------------------------------

async def test_2_een_keuze_vervalt_als_de_soort_of_de_lezingen_veranderen(client):
    wg, ids = (await _opzet(client))[:2]
    aan = [{"soort": "markering", "id": ids["ar"]}]
    # (a) Een besloten onderzoekspunt wordt een interpretatiekeuze: geen gekozen lezing, dus weer open.
    p = (await client.post(_punten(wg), json={"inhoud": {"soort": "onderzoekspunt", "vraag": "Elders?", "hangt_aan": aan}})).json()
    p = (await client.post(f"{_punten(wg)}/{p['id']}/besluit",
                           json={"verwachte_revisie": 1, "motivering": "Nagekeken."})).json()
    assert p["status"] == "gekozen"
    keuze = {"soort": "interpretatiekeuze", "vraag": "Elders?", "hangt_aan": aan,
             "lezingen": [{"label": "A", "omschrijving": "Ja"}, {"label": "B", "omschrijving": "Nee"}]}
    p = (await client.patch(f"{_punten(wg)}/{p['id']}", json={"verwachte_revisie": p["revisie"], "inhoud": keuze})).json()
    assert (p["status"], p["keuze"]) == ("open", None)
    # (b) Een gesignaleerd beleidspunt wordt een interpretatiekeuze: gesignaleerd hoort alleen bij beleid.
    q = (await client.post(_punten(wg), json={"inhoud": {"soort": "ontbrekend_uitvoeringsbeleid", "vraag": "Afronding?",
                                                         "hangt_aan": aan}})).json()
    q = (await client.post(f"{_punten(wg)}/{q['id']}/besluit", json={
        "verwachte_revisie": 1, "uitkomst": "gesignaleerd", "motivering": "Geen beleid."})).json()
    assert q["status"] == "gesignaleerd"
    q = (await client.patch(f"{_punten(wg)}/{q['id']}", json={"verwachte_revisie": q["revisie"],
                                                              "inhoud": {**keuze, "vraag": "Afronding?"}})).json()
    assert (q["status"], q["keuze"]) == ("open", None)
    # Een andere vraagtekst laat een keuze staan.
    r = (await client.post(_punten(wg), json={"inhoud": keuze})).json()
    r = (await client.post(f"{_punten(wg)}/{r['id']}/besluit", json={"verwachte_revisie": 1, "gekozen": "A",
                                                                     "motivering": "x", "methode": "grammaticaal"})).json()
    r = (await client.patch(f"{_punten(wg)}/{r['id']}", json={"verwachte_revisie": r["revisie"],
                                                              "inhoud": {**keuze, "vraag": "Elders, ook?"}})).json()
    assert r["status"] == "gekozen"


# --- 3 (middel), besluit gebruiker: optie a -----------------------------------------------------------

async def test_3_een_blokkerend_punt_zet_een_geaccordeerde_regel_terug_op_concept(client):
    wg, ids, b = await _opzet(client)
    regel = await _accordeer(client, wg, await _klaar_voor_accorderen(client, wg, ids, b))
    assert regel["status"] == "geaccordeerd"
    # Aanmaken.
    p = (await client.post(_punten(wg), json={"inhoud": {"soort": "onderzoekspunt", "vraag": "Wat zegt de MvT?",
                                                         "hangt_aan": [{"soort": "regel", "id": regel["id"]}]}})).json()
    regel = (await client.get(_url(wg, regel["id"]))).json()
    assert regel["status"] == "concept"
    revs = (await client.get(_url(wg, regel["id"], "revisies"))).json()["revisies"]
    assert revs[0]["actie"] == "regel-heropend-door-open-punt" and revs[0]["detail"]["open_punt_id"] == p["id"]
    # Heropenen van een besloten punt.
    p = (await client.post(f"{_punten(wg)}/{p['id']}/besluit", json={"verwachte_revisie": p["revisie"],
                                                                     "motivering": "Gelezen."})).json()
    regel = await _accordeer(client, wg, (await client.get(_url(wg, regel["id"]))).json())
    await client.post(f"{_punten(wg)}/{p['id']}/besluit", json={"verwachte_revisie": p["revisie"]})
    assert (await client.get(_url(wg, regel["id"]))).json()["status"] == "concept"
    await client.post(f"{_punten(wg)}/{p['id']}/besluit", json={"verwachte_revisie": p["revisie"] + 1, "motivering": "x"})
    regel = await _accordeer(client, wg, (await client.get(_url(wg, regel["id"]))).json())
    # Omhangen naar de regel; een punt dat ergens anders hangt, raakt de regel niet.
    q = (await client.post(_punten(wg), json={"inhoud": {"soort": "onderzoekspunt", "vraag": "Elders?",
                                                         "hangt_aan": [{"soort": "markering", "id": ids["rs"]}]}})).json()
    assert (await client.get(_url(wg, regel["id"]))).json()["status"] == "geaccordeerd"
    await client.post(f"{_punten(wg)}/{q['id']}/omhangen", json={"verwachte_revisie": q["revisie"],
                                                                 "hangt_aan": [{"soort": "regel", "id": regel["id"]}]})
    assert (await client.get(_url(wg, regel["id"]))).json()["status"] == "concept"
    assert "regel-heropend-door-open-punt" in await _acties(wg)


# --- 4 (middel) -------------------------------------------------------------------------------------

async def test_4_wie_de_opvolger_wist_herstelt_de_voorganger(client):
    wg, ids, b = await _opzet(client)
    oud = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                            "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    nieuw = (await client.post(_url(wg), json={"inhoud": _twee_gevallen(b),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    oud = (await client.post(_url(wg, oud["id"], "afwijzen"), json={
        "verwachte_revisie": oud["revisie"], "reden": "Samengevoegd", "opvolger_id": nieuw["id"]})).json()
    assert oud["status"] == "vervangen"
    nieuw = (await client.get(_url(wg, nieuw["id"]))).json()
    r = await client.delete(_url(wg, nieuw["id"]), params={"verwachte_revisie": nieuw["revisie"]})
    assert r.status_code == 200 and r.json()["hersteld"] == [oud["id"]]
    oud = (await client.get(_url(wg, oud["id"]))).json()
    assert (oud["status"], oud["vervangen_door"]) == ("concept", None)
    assert (await client.get(_url(wg, oud["id"], "revisies"))).json()["revisies"][0]["actie"] == "regel-hersteld"
    # Hij is weer te wijzigen.
    r = await client.post(_url(wg, oud["id"], "afwijzen"), json={"verwachte_revisie": oud["revisie"], "reden": "x"})
    assert r.status_code == 200


# --- 5 (middel) -------------------------------------------------------------------------------------

async def test_5_een_open_punt_verdwijnt_niet_zonder_besluit(client):
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    inhoud = {"soort": "onderzoekspunt", "vraag": "O1", "hangt_aan": [{"soort": "regel", "id": regel["id"]}]}
    p = (await client.post(_punten(wg), json={"inhoud": inhoud})).json()
    # Loshalen via de PATCH kan niet: dat is omhangen.
    r = await client.patch(f"{_punten(wg)}/{p['id']}", json={"verwachte_revisie": 1, "inhoud": {
        **inhoud, "hangt_aan": [{"soort": "werkgebied", "id": wg["id"]}]}})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "omhangen"
    # Wissen vraagt een reden zolang het punt open is.
    r = await client.delete(f"{_punten(wg)}/{p['id']}", params={"verwachte_revisie": 1})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "reden"
    r = await client.delete(f"{_punten(wg)}/{p['id']}", params={"verwachte_revisie": 1, "reden": "Dubbel met O2."})
    assert r.status_code == 200
    a = db.werkgebied_audit
    async with db.get_engine().connect() as conn:
        detail = (await conn.execute(select(a.c.detail).where(a.c.werkgebied_id == wg["id"],
                                                               a.c.actie == "open-punt-verwijderd"))).scalar_one()
    assert detail["reden"] == "Dubbel met O2."


# --- 6 (middel) -------------------------------------------------------------------------------------

async def test_6_een_oordeel_overleeft_geen_wijziging_van_zijn_geval(client):
    wg, ids, b = await _opzet(client)
    regel = await _klaar_voor_accorderen(client, wg, ids, b)
    voorbeelden = regel["inhoud"]["voorbeelden"]
    # Een andere toelichting raakt de uitkomst niet: het oordeel blijft.
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"], "inhoud": {
        **_inhoud(b, toelichting="Een toelichting."), "voorbeelden": voorbeelden}})).json()
    assert regel["inhoud"]["voorbeelden"][0]["oordeel"] == "juist" and regel["accorderen"]["mag"]
    # Een andere uitkomst van het geval: het voorbeeld moet opnieuw worden nagekeken.
    anders = _inhoud(b, voorbeelden=voorbeelden)
    anders["gevallen"][0]["uitkomst"] = [{"soort": "tekst", "tekst": "het bedrag"}]
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"], "inhoud": anders})).json()
    assert regel["inhoud"]["voorbeelden"][0]["oordeel"] == "open"
    assert "Voorbeeld 1 is nog niet beoordeeld." in regel["accorderen"]["redenen"]
    assert regel_store.heropen_oordelen(
        {"gevallen": [{"label": "a", "uitkomst": [1]}, {"label": "b", "uitkomst": [1]}]},
        {"gevallen": [{"label": "a", "uitkomst": [2]}, {"label": "b", "uitkomst": [1]}],
         "voorbeelden": [{"geval": "a", "oordeel": "juist"}, {"geval": "b", "oordeel": "juist"}]}) == [1], \
        "alleen de voorbeelden van het veranderde geval"


# --- 7 (laag–middel), besluit gebruiker: alleen `juist` telt -----------------------------------------

async def test_7_kan_niet_telt_niet_als_beoordeeld_voorbeeld_per_geval(client):
    wg, ids, b = await _opzet(client)
    regel = await _klaar_voor_accorderen(client, wg, ids, b)
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"], "inhoud": _inhoud(
        b, voorbeelden=[{"invoer": "0 termijnen", "uitkomst": "deling door nul"}])})).json()
    regel = await _beoordeel(client, wg, regel, "kan_niet")
    assert regel["accorderen"]["redenen"] == ["Er is nog geen voorbeeld met een juridisch juiste uitkomst."]
    # Per geval.
    p = regel_store.poort({"regelbegrip_id": "r", "uitvoer_begrip_id": "u", "invoer": [],
                           "gevallen": [{"label": "a", "uitkomst": []}, {"label": "b", "uitkomst": []}],
                           "voorbeelden": [{"geval": "a", "oordeel": "juist"}, {"geval": "b", "oordeel": "kan_niet"}]},
                          [], {})
    assert "Nog geen voorbeeld met een juridisch juiste uitkomst bij geval b." in p["redenen"]


# --- 8 (laag) ---------------------------------------------------------------------------------------

async def test_8_accorderen_leest_begrippen_en_markeringen_onder_een_leesslot(client, monkeypatch):
    wg, ids, b = await _opzet(client)
    regel = await _klaar_voor_accorderen(client, wg, ids, b)
    gezien = []
    echt = regel_store._leesslot

    async def spion(conn, werkgebied_id, row):
        gezien.append(row.id)
        await echt(conn, werkgebied_id, row)
    monkeypatch.setattr(regel_store, "_leesslot", spion)
    await _accordeer(client, wg, regel)
    assert gezien == [regel["id"]]


# --- 9 (laag) ---------------------------------------------------------------------------------------

def test_9_een_akkoord_op_de_nieuwe_stand_vraagt_een_motivering():
    with pytest.raises(ValueError):
        regel_contracts.DragerVerversing(verwachte_revisie=1, beoordeling="akkoord")
    regel_contracts.DragerVerversing(verwachte_revisie=1, beoordeling="akkoord", motivering="Gezien.")
    regel_contracts.DragerVerversing(verwachte_revisie=1)


async def test_9_terug_naar_open_wist_wie_beoordeelde(client):
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(b),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    [d] = regel["dragers"]
    regel = (await client.patch(_url(wg, regel["id"], "dragers", d["id"]),
                                json={"verwachte_revisie": regel["revisie"], "beoordeling": "akkoord"})).json()
    regel = (await client.patch(_url(wg, regel["id"], "dragers", d["id"]),
                                json={"verwachte_revisie": regel["revisie"], "beoordeling": "open"})).json()
    assert regel["dragers"][0]["beoordeeld_door"] is None


# --- 10 (laag) --------------------------------------------------------------------------------------

async def test_10_een_geval_bestaat_bij_aanmaken(client):
    wg, ids, b = await _opzet(client)
    regel = (await client.post(_url(wg), json={"inhoud": _twee_gevallen(b),
                                              "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    inhoud = {"soort": "onderzoekspunt", "vraag": "x", "hangt_aan": [{"soort": "geval", "id": regel["id"], "geval": "lid 9"}]}
    r = await client.post(_punten(wg), json={"inhoud": inhoud})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "geval_onbekend"
    inhoud["hangt_aan"][0]["geval"] = "a"
    assert (await client.post(_punten(wg), json={"inhoud": inhoud})).status_code == 201


# --- 11 (laag) --------------------------------------------------------------------------------------

async def test_11_de_rooktest_zegt_dat_hij_afkapt(client, monkeypatch):
    from app import begrip_projectie as bp
    from app.graafcontrole import controleer
    from graafdb_fake import installeer
    from test_regel_projectie import _twee_regels

    installeer(monkeypatch)
    # Zonder regels staan de sleutels er ook, leeg.
    uit = (await controleer(shacl=False))["begrippen"]
    assert (uit["regels_niet_herleidbaar"], uit["regels_niet_herleidbaar_volledig"]) == ([], True)
    await _twee_regels(client)
    await bp.reconcile()
    monkeypatch.setattr(regel_projectie, "MAX_NIET_HERLEIDBAAR", 1)
    uit = (await controleer(shacl=False))["begrippen"]
    assert len(uit["regels_niet_herleidbaar"]) == 1 and uit["regels_niet_herleidbaar_volledig"] is False


# --- 12 (laag) --------------------------------------------------------------------------------------

def test_12_dragend_staat_op_één_plek():
    assert regel_store.DRAGEND is regel_contracts.DRAGEND is regel_projectie.DRAGEND
