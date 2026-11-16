"""Drift-guard: de methodetekst in de code tegen de wetsanalyse-skill.

Waarom deze test bestaat. De dertien JAS-klassen dragen niet alleen een naam maar ook een
omschrijving, een herkenningsvraag en een uitdrukkingswijze — en dát is wat de annotatie-prompt
aan het model voorschotelt. Die duiding stond op twee plekken: leesbaar in de skill, en als
Python-strings in `agent/jas_klassen.py`. Alleen de namen waren bewaakt, dus de duiding liep
ongemerkt uit elkaar: de skill was op zeven plekken armer dan zijn eigen bron
(`docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md`), het zwaarst bij Delegatiebevoegdheid, waar vier
annotatie-relevante passages ontbraken.

Sinds die opschoning is de skill de bron en is het JAS_KLASSEN-blok afgeleid. Deze test bewaakt
dat: hij faalt zodra iemand de code met de hand bijwerkt of de markdown wijzigt zonder
`scripts/genereer_jas_klassen.py` te draaien.

Zelfde idioom als `test_jas_klassen.py` en `test_contract_drift.py`: één kopie, één guard ertegen.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.jas_klassen import JAS_KLASSEN, JAS_KLASSEN_VOLGORDE
from scripts.genereer_jas_klassen import (
    DOEL, REFERENTIE, ReferentieFout, bouw_blok, lees_klassen, vervang,
)

SKILL = REFERENTIE.parents[1] / "SKILL.md"


def test_referentie_en_skill_bestaan():
    """Zonder de skill kan de code niet worden afgeleid – zeg dat dan ook duidelijk."""
    assert REFERENTIE.exists(), f"skill-referentie ontbreekt: {REFERENTIE}"
    assert SKILL.exists(), f"SKILL.md ontbreekt: {SKILL}"


def test_jas_klassen_py_is_ongewijzigd_afgeleid_van_de_skill():
    """De drift-guard zelf: opnieuw genereren mag geen verschil opleveren."""
    huidig = DOEL.read_text(encoding="utf-8")
    verwacht = vervang(huidig, bouw_blok(lees_klassen()))
    assert verwacht == huidig, (
        "agent/jas_klassen.py loopt uit de pas met "
        f"{REFERENTIE.name}. Bewerk de markdown, niet de Python, en draai daarna:\n"
        "    .venv/bin/python scripts/genereer_jas_klassen.py"
    )


def test_referentie_dekt_precies_de_dertien_klassen_in_volgorde():
    namen = tuple(naam for naam, *_ in lees_klassen())
    assert namen == JAS_KLASSEN_VOLGORDE
    assert len(namen) == 13


def test_elke_klasse_draagt_alle_drie_de_bronvelden():
    """Een parse-regressie levert lege of afgekapte velden op; die mogen niet stil doorglippen.

    De ondergrens is bewust ruim: hij vangt 'leeg' en 'één woord', niet een bewuste inkorting.
    """
    for naam, omschrijving, vraag, uitdrukkingswijze in lees_klassen():
        for veld, waarde in (
            ("omschrijving", omschrijving), ("vraag", vraag),
            ("uitdrukkingswijze", uitdrukkingswijze),
        ):
            assert len(waarde) > 40, f"{naam}: veld {veld} is verdacht kort ({waarde!r})"


def test_skill_md_noemt_dezelfde_dertien_klassen():
    """De compacte tabel in SKILL.md is een derde drager van dezelfde namen."""
    tekst = SKILL.read_text(encoding="utf-8")
    for naam in JAS_KLASSEN_VOLGORDE:
        assert f"**{naam}**" in tekst, f"SKILL.md noemt de klasse {naam!r} niet in zijn tabel"


def test_generator_faalt_luid_bij_een_onleesbare_referentie(tmp_path: Path):
    """Half genereren is erger dan niet genereren."""
    leeg = tmp_path / "leeg.md"
    leeg.write_text("# geen klassen hier\n", encoding="utf-8")
    with pytest.raises(ReferentieFout):
        lees_klassen(leeg)
