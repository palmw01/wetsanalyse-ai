"""De regisseur (ADR-012): eerst een bevestiging, dan kindgesprekken met gewone runs, hoogstens n tegelijk, en een bundel
uit de stand bij de api. Hij neemt geen besluit van de jurist."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import pytest

from agent.models import ChatRequest
from agent.regie import regisseur as rg
from agent.regie.plan import plan_bronnen
from agent.runstore import Run
from agent.wetsanalyse_api import WetsanalyseApiFout

WG = "wg-1"


class Instellingen:
    legt_zelf_vast = True
    regie_parallel = 2


class NepApi:
    """De api zoals de regisseur hem ziet; elke aanroep wordt geteld."""

    def __init__(self, *, deelvragen=3, klaar=(), regie_409=False):
        self.aanroepen: list[str] = []
        self.berichten: list[dict[str, Any]] = []
        self.gesprekken: list[dict[str, Any]] = []
        self.regie_wijzigingen: list[dict[str, Any]] = []
        self.deelvragen = [{"id": f"d{i}", "nr": i, "vraag": f"Vraag {i}?", "klaar": f"d{i}" in klaar,
                            "telling": {"voorgesteld": i, "opgenomen": 0}} for i in range(1, deelvragen + 1)]
        self.regie_409 = regie_409

    def __getattribute__(self, naam):
        if not naam.startswith("_") and naam not in ("aanroepen", "berichten", "gesprekken", "regie_wijzigingen",
                                                     "deelvragen", "regie_409"):
            object.__getattribute__(self, "aanroepen").append(naam)
        return object.__getattribute__(self, naam)

    async def haal_werkgebied(self, wid):
        return {"id": wid, "deelvragen": []}

    async def haal_bronselectie(self, wid, na=""):
        return {"deelvragen": self.deelvragen}

    async def start_bronnen_run(self, wid, zoekversie=""):
        return {"id": "b1", "status": "klaar"}

    async def start_delegatie(self, invoer):
        if self.regie_409:
            raise WetsanalyseApiFout("nee", 409, "delegatie_loopt_al")
        self.regie = invoer
        return {"id": "regie-1"}

    async def wijzig_delegatie(self, rid, wijziging):
        self.regie_wijzigingen.append(wijziging)
        return {}

    async def maak_gesprek(self, invoer):
        self.gesprekken.append(invoer)
        return {"id": f"kind-{len(self.gesprekken)}"}

    async def voeg_bericht_toe(self, gid, bericht):
        self.berichten.append(bericht)
        return {}

    async def aclose(self):
        pass


class Kinderen:
    """Start kind-runs als echte taken en houdt bij hoeveel er tegelijk lopen."""

    def __init__(self, *, duur=0.05, faalt=(), blijft=False):
        self.verzoeken: list[ChatRequest] = []
        self.tegelijk = self.max_tegelijk = 0
        self.duur, self.faalt, self.blijft = duur, set(faalt), blijft
        self.gestopt: list[str] = []

    async def start(self, verzoek, wie, ouder):
        self.verzoeken.append(verzoek)
        if verzoek.conversation_id in self.faalt:
            raise RuntimeError("kapot")
        run = Run(run_id=f"r-{verzoek.conversation_id}", conversation_id=verzoek.conversation_id, user_id=wie,
                  ouder_run_id=ouder)

        async def werk():
            self.tegelijk += 1
            self.max_tegelijk = max(self.max_tegelijk, self.tegelijk)
            try:
                for _ in range(400 if self.blijft else 1):
                    if run.stop_gevraagd:
                        run.uitkomst = "gestopt"
                        return
                    await asyncio.sleep(self.duur)
                run.uitkomst = "klaar"
            finally:
                self.tegelijk -= 1
        run.taak = asyncio.create_task(werk())
        return run

    async def stop(self, run):
        self.gestopt.append(run.run_id)
        run.stop_gevraagd = True


def _verzoek(**kw) -> ChatRequest:
    return ChatRequest(question="Zoek per deelvraag de bronnen", conversation_id="regie", werkgebied_id=WG,
                       actie="regie_bronnen", **kw)


def _draai(verzoek, api, kinderen, *, run=None, parallel=None, tijdens=None) -> list[dict[str, Any]]:
    run = run or Run(run_id="regie-run", conversation_id="regie", user_id="jurist")

    async def verzamel():
        uit = []
        async for ev in rg.regie_stroom(verzoek, run, settings=Instellingen(), user_id="jurist",
                                        start_kind=kinderen.start, stop_kind=kinderen.stop, api=api,
                                        graph=object(), parallel=parallel, hartslag_s=0.01):
            uit.append(ev)
            if tijdens:
                tijdens(ev, run)
        return uit
    return asyncio.run(verzamel())


def _plan_id(api) -> str:
    return plan_bronnen(WG, {"deelvragen": api.deelvragen}).plan_id


def test_zonder_bevestiging_alleen_het_plan_met_een_knop():
    api, kinderen = NepApi(klaar=("d1",)), Kinderen()
    events = _draai(_verzoek(), api, kinderen)
    assert not kinderen.verzoeken and "start_delegatie" not in api.aanroepen
    bericht = api.berichten[-1]
    assert bericht["bevestiging"] == {"soort": "regie", "werkgebied_id": WG, "aantal": 2, "schatting": 0,
                                      "plan_id": _plan_id(api), "opdracht": "bronnen"}
    assert "Bronnen · deelvraag 2" in bericht["tekst"] and "Deelvraag 1 is al klaar." in bericht["tekst"]
    assert "geen tokens" in bericht["tekst"]
    assert [e["type"] for e in events][-2:] == ["token", "opgeslagen"]


def test_een_veranderd_plan_start_niet():
    api, kinderen = NepApi(), Kinderen()
    _draai(_verzoek(plan_id="f" * 16), api, kinderen)
    assert not kinderen.verzoeken and api.berichten[-1]["tekst"].startswith("Het plan veranderde")


def test_de_knop_voor_de_volgende_fase_geeft_het_plan_van_nu():
    """ADR-016 §A5, *Fasen*: de knop onder de bundel vraagt het plan op de stand van het moment van de klik, zonder te
    zeggen dat het plan veranderde."""
    api, kinderen = NepApi(), Kinderen()
    _draai(_verzoek(plan_id=rg.VOLGENDE_FASE), api, kinderen)
    bericht = api.berichten[-1]
    assert not kinderen.verzoeken and not bericht["tekst"].startswith("Het plan veranderde")
    assert bericht["bevestiging"]["plan_id"] == _plan_id(api)


def test_bevestigd_start_per_deelvraag_een_kindgesprek_en_bundelt():
    api, kinderen = NepApi(), Kinderen()
    events = _draai(_verzoek(plan_id=_plan_id(api)), api, kinderen)
    assert not [e for e in events if e["type"] == "error"], events
    # Per deelvraag een deelgesprek onder het regiegesprek, met de regie erbij.
    assert [(g["titel"], g["ouder_id"], g["delegatie_id"]) for g in api.gesprekken] == [
        (f"Bronnen · deelvraag {i}", "regie", "regie-1") for i in (1, 2, 3)]
    # Elk kind is een gewone run met de actie van een klik, in zijn eigen gesprek.
    assert sorted((v.actie, v.onderwerp.id, v.conversation_id) for v in kinderen.verzoeken) == [
        ("bronselectie", f"d{i}", f"kind-{i}") for i in (1, 2, 3)]
    assert kinderen.max_tegelijk <= 2
    assert [e["fase"] for e in events if e["type"] == "regie"] == ["start", "eind"]
    assert sum(1 for e in events if e["type"] == "regie_taak" and e["fase"] == "eind") == 3
    slot = api.berichten[-1]
    assert slot["artefact"] == {"soort": "regie", "ref": {"werkgebied_id": WG, "regie_id": "regie-1"},
                                "titel": "Regie · bronnen"}
    assert "**Opgeleverd**" in slot["tekst"] and "**Wacht op jou**" in slot["tekst"]
    assert "2 voorgestelde bronnen in het paneel" in slot["tekst"] and "volgende fase annoteren" in slot["tekst"]
    # De knop voor de volgende fase (ADR-016 §A5): annoteren, met het plan op de stand van de klik.
    assert slot["bevestiging"] == {"soort": "regie", "werkgebied_id": WG, "aantal": 3, "schatting": None,
                                   "plan_id": rg.VOLGENDE_FASE, "opdracht": "annoteren"}
    # Elk regiekind draagt het profiel van de ophaalstap op zijn event; het deelgesprek niet.
    assert {e.get("profiel") for e in events if e["type"] == "regie_taak" and e["fase"] == "start"} == {"retrieval"}
    assert not any("profiel" in g for g in api.gesprekken)
    assert api.regie_wijzigingen[-1]["status"] == "klaar"
    assert api.regie["plan_id"] == _plan_id(api) and api.regie["gesprek_id"] == "regie"


def test_nooit_meer_dan_de_grens_tegelijk():
    api, kinderen = NepApi(deelvragen=6), Kinderen(duur=0.03)
    _draai(_verzoek(plan_id=_plan_id(api)), api, kinderen, parallel=1)
    assert kinderen.max_tegelijk == 1 and len(kinderen.verzoeken) == 6
    api, kinderen = NepApi(deelvragen=6), Kinderen(duur=0.03)
    _draai(_verzoek(plan_id=_plan_id(api)), api, kinderen, parallel=9)
    assert kinderen.max_tegelijk == rg.MAX_PARALLEL


def test_een_kind_dat_faalt_stopt_de_rest_niet():
    api, kinderen = NepApi(), Kinderen(faalt=("kind-2",))
    _draai(_verzoek(plan_id=_plan_id(api)), api, kinderen)
    tekst = api.berichten[-1]["tekst"]
    assert "Bronnen · deelvraag 2: mislukt" in tekst and "Bronnen · deelvraag 3" in tekst.split("**Mislukt")[0]
    assert api.regie_wijzigingen[-1]["status"] == "klaar"


def test_stoppen_stopt_de_kinderen_en_start_geen_nieuwe(monkeypatch):
    monkeypatch.setattr(rg, "STOP_PEIL_S", 0.01)
    api, kinderen = NepApi(deelvragen=4), Kinderen(duur=0.01, blijft=True)

    def tijdens(ev, run):
        if ev["type"] == "regie_taak" and ev["fase"] == "start":
            run.stop_gevraagd = True
    _draai(_verzoek(plan_id=_plan_id(api)), api, kinderen, parallel=2, tijdens=tijdens)
    assert len(kinderen.verzoeken) <= 2 and set(kinderen.gestopt) == {f"r-{v.conversation_id}" for v in kinderen.verzoeken}
    assert "niet aan bod gekomen (de regie is gestopt)" in api.berichten[-1]["tekst"]
    assert api.regie_wijzigingen[-1]["status"] == "gestopt"


def test_er_loopt_al_een_regie():
    api, kinderen = NepApi(regie_409=True), Kinderen()
    _draai(_verzoek(plan_id=_plan_id(api)), api, kinderen)
    assert not kinderen.verzoeken and "Er loopt al een regie" in api.berichten[-1]["tekst"]


def test_niets_te_doen():
    api, kinderen = NepApi(klaar=("d1", "d2", "d3")), Kinderen()
    _draai(_verzoek(), api, kinderen)
    assert "niets te verdelen" in api.berichten[-1]["tekst"] and "bevestiging" not in api.berichten[-1]


def test_de_regisseur_neemt_geen_besluit():
    """Alleen de toegestane api-aanroepen, in de code én in een hele ronde; geen besluitendpoint."""
    api, kinderen = NepApi(), Kinderen()
    _draai(_verzoek(plan_id=_plan_id(api)), api, kinderen)
    assert set(api.aanroepen) <= rg.API_AANROEPEN
    bron = Path(rg.__file__).read_text()
    gebruikt = set(re.findall(r"\bapi\.([a-z_]+)\(", bron))
    assert gebruikt <= rg.API_AANROEPEN, gebruikt - rg.API_AANROEPEN
    verboden = {"zet_bronselectie_status", "noem_voorstel", "zet_bronnode_batch", "wijzig_werkgebied"}
    assert not (rg.API_AANROEPEN & verboden)


@pytest.mark.parametrize("tekst, opdracht", [
    ("Zoek per deelvraag de bronnen en annoteer de kern", "bronnen"),
    ("zoek per deelvraag de bronnen", "bronnen"),
    ("Bepaal voor elke deelvraag de bronnen", "bronnen"),
    ("Annoteer per deelvraag de kern", "annoteren"),
    ("Kun je per deelvraag annoteren wat ik opnam?", "annoteren"),   # een verzoek in vraagvorm
    ("Hoe annoteer ik per deelvraag?", None),
    ("Welke bronnen horen bij deelvraag 2?", None),
    ("Help mij de bronnen bij dit werkgebied te bepalen", None),
    ("Wat staat er per deelvraag aan bronnen?", None),
    # Meting ADR-016 A5 (M03): het werk over alle deelvragen is een regie, in code, zonder model.
    ("Kun je voor al mijn deelvragen tegelijk uitzoeken welke bepalingen erbij horen?", "bronnen"),
    ("Zoek voor alle deelvragen de bepalingen", "bronnen"),
    ("Annoteer alle deelvragen", "annoteren"),
    ("Hoeveel bronnen hebben al mijn deelvragen?", None),
    ("Welke bepalingen horen bij al mijn deelvragen?", None),
    ("Zoek uit wat de memorie van toelichting zegt over de bepalingen en vat dat per deelvraag samen.", None),
])
def test_een_getypte_opdracht(tekst, opdracht):
    assert rg.opdracht_in(tekst) == opdracht


def test_het_verzoek_van_een_regie():
    assert _verzoek().is_regie
    assert ChatRequest(question="q", werkgebied_id=WG, actie="regie_annoteren", plan_id="a" * 16).is_regie
    with pytest.raises(ValueError):
        ChatRequest(question="q", werkgebied_id=WG, plan_id="a" * 16)
    with pytest.raises(ValueError):
        ChatRequest(question="q", actie="regie_bronnen")


def test_geen_vraag_uit_de_routeringssets_valt_onder_de_regie():
    """De tekstroute staat vóór de graaf. Geen vraag uit de routerings- en gespreksset mag erin vallen: die horen elders
    (de regel uit de aanvulling op ADR-005, negatieven)."""
    import json
    root = Path(__file__).resolve().parents[1] / "eval"
    vragen = []
    for naam in ("golden_routering.jsonl", "golden_gesprek.jsonl"):
        for regel in (root / naam).read_text().splitlines():
            if regel.strip() and not regel.startswith("#"):
                rij = json.loads(regel)
                vragen += [rij.get("vraag", "")] + [b.get("vraag", "") for b in rij.get("beurten", [])]
    gevangen = [v for v in vragen if v and rg.opdracht_in(v)]
    assert not gevangen, gevangen


class AnnoteerApi(NepApi):
    async def haal_werkgebied(self, wid):
        return {"id": wid, "deelvragen": [
            {"id": "d1", "vraag": "Wie?", "status": "actief", "volgorde": 0, "bronnen": ["s1"]},
            {"id": "d2", "vraag": "Wanneer?", "status": "actief", "volgorde": 1, "bronnen": ["s1", "s2"]}]}

    async def haal_annotatie_werkvoorraad(self, wid, bereik="werkgebied", deelvraag_id=""):
        klaar = any(g for g in self.gesprekken)
        stand = (lambda i: "te_beoordelen" if klaar and i != "b:2" else "nieuw")
        return {"te_annoteren": [] if klaar else ["a:1", "a:2", "b:1", "b:2"],
                "eenheden": [{"bron_iri": i, "label": i, "regeling": "Iw", "selecties": s, "stand": {"status": stand(i)}}
                             for i, s in (("a:1", ["s1"]), ("a:2", ["s1"]), ("b:1", ["s2"]), ("b:2", ["s2"]))],
                "schatting": {"per_bepaling": 1000, "basis": 5}, "budget": {"resterend": 100_000, "actief": True}}


def test_annoteren_verdeelt_zonder_overlap_en_noemt_wat_te_beoordelen_is():
    from agent.regie.plan import plan_annoteren
    api, kinderen = AnnoteerApi(), Kinderen()

    async def plan():
        return plan_annoteren(await api.haal_werkgebied(WG), await api.haal_annotatie_werkvoorraad(WG))
    p = asyncio.run(plan())
    verzoek = ChatRequest(question="Annoteer per deelvraag de kern", conversation_id="regie", werkgebied_id=WG,
                          actie="regie_annoteren", plan_id=p.plan_id)
    _draai(verzoek, api, kinderen)
    per_kind = {v.deelvraag_id: (v.eenheden, v.bevestigd, v.budget_aandeel) for v in kinderen.verzoeken}
    assert per_kind == {"d1": (["a:1", "a:2"], 2, 2500), "d2": (["b:1", "b:2"], 2, 2500)}
    tekst = api.berichten[-1]["tekst"]
    assert "2 bepalingen met markeringen te beoordelen" in tekst
    assert "1 bepaling nog niet geannoteerd" in tekst and "start_bronnen_run" not in api.aanroepen


def test_een_getypte_opdracht_gaat_naar_de_regie(monkeypatch):
    import api.main as main
    gezien = {}

    async def nep(request, run, **kw):
        gezien["actie"] = request.actie
        yield {"type": "done"}
    monkeypatch.setattr(main, "regie_stroom", nep)
    monkeypatch.setattr(main.settings, "wetsanalyse_api_url", "http://api.test", raising=False)
    monkeypatch.setattr(main.settings, "wetsanalyse_api_token", "t", raising=False)
    if not main.settings.legt_zelf_vast:
        pytest.skip("legt_zelf_vast leest andere velden")
    maak = main._stroom_voor(ChatRequest(question="Zoek per deelvraag de bronnen", conversation_id="g",
                                         werkgebied_id=WG), "jurist")
    asyncio.run(_leeg(maak(Run(run_id="r", conversation_id="g"))))
    assert gezien == {"actie": None}


async def _leeg(stroom):
    return [e async for e in stroom]


def test_in_de_agentset_valt_alleen_onder_de_regie_wat_een_regie_verwacht():
    """De agentset van de centrale agent (ADR-016 §A6): de tekstroute pakt alleen een opdracht met `regisseur: true`."""
    import json
    rijen = [json.loads(r) for r in (Path(__file__).resolve().parents[1] / "eval" / "golden_centrale_agent.jsonl")
             .read_text().splitlines() if r.strip().startswith("{")]
    gevangen = [r["id"] for r in rijen if "opdracht" in r and rg.opdracht_in(r["opdracht"])
                and not (r.get("verwacht") or {}).get("regisseur")]
    assert not gevangen, gevangen
    assert any(rg.opdracht_in(r["opdracht"]) for r in rijen if r.get("id") == "M03")
