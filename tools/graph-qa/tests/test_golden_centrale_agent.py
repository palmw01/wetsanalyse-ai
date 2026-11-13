"""De agentset (ADR-016 §A6, stap M0): de vorm van `eval/golden_centrale_agent.jsonl`.

De set beschrijft het doel van de centrale agent en is de maat voor elke ronde van de meetlus. Een rij die van vorm
verandert, maakt rondes onvergelijkbaar; deze test houdt de groepen, de velden en de namen vast. Hij draait de
opdrachten niet: dat doet de meting op acceptatie.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest
from bronmodel.connectors import CONNECTORS

from agent.sjablonen import SJABLONEN
from agent.specialists import SPECIALISTS
from agent.tools import JAS_TOOLS, TOOLS

EVAL = Path(__file__).resolve().parents[1] / "eval"
SET = EVAL / "golden_centrale_agent.jsonl"


def _lees(pad: Path) -> list[dict]:
    return [json.loads(r) for r in pad.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]


ALLES = _lees(SET)
WERKGEBIED = next(r for r in ALLES if r["id"] == "_werkgebied")
RIJEN = [r for r in ALLES if r["id"] != "_werkgebied"]
PER_ID = {r["id"]: r for r in RIJEN}

#: §A6, de tabel met groepen.
GROEPEN = {"enkelvoudig": 10, "een_subagent": 5, "meer_subagents": 6, "vraag_omhoog": 4, "vervolg": 5}
VELDEN = {"route", "route_code", "subagents", "profielen", "tools_verplicht", "tools_verboden", "vraag_omhoog",
          "sjabloon", "bevestiging", "regisseur"}
#: Tools die ADR-016 toevoegt en die er nu nog niet zijn (A1, A4, A5). Komt er een bij in het ADR, dan hier ook.
NIEUW = {"subagent", "rapport", "regie_plan", "delegatie_stand", "beantwoord_kaart", "laad_skill", "lees_skill", "meer_tools"}
#: Geen tool maar een keten: verboden waar Lex vóór de poort van de jurist niet mag annoteren.
KETENS = {"annoteer"}
#: Routes in code die niet in de routeringsset staan: de getypte opdracht aan de regisseur (de ingang van de run, vóór
#: de supervisor) en het antwoord op een keuzekaart (een klik met een vaste actie).
ROUTES_BUITEN_DE_SET = {"regie", "keuze"}
#: `centraal` is het profiel van de centrale agent zelf (A2) en bestaat pas na A1.
PROFIELEN = set(SPECIALISTS) | {"centraal"}
#: De bepalingen van de voorbeelden en de evals in de skill: de set gebruikt andere (§A6).
SKILLVOORBEELD = re.compile(r"\bartikel (?:9|25)\b[^.]*Invorderingswet 1990|Successiewet", re.I)


def _namen(ingangen: list[str]) -> set[str]:
    return {naam for ingang in ingangen for naam in ingang.split("|")}


def test_dertig_opdrachten_in_de_groepen_van_het_adr():
    assert len(RIJEN) == 30
    assert Counter(r["groep"] for r in RIJEN) == GROEPEN
    assert len(PER_ID) == 30, "een id komt twee keer voor"


@pytest.mark.parametrize("rij", RIJEN, ids=lambda r: r["id"])
def test_elke_opdracht_legt_vast_wat_het_adr_vraagt(rij):
    assert rij["opdracht"].strip() and rij["goed"].strip()
    v = rij["verwacht"]
    assert set(v) == VELDEN
    assert v["route"] in {"code", "centraal"}
    laag, hoog = v["subagents"]
    assert 0 <= laag <= hoog
    assert set(v["profielen"]) <= PROFIELEN
    assert bool(v["profielen"]) == (hoog > 0), "profielen horen bij een opdracht die een subagent kan hebben"
    assert isinstance(v["bevestiging"], bool) and isinstance(v["regisseur"], bool)
    if v["vraag_omhoog"] is not None:
        assert set(v["vraag_omhoog"]) == {"van", "landt_bij"}
        assert set(v["vraag_omhoog"]["van"]) <= {"centraal", "subagent"} and v["vraag_omhoog"]["van"]
        assert v["vraag_omhoog"]["landt_bij"] in {"jurist", "centraal"}


@pytest.mark.parametrize("rij", RIJEN, ids=lambda r: r["id"])
def test_namen_bestaan(rij):
    v = rij["verwacht"]
    tools = {t["name"] for t in TOOLS + JAS_TOOLS} | set(SJABLONEN) | NIEUW | KETENS
    verplicht, verboden = _namen(v["tools_verplicht"]), _namen(v["tools_verboden"])
    assert verplicht | verboden <= tools, sorted((verplicht | verboden) - tools)
    assert not verplicht & verboden
    if v["sjabloon"] is not None:
        assert _namen([v["sjabloon"]]) <= set(SJABLONEN)
    assert set((rij.get("context") or {}).get("bronnen", [])) <= set(CONNECTORS)
    if v["route_code"] is not None:
        routes = {r["verwacht"].get("route") for r in _lees(EVAL / "golden_routering.jsonl")} | ROUTES_BUITEN_DE_SET
        assert v["route_code"] in routes
    if v["route"] == "code":
        assert v["route_code"], "een route in code heeft een naam"


@pytest.mark.parametrize("rij", RIJEN, ids=lambda r: r["id"])
def test_de_groep_past_bij_de_verwachting(rij):
    v, groep = rij["verwacht"], rij["groep"]
    laag, hoog = v["subagents"]
    if groep == "enkelvoudig":
        assert hoog == 0 and "subagent" in v["tools_verboden"] and v["vraag_omhoog"] is None
    if groep == "een_subagent":
        assert (laag, hoog) == (1, 1) and "subagent" in v["tools_verplicht"]
    if groep == "meer_subagents":
        assert laag >= 2 and v["bevestiging"], "meer dan één subagent vraagt een bevestigingskaart (A5)"
        assert v["regisseur"] == ("regie_plan" in v["tools_verplicht"] or v["route_code"] == "regie")
    if groep == "vraag_omhoog":
        assert v["vraag_omhoog"] is not None
    if groep == "vervolg":
        assert rij.get("opzet"), "een vervolg heeft beurten ervoor"
    if v["regisseur"]:
        assert (rij.get("context") or {}).get("werkgebied"), "de regisseur verdeelt per deelvraag van een werkgebied"


def test_opzet_verwijst_naar_bestaande_opdrachten():
    for rij in RIJEN:
        for stap in rij.get("opzet", []):
            assert ("opdracht" in stap) != ("vraag" in stap), rij["id"]
            if "opdracht" in stap:
                assert stap["opdracht"] in PER_ID and stap["opdracht"] != rij["id"]
                assert not PER_ID[stap["opdracht"]].get("opzet"), "een opzet is één laag diep"


def test_andere_bepalingen_dan_de_voorbeelden_in_de_skill():
    for rij in RIJEN:
        assert not SKILLVOORBEELD.search(rij["opdracht"]), rij["id"]
        for b in rij.get("bron", []):
            assert re.fullmatch(r"BWB[RV]\d+", b["bwb_id"])
            assert not (b["bwb_id"] == "BWBR0004770" and b["artikel"] in {"9", "25"}), rij["id"]


def test_het_meetwerkgebied_draagt_de_opdrachten_met_een_werkgebied():
    assert WERKGEBIED["naam"] and WERKGEBIED["analysevraag"]
    assert WERKGEBIED["gebeurtenis"], "zonder gebeurtenis vraagt de bronselectie daar eerst naar"
    assert len(WERKGEBIED["deelvragen"]) == 3
    assert all(re.fullmatch(r"BWB[RV]\d+", b) for b in WERKGEBIED["zoekbereik"])
    for rij in RIJEN:
        v = rij["verwacht"]
        if v["regisseur"]:
            assert v["subagents"] == [3, 3], "de regisseur start één kind per deelvraag"
    assert not any("verjaring" in d.lower() for d in WERKGEBIED["deelvragen"]), "V02 vraagt naar een deelvraag die ontbreekt"


@pytest.mark.parametrize("rij", RIJEN, ids=lambda r: r["id"])
def test_het_stoppunt_ligt_vast(rij):
    """Elke ronde stopt op hetzelfde punt (nulmeting, afwijking van §A6: de meting annoteert niet)."""
    v = rij["verwacht"]
    assert rij["stoppunt"] in {"einde", "bundel_bronnen", "vraag"}
    opzet_met_regie = any(PER_ID[s["opdracht"]]["verwacht"]["regisseur"] for s in rij.get("opzet", []) if "opdracht" in s)
    assert (rij["stoppunt"] == "bundel_bronnen") == (v["regisseur"] or opzet_met_regie)
    if rij["stoppunt"] == "vraag":
        assert v["vraag_omhoog"]["landt_bij"] == "jurist"


def test_de_samenvatting_toetst_een_run_tegen_de_set():
    """`eval/centrale_agent_vat.py`: uit de events van een beurt de meetpunten, en wat daarvan tegen de set past."""
    from eval.centrale_agent_vat import vat

    meting = {"type": "meting", "route": "duiding", "modelrondes": 3, "invoer": 10, "uitvoer": 5, "cache_lees": 100,
              "cache_schrijf": 20, "duur_ms": 900, "sjabloon": {"gevuld": {"antwoord_duiding": 1}}}
    events = [{"type": "tool_execution", "phase": "start", "tool": "get_lid"},
              {"type": "grounding", "niveau": "gegrond", "niet_letterlijk": [], "unsupported": []}, meting]
    s = vat({"id": "E08", "run": 1, "beurten": [{"label": "gemeten", "events": events}]}, PER_ID["E08"])
    assert (s["tokens"], s["modelrondes"], s["duur_ms"]) == (135, 3, 900)
    # Naar prijs gewogen: zonder aanroepen telt het schrijven als vijf minuten (10 + 5×5 + 0,1×100 + 1,25×20).
    assert (s["gewogen"], s["cache_schrijf_1u"]) == (70, 0)
    uur = {**meting, "aanroepen": [{"invoer": 10, "uitvoer": 5, "cache_lees": 100, "cache_schrijf": 20, "cache_schrijf_1u": 12}]}
    s_uur = vat({"id": "E08", "run": 1, "vorm": "meten", "beurten": [{"label": "gemeten", "events": [uur]}]}, PER_ID["E08"])
    assert (s_uur["gewogen"], s_uur["cache_schrijf_1u"], s_uur["vorm"]) == (79, 12, "meten")   # 8×1,25 + 12×2 = 34
    # Warm: het uurvoorvoegsel staat al in de cache, dus die 12 tokens tellen als gelezen (12×0,1 in plaats van 12×2).
    assert (s_uur["gewogen_warm"], s["gewogen_warm"]) == (56, s["gewogen"])
    # Per rol, met het model: de supervisorstap naast de antwoordlus (§A6).
    twee = {**meting, "aanroepen": [{"rol": "supervisor", "model": "licht", "invoer": 4, "uitvoer": 1, "cache_lees": 0, "cache_schrijf": 0},
                                    {"rol": "antwoord", "model": "zwaar", "invoer": 6, "uitvoer": 4, "cache_lees": 100, "cache_schrijf": 20}]}
    rollen = vat({"id": "E08", "run": 1, "beurten": [{"label": "gemeten", "events": [twee]}]}, PER_ID["E08"])["per_rol"]
    assert rollen["supervisor"] == {"aanroepen": 1, "modellen": ["licht"], "ruw": 5, "gewogen": 9, "gewogen_warm": 9}
    assert (rollen["antwoord"]["modellen"], rollen["antwoord"]["gewogen"]) == (["zwaar"], 61)
    # Welke vorm draaide, uit de run zelf.
    centraal = {**meting, "contextopbouw": {"agenten": [{"rol": "centraal", "profiel_id": "centraal"}]}}
    gezien = [vat({"id": "E08", "run": 1, "beurten": [{"label": "gemeten", "events": [m]}]}, PER_ID["E08"])["vorm_gezien"]
              for m in (twee, centraal, meting)]
    assert gezien == [["supervisor"], ["centraal"], []]
    assert s["route_past"] and s["delegatie_past"] and s["sjabloon_past"] and not s["tools_ontbreken"]

    # De overdracht naar de brede toolset en de tools per modelronde (A2-2b).
    breed = {**meting, "route": "centraal_breed", "sjabloon": {"geweigerd": {"antwoord_duiding:duiding.vul": 1},
                                                              "geweigerd_reden": {"antwoord_duiding:duiding.vul:geen_passage": 1}},
             "contextopbouw": {"agenten": [{"rol": "centraal", "profiel_id": "centraal_breed"}]},
             "aanroepen": [{"rol": "centraal", "tools_hash": "a"}, {"rol": "centraal", "tools_hash": "b"}]}
    tools = [{"type": "tool_execution", "phase": "start", "tool": t, "ronde": r}
             for t, r in (("get_lid", 0), ("meer_tools", 1), ("geldigheid", 2), ("get_artikel", 2))]
    s_breed = vat({"id": "B01", "run": 1, "beurten": [{"label": "gemeten", "events": [*tools, breed]}]}, _lees(EVAL / "golden_centrale_agent_breed.jsonl")[0])
    assert s_breed["meer_tools"] and s_breed["tools_hashes"] == 2 and not s_breed["tools_ontbreken"]
    assert s_breed["tools_per_ronde"] == [["meer_tools"], ["geldigheid", "get_artikel"]] and s_breed["rondes_met_meer_tools"] == 1
    assert s_breed["geweigerd_reden"] == {"antwoord_duiding:duiding.vul:geen_passage": 1}
    assert not s["meer_tools"] and s["tools_per_ronde"] == []

    regie = [{"type": "regie", "fase": "start"}, {"type": "regie_taak", "fase": "start", "gesprek_id": "k1"}]
    s = vat({"id": "M02", "run": 1, "beurten": [{"label": "gemeten", "events": regie}]}, PER_ID["M02"])
    assert s["route"] == "regie" and s["kindgesprekken"] == 1 and not s["delegatie_past"]

    s = vat({"id": "S01", "run": 1, "beurten": [{"label": "gemeten", "events": events}]}, PER_ID["S01"])
    assert not s["delegatie_past"] and "subagent" in s["tools_ontbreken"]


def test_de_andere_sets_worden_met_hun_eigen_scorers_gescoord():
    """`eval/centrale_agent_sets.py`: een beurt van de straat wordt een opname voor de scorers van de set zelf."""
    from eval.centrale_agent_sets import gesprekken, kwaliteitsset, scoor_gesprek, scoor_kwaliteit

    def beurt(tekst: str, route: str, *, tools=(), niveau="gegrond", bwb="BWBR0004770"):
        return {"vraag": "v", "tekst": tekst, "gesprek": "g1", "events": [
            *({"type": "tool_execution", "phase": "start", "tool": t} for t in tools),
            {"type": "sources", "sources": [{"uri": f"urn:bwb:{bwb}:artikel:1", "bwb_id": bwb}]},
            {"type": "grounding", "niveau": niveau, "grounded": niveau != "ongegrond", "cited": 1, "unsupported": []},
            {"type": "meting", "route": route, "modelrondes": 2, "duur_ms": 10, "invoer": 10, "uitvoer": 2,
             "cache_lees": 0, "cache_schrijf": 0}]}

    # De kwaliteitsset: de weigervraag slaagt alleen zonder bronnen.
    k_id, case = next((i, c) for i, c in kwaliteitsset().items() if c.get("should_refuse"))
    geweigerd = {"id": k_id, "set": "kwaliteit", "vorm": "supervisor", "run": 1,
                 "beurten": [{**beurt("Daar kan ik je niet mee helpen.", "afgewezen"), "events": [
                     {"type": "meting", "route": "afgewezen", "modelrondes": 1, "invoer": 5, "uitvoer": 1}]}]}
    assert scoor_kwaliteit(geweigerd, case)["geslaagd"]
    met_bron = {**geweigerd, "beurten": [beurt("Het regent.", "algemeen")]}
    assert not scoor_kwaliteit(met_bron, case)["refusal_ok"]

    # Een gesprek: de route komt uit het meting-event; een agent met een taak telt ook als zijn agent.
    case = gesprekken()["f-bronnen-dan-wetsvraag"]
    rec = {"id": case["id"], "set": "gesprek", "vorm": "supervisor", "run": 1,
           "beurten": [beurt("Bij deelvraag 2 ontbreekt nog een bron.", "deelvragen:dekking"),
                       beurt("Artikel 9 regelt de betalingstermijn.", "algemeen", tools=["get_artikel"])]}
    uit = scoor_gesprek(rec, case)
    assert uit["geslaagd"] and uit["beurten"][0]["routes"] == ["deelvragen:dekking", "deelvragen"]
    assert (uit["tokens"], uit["gewogen"]) == (24, 40)
    assert uit["tools"] == ["get_artikel"] and not uit["meer_tools"] and uit["tool_buiten_profiel"] == 0
    fout = scoor_gesprek({**rec, "beurten": [beurt("Geen idee.", "afgewezen"), rec["beurten"][1]]}, case)
    assert not fout["geslaagd"] and any("afgewezen" in f for f in fout["beurten"][0]["fouten"])

    # Bij de centrale agent is een specialist bij naam niet te toetsen: dat is geen fout, en het staat erbij.
    case = {"id": "x", "beurten": [{"vraag": "v", "verwacht": {"route": "definitie", "bevat": ["aanslag"]}}]}
    centraal = scoor_gesprek({"id": "x", "set": "gesprek", "vorm": "centraal", "run": 1,
                              "beurten": [beurt("Een belastingaanslag is …", "centraal")]}, case)
    assert centraal["geslaagd"] and centraal["beurten"][0]["niet_getoetst"] == ["route definitie"]
    supervisor = scoor_gesprek({"id": "x", "set": "gesprek", "vorm": "supervisor", "run": 1,
                                "beurten": [beurt("Een belastingaanslag is …", "duiding")]}, case)
    assert not supervisor["geslaagd"]


BREED = _lees(EVAL / "golden_centrale_agent_breed.jsonl")


@pytest.mark.parametrize("rij", BREED, ids=lambda r: r["id"])
def test_de_aanvulling_meet_de_overdracht_naar_de_brede_toolset(rij):
    """`golden_centrale_agent_breed.jsonl`: dezelfde vorm als de set, in een eigen groep naast de 30."""
    assert rij["groep"] == "breed" and rij["id"] not in PER_ID
    v = rij["verwacht"]
    assert set(v) == VELDEN and v["route"] == "centraal" and v["subagents"] == [0, 0]
    tools = {t["name"] for t in TOOLS + JAS_TOOLS} | set(SJABLONEN) | NIEUW
    assert _namen(v["tools_verplicht"]) | _namen(v["tools_verboden"]) <= tools
    assert ("meer_tools" in v["tools_verplicht"]) != ("meer_tools" in v["tools_verboden"]), "de overdracht hoort wel of juist niet"
    assert rij["stoppunt"] == "einde" and rij["goed"].strip()
    assert not SKILLVOORBEELD.search(rij["opdracht"])


def test_de_aanvulling_heeft_een_controle_zonder_overdracht():
    assert sum("meer_tools" in r["verwacht"]["tools_verboden"] for r in BREED) >= 1
    assert sum("meer_tools" in r["verwacht"]["tools_verplicht"] for r in BREED) >= 2
