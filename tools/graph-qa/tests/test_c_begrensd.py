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


def test_de_afloop_wordt_een_vraag_ook_na_niet_gelukt_en_niet_na_een_hervatting():
    kind = {"rapport": {"status": "niet_gelukt", "open": []}, "answer": "Gedaan.", "begrensd": True,
            "source_trace": EEN_VAN_DRIE}
    kinderen, _, _ = _kinderen(kind)
    afloop, _, _ = asyncio.run(sub.voer_uit(STATE, "algemeen", V03, lambda _e: None, settings=None, kinderen=kinderen,
                                            gestopt=lambda: False, api=Api()))
    assert afloop.uitkomst == "vraag" and afloop.vragen[0]["opties"][0] == sub.LEES_VERDER
    assert sub.eindstand([afloop.als_dict()]) == "wacht"
    afloop.delegatie_id = "d1"
    assert antwoordnodes.open_vraag([afloop.als_dict()]), "finalize sluit af met de vraagkaart"

    # Na een hervatting geen tweede vraag: het kind rondt af met wat het heeft.
    kinderen, _, _ = _kinderen(kind)
    hervat = sub.Afloop(profiel="algemeen", delegatie_id="d1", gesprek_id="g1", hervat=True)
    asyncio.run(sub._draai_kind(hervat, "t", "algemeen", V03, lambda _e: None, gesprek_id="o", werkgebied_id="",
                                run_id="r", user_id="u", bronnen=None, api=Api(), kinderen=kinderen,
                                gestopt=lambda: False, vraag="Ja, lees verder"))
    assert hervat.uitkomst == "niet_gelukt", hervat.uitkomst


def test_de_laatste_ronde_reist_mee_in_het_resultaat_van_het_kind():
    """`begrensd` komt uit `State.laatste_gehad`: de vlag die `agent_node` zet in de ronde van de grens."""
    import inspect

    from agent import agent

    assert "begrensd=bool(laatste.get(\"laatste_gehad\"))" in inspect.getsource(agent.answer_stream)
