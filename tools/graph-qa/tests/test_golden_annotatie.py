"""Guard: de gouden annotatieset tegen de letterlijke wettekst.

Waarom deze test bestaat. `golden_annotatie.jsonl` is het ijkpunt waartegen elke wijziging aan de
annotatieketen wordt afgemeten, en de matching is **exact**: `precisie_en_recall` doet een
set-doorsnede op `(klasse, genormaliseerd fragment)` (`eval/scoring.py:162-178`). Eén komma
verschil, één typografische apostrof of één hoofdletter in de klassenaam, en het anker matcht nooit
meer — zonder dat er iets rood wordt, want precisie en recall zitten niet in `passed`
(`eval/scoring.py:407-417`). Een verzonnen of overgetypt fragment zakt dus stilzwijgend weg als
"de agent vond het niet", en dat is precies de fout die je niet wilt maken in een meetinstrument.

`bronteksten.json` legt daarom de letterlijke lid-tekst vast zoals `tools/bwb-import` die in de
graaf zet — dezelfde tekst waartegen de live-eval scoort. Deze test bindt de set daaraan.

Zelfde idioom als `test_jas_klassen.py` en `test_methode_drift.py`: één kopie, één guard ertegen.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.jas_klassen import GELDIGE_JAS_KLASSEN
from eval.scoring import _norm

EVAL = Path(__file__).resolve().parents[1] / "eval"
GOLDEN = EVAL / "golden_annotatie.jsonl"
BRONTEKSTEN = EVAL / "bronteksten.json"


def _cases() -> list[dict]:
    regels = [r for r in GOLDEN.read_text(encoding="utf-8").splitlines()
              if r.strip() and not r.startswith("#")]
    return [json.loads(r) for r in regels]


def _bronteksten() -> dict[str, str]:
    return json.loads(BRONTEKSTEN.read_text(encoding="utf-8"))["bepalingen"]


def test_bestanden_bestaan_en_parsen():
    assert GOLDEN.exists() and BRONTEKSTEN.exists()
    cases = _cases()
    assert cases, "de gouden set is leeg"
    assert _bronteksten(), "bronteksten.json bevat geen bepalingen"


def test_elke_case_heeft_een_prompt_en_kanaries():
    """Zonder `kanaries` meet `injectie_weerstaan` niets: `any()` over een lege lijst is False,
    dus de case slaagt altijd op dat punt (`eval/scoring.py:377-385`). Dat is een garantie die
    stilzwijgend verdwijnt."""
    for c in _cases():
        assert c.get("prompt"), f"case zonder prompt: {c}"
        assert c.get("kanaries"), f"case zonder kanaries: {c['prompt']!r}"


def test_elk_anker_staat_letterlijk_in_de_brontekst():
    bron = _bronteksten()
    ontbreekt = []
    for c in _cases():
        if not c.get("verwacht"):
            continue
        sleutel = c.get("bron")
        assert sleutel, f"case met verwachtingen maar zonder `bron`: {c['prompt']!r}"
        assert sleutel in bron, f"onbekende bron-sleutel {sleutel!r} in {c['prompt']!r}"
        tekst = _norm(bron[sleutel])
        for el in c["verwacht"]:
            if _norm(el["tekst"]) not in tekst:
                ontbreekt.append(f"{sleutel}: {el['klasse']} – {el['tekst']!r}")
    assert not ontbreekt, (
        "deze ankers staan niet letterlijk in bronteksten.json:\n  " + "\n  ".join(ontbreekt)
        + "\nNeem het fragment over uit de brontekst; overtypen gaat mis op interpunctie."
    )


def test_elke_klasse_bestaat_met_exacte_casing():
    """`_paar` doet `.strip()` op de klasse maar géén `.lower()` (`eval/scoring.py:158`), dus
    'rechtssubject' matcht nooit met 'Rechtssubject'."""
    fout = [
        f"{c['prompt'][:40]}… → {el['klasse']!r}"
        for c in _cases() for el in c.get("verwacht", [])
        if el["klasse"] not in GELDIGE_JAS_KLASSEN
    ]
    assert not fout, "onbekende of verkeerd gespelde JAS-klassen:\n  " + "\n  ".join(fout)


def test_geen_anker_begint_met_het_lidnummer():
    """Het annotatiecorpus plakt `"{lid}. "` vóór de tekst (`agent/artikel.py:105`). Een anker dat
    daarmee begint staat wél in het corpus maar niet in de lid-tekst, en dan meet de guard hierboven
    iets anders dan de eval."""
    fout = [
        f"{c['prompt'][:40]}… → {el['tekst'][:40]!r}"
        for c in _cases() for el in c.get("verwacht", [])
        if el["tekst"][:3].strip().rstrip(".").isdigit()
    ]
    assert not fout, "ankers die met een lidnummer beginnen:\n  " + "\n  ".join(fout)


def test_ankers_zijn_onderling_onderscheidend():
    """`_koppel` claimt in pas 3 op token-IoU **zonder drempel** (`eval/scoring.py:267-278`): één
    gedeeld woord volstaat om een gold-element weg te kapen. Een anker dat alleen uit functiewoorden
    bestaat maakt `span_iou` en `classification_accuracy` daardoor onbetrouwbaar."""
    STOP = {"de", "het", "een", "van", "en", "of", "in", "op", "te", "dat", "die", "voor"}
    fout = [
        f"{c['prompt'][:40]}… → {el['tekst']!r}"
        for c in _cases() for el in c.get("verwacht", [])
        if set(_norm(el["tekst"]).split()) <= STOP
    ]
    assert not fout, "ankers zonder onderscheidend woord:\n  " + "\n  ".join(fout)


@pytest.mark.parametrize("veld", ["verwacht", "kanaries"])
def test_velden_hebben_het_verwachte_type(veld: str):
    for c in _cases():
        assert isinstance(c.get(veld, []), list), f"{c['prompt']!r}: {veld} is geen lijst"
