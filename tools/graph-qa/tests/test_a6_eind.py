"""De fixes na het eindverslag van A6 (15 nov 2026, `docs/architectuur/metingen/centrale-agent-2026-11-15-a6-eind/`), met
de gevallen uit die meting als test.

1. V03: het kind vond drie memories van toelichting, las ze "wegens rondegrens" niet en rondde `klaar` af over de
   wettekst. Een rapport zonder één gelezen stuk van de gevraagde bron wordt een vraag naar boven (`ongelezen_vraag`).
2. V04: "vóór en na de wijziging" zonder te zeggen welke: de code vraagt het de jurist (`welke_wijziging`).
3. F02: op "artikel 30?" antwoordde de jurist "De Invorderingswet 1990."; de code maakt de vorige opdracht af
   (`subagent_route.aangevuld`) in plaats van een nieuwe keuzevraag.
4. F03: de markering `later_gewijzigd` per deelgesprek, en de stand gelezen in code bij een vraag erover.
5. F05: een tekstantwoord per kop over gelezen bepalingen krijgt per kop een zin uit de bron (`tekstcitaten`).
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from agent import overdracht, tekstcitaten, welke_wijziging
from agent import subagent as sub
from agent.models import SubagentOpdracht
from agent.nodes import antwoord as antwoordnodes
from agent.nodes import subagent_route as route
from agent.nodes import supervisie
from test_a6_run1 import AGENTSET, regelingen
from test_subagent import STATE, Api, _kinderen

RECHTSPRAAK = {"rechtspraak": {"naam": "rechtspraak", "label": "Rechtspraak", "aan": True, "reden": "aan"}}

# 1. V03 ----------------------------------------------------------------------------------------------------------------

V03 = SubagentOpdracht(doel=AGENTSET["V03"]["opdracht"], oplevering="Per deelvraag de kern.")
GEVONDEN = ("zoek_kamerstukken", json.dumps({"status": "ok", "volledig": True, "resultaten": [
    {"id": "kst-36369-3", "label": "Kamerstuk 36369, nr. 3", "soort": "Memorie van toelichting"},
    {"id": "kst-36207-3", "label": "Kamerstuk 36207, nr. 3", "soort": "Memorie van toelichting"},
    {"id": "kst-36309-3", "label": "Kamerstuk 36309, nr. 3", "soort": "Memorie van toelichting"}]}))
WETTEKST = ("get_artikel", json.dumps({"status": "ok", "volledig": True, "artikel": {"iri": "urn:bwb:BWBR0004770:artikel:21"},
                                       "resultaten": [{"lid": "urn:bwb:BWBR0004770:artikel:21:lid:1", "nummer": "1",
                                                       "tekst": "’s Rijks schatkist heeft een voorrecht op alle goederen."}]}))
GELEZEN = ("get_kamerstuk", json.dumps({"status": "ok", "volledig": True, "stuk": {"id": "kst-36369-3", "label": "36369-3"},
                                        "resultaten": [{"nr": 1, "tekst": "Memorie van toelichting."}]}))


def test_v03_een_rapport_zonder_gelezen_memorie_is_een_vraag_aan_de_jurist():
    vraag = sub.ongelezen_vraag(V03, {"source_trace": [WETTEKST, GEVONDEN]})
    assert vraag["tekst"].startswith("Ik vond 3 stukken maar las ze niet") and vraag["tekst"].endswith("?")
    assert vraag["opties"] == [sub.LEES_ZE, sub.NIET_LEZEN] and len(vraag["tekst"]) <= 300
    assert sub.ongelezen_vraag(V03, {"source_trace": [WETTEKST, GEVONDEN, GELEZEN]}) is None, "één gelezen is genoeg"
    assert sub.ongelezen_vraag(V03, {"source_trace": [WETTEKST]}) is None, "niets gevonden: het rapport zegt het zelf"
    graaf = SubagentOpdracht(doel="Loop het hoofdstuk over dwanginvordering door.", oplevering="x")
    assert sub.ongelezen_vraag(graaf, {"source_trace": [GEVONDEN]}) is None, "de opdracht vroeg geen bron naast de wet"


def test_v03_de_afloop_wordt_een_vraag_en_de_beurt_eindigt_met_de_kaart():
    kind = {"rapport": {"status": "klaar"}, "answer": "Gedaan: wettekst gelezen.", "source_trace": [WETTEKST, GEVONDEN]}
    kinderen, _, _ = _kinderen(kind)
    afloop, _, _ = asyncio.run(sub.voer_uit(STATE, "algemeen", V03, lambda _e: None, settings=None, kinderen=kinderen,
                                            gestopt=lambda: False, api=Api()))
    assert afloop.uitkomst == "vraag" and afloop.vragen and afloop.met_rapport()
    assert sub.eindstand([afloop.als_dict()]) == "wacht"
    afloop.delegatie_id = "d1"
    assert antwoordnodes.open_vraag([afloop.als_dict()]), "finalize sluit af met de vraagkaart"


# 2. V04 ----------------------------------------------------------------------------------------------------------------

def test_v04_de_wijziging_zonder_te_zeggen_welke():
    titel = "Invorderingswet 1990"
    assert welke_wijziging.vraagt_welke(AGENTSET["V04"]["opdracht"], titel)
    for vraag in ("Vergelijk artikel 36 van de Invorderingswet 1990 van vóór en na de laatste wijziging.",
                  "Vergelijk artikel 36 van de Invorderingswet 1990 vóór en na de wijziging van 2010.",
                  "Vergelijk artikel 36 van de Invorderingswet 1990 vóór en na de wijziging bij Stb. 2009, 610.",
                  "Wat zegt artikel 36 van de Invorderingswet 1990?"):
        assert not welke_wijziging.vraagt_welke(vraag, titel), vraag


def test_v04_de_vraag_noemt_de_laatste_wijziging_als_kandidaat(monkeypatch):
    import agent.overzicht as overzicht

    monkeypatch.setattr(overzicht, "regelingen_in_vraag", lambda _g, v: regelingen(v))
    monkeypatch.setattr(welke_wijziging, "laatste_wijziging", lambda _g, b, a: "Stb. 2009, 610 (in werking 2010-07-04)")
    tekst = welke_wijziging.melding(AGENTSET["V04"]["opdracht"], object())
    assert tekst.startswith("Artikel 36 van de Invorderingswet 1990 kan meer dan eens gewijzigd zijn. Welke wijziging")
    assert "- de laatste wijziging: Stb. 2009, 610 (in werking 2010-07-04)" in tekst and "noem de datum" in tekst
    assert welke_wijziging.melding("Wat zegt artikel 36?", object()) == "", "geen wijziging genoemd: geen graafquery"


def test_v04_de_supervisor_vraagt_het_zonder_model(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    monkeypatch.setattr(supervisie, "welke_wijziging", lambda v, g: "Welke wijziging bedoel je?")
    b = SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan", legt_zelf_vast=True), graph=object(), kinderen=None)
    upd = supervisie._kies(b, {**STATE, "question": AGENTSET["V04"]["opdracht"], "modus": "auto", "agentvorm": "centraal"})
    assert upd["afwijzen"] and upd["afwijs_melding"] == "Welke wijziging bedoel je?"


def test_v04_de_geldigheid_wordt_een_leesbare_kandidaat(monkeypatch):
    import agent.tools as tools

    monkeypatch.setattr(tools, "dispatch", lambda *_a, **_k: json.dumps(
        {"status": "ok", "resultaten": [{"bron": "Stb.2009-610", "bepalingInwerking": "2010-07-04"}]}))
    assert welke_wijziging.laatste_wijziging(None, "BWBR0004770", "36") == "Stb. 2009, 610 (in werking 2010-07-04)"
    monkeypatch.setattr(tools, "dispatch", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("graaf weg")))
    assert welke_wijziging.laatste_wijziging(None, "BWBR0004770", "36") == ""


# 3. F02 ----------------------------------------------------------------------------------------------------------------

V01 = AGENTSET["V01"]["opdracht"]


def test_f02_het_antwoord_maakt_de_vorige_opdracht_af():
    opdracht = route.aangevuld("De Invorderingswet 1990.", V01, regelingen)
    assert "artikel 30 van de Invorderingswet 1990" in opdracht and opdracht.endswith("over de rente zegt.")
    [(profiel, o)] = route.plan(opdracht, RECHTSPRAAK, regelingen)
    assert profiel == "algemeen" and o.doel == opdracht
    # Alleen een antwoord dat één regeling noemt, op een opdracht met een artikel zonder regeling.
    assert route.aangevuld("Ja, graag.", V01, regelingen) == ""
    assert route.aangevuld("De Invorderingswet 1990.", "Wat is invorderingsrente?", regelingen) == ""
    assert route.aangevuld("Artikel 31 van de Invorderingswet 1990.", V01, regelingen) == ""


def test_f02_de_supervisor_geeft_de_afgemaakte_opdracht_aan_een_subagent(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    monkeypatch.setattr(supervisie, "_regelingtitels", lambda _g: regelingen)
    berichten = [{"role": "user", "content": V01},
                 {"role": "assistant", "content": [{"type": "text", "text": "Welke regeling bedoel je met artikel 30?"}]},
                 {"role": "user", "content": "De Invorderingswet 1990."}]
    b = SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan", legt_zelf_vast=True), graph=None, kinderen=object())
    state = {**STATE, "question": "De Invorderingswet 1990.", "modus": "auto", "agentvorm": "centraal",
             "bronstand": RECHTSPRAAK, "messages": berichten}
    upd = supervisie._kies(b, state)
    assert upd["specialist"] == "subagent_route" and "artikel 30 van de Invorderingswet 1990" in upd["zelfstandige_vraag"]
    assert upd["subagent_plan"][0]["opdracht"]["doel"] == upd["zelfstandige_vraag"]


# 4. F03 ----------------------------------------------------------------------------------------------------------------

STAND = [{"id": "d2", "soort": "regie", "status": "klaar", "later_gewijzigd": True,
          "plan": {"taken": [{"titel": "Deelvraag 1: bodemrecht"}, {"titel": "Deelvraag 2: verrekening"},
                             {"titel": "Deelvraag 3: derdenbeslag"}]},
          "uitkomst": {"kinderen": [{"uitkomst": "klaar", "gesprek_id": "k1", "later_gewijzigd": True},
                                    {"uitkomst": "klaar", "gesprek_id": "k2"}, {"uitkomst": "klaar", "gesprek_id": "k3"}]}}]


def test_f03_de_stand_zegt_per_deelgesprek_waar_is_doorgevraagd():
    tekst = overdracht.stand_tekst(STAND)
    assert "in 1 van de 3 deelgesprekken is later doorgevraagd" in tekst
    assert "Deelvraag 1: bodemrecht (regie): klaar, deelgesprek k1, hierin is later doorgevraagd" in tekst
    assert "Deelvraag 2: verrekening (regie): klaar, deelgesprek k2, hierin is niet doorgevraagd" in tekst


def test_f03_een_vraag_over_de_deelgesprekken_leest_de_stand_in_code(monkeypatch):
    assert overdracht.is_standvraag(AGENTSET["F03"]["opdracht"])
    assert not overdracht.is_standvraag("Wat zegt artikel 22 over het bodemrecht?")
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    monkeypatch.setattr(supervisie, "_delegatie_stand", lambda _b, _s, _i: ({}, overdracht.stand_tekst(STAND)))
    b = SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan", legt_zelf_vast=True), graph=None, kinderen=None)
    upd = supervisie._kies(b, {**STATE, "question": AGENTSET["F03"]["opdracht"], "modus": "auto",
                               "agentvorm": "centraal"})
    assert upd["specialist"] == "centraal" and "in 1 van de 3 deelgesprekken" in upd["rapporten"]


def test_f03_doorvragen_in_een_deelgesprek_noemt_dat_deelgesprek(monkeypatch):
    gezet: list[dict] = []

    class Api_:
        async def wijzig_delegatie(self, _id, waarden):
            gezet.append(waarden)

    from contextlib import asynccontextmanager

    import agent.nodes.context as context

    @asynccontextmanager
    async def met_api(_b, _u):
        yield Api_()

    monkeypatch.setattr(context, "met_api", met_api)
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    b = SimpleNamespace(settings=SimpleNamespace(legt_zelf_vast=True), loop=None)
    supervisie._deelgesprek(b, lambda _e: None, {**STATE, "gesprek_id": "k1"},
                            {"profiel": "algemeen", "delegatie_id": "d2"})
    assert gezet == [{"later_gewijzigd": True, "deelgesprek": "k1"}]


# 5. F05 ----------------------------------------------------------------------------------------------------------------

def _bepaling(nummer: str, tekst: str) -> tuple[str, str]:
    iri = f"urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie24%2FCirculaire.divisie{nummer}"
    return ("get_bepaling", json.dumps({"status": "ok", "volledig": True, "resultaten": [], "bepaling": {
        "iri": iri, "nummer": nummer, "label": f"Leidraad Invordering 2008, {nummer}", "tekst": tekst}}))


F05_TRACE = [
    _bepaling("24.1", "Verrekening vindt niet van rechtswege plaats. Of de ontvanger verrekent, beslist hij zelf. Verzoekt "
                      "de belastingschuldige om een teruggaaf met een openstaande aanslag te verrekenen, dan willigt de "
                      "ontvanger dat verzoek in."),
    _bepaling("24.2", "De ontvanger verrekent in het algemeen niet met een bedrag waarvan de verschuldigdheid wordt betwist."),
]
F05_TEKST = ("De Leidraad werkt artikel 24 op deze onderwerpen uit:\n\n**24.1 – Wanneer verrekening**\n"
             "Verrekening vindt niet van rechtswege plaats: de ontvanger beslist zelf of hij verrekent.\n\n"
             "**24.2 – Betwiste schuld**\nIn het algemeen verrekent de ontvanger niet met een bedrag dat de "
             "belastingschuldige betwist.\n\n**24.9 – Niet gelezen**\nIets anders.")


def test_f05_een_tekstantwoord_per_kop_krijgt_per_gelezen_bepaling_een_zin_uit_de_bron():
    citaten = tekstcitaten.uit_tekst(F05_TEKST, F05_TRACE)
    assert [c.tekst for c in citaten] == ["Verrekening vindt niet van rechtswege plaats.",
                                          "De ontvanger verrekent in het algemeen niet met een bedrag waarvan de "
                                          "verschuldigdheid wordt betwist."]
    assert all("divisie24" in c.vindplaats.iri for c in citaten), "de vindplaats komt uit de rij"


def test_f05_de_centrale_agent_krijgt_ze_onder_zijn_tekst():
    state = {"specialist": "centraal", "source_trace": F05_TRACE}
    met = antwoordnodes.met_rapportcitaten(state, F05_TEKST)
    assert [b.soort for b in met.blokken] == ["toelichting", "citaten"] and len(met.blokken[1].items) == 2
    assert antwoordnodes.met_rapportcitaten({**state, "specialist": "duiding"}, F05_TEKST) is None, "alleen centraal"
    assert antwoordnodes.met_rapportcitaten(state, "Geen koppen, dus geen citaten.") is None
