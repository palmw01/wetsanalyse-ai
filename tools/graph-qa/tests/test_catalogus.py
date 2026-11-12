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
from agent.llm_stap import Rol
from agent.models import ACTIE_TAAK, BRONSELECTIE_ACTIES, INTAKE_ACTIES, REGIE_ACTIES, Actie
from agent.tools import _BY_NAME
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
    assert _ids("methode") == set(PAKKET["skills"])
    assert _ids("agent") == set(AGENTS)
    assert _ids("tool") == set(_BY_NAME)
    assert _ids("controle") == {m.CONTROLE["naam"] for m in cat._controlemodules()}


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
    """Elke broncode van een methode staat in het bronregister van díe skill."""
    for o in ALLE:
        if o.soort == "methode":
            register = (WORTEL / PAKKET["skills"][o.naam]["map"] / "references/bronnen.md").read_text()
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


# --- samenwerking (ADR-014 §7) ----------------------------------------------------------------------------------------

PER_ID = {o.id: o for o in ALLE}


@pytest.mark.parametrize("o", ALLE, ids=IDS)
def test_wie_wat_mag_gebruiken(o: bc.Onderdeel):
    """`hangt_af_van` volgt de aanroepregels per concept: een skill gebruikt niets, een workflow nooit een agent, een
    ingang precies één workflow of agent. Een tool gebruikt alleen een tool als hij een connector is (een bundel)."""
    for d in o.hangt_af_van:
        doel = PER_ID[d]
        assert doel.concept in bc.MAG_GEBRUIKEN[o.concept], f"{o.id} ({o.concept}) mag {d} ({doel.concept}) niet gebruiken"
        if o.concept == "tool":
            assert o.soort == "connector" and doel.soort == "tool", f"{o.id}: alleen een connector bundelt tools"


@pytest.mark.parametrize("o", ALLE, ids=IDS)
def test_het_model_past_bij_het_concept(o: bc.Onderdeel):
    assert o.model in bc.MAG_MODEL[o.concept], f"{o.id}: model {o.model} past niet bij {o.concept}"


def test_een_strict_stap_noemt_de_rol_die_hem_draagt():
    rollen = {r.naam for r in Rol}
    for o in ALLE:
        for s in o.stappen:
            if s.model == "strict":
                assert s.rol in rollen, f"{o.id}, stap {s.naam}: strict zonder bestaande llm_stap.Rol"
            else:
                assert s.rol is None


def test_een_tool_hoort_bij_hoogstens_een_connector():
    for t in _ids("tool"):
        bundels = [o.id for o in ALLE if o.soort == "connector" and bc.oid("tool", t) in o.hangt_af_van]
        assert len(bundels) <= 1, f"{t} zit in {bundels}"


def test_elke_actie_is_de_ingang_van_precies_een_onderdeel():
    """Een klik op een suggestie, en dus een commando, kiest zonder model precies één onderdeel."""
    for actie in (*ACTIE_TAAK, *BRONSELECTIE_ACTIES, *INTAKE_ACTIES, *REGIE_ACTIES):
        doelen = [o.id for o in ALLE if o.concept in ("agent", "workflow") and actie in o.ingang]
        assert len(doelen) == 1, f"actie {actie} wijst naar {doelen}"


def test_elke_controle_staat_naast_zijn_code():
    for m in cat._controlemodules():
        assert set(m.CONTROLE) == {"naam", "label", "doel", "moment", "tests"}, m.__name__


def test_een_deel_hoort_bij_een_geheel_van_hetzelfde_concept():
    for o in ALLE:
        if o.deel_van:
            assert PER_ID[o.deel_van].concept == o.concept, o.id


def test_een_agent_zonder_modelstap_is_een_workflow():
    assert PER_ID["agent/annotatie"].concept == "workflow"
    assert PER_ID["agent/begrippen"].concept == "agent"


# --- de routeringstabel (ADR-010, ADR-014 §7) -------------------------------------------------------------------------

def _los_op(pad: str):
    import importlib
    module, naam = pad.split(":")
    return getattr(importlib.import_module(module), naam)


#: Wat `supervisie.py` importeert met een herkennersnaam maar geen route kiest: de stand van een open kaartje.
NIET_ROUTE = {"is_open", "is_aanvullen"}


def test_elke_route_bestaat_en_kiest_een_onderdeel():
    from agent.routes import ROUTES
    assert len({r.naam for r in ROUTES}) == len(ROUTES)
    for r in ROUTES:
        assert callable(_los_op(r.herkenner)), r.herkenner
        assert PER_ID[r.doel].concept in ("workflow", "agent"), f"route {r.naam} kiest {r.doel}"
        assert PER_ID[bc.oid("route", r.naam)].hangt_af_van == (r.doel,)


def test_de_routeringstabel_en_supervisie_zijn_gelijk():
    """Elke herkenner in de tabel wordt in `supervisie.py` gebruikt, en elke herkenner die `supervisie.py` importeert
    of definieert staat in de tabel. Een nieuwe vaste weg zonder rij, of een rij zonder weg, wordt rood."""
    import ast
    import inspect

    from agent.nodes import supervisie
    from agent.routes import ROUTES

    bron = inspect.getsource(supervisie)
    boom = ast.parse(bron)
    geimporteerd = {(a.asname or a.name): f"{n.module}:{a.name}" for n in ast.walk(boom)
                    if isinstance(n, ast.ImportFrom) and n.module for a in n.names}
    herkenners = {naam for naam in geimporteerd if re.match(r"(is_|lees_|wijst_|_heeft_)", naam)} - NIET_ROUTE
    helpers = {"_lijst", "_bron_uit", "_te_lezen", "_doorvraag", "_buiten_graaf_melding"}
    in_tabel = set()
    for r in ROUTES:
        module, naam = r.herkenner.split(":")
        lokaal = next((k for k, v in geimporteerd.items()
                       if v.split(":")[1] == naam and v.split(":")[0].split(".")[-1] == module.split(".")[-1]), naam)
        assert re.search(rf"\b{re.escape(lokaal)}\(", bron), f"route {r.naam}: {lokaal} wordt in supervisie niet aangeroepen"
        in_tabel.add(lokaal)
    assert herkenners | helpers <= in_tabel, f"herkenners zonder route: {sorted((herkenners | helpers) - in_tabel)}"


# --- commando's (#1276, ADR-014 §7) -----------------------------------------------------------------------------------

def test_elk_commando_wijst_naar_precies_een_onderdeel():
    """Een `/commando` is een suggestie uit `frontend/lib/vraagLex.ts`: met een `actie` wijst hij via die actie naar
    precies één workflow of agent; met een `doel` (annoteren) naar de route die een aangewezen bepaling annoteert; met
    `invullen` zet hij alleen een vraag klaar, die langs de supervisor gaat. De clientcommando's (`/nieuw`, `/bron`, `/help`) zijn bediening van de werkplek en vallen erbuiten."""
    bron = (WORTEL / "frontend" / "lib/vraagLex.ts").read_text()
    regels = [r for r in bron.splitlines() if "commando: {" in r]
    assert regels, "geen commando's gevonden in vraagLex.ts"
    for r in regels:
        naam = re.search(r'commando: \{ naam: "([a-z-]+)"', r)[1]
        if actie := re.search(r'actie: "([a-z_]+)"', r):
            doelen = [o.id for o in ALLE if o.concept in ("agent", "workflow") and actie[1] in o.ingang]
            assert len(doelen) == 1, f"/{naam} (actie {actie[1]}) wijst naar {doelen}"
        elif "invullen: true" in r:
            continue   # zet alleen een vraag klaar die de jurist afmaakt: die gaat langs de supervisor
        else:
            assert re.search(r"\bdoel\b", r), f"/{naam}: geen actie, doel of invullen"
            assert PER_ID["route/annotatie_doel"].hangt_af_van == ("workflow/annotatieketen",)
