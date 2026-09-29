"""Besliscontracten met nepmodellen op de vastgelegde graaftekst van lid 1."""
import json
from types import SimpleNamespace

import pytest
from bronmodel import CorpusMap, tekst_hash

from agent.config import Settings
from agent.jas_pipeline.broncontext import BronContext, ContextPassage
from agent.jas_pipeline.classificatie import batches, toolschema
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.keten import analyseer
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from agent.jas_pipeline.taal import SpacyProvider
from eval.onderzoek_invordering import DOSSIER, snapshot, KeuzeFake


@pytest.fixture(scope="module")
def casus():
    c = json.loads((DOSSIER / "bronnen.json").read_text())["casussen"][0]
    a = SpacyProvider("nl_core_news_md").analyseer(c["tekst"])
    if a.gedegradeerd:
        pytest.skip("volledige parse vereist")
    f = fuseer(detecteer_alles(BronTekst.van_tekst(c["bron_iri"], c["tekst"], analyse=a)))
    return c, f


def run(casus, actie="KEEP", context=None, kort=False, norm=GEEN_ANNOTATIE, motivering="Getoetst aan doeltekst."):
    c, f = casus
    keuzes = {k.label: ("Rechtsobject" if k.span.tekst == "Een belastingaanslag" else
                        "Tijdsaanduiding" if k.span.start == 37 and (kort or k.span.eind > 46) else
                        norm if k.span.start == 0 and k.span.eind == len(c["tekst"]) else GEEN_ANNOTATIE)
              for k in f.kandidaten}

    class Fake(KeuzeFake):
        def create(self, **kw):
            if kw["tools"][0]["name"] == "classificeer":
                return super().create(**kw)
            self.calls.append(kw)
            labels = kw["tools"][0]["input_schema"]["properties"]["oordelen"]["items"]["properties"]["geval"]["enum"]
            items = [{"geval": l, "actie": actie, "klasse": "Rechtsbetrekking" if actie == "CHANGE" else "",
                      "motivering": motivering} for l in labels]
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name="beoordeel", input={"oordelen": items})])

    fake = Fake(keuzes)
    snap = snapshot(c)
    cm = CorpusMap(snap["segmenten"])
    u = analyseer(snapshot=snap, corpus_segmenten=cm.als_dicts(), corpus=cm.corpus, llm=fake, model="nep",
                  settings=Settings(classifier_granulariteit="klasseverzameling"), context=context)
    return u, fake


@pytest.mark.parametrize("actie,status,voorstel", [
    ("KEEP", "REJECTED", False), ("CHANGE", "ACCEPTED", True), ("HUMAN_REVIEW", "HUMAN_REVIEW", True),
    ("ongeldige actie", "HUMAN_REVIEW", True),
])
def test_centrale_herbeoordeling_met_volledige_herkomst(casus, actie, status, voorstel):
    u, _ = run(casus, actie)
    b = next(b for b in u.beslissingen if b.label == "C001")
    assert b.status.value == status
    assert u.meting["review_calls"] == 1
    assert any(v["tekst"] == casus[0]["tekst"] for v in u.voorstellen) is voorstel
    oud = next(b for b in u.meting["oorspronkelijke_beslissingen"] if b["label"] == "C001")
    assert oud["status"] == "REJECTED" and oud["reden"] == "geen annotatie"
    assert u.meting["resolutie"][0]["motivering"]


def test_geaccepteerde_norm_veroorzaakt_geen_extra_review(casus):
    u, _ = run(casus, norm="Rechtsbetrekking")
    assert not u.meting["twijfels"]
    assert not u.meting.get("review_calls")


def test_ontbrekende_context_gaat_direct_naar_mens(casus):
    u, _ = run(casus, context=BronContext(ontbreekt=("aangevraagde graafnode",)))
    assert not u.meting.get("review_calls")
    assert u.meting["per_status"]["HUMAN_REVIEW"] == 1
    assert u.meting["reviewload"]["juridisch"] == 1


def test_ongemotiveerde_bevestiging_wordt_geen_stille_afwijzing(casus):
    u, _ = run(casus, motivering="")
    assert u.meting["per_status"]["HUMAN_REVIEW"] == 1
    assert u.meting["reviewload"]["reviewer_contract_failure"] == 1


def test_exacte_klassegroepen_lekken_geen_keuzes(casus):
    for groep in batches(list(casus[1].kandidaten), "klasseverzameling"):
        enum = toolschema(groep)["input_schema"]["properties"]["beslissingen"]["items"]["properties"]["beslissing"]["enum"]
        assert all(set(enum) == set(k.toegestane_beslissingen()) for k in groep)


def test_korte_en_lange_tijdfunctie_worden_geen_dubbele_annotatie(casus):
    u, _ = run(casus, kort=True)
    assert [v["tekst"] for v in u.voorstellen if v["klasse"] == "Tijdsaanduiding"] == [
        "zes weken na de dagtekening van het aanslagbiljet"]
    assert u.meting["alternatieve_tijdgrenzen"]
    assert any(b.reden.startswith("DUBBELE_TIJD_FUNCTIE:") for b in u.beslissingen)


def test_context_is_geen_annotatiedoel_en_reist_naar_ieder_model(casus):
    # Synthetische context om de grens van het interne contract te testen.
    tekst = "Dit is uitsluitend synthetische context."
    p = ContextPassage(bron_iri="urn:test:context", tekst=tekst, bron_hash=tekst_hash(tekst), herkomst="graaf")
    u, fake = run(casus, context=BronContext(passages=(p,)))
    assert all(tekst in c["messages"][0]["content"] for c in fake.calls)
    assert all(a["bron_iri"] == casus[0]["bron_iri"] for v in u.voorstellen for a in v["ankers"])
    assert u.meting["broncontext"]["sha256"]
    with pytest.raises(ValueError):
        ContextPassage(**{**p.model_dump(), "herkomst": "xml"})
    with pytest.raises(ValueError):
        ContextPassage(**{**p.model_dump(), "tekst": tekst + " veranderd"})
    with pytest.raises(ValueError):
        BronContext(passages=(p, p))
