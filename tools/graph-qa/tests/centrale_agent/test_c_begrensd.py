"""Een kind dat op zijn grens stopt, vraagt of het verder mag (plan centrale agent na A6, PR C).

In de laatste ronde koos een kind aan zijn rondegrens `klaar` of `niet_gelukt`, met de ongelezen nummers onder 'Open',
en de jurist hoorde niets (V03 in run 3; S04, F02 en P01 lieten stukken ongelezen). `ongelezen_vraag` ving alleen het
geval waarin het kind van de gevraagde bron níéts las. Nu geldt de regel voor elk kind dat op zijn grens stopte terwijl
er nog iets open was: een vraag uit code, één keer. Dezelfde nepstukken als `test_a6_eind.py`."""
from __future__ import annotations

import asyncio
import json

from agent import subagent as sub
from agent.models import SubagentOpdracht
from agent.nodes import antwoord as antwoordnodes
from test_a6_eind import GELEZEN, GEVONDEN, V03, WETTEKST
from test_subagent import STATE, Api, _kinderen

#: Twee memories gevonden, één gelezen: `ongelezen_vraag` zweeg hier, want er was er één gelezen.
EEN_VAN_DRIE = [WETTEKST, GEVONDEN, GELEZEN]


def test_een_kind_op_zijn_grens_met_ongelezen_stukken_vraagt_of_het_verder_mag():
    vraag = sub.begrensd_vraag(V03, {"begrensd": True, "source_trace": EEN_VAN_DRIE})
    assert vraag and vraag["opties"] == [sub.LEES_VERDER, sub.NIET_LEZEN]
    assert "niet gelezen: Kamerstuk 36207, nr. 3, Kamerstuk 36309, nr. 3" in vraag["tekst"], vraag["tekst"]
    assert vraag["tekst"].endswith("Zal ik verder lezen?") and len(vraag["tekst"]) <= sub.MAX_VRAAG_TEKENS


def test_wat_het_rapport_open_laat_telt_ook_bij_een_reeks_in_de_graaf():
    """S04: een reeks onderdelen van de Leidraad, het kind zet de ongelezen nummers onder 'Open'."""
    opdracht = SubagentOpdracht(doel="Geef per onderdeel van de Leidraad bij artikel 22 de kern.", oplevering="x")
    kind = {"begrensd": True, "source_trace": [WETTEKST],
            "rapport": {"status": "klaar", "open": ["Onderdelen 22.8.9 tot en met 22.9.3 niet gelezen."]}}
    vraag = sub.begrensd_vraag(opdracht, kind)
    assert vraag and "nog open: Onderdelen 22.8.9 tot en met 22.9.3 niet gelezen." in vraag["tekst"]


def test_geen_vraag_zonder_grens_of_zonder_iets_open():
    # Het kind vond zelf dat het genoeg had: geen grens, geen vraag.
    assert sub.begrensd_vraag(V03, {"source_trace": EEN_VAN_DRIE}) is None
    # Op zijn grens, maar alles gelezen en niets open.
    alles = [WETTEKST, GELEZEN]
    assert sub.begrensd_vraag(V03, {"begrensd": True, "source_trace": alles, "rapport": {"open": []}}) is None


def test_een_stuk_van_buiten_de_periode_telt_niet():
    """De jurist koos een periode; een uitspraak van daarbuiten las het kind terecht niet."""
    opdracht = SubagentOpdracht(doel="Vat de rechtspraak bij artikel 36 samen.", oplevering="x")
    gevonden = ("zoek_uitspraken", json.dumps({"status": "ok", "volledig": True, "resultaten": [
        {"id": "ECLI:NL:HR:2015:100", "label": "HR 2015"}]}))
    kind = {"begrensd": True, "source_trace": [gevonden]}
    assert sub.begrensd_vraag(opdracht, kind, [2020, 2026]) is None
    assert sub.begrensd_vraag(opdracht, kind, [2010, 2026]) is not None


def test_niet_gelukt_op_de_grens_krijgt_een_aanbod_en_geen_poort_en_niet_na_een_hervatting():
    """Sinds de meting na het plan (16 nov 2026): de uitkomst blijft `niet_gelukt`, het rapport gaat door, en het aanbod
    staat als kaart onder het antwoord."""
    kind = {"rapport": {"status": "niet_gelukt", "open": []}, "answer": "Gedaan.", "begrensd": True,
            "source_trace": EEN_VAN_DRIE}
    kinderen, _, _ = _kinderen(kind)
    afloop, _, _ = asyncio.run(sub.voer_uit(STATE, "algemeen", V03, lambda _e: None, settings=None, kinderen=kinderen,
                                            gestopt=lambda: False, api=Api()))
    assert afloop.uitkomst == "niet_gelukt" and afloop.aanbod and afloop.vragen[0]["opties"][0] == sub.LEES_VERDER
    assert sub.eindstand([afloop.als_dict()]) == "klaar"
    afloop.delegatie_id = "d1"
    assert not antwoordnodes.open_vraag([afloop.als_dict()]) and sub.open_aanbod([afloop.als_dict()])

    # Na een hervatting geen tweede aanbod: het kind rondt af met wat het heeft.
    kinderen, _, _ = _kinderen(kind)
    hervat = sub.Afloop(profiel="algemeen", delegatie_id="d1", gesprek_id="g1", hervat=True)
    asyncio.run(sub._draai_kind(hervat, "t", "algemeen", V03, lambda _e: None, gesprek_id="o", werkgebied_id="",
                                run_id="r", user_id="u", bronnen=None, api=Api(), kinderen=kinderen,
                                gestopt=lambda: False, vraag="Ja, lees verder"))
    assert hervat.uitkomst == "niet_gelukt" and not hervat.aanbod, hervat.uitkomst


def test_een_kind_dat_in_zijn_laatste_ronde_zijn_rapport_schrijft_krijgt_niets():
    """(a) De meting na het plan: alle vijf de kinderen schreven hun rapport in hun laatste ronde (`begrensd`), met iets
    onder 'Open' en ongelezen treffers, en kregen allemaal een vraag die het antwoord tegenhield. Een kind dat `klaar`
    meldt, krijgt geen vraag en geen aanbod."""
    kind = {"rapport": {"status": "klaar", "open": ["De tweede pagina van de treffers is niet gelezen."]},
            "answer": "Gedaan.", "begrensd": True, "source_trace": EEN_VAN_DRIE}
    kinderen, _, _ = _kinderen(kind)
    afloop, _, _ = asyncio.run(sub.voer_uit(STATE, "algemeen", V03, lambda _e: None, settings=None, kinderen=kinderen,
                                            gestopt=lambda: False, api=Api()))
    assert afloop.uitkomst == "klaar" and not afloop.aanbod and not afloop.vragen
    assert sub.eindstand([afloop.als_dict()]) == "klaar"


def test_een_te_lange_toelichting_wordt_ingekort_niet_weggelaten():
    opdracht = SubagentOpdracht(doel="Vat de rechtspraak bij artikel 36 samen.", oplevering="x")
    lang = "Van de gelezen stukken zijn alleen de eerste pagina's gelezen; " * 10
    vraag = sub.begrensd_vraag(opdracht, {"begrensd": True, "source_trace": [], "rapport": {"open": [lang]}})
    assert vraag and "nog open: Van de gelezen stukken" in vraag["tekst"] and "…" in vraag["tekst"]
    assert len(vraag["tekst"]) <= sub.MAX_VRAAG_TEKENS


def test_de_laatste_ronde_reist_mee_in_het_resultaat_van_het_kind():
    """`begrensd` komt uit `State.laatste_gehad`: de vlag die `agent_node` zet in de ronde van de grens."""
    import inspect

    from agent import agent

    assert "begrensd=bool(laatste.get(\"laatste_gehad\"))" in inspect.getsource(agent.answer_stream)


# -- de klik op het aanbod (`subagent_vervolg`) ----------------------------------------------------------------

def _aanbod_api():
    from test_subagent_vragen import Api as VraagApi

    api = VraagApi(status="klaar")
    api.delegatie["uitkomst"]["kinderen"][0].update(
        uitkomst="klaar", aanbod=True,
        vragen=[{"tekst": "Ik kwam aan de grens … Zal ik verder lezen?", "opties": [sub.LEES_VERDER, sub.NIET_LEZEN]}])
    return api


def test_nee_op_een_aanbod_hervat_niets_en_laat_het_antwoord_staan(monkeypatch):
    from agent.nodes import subagent_vervolg as vervolg
    from test_subagent_vragen import _draai_vervolg, _klik

    api = _aanbod_api()
    kinderen, gestart, _ = _kinderen({})
    upd, _ = _draai_vervolg(monkeypatch, api, kinderen, _klik(keuzes=[sub.NIET_LEZEN]))
    assert not gestart and upd["answer"] == vervolg.AANBOD_AFGESLAGEN
    kind = api.delegatie["uitkomst"]["kinderen"][0]
    assert not kind.get("aanbod") and api.delegatie["status"] == "klaar"
    # Een tweede klik op dezelfde kaart doet niets meer.
    upd, _ = _draai_vervolg(monkeypatch, api, kinderen, _klik(keuzes=[sub.LEES_VERDER]))
    assert not gestart and upd["answer"] == sub.AL_BEANTWOORD


def test_ja_op_een_aanbod_hervat_het_kind_ook_als_de_delegatie_klaar_is(monkeypatch):
    from agent.nodes import subagent_vervolg as vervolg
    from test_subagent_vragen import _draai_vervolg, _klik

    api = _aanbod_api()
    kinderen, gestart, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "Bevindingen: verder gelezen.",
                                      "source_trace": [WETTEKST]})
    upd, events = _draai_vervolg(monkeypatch, api, kinderen, _klik(keuzes=[sub.LEES_VERDER]))
    [(verzoek, _, _)] = gestart
    assert sub.LEES_VERDER in verzoek.question
    assert "Bevindingen: verder gelezen." in upd["rapporten"] and vervolg.route_na_vervolg(None, upd) == "agent"
    assert not any(e["type"] == "vraagkaart" for e in events)


def test_finalize_schrijft_het_antwoord_en_zet_het_aanbod_eronder(monkeypatch):
    """Het antwoord gaat eerst (`token`), daarna de kaart als keuze; `agent_node` sluit de beurt niet af."""
    from types import SimpleNamespace

    from fakes import FakeGraph, FakeLLM, make_settings

    events = []
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: events.append)
    b = SimpleNamespace(settings=make_settings(), graph=FakeGraph(), llm=FakeLLM([]))
    kind = {"uitkomst": "niet_gelukt", "aanbod": True, "delegatie_id": "d1", "rapport": True,
            "vragen": [{"tekst": "Zal ik verder lezen?", "opties": [sub.LEES_VERDER, sub.NIET_LEZEN]}]}
    state = {"answer": "Dit vond de subagent.", "question": "x", "source_trace": [], "subagenten": [kind], "messages": []}
    antwoordnodes.finalize_node(b, state)
    soorten = [e["type"] for e in events]
    assert soorten.index("token") < soorten.index("vraagkaart")
    [kaart] = [e["vraagkaart"] for e in events if e["type"] == "vraagkaart"]
    assert kaart["toelichting"] == sub.AANBOD_TOELICHTING and kaart["intake_id"] == "sa-d1"
    assert antwoordnodes.open_vraag([kind]) is None, "agent_node schrijft gewoon het antwoord"


# -- (b) hervatten met een grote bundel -----------------------------------------------------------------------

#: Een rapport ver boven de grens: veel citaten en lange bevindingen, zoals bij een kind dat tien uitspraken las.
GROOT = "\n".join([*(f"**ECLI:NL:HR:2099:{n}** — bevinding {n}: " + "de ontvanger moet aannemelijk maken " * 30
                     for n in range(60)),
                   *(f'> "Citaat {n}: ' + "het doel van de meldingsplicht is dat de ontvanger vroeg weet " * 20 + '"'
                     for n in range(200))])


def test_hervatten_met_een_grote_bundel_past_in_de_vraag(monkeypatch):
    """Na "Ja, lees verder" draagt de beurt de bundel van het hervatte kind: per rapport hoogstens `MAX_RAPPORT` tekens
    (`onschadelijk`), met de kop erbij, ook als het rapport veel groter is. De meting na het plan (16 nov 2026) zag na
    een hervatting een 400 zonder tokens; de bundel bleek daar niet de oorzaak, maar deze grens moet blijven."""
    from test_subagent_vragen import _draai_vervolg, _klik

    api = _aanbod_api()
    kinderen, gestart, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": GROOT, "source_trace": [WETTEKST]})
    upd, _ = _draai_vervolg(monkeypatch, api, kinderen, _klik(keuzes=[sub.LEES_VERDER]))
    assert gestart and len(GROOT) > 10 * sub.MAX_RAPPORT
    assert len(upd["rapporten"]) < sub.MAX_RAPPORT + 2_000, len(upd["rapporten"])
    assert WETTEKST in upd["source_trace"], "de trace blijft heel: de controle toetst ertegen"


def test_met_meer_kinderen_blijft_elk_rapport_binnen_zijn_grens():
    paren = [(sub.Afloop(profiel="algemeen", uitkomst="klaar", rapport=True),
              {"rapport": {"status": "klaar"}, "answer": GROOT}) for _ in range(sub.MAX_SUBAGENTS)]
    assert len(sub.bundel_rapporten(paren)) < sub.MAX_SUBAGENTS * (sub.MAX_RAPPORT + 2_000)


# -- een geweigerde aanroep is te herleiden ------------------------------------------------------------------

def test_een_geweigerde_aanroep_logt_de_opbouw_en_de_melding_van_de_provider(caplog):
    """De meting na het plan (16 nov 2026): na een hervatting faalde de centrale agent met een 400 zonder tokens, en de
    logs zeiden niet of de vraag te lang was of het schema te groot. `model_aanroep_fout` draagt nu de opbouw (tekens per
    deel) en het begin van de melding van de provider, zonder inhoud van het verzoek."""
    import logging

    import pytest

    from agent import llm_stap

    class Geweigerd(Exception):
        status_code = 400
        body = {"error": {"type": "invalid_request_error",
                          "message": "prompt is too long: 213456 tokens > 200000 maximum"}}

    class Weigert:
        meter = None

        def stream(self, **_k):
            class S:
                def __enter__(self):
                    raise Geweigerd("400")

                def __exit__(self, *_a):
                    return False
            return S()

    rol = llm_stap.Rol.STUKCONTROLE
    with caplog.at_level(logging.WARNING, logger=llm_stap.logger.name), pytest.raises(Geweigerd):
        with llm_stap.stroom(Weigert(), rol, model="m", system="geheim systeem", max_tokens=10,
                             messages=[{"role": "user", "content": "geheime vraag"}]):
            pass
    [regel] = [r for r in caplog.records if r.getMessage() == "model_aanroep_fout"]
    assert regel.provider_melding.startswith("prompt is too long") and regel.status == 400
    assert regel.beurt_tekens + regel.historie_tekens > 0 and regel.soort == "Geweigerd"
    assert "geheim" not in " ".join(str(v) for v in regel.__dict__.values()), "geen inhoud van het verzoek"
