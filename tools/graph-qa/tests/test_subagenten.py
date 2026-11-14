"""Meer subagents en de regisseur als tool (ADR-016 §A5): een plan met een bevestiging, hoogstens `REGIE_PARALLEL`
tegelijk met de wachtstap voor de cache, het plafond per opdracht, de bundel, en `regie_plan`."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agent import overdracht, subagent as sub
from agent.models import SubagentOpdracht
from agent.nodes import delegatie_plan
from agent.nodes import subagent_vervolg as vervolg
from test_regisseur import NepApi
from test_subagent import ARTIKEL, STATE

A = SubagentOpdracht(doel="Vat de uitspraken bij artikel 9 Iw 1990 samen.")
B = SubagentOpdracht(doel="Vat de Kamerstukken bij artikel 9 Iw 1990 samen.")
C = SubagentOpdracht(doel="Lees de toelichting bij artikel 9 Iw 1990.")


def _invoer(*opdrachten: SubagentOpdracht, profiel: str = "algemeen") -> dict:
    return {"opdrachten": [{"profiel": profiel, **o.model_dump()} for o in opdrachten]}


def _bouw(kinderen=True, **settings):
    return SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True, **settings), loop=None,
                           stop_check=None, graph=None)


# -- de overdracht: een plan, geen start --------------------------------------------------------------------

def test_subagenten_zet_het_plan_klaar_en_start_niets():
    upd = overdracht.OVERDRACHT["subagenten"].zet(_bouw(), {**STATE, "subagenten": []}, _invoer(A, B))
    assert [p["profiel"] for p in upd["subagent_plan"]] == ["algemeen", "algemeen"]
    assert upd["subagent_plan"][1]["opdracht"]["doel"] == B.doel
    assert overdracht.OVERDRACHT["subagenten"].naar == "subagent_plan"
    schema = overdracht.OVERDRACHT["subagenten"].schema
    items = schema["input_schema"]["properties"]["opdrachten"]["items"]
    assert schema["strict"] is False and items["additionalProperties"] is False and set(items["required"]) == set(
        items["properties"])


def test_subagenten_weigert_een_plan_dat_niet_past():
    zet = overdracht.OVERDRACHT["subagenten"].zet
    assert "twee tot 3" in zet(_bouw(), STATE, _invoer(A))
    assert "twee tot 3" in zet(_bouw(), STATE, _invoer(A, B, C, A))
    assert "bestaat niet" in zet(_bouw(), STATE, _invoer(A, B, profiel="centraal"))
    assert "niet starten" in zet(_bouw(kinderen=None), STATE, _invoer(A, B))
    assert "al een subagent" in zet(_bouw(), {**STATE, "subagenten": [{"uitkomst": "klaar"}]}, _invoer(A, B))


# -- het plan bij de api en de kaart ------------------------------------------------------------------------

class Api:
    def __init__(self, resterend: int | None = 400_000):
        self.aanroepen: list[tuple[str, object]] = []
        self.resterend = resterend
        self.delegatie: dict = {}

    async def budget_toegestaan(self):
        return True, ({"resterend": self.resterend, "actief": True} if self.resterend is not None else {})

    async def start_delegatie(self, invoer):
        self.aanroepen.append(("start_delegatie", invoer))
        self.delegatie = {"id": "d9", "soort": "subagent", "status": invoer.get("status", "loopt"), "werkgebied_id": "",
                          "plan": invoer["plan"], "uitkomst": {}}
        return self.delegatie

    async def haal_delegatie(self, did):
        self.aanroepen.append(("haal_delegatie", did))
        return self.delegatie

    async def wijzig_delegatie(self, did, wijziging):
        self.aanroepen.append(("wijzig_delegatie", wijziging))
        if wijziging.get("status"):
            self.delegatie = {**self.delegatie, "status": wijziging["status"],
                              **({"uitkomst": wijziging["uitkomst"]} if "uitkomst" in wijziging else {})}
        return self.delegatie

    async def maak_gesprek(self, invoer):
        self.aanroepen.append(("maak_gesprek", invoer))
        return {"id": f"kind-{sum(1 for n, _ in self.aanroepen if n == 'maak_gesprek')}"}

    async def aclose(self):
        pass


def test_het_plan_wacht_bij_de_api_met_een_plafond_en_een_kaart():
    api = Api()
    tekst, kaart = asyncio.run(sub.plan_klaar(STATE, [("algemeen", A), ("duiding", B)], settings=None, api=api))
    [(_, start)] = api.aanroepen
    assert start["status"] == "wacht" and start["budget_aandeel"] == 100_000 and start["plan"]["plafond"] == 100_000
    assert [t["profiel"] for t in start["plan"]["taken"]] == ["algemeen", "duiding"]
    assert (kaart["stap"], kaart["intake_id"], kaart["vrije_tekst"], kaart["overslaanbaar"]) == ("sa_start", "sa-d9",
                                                                                                    False, False)
    assert "100.000 tokens" in kaart["toelichting"] and "schatting" in kaart["toelichting"]
    assert "(duiding)" in kaart["toelichting"] and len(kaart["toelichting"]) <= 1000
    assert "bevestigt" in tekst
    # Zonder budgetstand geen plafond, en de kaart zegt het niet.
    _, kaart = asyncio.run(sub.plan_klaar(STATE, [("algemeen", A), ("algemeen", B)], settings=None, api=Api(None)))
    assert "tokens samen" not in kaart["toelichting"]


# -- uitvoeren: hoogstens twee tegelijk, de cache, het plafond --------------------------------------------

def _kinderen(verbruik: int = 1000):
    """Kinderen die pas klaar zijn als de test ze loslaat; elk kind heeft een `meting` met zijn verbruik."""
    runs: list = []

    async def start(verzoek, wie, ouder):
        run = SimpleNamespace(run_id=f"kind-run-{len(runs)}", uitkomst="klaar", status="klaar", events=[],
                              resultaat={"rapport": {"status": "klaar"}, "answer": f"Rapport {len(runs)}.",
                                         "source_trace": [ARTIKEL]}, verzoek=verzoek, klaar=asyncio.Event())

        async def loop():
            await asyncio.sleep(0)
            run.events.append({"type": "reason", "content": "…"})
            await run.klaar.wait()
            run.events.append({"type": "meting", "invoer": verbruik})
        run.taak = asyncio.create_task(loop())
        runs.append(run)
        return run

    async def stop(run):
        run.uitkomst = run.status = "gestopt"
        run.klaar.set()

    return sub.Kinderen(start=start, stop=stop), runs


def _plan(api: Api, n: int = 3, plafond: int | None = None):
    api.delegatie = {"id": "d9", "soort": "subagent", "status": "wacht", "werkgebied_id": "", "uitkomst": {},
                     "plan": {"taken": [{"titel": o.doel, "profiel": "algemeen", "opdracht": o.model_dump()}
                                        for o in (A, B, C)[:n]], **({"plafond": plafond} if plafond else {})}}


def test_hoogstens_twee_tegelijk_en_de_rest_na_de_eerste_ronde_van_de_eerste():
    api = Api()
    _plan(api)
    kinderen, runs = _kinderen()

    async def scenario():
        taak = asyncio.create_task(sub.voer_plan_uit(STATE, "d9", lambda _e: None, settings=None, kinderen=kinderen,
                                                     gestopt=lambda: False, api=api, cache_wacht_s=2))
        for _ in range(50):
            await asyncio.sleep(0.05)
            if len(runs) >= 2:
                break
        assert len(runs) == 2, "de tweede start zodra de eerste zijn eerste ronde begon; de derde wacht op een plek"
        await asyncio.sleep(0.3)
        assert len(runs) == 2
        runs[0].klaar.set()
        for _ in range(50):
            await asyncio.sleep(0.05)
            if len(runs) == 3:
                break
        for r in runs:
            r.klaar.set()
        return await taak

    paren, weigering = asyncio.run(scenario())
    assert not weigering and [a.uitkomst for a, _ in paren] == ["klaar"] * 3
    assert [r.verzoek.conversation_id for r in runs] == ["kind-1", "kind-2", "kind-3"]
    assert api.delegatie["status"] == "klaar" and len(api.delegatie["uitkomst"]["kinderen"]) == 3
    assert "1. RAPPORT VAN DE SUBAGENT" in sub.bundel_rapporten(paren) and "3. RAPPORT" in sub.bundel_rapporten(paren)


def test_bij_het_plafond_start_er_niets_nieuws():
    api = Api()
    _plan(api, plafond=1500)
    kinderen, runs = _kinderen(verbruik=1000)

    async def scenario():
        taak = asyncio.create_task(sub.voer_plan_uit(STATE, "d9", lambda _e: None, settings=None, kinderen=kinderen,
                                                     gestopt=lambda: False, api=api, parallel=1, cache_wacht_s=1))
        for _ in range(100):
            await asyncio.sleep(0.02)
            for r in runs:
                r.klaar.set()
            if taak.done():
                break
        return await taak

    paren, _ = asyncio.run(scenario())
    assert [a.uitkomst for a, _ in paren] == ["klaar", "klaar", "niet_gestart"]
    assert paren[2][0].reden == "het plafond van de opdracht is bereikt" and len(runs) == 2


def test_een_plan_start_maar_een_keer():
    api = Api()
    _plan(api)
    api.delegatie["status"] = "klaar"
    kinderen, runs = _kinderen()
    paren, weigering = asyncio.run(sub.voer_plan_uit(STATE, "d9", lambda _e: None, settings=None, kinderen=kinderen,
                                                     gestopt=lambda: False, api=api))
    assert weigering == sub.AL_BEANTWOORD and not paren and not runs


# -- de klik op de bevestiging ----------------------------------------------------------------------------

def _klik(actie: str = "antwoord") -> dict:
    return {**STATE, "intake_actie": {"intake_id": "sa-d9", "stap": "sa_start", "actie": actie, "keuzes": ["start"]}}


def test_de_bevestiging_start_de_subagents_en_de_centrale_agent_bundelt(monkeypatch):
    api = Api()
    _plan(api, n=2)
    kinderen, runs = _kinderen()
    monkeypatch.setattr(vervolg, "get_stream_writer", lambda: (lambda _e: None))

    async def laat_los():
        while True:
            await asyncio.sleep(0.01)
            for r in runs:
                r.klaar.set()

    def draai(maak, *, loop, schrijf):
        async def met_loslaten():
            hulp = asyncio.create_task(laat_los())
            try:
                return await maak(schrijf)
            finally:
                hulp.cancel()
        return asyncio.run(met_loslaten())

    monkeypatch.setattr(vervolg, "draai", draai)
    b = SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None, stop_check=None,
                        graph=None, agent_api=lambda *_a: api)
    upd = vervolg.subagent_vervolg_node(b, _klik())
    assert upd["rapporten"].startswith("RAPPORTEN VAN DE SUBAGENTS") and "2. RAPPORT" in upd["rapporten"]
    assert vervolg.route_na_vervolg(None, upd) == "agent" and upd["source_trace"].count(ARTIKEL) == 2


def test_laat_maar_start_geen_enkele_subagent(monkeypatch):
    api = Api()
    _plan(api, n=2)
    kinderen, runs = _kinderen()
    monkeypatch.setattr(vervolg, "get_stream_writer", lambda: (lambda _e: None))
    b = SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None, stop_check=None,
                        graph=None, agent_api=lambda *_a: api)
    upd = vervolg.subagent_vervolg_node(b, _klik("afbreken"))
    assert upd["answer"] == vervolg.NIET_GESTART and api.delegatie["status"] == "gestopt" and not runs


# -- de regisseur als tool ----------------------------------------------------------------------------------

def test_regie_plan_hoort_bij_een_werkgebied():
    zet = overdracht.OVERDRACHT["regie_plan"].zet
    assert "werkgebied" in zet(_bouw(), {**STATE, "werkgebied_id": ""}, {"opdracht": "bronnen"})
    assert zet(_bouw(), {**STATE, "werkgebied_id": "w1"}, {"opdracht": "annoteren"}) == {"regie_plan": "annoteren"}
    assert overdracht.OVERDRACHT["regie_plan"].naar == "regie_voorstel"


def test_regie_plan_legt_het_plan_van_de_regisseur_voor_met_zijn_knop(monkeypatch):
    events = []
    monkeypatch.setattr(delegatie_plan, "get_stream_writer", lambda: events.append)
    api = NepApi(deelvragen=2)
    b = SimpleNamespace(settings=SimpleNamespace(legt_zelf_vast=True, regie_parallel=2), loop=None,
                        agent_api=lambda *_a: api)
    upd = delegatie_plan.regie_voorstel_node(b, {**STATE, "werkgebied_id": "w1", "regie_plan": "bronnen"})
    [bevestiging] = [e["bevestiging"] for e in events if e["type"] == "bevestiging"]
    assert (bevestiging["soort"], bevestiging["opdracht"], bevestiging["aantal"]) == ("regie", "bronnen", 2)
    assert "deelgesprek" in upd["answer"] and "start_delegatie" not in api.aanroepen, "eerst de bevestiging"
