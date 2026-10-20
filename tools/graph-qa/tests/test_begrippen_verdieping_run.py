"""Lex denkt mee (spoor D, fase C2): de verdieping als beurt, tegen een nep-api en een nep-model.

Bewaakt: nooit rekenen zonder bevestiging, een gewijzigde werkvoorraad start niet, klare batches
worden hergebruikt (hervatten), budget en fouten laten de verdieping open in plaats van half, en de
uitkomst heeft de vorm van het api-contract.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import begrippen_verdieping as bv
from agent.begrippen_pipeline import classificatie, kaart, keten, verdieping as vd
from agent.begrippen_pipeline.model import Bron, Formulering, Manifest
from agent.jas_pipeline.taal.provider import NullProvider
from agent.models import ChatRequest, Verbruiksmeter
from fakes import agent_ctx, response, tool_block

API_CONTRACT = Path(__file__).resolve().parents[3] / "api" / "app" / "begrippen_run_contracts.py"


def _h(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


A = "De ontvanger verzendt de aanslag binnen zes weken. Daarna volgt de betaling."
B = "Tegen de aanslag kan bezwaar worden gemaakt; de inspecteur beslist."
I1, I2 = "urn:bwb:BWBR1:artikel:1", "urn:bwb:BWBR2:artikel:4"


def _f(eid, iri, tekst, deel, klasse="Rechtsobject"):
    s = tekst.index(deel)
    return Formulering(element_id=eid, bron_iri=iri, start=s, eind=s + len(deel), tekst=deel, jas_klasse=klasse)


MANIFEST = Manifest(
    bronnen=(Bron(bron_iri=I1, tekst=A, bron_hash=_h(A), label="art. 1 X", regeling="BWBR1"),
             Bron(bron_iri=I2, tekst=B, bron_hash=_h(B), label="art. 4 Y", regeling="BWBR2")),
    formuleringen=(_f("e1", I1, A, "de aanslag"), _f("e2", I2, B, "de aanslag"),
                   _f("e3", I1, A, "De ontvanger", "Rechtssubject")))
UITKOMST = keten.analyseer(MANIFEST, NullProvider())
VRAAG = UITKOMST.vragen[0].kandidaat_id


class NepApi:
    def __init__(self, *, aantal=1, batches=(), verdiept=False, run=True, groep_ids=None):
        self.wv = {"run": {"id": "r1", "manifest_id": MANIFEST.id} if run else None, "verdiept": verdiept,
                   "aantal": aantal, "vragen": [VRAAG] if aantal else [], "kaarten": [], "batches": list(batches),
                   "schatting": None, "budget": {"actief": True, "resterend": 50_000}}
        self.uitkomst = {"groep_ids": [g.id for g in UITKOMST.groepen] if groep_ids is None else groep_ids,
                         "vragen": [{"kandidaat_id": v.kandidaat_id} for v in UITKOMST.vragen]}
        self.batches: dict[str, dict] = {}
        self.verdieping: dict | None = None
        self.berichten: list[dict] = []
        self.geboekt: list[str] = []

    async def haal_werkgebied(self, wg):
        return {"naam": "Inv"}

    async def haal_verdieping(self, wg):
        return copy.deepcopy(self.wv)

    async def haal_begrippen_run(self, wg, rid):
        return {"manifest": MANIFEST.model_dump(mode="json"), "uitkomst": self.uitkomst}

    async def zet_begrippen_batch(self, wg, rid, bid, batch):
        self.batches[bid] = batch
        return {}

    async def zet_verdieping(self, wg, rid, v):
        self.verdieping = v
        return {}

    async def voeg_bericht_toe(self, gesprek, bericht):
        self.berichten.append(bericht)
        return {}

    async def boek_verbruik(self, verbruik, *, model, gesprek_id, run_id):
        self.geboekt.append(run_id)
        return {}

    async def aclose(self):
        pass


class NepModel:
    """Antwoordt per hulpmiddel; telt tokens zoals de adapter."""

    aanroepen: list[str] = []

    def __init__(self, oordeel="zelfde_betekenis", faal=False):
        self.oordeel, self.faal = oordeel, faal
        self.meter = Verbruiksmeter()

    def create(self, **kw):
        tool = kw["tools"][0]
        NepModel.aanroepen.append(tool["name"])
        if self.faal:
            raise RuntimeError("provider weg")
        props = tool["input_schema"]["properties"]
        if tool["name"] == classificatie.TOOL:
            items = [{"paar": p, "uitkomst": self.oordeel, "motivatie": "Beide de aanslag."}
                     for p in props["oordelen"]["items"]["properties"]["paar"]["enum"]]
            resp = response([tool_block("t", classificatie.TOOL, {"oordelen": items})], "tool_use")
        else:
            p = props["kaarten"]["items"]["properties"]
            items = [{"groep": g, "herkomst": "samengesteld", "fragmenten": [p["fragmenten"]["items"]["enum"][0]],
                      "definitie": "", "begripstype": "", "motivatie": "m"} for g in p["groep"]["enum"]]
            resp = response([tool_block("t", kaart.TOOL, {"kaarten": items})], "tool_use")
        resp.usage = SimpleNamespace(input_tokens=100, output_tokens=20)
        self.meter.tel_response(resp)
        return resp


@pytest.fixture(autouse=True)
def _leeg():
    NepModel.aanroepen = []


def _draai(api, bevestigd=None, maak=None, budget=None, stop=False):
    ctx = agent_ctx(api, gestopt=stop, maak_llm=maak or (lambda s: NepModel()), provider=NullProvider(),
                    budget_toegestaan=budget)
    return asyncio.run(bv.verdieping_kern(ctx, "wg1", bevestigd))


def _tekst(u):
    return u.gesprekstekst


# --- het verzoek -------------------------------------------------------------------------------

def test_de_bevestigingsknop_wordt_de_actie_meedenken():
    """De werkplek stuurt bij de knop nog `modus: begrippen_verdiepen`; dat is de taak `meedenken`."""
    r = ChatRequest(question="x", werkgebied_id="wg1", modus="begrippen_verdiepen", bevestigd=2)
    assert (r.actie, r.modus, r.bevestigd) == ("begrippen_meedenken", "auto", 2)
    with pytest.raises(ValueError):
        ChatRequest(question="x", modus="begrippen_verdiepen")
    with pytest.raises(ValueError):
        ChatRequest(question="x", werkgebied_id="wg1", bevestigd=2)


# --- het verloop -------------------------------------------------------------------------------

def test_zonder_bevestiging_alleen_het_voorstel():
    api = NepApi()
    evs = _draai(api)
    assert NepModel.aanroepen == [] and not api.batches and api.verdieping is None
    assert evs.status == "bevestiging" and evs.bevestiging == {"soort": "begrippen_verdiepen", "werkgebied_id": "wg1",
                                                               "aantal": 1, "schatting": None}
    assert "1 twijfelpunt" in _tekst(evs) and "50.000 tokens" in _tekst(evs)


def test_een_gewijzigde_werkvoorraad_start_niet():
    api = NepApi(aantal=1)
    evs = _draai(api, bevestigd=3)
    assert NepModel.aanroepen == [] and "De werkvoorraad veranderde: nu 1 in plaats van 3" in _tekst(evs)
    assert evs.bevestiging["aantal"] == 1


def test_met_bevestiging_batches_en_uitkomst():
    api = NepApi()
    evs = _draai(api, bevestigd=1)
    assert NepModel.aanroepen == [classificatie.TOOL, kaart.TOOL]
    assert [b["soort"] for b in api.batches.values()] == ["vraag", "kaart"]
    assert all(b["tokens"] == 120 for b in api.batches.values())
    assert api.geboekt == ["run9.v0", "run9.v1"]
    v = api.verdieping
    [groep] = v["groepen"]
    assert groep["door"] == "model" and groep["aandacht"] == "geel" and groep["leden"] == ["e1", "e2"]
    assert v["kaarten"][0]["herkomst"] == "samengesteld" and v["vragen"] == []
    assert v["oordelen"][0]["oordeel"] == "zelfde_betekenis"
    assert evs.artefact["soort"] == "begrippen" and evs.status == "ok" and evs.meting["model"]
    assert "Klaar met meedenken" in _tekst(evs)


def test_een_klare_batch_wordt_hervat_niet_opnieuw_gerekend():
    eerste = NepApi()
    _draai(eerste, bevestigd=1)
    [(vid, vraag)] = [(k, b) for k, b in eerste.batches.items() if b["soort"] == "vraag"]
    NepModel.aanroepen = []
    tweede = NepApi(aantal=0, batches=[{"id": vid, "resultaat": {"oordelen": vraag["oordelen"]}}])
    tweede.wv["kaarten"] = ["G-iets"]                      # nog iets te doen, dus wel bevestigen
    tweede.wv["aantal"] = 1
    _draai(tweede, bevestigd=1)
    assert NepModel.aanroepen == [kaart.TOOL]
    assert tweede.verdieping["groepen"] == eerste.verdieping["groepen"]


def test_budget_op_laat_de_verdieping_open():
    api = NepApi()

    async def op():
        return False
    evs = _draai(api, bevestigd=1, budget=op)
    assert NepModel.aanroepen == [] and api.verdieping is None
    assert "niet helemaal klaar – je tokenbudget is op" in _tekst(evs)


def test_een_fout_in_een_batch_laat_de_verdieping_open():
    api = NepApi()
    evs = _draai(api, bevestigd=1, maak=lambda s: NepModel(faal=True))
    assert api.verdieping is None and "1 batch mislukte" in _tekst(evs)


def test_stoppen():
    api = NepApi()
    evs = _draai(api, bevestigd=1, stop=True)
    assert NepModel.aanroepen == [] and "gestopt op verzoek" in _tekst(evs)


def test_niets_voor_het_model_dan_meteen_en_zonder_model():
    api = NepApi(aantal=0)
    _draai(api)
    assert NepModel.aanroepen == [] and api.verdieping is not None
    assert api.verdieping["vragen"] == [VRAAG] and api.verdieping["oordelen"] == []


def test_een_veranderde_keten_stopt():
    api = NepApi(groep_ids=["Ganders"])
    evs = _draai(api, bevestigd=1)
    assert NepModel.aanroepen == [] and "andere voorstellen" in _tekst(evs) and api.verdieping is None


def test_al_verdiept_en_geen_voorstellen():
    evs = _draai(NepApi(verdiept=True))
    assert "al meegedacht" in _tekst(evs)
    evs = _draai(NepApi(run=False))
    assert "nog geen begripsvoorstellen" in _tekst(evs)


# --- het contract ------------------------------------------------------------------------------

def _velden(klasse: str) -> set[str]:
    boom = ast.parse(API_CONTRACT.read_text())
    k = next(n for n in boom.body if isinstance(n, ast.ClassDef) and n.name == klasse)
    eigen = {s.target.id for s in k.body if isinstance(s, ast.AnnAssign)}
    for basis in k.bases:
        if isinstance(basis, ast.Name) and basis.id != "BaseModel":
            eigen |= _velden(basis.id)
    return eigen


def test_de_uitkomst_volgt_het_api_contract():
    if not API_CONTRACT.exists():
        pytest.skip("api niet in deze checkout")
    from agent.begrippen_pipeline.model import Fragment, Kaart, ModelOordeel
    assert set(Kaart.model_fields) == _velden("Kaart")
    assert set(Fragment.model_fields) == _velden("KaartFragment")
    assert set(ModelOordeel.model_fields) == _velden("ModelOordeel")
    her = vd.hergroepeer(MANIFEST, UITKOMST, [ModelOordeel(kandidaat_id=VRAAG, oordeel="zelfde_betekenis")])
    groep = bv._groep_contract(her.groepen[0], MANIFEST, UITKOMST, {VRAAG})
    assert set(groep) == _velden("VerdiepingGroep") and groep["door"] == "model"
    assert set(groep["voorstel"]) <= _velden("Voorstel")
