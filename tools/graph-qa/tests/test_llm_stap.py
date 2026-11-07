"""De gedeelde modelstap (H5): stopreden, pogingen, tellers, de rolcontrole en de logregel.

Wat het model krijgt, bewaakt `test_modelverzoeken.py`. Hier staat wat de stap met het antwoord doet.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agent.llm_stap import Rol, Stopreden, aanroep, lees_tool, lijst, stroom, vraag_tool
from agent.methode import instructies
from fakes import FakeLLM, response, text_block, tool_block

TOOL = "leg_vast"


def _verzoek(system: str = "Je legt iets vast.") -> dict:
    return dict(model="m", max_tokens=100, system=system, tools=[{"name": TOOL, "input_schema": {}}],
                tool_choice={"type": "auto"}, messages=[{"role": "user", "content": "geheime vraag"}])


def _tool(invoer: dict) -> SimpleNamespace:
    return response([tool_block("t1", TOOL, invoer)], "tool_use")


@pytest.mark.parametrize("ruw, verwacht", [
    ("end_turn", Stopreden.END_TURN), ("tool_use", Stopreden.TOOL_USE), ("max_tokens", Stopreden.MAX_TOKENS),
    ("refusal", Stopreden.REFUSAL), ("pause_turn", Stopreden.PAUSE_TURN), ("stop_sequence", Stopreden.STOP_SEQUENCE),
    ("iets_nieuws", Stopreden.ANDERS), ("", Stopreden.ANDERS), (None, Stopreden.ANDERS),
])
def test_stopreden_kent_elke_waarde_en_een_onbekende_is_anders(ruw, verwacht):
    assert Stopreden.van(SimpleNamespace(stop_reason=ruw)) is verwacht
    assert Stopreden.van(SimpleNamespace()) is Stopreden.ANDERS


def test_aanroep_geeft_de_kwargs_ongewijzigd_door():
    llm = FakeLLM([_tool({"a": 1})])
    verzoek = _verzoek()
    antwoord = aanroep(llm, Rol.KAARTACTIE, **verzoek)
    assert llm.calls == [verzoek]
    assert antwoord.stopreden is Stopreden.TOOL_USE and antwoord.duur_ms >= 0


def test_de_logregel_draagt_rol_stopreden_en_gebruik_maar_geen_inhoud(caplog):
    resp = _tool({"a": "geheim antwoord"})
    resp.usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=3,
                                 cache_creation_input_tokens=2)
    with caplog.at_level(logging.INFO, logger="graph_qa.llm"):
        aanroep(FakeLLM([resp]), Rol.KAARTACTIE, **_verzoek())
    [r] = [r for r in caplog.records if r.getMessage() == "model_aanroep"]
    assert (r.rol, r.model, r.stopreden) == ("kaartactie", "m", "tool_use")
    assert (r.invoer, r.uitvoer, r.cache_lees, r.cache_schrijf) == (10, 5, 3, 2)
    velden = {k: v for k, v in vars(r).items() if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__}
    assert not any("token" in k for k in velden), "geen veldnaam met 'token' (redactie in observability)"
    assert "geheim" not in repr(velden)


def test_een_rol_met_methoderol_eist_die_methodetekst_in_de_systeemprompt():
    llm = FakeLLM([_tool({})])
    with pytest.raises(ValueError, match="deelvragen"):
        aanroep(llm, Rol.DEELVRAGEN_VOORSTEL, **_verzoek("Geen methode hier."))
    assert llm.calls == [], "zonder methode gaat er niets naar het model"
    aanroep(llm, Rol.DEELVRAGEN_VOORSTEL, **_verzoek("Taak.\n\n" + instructies("deelvragen")))
    # Een andere methoderol is niet genoeg.
    with pytest.raises(ValueError):
        aanroep(FakeLLM([_tool({})]), Rol.DEELVRAGEN_VOORSTEL, **_verzoek(instructies("supervisor")))


def test_de_rolcontrole_leest_ook_een_gesplitste_systeemprompt():
    systeem = ["Taak.\n\n" + instructies("deelvragen"), "variabel deel"]
    aanroep(FakeLLM([_tool({})]), Rol.DEELVRAGEN_VOORSTEL, **{**_verzoek(), "system": systeem})
    blokken = [{"type": "text", "text": "Taak.\n\n" + instructies("deelvragen")}]

    class Blokken:   # FakeLLM voegt een lijst als strings samen; dit is de vorm die de adapter maakt
        def create(self, **_kw):
            return _tool({})
    aanroep(Blokken(), Rol.DEELVRAGEN_VOORSTEL, **{**_verzoek(), "system": blokken})


def test_lees_tool_neemt_de_eerste_aanroep_van_de_tool_en_weigert_onleesbaar():
    resp = response([text_block("eerst tekst"), tool_block("t0", "andere", {"x": 1}),
                     tool_block("t1", TOOL, {"a": 1}), tool_block("t2", TOOL, {"a": 2})], "tool_use")
    assert lees_tool(resp, TOOL) == {"a": 1}
    assert lees_tool(response([tool_block("t1", TOOL, "{kapot")], "tool_use"), TOOL) is None
    assert lees_tool(response([tool_block("t1", TOOL, "[1, 2]")], "tool_use"), TOOL) is None
    assert lees_tool(response([tool_block("t1", TOOL, '{"a": 3}')], "tool_use"), TOOL) == {"a": 3}
    assert lees_tool(response([text_block("geen tool")], "end_turn"), TOOL) is None


def test_lijst_geeft_alleen_een_lijst():
    assert lijst("k")({"k": [1]}) == [1]
    assert lijst("k")({"k": {"a": 1}}) is None and lijst("k")({}) is None


def test_zonder_tool_aanroep_een_tweede_poging_en_beide_tellen():
    llm = FakeLLM([response([text_block("hm")], "end_turn"), _tool({"a": 1})])
    meting: dict = {}
    uit = vraag_tool(llm, Rol.KAARTACTIE, verzoek=_verzoek(), pogingen=2, meting=meting)
    assert (uit.waarde, uit.pogingen, uit.stopreden) == ({"a": 1}, 2, Stopreden.TOOL_USE)
    assert meting == {"llm_calls": 2} and len(llm.calls) == 2


def test_een_onbruikbare_waarde_telt_als_geen_tool_aanroep():
    llm = FakeLLM([_tool({"items": "geen lijst"}), _tool({"items": [1, 2]})])
    uit = vraag_tool(llm, Rol.BEGRIP_KAART, verzoek=_verzoek(), pogingen=2, haal=lijst("items"))
    assert uit.waarde == [1, 2] and uit.pogingen == 2


def test_een_poging_is_een_poging_en_zonder_meting_telt_niets():
    llm = FakeLLM([response([text_block("hm")], "end_turn")])
    uit = vraag_tool(llm, Rol.INTAKE, verzoek=_verzoek(), pogingen=1)
    assert (uit.waarde, uit.pogingen, uit.stopreden) == (None, 1, Stopreden.END_TURN) and len(llm.calls) == 1


def test_de_tellers_houden_hun_eigen_namen_en_afkappen_telt_apart():
    llm = FakeLLM([response([text_block("half")], "max_tokens")])
    meting: dict = {}
    uit = vraag_tool(llm, Rol.JAS_REVIEWER, verzoek=_verzoek(), pogingen=1, meting=meting, teller="review_calls",
                     afgekapt_teller="review_afgekapt")
    assert uit.waarde is None and uit.stopreden is Stopreden.MAX_TOKENS
    assert meting == {"review_calls": 1, "review_afgekapt": 1}


def test_een_onbruikbare_poging_logt_de_stopreden(caplog):
    with caplog.at_level(logging.INFO, logger="graph_qa.llm"):
        vraag_tool(FakeLLM([response([text_block("nee")], "refusal")]), Rol.KAARTACTIE, verzoek=_verzoek(),
                   pogingen=1)
    [r] = [r for r in caplog.records if r.getMessage() == "geen bruikbare tool-aanroep"]
    assert (r.rol, r.tool, r.stopreden, r.poging) == ("kaartactie", TOOL, "refusal", 1)


def test_minder_dan_een_poging_is_een_fout():
    with pytest.raises(ValueError):
        vraag_tool(FakeLLM([]), Rol.KAARTACTIE, verzoek=_verzoek(), pogingen=0)


def test_een_fout_van_het_model_gaat_naar_de_aanroeper():
    class Kapot:
        def create(self, **_):
            raise RuntimeError("provider weg")
    with pytest.raises(RuntimeError, match="provider weg"):
        vraag_tool(Kapot(), Rol.KAARTACTIE, verzoek=_verzoek(), pogingen=2)


# --- H5c: de streamende aanroep van de antwoordlus ------------------------------------------------

def test_stroom_geeft_de_kwargs_door_en_logt_bij_het_eindantwoord(caplog):
    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])
    verzoek = {**_verzoek("Taak.\n\n" + instructies("duiding")), "historie_cache": True}
    with caplog.at_level(logging.INFO, logger="graph_qa.llm"):
        with stroom(llm, Rol.ANTWOORD, methoderol="duiding", **verzoek) as s:
            assert not [r for r in caplog.records if r.getMessage() == "model_aanroep"]
            resp = s.final_message()
    assert llm.calls == [verzoek] and resp.stop_reason == "end_turn" and s.antwoord.stopreden is Stopreden.END_TURN
    [r] = [r for r in caplog.records if r.getMessage() == "model_aanroep"]
    assert r.rol == "antwoord"


def test_stroom_eist_de_methoderol_van_de_specialist():
    with pytest.raises(ValueError, match="duiding"):
        with stroom(FakeLLM([]), Rol.ANTWOORD, methoderol="duiding", **_verzoek(instructies("algemeen"))):
            pass
    with pytest.raises(ValueError, match="retrieval"):
        with stroom(FakeLLM([]), Rol.OPHAAL, **_verzoek("Geen methode.")):
            pass
