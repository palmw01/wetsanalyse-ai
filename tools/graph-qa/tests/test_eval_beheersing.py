"""De eval moet begrensd, te volgen en eerlijk over storingen zijn.

Achtergrond: de run van 5 sep 2026 liep twee uur, werd door de job-timeout afgekapt en eindigde
rood. De oorzaak lag bij de provider (`overloaded_error` + timeouts), niet bij de agent — maar in
het rapport was dat niet te zien: één case las als "9/10 geslaagd", oftewel als een inhoudelijke
fout. Deze tests leggen de drie eigenschappen vast die dat voortaan voorkomen.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from eval.run_eval import print_annotatie_report, run_annotatie_suite
from eval.scoring import is_infrastructuurfout, score_annotatie


def _case(prompt="annoteer artikel 9 lid 1 van de Invorderingswet 1990", bron="X"):
    return {"prompt": prompt, "bron": bron, "verwacht": [], "kanaries": []}


# --- storing is geen regressie -------------------------------------------------

@pytest.mark.parametrize(
    ("bericht", "soort"),
    [
        ("Er ging iets mis bij het beantwoorden.", "APIStatusError"),
        ("De modelprovider is momenteel overbelast.", None),
        ("Ik kon de modelprovider niet bereiken.", None),
        ("anthropic.APITimeoutError: Request timed out", None),
    ],
)
def test_providerfout_telt_als_niet_gemeten(bericht, soort):
    r = score_annotatie(_case(), [], "", "", bericht, fout_soort=soort)
    assert r.niet_gemeten is True
    assert r.passed is False  # niet geslaagd, maar ook niet als gezakt te lezen


def test_inhoudelijke_fout_blijft_gewoon_gezakt():
    """Alleen de infrastructuur krijgt deze uitweg; een echte fout niet."""
    r = score_annotatie(_case(), [], "", "", "fragment staat niet letterlijk in de bron",
                        fout_soort="ValueError")
    assert r.niet_gemeten is False
    assert r.passed is False


def test_de_exceptienaam_is_de_betrouwbare_bron():
    """`answer_stream` saniteert de melding voor de jurist; de naam zegt wat er echt gebeurde."""
    assert is_infrastructuurfout("Er ging iets mis bij het beantwoorden.") is False
    assert is_infrastructuurfout("Er ging iets mis bij het beantwoorden.", "APIStatusError") is True


def test_exitcode_kijkt_alleen_naar_gemeten_cases(capsys):
    """Een storing mag de run niet rood maken; een échte fout wél."""
    goed = score_annotatie(_case(), [], "", "", None)
    storing = score_annotatie(_case(), [], "", "", "x", fout_soort="APITimeoutError")
    assert print_annotatie_report([goed, storing]) is True
    uit = capsys.readouterr().out
    assert "1 niet gemeten" in uit and "geen oordeel over de analyse" in uit

    kapot = score_annotatie(_case(), [], "", "", "iets inhoudelijks", fout_soort="ValueError")
    assert print_annotatie_report([goed, kapot]) is False


def test_alles_ongemeten_is_niet_groen(capsys):
    """Niets gemeten is geen goedkeuring — dezelfde regel als bij grounding 'onbepaald'."""
    storing = score_annotatie(_case(), [], "", "", "x", fout_soort="APIStatusError")
    assert print_annotatie_report([storing, storing]) is False
    assert "GEEN ENKELE CASE GEMETEN" in capsys.readouterr().out


# --- begrenzing en voortgang ---------------------------------------------------

def test_tijdbudget_slaat_de_rest_over_in_plaats_van_door_te_lopen(monkeypatch, capsys):
    """De vangrail die voorkomt dat de job-timeout de meting afkapt.

    Bij afkapping is er géén rapport en is zelfs de log al deels uit het venster verdwenen; bij een
    budgetstop staat er een leesbaar, onvolledig rapport.
    """
    import eval.run_eval as mod

    async def traag(case, *, settings, llm=None, graph=None, meter=None):
        return score_annotatie(case, [], "", "", None)

    monkeypatch.setattr(mod, "run_annotatie_case", traag)
    # De klok vervangen in de namespace van run_eval, niet op de stdlib-module: dat laatste is
    # globaal en raakt alles wat in deze testsessie de tijd leest.
    tijden = iter([0.0] + [10_000.0] * 20)  # de eerste case draait, daarna is het budget op
    monkeypatch.setattr(mod, "time", SimpleNamespace(monotonic=lambda: next(tijden, 10_000.0)))

    cases = [_case(bron=f"B{i}") for i in range(4)]
    res = asyncio.run(run_annotatie_suite(cases, settings=None, minuten=1.0))

    assert len(res) == 4, "elke case houdt een rij in het rapport"
    assert res[0].niet_gemeten is False
    assert all(r.niet_gemeten for r in res[1:]), "overgeslagen cases zijn niet gemeten, niet gezakt"
    assert "tijdbudget bereikt" in capsys.readouterr().out


def test_voortgang_wordt_per_case_gemeld(monkeypatch, capsys):
    """Zonder deze regels is een lopende run in de container een zwarte doos."""
    import eval.run_eval as mod

    async def snel(case, *, settings, llm=None, graph=None, meter=None):
        return score_annotatie(case, [], "", "", None)

    monkeypatch.setattr(mod, "run_annotatie_case", snel)
    asyncio.run(run_annotatie_suite([_case(bron="BWBR0004770/9/1")], settings=None))
    uit = capsys.readouterr().out
    assert "[1/1]" in uit and "BWBR0004770/9/1" in uit and "markeringen" in uit
    assert "suite klaar" in uit and "tokens" in uit
