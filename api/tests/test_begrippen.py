"""Begrippen (spoor D, levering 2): koppelingen met bewijsstand, de poort, actualiteit, de primaire
duiding, revisies en de export."""
from __future__ import annotations

import csv
import io

import pytest
from sqlalchemy import delete

from app import annotatie_v2_store as store, db
from app.annotatie_v2_contracts import Beslissing
from test_annotatie_v2 import ART, ONE, TWO, element, request, snapshot
from test_werkgebieden import ART2, _bron, _nieuw, client, database, graaf, snapshot2  # noqa: F401

DEFINITIE = {"definitie": "Degene die de belasting verschuldigd is.",
             "context": "Invordering van rijksbelastingen."}


async def _annoteer() -> dict[str, str]:
    """Drie elementen in twee regelingen: lid 1 en lid 2 van artikel 9, en artikel 2 van de AWR."""
    snap = snapshot()
    uit = await store.batch(request(snap, [element(snap, ONE), element(snap, TWO, 0, 4)]), snap, "lex")
    snap2 = snapshot2()
    uit2 = await store.batch(request(snap2, [element(snap2, ART2, 0, 4)], batch_id="awr"), snap2, "lex")
    per_bron = {e["eigenaar_iri"]: e["id"] for e in uit["elementen"] + uit2["elementen"]}
    return {"lid1": per_bron[ONE], "lid2": per_bron[TWO], "awr": per_bron[ART2]}


async def _beslis(eid: str, soort: str, snap: dict, **extra):
    view = await store.weergave(snap)
    revs = {l["bron_iri"]: l["revisie"] for l in view["lagen"]}
    await store.beslis(eid, Beslissing(type=soort, snapshot_id=snap["snapshot_id"], verwachte_revisies=revs, **extra),
                       snap, "jurist-a")


async def _keur_alles_goed(ids: dict[str, str]):
    snap = snapshot()
    for eid in (ids["lid1"], ids["lid2"]):
        await _beslis(eid, "approve", snap)
    await _beslis(ids["awr"], "approve", snapshot2())


async def _werkgebied(client) -> dict:
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    return (await _bron(client, wg, bron_iri=ART2))["werkgebied"]


async def _begrip(client, wg, element_ids=(), rol="duiding", naam="Belastingschuldige") -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen",
                          json={"inhoud": {"naam": naam}, "element_ids": list(element_ids), "rol": rol})
    assert r.status_code == 201, r.text
    return r.json()


def _url(wg, b, *rest) -> str:
    return "/".join([f"/v1/werkgebieden/{wg['id']}/begrippen/{b['id']}", *rest])


# --- de acceptatie --------------------------------------------------------------------------------

async def test_uit_meerdere_annotaties_een_begrip_en_elke_passage_terug(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"], ids["awr"]])
    r = await client.post(_url(wg, b, "koppelingen"), json={"verwachte_revisie": b["revisie"],
                                                            "element_ids": [ids["lid2"]], "rol": "definitie"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert {k["element_id"]: k["rol"] for k in b["koppelingen"]} == {
        ids["lid1"]: "duiding", ids["awr"]: "duiding", ids["lid2"]: "definitie"}
    assert {k["actualiteit"] for k in b["koppelingen"]} == {"actueel"}
    awr = next(k for k in b["koppelingen"] if k["element_id"] == ids["awr"])
    assert awr["bewijs"]["tekst"] == "Deze" and awr["bewijs"]["vindplaats"] == "Artikel 2"
    lid1 = next(k for k in b["koppelingen"] if k["element_id"] == ids["lid1"])
    assert lid1["bewijs"]["vindplaats"] == "Artikel 9 · Lid 1"

    # Nog niet te accorderen, en de poort zegt waarom.
    assert b["accorderen"]["mag"] is False
    redenen = " ".join(b["accorderen"]["redenen"])
    for stuk in ("geen definitie", "toelichting", "3 dragende koppelingen",
                 "3 dragende annotaties zijn nog niet door een jurist"):
        assert stuk in redenen, redenen
    assert (await client.post(_url(wg, b, "accorderen"), json={"verwachte_revisie": b["revisie"]})).status_code == 409

    # Invullen, de annotaties beoordelen, de koppelingen beoordelen – dan mag het.
    b = (await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"],
                                               "inhoud": {"naam": "Belastingschuldige", **DEFINITIE}})).json()
    await _keur_alles_goed(ids)
    for k in b["koppelingen"]:
        b = (await client.patch(_url(wg, b, "koppelingen", k["id"]),
                                json={"verwachte_revisie": b["revisie"], "beoordeling": "akkoord"})).json()
    assert b["accorderen"] == {"mag": True, "redenen": []}
    r = await client.post(_url(wg, b, "accorderen"), json={"verwachte_revisie": b["revisie"]})
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["status"], b["geaccordeerd_door"], b["geaccordeerd_revisie"]) == ("geaccordeerd", "jurist-a", b["revisie"])

    # De export draagt elke passage met haar vindplaats.
    data = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/export")).json()
    assert data["kader_iri"] == f"urn:wa:kader:{wg['id']}"
    [exp] = data["begrippen"]
    assert exp["iri"] == f"urn:wa:begrip:{b['id']}" and len(exp["koppelingen"]) == 3
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/export", params={"formaat": "csv"})
    assert r.headers["content-disposition"] == 'attachment; filename="begrippen.csv"'
    rijen = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert len(rijen) == 3
    assert {(x["vindplaats"], x["bron_iri"]) for x in rijen} == {
        ("Artikel 9 · Lid 1", ONE), ("Artikel 9 · Lid 2", TWO), ("Artikel 2", ART2)}
    assert {x["status"] for x in rijen} == {"geaccordeerd"}


# --- actualiteit ----------------------------------------------------------------------------------

async def test_een_veranderde_passage_blijft_staan_met_haar_bewijs(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"], ids["awr"]])

    snap = snapshot()
    await _beslis(ids["lid1"], "edit", snap, wijziging={"klasse": "Rechtsobject"})
    await _beslis(ids["awr"], "reject", snapshot2())
    b = (await client.get(_url(wg, b))).json()
    per = {k["element_id"]: k for k in b["koppelingen"]}
    assert per[ids["lid1"]]["actualiteit"] == "gewijzigd"
    assert per[ids["lid1"]]["bewijs"]["klasse"] == "Rechtssubject"        # de bewaarde stand
    assert per[ids["awr"]]["actualiteit"] == "verworpen"

    # Een hard verwijderd element: de koppeling cascadeert niet, ze is verdwenen.
    async with db.get_engine().begin() as conn:
        await conn.execute(delete(db.annotatie_v2_elementen).where(db.annotatie_v2_elementen.c.id == ids["awr"]))
    b = (await client.get(_url(wg, b))).json()
    awr = next(k for k in b["koppelingen"] if k["element_id"] == ids["awr"])
    assert (awr["actualiteit"], awr["bewijs"]["tekst"]) == ("verdwenen", "Deze")
    assert any("gewijzigd, verworpen of verdwenen" in x for x in b["accorderen"]["redenen"])


async def test_een_akkoord_op_de_annotatie_is_geen_wijziging(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    await _beslis(ids["lid1"], "approve", snapshot())
    k = (await client.get(_url(wg, b))).json()["koppelingen"][0]
    assert (k["actualiteit"], k["annotatie_beoordeeld"]) == ("actueel", True)


# --- primaire duiding, idempotentie, scope ----------------------------------------------------------

async def test_een_element_duidt_hooguit_een_begrip_aan(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    a = await _begrip(client, wg, [ids["lid1"]], naam="A")
    b = await _begrip(client, wg, naam="B")
    r = await client.post(_url(wg, b, "koppelingen"), json={"verwachte_revisie": b["revisie"],
                                                            "element_ids": [ids["lid1"]], "rol": "duiding"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "al_primair"
    assert r.json()["detail"]["begrip_naam"] == "A"
    # Als definitie mag het wel.
    r = await client.post(_url(wg, b, "koppelingen"), json={"verwachte_revisie": b["revisie"],
                                                            "element_ids": [ids["lid1"]], "rol": "definitie"})
    assert r.status_code == 200
    b = r.json()
    # En die definitie-koppeling ombuigen naar duiding mag niet zolang A haar draagt.
    k = b["koppelingen"][0]
    r = await client.patch(_url(wg, b, "koppelingen", k["id"]), json={"verwachte_revisie": b["revisie"], "rol": "duiding"})
    assert r.status_code == 409
    # A weg: de duiding is vrij.
    assert (await client.delete(_url(wg, a), params={"verwachte_revisie": a["revisie"]})).status_code == 200
    r = await client.patch(_url(wg, b, "koppelingen", k["id"]), json={"verwachte_revisie": b["revisie"], "rol": "duiding"})
    assert r.status_code == 200, r.text
    lijst = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen")).json()
    assert [x["inhoud"]["naam"] for x in lijst["begrippen"]] == ["B"]
    assert lijst["primair"] == {ids["lid1"]: {"begrip_id": b["id"], "naam": "B"}}


async def test_twee_keer_koppelen_is_idempotent(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    r = await client.post(_url(wg, b, "koppelingen"), json={"verwachte_revisie": b["revisie"],
                                                            "element_ids": [ids["lid1"]]})
    assert r.status_code == 200 and r.json()["revisie"] == b["revisie"]
    assert len(r.json()["koppelingen"]) == 1


async def test_een_element_buiten_het_werkgebied_wordt_geweigerd(client):
    ids = await _annoteer()
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ONE, bereik="node"))["werkgebied"]
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen",
                          json={"inhoud": {"naam": "X"}, "element_ids": [ids["lid1"], ids["awr"]]})
    assert r.status_code == 422
    assert r.json()["detail"]["element_ids"] == [ids["awr"]]
    # En er is niets aangemaakt.
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen")).json()["begrippen"] == []


# --- revisies, status, gearchiveerd ---------------------------------------------------------------

async def test_revisies_bewaren_de_oude_inhoud_en_412_bij_een_oude_stand(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    b2 = (await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"],
                                                "inhoud": {"naam": "Belastingschuldige", "definitie": "Eerste"}})).json()
    r = await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"], "inhoud": {"naam": "Ander"}})
    assert r.status_code == 412 and r.json()["detail"]["revisie"] == b2["revisie"]
    # Opslaan zonder wijziging is geen revisie.
    zelfde = (await client.patch(_url(wg, b2), json={"verwachte_revisie": b2["revisie"],
                                                     "inhoud": b2["inhoud"]})).json()
    assert zelfde["revisie"] == b2["revisie"]
    revs = (await client.get(_url(wg, b, "revisies"))).json()["revisies"]
    assert [(x["revisie"], x["actie"]) for x in revs] == [(2, "begrip-gewijzigd"), (1, "begrip-aangemaakt")]
    assert revs[0]["detail"]["velden"] == ["definitie"]
    assert (revs[1]["inhoud"]["definitie"], revs[0]["inhoud"]["definitie"]) == ("", "Eerste")
    # Eén tijdlijn: de audit van het werkgebied draagt de begripregels ook.
    audit = (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]
    assert [a["actie"] for a in audit[:2]] == ["begrip-gewijzigd", "begrip-aangemaakt"]


async def test_een_wijziging_na_accorderen_maakt_het_weer_een_concept(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    b = (await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"],
                                               "inhoud": {"naam": "Belastingschuldige", **DEFINITIE}})).json()
    await _beslis(ids["lid1"], "approve", snapshot())
    b = (await client.patch(_url(wg, b, "koppelingen", b["koppelingen"][0]["id"]),
                            json={"verwachte_revisie": b["revisie"], "beoordeling": "akkoord"})).json()
    b = (await client.post(_url(wg, b, "accorderen"), json={"verwachte_revisie": b["revisie"]})).json()
    assert b["status"] == "geaccordeerd"
    r = await client.post(_url(wg, b, "heropenen"), json={"verwachte_revisie": b["revisie"]})
    assert r.json()["status"] == "concept"
    b = (await client.post(_url(wg, r.json(), "accorderen"), json={"verwachte_revisie": r.json()["revisie"]})).json()
    b = (await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"],
                                               "inhoud": {**b["inhoud"], "uitleg": "Aanvulling"}})).json()
    assert b["status"] == "concept"


async def test_een_gearchiveerd_werkgebied_heeft_geen_begrippen_meer(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert (await client.get(_url(wg, b))).status_code == 404
    r = await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"], "inhoud": {"naam": "Y"}})
    assert r.status_code == 404


@pytest.mark.parametrize("inhoud", [{"naam": " "},
                                    {"naam": "X", "voorbeelden": [{"tekst": "a", "oordeel": "misschien"}]}])
async def test_ongeldige_inhoud_geeft_422(client, inhoud):
    wg = await _werkgebied(client)
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen", json={"inhoud": inhoud})
    assert r.status_code == 422


# --- review 15 okt: randgevallen ------------------------------------------------------------------

async def test_een_rol_ombuigen_naar_een_rol_die_er_al_is_geeft_409(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    b = (await client.post(_url(wg, b, "koppelingen"), json={"verwachte_revisie": b["revisie"],
                                                             "element_ids": [ids["lid1"]], "rol": "definitie"})).json()
    definitie = next(k for k in b["koppelingen"] if k["rol"] == "definitie")
    r = await client.patch(_url(wg, b, "koppelingen", definitie["id"]),
                           json={"verwachte_revisie": b["revisie"], "rol": "duiding"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "al_gekoppeld"
    assert len((await client.get(_url(wg, b))).json()["koppelingen"]) == 2


async def test_een_koppeling_opslaan_zonder_wijziging_is_geen_revisie(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    k = b["koppelingen"][0]
    r = await client.patch(_url(wg, b, "koppelingen", k["id"]),
                           json={"verwachte_revisie": b["revisie"], "rol": "duiding", "motivatie": ""})
    assert r.status_code == 200 and r.json()["revisie"] == b["revisie"]


async def test_een_revisieconflict_draagt_een_leesbare_melding(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"], "inhoud": {"naam": "Y"}})
    r = await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"], "inhoud": {"naam": "Z"}})
    assert r.status_code == 412 and "Iemand anders" in r.json()["detail"]["melding"]
    r = await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": 1, "naam": "Q"})
    assert r.status_code == 412 and "Iemand anders" in r.json()["detail"]["melding"]


async def test_het_model_is_slank_en_de_herkomst_rekent_de_api(client):
    """Spoor I1: JAS-duiding, begripstype, onderbouwing e.d. vallen weg; de herkomst kiest niemand."""
    wg = await _werkgebied(client)
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen", json={"inhoud": {
        "naam": "X", "jas_klasse": "Variabele en variabelewaarde", "begripstype": "actor", "onderbouwing": "o",
        "open_vragen": ["v?"], "eigenschappen": {"a": "b"}, "geldigheid": "g",
        "definitie": "Iets.", "definitie_herkomst": "letterlijk",
        "voorbeelden": [{"tekst": "a", "oordeel": "wel", "toelichting": "t"}]}})
    assert r.status_code == 201, r.text
    b = r.json()
    for weg in ("jas_klasse", "begripstype", "onderbouwing", "open_vragen", "eigenschappen", "geldigheid"):
        assert weg not in b["inhoud"]
    assert b["inhoud"]["voorbeelden"] == [{"tekst": "a", "oordeel": "wel"}]
    # Een eigen definitie is geformuleerd, wat de client ook meestuurt.
    assert (b["inhoud"]["definitie_herkomst"], b["inhoud"]["definitie_door"]) == ("geformuleerd", "analist")
    # Zonder definitie geen herkomst.
    r = await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"],
                                              "inhoud": {"naam": "X", "definitie_herkomst": "letterlijk"}})
    assert r.json()["inhoud"]["definitie_herkomst"] is None
