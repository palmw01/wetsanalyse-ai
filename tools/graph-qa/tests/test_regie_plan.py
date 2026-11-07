"""Het plan van een regie (ADR-012): zuiver, deterministisch, zonder overlap, en het krimpt tot het budget."""
from __future__ import annotations

import asyncio

from agent.models import ChatRequest
from agent.regie.plan import AANDEEL, MARGE, kind_verzoek, plan_annoteren, plan_bronnen
from agent.werkgebied_annotatie import binnen_aandeel, deel_van

WG = "wg-1"


def _werkgebied(*deelvragen) -> dict:
    return {"id": WG, "analysevraag": "Wanneer?", "deelvragen": [
        {"id": did, "vraag": f"Vraag {did}?", "status": status, "volgorde": i, "bronnen": list(bronnen)}
        for i, (did, bronnen, status) in enumerate(deelvragen)]}


def _wv(eenheden: dict[str, list[str]], *, per_bepaling=None, resterend=None) -> dict:
    return {"te_annoteren": list(eenheden),
            "eenheden": [{"bron_iri": i, "label": i.rsplit(":", 1)[-1], "regeling": "Iw", "selecties": s}
                         for i, s in eenheden.items()],
            "schatting": {"per_bepaling": per_bepaling, "basis": 5} if per_bepaling else None,
            "budget": {"resterend": resterend, "actief": resterend is not None}}


def test_bronnen_per_deelvraag_die_niet_klaar_is():
    ov = {"deelvragen": [{"id": "d1", "nr": 1, "vraag": "Wie?", "klaar": True},
                         {"id": "d2", "nr": 2, "vraag": "Wat?", "klaar": False},
                         {"id": "d3", "nr": 3, "vraag": "Wanneer?", "klaar": False}]}
    plan = plan_bronnen(WG, ov)
    assert [(t.deelvraag_id, t.nr, t.titel) for t in plan.taken] == [
        ("d2", 2, "Bronnen · deelvraag 2"), ("d3", 3, "Bronnen · deelvraag 3")]
    assert plan.buiten == ("Deelvraag 1 is al klaar.",) and plan.schatting == 0
    assert plan_bronnen(WG, ov).plan_id == plan.plan_id and len(plan.plan_id) == 16
    verzoek = ChatRequest(**kind_verzoek(plan.taken[0], werkgebied_id=WG, gesprek_id="kind"))
    assert (verzoek.actie, verzoek.onderwerp.id, verzoek.werkgebied_id) == ("bronselectie", "d2", WG)


def test_bronnen_zonder_deelvragen_is_de_analysevraag():
    plan = plan_bronnen(WG, {"deelvragen": [{"id": "analysevraag", "nr": 0, "vraag": "Wanneer?", "klaar": False}]})
    assert [t.titel for t in plan.taken] == ["Bronnen · analysevraag"]
    verzoek = ChatRequest(**kind_verzoek(plan.taken[0], werkgebied_id=WG, gesprek_id="kind"))
    assert verzoek.actie == "bronselectie" and verzoek.onderwerp is None


def test_annoteren_zonder_overlap_naar_de_eerste_deelvraag():
    wg = _werkgebied(("d1", ["s1"], "actief"), ("d2", ["s1", "s2"], "actief"), ("d3", ["s3"], "voorgesteld"))
    wv = _wv({"a:1": ["s1"], "a:2": ["s1", "s2"], "b:1": ["s2"], "c:1": ["s3"]}, per_bepaling=1000)
    plan = plan_annoteren(wg, wv)
    assert [(t.deelvraag_id, t.eenheden) for t in plan.taken] == [("d1", ("a:1", "a:2")), ("d2", ("b:1",))]
    alle = [i for t in plan.taken for i in t.eenheden]
    assert len(alle) == len(set(alle))
    assert any("onder geen deelvraag" in z for z in plan.buiten)       # c:1 hangt onder een voorgestelde deelvraag
    assert plan.taken[0].schatting == 2000 and plan.taken[0].aandeel == round(2000 * AANDEEL)
    assert plan.taken[0].titel == "Annoteren · deelvraag 1 (2 bepalingen)"
    assert plan_annoteren(wg, wv).plan_id == plan.plan_id
    # Het id gaat over het werk, niet over de schatting.
    assert plan_annoteren(wg, _wv({"a:1": ["s1"], "a:2": ["s1", "s2"], "b:1": ["s2"], "c:1": ["s3"]},
                                  per_bepaling=9999)).plan_id == plan.plan_id
    assert plan_annoteren(wg, _wv({"a:1": ["s1"], "b:1": ["s2"]})).plan_id != plan.plan_id


def test_annoteren_zonder_deelvragen_is_een_taak():
    plan = plan_annoteren({"id": WG, "deelvragen": []}, _wv({"a:1": ["s1"], "a:2": ["s1"]}))
    assert [(t.deelvraag_id, len(t.eenheden)) for t in plan.taken] == [("", 2)]
    verzoek = ChatRequest(**kind_verzoek(plan.taken[0], werkgebied_id=WG, gesprek_id="kind"))
    assert (verzoek.actie, verzoek.modus, verzoek.bevestigd, verzoek.eenheden) == (
        "werkgebied_annoteren", "werkgebied_annoteren", 2, ["a:1", "a:2"])


def test_het_plafond_in_de_volgorde_van_de_deelvragen():
    wg = _werkgebied(("d1", ["s1"], "actief"), ("d2", ["s2"], "actief"))
    wv = _wv({**{f"a:{i}": ["s1"] for i in range(3)}, **{f"b:{i}": ["s2"] for i in range(3)}})
    plan = plan_annoteren(wg, wv, plafond=4)
    assert [len(t.eenheden) for t in plan.taken] == [3, 1]
    assert any("plafond van 4" in z for z in plan.buiten)


def test_het_plan_krimpt_tot_het_budget():
    wg = _werkgebied(("d1", ["s1"], "actief"), ("d2", ["s2"], "actief"))
    wv = _wv({"a:1": ["s1"], "a:2": ["s1"], "b:1": ["s2"]}, per_bepaling=1000, resterend=int(2 * 1000 * MARGE))
    plan = plan_annoteren(wg, wv)
    assert [t.eenheden for t in plan.taken] == [("a:1", "a:2")]
    assert plan.hoog <= plan.resterend and any("passen niet in je budget" in z for z in plan.buiten)
    leeg = plan_annoteren(wg, _wv({"a:1": ["s1"]}, per_bepaling=1000, resterend=10))
    assert leeg.taken == () and leeg.buiten


def test_zonder_schatting_wordt_het_budget_verdeeld():
    wg = _werkgebied(("d1", ["s1"], "actief"), ("d2", ["s2"], "actief"))
    plan = plan_annoteren(wg, _wv({"a:1": ["s1"], "b:1": ["s2"]}, resterend=10_000))
    assert [t.aandeel for t in plan.taken] == [5000, 5000] and plan.schatting is None


def test_een_annotatiekind_is_een_geldig_verzoek():
    wg = _werkgebied(("d1", ["s1"], "actief"))
    plan = plan_annoteren(wg, _wv({"a:1": ["s1"]}, per_bepaling=1000))
    verzoek = ChatRequest(**kind_verzoek(plan.taken[0], werkgebied_id=WG, gesprek_id="kind"))
    assert (verzoek.modus, verzoek.bereik, verzoek.deelvraag_id, verzoek.bevestigd) == (
        "werkgebied_annoteren", "deelvragen", "d1", 1)
    assert verzoek.budget_aandeel == plan.taken[0].aandeel and verzoek.is_werkgebied_annotatie


def test_eenheden_alleen_bij_het_annoteren_van_een_werkgebied():
    import pytest
    with pytest.raises(ValueError):
        ChatRequest(question="q", eenheden=["a:1"])
    with pytest.raises(ValueError):
        ChatRequest(question="q", budget_aandeel=10)


def test_deel_van_is_een_doorsnede():
    wv = {"te_annoteren": ["a", "b", "c"], "naam": "X"}
    assert deel_van(wv, ["c", "a", "z"])["te_annoteren"] == ["a", "c"]
    assert deel_van(wv, None) is wv


def test_binnen_aandeel_stopt_voor_de_volgende_die_niet_past():
    verbruikt = [0]

    async def api():
        return True
    poort = binnen_aandeel(2500, verbruikt, 1000, api)
    verbruikt[0] = 1000
    assert asyncio.run(poort())          # 1000 + 1000 ≤ 2500
    verbruikt[0] = 2000
    assert not asyncio.run(poort())      # 2000 + 1000 > 2500
    # Zonder schatting: het gemiddelde tot nu toe.
    zonder = binnen_aandeel(2500, verbruikt := [1200], None, None)
    assert asyncio.run(zonder())         # 1200 + 1200 ≤ 2500
    verbruikt[0] = 2600
    assert not asyncio.run(zonder())     # na 2: 2600 + 1300 > 2500


def test_binnen_aandeel_houdt_de_poort_van_de_api():
    async def op():
        return False
    assert not asyncio.run(binnen_aandeel(10**9, [0], 1, op)())
