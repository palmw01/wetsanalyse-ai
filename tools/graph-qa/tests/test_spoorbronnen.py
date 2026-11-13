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
        lees_argument="ecli", id_prefixen=("ECLI:",), rol_in_antwoord="een test",
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
    ("get_uitspraak", {"id": "ECLI:NL:GHARL:2023:5000"}, {"status": "ok", "aantal": 0},
     {"stuk": {"leesbaar": False}}, "ECLI:NL:GHARL:2023:5000 heeft geen tekst om te lezen"),
    ("get_kamerstuk", {"id": "kst-30322-3", "inhoud": True}, {"status": "ok", "aantal": 0},
     {"stuk": {"id": "kst-30322-3"}, "zonder_koppen": True, "alineas": 210}, "kst-30322-3 heeft geen koppen, 210 alinea’s"),
    ("get_bekendmaking", {"id": "stb-2009-610", "artikel": "99"}, {"status": "ok", "aantal": 0},
     {"stuk": {"id": "stb-2009-610"}}, ""),
])
def test_wat_de_bron_opleverde(tool, invoer, eind, data, regel):
    assert sb.uitkomstregel(tool, invoer, eind, data) == regel


def test_elke_reden_in_de_code_heeft_een_zin():
    """Een nieuwe reden zonder zin heet "gaf een fout": niet fout, wel nietszeggend voor de jurist."""
    bron = "\n".join(p.read_text(encoding="utf-8") for p in AGENT.rglob("*.py"))
    redenen = set(re.findall(r'fout\(\s*"([a-z_]+)"', bron)) | set(re.findall(r'"reden": "([a-z_]+)"', bron))
    redenen |= {"tool_mislukt", "tool_resultaat_te_groot"}
    # Geen toolresultaat: de bronstand (waarom een connector uit staat, of deze beurt niet meedoet: `bronkeuze`) en de
    # leesroute (geeft geen event).
    redenen -= {"aan", "straat", "niet_nodig", "tool_niet_toegestaan_in_leesroute"}
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


def test_een_connector_noemt_de_regeling_bij_naam_als_die_bekend_is(monkeypatch):
    from agent import overzicht
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [{"bwb_id": "BWBR0004770", "citeertitel": "Invorderingswet 1990"}])
    regel = sb.toolregel({"name": "zoek_uitspraken", "input": {"bwb_id": "BWBR0004770", "artikel": "36"}})
    assert regel == "zoekt uitspraken bij artikel 36 van Invorderingswet 1990"
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [])
    assert "BWBR0004770" in sb.toolregel({"name": "zoek_uitspraken", "input": {"bwb_id": "BWBR0004770", "artikel": "36"}})


def test_de_voorleesregel():
    assert sb.voorleesregel("get_bekendmaking", {"id": "stcrt-2025-22266"}, 7, True) == "stcrt-2025-22266 gelezen, 7 pagina’s"
    assert sb.voorleesregel("get_bekendmaking", {"id": "stcrt-2025-22266"}, 8, False) == (
        "stcrt-2025-22266 deels gelezen (8 pagina’s), er is meer dan dit")


#: Per connector met een leestool die de voorlezing doorleest: de leestool, haar argument en een id.
_VOORLEESVORMEN = [(c.leestool, c.lees_argument, c.voorbeeld_id) for c in bm.CONNECTORS.values()
                   if c.leestool and c.lees_argument and c.voorbeeld_id]


@pytest.mark.parametrize("tool,arg,ident", _VOORLEESVORMEN)
def test_een_doorgelezen_stuk_geeft_een_spoorregel(tool, arg, ident):
    """Iteratie bekendmakingen ronde 4, B21: de voorlezing las een stuk in zeven pagina's, en het spoor zei zes keer
    "deels gelezen, er is meer dan dit". Nu één regel per stuk, voor elke connector; één pagina meldt zich zoals eerst."""
    import json
    from types import SimpleNamespace
    from unittest.mock import patch

    from agent.nodes import bron_lezen as bl

    def pagina(offset: int, totaal: int, per: int = 30) -> dict:
        rijen = [{"nr": n + 1, "tekst": f"Alinea {n + 1}."} for n in range(offset, min(offset + per, totaal))]
        vervolg = {"tool": tool, "args": {arg: ident, "offset": offset + per}} if offset + per < totaal else None
        return {"status": "ok", "volledig": vervolg is None, "aantal": len(rijen), "totaal": totaal, "stuk": {"id": ident},
                "resultaten": rijen, **({"vervolg": vervolg} if vervolg else {})}

    def spoor(totaal: int) -> list[str]:
        events: list[dict] = []
        aanroepen: list[dict] = []

        def uitvoeren(b, state, writer, aanroep):
            aanroepen.append(aanroep)
            data = pagina(int(aanroep["input"].get("offset") or 0), totaal)
            return execute_tool(_Bouw(), state, writer, aanroep, operation=lambda: data)

        state = {"run_id": "r", "bron_lezen": [{"name": tool, "input": {arg: ident}}], "source_trace": []}
        with patch.object(bl, "execute_tool", uitvoeren), patch.object(bl, "get_stream_writer", return_value=events.append):
            bl.bron_lezen_node(SimpleNamespace(), state)
        eind = [e for e in events if e.get("type") == "tool_execution" and e["phase"] == "end"]
        assert len(eind) == len(aanroepen), "elke pagina blijft een tool_execution, voor eval en audit"
        return [e["message"] for e in events if e.get("type") == "status" and e.get("bron")]

    label = sb.bron_van(tool).label
    assert spoor(100) == [f"{label} · {ident} gelezen, 4 pagina’s"]
    assert spoor(20) == [], "één pagina, helemaal gelezen: niets te melden, zoals eerst"
    lang = bl.MAX_RIJEN_KORT + 10
    if tool in bl.HEEL_LEZEN:  # een artikel leest de code altijd helemaal
        assert spoor(lang) == [f"{label} · {ident} gelezen, {-(-lang // 30)} pagina’s"]
    else:
        assert spoor(lang) == [f"{label} · {ident} deels gelezen, er is meer dan dit"], "lang: één pagina"
