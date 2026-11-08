"""De connectorbeschrijving is de enige bron (ADR-013): een onvolledige beschrijving of handwerk ernaast wordt rood.

Een bronconnector is een beschrijving in `bronmodel.connectors`, tools in `agent/tools/` en een straatvlag. De rest
van de keten leidt af: de toollaag (`tools.CONNECTORS`), de specialisten, de api (register en toegestane namen) en de
werkplek (de groep in de bronnenlijst). Deze tests lezen ook de api en de frontend, en draaien daarom mee in
`scripts/kruistests.sh`.

De nep-connector onderaan bewijst het generieke: een connector die alleen een beschrijving en een tool heeft, komt
zonder één regel extra code in de toollaag en bij de specialisten.
"""
from __future__ import annotations

import dataclasses
import re
import typing
from pathlib import Path

import pytest
from bronmodel import connectors as bm
from bronmodel.extern import BRONTYPEN, externe_vindplaats

from agent import specialists, tools
from agent.config import Settings
from agent.models import Connector

WORTEL = Path(__file__).resolve().parents[3]
BESCHRIJVINGEN = list(bm.CONNECTORS.values())
IDS = [c.naam for c in BESCHRIJVINGEN]

#: Gewone wetsvragen: geen enkele connector mag zich daardoor aangesproken voelen.
WETSVRAGEN = (
    "Wat staat er in artikel 9 van de Invorderingswet 1990?",
    "Wat is een belastingschuldige?",
    "Welke artikelen gaan over uitstel van betaling?",
    "Annoteer artikel 36 lid 2 van de Invorderingswet 1990",
    "Hoe verhoudt artikel 25 zich tot de Leidraad Invordering 2008?",
    "Wat voor weer wordt het morgen?",
)


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_beschrijving_is_volledig(c: bm.ConnectorBeschrijving):
    for veld in dataclasses.fields(c):
        if veld.init:
            assert getattr(c, veld.name), f"{c.naam}: veld '{veld.name}' is leeg"
    assert re.fullmatch(r"[a-z][a-z0-9_]*", c.naam)
    assert c.brontype in BRONTYPEN and c.brontype != "wettekst"
    assert c.leestool in c.tools
    assert c.specialisten <= set(specialists.SPECIALISTS), "een rol die niet bestaat"
    assert len(c.voorbeeldvragen) >= 3


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_tools_bestaan_en_horen_bij_een_connector(c: bm.ConnectorBeschrijving):
    bestaand = {t["name"] for t in tools.TOOLS}
    assert c.tools <= bestaand, f"{c.naam}: tools zonder implementatie: {c.tools - bestaand}"
    anderen = set().union(*(o.tools for o in BESCHRIJVINGEN if o is not c))
    assert not c.tools & anderen, "een tool hoort bij precies één connector"


def test_elke_connectortool_heeft_een_beschrijving():
    assert tools.CONNECTOR_TOOLS == frozenset().union(*(c.tools for c in BESCHRIJVINGEN))
    assert tools.CONNECTORS == {c.naam: c.tools for c in BESCHRIJVINGEN}


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_straat_kan_hem_aanbieden(c: bm.ConnectorBeschrijving):
    assert f"connector_{c.naam}" in Settings.model_fields, f"Settings mist connector_{c.naam}"
    config = (WORTEL / "tools" / "graph-qa" / "agent" / "config.py").read_text(encoding="utf-8")
    assert f'e.get("{c.env}")' in config, f"config.py leest {c.env} niet"
    assert Settings.model_fields[f"connector_{c.naam}"].default is False, "een connector staat standaard uit"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_signalen_herkennen_zijn_vragen_en_geen_wetsvragen(c: bm.ConnectorBeschrijving):
    for v in c.voorbeeldvragen:
        assert c.herkent(v), f"{c.naam} herkent zijn eigen voorbeeldvraag niet: {v}"
    for v in WETSVRAGEN:
        assert not c.herkent(v), f"{c.naam} voelt zich aangesproken door een wetsvraag: {v}"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_het_id_heeft_de_vorm_van_zijn_brontype(c: bm.ConnectorBeschrijving):
    for prefix in c.id_prefixen:
        voorbeeld = {"kst-": "kst-33755-3", "ECLI:": "ECLI:NL:HR:2020:1234", "CELEX:": "CELEX:32016R0679"}.get(prefix)
        if voorbeeld:
            vp = externe_vindplaats(voorbeeld)
            assert vp is not None and vp.brontype == c.brontype


def test_de_namen_in_de_contracten_zijn_de_beschrijving():
    assert set(typing.get_args(Connector)) == set(bm.CONNECTORS)
    # De api leest dezelfde namen; met de hand een Literal ernaast is drift die pas bij een nieuwe connector opvalt.
    for bestand in ("connectors.py", "gesprek_contracts.py", "werkgebied_contracts.py"):
        bron = (WORTEL / "api" / "app" / bestand).read_text(encoding="utf-8")
        assert "from bronmodel.connectors import" in bron, f"api/app/{bestand} leidt de namen niet af"
        for c in BESCHRIJVINGEN:
            assert f'Literal["{c.naam}"]' not in bron, f"api/app/{bestand}: '{c.naam}' met de hand"


def test_geen_specialist_noemt_een_connectortool_met_de_hand():
    bron = (WORTEL / "tools" / "graph-qa" / "agent" / "specialists.py").read_text(encoding="utf-8")
    for t in tools.CONNECTOR_TOOLS:
        assert f'"{t}"' not in bron, f"specialists.py noemt {t}: dat volgt uit de beschrijving"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_rollen_krijgen_zijn_tools(c: bm.ConnectorBeschrijving):
    for rol in c.specialisten:
        spec = specialists.SPECIALISTS[rol]
        assert spec.tools is None or c.tools <= spec.tools


def test_de_werkplek_kent_elke_groep():
    bronnen = (WORTEL / "frontend" / "lib" / "bronnen.ts").read_text(encoding="utf-8")
    naam = re.search(r"BRONTYPE_NAAM[^=]*=\s*\{([^}]*)\}", bronnen)
    assert naam, "BRONTYPE_NAAM niet gevonden"
    paren = dict(re.findall(r"(\w+):\s*\"([^\"]+)\"", naam.group(1)))
    for c in BESCHRIJVINGEN:
        assert paren.get(c.brontype) == c.groep, f"de werkplek noemt {c.brontype} anders dan de beschrijving"


# --- het generieke bewijs -------------------------------------------------------------------------------------

def test_een_nieuwe_connector_komt_er_zonder_code_bij(monkeypatch):
    """Een beschrijving en een tool: de toollaag, het filter en de specialisten volgen vanzelf."""
    nep = bm.ConnectorBeschrijving(
        naam="testbron", label="Testbron", brontype="uitspraak", groep="Uitspraken",
        dekt="uitspraken van een testgerecht", signalen=(r"\btestgerecht\b",), tools=frozenset({"zoek_testbron"}),
        leestool="zoek_testbron", id_prefixen=("ECLI:",), specialisten=frozenset({"duiding"}),
        rol_in_antwoord="een uitspraak onderbouwt een uitleg, nooit wat de wet zegt", grenzen="alleen een test",
        beheer="Een nep-connector.", voorbeeldvragen=("Wat zei het testgerecht?",))
    assert nep.herkent("Wat zei het testgerecht hierover?") and nep.herkent("Lees ECLI:NL:HR:2020:1234")
    assert not nep.herkent(WETSVRAGEN[0])

    monkeypatch.setitem(bm.CONNECTORS, nep.naam, nep)
    monkeypatch.setattr(tools, "CONNECTORS", {c.naam: c.tools for c in bm.CONNECTORS.values()})
    monkeypatch.setattr(tools, "CONNECTOR_TOOLS", frozenset().union(*tools.CONNECTORS.values()))
    assert "testbron" in bm.herkende("Wat zei het testgerecht?")
    # Het filter: uit tenzij de straat hem aanbiedt én de beurt hem kiest.
    uit = tools.toegestane_tools(frozenset({"zoek_testbron", "get_lid"}), Settings(), None)
    assert uit == {"get_lid"}
    aan = Settings().model_copy(update={"connector_testbron": True})
    assert tools.toegestane_tools(frozenset({"zoek_testbron"}), aan, ["testbron"]) == {"zoek_testbron"}
    assert tools.toegestane_tools(frozenset({"zoek_testbron"}), aan, []) == frozenset()
    # De specialisten: de rol uit de beschrijving krijgt de tool, een andere niet.
    afgeleid = specialists._met_connectors(dict(specialists.SPECIALISTS))
    assert "zoek_testbron" in afgeleid["duiding"].tools
    assert "zoek_testbron" not in afgeleid["definitie"].tools
