"""JAS-subtype: alleen bij eenduidig bewijs, anders leeg – nooit geraden."""
from __future__ import annotations

import json

import pytest

from agent.jas_pipeline.kandidaten import Evidence
from agent.jas_pipeline.subtype import DEL, PAR, TIJD, VAR, VERBIJZONDERT_PARAMETER, bepaal, codes_van
from agent.jas_pipeline.verklaringen import laad


@pytest.mark.parametrize("klasse, codes, verwacht", [
    (VAR, {"MONEY_AMOUNT"}, "variabelewaarde"),
    (VAR, {"PROPERTY_NOUN"}, "variabele"),
    (PAR, {"PERCENTAGE", "NORMATIVE_PREDICATE"}, "parameterwaarde"),
    (PAR, {"PARAMETER_NOUN"}, "parameter"),
    (DEL, {"DELEGATION_FORMULA"}, "delegatiebevoegdheid"),
    # Geen bewijs, of bewijs voor beide: onbepaald.
    (VAR, {"OBJECT_NP"}, ""),
    (VAR, {"MONEY_AMOUNT", "PROPERTY_NOUN"}, ""),
    (PAR, {"PARAMETER_NOUN", "MONEY_AMOUNT"}, ""),
    (PAR, {"DURATION_NUMBER"}, "parameterwaarde"),
    # Tijdsaanduiding: een duur of hoeveelheid verbijzondert een parameter (H2:107, ADR-001 PR 8).
    (TIJD, {"TEMPORAL_DURATION"}, VERBIJZONDERT_PARAMETER),
    (TIJD, {"TEMPORAL_PERIOD_OF", "OBJECT_NP"}, VERBIJZONDERT_PARAMETER),
    (TIJD, {"TEMPORAL_RECURRENCE"}, VERBIJZONDERT_PARAMETER),
    # Een datum, een periodewoord of een relatieve periode zonder telwoord zegt het niet eenduidig.
    (TIJD, {"TEMPORAL_DATE"}, ""),
    (TIJD, {"TEMPORAL_PERIOD_NOUN"}, ""),
    (TIJD, {"TEMPORAL_RELATIVE_PERIOD"}, ""),
    (TIJD, {"TEMPORAL_KERNEL"}, ""),
    # Duurbewijs op een andere klasse zet niets: het subtype hoort bij de Tijdsaanduiding.
    (PAR, {"TEMPORAL_DURATION"}, ""),
    ("Rechtsobject", {"TEMPORAL_DURATION"}, ""),
    # Andere klassen hebben geen subtype.
    ("Plaatsaanduiding", {"LOCATION_NAME"}, ""),
    (DEL, set(), ""),
])
def test_subtype(klasse, codes, verwacht):
    assert bepaal(klasse, codes) == verwacht


def test_een_tijdkern_erft_het_duurbewijs_van_zijn_ouder():
    """De kern 'zes weken' van 'zes weken na …' draagt alleen TEMPORAL_KERNEL; de codes van de ouder staan in het
    detail en wijzen het subtype aan. Een kern van een datum blijft leeg."""
    def kern(*codes):
        return Evidence(detector="fusie", code="TEMPORAL_KERNEL",
                        detail=json.dumps({"ouder": "x", "codes": list(codes)}))
    assert bepaal(TIJD, codes_van([kern("TEMPORAL_DURATION")])) == VERBIJZONDERT_PARAMETER
    assert bepaal(TIJD, codes_van([kern("TEMPORAL_DATE")])) == ""
    # Een kapot detail valt niet om en wijst niets aan.
    assert codes_van([Evidence(detector="fusie", code="TEMPORAL_KERNEL", detail="geen json")]) == ["TEMPORAL_KERNEL"]


def test_alle_subtypen_omvat_wat_de_regels_kunnen_zetten():
    from agent.jas_pipeline.subtype import ALLE_SUBTYPEN, REGELS, VERBIJZONDERINGEN
    gezet = {s for regels in REGELS.values() for s, _ in regels}
    assert gezet <= set(ALLE_SUBTYPEN) and len(set(ALLE_SUBTYPEN)) == len(ALLE_SUBTYPEN)
    assert set(ALLE_SUBTYPEN) - gezet == {"delegatie-invulling"}  # vraagt de graaf, de keten zet het niet
    assert set(VERBIJZONDERINGEN) <= set(ALLE_SUBTYPEN)


@pytest.mark.parametrize("tekst, verwacht", [
    # Het boekvoorbeeld: de tijdsaanduiding verbijzondert een parameter, het getal is een geneste parameterwaarde.
    ("Het bericht wordt binnen 48 uur bevestigd.",
     {("binnen 48 uur", TIJD, VERBIJZONDERT_PARAMETER), ("48", PAR, "parameterwaarde")}),
    # Een duur in woorden: één element, geen los getal en geen tweede markering (IW01, JAS-PRIORITY-001).
    ("Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.",
     {("zes weken na de dagtekening van het aanslagbiljet", TIJD, VERBIJZONDERT_PARAMETER)}),
    # Een datum verbijzondert niet eenduidig, en zijn dagnummer is geen getal in een duur.
    ("Deze wet treedt in werking op 1 september 2009.", {("op 1 september 2009", TIJD, "")}),
])
def test_door_de_detectoren(tekst, verwacht):
    """Detectie → fusie → specificiteit → deterministisch besluit → subtype, zonder model en zonder parse."""
    from agent.jas_pipeline.besluit import deterministisch
    from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
    from agent.jas_pipeline.fusie import fuseer

    gevonden = set()
    for k in fuseer(detecteer_alles(BronTekst.van_tekst("urn:t", tekst))).kandidaten:
        b = deterministisch(k)
        if b and b.klasse in {TIJD, PAR}:
            gevonden.add((k.span.tekst, b.klasse, bepaal(b.klasse, codes_van(k.evidence))))
    assert gevonden == verwacht


def test_elke_aanwijzende_code_bestaat_in_de_catalogus():
    from agent.jas_pipeline.subtype import REGELS
    bekend = set(laad()["detectie"])
    for regels in REGELS.values():
        for _subtype, codes in regels:
            assert codes <= bekend, codes - bekend


def test_de_keten_zet_het_subtype_op_het_element():
    """Door de hele keten: een bedrag dat het model als Parameter classificeert, krijgt het subtype
    parameterwaarde; het fragment zonder waardebewijs blijft onbepaald."""
    from test_bronnode_keten import L1, ROWS, ReadApi, run, snapshot
    from agent.agent import answer_stream
    from fakes import FakeGraph, KetenLLM, make_settings

    tekst = "De dwangsom bedraagt € 23 per dag."
    rows = [{**r, "tekst": tekst} if r["node"] == L1 else r for r in ROWS]
    llm = KetenLLM(kies=lambda toegestaan, f: PAR if PAR in toegestaan and "23" in f and len(f) < 20
                   else toegestaan[0])
    events = run(answer_stream("annoteer lid 1", doel={"bron_iri": L1}, llm=llm, graph=FakeGraph(result=rows),
                               annotaties=ReadApi(snapshot(L1, rows)), settings=make_settings(),
                               run_id="r", user_id="j"))
    elementen = [e["element"] for e in events if e["type"] == "element"]
    bedrag = [e for e in elementen if e["klasse"] == PAR and "23" in e["tekst"]]
    assert bedrag and bedrag[0]["jas_subtype"] == "parameterwaarde", elementen
    assert all(e["jas_subtype"] == "" for e in elementen if e["klasse"] not in {PAR, VAR, DEL})
