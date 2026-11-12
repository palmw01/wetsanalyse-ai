"""De catalogus (ADR-014) volgt de registers: volledig in beide richtingen, en niets met de hand ernaast.

Deze tests lezen bestanden in de hele repo (skill, bronmodel) en draaien daarom mee in `scripts/kruistests.sh`.
Bewijs voor het generieke, zoals bij de connectortest: een nep-specialist en een nep-connector komen in de catalogus
zonder één regel extra code.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest
from bronmodel import catalogus as bc
from bronmodel import connectors as bm

import typing

from agent import catalogus as cat
from agent import specialists
from agent.agents.register import AGENTS
from agent.begrippen_pipeline import keten as begrippenketen
from agent.jas_pipeline import keten as annotatieketen
from agent.models import ACTIE_TAAK, Actie
from agent.methodepakket import PAKKET
from agent.sjablonen import SJABLONEN

WORTEL = Path(__file__).resolve().parents[3]
ALLE = cat.catalogus()
IDS = [o.id for o in ALLE]


def _ids(soort: str) -> set[str]:
    return {o.naam for o in ALLE if o.soort == soort}


def test_elk_register_in_de_catalogus_en_omgekeerd():
    assert _ids("specialist") == set(specialists.SPECIALISTS)
    assert _ids("sjabloon") == set(SJABLONEN)
    assert _ids("connector") == set(bm.CONNECTORS)
    assert _ids("rol") == set(PAKKET["rollen"])
    assert _ids("methode") == {"wetsanalyse"}
    assert _ids("agent") == set(AGENTS)


def test_elk_regelbestand_staat_in_de_catalogus():
    """Elke YAML in de ketens is een regelset; een nieuw bestand komt vanzelf mee (of de catalogus weigert het, als
    zijn map niet in `REGELMAPPEN` staat)."""
    bestanden = {o.bestand[0] for o in ALLE if o.soort == "regelset"}
    for pad in cat.regelbestanden():
        rel = "tools/graph-qa/" + pad.relative_to(WORTEL / "tools/graph-qa").as_posix()
        assert rel in bestanden or "/profielen/" in rel, f"{rel} niet in de catalogus"


def test_een_agent_noemt_al_zijn_taken_en_acties():
    for naam, mod in AGENTS.items():
        o = cat.onderdeel(bc.oid("agent", naam))
        assert {t["taak"] for t in o.inhoud["taken"]} == {t.value for t in mod.Taak}
        assert {t["taak"] for t in o.inhoud["taken"] if t["model"]} == {t.value for t in mod.MODEL_TAKEN}
        assert set(o.ingang) == {a for a, (ag, _) in ACTIE_TAAK.items() if ag == naam}


@pytest.mark.parametrize("keten,fn", [(annotatieketen, "fasen.klaar"), (begrippenketen, "fase")])
def test_elke_fase_die_een_keten_meldt_staat_in_haar_stappen(keten, fn):
    """De stappen van een workflow komen uit de code: elke fase die de keten meldt, staat in `FASEN`, en omgekeerd."""
    bron = Path(keten.__file__).read_text()
    gemeld = set(re.findall(rf'\b{re.escape(fn)}\("([^"]+)"', bron))
    assert gemeld and gemeld == {s.naam for s in keten.FASEN}


def test_ingangen_van_workflows_en_agents_bestaan():
    acties = set(typing.get_args(Actie))
    for o in ALLE:
        if o.soort in ("agent", "workflow"):
            for i in o.ingang:
                assert i in acties or i == "annoteer", f"{o.id}: ingang {i} is geen actie"


def test_een_workflow_heeft_stappen_en_een_laag():
    for o in ALLE:
        if o.soort == "workflow":
            assert o.laag and o.stappen
            assert o.model == bc.zwaarste([s.model for s in o.stappen])


def test_ids_zijn_uniek_en_stabiel():
    assert len(IDS) == len(set(IDS))
    assert all(o.id == bc.oid(o.soort, o.naam) for o in ALLE)


@pytest.mark.parametrize("o", ALLE, ids=IDS)
def test_elk_onderdeel_is_beschreven(o: bc.Onderdeel):
    assert o.label and o.doel and o.versie, f"{o.id}: label, doel of versie leeg"
    assert o.soort in bc.SOORTEN
    assert o.model in ("geen", "strict", "agent")
    assert o.herkomst.bron and o.herkomst.licentie
    assert o.bestand and o.tests


@pytest.mark.parametrize("o", ALLE, ids=IDS)
def test_bestanden_en_tests_bestaan(o: bc.Onderdeel):
    for pad in (*o.bestand, *o.tests):
        assert (WORTEL / pad).exists(), f"{o.id}: {pad} bestaat niet"


@pytest.mark.parametrize("o", ALLE, ids=IDS)
def test_afhankelijkheden_bestaan(o: bc.Onderdeel):
    for d in o.hangt_af_van:
        assert d in IDS, f"{o.id} hangt af van {d}, dat niet in de catalogus staat"


def test_bewerkbaar_bij_een_rol_zijn_haar_secties():
    for o in ALLE:
        if o.soort == "rol":
            assert set(o.bewerkbaar) == set(PAKKET["rollen"][o.naam])
            assert set(o.bewerkbaar) <= set(PAKKET["secties"])


def test_verwijzingen_van_de_methode_staan_in_het_bronregister():
    register = (WORTEL / ".claude/skills/wetsanalyse/references/bronnen.md").read_text()
    for o in ALLE:
        if o.soort in ("methode", "rol"):
            for code in o.herkomst.verwijzing:
                assert f"| {code} |" in register, f"{o.id}: broncode {code} niet in het bronregister"


def test_letterlijke_tekst_van_derden_vraagt_een_bron_met_notice():
    """Letterlijk opnemen mag alleen bij een bron waarvan de licentie dat toestaat (W3C, ADR-014 §6), met een
    `BRON.md` in de repo die de notice draagt. Nu staat geen enkel onderdeel op letterlijk; de toets is er voor wie
    het eerste toevoegt."""
    for o in ALLE:
        if o.herkomst.letterlijk:
            bronnen = [p for p in o.herkomst.verwijzing if p.endswith("BRON.md")]
            assert bronnen, f"{o.id}: letterlijk zonder BRON.md in de verwijzing"
            for p in bronnen:
                assert "licen" in (WORTEL / p).read_text().lower()


def test_model_is_afgeleid():
    per_soort = {o.soort: o.model for o in ALLE if o.soort in ("specialist", "sjabloon", "connector", "methode")}
    assert per_soort == {"specialist": "agent", "sjabloon": "strict", "connector": "geen", "methode": "geen"}


def test_een_connector_draagt_zijn_straatvlag():
    for o in ALLE:
        if o.soort == "connector":
            assert o.straat == bm.CONNECTORS[o.naam].env


def test_een_specialist_hangt_aan_zijn_rol_en_sjablonen():
    for naam, spec in specialists.SPECIALISTS.items():
        o = cat.onderdeel(bc.oid("specialist", naam))
        assert bc.oid("rol", specialists.methoderol(naam)) in o.hangt_af_van
        assert {bc.oid("sjabloon", s) for s in spec.sjablonen} <= set(o.hangt_af_van)


def test_inhoud_valt_weg_uit_de_lijst():
    o = ALLE[0]
    assert "inhoud" not in o.als_dict()
    assert "inhoud" in o.als_dict(met_inhoud=True)


def test_een_onderdeel_met_een_ongeldig_id_wordt_geweigerd():
    with pytest.raises(ValueError):
        bc.Onderdeel(id="sjabloon/x", soort="connector", label="x", doel="x", model="geen", herkomst=bc.EIGEN,
                     bestand=("x",), versie="x")
    with pytest.raises(ValueError):
        bc.Onderdeel(id="route/x", soort="route", label="x", doel="x", model="geen", herkomst=bc.EIGEN,
                     bestand=("x",), versie="x", laag="workflow")


def test_nieuwe_specialist_en_connector_komen_mee_zonder_code(monkeypatch):
    nep = specialists.Specialist(system="nep", tools=frozenset({"get_artikel"}), doel="Een nep-specialist.")
    monkeypatch.setitem(specialists.SPECIALISTS, "nep", nep)
    voorbeeld = bm.CONNECTORS["kamerstukken"]
    nepc = dataclasses.replace(voorbeeld, naam="nepbron", label="Nepbron")
    monkeypatch.setitem(bm.CONNECTORS, "nepbron", nepc)
    monkeypatch.setattr(cat, "CONNECTORS", bm.CONNECTORS)
    cat.catalogus.cache_clear()
    try:
        ids = {o.id for o in cat.catalogus()}
        assert {"specialist/nep", "connector/nepbron"} <= ids
        assert cat.onderdeel("connector/nepbron").straat == "CONNECTOR_NEPBRON"
    finally:
        cat.catalogus.cache_clear()


def test_het_werkdocument_noemt_elke_soort():
    """`docs/architectuur/catalogus.md` heeft per soort een checklist voor het toevoegen; een nieuwe soort zonder
    checklist is een gat in de uitleg."""
    doc = (WORTEL / "docs" / "architectuur/catalogus.md").read_text().lower()
    for soort in bc.SOORTEN:
        assert re.search(rf"\*\*[^*\n]*\b{soort}\b[^*\n]*\*\*", doc), f"soort {soort} heeft geen checklist in catalogus.md"


def test_het_endpoint_geeft_de_lijst_zonder_inhoud_en_het_detail_met(monkeypatch):
    from fastapi.testclient import TestClient

    import api.main as main

    monkeypatch.setattr(main.settings, "qa_api_token", "", raising=False)
    monkeypatch.setattr(main.settings, "connector_kamerstukken", True, raising=False)
    monkeypatch.setattr(main.settings, "connector_rechtspraak", False, raising=False)
    client = TestClient(main.app)   # zonder `with`: de lifespan hoort niet bij deze lichte route
    r = client.get("/v1/catalogus")
    assert r.status_code == 200
    lijst = r.json()
    assert lijst["soorten"] == list(bc.SOORTEN)
    assert [o["id"] for o in lijst["onderdelen"]] == IDS
    assert all("inhoud" not in o for o in lijst["onderdelen"])
    per_id = {o["id"]: o for o in lijst["onderdelen"]}
    assert per_id["connector/kamerstukken"]["aan"] is True
    assert per_id["connector/rechtspraak"]["aan"] is False
    assert per_id["specialist/duiding"]["aan"] is True

    d = client.get("/v1/catalogus/rol/duiding").json()
    assert d["inhoud"]["secties"] and d["inhoud"]["secties"][0]["tekst"]
    assert "specialist/duiding" in d["gebruikt_door"]
    assert client.get("/v1/catalogus/rol/bestaat_niet").status_code == 404
