"""De exitcode van `main()`, en daarmee of de import-job rood wordt.

De dekkingsmeting bestond al, maar stond alleen in de logs — en daar keek niemand naar. Dat is
precies hoe elf Leidraad-artikelen (10.052 tekens) anderhalve maand konden ontbreken. Deze tests
leggen vast dat een dip zich meldt, dat de ontsnapping werkt, en dat de bestaande betekenis van
exitcode 1 niet verschuift.

Waarom exitcode 2 en niet 1: een 1 betekent dat een wet niet geschreven is, een 2 dat alles
geschreven is maar dat er tekst ontbreekt ten opzichte van de bron. `write_wet` doet de named-graph
PUT vóórdat er iets te meten valt, dus een 2 kost nooit data — het is een signaal. In het logboek
van een gefaalde job wil je dat verschil zonder zoeken zien.
"""
from __future__ import annotations

import pytest

import app.main as main_module
from app.models import ImportSummary


def _summary(bwb_id: str, *, bron: int, graaf: int) -> ImportSummary:
    return ImportSummary(bwb_id=bwb_id, wetten=1, bron_tekens=bron, graaf_tekens=graaf)


@pytest.fixture
def nep_import(monkeypatch: pytest.MonkeyPatch):
    """Vervang de echte import door een die alleen de opgegeven dekking teruggeeft."""
    monkeypatch.setattr(main_module, "maak_writer", lambda settings: object())
    monkeypatch.setattr(main_module, "prepare", lambda writer: None)

    def stel_in(dekkingen: dict[str, tuple[int, int]], stuk: set[str] | None = None) -> None:
        # De naad zit sinds de fasesplitsing op `_verzamel`/`_schrijf` in plaats van op
        # `run_import`: `run_imports` verzamelt eerst álle wetten en schrijft daarna pas, zodat een
        # verwijzing naar een structuurdeel van een andere wet in dezelfde run oplosbaar is.
        from types import SimpleNamespace

        from app.collect import Batch

        def _verzamel(bwb_id, settings):
            if stuk and bwb_id in stuk:
                raise RuntimeError("kapot")
            bron, graaf = dekkingen[bwb_id]
            return SimpleNamespace(
                wet=SimpleNamespace(bwb_id=bwb_id), wti=None, batch=Batch(),
                summary=_summary(bwb_id, bron=bron, graaf=graaf), xml_path=None,
            )

        monkeypatch.setattr(main_module, "_verzamel", _verzamel)
        monkeypatch.setattr(main_module, "_schrijf", lambda item, writer, index: item.summary)

    return stel_in


def test_volle_dekking_geeft_nul(nep_import) -> None:
    nep_import({"BWBR0004770": (1000, 1000), "BWBR0024096": (1000, 1042)})
    assert main_module.main(["BWBR0004770", "BWBR0024096"]) == 0


def test_dip_geeft_exitcode_twee_en_noemt_de_regeling(nep_import, capsys) -> None:
    """De verhouding van de Leidraad toen de elf artikelen ontbraken: 498.243 / 506.251 = 98,4%."""
    nep_import({"BWBR0004770": (1000, 1000), "BWBR0024096": (506251, 498243)})
    assert main_module.main(["BWBR0004770", "BWBR0024096"]) == 2
    uit = capsys.readouterr().out
    assert "Tekstdekking onder de drempel" in uit
    assert "BWBR0024096" in uit
    assert "ZAKT" in uit
    # De regeling die het wél haalt staat er ter vergelijking bij, maar niet als tekort.
    assert "BWBR0004770" in uit


def test_mislukte_import_blijft_exitcode_een(nep_import) -> None:
    """Een niet-geschreven wet weegt zwaarder dan een dekkingsdip en houdt zijn eigen code."""
    nep_import({"BWBR0004770": (1000, 1000), "SLECHT": (0, 0)}, stuk={"SLECHT"})
    assert main_module.main(["BWBR0004770", "SLECHT"]) == 1


def test_drempel_nul_zet_de_controle_uit(nep_import, monkeypatch: pytest.MonkeyPatch) -> None:
    """De ontsnapping: een regeling die legitiem lager meet mag de job niet blijven breken."""
    monkeypatch.setenv("BWB_MIN_DEKKING", "0")
    nep_import({"BWBR0024096": (506251, 498243)})
    assert main_module.main(["BWBR0024096"]) == 0


def test_onleesbare_drempel_zet_de_controle_niet_uit(
    nep_import, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Een tikfout in de bicep mag geen stille uitschakeling zijn — dan denk je dat je meet."""
    monkeypatch.setenv("BWB_MIN_DEKKING", "nul-komma-negen")
    nep_import({"BWBR0024096": (506251, 498243)})
    assert main_module.main(["BWBR0024096"]) == 2


def test_zonder_meting_geen_dekkingsfout(nep_import) -> None:
    """`bron_tekens == 0` betekent dat de meting niet lukte, niet dat er tekst ontbreekt."""
    nep_import({"BWBR0004770": (0, 0)})
    assert main_module.main(["BWBR0004770"]) == 0
