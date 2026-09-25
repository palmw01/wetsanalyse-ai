"""De vocabulaire in de api is gegenereerd uit de methode en loopt er niet van weg.

Wie een klasse, profiel, detectorregel of verklaring wijzigt, draait daarna
`python scripts/genereer_jas_vocabulaire.py`; anders faalt deze test (zelfde patroon als
`test_methode_drift.py` voor `jas_klassen.py`)."""
from __future__ import annotations

import pytest

pytest.importorskip("rdflib")


def test_de_vocabulaire_in_de_api_is_actueel():
    from scripts.genereer_jas_vocabulaire import main
    assert main(check=True) == 0, "draai: python scripts/genereer_jas_vocabulaire.py"


def test_slug_is_dezelfde_regel_als_in_de_api():
    from scripts.genereer_jas_vocabulaire import slug
    assert slug("Delegatiebevoegdheid en delegatie-invulling") == "DelegatiebevoegdheidEnDelegatieInvulling"
    assert slug("Variabele en variabelewaarde") == "VariabeleEnVariabelewaarde"
