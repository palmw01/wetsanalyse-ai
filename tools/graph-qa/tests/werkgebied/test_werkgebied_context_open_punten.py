"""De open punten in het dossier van Lex (L-X-1): welke lezing gekozen is en wat nog open staat, zodat een volgend
gesprek daarop voortbouwt. Een werkgebied zonder open punten geeft dezelfde tekst als eerst."""
from __future__ import annotations

from agent.werkgebied_context import MAX_OPEN_PUNTEN, context_tekst

WG = {"naam": "Termijnen", "analysevraag": "Wanneer is een aanslag invorderbaar?"}


def test_zonder_open_punten_blijft_de_tekst_gelijk():
    assert context_tekst(WG) == context_tekst({**WG, "open_punten": {"telling": {}, "punten": []}})


def test_een_gekozen_lezing_en_wat_nog_te_toetsen_is():
    punten = [{"soort": "interpretatiekeuze", "soort_naam": "interpretatiekeuze", "status": "gekozen",
               "vraag": "Saldering per termijn of over het jaar?", "gekozen": "B", "methode": "wetshistorisch",
               "gekozen_lezing": "Over het jaar.", "nog_te_toetsen": ["jurisprudentie"]},
              {"soort": "onderzoekspunt", "soort_naam": "onderzoekspunt", "status": "open",
               "vraag": "Geldt lid 5 ook voor het winstaandeel?", "nog_te_toetsen": []}]
    tekst = context_tekst({**WG, "open_punten": {"punten": punten}})
    assert "Open punten (de jurist kiest; leg voor, kies niet zelf):" in tekst
    assert ("- interpretatiekeuze (gekozen: B, wetshistorisch): Saldering per termijn of over het jaar? → Over het "
            "jaar.; nog te toetsen: jurisprudentie") in tekst
    assert "- onderzoekspunt (open): Geldt lid 5 ook voor het winstaandeel?" in tekst


def test_te_veel_open_punten_worden_geteld():
    punten = [{"soort_naam": "onderzoekspunt", "status": "open", "vraag": f"Vraag {i}?"} for i in range(20)]
    tekst = context_tekst({**WG, "open_punten": {"punten": punten, "afgekapt": 3}})
    assert f"Vraag {MAX_OPEN_PUNTEN - 1}?" in tekst and f"Vraag {MAX_OPEN_PUNTEN}?" not in tekst
    assert f"(en {20 - MAX_OPEN_PUNTEN + 3} meer)" in tekst
