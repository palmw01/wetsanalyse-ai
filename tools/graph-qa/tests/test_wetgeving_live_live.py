"""De live-proef van de bronconnector Wetgeving buiten de kennisgraaf (ADR-013, fase 1e): het contract met de echte dienst.

De suite draait tegen opgenomen antwoorden (`test_wetgeving_tools.py`). Deze proef toetst wat de connector van de
zoekdienst van de BWB en het repository van KOOP aanneemt – de indexen (`afkorting`, `titel`, `geldigheidsdatum`,
`authority`, `rechtsgebied`, sorteren op `dcterms.modified`), de recordvorm (`locatie_toestand` op het repository, de
geldigheids- en zichtperiode), en dat de lezer van de importer een actuele toestand volledig leest – zonder graaf, model of
secrets, en kost niets. Hij draait niet in de poort maar dagelijks in `bronnenwacht.yml`; lokaal met
`BRONNEN_LIVE=1 uv run pytest -m live tests/test_wetgeving_live_live.py`.

**De drifttoets.** Voor een regeling die óók in de graaf staat (de Iw 1990) leest de connector de toestand die de importer
nu zou importeren, met dezelfde lezer: de dekking moet boven de drempel van de importer liggen. Zo valt een wijziging in de
XML die de lezer niet kent hier op, en niet pas bij een jurist.

Een storing van de dienst is iets anders dan een veranderd contract: na één herhaling falen de tests met
`DIENST ONBEREIKBAAR` vooraan.
"""
from __future__ import annotations

import os
import time

import pytest

from agent.adapters.sru_bwb import REPOSITORY_HOST, BwbFout, SruBwb
from bronmodel.bwb.dekking import STANDAARD_DREMPEL

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("BRONNEN_LIVE"), reason="live: zet BRONNEN_LIVE=1"),
]

PW, IW = "BWBR0015703", "BWBR0004770"
#: Boek 7 BW: een wettekst die één `<boek>` is, met `sub-paragraaf` (de lezer leest erdoorheen).
BW7 = "BWBR0005290"


@pytest.fixture(scope="module")
def bron() -> SruBwb:
    return SruBwb()


def _met_herhaling(doe):
    fout: Exception | None = None
    for poging in range(2):
        try:
            return doe()
        except BwbFout as exc:
            if exc.code != "onbereikbaar":
                raise
            fout = exc
        if poging == 0:
            time.sleep(5)
    pytest.fail(f"DIENST ONBEREIKBAAR: {fout}")


def test_de_indexen_bestaan_en_filteren(bron: SruBwb):
    vandaag = time.strftime("%Y-%m-%d")
    for cql in (f'overheidbwb.afkorting="Wlz" and overheidbwb.geldigheidsdatum={vandaag}',
                f'overheidbwb.titel adj "Participatiewet" and overheidbwb.geldigheidsdatum={vandaag}',
                f'overheid.authority="Financiën" and overheidbwb.geldigheidsdatum={vandaag} and dcterms.type="wet"',
                f'overheidbwb.rechtsgebied="Belastingrecht" and overheidbwb.geldigheidsdatum={vandaag} '
                "sortBy dcterms.modified/sort.descending"):
        totaal, rijen = _met_herhaling(lambda q=cql: bron.zoek(q, maximum=5))
        assert totaal > 0 and rijen, cql
    _, gesorteerd = _met_herhaling(lambda: bron.zoek(
        f'overheidbwb.rechtsgebied="Belastingrecht" and overheidbwb.geldigheidsdatum={vandaag} '
        "sortBy dcterms.modified/sort.descending", maximum=10))
    datums = [t.gewijzigd for t in gesorteerd]
    assert datums == sorted(datums, reverse=True), "sortBy op dcterms.modified werkt niet meer"


def test_een_afkorting_vindt_de_wet(bron: SruBwb):
    _, rijen = _met_herhaling(lambda: bron.zoek(
        f'overheidbwb.afkorting="Wlz" and overheidbwb.geldigheidsdatum={time.strftime("%Y-%m-%d")}', maximum=5))
    assert any(t.titel == "Wet langdurige zorg" for t in rijen)


def test_de_recordvorm_en_de_toestand_op_peildatum(bron: SruBwb):
    t = _met_herhaling(lambda: bron.toestand_op(PW, "2015-01-15"))
    assert t.geldig_vanaf <= "2015-01-15" <= t.geldig_tot and t.zicht_vanaf
    assert REPOSITORY_HOST in t.xml_url and t.versie.startswith("2015-01-01_")
    alle = _met_herhaling(lambda: bron.toestanden(PW))
    assert len(alle) > 100 and alle == sorted(alle, key=lambda x: (x.geldig_vanaf, x.zicht_vanaf, x.versie))


def test_de_lezer_van_de_importer_leest_een_actuele_toestand_volledig(bron: SruBwb):
    for bwb in (PW, IW, BW7):
        g = _met_herhaling(lambda b=bwb: bron.lees(bron.toestand_op(b)))
        assert g.dekking >= STANDAARD_DREMPEL and not g.wet.overgeslagen, (bwb, g.dekking, g.wet.overgeslagen)
        assert g.xsd_geldig, f"{bwb}: de toestand valideert niet meer tegen de XSD van de importer"
