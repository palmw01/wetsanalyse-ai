"""Drift-guard: de agent-modellen tegen het contract van de wetsanalyse-api.

graph-qa en de api hebben elk hun eigen model van hetzelfde object, en ze komen alleen samen in één
HTTP-call in een ánder proces. Een verschil tussen die twee is daar geen typefout maar een 422 – en
omdat de batch alles-of-niets is, verliest de jurist dan de complete annotatie.

Het elementcontract van de api (`annotatie_v2_contracts.Element`) laat onbekende velden door
(`extra="allow"`), dus een veld dat de api niet declareert reist gewoon mee. Wat wél kan breken is
een veld dat beide kanten kennen maar anders typeren. De vertaling staat op de grens
(`wetsanalyse_api.naar_contract`); deze test faalt zodra zo'n gedeeld veld uit elkaar loopt zonder
dat de vertaling het opvangt.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent import models as am
from agent.wetsanalyse_api import naar_contract, _leeg_is_niets

CONTRACT = Path(__file__).resolve().parents[3] / "api" / "app" / "annotatie_v2_contracts.py"

#: Gedeelde velden met een bewust verschil dat de api zelf afhandelt: "" betekent daar "geen id".
OPGEVANGEN = {("AnnotatieVoorstel", "id")}

PAREN = [("AnnotatieVoorstel", "Element")]


def _api_velden(klasse: str, bestand: Path = CONTRACT) -> dict[str, str]:
    """De veldtypes van één contractklasse, uit de bron gelezen.

    Importeren kan niet: de api-modules gebruiken relatieve imports en graph-qa heeft de api niet als
    afhankelijkheid – dat is juist de scheiding die deze test bewaakt.
    """
    bron = bestand.read_text()
    blok = re.search(rf"^class {klasse}\(BaseModel\):(.*?)(?=^class |\Z)", bron, re.S | re.M)
    assert blok, f"contractklasse {klasse} niet gevonden"
    uit: dict[str, str] = {}
    for regel in blok.group(1).splitlines():
        regel = regel.split("#")[0].strip()
        if regel.startswith(('"', "'")):
            continue
        veld = re.match(r"^(\w+)\s*:\s*([^=]+?)(?:\s*=.*)?$", regel)
        if veld:
            uit[veld.group(1)] = veld.group(2).strip()
    return uit


def _vorm(annotatie: object) -> str:
    """De vorm van een type, zonder module-paden: `list[a.b.C]` en `list[C]` zijn hetzelfde.

    Niet splitsen op de laatste punt – dat verminkt `list[...]` tot `C]` en levert vals alarm.
    """
    tekst = str(annotatie).replace("typing.", "").replace("<class '", "").replace("'>", "")
    tekst = re.sub(r"[\w.]*\.(\w+)", r"\1", tekst)
    # Een kale `dict` valideert hetzelfde als `dict[str, Any]`.
    return tekst.replace(" ", "").strip().replace("dict[str,Any]", "dict")


@pytest.mark.skipif(not CONTRACT.exists(), reason="api-contract niet beschikbaar (los uitgecheckt)")
@pytest.mark.parametrize("agent_klasse, api_klasse", PAREN)
def test_geen_stil_verschil_met_het_api_contract(agent_klasse, api_klasse):
    agent = getattr(am, agent_klasse).model_fields
    api = _api_velden(api_klasse)

    for naam, veld in agent.items():
        if (agent_klasse, naam) == ("AnnotatieVoorstel", "ankers"):
            # Getypeerde multiankers aan de api-kant; de runtime-roundtrip hieronder bewaakt deze grens.
            assert _vorm(veld.annotation) == "list[dict]"
            continue
        if (agent_klasse, naam) in OPGEVANGEN or naam not in api:
            continue
        assert _vorm(veld.annotation) == _vorm(api[naam]), (
            f"{agent_klasse}.{naam} is {_vorm(veld.annotation)} en {api_klasse}.{naam} is "
            f"{api[naam]}. Zo'n verschil is een 422 op de batch, en die is alles-of-niets: de "
            f"jurist verliest de hele annotatie. Vertaal het in `wetsanalyse_api.naar_contract` en "
            f"zet het in OPGEVANGEN."
        )


def test_v2_multiankers_blijven_getypeerd_en_behouden_aan_de_api_grens():
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("v2_contract_test", CONTRACT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    anchors = [
        {"bron_iri": "urn:lid1", "start": 1, "eind": 2, "tekst": "😀", "bron_hash": "a" * 64},
        {"bron_iri": "urn:lid2", "start": 0, "eind": 4, "tekst": "test", "bron_hash": "b" * 64},
    ]
    proposal = am.AnnotatieVoorstel(klasse="Rechtsfeit", tekst="😀 test", ankers=anchors)
    actual = module.Element.model_validate(proposal.model_dump()).model_dump()
    assert actual["ankers"] == anchors
    assert actual["klasse"] == "Rechtsfeit" and actual["tekst"] == "😀 test"
    with pytest.raises(ValueError):
        module.Element.model_validate({"klasse": "Rechtsfeit", "tekst": "x", "ankers": [{"bron_iri": "urn:x"}]})


def test_de_vertaling_dekt_alles_wat_in_opgevangen_staat():
    """Anders staat er een afspraak op papier die niemand uitvoert."""
    assert naar_contract({"aandacht": ""})["aandacht"] is None
    assert naar_contract({"aandacht": "geel"})["aandacht"] == "geel", "een echt oordeel blijft staan"


def test_de_vertaling_laat_geldige_waarden_met_rust():
    element = {"aandacht": "rood", "klasse": "Voorwaarde", "tekst": "indien"}
    assert naar_contract(element) == element


def test_leeg_is_niets_werkt_op_elk_veld():
    assert _leeg_is_niets({"aandacht": ""})["aandacht"] is None
    assert _leeg_is_niets({}, "iets")["iets"] is None


def test_de_guard_slaat_aan_op_precies_dit_soort_verschil():
    """Bewijs dat de vergelijking een typeverschil ziet, in plaats van alleen groen te staan."""
    api = _api_velden("Element")
    assert _vorm(am.AnnotatieVoorstel.model_fields["klasse"].annotation) == _vorm(api["klasse"])
    assert _vorm("str | None") != _vorm(api["klasse"]), "als dit gelijk is, bewaakt de guard niets meer"


GESPREK_CONTRACT = CONTRACT.with_name("gesprek_contracts.py")


def _bericht_velden() -> set[str]:
    """De velden van `BerichtInvoer` in de api, uit de bron gelezen (zelfde reden als hierboven)."""
    blok = re.search(r"^class BerichtInvoer\(BaseModel\):(.*?)(?=^class |\Z)",
                     GESPREK_CONTRACT.read_text(), re.S | re.M)
    assert blok, "BerichtInvoer niet gevonden"
    return {m.group(1) for regel in blok.group(1).splitlines()
            if (m := re.match(r"^\s{4}(\w+)\s*:", regel.split("#")[0]))}


@pytest.mark.parametrize("annotatie", [True, False])
def test_elk_veld_van_het_chatbericht_bestaat_in_de_api(annotatie):
    """Een veld dat `BerichtInvoer` niet kent, laat Pydantic stil vallen: dan staat de chip naar het
    annotatiepaneel er direct na de beurt, maar is hij na het heropenen van het gesprek weg. Deze
    test faalt in plaats van dat een veld ongemerkt verdwijnt."""
    import asyncio
    from types import SimpleNamespace
    from agent import beurt
    from fakes import make_settings

    verstuurd: list[dict] = []

    class Api:
        def __init__(self, *args):
            pass
        async def zet_bronnode_batch(self, data):
            return {}
        async def voeg_bericht_toe(self, gesprek_id, bericht):
            verstuurd.append(bericht)
            return {}
        async def aclose(self):
            pass

    schrijver = beurt.BeurtSchrijver()
    schrijver.verwerk({"type": "tool_execution", "run_id": "r1", "call_id": "c1", "tool": "t", "phase": "end"})
    if annotatie:
        schrijver.doel = {"schema_versie": 2, "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1",
                          "snapshot_id": "s", "bereik": [], "label": "Artikel 9, Lid 1"}
        schrijver.run = {"modus": "nieuw"}
        schrijver.hergebruik = {"volledig": False}
    else:
        schrijver.tekst = "Een antwoord."

    async def leg_vast():
        original = beurt.WetsanalyseApi
        beurt.WetsanalyseApi = Api
        try:
            return [e async for e in beurt._leg_vast(schrijver, settings=make_settings(),
                    run=SimpleNamespace(run_id="r1"), gesprek_id="g1", gestopt=False, user_id="jurist")]
        finally:
            beurt.WetsanalyseApi = original

    asyncio.run(leg_vast())
    bericht, = verstuurd
    if annotatie:
        assert "annotatie_doel" in bericht  # anders toetst deze test het v2-pad niet
    onbekend = set(bericht) - _bericht_velden()
    assert not onbekend, f"de api laat deze velden van het chatbericht vallen: {sorted(onbekend)}"


def test_search_annotaties_vraagt_niets_wat_de_api_niet_kent():
    """De filters van de zoektool zijn velden van `Zoekvraag`, en een keuzelijst in de tool heeft
    precies de waarden die de api toestaat. Anders weigert de api (422) wat het model mocht vragen,
    of kan het model iets niet vragen wat de api wel kan."""
    from agent.tools.annotatie_tools import ANNOTATIE_TOOLS

    props = next(t for t in ANNOTATIE_TOOLS if t["name"] == "search_annotaties")["input_schema"]["properties"]
    velden = _api_velden("Zoekvraag")
    assert set(props) <= set(velden), f"onbekend bij de api: {sorted(set(props) - set(velden))}"
    blok = re.search(r"^class Zoekvraag\(BaseModel\):(.*?)(?=^class |\Z)", CONTRACT.read_text(), re.S | re.M).group(1)
    for naam, definitie in props.items():
        enum = (definitie.get("items") or {}).get("enum")
        if not enum:
            continue
        m = re.search(rf"^\s*{naam}\s*:\s*list\[Literal\[(.*?)\]\]", blok, re.S | re.M)
        assert m, f"{naam}: geen keuzelijst in Zoekvraag"
        assert set(enum) == set(re.findall(r'"([^"]+)"', m.group(1))), naam
