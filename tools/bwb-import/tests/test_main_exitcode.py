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

from types import SimpleNamespace

import pytest

import app.main as main_module
from app.models import ImportResult, ImportSummary


def _summary(bwb_id: str, *, bron: int, graaf: int) -> ImportSummary:
    return ImportSummary(bwb_id=bwb_id, wetten=1, bron_tekens=bron, graaf_tekens=graaf)


@pytest.fixture
def nep_import(monkeypatch: pytest.MonkeyPatch):
    """Vervang de echte import door een die alleen de opgegeven dekking teruggeeft."""
    monkeypatch.setattr(
        main_module,
        "maak_writer",
        # Geen kaal object(): `run_imports` waarborgt na afloop de similarity-index.
        lambda settings: SimpleNamespace(ensure_similarity_index=lambda: None),
    )
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


# ------------------------------------------------- de graafwacht (--alleen-bij-verlies)
def _wacht_writer(monkeypatch: pytest.MonkeyPatch, compleet: bool) -> list[list[str]]:
    """Vervang de writer door één die alleen `graaf_is_compleet` beantwoordt; geeft de peilingen."""
    gepeild: list[list[str]] = []

    def peil(bwb_ids):
        gepeild.append(list(bwb_ids))
        return compleet

    monkeypatch.setattr(
        main_module, "maak_writer", lambda settings: SimpleNamespace(graaf_is_compleet=peil)
    )
    return gepeild


def test_graafwacht_importeert_niet_op_een_complete_graaf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Elk kwartier draaien mag niet elk kwartier overheid.nl bevragen."""
    gepeild = _wacht_writer(monkeypatch, compleet=True)
    monkeypatch.setattr(
        main_module, "run_imports", lambda *a, **k: pytest.fail("er is onnodig geïmporteerd")
    )
    assert main_module.main(["BWBR0004770", "BWBR0005537", "--alleen-bij-verlies"]) == 0
    assert gepeild == [["BWBR0004770", "BWBR0005537"]]


def test_graafwacht_importeert_wel_bij_verlies(monkeypatch: pytest.MonkeyPatch) -> None:
    """De storing van 8 sep 2026: GraphDB herstart leeg, en dan moet hij juist wél aan het werk."""
    _wacht_writer(monkeypatch, compleet=False)
    gedraaid: list[list[str]] = []

    def nep_import(bwb_ids, settings):
        gedraaid.append(list(bwb_ids))
        return [ImportResult(bwb_id=b, ok=True, overzicht=_summary(b, bron=10, graaf=10))
                for b in bwb_ids]

    monkeypatch.setattr(main_module, "run_imports", nep_import)
    assert main_module.main(["BWBR0004770", "--alleen-bij-verlies"]) == 0
    assert gedraaid == [["BWBR0004770"]]


def test_zonder_de_vlag_peilt_hij_niet(monkeypatch: pytest.MonkeyPatch) -> None:
    """De wekelijkse import haalt de wettekst op ook als de graaf compleet is."""
    monkeypatch.setattr(
        main_module,
        "maak_writer",
        lambda settings: SimpleNamespace(
            graaf_is_compleet=lambda ids: pytest.fail("de gewone import hoort niet te peilen")
        ),
    )
    monkeypatch.setattr(
        main_module,
        "run_imports",
        lambda ids, s: [ImportResult(bwb_id=b, ok=True, overzicht=_summary(b, bron=10, graaf=10))
                        for b in ids],
    )
    assert main_module.main(["BWBR0004770"]) == 0
