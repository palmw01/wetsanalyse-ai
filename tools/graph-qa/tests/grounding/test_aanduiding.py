"""De vindplaats in woorden: een divisie van een beleidsregel is geen artikel en heeft geen leden."""
from __future__ import annotations

from agent.annotatie import aanduiding_in_woorden


def test_vindplaats_noemt_een_divisie_geen_artikel():
    """"art. 25.1 lid 2" is een vindplaats die niet bestaat: een divisie heeft geen leden."""
    assert aanduiding_in_woorden("9", "1", "Artikel") == "art. 9 lid 1"
    assert aanduiding_in_woorden("25", "", "Divisie") == "bepaling 25"
    assert aanduiding_in_woorden("25", "25.1.1", "Divisie") == "bepaling 25, 25.1.1"
    # Onbekend soort valt terug op wat er stond — bij de zes wet-achtige regelingen is dat juist.
    assert aanduiding_in_woorden("9", "1", "") == "art. 9 lid 1"
