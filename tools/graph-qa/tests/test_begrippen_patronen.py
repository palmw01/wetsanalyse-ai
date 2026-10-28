"""Het patroonregister van de begrippenketen (ADR-004): elke regel met zijn eigen tests."""
from __future__ import annotations

import pytest

from agent.begrippen_pipeline import patronen
from agent.begrippen_pipeline.model import Bron, Formulering, Hypothese, Manifest, Taalanalyse

REGELS = patronen.alle_regels()


def _gevallen(soort: str):
    return [pytest.param(r, geval, id=f"{r.id}-{soort}-{i}")
            for r in REGELS for i, geval in enumerate(r.tests[soort])]


def _eerste(r: patronen.Regel, tekst: str):
    return r.patroon.search(tekst)


@pytest.mark.parametrize("regel, geval", _gevallen("positief") + _gevallen("rand") + _gevallen("overlap"))
def test_regel_vangt_van_en_naar(regel, geval):
    m = _eerste(regel, geval["tekst"])
    assert m, f"{regel.id} matcht niet op {geval['tekst']!r}"
    assert (m.group("van"), m.group("naar")) == (geval["van"], geval["naar"])


@pytest.mark.parametrize("regel, geval", _gevallen("negatief"))
def test_regel_matcht_niet_op_negatief(regel, geval):
    assert not _eerste(regel, geval["tekst"]), f"{regel.id} matcht ten onrechte"


def test_register_weigert_onvolledige_regels():
    goed = {"id": "begrip.x.y", "hypothese": "kwalificatie", "code": "X", "polariteit": "steun",
            "sterkte": "sterk", "bron": "b", "versie": 1, "patroon": r"(?P<van>\w+) als (?P<naar>\w+)",
            "tests": {s: [{}] for s in patronen.TESTSOORTEN}}
    patronen._regel(goed)
    with pytest.raises(ValueError, match="ontbrekende tests"):
        patronen._regel({**goed, "tests": {"positief": [{}]}})
    with pytest.raises(ValueError, match="'van' en 'naar'"):
        patronen._regel({**goed, "patroon": r"(?P<van>\w+) als \w+"})
    with pytest.raises(ValueError, match="vorm"):
        patronen._regel({**goed, "id": "jas.x.y"})


def test_gevangen_woord_wordt_wettelijke_term_als_het_geen_eigen_formulering_is():
    w = "urn:bwb:BWBR0004770:artikel:"
    defb = Bron(bron_iri=w + "2:lid:1:o:m", aanhef="Deze wet verstaat onder:", bron_hash="h",
                tekst="belastingaanslag: de aanslag en de navorderingsaanslag;")
    b93 = Bron(bron_iri=w + "9:lid:3", bron_hash="h3",
               tekst="Een met een belastingaanslag gelijkgestelde beschikking is invorderbaar.")
    f_def = Formulering(element_id="d", bron_iri=defb.bron_iri, start=0, eind=16,
                        tekst="belastingaanslag", jas_klasse="Brondefinitie")
    s = b93.tekst.index("met een")
    tekst = "met een belastingaanslag gelijkgestelde beschikking"
    f_b = Formulering(element_id="b", bron_iri=b93.bron_iri, start=s, eind=s + len(tekst),
                      tekst=tekst, jas_klasse="Rechtsobject")
    m = Manifest(bronnen=(defb, b93), formuleringen=(f_def, f_b))
    taal = {"d": Taalanalyse(element_id="d", kern="belastingaanslag", term="belastingaanslag"),
            "b": Taalanalyse(element_id="b", kern="beschikking", kernvorm="beschikking",
                             term="beschikking", beperkt=True)}
    sig = [(x.hypothese, x.van, x.naar, x.bewijs.code) for x in patronen.toepassen(m, taal)]
    assert (Hypothese.KWALIFICATIE, "b", "d", "KWALIFICATIE") in sig


def test_uitsluiting_is_ook_tegenbewijs_tegen_samenvoegen():
    b = Bron(bron_iri="urn:bwb:BWBR1:artikel:1", bron_hash="h",
             tekst="Onder werknemer wordt niet verstaan de bestuurder.")
    fs = tuple(Formulering(element_id=e, bron_iri=b.bron_iri, start=b.tekst.index(t),
                           eind=b.tekst.index(t) + len(t), tekst=t, jas_klasse="Rechtssubject")
               for e, t in (("w", "werknemer"), ("b", "bestuurder")))
    taal = {"w": Taalanalyse(element_id="w", kern="werknemer", term="werknemer"),
            "b": Taalanalyse(element_id="b", kern="bestuurder", term="bestuurder")}
    sig = {(x.hypothese.value, x.van, x.naar, x.bewijs.polariteit.value)
           for x in patronen.toepassen(Manifest(bronnen=(b,), formuleringen=fs), taal)}
    assert ("uitsluiting", "w", "b", "steun") in sig
    assert ("zelfde_betekenis", "b", "w", "tegen") in sig


def test_kopsignaal_is_zwak_en_alleen_naar_een_bestaande_kern():
    b = Bron(bron_iri="urn:bwb:BWBR1:artikel:1", bron_hash="h", tekst="de aanslag en de navorderingsaanslag")
    fs = tuple(Formulering(element_id=e, bron_iri=b.bron_iri, start=b.tekst.index(t),
                           eind=b.tekst.index(t) + len(t), tekst=t, jas_klasse="Rechtsobject")
               for e, t in (("a", "de aanslag"), ("n", "de navorderingsaanslag")))
    taal = {"a": Taalanalyse(element_id="a", kern="aanslag", term="aanslag"),
            "n": Taalanalyse(element_id="n", kern="navorderingsaanslag", term="navorderingsaanslag",
                             kop="aanslag")}
    sig = patronen.kopsignalen(Manifest(bronnen=(b,), formuleringen=fs), taal)
    assert [(s.hypothese, s.van, s.naar, s.bewijs.sterkte.value) for s in sig] == \
        [(Hypothese.HIERARCHIE, "a", "n", "zwak")]


def test_referentieset_gelijkstelling_en_alleen_zwakke_kopsignalen():
    pytest.importorskip("spacy")
    from agent.begrippen_pipeline.taal import analyseer
    from agent.jas_pipeline.taal.provider import SpacyProvider
    from eval import begrippen_eval as be
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd (uv sync --extra nlp)")
    bronnen, cases, _ = be.laad()
    m = be.manifest_uit(bronnen, cases)
    taal = analyseer(m, p)
    sig = {(s.hypothese.value, s.van, s.naar, s.bewijs.code) for s in patronen.toepassen(m, taal)}
    assert ("kwalificatie", "f21", "f01", "KWALIFICATIE") in sig
    assert {s.bewijs.sterkte.value for s in patronen.kopsignalen(m, taal)} == {"zwak"}
