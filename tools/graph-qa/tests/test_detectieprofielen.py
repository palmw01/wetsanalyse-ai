"""Detectieprofielen (ADR-001 PR 4): volledig, herleidbaar naar H2-JAS.md en zonder eigen JAS-definities."""
from __future__ import annotations

import re

import pytest

from agent.jas_klassen import JAS_KLASSEN, JAS_KLASSEN_VOLGORDE, REGELS, RegelType
from agent.jas_pipeline.profielen import H2, ProfielFout, laad, referentietekst, casustekst

H2_REGELS = H2.read_text(encoding="utf-8").splitlines()
_VELDLABEL = {"omschrijving": "**omschrijving klasse**", "vraag": "**vraag**",
              "uitdrukkingswijze": "**uitdrukkingswijze**"}

# De zestien officiële begrippen uit de JAS-tabel (wa-table.png, H2:79/88/124).
OFFICIELE_BEGRIPPEN = {
    "Rechtssubject", "Rechtsobject", "Rechtsbetrekking", "Rechtsfeit", "Voorwaarde",
    "Afleidingsregel", "Variabele", "Variabelewaarde", "Parameter", "Parameterwaarde", "Operator",
    "Tijdsaanduiding", "Plaatsaanduiding", "Delegatiebevoegdheid", "Delegatie-invulling",
    "Brondefinitie",
}


def _sectie_van(regelnummer: int) -> str:
    """De ###-kop waaronder een regel van H2-JAS.md valt."""
    for regel in reversed(H2_REGELS[:regelnummer]):
        if regel.startswith("### "):
            return regel[4:].strip()
    return ""


def test_elke_jas_klasse_heeft_precies_een_profiel():
    assert list(laad()) == list(JAS_KLASSEN_VOLGORDE)


def test_de_zestien_officiele_begrippen_zijn_gedekt_met_subtype_bij_de_paren():
    begrippen = {b["naam"]: b["subtype"] for p in laad().values() for b in p.begrippen}
    assert set(begrippen) == OFFICIELE_BEGRIPPEN
    for paar in (("Variabele", "Variabelewaarde"), ("Parameter", "Parameterwaarde"),
                 ("Delegatiebevoegdheid", "Delegatie-invulling")):
        assert all(begrippen[b] for b in paar) and begrippen[paar[0]] != begrippen[paar[1]]


@pytest.mark.parametrize("klasse", JAS_KLASSEN_VOLGORDE)
def test_bronverwijzingen_wijzen_naar_het_juiste_veld_van_de_juiste_klasse(klasse):
    """De drift-guard: een H2-verwijzing die verschuift of naar een andere klasse wijst, faalt hier."""
    p = laad()[klasse]
    kop = klasse.split(" ")[0]              # "Variabele en variabelewaarde" → sectie "Variabele(waarde)"
    for veld, ref in p.bron.items():
        nummer = int(re.fullmatch(r"H2:(\d+)", ref).group(1))
        assert _VELDLABEL[veld] in H2_REGELS[nummer - 1], f"{klasse} {veld} → {ref}"
        assert _sectie_van(nummer).startswith(kop), f"{ref} valt onder {_sectie_van(nummer)!r}"


def test_officiele_tekst_komt_uit_jas_klassen_en_niet_uit_het_profiel():
    officieel = {k.naam: k for k in JAS_KLASSEN}
    for naam, p in laad().items():
        assert p.official_definition == officieel[naam].omschrijving
        assert p.official_recognition_intent == officieel[naam].vraag
        assert p.official_expression_patterns == officieel[naam].uitdrukkingswijze
        assert "omschrijving" not in p.data and "vraag" not in p.data


def test_elke_testcasus_is_letterlijk_en_komt_niet_uit_held_out():
    for p in laad().values():
        assert p.test_cases, f"{p.jas_class} heeft geen testcasussen"
        for t in p.test_cases:
            assert t["span"] in casustekst(t), f"{p.jas_class}: {t['span']!r} staat niet in de tekst"
            if t["status"] == "synthetic":
                # Een zelfgemaakte zin draagt de herkomst van wat hij toetst: een uitdrukkingswijze
                # uit H2, of een negatief patroon dat een projectregel is (ADR-001 §3E) – nooit JAS.
                assert re.fullmatch(r"H2:\d+|adr-001:[a-z-]+", str(t.get("bron", ""))), t


def test_held_out_referentie_wordt_geweigerd():
    with pytest.raises(ProfielFout):
        referentietekst("BW01")


def test_prioriteitsregels_staan_in_beide_profielen():
    """JAS-PRIORITY-001/002 (H2:107, H2:116): de verwarring staat bij winnaar én verliezer."""
    profielen = laad()
    for regel in (r for r in REGELS if r.type == RegelType.PRIORITEIT):
        rang = dict(regel.priority)
        winnaar = max(rang, key=rang.get)
        for verliezer in (k for k in regel.applies_to if k != winnaar):
            for van, naar in ((winnaar, verliezer), (verliezer, winnaar)):
                assert any(c["klasse"] == naar and c.get("regel") == regel.id
                           for c in profielen[van].confusable_classes), f"{van} → {naar} mist {regel.id}"


def test_kandidaatregels_zijn_uniek():
    ids = [r["id"] for p in laad().values() for r in p.candidate_rules]
    assert len(ids) == len(set(ids))


def test_elk_profiel_zegt_waar_het_model_nog_nodig_is():
    for p in laad().values():
        assert p.llm_needed_for and p.negative_patterns is not None and p.required_context
