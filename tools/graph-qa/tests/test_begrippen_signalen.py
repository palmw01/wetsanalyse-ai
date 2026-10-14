"""Signalen uit definities en verwijzingen (ADR-004): bereik, wettelijke termen, richting."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

from agent.begrippen_pipeline import definities, signalen
from agent.begrippen_pipeline.model import Bron, Formulering, Manifest, Taalanalyse

W = "urn:bwb:BWBR0004770:artikel:"
PAKKET = Path(__file__).resolve().parents[1] / "agent" / "begrippen_pipeline"


def _f(eid: str, bron: Bron, tekst: str, n: int = 0) -> Formulering:
    i = -1
    for _ in range(n + 1):
        i = bron.tekst.index(tekst, i + 1)
    return Formulering(element_id=eid, bron_iri=bron.bron_iri, start=i, eind=i + len(tekst),
                       tekst=tekst, jas_klasse="Rechtsobject")


def _t(eid: str, term: str, *, beperkt=False, kern="", aanwijzend=False, ante=None) -> Taalanalyse:
    return Taalanalyse(element_id=eid, kern=kern or term.split()[-1], term=term, beperkt=beperkt,
                       aanwijzend=aanwijzend, antecedent_start=ante[0] if ante else None,
                       antecedent_eind=ante[1] if ante else None)


def _codes(sigs) -> set[tuple[str, str, str, str]]:
    return {(s.hypothese.value, s.van, s.naar, s.bewijs.code) for s in sigs}


@pytest.mark.parametrize("formule, soort, prefix", [
    ("Deze wet verstaat onder:", "regeling", "urn:bwb:BWBR0004770"),
    ("In deze wet en de daarop berustende bepalingen wordt verstaan onder:", "regeling", "urn:bwb:BWBR0004770"),
    ("In dit artikel wordt verstaan onder:", "artikel", W + "2"),
    ("Voor de toepassing van artikel 9 wordt verstaan onder:", "artikel", W + "9"),
    ("In dit lid wordt verstaan onder:", "lid", W + "2:lid:1"),
    ("In dit hoofdstuk wordt verstaan onder:", "onbekend", ""),
    ("Het volgende geldt:", "onbekend", ""),
])
def test_bereik_volgt_de_formule(formule, soort, prefix):
    b = definities.bereik_uit(formule, W + "2:lid:1:o:m")
    assert (b.soort, b.prefix) == (soort, prefix)


def test_bereik_omvat():
    b = definities.Bereik("artikel", W + "9")
    assert b.omvat(W + "9:lid:1") and b.omvat(W + "9") and not b.omvat(W + "90:lid:1")
    assert definities.Bereik("onbekend").omvat(W + "9") is None


@pytest.mark.parametrize("tekst, doel", [
    (", bedoeld in onderdeel c;", W + "2:lid:2:o:c"),
    (" als bedoeld in artikel 2, eerste lid, onderdeel m, is", W + "2:lid:1:o:m"),
    (" bedoeld in artikel 9", W + "9"),
    (" bedoeld in het eerste lid", W + "2:lid:1"),
    (" bedoeld in het honderdste lid", ""),           # onbekend rangtelwoord: niet raden
    (" die in onderdeel c staat", ""),
])
def test_verwijzing_na(tekst, doel):
    m = Manifest(bronnen=(Bron(bron_iri=W + "2:lid:2:o:d", tekst="x", bron_hash="h"),), formuleringen=())
    assert definities.verwijzing_na(m, W + "2:lid:2:o:d", tekst) == doel


def _iw():
    m_def = Bron(bron_iri=W + "2:lid:1:o:m", aanhef="Deze wet verstaat onder:", bron_hash="h1",
                 tekst="belastingaanslag: de voorlopige aanslag, de aanslag en de navorderingsaanslag;")
    lid3 = Bron(bron_iri=W + "2:lid:3", bron_hash="h3", tekst=(
        "Voor de toepassing van deze wet geldt, in afwijking in zoverre van het eerste en het "
        "tweede lid, als belastingaanslag:"))
    a91 = Bron(bron_iri=W + "9:lid:1", bron_hash="h9",
               tekst="Een belastingaanslag is invorderbaar zes weken na de dagtekening.")
    a911 = Bron(bron_iri=W + "9:lid:11", bron_hash="h11",
                tekst="In afwijking van het eerste lid is een belastingaanslag die een bedrag behelst niet invorderbaar.")
    elders = Bron(bron_iri="urn:bwb:BWBR0002320:artikel:1", bron_hash="hx",
                  tekst="De belastingaanslag wordt vastgesteld.")
    fs = [_f("def", m_def, "belastingaanslag"), _f("vl", m_def, "de voorlopige aanslag"),
          _f("aa", m_def, "de aanslag"), _f("na", m_def, "de navorderingsaanslag"),
          _f("l3", lid3, "belastingaanslag"), _f("u9", a91, "Een belastingaanslag"),
          _f("be", a911, "een belastingaanslag die een bedrag behelst"),
          _f("ex", elders, "De belastingaanslag")]
    taal = {"def": _t("def", "belastingaanslag"), "vl": _t("vl", "voorlopige aanslag"),
            "aa": _t("aa", "aanslag"), "na": _t("na", "navorderingsaanslag"),
            "l3": _t("l3", "belastingaanslag"), "u9": _t("u9", "belastingaanslag"),
            "be": _t("be", "belastingaanslag", beperkt=True, kern="belastingaanslag"),
            "ex": _t("ex", "belastingaanslag")}
    return Manifest(bronnen=(m_def, lid3, a91, a911, elders), formuleringen=tuple(fs)), taal


def test_wettelijke_termen_uit_definitie_en_opsomming():
    m, taal = _iw()
    wts = {(w.term, w.soort, w.anker, w.definitie_anker) for w in definities.wettelijke_termen(m, taal)}
    assert ("belastingaanslag", "definitie", "def", "") in wts
    assert {("voorlopige aanslag", "opsomming", "vl", "def"), ("aanslag", "opsomming", "aa", "def"),
            ("navorderingsaanslag", "opsomming", "na", "def")} <= wts


def test_signalen_op_een_kleine_wet():
    m, taal = _iw()
    s = _codes(signalen.alle(m, taal))
    assert ("zelfde_betekenis", "def", "u9", "WETTELIJKE_TERM") in s
    assert ("hierarchie", "def", "aa", "OPSOMMING_IN_DEFINITIE") in s     # soort, geen synoniem
    assert ("hierarchie", "def", "be", "BEPERKTE_TERM") in s
    assert not any(c[1:3] == ("be", "def") or c[1:3] == ("def", "be") for c in s
                   if c[0] == "zelfde_betekenis")                        # beperkt ≠ zelfde
    assert ("zelfde_betekenis", "def", "l3", "AFWIJKENDE_KWALIFICATIE") in s
    assert ("zelfde_betekenis", "def", "ex", "BUITEN_BEREIK") in s        # andere wet


def test_kop_in_definitie_maakt_geen_synoniem_van_de_soort():
    m, taal = _iw()
    s = _codes(signalen.alle(m, taal))
    assert not any(c[0] == "zelfde_betekenis" and {"def", "aa"} == {c[1], c[2]} for c in s)


def test_alle_codes_hebben_een_verklaring_en_omgekeerd():
    verkl = yaml.safe_load((PAKKET / "verklaringen.yaml").read_text())["signalen"]
    gebruikt = set()
    for py in PAKKET.glob("*.py"):
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_b" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                gebruikt.add(node.args[0].value)
    assert gebruikt, "geen codes gevonden – is de helper hernoemd?"
    assert gebruikt <= set(verkl), f"zonder verklaring: {gebruikt - set(verkl)}"
    assert set(verkl) <= gebruikt, f"verklaring zonder code: {set(verkl) - gebruikt}"
    assert all(re.fullmatch(r"[A-Z_]+", c) for c in verkl)


# --- op de referentieset, met de echte parser ------------------------------------------------

@pytest.fixture(scope="module")
def ref_signalen():
    pytest.importorskip("spacy")
    from agent.begrippen_pipeline.taal import analyseer
    from agent.jas_pipeline.taal.provider import SpacyProvider
    from eval import begrippen_eval as be
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd (uv sync --extra nlp)")
    bronnen, cases, _ = be.laad()
    m = be.manifest_uit(bronnen, cases)
    return _codes(signalen.alle(m, analyseer(m, p)))


@pytest.mark.parametrize("verwacht", [
    ("zelfde_betekenis", "f01", "f24", "AANWIJZEND"),            # "die belastingaanslag" via "als bedoeld in"
    ("zelfde_betekenis", "f09", "f25", "BEDOELD_IN"),            # "bedoeld in onderdeel c"
    ("inclusie", "f08", "f09", "MEDE_VERSTAAN"),
    ("inclusie", "f10", "f11", "MEDE_VERSTAAN"),
    ("zelfde_betekenis", "f01", "f08", "UITBREIDING_MEDE"),
    ("zelfde_betekenis", "f02", "f17", "WETTELIJKE_TERM"),       # term uit een opsomming
    ("hierarchie", "f01", "f20", "BEPERKTE_TERM"),
    ("zelfde_betekenis", "f01", "f22", "AFWIJKENDE_KWALIFICATIE"),
])
def test_referentieset_kerngevallen(ref_signalen, verwacht):
    assert verwacht in ref_signalen


def test_referentieset_homoniem_krijgt_alleen_zwak_bewijs(ref_signalen):
    termijnen = {c[3] for c in ref_signalen if {c[1], c[2]} == {"f18", "f19"}}
    assert termijnen == {"ZELFDE_TERM"}
