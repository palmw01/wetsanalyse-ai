"""De vaste route voor een lijstvraag over een bron naast de wet (ADR-013, ADR-010 laag 2) en de citeervormen.

Aanleiding: gesprek e906567a op acceptatie (9 nov 2026).
- "Wat is het laatste stuk van dossier 32140?" kostte elf modelrondes en gaf twee foute antwoorden. Nu is het één
  toolaanroep, zonder model, met het blok `stukken`.
- "Kamerstuk 32140, nr. 342" ging langs het model, dat een id raadde. Nu leest de code het genoemde stuk direct.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from bronmodel import connectors as bm

from agent import bron_lijst
from agent.agent import answer_stream
from fakes import FakeGraph, FakeLLM, make_settings

AAN = make_settings(connector_kamerstukken=True)
KST = frozenset({"kamerstukken"})


@pytest.mark.parametrize("vraag,args", [
    ("Geef mij de 10 meest recente kamerstukken", {"volgorde": "nieuwste", "aantal": 10}),
    ("Wat is het laatste stuk van dossier 32140?", {"volgorde": "nieuwste", "aantal": 1, "dossier": "32140"}),
    ("wat is het laatste kamerstuk in dossier 36200 IX", {"volgorde": "nieuwste", "aantal": 1, "dossier": "36200-IX"}),
    ("de laatste vijf moties van de Eerste Kamer",
     {"volgorde": "nieuwste", "aantal": 5, "soort": "motie", "kamer": "Eerste Kamer"}),
    ("geef de laatste 3 brieven in vergaderjaar 2025-2026",
     {"volgorde": "nieuwste", "aantal": 3, "soort": "brief", "vergaderjaar": "2025-2026"}),
    ("Geef de eerste memorie van toelichting in dossier 33755",
     {"volgorde": "oudste", "aantal": 1, "dossier": "33755", "soort": "memorie van toelichting"}),
    ("De oudste kamerstukken over één bankrekeningnummer sinds 2011",
     {"volgorde": "oudste", "aantal": 10, "vanaf": "2011", "tekst": '"één bankrekeningnummer"'}),
    ("de nieuwste kamerstukken over invorderingsrente in 2024",
     {"volgorde": "nieuwste", "aantal": 10, "vanaf": "2024", "tot": "2024", "tekst": "invorderingsrente"}),
    # Zonder volgorde: de zoektool kiest (relevantie bij tekst, een dossier op nummer). "Eerste Kamer" is geen volgorde
    # (acceptatie 9 nov 2026: dat werd "oudste eerst").
    ("Kamerstukken uit vergaderjaar 2025-2026 van de Eerste Kamer over invorderingsrente",
     {"kamer": "Eerste Kamer", "vergaderjaar": "2025-2026", "tekst": "invorderingsrente"}),
    ("welke kamerstukken gaan over de invorderingsrente", {"tekst": "invorderingsrente"}),
    ("Kamerstukken van dossier 32140", {"dossier": "32140"}),
])
def test_de_code_leest_de_lijstvraag(vraag, args):
    lijst = bron_lijst.lees(vraag, KST)
    assert lijst is not None and lijst.connector == "kamerstukken" and lijst.tool == "zoek_kamerstukken"
    assert lijst.args == args


@pytest.mark.parametrize("vraag", [
    # Een vraag naar de inhoud: het stuk moet gelezen worden.
    "Wat staat er in het laatste kamerstuk van dossier 32140?",
    "Wat bedoelde de wetgever in de laatste memorie van toelichting?",
    # Iets wat de code niet plaatst ("nummer"): het model leest het beter.
    "wat is het laatste nummer in dossier 32140",
    # Geen bron naast de wet, of geen volgorde.
    "Wat is de laatste wijziging van artikel 9 Invorderingswet 1990?",
    "Wat zijn de nieuwste uitspraken over aansprakelijkheid?",
    "welke wetten en kamerstukken gaan over de invorderingsrente",
    # Alleen de bron, zonder filter of volgorde.
    "Kamerstukken",
    # Een genoemd stuk wordt gelezen, geen lijst.
    "Wat is de laatste alinea van Kamerstuk 32140, nr. 342?",
    # Een onderwerp van meer dan vier woorden: de zoekterm kiest het model.
    "de nieuwste kamerstukken over de hoogte van de invorderingsrente voor ondernemers in coronatijd",
])
def test_geen_lijstvraag_of_niet_helemaal_te_lezen(vraag):
    assert bron_lijst.lees(vraag, KST) is None


def test_zonder_aangezette_connector_geen_lijst():
    assert bron_lijst.lees("Geef mij de 10 meest recente kamerstukken", frozenset()) is None


@pytest.mark.parametrize("tekst,ids", [
    ("Kamerstuk 32140, nr. 342", ["kst-32140-342"]),
    ("Kamerstukken II 2013/14, 33754, nr. 7", ["kst-33754-7"]),
    ("kamerstuk 36200 IX nummer 2", ["kst-36200-IX-2"]),
    ("Kamerstukken 33755, nummer 3", ["kst-33755-3"]),
    ("Wat staat er in kst-32140-101 en Kamerstukken 33402, nr. 61?", ["kst-32140-101", "kst-33402-61"]),
    ("kst-33402-61 en Kamerstukken 33402, nr. 61", ["kst-33402-61"]),
    ("kamerstukken over invorderingsrente", []),
    ("Kamerstuk 32140", []),
])
def test_een_citeervorm_wordt_een_id(tekst, ids):
    assert [i for _, i in bm.genoemde_stukken(tekst)] == ids


def test_elke_citeervorm_maakt_een_id_van_zijn_connector():
    for c in bm.CONNECTORS.values():
        for patroon, vorm in c.citeervormen:
            import re
            assert set(re.findall(r"\{(\w+)\}", vorm)) == set(re.compile(patroon).groupindex), (
                f"{c.naam}: de vorm {vorm} vraagt andere groepen dan het patroon levert")


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def test_de_route_roept_de_zoektool_een_keer_aan_zonder_model(monkeypatch):
    from agent import tools as t
    from test_kamerstuk_tools import _veel, NepBron

    bron = NepBron(list(reversed(_veel(30))))
    monkeypatch.setattr(t, "_KAMERSTUKBRON", bron)
    llm = FakeLLM([])  # elke modelaanroep faalt
    events = _run(answer_stream("Wat is het laatste stuk van dossier 99001?", settings=AAN, llm=llm,
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    assert llm.calls == [], "geen supervisor en geen specialist"
    starts = [e for e in events if e["type"] == "tool_execution" and e.get("phase") == "start"]
    assert [e["tool"] for e in starts] == ["zoek_kamerstukken"]
    assert bron.vragen[-1].endswith(' AND w.dossiernummer=="99001" sortBy dt.date/sort.descending dt.identifier/sort.ascending')
    tekst = "".join(e.get("content", "") for e in events if e["type"] == "token")
    assert "**Gevonden Kamerstukken**" in tekst and "Gezocht op dossier 99001. Nieuwste eerst." in tekst
    assert "1 van de 30 stukken." in tekst
    grounding, = [e for e in events if e["type"] == "grounding"]
    assert not grounding.get("onbevestigd") and not grounding.get("unsupported")


def test_niets_gevonden_is_een_leemte(monkeypatch):
    from agent import tools as t
    from test_kamerstuk_tools import NepBron

    monkeypatch.setattr(t, "_KAMERSTUKBRON", NepBron([]))
    events = _run(answer_stream("de laatste vijf moties van de Eerste Kamer", settings=AAN, llm=FakeLLM([]),
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    tekst = "".join(e.get("content", "") for e in events if e["type"] == "token")
    assert tekst.startswith("Geen Kamerstukken gevonden die aan de zoekvraag voldoen.")
    assert "soort stuk „motie”" in tekst and "van de Eerste Kamer" in tekst and "Kamer Eerste" not in tekst


def test_een_fout_gaat_naar_de_agent_met_het_resultaat(monkeypatch):
    from agent import tools as t
    from agent.adapters.sru_kamerstukken import KamerstukFout
    from fakes import response, text_block
    from test_kamerstuk_tools import DOSSIER, NepBron

    class Weg(NepBron):
        def zoek(self, cql, **_):
            raise KamerstukFout("de officiële publicaties zijn niet bereikbaar: ConnectError")

    monkeypatch.setattr(t, "_KAMERSTUKBRON", Weg(DOSSIER))
    llm = FakeLLM([response([text_block("De officiële publicaties zijn nu niet bereikbaar.")], "end_turn")])
    events = _run(answer_stream("Geef mij de 10 meest recente kamerstukken", settings=AAN, llm=llm,
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    assert len(llm.calls) == 1, "geen supervisor; de agent formuleert de fout"
    laatste = llm.calls[0]["messages"][-1]["content"]
    assert any(b.get("type") == "tool_result" and "bron_onbereikbaar" in json.dumps(b) for b in laatste)
    assert "niet bereikbaar" in "".join(e.get("content", "") for e in events if e["type"] == "token")


def test_een_citeervorm_wordt_vooraf_gelezen(monkeypatch):
    from agent import tools as t
    from fakes import response, text_block
    from test_kamerstuk_tools import DOSSIER, NepBron

    monkeypatch.setattr(t, "_KAMERSTUKBRON", NepBron(DOSSIER))
    llm = FakeLLM([response([text_block("Kst-99001-3 legt het doel uit.")], "end_turn")])
    _run(answer_stream("Kamerstuk 99001, nr. 3", settings=AAN, llm=llm, graph=FakeGraph(result=""),
                       bronnen=["kamerstukken"]))
    assert len(llm.calls) == 1, "geen supervisorcall: de citeervorm bepaalt de route"
    gelezen = [b for m in llm.calls[0]["messages"] for b in (m["content"] if isinstance(m["content"], list) else [])
               if b.get("type") == "tool_use"]
    assert [(g["name"], g["input"]) for g in gelezen] == [("get_kamerstuk", {"id": "kst-99001-3"})]


def test_een_dossier_op_nummer_toont_het_begin_van_de_lijst(monkeypatch):
    """Een dossier zonder volgorde staat op nummer, en een pagina kan langer zijn dan het blok draagt: dan het begin,
    met "N van de M stukken", en niet "geen gevonden"."""
    from agent import tools as t
    from agent.sjablonen.extern import MAX_LIJST
    from test_kamerstuk_tools import _veel, NepBron

    monkeypatch.setattr(t, "_KAMERSTUKBRON", NepBron(_veel(60)))
    events = _run(answer_stream("Kamerstukken van dossier 99001", settings=AAN, llm=FakeLLM([]),
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    tekst = "".join(e.get("content", "") for e in events if e["type"] == "token")
    assert tekst.count("\n- [") + tekst.startswith("- [") <= MAX_LIJST and "van de 60 stukken." in tekst
    assert "Op nummer." in tekst


def test_een_dossier_met_een_aantal_is_de_nieuwste():
    """Acceptatie 9 nov 2026: {dossier, aantal} gaf `ongeldig_aantal`; nu is dat de nieuwste stukken."""
    from test_kamerstuk_tools import DOSSIER, NepBron, roep

    bron = NepBron(DOSSIER)
    d = roep("zoek_kamerstukken", {"dossier": "99001", "aantal": 2}, bron)
    assert d["status"] == "ok" and d["zoekvraag"]["volgorde"] == "nieuwste"
    assert bron.vragen[-1].endswith("sortBy dt.date/sort.descending dt.identifier/sort.ascending")
