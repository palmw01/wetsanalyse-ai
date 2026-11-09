"""Het register van spoorbronnen: wat Lex doet en wat de bron opleverde, in het denkproces (9 nov 2026).

Het tweede blok onder het antwoord ("Graaf geraadpleegd · N aanroepen") verdween; wat de jurist eruit nodig had staat nu
als regel in het denkproces. Deze tests bewaken dat elke tool een bron, een werkwoord en een zoek/lees-indeling heeft,
dat een nieuwe connector er zonder code bij komt, en dat er nooit een toolnaam, JSON of foutcode in de tekst staat.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from bronmodel import connectors as bm

from agent import overzicht, spoorbronnen as sb
from agent.resultaat import REDEN_ZIN
from agent.tool_execution import execute_tool
from agent.tools import TOOLS
from agent.tools.jas_tools import JAS_TOOL_NAMEN

AGENT = Path(__file__).resolve().parents[1] / "agent"
#: Namen die de code zelf aan `execute_tool` geeft, zonder dat ze in `TOOLS` staan.
IN_CODE = {"get_bronnode", "get_annotatieweergave"}


def _alle_tools() -> set[str]:
    return {t["name"] for t in TOOLS} | set(JAS_TOOL_NAMEN) | IN_CODE


def test_elke_tool_hoort_bij_precies_een_bron_en_zoekt_of_leest():
    for tool in sorted(_alle_tools()):
        bij = [b.naam for b in sb.bronnen() if tool in b.tools]
        assert len(bij) == 1, f"{tool}: bij {bij or 'geen bron'}"
    for b in sb.bronnen():
        assert not (b.zoektools & b.leestools), f"{b.naam}: zoekt én leest"
        assert set(b.werkwoorden) == b.tools, f"{b.naam}: werkwoorden en tools lopen uiteen"


def test_elke_aanroep_in_code_noemt_een_bekende_tool():
    """Een naam die de code aan `execute_tool` geeft maar die geen bron heeft, kreeg "raadpleegt de kennisgraaf"."""
    gevonden = set()
    for pad in AGENT.rglob("*.py"):
        gevonden |= set(re.findall(r'\{"name": "(\w+)", "input"', pad.read_text(encoding="utf-8")))
    assert gevonden <= _alle_tools(), gevonden - _alle_tools()


def test_elke_tool_heeft_een_werkwoord_zonder_gaten_of_toolnaam(monkeypatch):
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [])
    for tool in sorted(_alle_tools()):
        for invoer in ({}, {"bwb_id": "BWBR1", "artikel": "1", "query": "x", "id": "kst-1-2", "klasse": "Voorwaarde"}):
            regel = sb.toolregel({"name": tool, "input": invoer})
            assert regel and regel != "raadpleegt de kennisgraaf", tool
            assert "{" not in regel and "_" not in regel, (tool, regel)


def test_de_klasse_staat_in_het_werkwoord():
    assert sb.toolregel({"name": "search_annotaties", "input": {"jas_klassen": ["Rechtssubject"]}}) == \
        "zoekt in de annotaties naar Rechtssubject"
    assert sb.toolregel({"name": "search_annotaties", "input": {}}) == "zoekt in de annotaties"


def test_dezelfde_regel_als_de_connectorbeschrijving():
    """De interne bronnen kiezen hun vorm zoals `ConnectorBeschrijving.werkwoord`: naast elkaar op dezelfde vormen."""
    for c in bm.CONNECTORS.values():
        for tool, vormen in c.werkwoorden.items():
            for invoer in ({}, {"id": "kst-1"}, {"dossier": "33755"}, {"woorden": "rente"}, {"tabel": "2", "id": "kst-1"}):
                assert sb.kies_vorm(vormen, invoer) == c.werkwoord(tool, invoer), (tool, invoer)


def test_een_nieuwe_connector_komt_er_zonder_code_bij(monkeypatch):
    nep = bm.ConnectorBeschrijving(
        naam="testbron", label="Testbron", brontype="uitspraak", groep="Uitspraken", dekt="uitspraken",
        signalen=(r"\btestgerecht\b",), tools=frozenset({"zoek_testbron", "lees_testbron"}), leestool="lees_testbron",
        lees_argument="ecli", id_prefixen=("ECLI:",), specialisten=frozenset({"duiding"}), rol_in_antwoord="een test",
        kop_in_antwoord="Uit de test", levert=("uitspraken",), niet_in_tekst=(), grenzen="alleen een test",
        werkwoorden={"zoek_testbron": ("zoekt uitspraken over „{zoekterm}”", "zoekt uitspraken"),
                     "lees_testbron": ("leest uitspraak {ecli}", "leest een uitspraak")},
        beheer="Een nep-connector.", voorbeeldvragen=("Wat zei het testgerecht?",))
    monkeypatch.setitem(bm.CONNECTORS, nep.naam, nep)

    bron = sb.bron_van("zoek_testbron")
    assert bron is not None and bron.label == "Testbron" and sb.bron_van("lees_testbron") == bron
    assert sb.toolregel({"name": "zoek_testbron", "input": {"zoekterm": "rente"}}) == "zoekt uitspraken over „rente”"
    assert sb.uitkomstregel("zoek_testbron", {}, {"status": "ok", "aantal": 3}) == "3 gevonden"
    assert sb.uitkomstregel("lees_testbron", {"ecli": "ECLI:NL:HR:1"}, {"status": "ok", "aantal": 9, "has_more": True}) \
        == "ECLI:NL:HR:1 deels gelezen, er is meer dan dit"


@pytest.mark.parametrize(("tool", "invoer", "eind", "data", "regel"), [
    ("zoek_kamerstukken", {}, {"status": "ok", "aantal": 16, "has_more": False}, {}, "16 gevonden"),
    ("search_begrippen", {}, {"status": "ok", "aantal": 0, "has_more": False}, {}, "niets gevonden"),
    ("zoek_kamerstukken", {}, {"status": "ok", "aantal": 10, "has_more": True}, {"totaal": 1218}, "10 van 1.218 gevonden"),
    ("search_wetgeving", {}, {"status": "ok", "aantal": 20, "has_more": True}, {}, "20 gevonden, er is meer dan dit"),
    ("get_kamerstuk", {"id": "kst-33755-3"}, {"status": "ok", "aantal": 7, "has_more": True}, {},
     "kst-33755-3 deels gelezen, er is meer dan dit"),
    ("get_artikel", {"artikel": "29"}, {"status": "ok", "aantal": 0, "has_more": False}, {}, ""),
    ("get_lid", {}, {"status": "ok", "aantal": 3, "has_more": True}, {}, "deels gelezen, er is meer dan dit"),
    ("zoek_kamerstukken", {}, {"status": "error", "foutcode": "bron_onbereikbaar"}, {}, "niet bereikbaar"),
    ("get_lid", {}, {"status": "unavailable", "foutcode": "tool_mislukt"}, {}, "mislukt"),
    ("get_lid", {}, {"status": "error", "foutcode": "iets_onbekends"}, {}, "gaf een fout"),
    ("get_annotatiedekking", {}, {"status": "ok"}, {"peilmoment": "2026-11-09T19:31:08Z"}, ""),
])
def test_wat_de_bron_opleverde(tool, invoer, eind, data, regel):
    assert sb.uitkomstregel(tool, invoer, eind, data) == regel


def test_elke_reden_in_de_code_heeft_een_zin():
    """Een nieuwe reden zonder zin heet "gaf een fout": niet fout, wel nietszeggend voor de jurist."""
    bron = "\n".join(p.read_text(encoding="utf-8") for p in AGENT.rglob("*.py"))
    redenen = set(re.findall(r'fout\(\s*"([a-z_]+)"', bron)) | set(re.findall(r'"reden": "([a-z_]+)"', bron))
    redenen |= {"tool_mislukt", "tool_resultaat_te_groot"}
    # Geen toolresultaat: de bronstand (waarom een connector uit staat) en de leesroute (geeft geen event).
    redenen -= {"straat", "tool_niet_toegestaan_in_leesroute"}
    assert redenen <= set(REDEN_ZIN), redenen - set(REDEN_ZIN)


class _Graaf:
    def close(self): ...


class _Bouw:
    graph = _Graaf()
    annotaties = None
    begrippen = None
    settings = None


def test_execute_tool_meldt_de_uitkomst_met_de_bron_als_actor():
    events: list[dict] = []
    tool = {"id": "c1", "name": "zoek_kamerstukken", "input": {"dossier": "33755"}}
    execute_tool(_Bouw(), {"run_id": "r"}, events.append, tool,
                 operation=lambda: {"status": "ok", "volledig": True, "aantal": 2, "resultaten": [{"id": "a"}, {"id": "b"}]})
    eind = [e for e in events if e.get("type") == "tool_execution" and e["phase"] == "end"]
    assert eind and eind[0]["bron"] == "kamerstukken"
    status = [e for e in events if e.get("type") == "status"]
    assert status == [{"type": "status", "message": "Kamerstukken · 2 gevonden", "bron": "kamerstukken"}]


def test_een_lees_zonder_iets_te_melden_geeft_geen_regel():
    events: list[dict] = []
    execute_tool(_Bouw(), {"run_id": "r"}, events.append, {"id": "c2", "name": "get_lid", "input": {}},
                 operation=lambda: {"status": "ok", "volledig": True, "aantal": 0, "resultaten": []})
    assert not [e for e in events if e.get("type") == "status"]


def test_geen_toolnaam_json_of_code_in_een_regel():
    regels = [sb.uitkomstregel(t, {}, {"status": s, "aantal": 1, "has_more": True, "foutcode": f}, {})
              for t in sorted(_alle_tools()) for s, f in (("ok", ""), ("error", "bron_onbereikbaar"), ("error", "x_y"))]
    for regel in regels:
        assert not re.search(r"[{}\[\]_]|\bms\b", regel), regel
