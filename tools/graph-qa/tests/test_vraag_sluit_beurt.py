"""Een vraag van een subagent sluit de beurt, en wat het antwoord over een stuk zegt rust op zijn gelezen tekst (ADR-016
§A4; meting bundel 116, 14 nov 2026, D01: het kind stond op `vraag` en de kaart kwam, maar de centrale agent schreef in
dezelfde beurt al samenvattingen van uitspraken die niemand las, met het oordeel *gegrond*)."""
from __future__ import annotations

import json
from types import SimpleNamespace

from agent.agentvorm import SUBAGENT_INSTRUCTIE
from agent.gelezen import MAX_EIGEN_WOORDEN, ongelezen_samengevat
from agent.grounding import check_grounding
from agent.nodes import antwoord as antwoordnodes
from agent.nodes.antwoord import VRAAG_VAN_SUBAGENT
from fakes import make_settings

HR = "ECLI:NL:HR:2026:586"
ZOEK = ("zoek_uitspraken", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [
    {"id": HR, "label": "HR 6 maart 2026", "titel": "Hoge Raad, 6 maart 2026, una via en vergrijpboete"}]}))
LEES = ("get_uitspraak", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "stuk": {"id": HR, "label": "HR"},
                                     "resultaten": [{"nr": 1, "tekst": "De Hoge Raad oordeelt over una via."}]}))
SAMENVATTING = (f"In {HR} oordeelt de Hoge Raad dat de bestuurder de melding van betalingsonmacht te laat deed, zodat het "
                "wettelijke rechtsvermoeden van onbehoorlijk bestuur geldt.")


class GeenModel:
    meter = None

    def stream(self, **_k):
        raise AssertionError("geen modelronde bij een open vraag")

    create = stream


def test_een_open_vraag_van_een_subagent_sluit_de_beurt_zonder_modelronde(monkeypatch):
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: (lambda _e: None))
    state = {"question": "Vat per uitspraak samen …", "messages": [{"role": "user", "content": "Vat per uitspraak samen …"}],
             "agentvorm": "centraal", "specialist": "centraal", "source_trace": [ZOEK], "turns": 0,
             "subagenten": [{"uitkomst": "vraag", "delegatie_id": "d1", "vragen": [{"tekst": "Welke periode?",
                                                                                      "opties": []}]}]}
    b = SimpleNamespace(settings=make_settings(), llm=GeenModel(), memory_context=lambda _s: "",
                        advies_context=lambda _s: "")
    upd = antwoordnodes.agent_node(b, state)
    assert upd["answer"] == VRAAG_VAN_SUBAGENT and upd["pending_tools"] == []
    # Zonder vraag (of in het kind zelf) gaat de beurt gewoon naar het model.
    assert antwoordnodes.open_vraag([{"uitkomst": "klaar", "delegatie_id": "d1"}]) is None


def test_een_samenvatting_van_een_stuk_dat_alleen_gevonden_is_is_een_bewering():
    assert ongelezen_samengevat(SAMENVATTING, [ZOEK]) == [f"samenvatting van {HR} zonder gelezen tekst"]
    # Een vermelding met wat het zoekresultaat zegt, is geen samenvatting.
    assert ongelezen_samengevat(f"- {HR} (HR 6 maart 2026), over una via en een vergrijpboete.", [ZOEK]) == []
    # Gelezen: dan rust de samenvatting op de tekst, en toetst de rest van de controle haar.
    assert ongelezen_samengevat(SAMENVATTING, [ZOEK, LEES]) == []
    assert MAX_EIGEN_WOORDEN >= 3


def test_verify_keurt_zo_n_samenvatting_niet_goed_ook_met_letterlijke_citaten():
    rapport = check_grounding(SAMENVATTING, [ZOEK])
    assert f"samenvatting van {HR} zonder gelezen tekst" in rapport.beweringen and rapport.niveau != "gegrond"
    assert f"samenvatting van {HR} zonder gelezen tekst" not in check_grounding(SAMENVATTING, [ZOEK, LEES]).beweringen


def test_de_subagent_stelt_zijn_vragen_in_een_keer():
    assert "alle vragen die de opdracht openlaat in één keer" in SUBAGENT_INSTRUCTIE
