"""Het beslisregister: ook wat geen voorstel werd, reist mee naar de api (validatieplan V4)."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from eval.beslisstabiliteit import rapport
from test_hybride_keten import KetenLLM, _draai, _elementen

V2_CONTRACT = Path(__file__).resolve().parents[3] / "api" / "app" / "annotatie_v2_contracts.py"


def _velden(klasse: str) -> set[str]:
    """De velden van een api-model, uit de bron gelezen: de api is geen dependency van graph-qa."""
    blok = re.search(rf"^class {klasse}\(BaseModel\):(.*?)(?=^class |\Z)", V2_CONTRACT.read_text(), re.S | re.M)
    assert blok, f"{klasse} niet gevonden"
    return {m.group(1) for regel in blok.group(1).splitlines()
            if (m := re.match(r"^\s{4}(\w+)\s*:", regel.split("#")[0]))}


def _kies(toegestaan: list[str]) -> str:
    """Wijs de voorwaarde af en kies bij de rest een klasse die niet mag: een contractfout."""
    if "Voorwaarde" in toegestaan:
        return GEEN_ANNOTATIE
    return "Plaatsaanduiding"


def _register(events) -> list[dict]:
    return next(e["dekking"]["beslissingen"] for e in events if e["type"] == "dekking")


def test_register_bevat_elke_kandidaat_ook_de_afgewezen():
    events = _draai(KetenLLM(kies=_kies))
    register = _register(events)
    run = next(e for e in events if e["type"] == "run")["run"]
    assert len(register) == run["instellingen"]["meting"]["kandidaten"]
    afgewezen = [b for b in register if b["status"] == "REJECTED"]
    assert afgewezen, "de voorwaarde is afgewezen en hoort in het register te staan"
    labels_met_element = {e["trace"]["kandidaat"]["label"] for e in _elementen(events)}
    assert not {b["label"] for b in afgewezen} & labels_met_element
    # De resolver overschrijft `reden`; de classifierreden blijft bewaard.
    contract = [b for b in register if b["classifier_reden"].startswith("CLASSIFIER_ONGELDIGE_KLASSE")]
    assert contract and all(not b["reden"].startswith("CLASSIFIER_") for b in contract)
    assert all(b["bewijs_fingerprint"] and b["bron_iri"] and b["eind"] > b["start"] for b in register)


def test_register_is_deterministisch_over_runs():
    a, b = (_register(_draai(KetenLLM(kies=_kies))) for _ in range(2))
    assert [x["bewijs_fingerprint"] for x in a] == [x["bewijs_fingerprint"] for x in b]
    r = rapport([a, b])
    assert r["fingerprint_drift"] == [] and r["kandidaatbeslisstabiliteit"] == 1.0
    assert r["contractfouten"] == 2 * sum(x["classifier_reden"].startswith("CLASSIFIER_ONGELDIGE") for x in a)


def test_register_past_in_het_api_contract():
    register = _register(_draai(KetenLLM(kies=_kies)))
    onbekend = {k for b in register for k in b} - _velden("KandidaatBeslissing")
    assert not onbekend, f"de api kent deze registervelden niet: {sorted(onbekend)}"


def test_driver_stuurt_het_register_mee_in_de_batch():
    from agent import beurt
    from fakes import make_settings

    verstuurd: list[dict] = []
    berichten: list[dict] = []

    class Api:
        def __init__(self, *args):
            pass

        async def zet_bronnode_batch(self, data):
            verstuurd.append(data)
            return {}

        async def voeg_bericht_toe(self, gesprek_id, bericht):
            berichten.append(bericht)
            return {}

        async def aclose(self):
            pass

    register = [{"kandidaat_id": "K1", "label": "C001", "status": "REJECTED"}]
    schrijver = beurt.BeurtSchrijver()
    schrijver.doel = {"schema_versie": 2, "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1",
                      "snapshot_id": "s", "bereik": [], "label": "Lid 1"}
    schrijver.run = {"modus": "nieuw"}
    schrijver.hergebruik = {"volledig": False}
    schrijver.verwerk({"type": "dekking", "dekking": {"per_bron": {}, "proces": {}, "beslissingen": register}})

    async def leg_vast():
        original = beurt.WetsanalyseApi
        beurt.WetsanalyseApi = Api
        try:
            return [e async for e in beurt._leg_vast(schrijver, settings=make_settings(),
                    run=SimpleNamespace(run_id="r1"), gesprek_id="g1", gestopt=False, user_id="jurist")]
        finally:
            beurt.WetsanalyseApi = original

    asyncio.run(leg_vast())
    batch, = verstuurd
    assert batch["beslissingen"] == register
    onbekend = set(batch) - _velden("Batch")
    assert not onbekend, f"de api laat deze batchvelden vallen: {sorted(onbekend)}"
    assert "beslissingen" not in berichten[0].get("dekking", {}), "het register hoort niet in het chatbericht"


def test_rapport_ziet_een_wisselende_beslissing_en_een_fingerprint_drift():
    def b(uitkomst, klasse="", fp="f"):
        return {"kandidaat_id": "K1", "start": 0, "eind": 5, "status": uitkomst, "klasse": klasse,
                "bewijs_fingerprint": fp}
    r = rapport([[b("ACCEPTED", "Rechtsobject")], [b("REJECTED")], [b("ACCEPTED", "Rechtsobject", fp="g")]])
    [rij] = r["rijen"]
    assert r["kandidaatbeslisstabiliteit"] == 0.0 and r["fingerprint_drift"] == ["K1"]
    assert rij["accept_overeenstemming"] == 2 / 3 and rij["klasse_overeenstemming"] == 1.0
    assert rij["uitkomsten"] == ["ACCEPTED:Rechtsobject", "REJECTED:", "ACCEPTED:Rechtsobject"]
    # Een kandidaat die in één run ontbreekt, is niet detectiestabiel.
    r = rapport([[b("REJECTED")], []])
    assert r["detectie_stabiel"] == 0.0 and r["rijen"][0]["aanwezig"] == "1/2"
