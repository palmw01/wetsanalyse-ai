"""De exitcode van `main()`, en daarmee of de import-job rood wordt.

De dekkingsmeting bestond al, maar stond alleen in de logs — en daar keek niemand naar. Dat is
precies hoe elf Leidraad-artikelen (10.052 tekens) anderhalve maand konden ontbreken. Deze tests
leggen vast dat een dip zich meldt, dat de ontsnapping werkt, en dat de bestaande betekenis van
exitcode 1 niet verschuift.

Waarom exitcode 2 en niet 1: een 1 betekent dat een wet niet gelezen of geschreven kon worden, een 2
dat de importpoort aansloeg op de inhoud. De poort beslist vóór de named-graph PUT en vervangt nooit
door minder, dus een 2 kost nooit data. In het logboek van een gefaalde job wil je dat verschil
zonder zoeken zien.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.main as main_module
from app.dekking import Stand
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
        lambda settings: SimpleNamespace(
            ensure_similarity_index=lambda: None, graaf_stand=lambda bwb_ids: {}
        ),
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
        monkeypatch.setattr(main_module, "_schrijf", lambda item, writer, *_indexen: item.summary)

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
    """GraphDB herstart leeg, en dan moet de graafwacht juist wél aan het werk."""
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


# ------------------------------------------------- de importpoort, door `_schrijf` heen
class _PoortWriter:
    """Een writer zonder GraphDB: bouwt een graph met `tekens` tekens en onthoudt elke PUT."""

    def __init__(self, tekens: int) -> None:
        self._tekens = tekens
        self.puts: list[str] = []
        self.similarity = 0

    def build_graph(self, wet, **_kw):
        return object(), ImportSummary(bwb_id=wet.bwb_id, wetten=1)

    def tel_tekens(self, graph) -> int:
        return self._tekens

    def vervang_wet(self, bwb_id, graph) -> None:
        self.puts.append(bwb_id)

    def ensure_similarity_index(self) -> None:
        self.similarity += 1


def _instellingen(*, wti: bool = False, drempel: float = 0.995) -> SimpleNamespace:
    return SimpleNamespace(min_dekking=drempel, import_wti=wti)


def _item(bwb_id: str = "BWBR0005537", *, wti=None, xsd=None) -> SimpleNamespace:
    return SimpleNamespace(
        wet=SimpleNamespace(bwb_id=bwb_id), wti=wti, batch=None, summary=None, xml_path=None,
        xsd_geldig=xsd,
    )


def _schrijf(
    monkeypatch: pytest.MonkeyPatch, writer, stand: Stand, *, bron: int, item=None, instellingen=None
):
    monkeypatch.setattr(main_module, "bron_tekens", lambda _pad: bron)
    item = item or _item()
    return main_module._schrijf(
        item, writer, {}, set(), {item.wet.bwb_id: stand}, instellingen or _instellingen()
    )


def test_dip_vervangt_een_rijkere_graph_niet(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _PoortWriter(tekens=800)
    summary = _schrijf(monkeypatch, writer, Stand(tekens=1000), bron=1000)
    assert writer.puts == []
    assert summary.tegengehouden is True
    assert "blijft staan" in (summary.poort or "")


def test_dip_vult_een_lege_graaf_wel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Na een GraphDB-herstart is een onvolledige wet beter dan geen wet, en de job wordt toch rood."""
    writer = _PoortWriter(tekens=800)
    summary = _schrijf(monkeypatch, writer, Stand(), bron=1000)
    assert writer.puts == ["BWBR0005537"]
    assert summary.tegengehouden is False
    assert summary.poort is not None


def test_dip_die_niet_achteruitgaat_wordt_geschreven(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dezelfde onvolledige graph opnieuw schrijven kost niets en houdt de tekst actueel."""
    writer = _PoortWriter(tekens=800)
    _schrijf(monkeypatch, writer, Stand(tekens=800), bron=1000)
    assert writer.puts == ["BWBR0005537"]


def test_lege_toestand_wordt_nooit_geschreven(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ook niet op een lege graaf: een graph zonder tekst liet de graafwacht vroeger gerust."""
    writer = _PoortWriter(tekens=0)
    with pytest.raises(main_module.LegeToestand):
        _schrijf(monkeypatch, writer, Stand(), bron=1000)
    assert writer.puts == []


def test_mislukte_wti_vervangt_geen_verrijkte_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _PoortWriter(tekens=1000)
    summary = _schrijf(
        monkeypatch, writer, Stand(tekens=1000, wti=True), bron=1000,
        instellingen=_instellingen(wti=True),
    )
    assert writer.puts == []
    assert summary.tegengehouden is True


def test_mislukte_wti_vult_een_graph_zonder_verrijking_wel(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _PoortWriter(tekens=1000)
    summary = _schrijf(
        monkeypatch, writer, Stand(), bron=1000, instellingen=_instellingen(wti=True)
    )
    assert writer.puts == ["BWBR0005537"]
    assert summary.poort is not None


def test_wti_uit_is_geen_mislukking(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _PoortWriter(tekens=1000)
    summary = _schrijf(monkeypatch, writer, Stand(tekens=1000, wti=True), bron=1000)
    assert writer.puts == ["BWBR0005537"]
    assert summary.poort is None


def test_mislukte_meting_mag_niet_krimpen(monkeypatch: pytest.MonkeyPatch) -> None:
    def kapot(_pad):
        raise OSError("onleesbaar")

    writer = _PoortWriter(tekens=800)
    monkeypatch.setattr(main_module, "bron_tekens", kapot)
    item = _item()
    summary = main_module._schrijf(
        item, writer, {}, set(), {"BWBR0005537": Stand(tekens=1000)}, _instellingen()
    )
    assert writer.puts == []
    assert summary.tegengehouden is True


def test_mislukte_meting_zonder_krimp_schrijft_zonder_signaal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = _PoortWriter(tekens=1000)
    summary = _schrijf(monkeypatch, writer, Stand(tekens=1000), bron=0)
    assert writer.puts == ["BWBR0005537"]
    assert summary.poort is None


def test_xsd_uitslag_is_een_signaal_en_blokkeert_niet(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _PoortWriter(tekens=1000)
    summary = _schrijf(monkeypatch, writer, Stand(), bron=1000, item=_item(xsd=False))
    assert writer.puts == ["BWBR0005537"]
    assert summary.xsd_geldig is False


def _batch(monkeypatch: pytest.MonkeyPatch, writer, stand) -> None:
    writer.graaf_stand = stand
    monkeypatch.setattr(main_module, "maak_writer", lambda settings: writer)
    monkeypatch.setattr(main_module, "prepare", lambda writer: None)
    monkeypatch.setattr(main_module, "_verzamel", lambda bwb_id, settings: _item(bwb_id))
    monkeypatch.setattr(main_module, "structuurindex", lambda batches: {})
    monkeypatch.setattr(main_module, "bepalingsindex", lambda batches: set())
    monkeypatch.setattr(main_module, "bron_tekens", lambda _pad: 1000)


def test_tegengehouden_wet_geeft_exitcode_twee(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    writer = _PoortWriter(tekens=800)
    _batch(monkeypatch, writer, lambda ids: {b: Stand(tekens=1000) for b in ids})
    assert main_module.main(["BWBR0005537"]) == 2
    assert writer.puts == []
    # Er is niets geschreven, dus ook geen reden om de similarity-index aan te raken.
    assert writer.similarity == 0
    assert "NIET GESCHREVEN" in capsys.readouterr().out


def test_lege_toestand_geeft_exitcode_een(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _PoortWriter(tekens=0)
    _batch(monkeypatch, writer, lambda ids: {})
    assert main_module.main(["BWBR0005537"]) == 1


def test_falende_standquery_schrijft_niets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Terugvallen op "er staat niets" zou de poort stil openzetten."""

    def faal(_ids):
        raise OSError("graaf weg")

    writer = _PoortWriter(tekens=1000)
    _batch(monkeypatch, writer, faal)
    with pytest.raises(OSError):
        main_module.run_imports(["BWBR0005537"], settings=_instellingen())
    assert writer.puts == []


def test_resultaat_noemt_tegengehouden_als_status() -> None:
    summary = ImportSummary(bwb_id="X", tegengehouden=True)
    assert ImportResult(bwb_id="X", ok=True, overzicht=summary).as_dict()["status"] == "tegengehouden"
