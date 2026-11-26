"""De route van de contenttoets (plan contenttoets, C2): zonder model naar het profiel, achter een proefvlag."""
from __future__ import annotations

from datetime import date

import pytest
from bronmodel.plugins import CONTENTTOETS, PLUGINS

from agent import contenttoets as ct, profielen, skills
from agent.models import PLUGIN_ACTIES
from agent.nodes import supervisie
from agent.nodes.context import Bouw
from agent.nodes.contenttoets import bereid_contenttoets_node
from agent.sjablonen.contenttoets import CONTENT_TOOL, content_van
from fakes import FakeGraph, make_settings

TEKST = ("U kunt uw belastingschuld betalen in maximaal 24 maanden, in gelijke termijnen van minimaal € 20 per maand. "
         "Of u krijgt 4 maanden kort uitstel.")


class _GeenModel:
    def create(self, **_):
        raise AssertionError("de route vraagt geen model")

    stream = create


def _bouw(aan: bool) -> Bouw:
    return Bouw(settings=make_settings(contenttoets=aan), llm=_GeenModel(), graph=FakeGraph(results=lambda q: ""),
                stop_check=None, model="m", model_router="m", model_ophaal="m", memory_context=lambda _s: "",
                advies_context=lambda _s: "")


def _route(vraag: str, *, aan: bool = True, actie: str = "", plugins=None, stand=None) -> tuple[str, dict]:
    state = {"question": vraag, "messages": [{"role": "user", "content": vraag}], "modus": "auto", "werkgebied_id": "",
             "actie": actie, "context": {}, "opgegeven_doel": {}, "focus": {}, "bronstand": stand or {},
             "plugins": plugins}
    b = _bouw(aan)
    upd = supervisie.ingang_node(b, state)
    return supervisie._entry_node(b, {**state, **upd}), upd


@pytest.fixture(autouse=True)
def _stil(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))


def test_het_commando_gaat_zonder_model_naar_het_profiel():
    node, upd = _route(f"/contenttoets {TEKST}")
    assert node == "contenttoets_voorbereiden" and upd["specialist"] == "contenttoets" and upd["contenttoets"] is True


def test_de_actie_van_de_werkplek_ook():
    node, upd = _route(f"/contenttoets {TEKST}", actie="contenttoets")
    assert node == "contenttoets_voorbereiden"


def test_in_een_gesprek_waar_de_plugin_uit_staat_een_vaste_zin():
    node, upd = _route(f"/contenttoets {TEKST}", plugins=[])
    assert node == "afwijzen" and upd["afwijs_melding"] == ct.UIT_IN_GESPREK
    node, _ = _route(f"/contenttoets {TEKST}", plugins=["contenttoets"])
    assert node == "contenttoets_voorbereiden"


def test_de_beurt_neemt_alleen_bekende_plugins_aan():
    from pydantic import ValidationError

    from agent.models import ChatRequest

    assert ChatRequest(question="x", plugins=["contenttoets"]).plugins == ["contenttoets"]
    with pytest.raises(ValidationError):
        ChatRequest(question="x", plugins=["onbekend"])


def test_met_de_proefvlag_uit_een_vaste_zin():
    node, upd = _route(f"/contenttoets {TEKST}", aan=False)
    assert node == "afwijzen" and upd["afwijs_melding"] == ct.UIT


@pytest.mark.parametrize("vraag,melding", [("/contenttoets", ct.LEEG), ("/contenttoets kort", ct.LEEG),
                                           ("/contenttoets " + "x" * (ct.MAX_TEKENS + 1), ct.TE_LANG[:20])])
def test_zonder_of_met_te_veel_tekst_een_vaste_zin(vraag, melding):
    node, upd = _route(vraag)
    assert node == "afwijzen" and upd["afwijs_melding"].startswith(melding)


@pytest.mark.parametrize("vraag,ja", [("/contenttoets tekst", True), ("  /Contenttoets\ntekst", True),
                                      ("/contenttoetsen tekst", False), ("Valideer /contenttoets", False), ("", False)])
def test_het_commando_herkennen(vraag, ja):
    assert ct.is_contenttoets(vraag) is ja


def test_de_peildatum_staat_vooraan_en_anders_geldt_vandaag():
    vandaag = date(2026, 11, 25)
    assert ct.ontleed(f"/contenttoets {TEKST}", vandaag=vandaag) == (TEKST, "2026-11-25")
    assert ct.ontleed(f"/contenttoets peildatum=1-3-2026 {TEKST}", vandaag=vandaag) == (TEKST, "2026-03-01")
    assert ct.ontleed(f"/contenttoets peildatum: 2026-01-31\n{TEKST}", vandaag=vandaag) == (TEKST, "2026-01-31")
    # Een datum die niet bestaat, blijft tekst; dan geldt vandaag.
    assert ct.ontleed("/contenttoets peildatum=31-2-2026 x", vandaag=vandaag)[1] == "2026-11-25"


def test_de_voorbereiding_zet_de_content_in_het_bronspoor(monkeypatch):
    import agent.nodes.contenttoets as node
    monkeypatch.setattr(node, "get_stream_writer", lambda: (lambda _e: None))
    uit = bereid_contenttoets_node(_bouw(True), {"question": f"/contenttoets peildatum=2026-03-01 {TEKST}",
                                                 "source_trace": [("x", "{}")]})
    assert uit["source_trace"][0] == ("x", "{}") and uit["source_trace"][-1][0] == CONTENT_TOOL
    gegeven = content_van(uit["source_trace"])
    assert (gegeven["content"], gegeven["peildatum"]) == (TEKST, "2026-03-01")
    assert "messages" not in uit                       # de content staat al in de vraag; geen extra bericht


def test_het_profiel_is_een_plugin_naast_de_wetsanalyse():
    p = profielen.PROFIELEN["contenttoets"]
    assert p.rol == "contenttoets" and not p.kiesbaar
    assert "antwoord_contenttoets" in p.sjablonen
    assert not set(p.tools) & profielen.TOOLS_VAN_WETSANALYSE
    assert "contenttoets" not in skills.namen()       # niet in het voorvoegsel van de centrale agent


def test_het_pluginregister_klopt_met_profiel_actie_en_sjabloon():
    from agent.sjablonen import SJABLONEN

    assert PLUGIN_ACTIES == tuple(p.actie for p in PLUGINS)
    for p in PLUGINS:
        assert p.profiel in profielen.PROFIELEN and p.sjabloon in SJABLONEN
    assert CONTENTTOETS.commando == ct.COMMANDO.lstrip("/")


def test_de_bronstand_zegt_dat_de_contenttoets_alleen_de_graaf_gebruikt(monkeypatch):
    # Meting C5b: het bronstand-event noemde de connectors uit het gespreksmenu als aan, terwijl de contenttoets alleen
    # de kennisgraaf gebruikt (besluit 26 nov 2026).
    from agent import bronstand
    events = []
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: events.append)
    stand = {"kamerstukken": {"naam": "kamerstukken", "label": "Kamerstukken", "aan": True, "reden": "aan"},
             "rechtspraak": {"naam": "rechtspraak", "label": "Rechtspraak", "aan": False, "reden": "gesprek"}}
    _, upd = _route(f"/contenttoets {TEKST}", stand=stand)
    assert upd["bronnen"] == [] and upd["bronstand"]["kamerstukken"]["reden"] == "werkwijze"
    assert upd["bronstand"]["rechtspraak"]["reden"] == "gesprek"  # wat al uit stond, blijft zo
    assert "bronkeuze" not in upd  # de keuze voor de vervolgvraag blijft van het gesprek
    [ev] = [e for e in events if e.get("type") == "bronstand"]
    assert {b["naam"]: b["reden"] for b in ev["bronnen"]} == {"kamerstukken": "werkwijze", "rechtspraak": "gesprek"}
    # De prompt noemt een bron die de werkwijze niet gebruikt niet.
    assert "Kamerstukken" not in bronstand.prompt_blok(upd["bronstand"])
    assert "deze werkwijze" in bronstand.uit_zin(upd["bronstand"], "kamerstukken")


def test_zonder_connectors_aan_geen_tweede_event(monkeypatch):
    events = []
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: events.append)
    _, upd = _route(f"/contenttoets {TEKST}")
    assert "bronstand" not in upd and not [e for e in events if e.get("type") == "bronstand"]
