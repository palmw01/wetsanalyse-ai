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

from agent import catalogus as cat
from agent import specialists
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
