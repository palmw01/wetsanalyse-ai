"""Procestaal boven een scheidingslijn is geen antwoord (nameting #1274, K07)."""
from __future__ import annotations

import pytest

from agent.narratie import zonder_aanloop


def test_procestaal_boven_een_scheidingslijn_gaat_eraf():
    tekst = ("Nu heb ik de letterlijke tekst van alinea 148. Ik kan het antwoord nu opbouwen.\n\n---\n\n"
             "**Twee lagen van bestuurdersaansprakelijkheid**\n\nDe Kamerstukken onderscheiden twee lagen.")
    antwoord, aanloop = zonder_aanloop(tekst)
    assert antwoord.startswith("**Twee lagen") and aanloop.startswith("Nu heb ik")


@pytest.mark.parametrize("tekst", [
    "**Kort antwoord**\n\n---\n\nArtikel 36 regelt de aansprakelijkheid.",               # een kop, geen procestaal
    'De wet zegt "ik heb het recht" niet.\n\n---\n\nVerder.',                           # een citaat
    "Artikel 36 regelt de hoofdelijke aansprakelijkheid van bestuurders.\n\n---\n\nMeer.",  # geen eerste persoon
    "Ik heb dit gelezen. Zonder scheidingslijn blijft alles staan.",
])
def test_zonder_procestaal_of_zonder_lijn_blijft_de_tekst(tekst):
    assert zonder_aanloop(tekst) == (tekst, "")
