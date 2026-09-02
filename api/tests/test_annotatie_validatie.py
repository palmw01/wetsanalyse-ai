"""De invarianten die de api zelf afdwingt vóór hij een annotatie vastlegt.

Tot 2 sep 2026 toetste de api bij het opslaan alleen de JAS-klasse en een leeg fragment; de samenhang
tussen een fragment en zijn anker leunde volledig op de aanleverende partij. Deze tests leggen vast
wat de api daar nu zélf van vindt — zie `app/annotatie_validatie` voor het waarom.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.annotatie_contracts import Anker, ElementInvoer
from app.annotatie_validatie import bronversies, controleer_element

BASIS = "/v1/annotatie/documenten"


def _el(tekst: str, klasse: str = "Rechtssubject", lid: str = "1", **anker) -> ElementInvoer:
    return ElementInvoer(
        klasse=klasse, tekst=tekst, lid=lid,
        anker=Anker(**anker) if anker else None,
    )


# --- de invarianten als pure functie ---------------------------------------------------------------

def test_de_operator_en_met_een_anker_van_83_tekens():
    """De echte casus, live gezien op 1 sep 2026 vóór de fix aan de agentkant.

    De patcher verving `tekst` door een korter fragment zonder het anker bij te werken. Omdat
    `bron_hash` klopte gebruikte de werkplek die offsets rechtstreeks en lichtte 83 tekens op waar
    er twee gemarkeerd waren. De api nam dat klakkeloos aan.
    """
    kapot = _el("en", klasse="Operator", start=120, eind=203, bron_hash="a1b2c3d4")
    assert controleer_element(kapot) == "anker_dekt_fragment_niet"


def test_een_kloppend_anker_gaat_gewoon_door():
    goed = _el("de belastingschuldige", start=4, eind=25, bron_hash="a1b2c3d4")
    assert controleer_element(goed) == ""


def test_een_element_zonder_anker_is_toegestaan():
    """`_anker_voor` in de agent geeft bewust None als lokaliseren niet lukt.

    "Een ontbrekend anker is zichtbaar in de werkplek, een fout anker niet." Dat hier alsnog fataal
    maken zou brongetrouwe tekst weggooien wegens een plaatsbepaling die niet scherp te krijgen was.
    """
    assert controleer_element(_el("de ontvanger")) == ""


@pytest.mark.parametrize("start,eind", [(-1, 5), (10, 10), (10, 4)])
def test_onzinnige_offsets(start, eind):
    assert controleer_element(_el("abc", start=start, eind=eind)) == "anker_offsets_ongeldig"


def test_een_anker_dat_in_een_ander_lid_wijst():
    """In de agent zijn lid en anker sinds `_lokaliseer` één beslissing; uiteenlopen betekent dat
    er iets tussen zit dat ze los heeft getrokken, en dan weten we niet welke van de twee klopt."""
    el = ElementInvoer(klasse="Rechtssubject", tekst="de ontvanger", lid="1",
                       anker=Anker(lid="2", start=0, eind=12, bron_hash="x"))
    assert controleer_element(el) == "anker_lid_wijkt_af"


def test_een_leeg_lid_aan_een_van_beide_kanten_is_geen_conflict():
    """Alleen een echte tegenspraak telt; niet ingevuld is geen claim."""
    el = ElementInvoer(klasse="Rechtssubject", tekst="de ontvanger", lid="",
                       anker=Anker(lid="2", start=0, eind=12, bron_hash="x"))
    assert controleer_element(el) == ""


def test_de_klasse_en_het_lege_fragment_blijven_gelden():
    assert controleer_element(_el("de ontvanger", klasse="Verzonnenklasse")) == "ongeldige_klasse"
    assert controleer_element(_el("   ")) == "leeg_fragment"


# --- de brontekstversies van een document ----------------------------------------------------------

def test_bronversies_telt_alleen_echte_hashes():
    elementen = [
        _el("a", start=0, eind=1, bron_hash="aaa"),
        _el("b", start=1, eind=2, bron_hash="aaa"),
        _el("c"),                                        # geen anker
        _el("d", start=2, eind=3, bron_hash=""),         # anker zonder hash
    ]
    assert bronversies(elementen) == ["aaa"]


def test_twee_bronversies_worden_allebei_gemeld():
    elementen = [
        _el("a", start=0, eind=1, bron_hash="aaa"),
        _el("b", start=1, eind=2, bron_hash="bbb"),
    ]
    assert bronversies(elementen) == ["aaa", "bbb"]


def test_zonder_ankers_geen_versies():
    assert bronversies([_el("a"), _el("b")]) == []


# --- langs de echte endpoints ----------------------------------------------------------------------

@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    from app import db, ratelimit
    from app.config import get_settings
    from app.deps import get_annotatie_store
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    get_annotatie_store.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await maak_testgebruikers("gebruiker-a")

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"X-User-Id": "gebruiker-a"}) as ac:
        yield ac


async def _doc(client) -> str:
    r = await client.post(BASIS, json={"bwbId": "BWBR0004770", "artikel": "9", "lid": "1"})
    return r.json()["slug"]


async def test_een_kapot_anker_wordt_verworpen_en_geteld(client):
    """Verwerpen, niet 422: één kapot element mag de rest van de ronde niet meeslepen."""
    slug = await _doc(client)
    r = await client.put(f"{BASIS}/{slug}/elementen", json={"ronde": 1, "elementen": [
        {"id": "goed", "klasse": "Rechtssubject", "tekst": "de ontvanger", "lid": "1",
         "anker": {"lid": "1", "start": 0, "eind": 12, "bron_hash": "aaa"}},
        {"id": "kapot", "klasse": "Operator", "tekst": "en", "lid": "1",
         "anker": {"lid": "1", "start": 120, "eind": 203, "bron_hash": "aaa"}},
    ]})
    assert r.status_code == 200
    assert r.headers.get("X-Verworpen") == "1"
    assert [e["id"] for e in r.json()["elementen"]] == ["goed"]

    # Wát er sneuvelde staat in het spoor, niet alleen hoevéél.
    audit = (await client.get(f"{BASIS}/{slug}/audit")).json()
    regel = next(a for a in audit if a["actie"] == "elementen-voorgesteld")
    assert regel["detail"]["afgekeurd"][0]["reden"] == "anker_dekt_fragment_niet"


async def test_een_document_met_een_bronversie_meldt_niets(client):
    slug = await _doc(client)
    r = await client.put(f"{BASIS}/{slug}/elementen", json={"ronde": 1, "elementen": [
        {"id": "a", "klasse": "Rechtssubject", "tekst": "de ontvanger", "lid": "1",
         "anker": {"lid": "1", "start": 0, "eind": 12, "bron_hash": "aaa"}},
    ]})
    assert r.json()["bronversies"] == ["aaa"]
    audit = (await client.get(f"{BASIS}/{slug}/audit")).json()
    assert not [a for a in audit if a["actie"] == "bronversie-conflict"]


async def test_een_tweede_bronversie_wordt_gemarkeerd_niet_geweigerd(client):
    """De importer draait wekelijks en overheid.nl verandert; dat is geen fout van de indiener.

    Dit gebeurt in het echt doordat een BEVROREN element (de jurist besliste erover) zijn oude anker
    houdt terwijl de agent na een herimport verse ankers maakt — vandaar dat beide hashes in dezelfde
    ronde langskomen. Een PUT is de volledige uitkomst van één ronde en trekt weggelaten
    agent-elementen in, dus twee losse rondes zouden het oude element juist opruimen.
    """
    slug = await _doc(client)
    r = await client.put(f"{BASIS}/{slug}/elementen", json={"ronde": 1, "elementen": [
        {"id": "oud", "klasse": "Rechtssubject", "tekst": "de ontvanger", "lid": "1",
         "anker": {"lid": "1", "start": 0, "eind": 12, "bron_hash": "aaa"}},
        {"id": "nieuw", "klasse": "Voorwaarde", "tekst": "indien hij verzoekt", "lid": "1",
         "anker": {"lid": "1", "start": 30, "eind": 49, "bron_hash": "bbb"}},
    ]})
    assert r.status_code == 200
    assert "X-Verworpen" not in r.headers          # niets verworpen
    assert r.json()["bronversies"] == ["aaa", "bbb"]
    assert len(r.json()["elementen"]) == 2         # beide blijven staan

    audit = (await client.get(f"{BASIS}/{slug}/audit")).json()
    conflict = next(a for a in audit if a["actie"] == "bronversie-conflict")
    assert conflict["detail"]["bronversies"] == ["aaa", "bbb"]


async def test_een_eigen_markering_met_kapot_anker_geeft_de_jurist_een_melding(client):
    """Hier wél een 422: er is één element en de indiener is een mens die het meteen moet horen."""
    slug = await _doc(client)
    r = await client.post(f"{BASIS}/{slug}/elementen", json={
        "klasse": "Rechtssubject", "tekst": "de ontvanger", "lid": "1",
        "anker": {"lid": "1", "start": 0, "eind": 99, "bron_hash": "aaa"},
    })
    assert r.status_code == 422
    assert "selectie" in r.json()["detail"].lower()


async def test_een_edit_die_het_anker_niet_meeneemt_wordt_geweigerd(client):
    """Kort de jurist een fragment in zonder dat het anker meeschuift, dan wijst het naar meer tekst
    dan hij markeerde – precies het defect dat de patcher aan de agentkant maakte."""
    slug = await _doc(client)
    await client.put(f"{BASIS}/{slug}/elementen", json={"ronde": 1, "elementen": [
        {"id": "a", "klasse": "Rechtssubject", "tekst": "de ontvanger", "lid": "1",
         "anker": {"lid": "1", "start": 0, "eind": 12, "bron_hash": "aaa"}},
    ]})
    r = await client.post(f"{BASIS}/{slug}/elementen/a/beslissing", json={
        "type": "edit",
        "wijziging": {"tekst": "ontvanger",
                      "anker": {"lid": "1", "start": 0, "eind": 12, "bron_hash": "aaa"}},
    })
    assert r.status_code == 422

    # En met een anker dat wél meeschuift gaat het gewoon door.
    ok = await client.post(f"{BASIS}/{slug}/elementen/a/beslissing", json={
        "type": "edit",
        "wijziging": {"tekst": "ontvanger",
                      "anker": {"lid": "1", "start": 3, "eind": 12, "bron_hash": "aaa"}},
    })
    assert ok.status_code == 200
