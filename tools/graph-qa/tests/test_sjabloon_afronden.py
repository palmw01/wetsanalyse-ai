"""Afronden met een sjabloon na een vondst van een bronconnector (ADR-008, ADR-013): één schrijfronde, en meetbaar.

Iteratie wetgeving_live ronde 4 (12 nov 2026), en bij alle connectors: de rol zei "antwoord in tekst" bij elke vraag die
om meer gaat dan de wettekst, en daarna vroeg de code alsnog om het sjabloon. Elk antwoord werd zo twee keer geschreven
(~20–25k tokens per vraag), en het verzoek ("wijs de gevonden stukken aan") zette een lijst onder een telling of opbouw
die niet gevraagd was (I13, I30). Wat er met de sjablonen gebeurde, stond alleen in de logs.

Het mechanisme, voor elke connector:
- staat er een connector aan, dan zegt de prompt dat een antwoord na een vondst met het sjabloon afrondt, en dat
  'stukken' alleen een lijst is als de vraag erom vraagt;
- schrijft het model toch tekst, dan volgt het herhaalverzoek alleen bij een lijst of tabel, en het noemt de stukken
  die die lijst noemt; tekst zonder lijst is het antwoord, zonder tweede ronde;
- het `meting`-event telt per beurt het herhaalverzoek, de aangenomen tekst, de weigeringen (per redencode) en de
  gevulde sjablonen.
"""
from __future__ import annotations

import asyncio
import json

from agent.nodes.antwoord import AFRONDEN_EXTERN, genoemde_stukken, heeft_lijst
from agent.sjablonen import EXTERN
from fakes import FakeGraph, FakeLLM, response, text_block, tool_block
from test_bekendmaking_tools import ART36, _gevraagd, _stream_met_graaf

VRAAG = "Wanneer trad artikel 36 van de Invorderingswet 1990 in werking?"
ZOEK = tool_block("t1", "zoek_bekendmakingen", {"bwb_id": "BWBR0004770", "artikel": "36"})


def _llm(*antwoorden):
    return FakeLLM([response([text_block("duiding")], "end_turn"), response([ZOEK], "tool_use"), *antwoorden])


def _systeem(call) -> str:
    system = call.get("system")
    return "".join(d.get("text", "") if isinstance(d, dict) else str(d) for d in system) if isinstance(system, list) else str(system)


def test_met_een_connector_aan_zegt_de_prompt_dat_een_vondst_met_het_sjabloon_afrondt(monkeypatch):
    llm = _llm(response([text_block("Stb. 2010, 176 regelt de inwerkingtreding.")], "end_turn"))
    _stream_met_graaf(VRAAG, monkeypatch, llm, FakeGraph(result=ART36))
    agent = _systeem(llm.calls[1])
    assert AFRONDEN_EXTERN.format(extern=EXTERN).strip() in agent
    assert "Dit gaat voor 'antwoord in tekst'" in agent and "blijft 'stukken' leeg" in agent


def test_zonder_connector_blijft_de_prompt_gelijk():
    from agent.agent import answer_stream
    from fakes import make_settings

    llm = FakeLLM([response([text_block("duiding")], "end_turn"), response([text_block("Geen bron nodig.")], "end_turn")])

    async def verzamel():
        return [e async for e in answer_stream("Wat betekent betalingsonmacht?", settings=make_settings(), llm=llm,
                                               graph=FakeGraph(result=""))]
    asyncio.run(verzamel())
    assert all("AFRONDEN MET EEN BRON NAAST DE WET" not in _systeem(c) for c in llm.calls)


def test_tekst_zonder_lijst_na_een_vondst_is_het_antwoord_zonder_tweede_ronde(monkeypatch):
    llm = _llm(response([text_block("Artikel 36 trad in werking bij Stb. 2010, 176.")], "end_turn"))
    events = _stream_met_graaf(VRAAG, monkeypatch, llm, FakeGraph(result=ART36))
    assert len(llm.calls) == 3 and _gevraagd(llm) == 0, "geen herhaalverzoek: de tekst draagt geen lijst"
    tekst = "".join(e.get("content", "") for e in events if e.get("type") == "token")
    assert "Stb. 2010, 176" in tekst
    # Zonder sjabloon komt de bronnenlijst nog steeds uit `finalize`: een gevonden stuk dat niet gelezen is, is geen bron,
    # ook niet als de tekst het noemt.
    [bronnen] = [e["sources"] for e in events if e["type"] == "sources"]
    assert not any("stb" in json.dumps(b).lower() for b in bronnen), bronnen


def test_een_lijst_in_tekst_vraagt_het_sjabloon_met_alleen_de_genoemde_stukken(monkeypatch):
    llm = _llm(response([text_block("- Stb. 2010, 176: de inwerkingtreding\n- verder niets")], "end_turn"),
               response([text_block("klaar")], "end_turn"))
    _stream_met_graaf(VRAAG, monkeypatch, llm, FakeGraph(result=ART36))
    assert len(llm.calls) == 4 and _gevraagd(llm) == 1
    verzoek = [m for m in llm.calls[-1]["messages"] if m["role"] == "user"][-1]["content"]
    assert "geen andere: stb-2010-176." in verzoek, "alleen wat de lijst noemt, geen lijst die niet gevraagd is"


def test_een_lijst_zonder_gevonden_stuk_vraagt_stukken_leeg_te_laten(monkeypatch):
    llm = _llm(response([text_block("Twee punten:\n1. de wet\n2. het besluit")], "end_turn"),
               response([text_block("klaar")], "end_turn"))
    _stream_met_graaf(VRAAG, monkeypatch, llm, FakeGraph(result=ART36))
    verzoek = [m for m in llm.calls[-1]["messages"] if m["role"] == "user"][-1]["content"]
    assert "laat 'stukken' dan leeg" in verzoek


def test_een_lijst_of_tabel_is_twee_regels_of_meer():
    assert heeft_lijst("- a\n- b") and heeft_lijst("1. a\n2) b") and heeft_lijst("| a | b |\n|---|---|")
    assert not heeft_lijst("Eén zin met - een streepje.") and not heeft_lijst("- alleen één punt")


def test_een_label_telt_alleen_als_heel_woord():
    gevonden = {"zoek_x": [("x-1", "Artikel 1"), ("x-19", "Artikel 19"), ("x-2", "Artikel 2")]}
    assert genoemde_stukken("- Artikel 19\n- en x-2", gevonden) == ["x-19", "x-2"]


def test_het_meting_event_telt_wat_er_met_de_sjablonen_gebeurde(monkeypatch):
    """Een herhaalverzoek, een weigering met redencode en een gevuld sjabloon: alles in `sjabloon` van de meting."""
    from agent.agent import answer_stream
    from agent.beurtmeting import gemeten
    from agent.models import Verbruiksmeter
    from agent import tools
    from fakes import make_settings
    from test_bekendmaking_tools import _bron

    monkeypatch.setattr(tools.CONNECTORMODULES["bekendmakingen"], "_bron", _bron())
    fout = tool_block("s1", EXTERN, {"kort_antwoord": "x", "extern": [{"id": "stb-2099-1", "van_nr": 1, "tot_nr": 1}],
                                     "stukken": [], "twijfel": []})
    goed = tool_block("s2", EXTERN, {"kort_antwoord": "Het besluit Stb. 2010, 176.", "extern": [],
                                     "stukken": ["stb-2010-176"], "twijfel": []})
    llm = _llm(response([text_block("- Stb. 2010, 176\n- Stb. 2009, 610")], "end_turn"),
               response([fout], "tool_use"), response([goed], "tool_use"))
    meter = Verbruiksmeter()

    async def verzamel():
        stroom = answer_stream(VRAAG, settings=make_settings(connector_bekendmakingen=True), llm=llm,
                               graph=FakeGraph(result=ART36), bronnen=["bekendmakingen"], meter=meter)
        return [e async for e in gemeten(stroom, meter=meter, run=None, gesprek_id="", model="m")]
    events = asyncio.run(verzamel())
    [meting] = [e for e in events if e["type"] == "meting"]
    assert meting["sjabloon"] == {"gevraagd": 1, "geweigerd": {f"{EXTERN}:extern.blokken": 1}, "gevuld": {EXTERN: 1}}
    assert json.dumps(meting["sjabloon"]).isascii(), "alleen namen uit de code, geen inhoud"
