"""D01 uit de meting van bundel 117 (14 nov 2026), met nepbronnen in de echte vorm: zoek_uitspraken en get_uitspraak door
de echte toollaag, met uitspraken waarvan de inhoud níét over de melding van betalingsonmacht gaat.

Het kind las tien uitspraken, gaf geen rapport en werd door de code afgesloten. De centrale agent schreef er daarna zeven
samenvattingen bij, en geen enkele klopte: HR:2026:586 (una via, vergrijpboete) werd een meldingszaak, GHSHE:2025:1495
(aanmerkelijk belang) ging over "een mondelinge mededeling volstaat niet". `verify` zei *gegrond*, want de stukken stonden
in de trace (ADR-016 §A4)."""
from __future__ import annotations

import json
from types import SimpleNamespace

from agent import subagent as sub
from agent import tools
from agent.grounding import check_grounding
from agent.nodes import antwoord as antwoordnodes
from agent.nodes import subagent_route as route
from agent.nodes.antwoord import SUBAGENT_AFGESLOTEN
from agent.sjablonen import vul
from fakes import FakeGraph, make_settings
from test_rechtspraak_tools import AAN, ARTIKEL, IW, V_NU, Link, NepBron
from test_subagent import STATE, Api, _kinderen

HR, HOF, PHR = "ECLI:NL:HR:2026:586", "ECLI:NL:GHSHE:2025:1495", "ECLI:NL:PHR:2024:936"
INHOUD = {
    HR: ("Hoge Raad", "2026-03-06", "Vergrijpboete; una via.",
         "Het Hof heeft de vergrijpboete terecht vernietigd. Volgens het una-via-beginsel mocht de inspecteur na de "
         "strafrechtelijke vervolging niet ook een boete opleggen voor hetzelfde feit."),
    HOF: ("Gerechtshof 's-Hertogenbosch", "2025-05-15", "Inkomstenbelasting; aanmerkelijk belang.",
          "De vervreemding van de aandelen leidt tot een voordeel uit aanmerkelijk belang in box 2. De koopsom is "
          "zakelijk vastgesteld."),
    PHR: ("Parket bij de Hoge Raad", "2024-09-20", "Verjaring van de invorderingsbevoegdheid.",
          "De invorderingsbevoegdheid van de ontvanger was verjaard, omdat de stuitingshandeling te laat kwam."),
}
VRAAG = ("Zoek de rechtspraak over de melding van betalingsonmacht bij artikel 36 van de Invorderingswet 1990 uit de "
         "periode van mijn dossier, en vat per uitspraak samen wat de rechter over de melding zegt.")


def _xml(ecli: str) -> bytes:
    orgaan, datum, indicatie, tekst = INHOUD[ecli]
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description><dcterms:identifier>{ecli}</dcterms:identifier><dcterms:creator>{orgaan}</dcterms:creator>
  <dcterms:date>{datum}</dcterms:date><dcterms:type>Uitspraak</dcterms:type></rdf:Description></rdf:RDF>
<inhoudsindicatie><para>{indicatie}</para></inhoudsindicatie>
<uitspraak><section><title>Beoordeling</title><para>{tekst}</para></section></uitspraak></open-rechtspraak>""".encode()


BRON = NepBron([Link(e, f"{e} - {INHOUD[e][0]}, {INHOUD[e][1]} / 25/00{i}", "Door computer herkende referentie", V_NU)
                for i, e in enumerate(INHOUD)], docs={e: _xml(e) for e in INHOUD})
ZOEK = ("zoek_uitspraken", tools.dispatch("zoek_uitspraken", FakeGraph(result=ARTIKEL), {"bwb_id": IW, "artikel": "36"},
                                          AAN, rechtspraak=BRON))
TRACE = [ZOEK, *(("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": e}, AAN, rechtspraak=BRON))
                 for e in INHOUD)]

#: Wat de centrale agent in bundel 117 schreef, in de vorm van de meting: per uitspraak een samenvatting die niet klopt.
VERKEERD = {
    HR: f"In {HR} oordeelt de Hoge Raad dat de bestuurder de melding van betalingsonmacht te laat deed, zodat het "
        "wettelijke rechtsvermoeden van onbehoorlijk bestuur geldt.",
    HOF: f"In {HOF} beslist het hof dat een mondelinge mededeling aan de ontvanger niet volstaat als melding van "
         "betalingsonmacht.",
}


def test_de_trace_heeft_de_echte_vorm():
    zoek = json.loads(ZOEK[1])
    assert zoek["status"] == "ok" and {r["id"] for r in zoek["resultaten"]} == set(INHOUD)
    assert all(json.loads(t)["stuk"]["id"] in INHOUD for n, t in TRACE if n == "get_uitspraak")


# -- 1 en 4: een kind dat de code afsloot, krijgt geen samenvatting en heet `afgesloten` ----------------------------------

class GeenModel:
    meter = None

    def stream(self, **_k):
        raise AssertionError("geen modelronde na een kind zonder rapport")

    create = stream


def test_een_afgesloten_kind_heet_afgesloten_en_de_beurt_eindigt_met_tekst_uit_code(monkeypatch):
    events = []
    monkeypatch.setattr(route, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(sub, "WetsanalyseApi", lambda *_a: Api())
    kinderen, _, _ = _kinderen({"answer": SUBAGENT_AFGESLOTEN, "afgesloten": True, "source_trace": TRACE,
                                "modellen": ["m"]})
    b = SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None, stop_check=None,
                        graph=None)
    upd = route.subagent_route_node(b, {**STATE, "question": VRAAG, "source_trace": []})
    [taak] = [e for e in events if e["type"] == "regie_taak" and e["fase"] == "eind"]
    [regie] = [e for e in events if e["type"] == "regie" and e["fase"] == "eind"]
    assert taak["uitkomst"] == "afgesloten" and "rapport" not in taak
    assert (regie["afgesloten"], regie["opgeleverd"], regie["mislukt"]) == (1, 0, 0)

    state = {**STATE, **upd, "question": VRAAG, "messages": [{"role": "user", "content": VRAAG}], "turns": 0,
             "agentvorm": "centraal"}
    uit = antwoordnodes.agent_node(SimpleNamespace(settings=make_settings(), llm=GeenModel()), state)
    tekst = uit["answer"]
    assert tekst.startswith(sub.ZONDER_RAPPORT["afgesloten"]) and sub.KLEINER in tekst
    assert all(f"- {json.loads(t)['stuk']['label']}" in tekst for n, t in TRACE if n == "get_uitspraak")
    for woord in ("una via", "vergrijpboete", "aanmerkelijk", "verjaard", "melding van betalingsonmacht"):
        assert woord not in tekst, "geen inhoud over de stukken"
    assert check_grounding(tekst, TRACE).beweringen == []


# -- 2: na een rapport rust een duiding op een passage van dat stuk -----------------------------------------------------

def _rapport() -> dict:
    """Een rapport `klaar` dat alleen uit HR:2026:586 citeert, door de code gevuld uit de trace."""
    rij = next(json.loads(t) for n, t in TRACE if n == "get_uitspraak" and HR in t)
    nr = next(r["nr"] for r in rij["resultaten"] if "una-via" in r["tekst"])
    a = vul("rapport", {"status": "klaar", "gedaan": "Drie uitspraken gelezen.", "bevindingen": "Over boetes.",
                        "onderbouwing": [], "open": [], "vragen": [], "extern": [{"id": HR, "van_nr": nr, "tot_nr": nr}]},
            TRACE)
    return {"rapport": {"status": "klaar"}, "antwoord": a.model_dump(), "answer": "Over boetes.", "source_trace": TRACE}


def test_na_een_rapport_steunt_een_duiding_alleen_op_de_passages_van_dat_stuk():
    steun = sub.steun_van([_rapport()])
    assert set(steun) == {HR} and "una-via-beginsel" in steun[HR]
    # De samenvattingen van bundel 117: de ene steunt niet op de passage van HR:2026:586, de andere heeft geen passage.
    fout = check_grounding("\n".join(VERKEERD.values()), TRACE, steun=steun)
    assert f"duiding van {HR} die de passages van dat stuk niet dragen" in fout.beweringen
    assert f"duiding van {HOF} zonder passage van dat stuk in het rapport" in fout.beweringen
    assert fout.niveau != "gegrond"
    # Wat de passage zegt, mag; een stuk zonder passage noemen met wat het zoekresultaat zegt, ook.
    goed = (f"In {HR} oordeelt de Hoge Raad dat de inspecteur volgens het una-via-beginsel na de strafrechtelijke "
            f"vervolging geen boete mocht opleggen voor hetzelfde feit.\n- {PHR} (Parket bij de Hoge Raad, 20 september 2024)")
    assert not [b for b in check_grounding(goed, TRACE, steun=steun).beweringen if b.startswith("duiding")]
    # Zonder rapport (geen subagent) geldt deze toets niet; dan toetst `verify` alleen of het stuk gelezen is.
    assert not [b for b in check_grounding("\n".join(VERKEERD.values()), TRACE).beweringen if b.startswith("duiding")]


def test_verify_node_geeft_de_passages_van_het_rapport_mee():
    state = {"subagenten": [{"uitkomst": "klaar"}], "rapport_steun": sub.steun_van([_rapport()]),
             "antwoord": {"blokken": [{"soort": "extern", "id": PHR, "passages": [{"tekst": "verjaard"}]}]}}
    steun = antwoordnodes.rapport_steun(state)
    assert set(steun) == {HR, PHR}
    assert antwoordnodes.rapport_steun({"subagenten": [{"uitkomst": "afgesloten"}]}) is None


# -- 3: de inhoud van het rapport staat in het eind-event ---------------------------------------------------------------

def test_de_inhoud_van_het_rapport_staat_in_het_eind_event(monkeypatch):
    events = []
    monkeypatch.setattr(route, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(sub, "WetsanalyseApi", lambda *_a: Api())
    kinderen, _, _ = _kinderen(_rapport())
    b = SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None, stop_check=None,
                        graph=None)
    route.subagent_route_node(b, {**STATE, "question": VRAAG, "source_trace": []})
    [taak] = [e for e in events if e["type"] == "regie_taak" and e["fase"] == "eind"]
    assert taak["rapport"]["status"] == "klaar" and taak["rapport"]["stukken"] == [HR]
    assert taak["rapport"]["gedaan"] == "Drie uitspraken gelezen." and taak["rapport"]["bevindingen"] == "Over boetes."
