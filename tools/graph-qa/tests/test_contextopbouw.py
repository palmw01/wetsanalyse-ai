"""De contextopbouw van een beurt (plan contextweergave, stap 1 en 2).

Stap 1: de indeling van een verzoek over de categorieën, in één maat, één keer berekend, met de rol erbij.
Stap 2: de verdeling in de eenheid van `usage`, het begin en het laatste verzoek per lus, het verbruik per rol, en de
`contextopbouw` op het `meting`-event en op het bericht.

Het verzoek aan het model blijft byte-gelijk: `tests/test_modelverzoeken.py` legt de kwargs van elke aanroepplek vast,
en hier staat dat het kader van de meting de provider niet bereikt.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import contextdelen as delen
from agent import verzoekopbouw
from agent.berichten import BEURTCONTEXT_KOP, _msg_lengte, beurt_start, met_beurtcontext
from agent.contextopbouw import VERSIE, contextopbouw, grootste_rest, verdeel
from agent.llm_stap import Rol, aanroep, stroom
from agent.models import MAX_AANROEPEN, Verbruiksmeter
from agent.modelvenster import STANDAARD, VENSTERS, modelvenster
from agent.observability import GEHEIME_VELDEN, JsonFormatter
from agent.prompts import SYSTEM_PROMPT
from agent.verzoekopbouw import opbouw, samenstelling
from fakes import FakeGraph, make_settings, text_block, tool_block

ROOT = Path(__file__).resolve().parents[3]
API_CONTRACT = ROOT / "api" / "app" / "gesprek_contracts.py"


def _json(deel) -> int:
    return len(json.dumps(deel, ensure_ascii=False))


def _tool(naam: str) -> dict:
    return {"name": naam, "description": f"De tool {naam}.", "input_schema": {"type": "object", "properties": {}}}


def _connectortool() -> str:
    from agent.tools import CONNECTOR_TOOLS
    return sorted(CONNECTOR_TOOLS)[0]


def _sjabloon() -> str:
    from agent.sjablonen import SJABLONEN
    return sorted(SJABLONEN)[0]


TOOLS = [_tool("get_artikel"), _tool(_connectortool()), _tool(_sjabloon()), _tool("classificeer")]
STABIEL = SYSTEM_PROMPT + "\n\nSPECIALIST: je legt uit wat een bepaling regelt."
CONTEXT = "AANPAK (door jou gepland):\nzoek artikel 9 op"


def _historie() -> list[dict]:
    return [
        {"role": "user", "content": "eerste vraag"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t0", "name": "get_artikel", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t0", "content": "oude tekst"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "eerste antwoord"}]},
    ]


def _beurt() -> list[dict]:
    return [
        {"role": "user", "content": "tweede vraag"},
        {"role": "assistant", "content": [{"type": "text", "text": "ik zoek het op"},
                                          {"type": "tool_use", "id": "t1", "name": "get_artikel", "input": {"a": 9}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "tekst van artikel 9"}]},
    ]


# ── Stap 1: het register en de indeling ──────────────────────────────────────────────────────────────────────────────

def test_het_register_heeft_elke_categorie_een_keer_in_vaste_volgorde():
    assert delen.IDS == ("systeem", "methode", "graaftools", "connectortools", "agenttools", "sjablonen", "beurtcontext", "opdracht",
                         "historie", "beurt", "toolresultaten", "overig")
    assert len(set(delen.IDS)) == len(delen.IDS)
    assert delen.VOORVOEGSEL == {"systeem", "methode", "graaftools", "connectortools", "agenttools", "sjablonen"}
    assert all(c.omschrijving for c in delen.CATEGORIEEN)


def test_een_tool_valt_in_de_categorie_van_zijn_register():
    assert delen.tool_categorie("get_artikel") == delen.GRAAFTOOLS
    assert delen.tool_categorie(_connectortool()) == delen.CONNECTORTOOLS
    assert delen.tool_categorie(_sjabloon()) == delen.SJABLONEN
    assert delen.tool_categorie("classificeer") == delen.OVERIG


def test_elke_tool_van_de_antwoordlus_valt_in_een_voorvoegselcategorie():
    """Een nieuwe connector of een nieuw sjabloon valt vanzelf goed: de indeling leest de registers, geen lijst."""
    from agent.sjablonen import SJABLONEN, sjabloon_schemas
    from agent.tools import TOOLS as ALLE

    namen = [t["name"] for t in ALLE] + [s["name"] for s in sjabloon_schemas(frozenset(SJABLONEN))]
    assert {delen.tool_categorie(n) for n in namen} == {delen.GRAAFTOOLS, delen.CONNECTORTOOLS, delen.SJABLONEN}


def test_alleen_de_toollussen_zijn_een_lus_en_elke_rol_kiest():
    assert {r for r in Rol if r.lus} == {Rol.OPHAAL, Rol.ANTWOORD, Rol.CENTRAAL}
    assert all(isinstance(r.lus, bool) and len(r.value) == 3 for r in Rol)


def test_elk_deel_valt_in_precies_een_categorie_en_de_som_is_het_geheel():
    berichten = _historie() + _beurt()
    venster, _ = met_beurtcontext(berichten, "tweede vraag", CONTEXT)
    s = samenstelling([STABIEL], TOOLS, venster, beurt_start=len(_historie()))
    geheel = sum(_json(t) for t in TOOLS) + _json(STABIEL) + sum(_json(m) for m in venster)
    assert sum(s.values()) == geheel
    assert set(s) <= set(delen.IDS) and list(s) == [c for c in delen.IDS if c in s]
    # Per categorie wat erin hoort.
    assert s["systeem"] == _json(SYSTEM_PROMPT) and s["methode"] == _json(STABIEL) - _json(SYSTEM_PROMPT)
    assert s["graaftools"] == _json(TOOLS[0]) and s["connectortools"] == _json(TOOLS[1])
    assert s["sjablonen"] == _json(TOOLS[2]) and s["overig"] == _json(TOOLS[3])
    assert s["beurtcontext"] == _json({"type": "text", "text": BEURTCONTEXT_KOP + CONTEXT})
    assert s["historie"] == sum(_json(m) for m in _historie())   # ook het oude toolresultaat is historie
    assert s["toolresultaten"] == _json(_beurt()[2]["content"][0])
    assert s["beurt"] == sum(_json(m) for m in venster[4:]) - s["beurtcontext"] - s["toolresultaten"]
    assert "opdracht" not in s


@pytest.mark.parametrize("plek", ["vraag", "systeem"])
def test_de_beurtcontext_wordt_op_beide_plekken_herkend(plek):
    """De meetvlag `beurtcontext_plek` zet de context in de systeemprompt; de indeling hangt niet af van de plek."""
    berichten = _historie() + _beurt()
    start = beurt_start(berichten, "tweede vraag")
    if plek == "systeem":
        s = samenstelling([STABIEL, CONTEXT], [], berichten, beurt_start=start)
        assert s["beurtcontext"] == _json(CONTEXT)
    else:
        venster, _ = met_beurtcontext(berichten, "tweede vraag", CONTEXT)
        # Zonder opgave wijst de kop het begin van de beurt aan.
        s = samenstelling([STABIEL], [], venster)
        assert s == samenstelling([STABIEL], [], venster, beurt_start=start)
        assert s["beurtcontext"] == _json({"type": "text", "text": BEURTCONTEXT_KOP + CONTEXT})
    assert s["systeem"] == _json(SYSTEM_PROMPT) and s["historie"] == sum(_json(m) for m in _historie())
    assert s["toolresultaten"] == _json(_beurt()[2]["content"][0])


def test_een_tussenbericht_van_de_code_verplaatst_het_begin_van_de_beurt_niet():
    """Het herhaalverzoek om een sjabloon is een platte user-beurt midden in de beurt; met het begin van de aanroeper
    blijft wat ervoor staat bij de beurt."""
    berichten = _historie() + _beurt() + [{"role": "assistant", "content": "een lijst"},
                                          {"role": "user", "content": "Je antwoordde met een lijst in tekst."}]
    s = samenstelling("x", [], berichten, beurt_start=4)
    assert s["historie"] == sum(_json(m) for m in _historie())
    # Ook de oudere velden volgen dat begin; zonder opgave telt de laatste platte user-beurt, zoals voorheen.
    lengte = sum(_msg_lengte(m) for m in _historie())
    assert opbouw(system="x", tools=[], messages=berichten, beurt_start=4)["historie_tekens"] == lengte
    assert opbouw(system="x", tools=[], messages=berichten)["historie_tekens"] > lengte


def test_een_opdracht_met_historie_wordt_goed_ingedeeld():
    """Een hervat kindgesprek (ADR-016 A4): het eerste bericht is de opdracht, daarna eigen historie en de beurt."""
    berichten = [{"role": "user", "content": "OPDRACHT: zoek de bronnen bij deelvraag 2"}] + _historie()[1:] + _beurt()
    s = samenstelling([STABIEL], [], berichten, beurt_start=4, opdracht=True)
    assert s["opdracht"] == _json(berichten[0])
    assert s["historie"] == sum(_json(m) for m in berichten[1:4])
    assert s["beurt"] + s["toolresultaten"] == sum(_json(m) for m in berichten[4:])
    # Een subagent in zijn eerste beurt: de opdracht ís de vraag, zonder historie.
    eerste = samenstelling([STABIEL], [], [berichten[0]], beurt_start=0, opdracht=True)
    assert eerste["opdracht"] == _json(berichten[0]) and "historie" not in eerste and "beurt" not in eerste


def test_wat_niet_in_te_delen_is_wordt_overig_en_de_som_klopt(monkeypatch):
    vreemd = [{"role": "user", "content": {"geen": "lijst"}}, "geen bericht", {"role": "user", "content": ["los"]}]
    s = samenstelling(None, [], vreemd)
    assert sum(s.values()) == sum(_json(m) for m in vreemd) and s["overig"] > 0
    # Faalt het indelen helemaal, dan is alles `overig`; de rest van de opbouw staat er nog.
    monkeypatch.setattr(verzoekopbouw, "samenstelling", lambda *a, **k: 1 / 0)
    o = opbouw(system="s", tools=TOOLS, messages=_beurt())
    assert list(o["samenstelling"]) == ["overig"] and o["samenstelling"]["overig"] > 0 and o["tools_aantal"] == 4


def test_de_samenstelling_draagt_geen_inhoud_en_geen_veld_met_token():
    o = opbouw(system=[STABIEL], tools=TOOLS, messages=_historie() + _beurt())
    tekst = json.dumps(o)
    assert "tweede vraag" not in tekst and "get_artikel" not in tekst
    assert not any("token" in k for k in [*o, *o["samenstelling"]])


# ── Stap 1: één berekening, de rol naar de meter, het verzoek byte-gelijk ────────────────────────────────────────────

def _usage(invoer=0, uitvoer=0, lees=0, schrijf=0, uur=None, **extra):
    u = SimpleNamespace(input_tokens=invoer, output_tokens=uitvoer, cache_read_input_tokens=lees,
                        cache_creation_input_tokens=schrijf, **extra)
    if uur is not None:
        u.cache_creation = SimpleNamespace(ephemeral_1h_input_tokens=uur, ephemeral_5m_input_tokens=schrijf - uur)
    return u


def _resp(blokken=(), stop="end_turn", **usage):
    return SimpleNamespace(content=list(blokken), stop_reason=stop, usage=_usage(**usage))


class _Provider:
    """`client.messages` van de SDK: onthoudt elk verzoek zoals het de deur uitgaat."""

    def __init__(self, antwoorden):
        self.antwoorden, self.verzoeken = list(antwoorden), []

    def create(self, **kw):
        self.verzoeken.append(kw)
        return self.antwoorden.pop(0)

    def stream(self, **kw):
        self.verzoeken.append(kw)
        resp = self.antwoorden.pop(0)
        return _Ctx(resp)


class _Ctx:
    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return SimpleNamespace(text_stream=iter([]), get_final_message=lambda: self._resp)

    def __exit__(self, *_a):
        return False


def _adapter(antwoorden, **settings):
    """De echte adapter met een nagebootste SDK-client: zo loopt de test over modelstap → adapter → meter."""
    from agent.adapters.anthropic_llm import AnthropicLLM

    llm = AnthropicLLM.__new__(AnthropicLLM)
    llm._caching = llm._historie_caching = settings.get("caching", True)
    llm._ttl = "1h"
    llm.meter = Verbruiksmeter()
    llm._client = SimpleNamespace(messages=_Provider(antwoorden))
    return llm


def _verzoek(**kw):
    return {"model": "claude-sonnet-4-6", "max_tokens": 100, "system": [STABIEL], "tools": TOOLS[:3],
            "messages": _historie() + _beurt(), **kw}


def test_het_kader_bereikt_de_provider_niet_het_verzoek_blijft_byte_gelijk():
    """Wat de adapter naar de provider stuurt is hetzelfde met en zonder de gedeelde modelstap en haar meetkader."""
    kaal = _adapter([_resp(), _resp()])
    kaal.create(**_verzoek())
    with kaal.stream(**_verzoek(), historie_cache=True, berichtpunten=(3,)) as s:
        s.final_message()
    via = _adapter([_resp(), _resp()])
    kader = {"beurt_start": 4, "opdracht": False, "venster_telling": {"beurten_venster": 2},
             "historiegrens_tekens": 40_000}
    aanroep(via, Rol.INTAKE, kader=kader, **_verzoek())
    with stroom(via, Rol.ANTWOORD, kader=kader, **_verzoek(), historie_cache=True, berichtpunten=(3,)) as s:
        s.final_message()
    a, b = kaal._client.messages.verzoeken, via._client.messages.verzoeken
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)
    assert not any("kader" in v or "beurt_start" in v for v in b)


def test_de_opbouw_wordt_per_aanroep_een_keer_berekend_en_de_rol_gaat_mee(monkeypatch, caplog):
    keren = []
    echt = verzoekopbouw.samenstelling
    monkeypatch.setattr(verzoekopbouw, "samenstelling", lambda *a, **k: keren.append(1) or echt(*a, **k))
    llm = _adapter([_resp(invoer=10), _resp(invoer=20)])
    with caplog.at_level(logging.INFO, logger="graph_qa.llm"):
        aanroep(llm, Rol.INTAKE, **_verzoek())
        with stroom(llm, Rol.ANTWOORD, kader={"beurt_start": 4}, **_verzoek()) as s:
            s.final_message()
    assert len(keren) == 2
    regels = [r for r in caplog.records if r.getMessage() == "model_aanroep"]
    eerste, tweede = llm.meter.aanroepen
    assert (eerste["rol"], tweede["rol"]) == ("intake", "antwoord") == (regels[0].rol, regels[1].rol)
    assert eerste["model"] == "claude-sonnet-4-6"
    # De logregel en de meter lezen dezelfde opbouw.
    assert regels[1].samenstelling == tweede["samenstelling"] and regels[1].tools_hash == tweede["tools_hash"]
    # En de logregel komt door de redactie.
    assert json.loads(JsonFormatter().format(regels[1]))["samenstelling"] == tweede["samenstelling"]
    # Buiten de modelstap (een losse aanroep op de adapter) rekent de adapter zelf, zonder rol.
    los = _adapter([_resp(invoer=1)])
    los.create(**_verzoek())
    assert "rol" not in los.meter.aanroepen[0] and los.meter.aanroepen[0]["samenstelling"]


def test_parallelle_aanroepen_zien_elkaars_kader_niet():
    from concurrent.futures import ThreadPoolExecutor

    llm = _adapter([_resp(invoer=1) for _ in range(8)])
    rollen = [Rol.JAS_CLASSIFIER, Rol.JAS_REVIEWER] * 4
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda r: aanroep(llm, r, **_verzoek()), rollen))
    stand = llm.meter.stand()["per_rol"]
    assert stand["jas_classifier"]["aanroepen"] == stand["jas_reviewer"]["aanroepen"] == 4


# ── Stap 2: de verdeling ─────────────────────────────────────────────────────────────────────────────────────────────

def test_grootste_rest_verdeelt_precies_en_deterministisch():
    assert grootste_rest({"a": 1, "b": 1, "c": 1}, 10) == {"a": 4, "b": 3, "c": 3}
    assert grootste_rest({"a": 3, "b": 1}, 0) == {"a": 0, "b": 0}
    for totaal in (1, 7, 999, 31_337):
        uit = grootste_rest({"a": 5, "b": 13, "c": 2, "d": 977}, totaal)
        assert sum(uit.values()) == totaal


def _aanroep(**kw):
    return {"invoer": 100, "cache_lees": 0, "cache_schrijf": 900, "uitvoer": 50,
            "samenstelling": {"systeem": 400, "graaftools": 600, "historie": 300, "beurt": 100, "toolresultaten": 600},
            **kw}


def test_zonder_anker_gaat_alles_naar_tekens_en_de_som_is_het_totaal():
    d = verdeel(_aanroep())
    assert d["totaal"] == 1000 == sum(x["omvang"] for x in d["delen"])
    assert [x["categorie"] for x in d["delen"]] == ["systeem", "graaftools", "historie", "beurt", "toolresultaten"]
    assert d["voorvoegsel"] == {"omvang": 500, "exact": False}
    assert d["cache"] == {"lees": 0, "schrijf": 900, "nieuw": 100}


def test_met_anker_is_het_voorvoegsel_exact_en_de_som_nog_steeds_het_totaal():
    d = verdeel(_aanroep(), anker=700)
    omvang = {x["categorie"]: x["omvang"] for x in d["delen"]}
    assert d["voorvoegsel"] == {"omvang": 700, "exact": True}
    assert omvang["systeem"] + omvang["graaftools"] == 700 and omvang["systeem"] == 280
    assert omvang["historie"] + omvang["beurt"] + omvang["toolresultaten"] == 300
    assert sum(omvang.values()) == d["totaal"] == 1000


def test_een_anker_dat_niet_past_telt_niet_en_een_lege_samenstelling_is_overig():
    assert verdeel(_aanroep(), anker=5000)["voorvoegsel"]["exact"] is False
    assert verdeel(_aanroep(samenstelling={"historie": 10}), anker=700)["voorvoegsel"] == {"omvang": 0, "exact": False}
    leeg = verdeel(_aanroep(samenstelling={}))
    assert leeg["delen"] == [{"categorie": "overig", "omvang": 1000}]
    # Alleen een voorvoegsel in tekens, maar de API telde meer: de rest is `overig`.
    rest = verdeel(_aanroep(samenstelling={"systeem": 10}), anker=700)
    assert rest["delen"] == [{"categorie": "systeem", "omvang": 700}, {"categorie": "overig", "omvang": 300}]


# ── Stap 2: de contextopbouw uit de meter ────────────────────────────────────────────────────────────────────────────

def _lus(meter, *, rol="antwoord", lus=True, ms=100, kader=None, berichten=None, **usage):
    o = opbouw(system=[STABIEL], tools=TOOLS[:3], messages=berichten or (_historie() + _beurt()), beurt_start=4)
    meter.tel_response(SimpleNamespace(usage=_usage(**usage)), ms=ms, opbouw=o, rol=rol, lus=lus,
                       model="claude-sonnet-4-6", kader=kader)


def _beurtmeter() -> Verbruiksmeter:
    """Een beurt zoals op acceptatie: de supervisor, een koud begin dat het voorvoegsel schrijft, en twee rondes die
    het lezen."""
    meter = Verbruiksmeter()
    _lus(meter, rol="supervisor", lus=False, invoer=900, uitvoer=40)
    kader = {"venster_telling": {"beurten_historie": 5, "beurten_venster": 3, "ingekort": 2},
             "historiegrens_tekens": 40_000}
    _lus(meter, invoer=50, schrijf=9000, uur=8000, uitvoer=200, kader=kader, berichten=_historie() + _beurt()[:1])
    _lus(meter, invoer=40, lees=9000, schrijf=600, uur=0, uitvoer=300, kader=kader, berichten=_historie() + _beurt()[:2])
    _lus(meter, invoer=30, lees=9600, schrijf=700, uur=0, uitvoer=500, kader=kader)
    return meter


def test_elke_aanroep_van_een_agent_draagt_zijn_profiel():
    """ADR-016 §A3: het profiel staat per agent én per aanroep. Een losse stap (de supervisor) heeft er geen. De meting
    op acceptatie vond het eerst alleen per agent (12 nov 2026)."""
    meter = Verbruiksmeter()
    _lus(meter, rol="supervisor", lus=False, invoer=900, uitvoer=40)
    profiel = {"profiel_id": "centraal", "profiel_versie": "99fb700096f8"}
    _lus(meter, rol="centraal", invoer=50, schrijf=9000, uur=8000, uitvoer=200, kader=profiel)
    _lus(meter, rol="centraal", invoer=30, lees=9000, uitvoer=300, kader=profiel)
    c = contextopbouw(meter)
    los, eerste, tweede = c["aanroepen"]
    assert "profiel_id" not in los and "profiel_versie" not in los
    for regel in (eerste, tweede):
        assert (regel["rol"], regel["profiel_id"], regel["profiel_versie"]) == ("centraal", "centraal", "99fb700096f8")
    [agent] = c["agenten"]
    assert (agent["profiel_id"], agent["profiel_versie"]) == ("centraal", "99fb700096f8")


def test_een_beurt_zonder_model_heeft_geen_contextopbouw():
    assert contextopbouw(None) is None and contextopbouw(Verbruiksmeter()) is None


def test_de_contextopbouw_heeft_de_vorm_van_het_plan():
    c = contextopbouw(_beurtmeter(), run_id="r1", ouder_run_id="r0")
    assert (c["versie"], c["run_id"], c["ouder_run_id"], c["profiel_id"], c["profiel_versie"]) == (VERSIE, "r1", "r0", "", "")
    [agent] = c["agenten"]   # de supervisor is een rol in het verbruik, geen agent met een context
    assert (agent["rol"], agent["model"], agent["venster"]) == ("antwoord", "claude-sonnet-4-6", 1_000_000)
    laatste, begin = agent["laatste"], agent["begin"]
    assert laatste["totaal"] == 30 + 9600 + 700 == sum(d["omvang"] for d in laatste["delen"])
    assert laatste["cache"] == {"lees": 9600, "schrijf": 700, "nieuw": 30}
    # Het anker uit het koude begin geldt voor het laatste verzoek: hetzelfde voorvoegsel.
    assert laatste["voorvoegsel"] == {"omvang": 8000, "exact": True}
    assert begin["totaal"] == 9050 and begin["cache"] == {"lees": 0, "schrijf": 9000, "nieuw": 50}
    assert len(begin["tools_hash"]) == len(begin["system_hash"]) == 12
    assert agent["venster_beurten"] == {"in_venster": 3, "gekrompen": 2, "weggevallen": 2}
    historie = next(d["omvang"] for d in laatste["delen"] if d["categorie"] == "historie")
    assert agent["historiegrens"] > historie > 0   # de historie is klein tegen de grens van 40k tekens
    assert [v["rol"] for v in c["verbruik"]] == ["supervisor", "antwoord"]
    assert c["verbruik"][1] == {"rol": "antwoord", "model": "claude-sonnet-4-6", "aanroepen": 3, "invoer": 120,
                                "cache_lees": 18600, "cache_schrijf": 10300, "uitvoer": 1000, "duur": 300}
    assert [a["rol"] for a in c["aanroepen"]] == ["supervisor", "antwoord", "antwoord", "antwoord"]
    assert set(c["aanroepen"][0]) == {"rol", "totaal", "cache_lees", "cache_schrijf", "invoer", "uitvoer", "ms",
                                      "tools_hash", "system_hash"}


def test_de_som_is_gelijk_aan_wat_dezelfde_meter_boekt():
    meter = _beurtmeter()
    c = contextopbouw(meter)
    geboekt = {k: v for k, v in meter.als_dict().items() if k != "calls"}   # wat `boek_verbruik` naar de api stuurt
    assert c["som"] == geboekt
    assert {k: sum(v[k] for v in c["verbruik"]) for k in geboekt} == geboekt
    assert sum(v["aanroepen"] for v in c["verbruik"]) == meter.calls


def test_zonder_anker_valt_alles_terug_op_tekens():
    """Een warm begin (niemand schreef het voorvoegsel in deze beurt), of een provider die `cache_creation` niet meldt."""
    for uur in (0, None):
        meter = Verbruiksmeter()
        _lus(meter, invoer=30, lees=9000, schrijf=500, uur=uur)
        [agent] = contextopbouw(meter)["agenten"]
        assert agent["laatste"]["voorvoegsel"]["exact"] is False
        assert sum(d["omvang"] for d in agent["laatste"]["delen"]) == agent["laatste"]["totaal"] == 9530
        assert ("cache_schrijf_1u" in meter.aanroepen[0]) is (uur is not None)


def test_een_anker_geldt_alleen_voor_hetzelfde_voorvoegsel():
    meter = Verbruiksmeter()
    _lus(meter, invoer=50, schrijf=9000, uur=8000)
    andere = opbouw(system=[STABIEL], tools=TOOLS[:2], messages=_beurt())
    meter.tel_response(SimpleNamespace(usage=_usage(invoer=30, lees=100, schrijf=7000, uur=0)), opbouw=andere,
                       rol="antwoord", lus=True, model="m")
    [agent] = contextopbouw(meter)["agenten"]
    assert agent["laatste"]["voorvoegsel"]["exact"] is False and agent["venster"] == STANDAARD


def test_laatste_begin_en_sommen_tellen_ook_voorbij_de_grens_op_de_lijst():
    meter = Verbruiksmeter()
    for i in range(MAX_AANROEPEN + 7):
        _lus(meter, invoer=i + 1, uitvoer=1)
    c = contextopbouw(meter)
    assert len(c["aanroepen"]) == MAX_AANROEPEN
    [agent] = c["agenten"]
    assert agent["begin"]["totaal"] == 1 and agent["laatste"]["totaal"] == MAX_AANROEPEN + 7
    assert c["verbruik"][0]["aanroepen"] == MAX_AANROEPEN + 7 == meter.calls
    assert c["som"]["invoer"] == sum(range(1, MAX_AANROEPEN + 8))


def test_alleen_losse_stappen_geven_verbruik_maar_geen_context():
    meter = Verbruiksmeter()
    for _ in range(3):
        _lus(meter, rol="jas_classifier", lus=False, invoer=100, uitvoer=10)
    c = contextopbouw(meter)
    assert c["agenten"] == [] and c["verbruik"][0]["aanroepen"] == 3 and c["som"]["invoer"] == 300


def _sleutels(waarde) -> set[str]:
    if isinstance(waarde, dict):
        return set(waarde) | {s for v in waarde.values() for s in _sleutels(v)}
    if isinstance(waarde, list):
        return {s for v in waarde for s in _sleutels(v)}
    return set()


def test_geen_veld_heet_token_en_niets_valt_weg_in_de_log():
    c = contextopbouw(_beurtmeter(), run_id="r1")
    sleutels = _sleutels(c)
    assert not any("token" in s.lower() for s in sleutels) and not sleutels & GEHEIME_VELDEN
    regel = logging.LogRecord("t", logging.INFO, "", 0, "meting", None, None)
    regel.contextopbouw = c
    assert json.loads(JsonFormatter().format(regel))["contextopbouw"] == json.loads(json.dumps(c))


def test_de_contextopbouw_draagt_geen_inhoud():
    tekst = json.dumps(contextopbouw(_beurtmeter()))
    for geheim in ("tweede vraag", "tekst van artikel 9", "get_artikel", "SPECIALIST"):
        assert geheim not in tekst


# ── Stap 2: het venster van het model ────────────────────────────────────────────────────────────────────────────────

def test_elk_model_uit_de_config_en_de_uitrol_staat_in_het_register():
    """Een nieuw model zonder venster krijgt de default en maakt deze test rood: geen stille fout."""
    settings = make_settings()
    modellen = {settings.llm_model, *(settings.model_voor(rol) for rol in ("router", "ophaal"))}
    infra = (ROOT / ".github" / "workflows" / "azure-infra.yml").read_text(encoding="utf-8")
    modellen |= set(re.findall(r"vars\.LLM_MODEL \|\| '([^']+)'", infra))
    assert modellen and not modellen - set(VENSTERS), f"zonder venster: {sorted(modellen - set(VENSTERS))}"
    assert modelvenster("onbekend-model") == STANDAARD == min(STANDAARD, *VENSTERS.values())


# ── Stap 2: het contract met de api ──────────────────────────────────────────────────────────────────────────────────

def _api_klasse(naam: str) -> dict[str, ast.AnnAssign]:
    boom = ast.parse(API_CONTRACT.read_text(encoding="utf-8"))
    klasse = next(k for k in ast.walk(boom) if isinstance(k, ast.ClassDef) and k.name == naam)
    return {r.target.id: r for r in klasse.body if isinstance(r, ast.AnnAssign) and r.target.id != "model_config"}


@pytest.mark.skipif(not API_CONTRACT.exists(), reason="api-contract niet beschikbaar (los uitgecheckt)")
def test_de_contextopbouw_is_gelijk_aan_het_contract_van_de_api():
    """De api laat een onbekend veld stil vallen, dus beide kanten dragen precies dezelfde velden; en het bericht en de
    grens op de lijst kennen het veld."""
    assert set(contextopbouw(_beurtmeter())) == set(_api_klasse("Contextopbouw"))
    assert "contextopbouw" in _api_klasse("BerichtInvoer") and "contextopbouw" in _api_klasse("Bericht")
    bron = API_CONTRACT.read_text(encoding="utf-8")
    assert int(re.search(r"^MAX_CONTEXT_AANROEPEN = (\d+)", bron, re.M).group(1)) == MAX_AANROEPEN
    assert len(Rol) <= 64   # `verbruik` heeft een rij per rol; de api begrenst de lijst daarop


# ── Stap 2: van de antwoordlus naar het event en het bericht ─────────────────────────────────────────────────────────

def test_een_beurt_zet_dezelfde_contextopbouw_op_het_event_en_op_het_bericht(monkeypatch):
    from agent.agent import answer_stream
    from agent.beurt import voer_beurt_uit
    from agent.beurtmeting import gemeten
    from agent.runs import Run

    bewaard: list[dict] = []

    class Api:
        async def voeg_bericht_toe(self, _gesprek, bericht):
            bewaard.append(bericht)
            return {}

        async def boek_verbruik(self, verbruik, **_kw):
            bewaard.append({"geboekt": verbruik})

        async def aclose(self):
            pass

    monkeypatch.setattr("agent.beurt.WetsanalyseApi", lambda *_a, **_k: Api())
    settings = make_settings(enable_planning=False, grounding_correct=False, wetsanalyse_api_url="http://api",
                             wetsanalyse_api_token="t", qa_api_token="q")
    graph = FakeGraph(result='?regeling\t?citeertitel\n<urn:bwb:BWBR0004770>\t"Invorderingswet 1990"\n')
    llm = _adapter([
        _resp([tool_block("t1", "list_regelingen", {})], "tool_use", invoer=50, schrijf=9000, uur=8000, uitvoer=20),
        _resp([text_block("Klaar.")], "end_turn", invoer=40, lees=9000, schrijf=300, uur=0, uitvoer=10),
    ])

    async def draai():
        run = Run(run_id="r1", conversation_id="g1", vraag="welke regelingen zijn er?", ouder_run_id="r0")
        beurt = voer_beurt_uit(
            answer_stream(run.vraag, "g1", settings=settings, llm=llm, graph=graph, run_id="r1", user_id="j"),
            settings=settings, run=run, gesprek_id="g1", user_id="j", meter=llm.meter)
        return [e async for e in gemeten(beurt, meter=llm.meter, run=run, gesprek_id="g1", model=settings.llm_model)]

    events = asyncio.run(draai())
    assert [e["type"] for e in events][-2:] == ["meting", "done"]
    [meting] = [e for e in events if e["type"] == "meting"]
    [bericht] = [b for b in bewaard if "rol" in b]
    c = meting["contextopbouw"]
    assert bericht["contextopbouw"] == c
    assert (c["run_id"], c["ouder_run_id"]) == ("r1", "r0")
    [agent] = c["agenten"]
    assert agent["rol"] == "antwoord" and agent["laatste"]["voorvoegsel"] == {"omvang": 8000, "exact": True}
    assert agent["begin"]["cache"] == {"lees": 0, "schrijf": 9000, "nieuw": 50}
    assert agent["laatste"]["totaal"] == 9340 == sum(d["omvang"] for d in agent["laatste"]["delen"])
    soorten = {d["categorie"] for d in agent["laatste"]["delen"]}
    assert {"systeem", "methode", "graaftools", "beurt", "toolresultaten"} <= soorten
    assert agent["venster_beurten"] == {"in_venster": 1, "gekrompen": 0, "weggevallen": 0}
    # Wat het budget zag, is de som.
    [geboekt] = [b["geboekt"] for b in bewaard if "geboekt" in b]
    assert c["som"] == {k: v for k, v in geboekt.items() if k != "calls"}
    # Het bestaande deel van het event blijft: de aanroepen met hun opbouw, nu met de rol erbij.
    assert [a["rol"] for a in meting["aanroepen"]] == ["antwoord", "antwoord"]
