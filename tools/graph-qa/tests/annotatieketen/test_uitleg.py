"""De uitleg bij een voorstel: criterium + toepassing, en een reden per alternatief – uit data."""
from __future__ import annotations

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.taal import SpacyProvider
from agent.jas_pipeline.uitleg import reden_alternatief, toelichting

TEKST = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."


@pytest.fixture(scope="module")
def keten():
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("volledige parser vereist")
    f = fuseer(detecteer_alles(BronTekst.van_tekst("urn:t", TEKST, analyse=p.analyseer(TEKST))))
    bij: dict[str, list] = {}
    for b in f.bijdragen:
        bij.setdefault(b.kandidaat_id, []).append(b)
    return {k.span.tekst: (k, bij.get(k.id, [])) for k in f.kandidaten}


def test_toelichting_heeft_criterium_en_toepassing_zonder_ruwe_codes(keten):
    k, bij = keten["Een belastingaanslag"]
    t = toelichting(k, "Rechtsobject", "model", bij)
    assert t.startswith("Een rechtsobject is het voorwerp van een rechtsbetrekking en/of rechtsfeit. Hier: ")
    assert 'Document of rechtshandeling als ding ("belastingaanslag")' in t
    assert "THING_NP" not in t and "thing np" not in t
    assert toelichting(k, "Rechtsobject", "model", bij) == t          # deterministisch


def test_reden_per_alternatief_komt_uit_het_bewijs_van_die_klasse(keten):
    k, bij = keten["zes weken na de dagtekening van het aanslagbiljet"]
    reden = reden_alternatief("Rechtsfeit", "Tijdsaanduiding", bij)
    assert reden.startswith('aangedragen door Handeling als zelfstandig naamwoord ("dagtekening")')
    assert "ook mogelijk" not in reden


def test_een_tijdkern_noemt_de_langere_tijdsaanduiding(keten):
    k, bij = keten["zes weken"]
    assert reden_alternatief("Tijdsaanduiding", "Rechtsobject", bij).startswith(
        "aangedragen door Kern van dezelfde tijdsfunctie")


def test_zonder_bewijs_valt_de_reden_terug_op_het_profiel_of_een_vaste_zin():
    assert reden_alternatief("Rechtssubject", "Rechtsobject", []).startswith("beide naamwoordgroep")
    assert reden_alternatief("Operator", "Brondefinitie", []) == "ook mogelijk volgens de detectie"


def test_een_terugval_noemt_de_mogelijke_klassen(keten):
    k, bij = keten[TEKST]
    assert toelichting(k, "", "terugval", bij) == "Nog geen klasse gekozen; mogelijk: Rechtsbetrekking, Rechtsfeit."
