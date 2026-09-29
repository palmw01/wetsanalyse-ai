"""Herkomst vóór interne regelmerge/fusie, zonder aanpassing van de kandidaatsemantiek."""
from agent.jas_pipeline.beslisregister import compact
from agent.jas_pipeline.besluit import Beslissing, deterministisch
from agent.jas_pipeline.classificatie import kandidaatregel
from agent.jas_pipeline.detectoren import BronTekst
from agent.jas_pipeline.detectoren.regels import Regel, RegelDetector
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import CandidateStatus


def resultaten():
    def regel(rid, klasse, code):
        return Regel.van("test", {"id": rid, "klassen": [klasse], "code": code,
                                 "bron": "test", "versie": 1, "patroon": "zes weken", "bewijs": "zwak"})
    d = RegelDetector("test", (regel("jas.test.tijd", "Tijdsaanduiding", "TEMPORAL_DURATION"),
                              regel("jas.test.object", "Rechtsobject", "OBJECT_NP")))
    return [d.detecteer(BronTekst.van_tekst("test", "zes weken"))]


def test_bewaart_klassen_per_regel_voor_interne_merge_en_voor_fusie():
    rs = resultaten()
    assert len(rs[0].kandidaten) == 1
    f = fuseer(rs)
    assert len(f.bijdragen) == 2
    assert {b.bewijs[0].regel: b.mogelijke_klassen for b in f.bijdragen} == {
        "jas.test.tijd": ("Tijdsaanduiding",), "jas.test.object": ("Rechtsobject",)}
    assert all(b.detector == "test" and b.versie == rs[0].versie and b.regel_versie == "1" for b in f.bijdragen)


def test_afgewezen_kandidaat_houdt_bijdragen_en_oude_registeraanroep_werkt():
    f = fuseer(resultaten())
    k, = f.kandidaten
    b = Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.REJECTED, door="model")
    oud, = compact(f.kandidaten, [b], [])
    nieuw, = compact(f.kandidaten, [b], [], f.bijdragen)
    assert oud["detectiebijdragen"] == []
    assert len(nieuw["detectiebijdragen"]) == 2
    assert {key: value for key, value in nieuw.items() if key != "detectiebijdragen"} == {
        key: value for key, value in oud.items() if key != "detectiebijdragen"}


def test_diagnostiek_heeft_geen_invloed_op_prompt_of_besluit():
    rs = resultaten()
    met = fuseer(rs)
    zonder = fuseer([r.model_copy(update={"bijdragen": ()}) for r in rs])
    assert met.kandidaten == zonder.kandidaten
    assert [kandidaatregel(k) for k in met.kandidaten] == [kandidaatregel(k) for k in zonder.kandidaten]
    assert [deterministisch(k) for k in met.kandidaten] == [deterministisch(k) for k in zonder.kandidaten]
