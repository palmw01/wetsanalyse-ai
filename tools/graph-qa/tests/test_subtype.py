"""JAS-subtype: alleen bij eenduidig bewijs, anders leeg – nooit geraden."""
from __future__ import annotations

import pytest

from agent.jas_pipeline.subtype import DEL, PAR, VAR, bepaal
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
    # Andere klassen hebben geen subtype.
    ("Tijdsaanduiding", {"TEMPORAL_DATE"}, ""),
    (DEL, set(), ""),
])
def test_subtype(klasse, codes, verwacht):
    assert bepaal(klasse, codes) == verwacht


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
