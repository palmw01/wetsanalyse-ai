"""De live-proef van de bronconnector Rechtspraak (ADR-013): het contract met LiDO en de open data van de Rechtspraak.

De suite draait tegen een nep (`test_rechtspraak_tools.py`). Een nep bevestigt niet wat de connector van de echte
diensten aanneemt: dat `get-id` een versie van een artikel vindt (via de ref, en via de jci met een toestanddatum),
dat de links aan een versie hangen en oudere versies er meer hebben, de vorm van `get-links`, en de vorm van een
uitspraak bij de Rechtspraak. Deze proef toetst dat, zonder graaf, model of secrets, en kost niets. De vaste gevallen
komen uit de spike van 10 nov 2026 (`docs/architectuur/metingen/lido-spike-2026-11-10/`).

Hij draait niet in de poort: dan hangt elke PR af van overheid.nl. Dagelijks draait hij in
`.github/workflows/bronnenwacht.yml`; lokaal met `BRONNEN_LIVE=1 uv run pytest -m live`.

Een storing van een dienst is iets anders dan een veranderd contract. Is een dienst onbereikbaar, dan falen de tests
met `DIENST ONBEREIKBAAR` vooraan; anders zegt de melding welk deel van het contract brak.
"""
from __future__ import annotations

import json
import os

import pytest

from agent import tools
from agent.adapters.lido_rechtspraak import LidoRechtspraak, RechtspraakFout, begindatum
from agent.config import Settings
from agent.tools.rechtspraak_tools import lees

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("BRONNEN_LIVE"), reason="live: zet BRONNEN_LIVE=1"),
]

AAN = Settings(connector_rechtspraak=True)
IW = "BWBR0004770"
AWB = "BWBR0005537"
#: Art. 9 Iw (label-id 2910654): de huidige versie noemt een handvol uitspraken, de versie van 2016 meer dan honderd.
ART9_JCI = "jci1.3:c:BWBR0004770&hoofdstuk=II&artikel=9&z=2026-10-01&g=2026-10-01"
#: Awb art. 8:7: de ref-route geeft niets, de jci-route wel.
AWB_87_JCI = "jci1.3:c:BWBR0005537&hoofdstuk=8&titeldeel=8.1&afdeling=8.1.1&artikel=8:7&z=2026-07-01&g=2026-07-01"
#: Een arrest dat LiDO aan art. 9 Iw koppelt, en dat de Rechtspraak met tekst publiceert.
HR = "ECLI:NL:HR:2022:50"


def _of_storing(doe):
    try:
        return doe()
    except RechtspraakFout as exc:
        if exc.code == "onbereikbaar":
            pytest.fail(f"DIENST ONBEREIKBAAR: {exc}")
        raise


@pytest.fixture(scope="module")
def bron():
    b = LidoRechtspraak()
    yield b
    b.close()


def test_de_versies_van_een_artikel_hangen_aan_haar_label_id(bron):
    k = _of_storing(lambda: bron.koppelingen(IW, "9", ART9_JCI))
    assert k.route == "ref", "de ref-route vond de huidige versie niet meer"
    assert len(k.versies) >= 3, f"LiDO kende maar {len(k.versies)} versies van art. 9 Iw"
    assert all("/BWBR0004770/2910654/" in v for v in k.versies), "de label-id van LiDO is niet die van de BWB"
    assert [begindatum(v) for v in k.versies] == sorted((begindatum(v) for v in k.versies), reverse=True)


def test_oudere_versies_dragen_de_meeste_uitspraken(bron):
    k = _of_storing(lambda: bron.koppelingen(IW, "9", ART9_JCI))
    per_versie: dict[str, set[str]] = {}
    for ln in k.links:
        per_versie.setdefault(ln.versie, set()).add(ln.ecli)
    alle = set().union(*per_versie.values())
    assert len(alle) >= 100, f"over alle versies maar {len(alle)} uitspraken"
    assert len(per_versie.get(k.versies[0], set())) < len(alle), "samenvoegen over versies voegt niets meer toe"
    assert HR in alle, f"{HR} hangt niet meer aan art. 9 Iw"
    assert not k.onvolledig, f"versies kwamen niet volledig binnen: {k.onvolledig}"


def test_de_titel_draagt_instantie_datum_en_zaaknummer(bron):
    k = _of_storing(lambda: bron.koppelingen(IW, "9", ART9_JCI))
    titel = next(ln.titel for ln in k.links if ln.ecli == HR and ln.titel)
    assert titel.startswith(f"{HR} - Hoge Raad, 21-01-2022 / "), f"de vorm van de titel veranderde: {titel}"


def test_zonder_ref_vindt_de_jci_de_versies(bron):
    """De Awb: `juriconnect-ref` geeft niets (ook niet zonder dubbele punt), de jci met een toestanddatum wel."""
    k = _of_storing(lambda: bron.koppelingen(AWB, "8:7", AWB_87_JCI))
    assert k.route == "jci", f"route {k.route!r}: werkt de ref nu wel voor de Awb? Dan kan de jci-route weg"
    assert k.versies and k.links, "de jci-route vond geen versies of geen uitspraken bij Awb art. 8:7"


def test_een_uitspraak_heeft_metadata_en_alineas(bron):
    doc = _of_storing(lambda: bron.document(HR))
    meta, rijen = lees(doc.xml)
    assert meta.get("identifier") == HR
    assert meta.get("date") == "2022-01-21" and meta.get("creator") == "Hoge Raad", meta
    assert meta.get("type") == "Uitspraak"
    assert rijen and rijen[0]["kop"] == "Inhoudsindicatie" and any(r["kop"] == "Uitspraak" for r in rijen)
    assert any("Invorderingswet" in r["tekst"] for r in rijen), "de tekst noemt de wet niet meer"


def test_de_metadata_alleen_draagt_dezelfde_wijzigingsdatum(bron):
    """De versiecontrole van de cache vraagt `return=META` en vergelijkt `dcterms:modified` met het document."""
    from agent.adapters.lido_rechtspraak import RECHTSPRAAK_URL, _gewijzigd
    doc = _of_storing(lambda: bron.document(HR))
    meta = _of_storing(lambda: bron._get(RECHTSPRAAK_URL, id=HR, **{"return": "META"}))
    assert "<uitspraak" not in meta, "return=META gaf de hele uitspraak"
    assert _gewijzigd(meta) and _gewijzigd(meta) == doc.gewijzigd


def test_een_onbekende_ecli_is_niet_gevonden(bron):
    with pytest.raises(RechtspraakFout) as exc:
        bron.document("ECLI:NL:HR:1900:1")
    assert exc.value.code in {"niet_gevonden", "geweigerd"}, exc.value


def test_de_leestool_tegen_de_echte_dienst():
    uit = json.loads(tools.dispatch("get_uitspraak", None, {"id": HR}, AAN))
    assert uit["status"] == "ok", uit
    assert uit["stuk"]["datum"] == "2022-01-21" and uit["stuk"]["bron_hash"]
    assert uit["resultaten"] and all("iri" not in r for r in uit["resultaten"])
