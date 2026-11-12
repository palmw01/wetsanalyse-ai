"""Een id in een aanroep van het model komt uit het gesprek (iteratie bekendmakingen, ronde 5; wetgeving_live I20).

Het mechanisme is declaratief per parameter (`id_herkomst.ARGUMENTEN`, en per connector het id-argument van de leestool),
en zit in de ene uitvoeringsgrens (`tool_execution.execute_tool`). Deze tests leggen het vast op meer tools en elke
connector, niet op één vraag."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from bronmodel.connectors import CONNECTORS

from agent import id_herkomst, tool_execution
from agent.resultaat import is_fout
from agent.tools import TOOLS
from fakes import FakeGraph

#: Een graaf die aantoont dat een regeling er niet in staat: de kop `?r`, geen rij.
NIET_IN_GRAAF = FakeGraph(result="?r\n")
#: Een graaf die de regeling kent.
IN_GRAAF = FakeGraph(result="?r\n<urn:bwb:BWBR0004770>\n")


def _state(vraag: str = "Wat zegt de wet?", resultaten: tuple[str, ...] = ()) -> dict:
    berichten = [{"role": "user", "content": vraag}]
    for i, r in enumerate(resultaten):
        berichten += [{"role": "assistant", "content": [{"type": "tool_use", "id": f"t{i}", "name": "x", "input": {}}]},
                      {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": r}]}]
    return {"question": vraag, "messages": berichten}


def test_elke_tool_met_een_id_parameter_valt_eronder():
    """Per parameter, niet per tool: elke tool met `bwb_id`, `bron_iri` of `dossier`, en elke leestool van een connector,
    heeft een id-argument. Een nieuwe tool met zo'n parameter valt er zonder code onder."""
    for t in TOOLS:
        for p in set(t["input_schema"].get("properties", {})) & set(id_herkomst.ARGUMENTEN):
            assert id_herkomst.id_argumenten(t["name"], {p: "BWBR0000001"}), (t["name"], p)
    for c in CONNECTORS.values():
        assert id_herkomst.LEESARGUMENTEN[c.leestool] == c.lees_argument
        [(p, soort, _)] = id_herkomst.id_argumenten(c.leestool, {c.lees_argument: c.voorbeeld_id})
        assert soort is id_herkomst.STUK


@pytest.mark.parametrize("tool,args", [
    ("get_artikel", {"bwb_id": "BWBR0002471", "artikel": "1"}),
    ("zoek_regelingen", {"bwb_id": "BWBR0002471"}),
    ("zoek_uitspraken", {"bwb_id": "BWBR0002471", "artikel": "1"}),
    ("zoek_bekendmakingen", {"bwb_id": "BWBR0002471"}),
    ("search_annotaties", {"bron_iri": "urn:bwb:BWBR0002471:artikel:1"}),
])
def test_een_bwb_id_buiten_de_graaf_uit_eigen_kennis_wordt_niet_uitgevoerd(tool, args):
    """I20: `zoek_regelingen {bwb_id: BWBR0002471}`, een id uit het geheugen voor een regeling buiten de graaf."""
    zin = id_herkomst.toets(tool, args, _state(), graph=NIET_IN_GRAAF)
    assert zin and "BWBR0002471" in zin and "eigen kennis" in zin and "zoek" in zin


@pytest.mark.parametrize("hoe", ["vraag", "resultaat", "register", "werkgebied"])
def test_een_bwb_id_uit_het_gesprek_mag(hoe):
    args = {"bwb_id": "BWBR0002471", "artikel": "1"}
    state = (_state("Wat zegt artikel 1 van BWBR0002471?") if hoe == "vraag" else
             _state(resultaten=(json.dumps({"resultaten": [{"bwb_id": "BWBR0002471"}]}),)) if hoe == "resultaat" else
             {**_state(), "bronregister": [["zoek_regelingen", "… BWBR0002471 …"]]} if hoe == "register" else
             {**_state(), "werkgebied_context": "Bron: urn:bwb:BWBR0002471:artikel:1"})
    assert id_herkomst.toets("get_wettekst", args, state, graph=NIET_IN_GRAAF) is None


def test_een_bwb_id_van_een_regeling_in_de_graaf_mag_en_een_storing_bewijst_niets():
    """Een regeling in de graaf: het resultaat noemt haar en de controle toetst het id; anders kostte elke graafvraag
    een zoekronde. Een graaf die niet (leesbaar) antwoordt, toont niets aan."""
    args = {"bwb_id": "BWBR0004770", "artikel": "9"}
    assert id_herkomst.toets("get_artikel", args, _state(), graph=IN_GRAAF) is None
    assert id_herkomst.toets("get_artikel", args, _state(), graph=FakeGraph(result="")) is None
    assert id_herkomst.toets("get_artikel", args, _state(), graph=None) is None


def test_wat_het_model_zelf_in_deze_beurt_schreef_telt_niet():
    state = _state()
    state["messages"].append({"role": "assistant", "content": [{"type": "text", "text": "Ik lees BWBR0002471."}]})
    assert id_herkomst.toets("get_artikel", {"bwb_id": "BWBR0002471", "artikel": "1"}, state, graph=NIET_IN_GRAAF)


@pytest.mark.parametrize("naam", sorted(CONNECTORS))
def test_een_stuk_uit_eigen_kennis_wordt_niet_gelezen_bij_elke_connector(naam):
    c = CONNECTORS[naam]
    args = {c.lees_argument: c.voorbeeld_id}
    zin = id_herkomst.toets(c.leestool, args, _state(), graph=NIET_IN_GRAAF)
    assert zin and "eigen kennis" in zin
    if c.brontype != "wettekst_live":
        assert c.voorbeeld_id in zin and any(t in zin for t in c.tools - {c.leestool}), "de zoektool van de connector"
    gevonden = _state(resultaten=(json.dumps({"resultaten": [{"id": c.voorbeeld_id}]}),))
    assert id_herkomst.toets(c.leestool, args, gevonden, graph=NIET_IN_GRAAF) is None
    assert id_herkomst.toets(c.leestool, args, _state(f"Wat staat er in {c.voorbeeld_id}?"), graph=NIET_IN_GRAAF) is None


def test_een_stuk_in_een_citeervorm_in_de_vraag_mag_en_een_ander_nummer_niet():
    args = {"id": "stb-2010-176"}
    assert id_herkomst.toets("get_bekendmaking", args, _state("Wat staat er in Stb. 2010, 176?")) is None
    assert id_herkomst.toets("get_bekendmaking", {"id": "stb-2010-17"}, _state("Wat staat er in Stb. 2010, 176?"))
    assert id_herkomst.toets("get_kamerstuk", {"id": "kst-32140-342"},
                             _state("Wat staat er in Kamerstuk 32140, nr. 342?")) is None


def test_een_dossiernummer_uit_eigen_kennis_wordt_niet_gezocht():
    zin = id_herkomst.toets("zoek_kamerstukken", {"dossier": "32140"}, _state("De wetsgeschiedenis van de Iw 1990?"))
    assert zin and "32140" in zin and "zoek_kamerstukken" in zin
    assert id_herkomst.toets("zoek_kamerstukken", {"dossier": "32140"}, _state("Stukken uit dossier 32140?")) is None


def _bouw(graph):
    return SimpleNamespace(graph=graph, settings=None, annotaties=object(), begrippen=object())


def test_de_uitvoeringsgrens_weigert_voor_het_model_en_niet_voor_code(monkeypatch):
    """In `execute_tool`: een aanroep van het model met een onbekend id gaat niet naar de bron, maar terug als fout
    (`is_error` in `tools_node`), met het event en de reden voor de meting. Code die een tool aanroept, valt er niet onder."""
    aanroepen = []
    monkeypatch.setattr(tool_execution, "dispatch", lambda name, *a, **k: aanroepen.append(name) or '{"status": "ok"}')
    events = []
    tool = {"name": "get_bekendmaking", "id": "c1", "input": {"id": "stb-2010-176"}}
    raw = tool_execution.execute_tool(_bouw(NIET_IN_GRAAF), _state(), events.append, tool, van_model=True)
    assert is_fout(raw) and json.loads(raw)["reden"] == "id_niet_uit_gesprek" and not aanroepen
    [eind] = [e for e in events if e.get("phase") == "end"]
    assert eind["status"] == "error" and eind["foutcode"] == "id_niet_uit_gesprek"
    tool_execution.execute_tool(_bouw(NIET_IN_GRAAF), _state(), events.append, tool)
    assert aanroepen == ["get_bekendmaking"], "een aanroep uit code leidt zijn id zelf af"


def test_de_antwoordlus_vraagt_de_toets():
    import inspect

    from agent.nodes import antwoord
    assert "van_model=True" in inspect.getsource(antwoord.tools_node)
