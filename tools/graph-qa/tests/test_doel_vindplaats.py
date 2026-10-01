"""Regressie: een mislukte fetch-call mag het doel van een annotatiebeurt niet bepalen.

Het scenario. Een jurist vraagt "annoteer artikel 6 van BWBR0019237, neem ook de onderdelen
mee". De onderdelen zijn niet als bepaling op te halen, dus de agent probeert het met de IRI-vorm:
`get_bepaling(BWBR0019237, "artikel:6:lid:1:o:c")`. Die call faalt — maar `dispatch` geeft een
ongeldige aanduiding als tekst terug in plaats van te crashen, dus de beurt loopt door. En
`_doel_uit_toolcalls` leest de INPUT van de fetch-calls, niet het resultaat; zonder filter wordt
die kapotte aanduiding het doel, met markeringen onder een vindplaats die de werkplek per definitie
niet kan openen. De fout ontstaat in de agent en wordt zichtbaar bij de jurist, twee stappen
verderop.

Deze test legt de eerste helft van de bescherming vast: het doel slaat mislukte calls over. De
tweede helft – een ongeldige vindplaats breekt de beurt – zit in `bronmodel.resolve`; een
terugval op de tool-trace is er niet.
"""
from __future__ import annotations

import pytest

from agent.doel import _doel_uit_toolcalls, _is_vindplaats


def _call(naam: str, **inp) -> dict:
    return {"role": "assistant", "content": [{"type": "tool_use", "name": naam, "input": inp}]}


def test_iri_achtervoegsel_is_geen_vindplaats():
    assert not _is_vindplaats("artikel:6:lid:1:o:c")
    assert not _is_vindplaats("")


@pytest.mark.parametrize("aanduiding", ["6", "22a", "9.1"])
def test_gewone_aanduidingen_blijven_geldig(aanduiding: str):
    assert _is_vindplaats(aanduiding)


def test_mislukte_call_kaapt_het_doel_niet():
    """Precies het productiescenario: geldige calls, daarna drie pogingen met een IRI-achtervoegsel."""
    messages = [
        _call("get_artikel", bwb_id="BWBR0019237", artikel="6"),
        _call("get_lid", bwb_id="BWBR0019237", artikel="6", lid="1"),
        _call("get_bepaling", bwb_id="BWBR0019237", nummer="artikel:6:lid:1:o:a"),
        _call("get_bepaling", bwb_id="BWBR0019237", nummer="artikel:6:lid:1:o:c"),
    ]
    doel = _doel_uit_toolcalls(messages)
    assert doel["artikel"] == "6", "de laatste GELDIGE fetch hoort te winnen"
    assert doel["lid"] == "1"
    assert "o:c" not in doel["artikel"]


def test_zonder_enige_geldige_call_blijft_het_doel_leeg():
    """Liever geen doel dan een kapot doel – dan valt de beurt terug op de JSON van het model."""
    doel = _doel_uit_toolcalls([_call("get_bepaling", bwb_id="BWBR0019237", nummer="artikel:6:lid:1:o:c")])
    assert doel["artikel"] == ""
    assert doel["bwbId"] == ""


