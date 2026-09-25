"""Gedragsregressies voor scope, idempotentie, bronversies en gedeelde reviews."""
import hashlib

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import db
from app import annotatie_v2_store as store
from app.annotatie_v2_contracts import Batch, Beslissing, Zoekvraag

LAW = "urn:bwb:BWBR0004770"
ART = LAW + ":artikel:9"
ONE = ART + ":lid:1"
TWO = ART + ":lid:2"


def snapshot(target=ART, second="Beta"):
    nodes = [dict(bron_iri=LAW, parent_iri="", type="Wet", label="Wet", tekst=""),
             dict(bron_iri=ART, parent_iri=LAW, type="Artikel", label="Artikel 9", tekst=""),
             dict(bron_iri=ONE, parent_iri=ART, type="Lid", label="Lid 1", tekst="😀 Alfa Alfa"),
             dict(bron_iri=TWO, parent_iri=ART, type="Lid", label="Lid 2", tekst=second)]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0004770")
    return dict(snapshot_id=store.digest(nodes), doel=next(n for n in nodes if n["bron_iri"] == target), nodes=nodes)


def element(snap, iri=ONE, start=2, end=6, **extra):
    n = store.nodes_van(snap)[iri]
    return dict(klasse="Rechtssubject", tekst=n["tekst"][start:end],
                ankers=[dict(bron_iri=iri, start=start, eind=end, tekst=n["tekst"][start:end], bron_hash=n["bron_hash"])], **extra)


def request(snap, elements=None, batch_id="test", revisions=None, **extra):
    return Batch.model_validate(dict(batch_id=batch_id, doel={"bron_iri": snap["doel"]["bron_iri"]},
        snapshot_id=snap["snapshot_id"], elementen=elements or [], verwachte_revisies=revisions or {}, **extra))


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


async def test_lid_view_contains_no_sibling_and_lca_only_reference():
    snap = snapshot()
    first = element(snap)
    second = element(snap, TWO, 0, 4)
    multi = dict(klasse="Voorwaarde", tekst=first["tekst"] + " " + second["tekst"],
                 ankers=[*first["ankers"], *second["ankers"]])
    await store.batch(request(snap, [first, second, multi]), snap, "a")
    child = await store.weergave(snapshot(ONE))
    assert [s["bron_iri"] for s in child["segmenten"]] == [ONE]
    assert len(child["elementen"]) == 1
    assert len(child["verwijzingen"]) == 1
    assert child["verwijzingen"][0]["eigenaar_iri"] == ART
    assert "Beta" not in str(child)
    whole = await store.weergave(snap)
    assert len(whole["elementen"]) == 3
    assert not whole["verwijzingen"]


async def test_idempotent_batch_preserves_exact_reply_and_no_extra_audit():
    snap = snapshot(ONE)
    req = request(snap, [element(snap)])
    first = await store.batch(req, snap, "a")
    assert await store.batch(req, snap, "a") == first
    async with db.get_engine().connect() as conn:
        assert len((await conn.execute(select(db.annotatie_v2_audit))).all()) == 2
    altered = req.model_copy(update={"run": {"model": "ander"}})
    with pytest.raises(HTTPException) as exc:
        await store.batch(altered, snap, "a")
    assert exc.value.status_code == 409


async def test_invalid_fragment_rolls_back_entire_batch():
    snap = snapshot()
    bad = element(snap, TWO, 0, 4)
    bad["ankers"][0]["tekst"] = "fake"
    with pytest.raises(HTTPException):
        await store.batch(request(snap, [element(snap), bad]), snap, "a")
    assert not (await store.weergave(snap))["elementen"]
    assert not (await store.weergave(snap))["lagen"]


async def test_unicode_codepoints_and_repeated_quotes_are_distinct():
    snap = snapshot(ONE)
    result = await store.batch(request(snap, [element(snap), element(snap, start=7, end=11)]), snap, "a")
    assert len(result["elementen"]) == 2
    assert len({e["id"] for e in result["elementen"]}) == 2


async def test_child_selection_rejects_sibling_anchor():
    snap = snapshot(ONE)
    with pytest.raises(HTTPException) as exc:
        await store.batch(request(snap, [element(snap, TWO, 0, 4)]), snap, "a")
    assert exc.value.status_code == 422


async def test_revision_conflict_is_atomic():
    snap = snapshot()
    await store.batch(request(snap, [element(snap)]), snap, "a")
    with pytest.raises(HTTPException) as exc:
        await store.batch(request(snap, [element(snap, TWO, 0, 4), element(snap, start=7, end=11)], batch_id="b"), snap, "b")
    assert exc.value.status_code == 412
    assert len((await store.weergave(snap))["elementen"]) == 1


async def test_completed_empty_child_is_covered_but_parent_context_missing():
    snap = snapshot(ONE)
    await store.batch(request(snap, dekking={"voltooid": True, "bereik": [ONE]}), snap, "a")
    assert (await store.dekking(snap))["voltooid"]
    parent = await store.dekking(snapshot())
    assert not parent["voltooid"]
    assert parent["bereik"] == [ONE]
    assert not parent["parent_context"]


async def test_parent_completed_coverage_covers_children():
    snap = snapshot()
    await store.batch(request(snap, dekking={"voltooid": True, "bereik": [ONE, TWO], "parent_context": True}), snap, "a")
    assert (await store.dekking(snapshot(ONE)))["voltooid"]
    assert not (await store.dekking(snapshot(second="Changed")))["voltooid"]
    # Een wijziging in lid 2 wist de afgeronde dekking van ongewijzigd lid 1 niet.
    assert (await store.dekking(snapshot(ONE, second="Changed")))["voltooid"]


async def test_move_correction_preserves_id_history_and_changes_both_revisions():
    snap = snapshot()
    first = await store.batch(request(snap, [element(snap)]), snap, "a")
    eid = first["elementen"][0]["id"]
    moved = element(snap, TWO, 0, 4)
    result = await store.beslis(eid, Beslissing(type="edit", snapshot_id=snap["snapshot_id"],
        verwachte_revisies={ONE: 1, TWO: 0}, wijziging={k: moved[k] for k in ("tekst", "ankers")}), snap, "b")
    assert result["element"]["id"] == eid
    assert result["element"]["eigenaar_iri"] == TWO
    assert result["element"]["beslissingen"][0]["actor"] == "b"
    assert {l["bron_iri"]: l["revisie"] for l in result["lagen"]} == {ONE: 2, TWO: 1}
    assert not (await store.weergave(snapshot(ONE)))["elementen"]


async def test_changed_source_invalidates_only_affected_anchors():
    snap = snapshot()
    await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)]), snap, "a")
    changed = snapshot(second="Other")
    view = await store.weergave(changed)
    assert {e["eigenaar_iri"]: e["verouderd"] for e in view["elementen"]} == {ONE: False, TWO: True}


async def test_approved_element_requires_explicit_reopen():
    snap = snapshot(ONE)
    first = await store.batch(request(snap, [element(snap)]), snap, "a")
    eid = first["elementen"][0]["id"]
    await store.beslis(eid, Beslissing(type="approve", snapshot_id=snap["snapshot_id"],
                                      verwachte_revisies={ONE: 1}), snap, "b")
    with pytest.raises(HTTPException) as exc:
        await store.beslis(eid, Beslissing(type="reject", snapshot_id=snap["snapshot_id"],
                                          verwachte_revisies={ONE: 2}), snap, "b")
    assert exc.value.status_code == 409


async def test_search_stale_projection_is_partial_not_false_empty(monkeypatch):
    from app import graaf_projectie_v2, annotatie_v2_zoeken
    snap = snapshot(ONE)
    await store.batch(request(snap, [element(snap)]), snap, "a")
    async def candidates(_):
        return {"ids": [], "manifest": {}, "beschikbaar": True}
    async def resolve(_):
        return snap
    monkeypatch.setattr(graaf_projectie_v2, "zoek_kandidaten", candidates)
    monkeypatch.setattr(annotatie_v2_zoeken, "resolve_bron", resolve)
    result = await annotatie_v2_zoeken.zoek(Zoekvraag(bron_iri=ONE))
    assert result["status"] == "partial"
    assert not result["volledig"]
    assert result["resultaten"] == []


async def test_search_ignores_stale_graph_lifecycle(monkeypatch):
    from app import graaf_projectie_v2, annotatie_v2_zoeken
    snap = snapshot(ONE)
    first = await store.batch(request(snap, [element(snap)]), snap, "a")
    eid = first["elementen"][0]["id"]
    await store.beslis(eid, Beslissing(type="reject", snapshot_id=snap["snapshot_id"],
                                      verwachte_revisies={ONE: 1}), snap, "b")
    async def candidates(_):
        return {"ids": [eid], "manifest": {}, "beschikbaar": True}
    async def resolve(_):
        return snap
    monkeypatch.setattr(graaf_projectie_v2, "zoek_kandidaten", candidates)
    monkeypatch.setattr(annotatie_v2_zoeken, "resolve_bron", resolve)
    result = await annotatie_v2_zoeken.zoek(Zoekvraag(bron_iri=ONE, lifecycle="voorgesteld"))
    assert not result["resultaten"]


async def test_api_view_active_user_and_export_scope(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app import annotatie_v2
    from app.config import get_settings
    from conftest import maak_testgebruikers
    monkeypatch.setenv("ANNOTATIE_CONTRACT_VERSIE", "2")
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()

    await maak_testgebruikers("v2-reviewer")
    from app.main import app
    async def resolve(goal):
        return snapshot(goal.get("bron_iri", ART))
    monkeypatch.setattr(annotatie_v2, "_resolve_bron", resolve)
    snap = snapshot()
    await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)]), snap, "v2-reviewer")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/v1/annotatie/weergave", params={"bron_iri": ONE})).status_code == 401
        headers = {"X-User-Id": "v2-reviewer"}
        response = await client.get("/v1/annotatie/weergave", params={"bron_iri": ONE}, headers=headers)
        assert response.status_code == 200
        assert "Beta" not in response.text
        export = await client.post("/v1/annotatie/weergave/export", headers=headers,
            json={"bron_iri": ONE, "snapshot_id": snap["snapshot_id"], "formaat": "json"})
        assert export.status_code == 200
        assert "Beta" not in export.text
        assert (await client.get("/v1/annotatie/capabilities", headers=headers)).json()["bronnodes_actief"]
        legacy = await client.put("/v1/annotatie/lagen/BWBR0004770/9/elementen", headers=headers, json={})
        assert legacy.status_code == 409
        monkeypatch.setenv("ANNOTATIE_CONTRACT_VERSIE", "1")
        get_settings.cache_clear()
        assert (await client.get("/v1/annotatie/weergave", headers=headers, params={"bron_iri": ONE})).status_code == 503
    get_settings.cache_clear()


async def test_search_anchor_scope_and_cursor_are_verified(monkeypatch):
    from app import graaf_projectie_v2, annotatie_v2_zoeken
    snap = snapshot()
    first = element(snap)
    second = element(snap, TWO, 0, 4)
    multi = dict(klasse="Voorwaarde", tekst=first["tekst"] + " " + second["tekst"],
                 ankers=[*first["ankers"], *second["ankers"]])
    result = await store.batch(request(snap, [first, multi]), snap, "a")
    async with db.get_engine().begin() as conn:
        from sqlalchemy import update
        await conn.execute(update(db.annotatie_v2_lagen).values(geprojecteerd_revisie=1))
    async def candidates(_):
        return {"ids": [e["id"] for e in result["elementen"]],
                "manifest": {l["id"]: 1 for l in result["lagen"]}, "beschikbaar": True}
    async def resolve(_):
        return snapshot(ONE)
    monkeypatch.setattr(graaf_projectie_v2, "zoek_kandidaten", candidates)
    monkeypatch.setattr(annotatie_v2_zoeken, "resolve_bron", resolve)
    page = await annotatie_v2_zoeken.zoek(Zoekvraag(bron_iri=ONE, limit=1))
    assert page["status"] == "ok"
    assert page["cursor"]
    next_page = await annotatie_v2_zoeken.zoek(Zoekvraag(bron_iri=ONE, limit=1, cursor=page["cursor"]))
    assert next_page["resultaten"][0]["soort"] == "verwijzing"
    assert "Beta" not in str(next_page)
    with pytest.raises(HTTPException) as exc:
        await annotatie_v2_zoeken.zoek(Zoekvraag(bron_iri=ONE, limit=2, cursor=page["cursor"]))
    assert exc.value.status_code == 422


async def test_search_filters_are_and_lists_or(monkeypatch):
    from app import graaf_projectie_v2, annotatie_v2_zoeken
    snap = snapshot(ONE)
    el = element(snap, toelichting="Bijzondere toelichting")
    result = await store.batch(request(snap, [el]), snap, "a")
    async with db.get_engine().begin() as conn:
        from sqlalchemy import update
        await conn.execute(update(db.annotatie_v2_lagen).values(geprojecteerd_revisie=1))
    async def candidates(_):
        return {"ids": [result["elementen"][0]["id"]],
                "manifest": {result["lagen"][0]["id"]: 1}, "beschikbaar": True}
    async def resolve(_):
        return snap
    monkeypatch.setattr(graaf_projectie_v2, "zoek_kandidaten", candidates)
    monkeypatch.setattr(annotatie_v2_zoeken, "resolve_bron", resolve)
    query = Zoekvraag(bronnode_id=ONE, jas_klassen=["Voorwaarde", "Rechtssubject"],
        lifecycle=["voorgesteld", "human_approved"], laagstatus=["in_review"],
        tekstveld="toelichting", tekst="BIJZONDERE", match="bevat")
    assert len((await annotatie_v2_zoeken.zoek(query))["resultaten"]) == 1
    query.match = "exact"
    assert not (await annotatie_v2_zoeken.zoek(query))["resultaten"]


async def test_missing_cursor_epoch_is_invalid_and_sources_cached_per_law(monkeypatch):
    import base64
    import json
    from app import graaf_projectie_v2, annotatie_v2_zoeken
    snap = snapshot()
    result = await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)]), snap, "a")
    calls = []
    async def resolve(goal):
        calls.append(goal)
        return snap
    async def candidates(_):
        return {"ids": [e["id"] for e in result["elementen"]], "manifest": {}, "beschikbaar": True}
    monkeypatch.setattr(graaf_projectie_v2, "zoek_kandidaten", candidates)
    monkeypatch.setattr(annotatie_v2_zoeken, "resolve_bron", resolve)
    assert len((await annotatie_v2_zoeken.zoek(Zoekvraag()))["resultaten"]) == 2
    assert calls == [{"bwb_id": "BWBR0004770"}]
    req = Zoekvraag()
    req.cursor = base64.urlsafe_b64encode(json.dumps({"query": store.digest(
        req.model_dump(exclude={"cursor", "offset"})), "offset": 0}).encode()).decode()
    with pytest.raises(HTTPException) as exc:
        await annotatie_v2_zoeken.zoek(req)
    assert exc.value.status_code == 422


async def test_reuse_of_completed_locked_layer_does_not_mutate_review_revision():
    snap = snapshot(ONE)
    await store.batch(request(snap, dekking={"voltooid": True, "bereik": [ONE]}), snap, "a")
    layer = (await store.weergave(snap))["lagen"][0]
    await store.zet_status(layer["id"], "geaccordeerd", 1, "a")
    req = request(snap, batch_id="reuse", run={"modus": "hergebruik"},
                  dekking={"voltooid": True, "bereik": [ONE], "parent_context": True})
    await store.batch(req, snap, "a")
    assert (await store.weergave(snap))["lagen"][0]["revisie"] == 2


async def test_source_change_reopens_layer_without_erasing_approved_history():
    snap = snapshot(TWO)
    first = await store.batch(request(snap, [element(snap, TWO, 0, 4)]), snap, "a")
    eid, layer = first["elementen"][0]["id"], first["lagen"][0]
    await store.beslis(eid, Beslissing(type="approve", snapshot_id=snap["snapshot_id"],
                                      verwachte_revisies={TWO: 1}), snap, "b")
    await store.zet_status(layer["id"], "geaccordeerd", 2, "b", snap)
    changed = snapshot(TWO, second="Other")
    await store.batch(request(changed, [element(changed, TWO, 0, 5)], batch_id="changed",
                              revisions={TWO: 3}), changed, "a")
    view = await store.weergave(changed)
    assert view["lagen"][0]["status"] == "in_review"
    old = next(e for e in view["elementen"] if e["id"] == eid)
    assert old["verouderd"] and old["lifecycle"] == "human_approved"
    assert old["beslissingen"][0]["actor"] == "b"


async def test_parent_context_does_not_reopen_or_touch_reused_approved_children():
    for index, iri in enumerate((ONE, TWO)):
        child = snapshot(iri)
        created = await store.batch(request(child, batch_id=str(index),
            dekking={"voltooid": True, "bereik": [iri]}), child, "a")
        await store.zet_status(created["lagen"][0]["id"], "geaccordeerd", 1, "a")
    parent = snapshot()
    left, right = element(parent), element(parent, TWO, 0, 4)
    multi = dict(klasse="Voorwaarde", tekst=left["tekst"] + " " + right["tekst"],
                 ankers=[*left["ankers"], *right["ankers"]])
    await store.batch(request(parent, [multi], batch_id="parent", revisions={ONE: 2, TWO: 2},
        dekking={"voltooid": True, "bereik": [ONE, TWO], "parent_context": True}), parent, "a")
    view = await store.weergave(parent)
    children = [l for l in view["lagen"] if l["bron_iri"] in {ONE, TWO}]
    assert all(l["revisie"] == 2 and l["status"] == "geaccordeerd" for l in children)
    assert view["dekking"]["voltooid"]


async def test_removed_source_node_historical_detail_and_search(monkeypatch):
    from app import annotatie_v2, annotatie_v2_zoeken, graaf_projectie_v2
    old = snapshot(TWO)
    created = await store.batch(request(old, [element(old, TWO, 0, 4)]), old, "a")
    current = snapshot()
    current["nodes"] = [n for n in current["nodes"] if n["bron_iri"] != TWO]
    current["snapshot_id"] = store.digest(current["nodes"])
    calls = []
    async def resolve(goal):
        calls.append(goal)
        return current
    async def candidates(filters):
        assert filters["bron_iri"] == ""  # historical source must not require live-tree membership
        assert filters["scoped_nodes"] == [TWO]
        return {"ids": [created["elementen"][0]["id"]], "manifest": {}, "beschikbaar": True}
    monkeypatch.setattr(annotatie_v2, "resolve_bron", resolve)
    monkeypatch.setattr(annotatie_v2_zoeken, "resolve_bron", resolve)
    monkeypatch.setattr(graaf_projectie_v2, "zoek_kandidaten", candidates)
    detail = await annotatie_v2.get_element(created["elementen"][0]["id"], "a")
    assert detail["element"]["verouderd"]
    assert detail["bronverwijzing"]["historisch"]
    assert detail["bronnen"][0]["tekst"] == "Beta"
    assert calls[0] == {"bwb_id": "BWBR0004770"}
    result = await annotatie_v2_zoeken.zoek(Zoekvraag(bron_iri=TWO, scope="node",
        inclusief_verouderd=True, bronversie=old["snapshot_id"]))
    assert result["resultaten"][0]["verouderd"]
    assert result["resultaten"][0]["bronverwijzing"]["historisch"]


async def test_pdf_preserves_all_local_anchors_and_owner(monkeypatch):
    import shutil
    import subprocess
    from app import annotatie_v2
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext ontbreekt voor onafhankelijke PDF-tekstextractie")
    snap = snapshot()
    a, b = element(snap), element(snap, TWO, 0, 4)
    multi = dict(klasse="Voorwaarde", tekst=a["tekst"] + " " + b["tekst"], ankers=a["ankers"] + b["ankers"])
    await store.batch(request(snap, [multi]), snap, "a")
    async def resolve(_):
        return snap
    monkeypatch.setattr(annotatie_v2, "resolve_bron", resolve)
    response = await annotatie_v2.post_export(annotatie_v2.ExportInvoer(
        bron_iri=ART, snapshot_id=snap["snapshot_id"], formaat="pdf"), "a")
    parsed = subprocess.run(["pdftotext", "-", "-"], input=response.body, capture_output=True, check=True).stdout.decode()
    assert "Eigenaar: " + ART in parsed
    assert ONE in parsed and TWO in parsed
    assert "[2, 6)" in parsed and "[0, 4)" in parsed
    assert a["ankers"][0]["bron_hash"] in parsed.replace("\n", "")


async def test_elke_commit_projecteert_direct_en_een_fout_niet(monkeypatch, caplog):
    # Zoals v1: direct na de commit naar de graaf, met de lus als vangnet. Een geweigerde mutatie
    # projecteert niets, en een haperende graaf laat de mutatie zelf niet falen.
    import asyncio
    from app import graaf_projectie_v2
    geprojecteerd = []
    async def projecteer(laag_id):
        geprojecteerd.append(laag_id)
        return True
    monkeypatch.setattr(graaf_projectie_v2, "projecteer", projecteer)
    graaf_projectie_v2.activeer(True)
    try:
        snap = snapshot(ONE)
        created = await store.batch(request(snap, [element(snap)]), snap, "a")
        await asyncio.gather(*graaf_projectie_v2._taken)
        assert geprojecteerd == [created["lagen"][0]["id"]]

        with pytest.raises(HTTPException):
            await store.batch(request(snap, [element(snap, start=7, end=11)], batch_id="oud",
                                      revisions={ONE: 0}), snap, "a")
        await asyncio.gather(*graaf_projectie_v2._taken)
        assert len(geprojecteerd) == 1

        async def faalt(laag_id):
            raise RuntimeError("graaf weg")
        monkeypatch.setattr(graaf_projectie_v2, "projecteer", faalt)
        await store.zet_status(created["lagen"][0]["id"], "in_review", 1, "a")
        await asyncio.gather(*graaf_projectie_v2._taken)
        assert "annotatie_v2_projectie_uitgesteld" in caplog.text
    finally:
        await graaf_projectie_v2.stop()


async def test_zonder_graaf_geen_directe_projectie(monkeypatch):
    from app import graaf_projectie_v2
    monkeypatch.setattr(graaf_projectie_v2, "projecteer", lambda laag_id: pytest.fail("geen graaf geconfigureerd"))
    snap = snapshot(ONE)
    await store.batch(request(snap, [element(snap)]), snap, "a")
    assert not graaf_projectie_v2._taken


async def test_herkomstspoor_per_element_blijft_bewaard_tot_in_de_weergave():
    """ADR-001 PR 15: `trace` is een expliciet contractveld en reist mee tot in de opslag en de export."""
    snap = snapshot(ONE)
    spoor = {"pijplijn": "hybrid_v1", "jas_versie": "1.0.10",
             "kandidaat": {"id": "Kabc", "label": "C001", "bewijs": [{"detector": "tijd", "code": "TEMPORAL_DURATION"}]},
             "beslissing": {"door": "regel", "status": "ACCEPTED"}, "vraag": ""}
    await store.batch(request(snap, [element(snap, trace=spoor)]), snap, "a")
    [e] = (await store.weergave(snap))["elementen"]
    assert e["trace"] == spoor


async def test_element_zonder_spoor_krijgt_een_leeg_spoor():
    snap = snapshot(ONE)
    await store.batch(request(snap, [element(snap)]), snap, "a")
    [e] = (await store.weergave(snap))["elementen"]
    assert e.get("trace", {}) == {}


def test_csv_provenance_draagt_het_spoor_alleen_als_het_er_is():
    from app.annotatie_v2 import _provenance
    assert _provenance({"geproduceerd_door": {"model": "m"}}) == {"model": "m"}
    assert _provenance({"geproduceerd_door": {"model": "m"}, "trace": {"x": 1}}) == {"model": "m", "trace": {"x": 1}}


async def test_structurele_dekking_reist_mee_en_veroudert_met_de_tekst():
    """De keten meldt per bronnode wat hij wel en niet kon bekijken; de weergave toont de recentste
    meting die nog over déze tekst gaat – een oudere wijst met haar offsets naar tekst die er niet meer staat."""
    snap = snapshot(ONE)
    meting = {"dimensies": {"tijd": "uitgevoerd", "definitie": "overgeslagen"},
              "ongedekt": [{"tekst": "Alfa", "start": 7, "eind": 11}]}
    await store.batch(request(snap, [element(snap)], dekking={"voltooid": True, "bereik": [ONE],
                                                              "structureel": {ONE: meting},
                                                              "proces": {"ACCEPTED": 1}}), snap, "a")
    view = await store.weergave(snap)
    assert view["dekking"]["structureel"] == {ONE: meting}
    # Andere tekst in lid 1: de oude meting geldt niet meer.
    gewijzigd = snapshot(ONE, second="Beta")
    for n in gewijzigd["nodes"]:
        if n["bron_iri"] == ONE:
            n["tekst"], n["bron_hash"] = "Iets anders", hashlib.sha256(b"Iets anders").hexdigest()
    assert (await store.weergave(gewijzigd))["dekking"]["structureel"] == {}
