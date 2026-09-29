"""Graafcasussen en gemarkeerde synthetische tegenproeven; geen juridische goldset."""
import json
from pathlib import Path

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.taal import SpacyProvider

DOSSIER = Path(__file__).resolve().parents[3] / "docs/wetsanalyse/onderzoek-invordering-2026-09-29"
CASES = {c["id"]: c for c in json.loads((DOSSIER / "bronnen.json").read_text())["casussen"]}


@pytest.fixture(scope="module")
def parser():
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("Een synthetische controle.").gedegradeerd:
        pytest.skip("volledige parser vereist")
    return p


def detect(tekst, parser=None):
    return fuseer(detecteer_alles(BronTekst.van_tekst(
        "urn:synthetische-controle", tekst, analyse=parser.analyseer(tekst) if parser else None)))


@pytest.mark.parametrize("verwijzing", ["artikel 9.1", "artikel 3:4", "art. 4"])
def test_afleiding_beschermt_notatie_en_stopt_bij_volgende_zin(verwijzing):
    zin = f"Volgens {verwijzing} bedraagt de vergoeding € 1.000."
    ks = detect(zin + " De aanvraag vervalt.").kandidaten
    ar = [k for k in ks if "Afleidingsregel" in k.possible_classes]
    assert [k.span.tekst for k in ar] == [zin]


@pytest.mark.parametrize("datum,geldig", [
    ("31 december", True), ("29 februari", True), ("29 februari 2024", True),
    ("29 februari 2025", False), ("31 februari", False), ("31 april", False),
    ("0 januari", False), ("1\u00a0januari 2027", True),
])
def test_synthetische_kalenderdatum(datum, geldig):
    ks = detect(f"De termijn eindigt op {datum}. Daarna vervalt het recht.").kandidaten
    dates = [k for k in ks if any(e.code == "TEMPORAL_DATE" for e in k.evidence)]
    assert [k.span.tekst for k in dates] == ([f"op {datum}"] if geldig else [])


def test_datums_op_herhaalde_offsets_blijven_afzonderlijk():
    c = CASES["LI-9.1"]
    ks = detect(c["tekst"]).kandidaten
    dates = [k for k in ks if any(e.code == "TEMPORAL_DATE" for e in k.evidence)]
    assert len(dates) == 2
    assert len({k.span.start for k in dates}) == 2
    assert all("31 december" in k.span.tekst for k in dates)
