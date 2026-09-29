"""Bronbeleid, meetbetrouwbaarheid en transport; geen juridische gold-asserties."""
import copy
import json

import pytest

from agent.jas_pipeline.classificatie import toolschema, valideer
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import CandidateStatus
from agent.jas_pipeline.taal import SpacyProvider
from eval.onderzoek_invordering import (
    DOSSIER, conceptbereik, controleer_bronnen, controleer_concepten, speel,
)


@pytest.fixture(scope="module")
def pakket():
    return json.loads((DOSSIER / "bronnen.json").read_text())


@pytest.fixture(scope="module")
def concepten():
    return json.loads((DOSSIER / "concepten.json").read_text())


@pytest.fixture(scope="module")
def detecties(pakket):
    provider = SpacyProvider("nl_core_news_md")
    uit = {}
    for c in pakket["casussen"]:
        a = provider.analyseer(c["tekst"])
        if a.gedegradeerd:
            pytest.skip("nl_core_news_md vereist voor volledige onderzoeksreplay")
        uit[c["id"]] = fuseer(detecteer_alles(BronTekst.van_tekst(
            c["bron_iri"], c["tekst"], analyse=a, context=c["ouder_context"])))
    return uit


def test_graafherkomst_hashes_en_alle_klassen(pakket, concepten):
    controleer_bronnen(pakket)
    controleer_concepten(pakket, concepten)


@pytest.mark.parametrize("fout", ["xml", "tekst", "dubbel", "budget"])
def test_verkeerde_of_veranderde_bron_wordt_geweigerd(pakket, fout):
    p = copy.deepcopy(pakket)
    if fout == "xml":
        p["casussen"][0]["herkomst"] = "xml"
    elif fout == "tekst":
        p["casussen"][0]["tekst"] += " Gewijzigd."
    elif fout == "dubbel":
        p["contextpassages"].append(p["casussen"][0])
    else:
        p["contextbudget"]["gebruikt"] = 0
    with pytest.raises(ValueError):
        controleer_bronnen(p)


def test_verkeerde_offsets_en_onvolledige_klassenbeoordeling_falen(pakket, concepten):
    changed = copy.deepcopy(concepten)
    changed["IW-9-1"]["elementen"][0]["start"] += 1
    with pytest.raises(ValueError, match="exact bronfragment"):
        controleer_concepten(pakket, changed)
    changed = copy.deepcopy(concepten)
    del changed["LI-9.1"]["klassenbeoordeling"]["Rechtsfeit"]
    with pytest.raises(ValueError, match="dertien"):
        controleer_concepten(pakket, changed)


@pytest.mark.parametrize("cid,fragment,klasse", [
    ("IW-9-1", "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.", "Rechtsbetrekking"),
    ("IW-9-5", "Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn", "Voorwaarde"),
    ("LI-9.1", "voorlopige aanslagen", "Rechtsobject"),
    ("LI-9.5", "één maand", "Tijdsaanduiding"),
])
@pytest.mark.parametrize("review", [False, True])
def test_beschikbare_kandidaat_blijft_intact_tot_uitvoer(pakket, detecties, cid, fragment, klasse, review):
    c = next(c for c in pakket["casussen"] if c["id"] == cid)
    # Herhaalde fragmenten onderscheiden op positie; geen label van een andere casus hergebruiken.
    k = next(k for k in detecties[cid].kandidaten if k.span.tekst == fragment and klasse in k.possible_classes)
    uit, fake = speel(c, {k.label: klasse}, [k.label] if review else [])
    v = next(v for v in uit.voorstellen if v["trace"]["kandidaat"]["id"] == k.id)
    assert (v["tekst"], v["klasse"]) == (fragment, klasse)
    assert (v["ankers"][0]["start"], v["ankers"][0]["eind"]) == (k.span.start, k.span.eind)
    assert v["ankers"][0]["bron_iri"] == c["bron_iri"]
    assert v["trace"]["kandidaat"]["bewijs"]
    assert not any(b["ernst"] == "fout" for b in uit.meting["validatie"])
    assert uit.meting.get("review_calls", 0) == int(review)
    assert len(fake.calls) == 1 + int(review)


def test_optie_of_overlap_telt_niet_als_beschikbare_kern(detecties):
    f = detecties["IW-9-1"]
    k = next(k for k in f.kandidaten if k.span.tekst == "zes weken na de dagtekening van het aanslagbiljet")
    # Meet tegen alleen de lange kandidaat: de kern is een optie, geen zelfstandige kandidaat.
    e = {"id": "test", "status": "open", "start": 37, "eind": 46, "mogelijke_klassen": ["Tijdsaanduiding"]}
    [r] = conceptbereik([e], [k])
    assert r["kern"] == [] and r["klassen_op_kern"] == []
    assert r["optie"] == [k.label] and r["klassen_op_optie"] == ["Tijdsaanduiding"]


def test_batchgeldigheid_is_geen_kandidaatgeldigheid(detecties):
    ks = list(detecties["LI-9.5"].kandidaten)
    target = next(k for k in ks if k.span.tekst == "één maand")
    klasse = "Variabele en variabelewaarde"
    schema = toolschema(ks)
    assert klasse in schema["input_schema"]["properties"]["beslissingen"]["items"]["properties"]["beslissing"]["enum"]
    assert klasse not in target.possible_classes
    [b] = valideer([target], [{"kandidaat": target.label, "beslissing": klasse, "optie": ""}])
    assert b.status is CandidateStatus.UNCERTAIN
    assert b.reden == "CLASSIFIER_ONGELDIGE_KLASSE:" + klasse


def test_historische_replay_alleen_volledig_beschikbaar_voor_lid1(pakket, detecties):
    historie = json.loads((DOSSIER / "historische-sporen.json").read_text())
    assert not historie["IW-9-5"]["beslissingen"] and not historie["LI-9.5"]["beslissingen"]
    c = pakket["casussen"][0]
    oud = historie[c["id"]]
    uit, _ = speel(c, {b["label"]: b["klasse"] or "Geen annotatie" for b in oud["beslissingen"]})
    assert uit.meting["per_status"] == oud["run"]["instellingen"]["meting"]["per_status"]
    assert {(v["tekst"], v["klasse"]) for v in uit.voorstellen} == {(v["tekst"], v["klasse"]) for v in oud["elementen"]}
    assert not uit.meting["twijfels"]
