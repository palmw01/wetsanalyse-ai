"""Momentopnamen van artefacten (de versiekiezer zoals bij Claude): bij het bewaren van een beurt van Lex met een
artefact legt de api de stand van dat moment vast, en het bericht verwijst ernaar met `artefact.ref.versie`."""
from __future__ import annotations

from sqlalchemy import func, select, update

from app import annotatie_v2, artefact_versies, db
from app import annotatie_v2_store as store
from test_annotatie_v2 import ART, element, request, snapshot
from test_werkgebieden import _nieuw, client, database, graaf  # noqa: F401

G = "/v1/gesprekken"


async def _gesprek(client) -> str:
    r = await client.post(G, json={"titel": "Vraag"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _beurt(client, gid: str, run_id: str, soort: str, ref: dict, rol: str = "assistant") -> dict:
    r = await client.post(f"{G}/{gid}/berichten", json={
        "rol": rol, "tekst": "Klaar.", "run_id": run_id, "artefact": {"soort": soort, "ref": ref, "titel": "x"}})
    assert r.status_code == 201, r.text
    return r.json()


async def _wijzig_tijdens_lezen(monkeypatch, wid: str, keer: int) -> list[int]:
    """`_inhoud` die de eerste `keer` keer het werkgebied ziet wijzigen terwijl hij leest."""
    echt, gelezen = artefact_versies._inhoud, []

    async def inhoud(soort, ref):
        uit = await echt(soort, ref)
        gelezen.append(uit["werkgebied"]["revisie"])
        if len(gelezen) <= keer:
            async with db.get_engine().begin() as conn:
                await conn.execute(update(db.werkgebieden).where(db.werkgebieden.c.id == wid).values(
                    revisie=db.werkgebieden.c.revisie + 1))
        return uit

    monkeypatch.setattr(artefact_versies, "_inhoud", inhoud)
    return gelezen


async def test_een_wijziging_tijdens_het_lezen_leest_opnieuw(client, monkeypatch):
    wg = await _nieuw(client)
    gelezen = await _wijzig_tijdens_lezen(monkeypatch, wg["id"], 1)
    uit = await artefact_versies._een_stand("werkgebied", {"werkgebied_id": wg["id"]})
    assert len(gelezen) == 2 and uit["werkgebied"]["revisie"] == wg["revisie"] + 1 and "consistent" not in uit


async def test_blijft_het_wijzigen_dan_telt_de_opname_toch(client, monkeypatch):
    wg, gid = await _nieuw(client), await _gesprek(client)
    gelezen = await _wijzig_tijdens_lezen(monkeypatch, wg["id"], 99)
    bericht = await _beurt(client, gid, "r-druk", "werkgebied", {"werkgebied_id": wg["id"]})
    assert len(gelezen) == artefact_versies.POGINGEN
    versie = await artefact_versies.haal(bericht["artefact"]["ref"]["versie"])
    assert versie["inhoud"]["consistent"] is False


async def _aantal() -> int:
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(func.count()).select_from(db.artefact_versies))).scalar()


async def test_elke_beurt_van_lex_is_een_versie_van_het_werkgebied(client):
    wg = await _nieuw(client, "Rekeningafspraak")
    gid = await _gesprek(client)
    b1 = await _beurt(client, gid, "run-1", "werkgebied", {"werkgebied_id": wg["id"]})
    v1 = b1["artefact"]["ref"]["versie"]
    r = await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": wg["revisie"], "naam": "Nieuw"})
    assert r.status_code == 200, r.text
    b2 = await _beurt(client, gid, "run-2", "werkgebied", {"werkgebied_id": wg["id"]})
    v2 = b2["artefact"]["ref"]["versie"]

    een = (await client.get(f"/v1/artefact-versies/{v1}")).json()
    assert (een["nr"], een["totaal"], een["vorige"], een["volgende"]) == (1, 2, None, v2)
    assert een["inhoud"]["werkgebied"]["naam"] == "Rekeningafspraak"
    assert "bronselectie" in een["inhoud"]
    twee = (await client.get(f"/v1/artefact-versies/{v2}")).json()
    assert (twee["nr"], twee["vorige"], twee["inhoud"]["werkgebied"]["naam"]) == (2, v1, "Nieuw")
    assert twee["sleutel"] == f"werkgebied:{wg['id']}" and twee["soort"] == "werkgebied"

    # Het bericht na herladen draagt de versie; de lijst noemt beide.
    berichten = (await client.get(f"{G}/{gid}")).json()["berichten"]
    assert [b["artefact"]["ref"]["versie"] for b in berichten] == [v1, v2]
    lijst = (await client.get("/v1/artefact-versies", params={"sleutel": f"werkgebied:{wg['id']}"})).json()
    assert [v["id"] for v in lijst["versies"]] == [v1, v2] and [v["nr"] for v in lijst["versies"]] == [1, 2]


async def test_dezelfde_beurt_nog_eens_is_geen_tweede_versie(client):
    wg = await _nieuw(client)
    gid = await _gesprek(client)
    a = await _beurt(client, gid, "run-1", "werkgebied", {"werkgebied_id": wg["id"]})
    b = await _beurt(client, gid, "run-1", "werkgebied", {"werkgebied_id": wg["id"]})
    assert a["id"] == b["id"] and a["artefact"]["ref"]["versie"] == b["artefact"]["ref"]["versie"]
    assert await _aantal() == 1


async def test_geen_versie_zonder_beurt_van_lex(client):
    wg = await _nieuw(client)
    gid = await _gesprek(client)
    b = await _beurt(client, gid, "", "werkgebied", {"werkgebied_id": wg["id"]})
    assert "versie" not in b["artefact"]["ref"]
    b = await _beurt(client, gid, "run-u", "werkgebied", {"werkgebied_id": wg["id"]}, rol="user")
    assert "versie" not in b["artefact"]["ref"]
    # `regels` is gereserveerd en heeft geen inhoud om vast te leggen.
    b = await _beurt(client, gid, "run-r", "regels", {"werkgebied_id": wg["id"]})
    assert "versie" not in b["artefact"]["ref"]
    assert await _aantal() == 0


async def test_een_storing_laat_het_bericht_landen_zonder_versie(client, monkeypatch):
    wg = await _nieuw(client)
    gid = await _gesprek(client)

    async def kapot(soort, ref):
        raise RuntimeError("graaf weg")
    monkeypatch.setattr(artefact_versies, "_inhoud", kapot)
    b = await _beurt(client, gid, "run-1", "werkgebied", {"werkgebied_id": wg["id"]})
    assert "versie" not in b["artefact"]["ref"]
    # Een onbekend object (verwijderd werkgebied) ook.
    monkeypatch.undo()
    b = await _beurt(client, gid, "run-2", "bronselectie", {"werkgebied_id": "bestaat-niet"})
    assert "versie" not in b["artefact"]["ref"]
    assert len((await client.get(f"{G}/{gid}")).json()["berichten"]) == 2


async def test_deelvraag_en_bronselectie(client):
    wg = await _nieuw(client)
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen",
                          json={"verwachte_revisie": wg["revisie"], "vraag": "Wie is belastingschuldige?"})
    assert r.status_code == 201, r.text
    d = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()["deelvragen"][0]
    gid = await _gesprek(client)
    b = await _beurt(client, gid, "run-1", "deelvraag", {"werkgebied_id": wg["id"], "deelvraag_id": d["id"]})
    v = (await client.get(f"/v1/artefact-versies/{b['artefact']['ref']['versie']}")).json()
    assert v["sleutel"] == f"deelvraag:{wg['id']}:{d['id']}"
    assert v["inhoud"]["deelvraag"]["vraag"] == "Wie is belastingschuldige?"
    b = await _beurt(client, gid, "run-2", "bronselectie", {"werkgebied_id": wg["id"]})
    v = (await client.get(f"/v1/artefact-versies/{b['artefact']['ref']['versie']}")).json()
    assert v["sleutel"] == f"bronselectie:{wg['id']}" and v["inhoud"]["bronselectie"]["deelvragen"]


def test_sleutel_per_object():
    assert artefact_versies.sleutel_van("begrip", {"werkgebied_id": "w", "begrip_id": "b"}) == "begrip:w:b"
    assert artefact_versies.sleutel_van("begrippen", {"werkgebied_id": "w", "run_id": "r"}) == "begrippen:w"
    assert artefact_versies.sleutel_van("annotatie", {"bron_iri": ART}) == f"annotatie:{ART}"
    assert artefact_versies.sleutel_van("deelvraag", {"werkgebied_id": "w"}) is None
    assert artefact_versies.sleutel_van("werkgebied", {}) is None


async def test_een_onbekende_versie_is_404(client):
    assert (await client.get("/v1/artefact-versies/bestaat-niet")).status_code == 404


async def test_een_werkgebied_verwijderen_wist_zijn_versies(client):
    wg = await _nieuw(client)
    gid = await _gesprek(client)
    b = await _beurt(client, gid, "run-1", "werkgebied", {"werkgebied_id": wg["id"]})
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    assert await _aantal() == 0
    assert (await client.get(f"/v1/artefact-versies/{b['artefact']['ref']['versie']}")).status_code == 404
    # Het bericht blijft: het gesprek is een verslag.
    assert len((await client.get(f"{G}/{gid}")).json()["berichten"]) == 1


async def test_een_annotatie_verwijderen_wist_haar_versies(monkeypatch):
    snap = snapshot()

    async def resolve(doel):
        assert doel["bron_iri"] == ART
        return snap
    monkeypatch.setattr(annotatie_v2, "_resolve_bron", resolve)
    await store.batch(request(snap, [element(snap)]), snap, "lex")
    vid = await artefact_versies.leg_vast("g1", "run-1", {"soort": "annotatie", "ref": {"bron_iri": ART}})
    v = await artefact_versies.haal(vid)
    assert v["sleutel"] == f"annotatie:{ART}" and len(v["inhoud"]["weergave"]["lagen"]) == 1

    view = await store.weergave(snap)
    await store.verwijder_weergave(snap, {l["bron_iri"]: l["revisie"] for l in view["lagen"]}, "jurist-a")
    assert await _aantal() == 0
