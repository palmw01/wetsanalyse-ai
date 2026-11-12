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


def test_een_lijst_in_tekst_zet_de_code_om_naar_het_sjabloon_zonder_modelronde(monkeypatch):
    """Iteratie ronde 5 (I01, I14): het model schreef de lijst in tekst, en het herhaalverzoek kostte een ronde van ~25k.
    Nu zet de code de stukken die de lijst noemt in het blok `stukken`, met de rest van de tekst als kort antwoord."""
    llm = _llm(response([text_block("Artikel 36 trad in werking bij:\n- Stb. 2010, 176: de inwerkingtreding\n"
                                    "- Stb. 2009, 610: de wijziging")], "end_turn"))
    events = _stream_met_graaf(VRAAG, monkeypatch, llm, FakeGraph(result=ART36))
    assert len(llm.calls) == 3 and _gevraagd(llm) == 0, "geen herhaalverzoek, geen tweede schrijfronde"
    [antwoord] = [e["antwoord"] for e in events if e.get("type") == "antwoord"]
    toelichting, lijst = antwoord["blokken"][:2]
    assert toelichting["tekst"] == "Artikel 36 trad in werking bij:", "de lijstregels zijn eruit"
    assert lijst["soort"] == "stukken" and {i["id"] for i in lijst["items"]} == {"stb-2010-176", "stb-2009-610"}
    assert all(i["link"] for i in lijst["items"]), "met link uit de code"


def test_een_lijst_van_meer_stukken_dan_een_blok_draagt_is_het_antwoord():
    """I12: een opbouw van 52 paragrafen werd na het herhaalverzoek een lijst van 25 met twee weigeringen (213k)."""
    from agent.nodes.antwoord import lijst_omzetten
    from agent.sjablonen.extern import MAX_LIJST

    gevonden = {"zoek_x": [(f"x-{n}", f"§ {n}") for n in range(1, MAX_LIJST + 3)]}
    tekst = "Opbouw:\n" + "\n".join(f"- § {n}" for n in range(1, MAX_LIJST + 3))
    assert lijst_omzetten(tekst, gevonden, {EXTERN}, []) == ("aangenomen", None)


def test_zonder_uitleg_naast_de_lijst_of_zonder_extern_sjabloon_volgt_het_herhaalverzoek():
    from agent.nodes.antwoord import lijst_omzetten, zonder_lijstregels

    gevonden = {"zoek_x": [("x-1", "Artikel 1"), ("x-2", "Artikel 2")]}
    assert zonder_lijstregels("- Artikel 1\n- Artikel 2", ["x-1", "x-2"], gevonden) == ""
    assert lijst_omzetten("Kijk:\n- Artikel 1\n- Artikel 2", gevonden, {"antwoord_bepaling"}, []) is None
    assert zonder_lijstregels("Uitleg.\n\n| art | titel |\n|---|---|\n| Artikel 1 | a |", ["x-1"], gevonden) == "Uitleg."


def test_een_lijst_zonder_stukken_na_een_zoekvraag_is_het_antwoord(monkeypatch):
    """Ronde 6, I30: een opsomming van statussen ("150 geldende artikelen") is geen lijst van stukken. Zonder gelezen stuk
    geen herhaalverzoek en geen omzetting: de tekst is het antwoord."""
    llm = _llm(response([text_block("Twee punten:\n1. de wet\n2. het besluit")], "end_turn"))
    events = _stream_met_graaf(VRAAG, monkeypatch, llm, FakeGraph(result=ART36))
    assert len(llm.calls) == 3 and _gevraagd(llm) == 0
    assert not [e for e in events if e.get("type") == "antwoord"], "geen sjabloon, dus geen lijst eronder"


def _paren(*labels: str, prefix: str = "x") -> dict[str, list[tuple[str, str]]]:
    return {"zoek_x": [(f"{prefix}-{i}", label) for i, label in enumerate(labels)]}


def test_alleen_de_lijstregels_noemen_stukken():
    """Ronde 6, I30: "van artikel 1 tot en met artikel 86" in de lopende tekst zette "Artikel 1" als lijst eronder."""
    gevonden = _paren("Artikel 1", "Artikel 2")
    tekst = "De wet telt 174 artikelen, van artikel 1 tot en met artikel 86.\n\n- **150** geldend\n- **20** vervallen"
    assert genoemde_stukken(tekst, gevonden) == []
    assert genoemde_stukken("Zie:\n- Artikel 2: titel\n- iets", gevonden) == ["x-1"]


def test_een_kaal_nummer_in_een_tabel_is_het_stuk_met_dat_nummer():
    """Ronde 6, I14: de zeven artikelen stonden als "**19a**" in een tabel; alleen twee werden herkend."""
    from agent.nodes.antwoord import zonder_lijstregels

    gevonden = _paren("Artikel 19a", "Artikel 20", "Artikel 22a")
    tekst = ("Het begrip staat in drie artikelen:\n\n| Artikel | Titel |\n|---|---|\n| **19a** | Kostendelende medebewoner |"
             "\n| **20** | Jongerennormen |\n| 22a | Kostendelersnorm |\n\nArtikel 19a is het centrale artikel.")
    assert genoemde_stukken(tekst, gevonden) == ["x-0", "x-1", "x-2"]
    assert zonder_lijstregels(tekst, ["x-0", "x-1", "x-2"], gevonden) == ("Het begrip staat in drie artikelen:\n\n"
                                                                          "Artikel 19a is het centrale artikel.")


def test_de_kern_komt_uit_het_label_voor_elke_connector():
    """Het nummer komt uit het label, niet uit een vaste vorm: een Staatsblad, een Kamerstuk, een paragraaf."""
    gevonden = _paren("Stb. 2010, 176", "Kamerstukken 34273, nr. 7", "§ 22a")
    tekst = "| Stb. | datum |\n|---|---|\n| 2010, 176 | 2010-05-11 |\n\n- 34273, nr. 7 – nota\n- § 22a Aangifte"
    assert genoemde_stukken(tekst, gevonden) == ["x-0", "x-1", "x-2"]


def test_een_nummer_bij_twee_stukken_telt_niet():
    """Dezelfde kern bij twee stukken (artikel 1 van twee regelingen) is dubbelzinnig: dan alleen bij id of label."""
    gevonden = {"zoek_x": [("a-1", "Artikel 1"), ("b-1", "Artikel 1 ")]}
    assert genoemde_stukken("| **1** | Begrippen |\n| **2** | Doel |", gevonden) == []


def test_een_lijst_of_tabel_is_twee_regels_of_meer():
    assert heeft_lijst("- a\n- b") and heeft_lijst("1. a\n2) b") and heeft_lijst("| a | b |\n|---|---|")
    assert not heeft_lijst("Eén zin met - een streepje.") and not heeft_lijst("- alleen één punt")


def test_een_label_telt_alleen_als_heel_woord():
    gevonden = {"zoek_x": [("x-1", "Artikel 1"), ("x-19", "Artikel 19"), ("x-2", "Artikel 2")]}
    assert genoemde_stukken("- Artikel 19\n- en x-2", gevonden) == ["x-19", "x-2"]
    assert genoemde_stukken("Artikel 19 en x-2 in de lopende tekst.", gevonden) == []


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


def _fout():
    return tool_block(f"s{id(object())}", EXTERN, {"kort_antwoord": "x", "extern": [{"id": "stb-2099-1", "van_nr": 1,
                                                   "tot_nr": 1}], "stukken": [], "twijfel": []})


def _resultaten(llm) -> list[str]:
    return [json.dumps(b, ensure_ascii=False) for m in llm.calls[-1]["messages"] if m["role"] == "user"
            and isinstance(m["content"], list) for b in m["content"] if b.get("type") == "tool_result"]


def test_na_een_tweede_weigering_is_de_tekst_het_antwoord(monkeypatch):
    """Ronde 5, I12 en I28: twee weigeringen achter elkaar, en het model probeerde door tot 8 rondes (213k)."""
    from agent.nodes.sjabloon import OPNIEUW, TEKST_NU

    llm = _llm(response([_fout()], "tool_use"), response([_fout()], "tool_use"),
               response([text_block("- Stb. 2010, 176\n- Stb. 2009, 610")], "end_turn"))
    events = _stream_met_graaf(VRAAG, monkeypatch, llm, FakeGraph(result=ART36))
    assert len(llm.calls) == 5 and _gevraagd(llm) == 0, "geen derde poging en geen herhaalverzoek na een weigering"
    eerste, tweede = _resultaten(llm)[-2:]
    assert OPNIEUW.format(naam=EXTERN).split("{")[0][:30] in json.loads(eerste)["content"]
    assert TEKST_NU.strip()[:40] in json.loads(tweede)["content"]
    assert "Stb. 2010, 176" in "".join(e.get("content", "") for e in events if e.get("type") == "token")


def test_de_prompt_zegt_tekst_als_er_niets_aan_te_wijzen_is():
    """Ronde 5, I30: 'stukken' leeg bij een telling, en daarna weigerde het sjabloon omdat er niets aangewezen was."""
    assert "antwoord dan in tekst" in AFRONDEN_EXTERN and "niet te vullen" in AFRONDEN_EXTERN


def test_een_eigen_kanttekening_als_blokcitaat_wordt_gewone_tekst():
    """Ronde 6, I28: "> Let op: artikel 33 IW 1990 ziet op …" stond als blokcitaat, en de controle zag het als onbevestigd.
    Een blokcitaat dat letterlijk in de bron staat, blijft."""
    from agent.nodes.antwoord import kanttekening_als_tekst

    trace = [("get_artikel", json.dumps({"status": "ok", "resultaten": [{"tekst": "De ontvanger kan uitstel verlenen voor de duur van zes maanden."}]}))]
    tekst = ("Vergelijking.\n\n> De ontvanger kan uitstel verlenen voor de duur van zes maanden.\n\n"
             "> Let op: dit artikel ziet op een bijzondere groep lichamen.\n")
    uit, n = kanttekening_als_tekst(tekst, trace)
    assert n == 1
    assert "> De ontvanger kan uitstel" in uit and "\nLet op: dit artikel ziet op" in uit and "> Let op" not in uit
    assert kanttekening_als_tekst("Geen citaat hier.", trace) == ("Geen citaat hier.", 0)


def test_een_telling_in_een_opsomming_is_geen_stuk():
    """Ronde 7, I30: "- **4** nog niet in werking getreden" zette "Artikel 4" als lijst onder de telling. Een kort kaal
    nummer telt alleen als de regel precies dat nummer is of het voorvoegsel van het label draagt."""
    gevonden = _paren("Artikel 4", "Artikel 20", "§ 22a")
    assert genoemde_stukken("Telling:\n- **150** geldend\n- **20** vervallen\n- **4** nog niet in werking", gevonden) == []
    assert genoemde_stukken("- Artikel 20 regelt de norm\n- § 22a Aangifte", gevonden) == ["x-1", "x-2"]
    assert genoemde_stukken("| **4** | Alleenstaande |\n| 20 | Jongerennormen |", gevonden) == ["x-0", "x-1"]
