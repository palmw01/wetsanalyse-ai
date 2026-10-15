"""De taalstap van de begrippenketen (ADR-004): kern, term, beperking, kop en terugverwijzing."""
from __future__ import annotations

import pytest

from agent.begrippen_pipeline.taal import analyseer
from agent.jas_pipeline.taal.provider import NullProvider, SpacyProvider
from eval import begrippen_eval as be


@pytest.fixture(scope="module")
def manifest():
    bronnen, cases, _ = be.laad()
    return be.manifest_uit(bronnen, cases)


@pytest.fixture(scope="module")
def spacy_md():
    pytest.importorskip("spacy")
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd (uv sync --extra nlp)")
    return p


@pytest.fixture(scope="module")
def taal(manifest, spacy_md):
    return analyseer(manifest, spacy_md)


@pytest.mark.parametrize("eid, term", [
    ("f01", "belastingaanslag"), ("f12", "belastingaanslag"),     # lidwoord valt weg
    ("f02", "voorlopige aanslag"), ("f17", "voorlopige aanslag"), # vast bijvoeglijk naamwoord blijft
    ("f03", "aanslag"),
    ("f18", "termijn"), ("f19", "termijn"),                       # lemma: zelfde term, andere betekenis
    ("f06", "belastingschuldige"),                                # bij spaCy een ADJ; telt als kern
    ("f09", "beschikking of uitspraak"), ("f25", "beschikking of uitspraak"),
    ("f11", "kennisgeving"),                                      # "van de beschikking …" hoort er niet bij
])
def test_term(taal, eid, term):
    assert taal[eid].term == term


@pytest.mark.parametrize("eid, beperkt", [
    ("f20", True),    # "… die een uit te betalen bedrag behelst"
    ("f11", True),    # "… van de beschikking of de uitspraak"
    ("f21", True),    # "met een belastingaanslag gelijkgestelde …"
    ("f09", False),   # nevenschikking beperkt niet
    ("f25", False),   # "bedoeld in onderdeel c" is een verwijzing
    ("f12", False),
])
def test_beperking(taal, eid, beperkt):
    assert taal[eid].beperkt is beperkt


def test_kop_van_samenstelling_alleen_als_hij_in_het_werkgebied_voorkomt(taal):
    assert taal["f04"].kop == "aanslag"        # "aanslag" is zelf een kern (f03)
    assert taal["f01"].kop == "aanslag"
    assert taal["f10"].kop == ""               # "biljet" komt niet als kern voor


def test_aanwijzende_formulering_wijst_terug_naar_dezelfde_kern(taal, manifest):
    t = taal["f24"]
    assert t.aanwijzend
    bron = manifest.bron(manifest.formulering("f24").bron_iri)
    assert bron.tekst[t.antecedent_start:t.antecedent_eind] == "een belastingaanslag"
    assert t.antecedent_eind <= manifest.formulering("f24").start


def test_deterministisch(manifest, spacy_md):
    assert analyseer(manifest, spacy_md) == analyseer(manifest, spacy_md)


def test_zonder_parser_gedegradeerd_maar_bruikbaar(manifest):
    taal = analyseer(manifest, NullProvider())
    assert all(t.gedegradeerd for t in taal.values())
    assert taal["f12"].term == "belastingaanslag"
    assert taal["f24"].aanwijzend and taal["f24"].antecedent_start is None
    assert all(t.kop == "" and not t.beperkt for t in taal.values())
