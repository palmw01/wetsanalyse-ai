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
    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", bron)
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

    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", NepBron([]))
    events = _run(answer_stream("de laatste vijf moties van de Eerste Kamer", settings=AAN, llm=FakeLLM([]),
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    tekst = "".join(e.get("content", "") for e in events if e["type"] == "token")
    assert tekst.startswith("Bij deze zoekvraag vond ik geen kamerstukken.")
    assert tekst.endswith("Dat ik niets vond, betekent niet dat het niet bestaat.")
    assert "soort stuk „motie”" in tekst and "van de Eerste Kamer" in tekst and "Kamer Eerste" not in tekst
    # Bij niets gevonden zegt een volgorde niets (meting Staatsblad B14: "Meest relevante eerst." onder 0 treffers).
    assert "eerst." not in tekst


def test_een_fout_gaat_naar_de_agent_met_het_resultaat(monkeypatch):
    from agent import tools as t
    from agent.adapters.sru_kamerstukken import KamerstukFout
    from fakes import response, text_block
    from test_kamerstuk_tools import DOSSIER, NepBron

    class Weg(NepBron):
        def zoek(self, cql, **_):
            raise KamerstukFout("de officiële publicaties zijn niet bereikbaar: ConnectError")

    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", Weg(DOSSIER))
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

    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", NepBron(DOSSIER))
    # Tekst zonder lijst na een gelezen stuk is het antwoord: geen vraag om het sjabloon (nodes/antwoord.heeft_lijst).
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

    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", NepBron(_veel(60)))
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


ALLE = frozenset({"kamerstukken", "bekendmakingen", "rechtspraak"})


@pytest.mark.parametrize("vraag,connector,args", [
    # Meting bekendmakingen (10 nov 2026, B11): "van 2018" viel stil weg, en de lijst toonde 2025–2026.
    ("Welke verbeterbladen staan er in het Staatsblad van 2018?", "bekendmakingen",
     {"soort": "verbeterblad", "publicatie": "Staatsblad", "vanaf": "2018", "tot": "2018"}),
    ("Welke verbeterbladen van 2018 staan in het Staatsblad?", "bekendmakingen",
     {"soort": "verbeterblad", "publicatie": "Staatsblad", "vanaf": "2018", "tot": "2018"}),
    ("Welke verbeterbladen staan er in het Staatsblad uit 2018?", "bekendmakingen",
     {"soort": "verbeterblad", "publicatie": "Staatsblad", "vanaf": "2018", "tot": "2018"}),
    # Een periode: eerst werd alleen het eerste jaar gelezen.
    ("Geef de nieuwste uitspraken uit 2023 en 2024", "rechtspraak",
     {"volgorde": "nieuwste", "aantal": 10, "vanaf": "2023", "tot": "2024"}),
    ("Geef de nieuwste uitspraken uit 2023-2024", "rechtspraak",
     {"volgorde": "nieuwste", "aantal": 10, "vanaf": "2023", "tot": "2024"}),
    ("de nieuwste kamerstukken tussen 2020 en 2022", "kamerstukken",
     {"volgorde": "nieuwste", "aantal": 10, "vanaf": "2020", "tot": "2022"}),
    ("de oudste kamerstukken van 2020 tot en met 2022", "kamerstukken",
     {"volgorde": "oudste", "aantal": 10, "vanaf": "2020", "tot": "2022"}),
    # Een telling is een lijstvraag: het totaal komt uit de bron, met de zoekvraag erbij (B10).
    ("Hoeveel ministeriële regelingen van het Ministerie van Financiën staan er uit 2025 in de Staatscourant?",
     "bekendmakingen", {"soort": "ministeriële regeling", "orgaan": "Ministerie van Financiën",
                        "publicatie": "Staatscourant", "vanaf": "2025", "tot": "2025"}),
])
def test_jaren_en_perioden(vraag, connector, args):
    lijst = bron_lijst.lees(vraag, ALLE)
    assert lijst is not None and lijst.connector == connector
    assert lijst.args == args


@pytest.mark.parametrize("vraag", [
    # Een getal dat de code niet plaatst, gaat naar het model in plaats van stil weg te vallen.
    "Geef de 3 nieuwste Kamerstukken 2021",
    "Geef de nieuwste uitspraken 2023",
    "Welke publicaties in de Staatscourant staan er onder nummer 37344?",
])
def test_een_getal_dat_de_code_niet_plaatst_gaat_naar_het_model(vraag):
    assert bron_lijst.lees(vraag, ALLE) is None


@pytest.mark.parametrize("vraag,connector", [
    ("Geef de 100 nieuwste kamerstukken", "kamerstukken"),
    ("de 100 nieuwste uitspraken van de Hoge Raad", "rechtspraak"),
    ("Wat zijn de 100 meest recente publicaties?", "bekendmakingen"),
])
def test_meer_dan_een_pagina_wordt_begrensd_maar_niet_stil(vraag, connector):
    """Externe review (10 nov 2026): "de 100 nieuwste" gaf stil 25."""
    lijst = bron_lijst.lees(vraag, ALLE)
    assert lijst is not None and lijst.connector == connector
    assert lijst.args["aantal"] == bron_lijst.MAX_AANTAL and lijst.gevraagd == 100
    assert bron_lijst.lees(vraag.replace("100", "10"), ALLE).gevraagd == 0


def test_het_antwoord_zegt_dat_het_minder_toont_dan_gevraagd(monkeypatch):
    from agent import tools as t
    from test_kamerstuk_tools import _veel, NepBron

    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", NepBron(list(reversed(_veel(60)))))
    events = _run(answer_stream("Geef de 100 nieuwste kamerstukken", settings=AAN, llm=FakeLLM([]),
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    tekst = "".join(e.get("content", "") for e in events if e["type"] == "token")
    assert "Je vroeg om 100; per keer toon ik er hoogstens 25. Vraag om de volgende als je meer wilt zien." in tekst
    assert "25 van de 60 stukken." in tekst


@pytest.mark.parametrize("vraag,soort", [
    ("Hoeveel wetten van het Ministerie van Financiën staan er in het Staatsblad van 2024?", "wet"),
    ("Welke Staatsbladen wijzigen de belastingwetten?", None),
    ("Wat staat er in de Wet op de huurtoeslag?", None)])
def test_wetten_is_een_soort_maar_de_wet_niet(vraag, soort):
    """Iteratie bekendmakingen ronde 1, B20: "wetten" ging naar het model; "de wet" en "belastingwetten" zijn geen soort."""
    uit = bron_lijst.lees(vraag, frozenset({"bekendmakingen"}), lambda t: [])
    assert (uit.args.get("soort") if uit else None) == soort


# --- ronde 1 van de iteratie (11 nov 2026): de maand, het werkwoord, het dossier en een ingesloten regelingnaam ---------

ALLE3 = frozenset({"kamerstukken", "rechtspraak", "bekendmakingen"})


@pytest.mark.parametrize("vraag,connector,args", [
    # De maand (Rechtspraak R04): "in", "sinds" en "voor" geven een eigen periode.
    ("Welke uitspraken deed de Centrale Raad van Beroep in maart 2025?", "rechtspraak",
     {"instantie": "Centrale Raad van Beroep", "vanaf": "2025-03", "tot": "2025-03"}),
    ("Geef de nieuwste uitspraken van de Hoge Raad sinds juni 2026", "rechtspraak",
     {"volgorde": "nieuwste", "aantal": 10, "instantie": "Hoge Raad", "vanaf": "2026-06"}),
    ("De nieuwste conclusies voor januari 2025", "rechtspraak",
     {"volgorde": "nieuwste", "aantal": 10, "soort": "conclusie", "tot": "2024-12"}),
    ("Welke moties van de Tweede Kamer zijn er in februari 2026 ingediend?", "kamerstukken",
     {"soort": "motie", "kamer": "Tweede Kamer", "vanaf": "2026-02", "tot": "2026-02"}),
    # Het werkwoord na het onderwerp zoekt niet mee (Kamerstukken K09).
    ("Welke memories van toelichting over de inkomstenbelasting zijn er in 2024 verschenen?", "kamerstukken",
     {"soort": "memorie van toelichting", "vanaf": "2024", "tot": "2024", "tekst": "inkomstenbelasting"}),
    # "Zoek …" en "Vind …" zoeken niets (Kamerstukken ronde 2, K30).
    ("Zoek kamerstukken over invorderingsrente", "kamerstukken", {"tekst": "invorderingsrente"}),
    ("Vind Kamerstukken over kwijtschelding uit 2024", "kamerstukken",
     {"vanaf": "2024", "tot": "2024", "tekst": "kwijtschelding"}),
    # "kamerdossier" is een dossier (Staatsblad B18).
    ("Wat is het laatste stuk van kamerdossier 32140?", "kamerstukken",
     {"volgorde": "nieuwste", "aantal": 1, "dossier": "32140"}),
])
def test_ronde1_de_lijstroute_leest_meer(vraag, connector, args):
    l = bron_lijst.lees(vraag, ALLE3, lambda t: [])
    assert l is not None and l.connector == connector and l.args == args, l


def test_een_maand_zonder_datumfilter_is_geen_lijstvraag():
    """Een connector zonder `vanaf`/`tot` laat een maand niet stil vallen."""
    from bronmodel.connectors import KAMERSTUKKEN

    zonder = frozenset({"kamerstukken"})
    assert KAMERSTUKKEN.veld("datum") is not None  # de toets hieronder heeft een connector met datum nodig
    assert bron_lijst.lees("de nieuwste moties in maart 2025", zonder, lambda t: []).args.get("vanaf") == "2025-03"


def test_een_naam_binnen_een_langere_regelingnaam_telt_niet():
    """'Uitvoeringsregeling Invorderingswet 1990' noemt de Invorderingswet 1990 niet (Rechtspraak R23)."""
    namen = {"BWBR0004770": {"Invorderingswet 1990"}, "BWBR0004766": {"Uitvoeringsregeling Invorderingswet 1990"}}

    def regelingen(t):
        return [(b, n) for b, n in namen.items() if any(x.lower() in t.lower() for x in n)]
    l = bron_lijst.lees("Geef alle uitspraken die artikel 2 van de Uitvoeringsregeling Invorderingswet 1990 noemen",
                        frozenset({"rechtspraak"}), regelingen)
    # "alle": een volle pagina (Rechtspraak ronde 2, R23: 10 van de 11).
    assert l is not None and l.args == {"aantal": 25, "bwb_id": "BWBR0004766", "artikel": "2"}
    beide = bron_lijst.lees("uitspraken bij artikel 2 Invorderingswet 1990 en de Uitvoeringsregeling Invorderingswet 1990",
                            frozenset({"rechtspraak"}), regelingen)
    assert beide is None, "twee regelingen die elk zelf genoemd worden, blijven dubbelzinnig"


@pytest.mark.parametrize("vraag", ["Wat is een inwerkingtredingsbesluit?", "Wat is een motie?",
                                   "Wat zijn conclusies van de advocaat-generaal?", "Wat betekent een verbeterblad?",
                                   "Wat houdt een ministeriële regeling in?"])
def test_een_begripsvraag_is_geen_lijst(vraag):
    """Alleen een soort stuk, en de vraag wat het is: dat is uitleg, geen lijst (Staatsblad en Staatscourant, 11 nov)."""
    assert bron_lijst.lees(vraag, ALLE3, lambda t: []) is None


@pytest.mark.parametrize("vraag", ["Wat is het laatste inwerkingtredingsbesluit?",
                                   "Wat zijn de moties van de Eerste Kamer?", "Welke moties zijn er?"])
def test_een_lijst_met_wat_blijft_een_lijst(vraag):
    assert bron_lijst.lees(vraag, ALLE3, lambda t: []) is not None


# --- Telvragen (Kamerstukken ronde 5): het aantal uit de bron, één route voor elke connector ----------------------

ALLE_CONNECTORS = frozenset(bm.CONNECTORS)


@pytest.mark.parametrize("vraag,connector,args,verdeling", [
    ("Hoeveel Kamerstukken hebben de Douanewet in de titel?", "kamerstukken", {"woorden": "Douanewet"}, ""),
    ("Hoeveel stukken zitten er in dossier 33755?", "kamerstukken", {"dossier": "33755"}, ""),
    ("Hoeveel kamerstukken met invorderingsrente in de titel zijn er sinds 2020?", "kamerstukken",
     {"woorden": "invorderingsrente", "vanaf": "2020"}, ""),
    ("Hoeveel wetten van het Ministerie van Financiën staan er in het Staatsblad van 2024?", "bekendmakingen",
     {"soort": "wet", "orgaan": "Ministerie van Financiën", "publicatie": "Staatsblad", "vanaf": "2024", "tot": "2024"}, ""),
    ("Hoeveel publicaties hebben de Invorderingswet 1990 in de titel?", "bekendmakingen",
     {"woorden": "Invorderingswet 1990"}, ""),
    ("Hoeveel uitspraken van de Hoge Raad in het belastingrecht zijn er sinds 2025?", "rechtspraak",
     {"instantie": "Hoge Raad", "rechtsgebied": "belastingrecht", "vanaf": "2025"}, ""),
    ("Hoe verdelen de uitspraken van de Hoge Raad in het belastingrecht zich over de instanties?", "rechtspraak",
     {"instantie": "Hoge Raad", "rechtsgebied": "belastingrecht"}, "instanties"),
])
def test_een_telvraag_is_een_lijstvraag_met_tellen(vraag, connector, args, verdeling):
    lijst = bron_lijst.lees(vraag, ALLE_CONNECTORS)
    assert lijst is not None, vraag
    assert (lijst.connector, lijst.args, lijst.tellen, lijst.verdeling) == (connector, args, True, verdeling)


@pytest.mark.parametrize("vraag", [
    "Geef de 10 nieuwste kamerstukken",
    "Kamerstukken van dossier 32140",
    "de laatste vijf moties van de Eerste Kamer",
])
def test_een_gewone_lijstvraag_telt_niet(vraag):
    lijst = bron_lijst.lees(vraag, ALLE_CONNECTORS)
    assert lijst is not None and not lijst.tellen and not lijst.verdeling


@pytest.mark.parametrize("vraag", [
    # Een verdeling zonder woord waarover, en een titel die de code niet plaatst: dan leest het model de vraag.
    "Hoe is de verdeling van de kamerstukken?",
    "Hoeveel kamerstukken hebben een heel lange titel met veel woorden erin in de titel?",
])
def test_een_telvraag_die_de_code_niet_helemaal_leest_gaat_naar_het_model(vraag):
    assert bron_lijst.lees(vraag, ALLE_CONNECTORS) is None


def test_de_telling_komt_uit_het_totaal_van_de_bron_niet_uit_de_pagina():
    from agent.nodes.bron_lijst import telling

    rijen = [{"id": f"kst-1-{i}"} for i in range(10)]
    # Kamerstukken, Staatsblad en Staatscourant: KOOP telt alles.
    t = telling("Kamerstukken", {"status": "ok", "volledig": False, "totaal": 72, "resultaten": rijen})
    assert (t.aantal, t.dekking, t.per) == (72, "precies", [])
    # Rechtspraak: LiDO geeft een ondergrens, en dat zegt de telling.
    t = telling("Rechtspraak", {"status": "ok", "volledig": False, "totaal": 312, "dekking": "ten minste",
                                "resultaten": rijen, "per_instantie": {"Hoge Raad": 40, "Gerechtshof": 120}},
                "instanties")
    assert (t.aantal, t.dekking, t.per_wat) == (312, "ten minste", "instantie")
    assert [(p.waarde, p.aantal) for p in t.per] == [("Hoge Raad", 40), ("Gerechtshof", 120)]
    # Een verdeling die de bron niet geeft: gezegd, niet uit de tien rijen van de pagina geteld.
    t = telling("Kamerstukken", {"status": "ok", "totaal": 72, "resultaten": rijen}, "jaren")
    assert t.per == [] and "Een verdeling naar jaren geeft Kamerstukken niet" in t.zonder_verdeling
    # Zonder totaal: een volledig resultaat telt zijn rijen, anders is het ten minste dat.
    assert telling("X", {"volledig": True, "resultaten": rijen}).dekking == "precies"
    t = telling("X", {"volledig": False, "resultaten": rijen})
    assert (t.aantal, t.dekking) == (10, "ten minste")


def test_de_tekst_van_een_telling_staat_voor_de_lijst():
    from bronmodel.antwoord import Antwoord, Stuk, Stukken, TelPost, Telling, antwoord_tekst

    blok = Stukken(brontype="uitspraak", kop="Gevonden Rechtspraak", items=[Stuk(id="ECLI:NL:HR:2022:50", label="HR")],
                   totaal=1312, telling=Telling(aantal=1312, dekking="ten minste", bron="Rechtspraak", per_wat="instantie",
                                                per=[TelPost(waarde="Hoge Raad", aantal=40)]))
    tekst = antwoord_tekst(Antwoord(sjabloon="extern", blokken=[blok]))
    assert tekst.startswith("**Gevonden Rechtspraak**\n\nRechtspraak telt ten minste 1.312 stukken bij deze zoekvraag.\n\n"
                            "Per instantie:\n- Hoge Raad: 40\n\n- HR")


def test_een_telvraag_bij_kamerstukken_antwoordt_zonder_model_met_het_totaal(monkeypatch):
    from agent import tools as t
    from test_kamerstuk_tools import _veel, NepBron

    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", NepBron(list(reversed(_veel(30)))))
    llm = FakeLLM([])
    events = _run(answer_stream("Hoeveel stukken zitten er in dossier 99001?", settings=AAN, llm=llm,
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    assert llm.calls == []
    antwoord, = [e["antwoord"] for e in events if e["type"] == "antwoord"]
    blok, = antwoord["blokken"]
    assert blok["telling"]["aantal"] == 30 and blok["telling"]["dekking"] == "precies"
    tekst = "".join(e.get("content", "") for e in events if e["type"] == "token")
    assert "Kamerstukken telt 30 stukken bij deze zoekvraag." in tekst


def test_een_verdeling_bij_rechtspraak_komt_uit_de_telling_van_lido(monkeypatch):
    """Rechtspraak ronde 3, R22: het model duidde de verdeling ("past bij het civielrechtelijke karakter"). Nu komt ze uit
    `per_instantie`, zonder model en dus zonder duiding."""
    from agent import overzicht, tools as t
    from tests.test_rechtspraak_tools import LINKS, NepBron, _tsv

    namen = ("?regeling\t?citeertitel\t?soort\t?afkortingen\n"
             "<urn:bwb:BWBR0004770>\t\"Invorderingswet 1990\"\t\"wet\"\t\"IW | Iw 1990\"\n")
    artikel = _tsv(["node", "jci", "labelId", "label", "soort", "citeertitel"],
                   [["urn:bwb:BWBR0004770:artikel:36", "jci1.3:c:BWBR0004770&artikel=36", "x", "Artikel 36",
                     "urn:bwb-ns:Artikel", "Invorderingswet 1990"]])
    graaf = FakeGraph(results=lambda q: artikel if "?labelId" in q else namen)
    overzicht._REGELINGEN_CACHE.clear()
    monkeypatch.setattr(t.CONNECTORMODULES["rechtspraak"], "_bron", NepBron(LINKS))
    llm = FakeLLM([])
    try:
        events = _run(answer_stream("Hoe verdelen de uitspraken over artikel 36 van de Invorderingswet 1990 zich over de "
                                    "instanties?", settings=make_settings(connector_rechtspraak=True), llm=llm,
                                    graph=graaf, bronnen=["rechtspraak"]))
    finally:
        overzicht._REGELINGEN_CACHE.clear()
    assert llm.calls == [], "geen supervisor en geen specialist"
    antwoord, = [e["antwoord"] for e in events if e["type"] == "antwoord"]
    blok, = [b for b in antwoord["blokken"] if b["soort"] == "stukken"]
    telling = blok["telling"]
    assert telling["dekking"] == "ten minste" and telling["aantal"] == blok["totaal"]
    assert telling["per_wat"] == "instantie" and {p["waarde"] for p in telling["per"]} >= {"Hoge Raad"}
    assert sum(p["aantal"] for p in telling["per"]) == telling["aantal"]


def _sets():
    from pathlib import Path
    data = Path(__file__).parent / "data"
    for naam, connector in (("kamerstukken_vragenset_30.json", "kamerstukken"),
                            ("rechtspraak_vragenset_30.json", "rechtspraak"),
                            ("bekendmakingen_vragenset.json", "bekendmakingen")):
        inhoud = json.loads((data / naam).read_text())
        for v in inhoud["vragen"] if isinstance(inhoud, dict) else inhoud:
            if v.get("soort", "").startswith(("telling", "verdeling")) and not v.get("gesprek"):
                yield pytest.param(v, connector, id=v["id"])


@pytest.mark.parametrize("v,connector", list(_sets()))
def test_elke_telvraag_uit_de_vragensets_telt_in_de_lijstroute(v, connector):
    """Het mechanisme over drie connectors: elke telvraag uit hun vragenset gaat de lijstroute in en telt, met de
    argumenten die de set verwacht. Een regeling bij naam leest de code met de namen uit de graaf (hier vast)."""
    regelingen = (lambda t: [("BWBR0004770", {"Invorderingswet 1990"})] if "Invorderingswet 1990" in t else [])
    lijst = bron_lijst.lees(v["vraag"], frozenset({connector}), regelingen=regelingen)
    assert lijst is not None and lijst.tellen, v["vraag"]
    assert lijst.tool == v["tool"] and lijst.args == v["args"]
    assert bool(lijst.verdeling) == v["soort"].startswith("verdeling")


IW = ("BWBR0004770", {"Invorderingswet 1990", "Iw 1990"})


@pytest.mark.parametrize("vraag,connector,args,kanttekening", [
    # Kamerstukken koppelt geen stuk aan een regeling: de naam in de titel, en dat zegt de kanttekening (K17).
    ("Welke Kamerstukken horen bij de Invorderingswet 1990?", "kamerstukken", {"woorden": "Invorderingswet 1990"}, True),
    # Rechtspraak en Staatsblad en Staatscourant koppelen wel (`wetsverwijzing`): het bwb-id, zonder kanttekening.
    ("Welke uitspraken horen bij de Invorderingswet 1990?", "rechtspraak", {"bwb_id": "BWBR0004770"}, False),
    ("Welke publicaties in het Staatsblad horen bij de Invorderingswet 1990?", "bekendmakingen",
     {"bwb_id": "BWBR0004770", "publicatie": "Staatsblad"}, False),
    ("Hoeveel Kamerstukken horen bij de Invorderingswet 1990?", "kamerstukken", {"woorden": "Invorderingswet 1990"}, True),
])
def test_stukken_bij_een_regeling_leest_de_code_per_connector(vraag, connector, args, kanttekening):
    lijst = bron_lijst.lees(vraag, frozenset({connector}), regelingen=lambda t: [IW] if "Invorderingswet 1990" in t else [])
    assert lijst is not None and lijst.args == args
    assert bool(lijst.kanttekening) is kanttekening
    if kanttekening:
        assert "„Invorderingswet 1990” in de titel" in lijst.kanttekening


@pytest.mark.parametrize("vraag,regelingen", [
    ("Welke Kamerstukken horen bij de Invorderingswet 1990?", None),  # zonder graaf: geen namen
    ("Welke Kamerstukken horen bij de Invorderingswet 1990 en de AWR?", [IW, ("BWBR0002320", {"AWR"})]),
    ("Welke Kamerstukken horen bij artikel 36 van de Invorderingswet 1990?", [IW]),  # een artikel: niet als geheel
])
def test_stukken_bij_een_regeling_die_de_code_niet_eenduidig_plaatst_gaan_naar_het_model(vraag, regelingen):
    lees = None if regelingen is None else (lambda t: regelingen)
    assert bron_lijst.lees(vraag, KST, regelingen=lees) is None


@pytest.mark.parametrize("vraag,args", [
    ("Welke publicaties horen bij Kamerdossier 36602?", {"dossier": "36602"}),
    ("Welke Kamerstukken horen bij Kamerdossier 36602?", {"dossier": "36602"}),
    ("Hoeveel stukken horen bij Kamerdossier 36602?", {"dossier": "36602"}),
])
def test_horen_bij_zonder_regeling_leest_de_rest_van_de_vraag(vraag, args):
    """Meting Staatsblad ronde 5, B18: "horen bij" zonder regeling bij naam brak de hele lijstvraag af (0 -> 184k
    tokens). Zonder genoemde regeling is het het patroon "stukken bij een regeling" niet; het dossierfilter leest de
    vraag, met of zonder graaf (de namenlijst is dan leeg)."""
    alle = frozenset({"kamerstukken", "bekendmakingen", "rechtspraak", "wetgeving_live"})
    lijst = bron_lijst.lees(vraag, alle, regelingen=lambda t: [])
    assert lijst is not None and lijst.connector == "kamerstukken" and lijst.args == args and not lijst.kanttekening


@pytest.mark.parametrize("connector", ["kamerstukken", "bekendmakingen", "rechtspraak"])
def test_horen_bij_een_naam_die_de_graaf_niet_kent_gaat_naar_het_model(connector):
    """De naam blijft over in de vraag, en wat de code niet plaatst, leest het model (I02: de Wet op de zorgtoeslag
    staat niet in de graaf)."""
    assert bron_lijst.lees("Welke stukken horen bij de Wet op de zorgtoeslag?", frozenset({connector}),
                           regelingen=lambda t: []) is None


def test_de_kanttekening_staat_bij_de_zoekvraag_van_de_lijst(monkeypatch):
    from agent import overzicht, tools as t
    from test_kamerstuk_tools import _veel, NepBron

    namen = ("?regeling\t?citeertitel\t?soort\t?afkortingen\n"
             "<urn:bwb:BWBR0004770>\t\"Invorderingswet 1990\"\t\"wet\"\t\"IW | Iw 1990\"\n")
    overzicht._REGELINGEN_CACHE.clear()
    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", NepBron(_veel(5)))
    llm = FakeLLM([])
    try:
        events = _run(answer_stream("Welke Kamerstukken horen bij de Invorderingswet 1990?", settings=AAN, llm=llm,
                                    graph=FakeGraph(result=namen), bronnen=["kamerstukken"]))
    finally:
        overzicht._REGELINGEN_CACHE.clear()
    assert llm.calls == []
    blok, = [b for e in events if e["type"] == "antwoord" for b in e["antwoord"]["blokken"]]
    assert "Kamerstukken koppelt een stuk niet aan een regeling" in blok["zoekvraag"]
