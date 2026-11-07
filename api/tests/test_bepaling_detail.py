"""Het detail van een bepaling voor het paneel naast het gesprek: alles uit de graaf, niets geraden (ADR-008)."""
import httpx
import pytest

from app import bepaling_detail, db
from app.bepaling_graaf_contract import MAX_VOORBEELDEN, BepalingDetail

BWB = bepaling_detail.BWB
IW = "urn:bwb:BWBR0004770"
A36 = f"{IW}:artikel:36"
LIDR = "urn:bwb:BWBR0024096"


def t(p, o, iri=False, naam=""):
    return {"p": BWB + p, "o": o, "isIri": "true" if iri else "false", "naam": naam}


UIT = [
    t("status", "goed"), t("inwerking", "2010-07-04"), t("bron", "Stb.2009-610"), t("vindplaats", "Artikel 36"),
    t("grondslagVoor", "urn:bwb:BWBR0004772", iri=True, naam="Uitvoeringsbesluit Invorderingswet 1990"),
    t("grondslagVoor", "urn:bwb:BWBR0004772", iri=True, naam="Uitvoeringsbesluit Invorderingswet 1990"),
    *[t("bevoegdheidVoor", f"urn:bwb:BWBR00471{n:02d}", iri=True, naam=f"Regeling {n}") for n in range(12)],
    t("verwijzingDoor", "urn:bwb:BWBR0030850", iri=True, naam="Leidraad X"),
    t("definieertBegrip", "bestuurder"),
]
REG = [{"p": BWB + "geldigVanaf", "o": "2026-10-01"}, {"p": BWB + "toestandUrl", "o": "http://wetten.overheid.nl/id/BWBR0004770/2026-10-01/0"}]
VERW = [
    {"richting": "uit", "van": f"{A36}:lid:8", "naar": "urn:bwb:BWBR0005291:artikel:45", "anker": "Artikel 45, leden 4 en 5, van Boek 3 van het Burgerlijk Wetboek",
     "vanLabel": "Artikel 36, lid 8", "naarInGraaf": "false"},
    {"richting": "uit", "van": f"{A36}:lid:1", "naar": "urn:bwb:BWBR0007168:artikel:1", "anker": "artikel 1 van de Wet belastingen op milieugrondslag",
     "vanLabel": "Artikel 36, lid 1", "naarInGraaf": "true"},
    {"richting": "uit", "van": f"{A36}:lid:1", "naar": "urn:bwb:BWBR0007168:artikel:1", "anker": "artikel 1 van de Wet belastingen op milieugrondslag",
     "vanLabel": "Artikel 36, lid 1", "naarInGraaf": "true"},
    {"richting": "in", "van": f"{LIDR}:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.8", "naar": A36, "vanLabel": "Artikel 36.8"},
    {"richting": "in", "van": f"{IW}:artikel:56:lid:1", "naar": A36, "vanLabel": "Artikel 56, lid 1"},
    {"richting": "in", "van": f"{IW}:artikel:56:lid:1", "naar": f"{A36}:lid:2", "vanLabel": "Artikel 56, lid 1"},
    {"richting": "in", "van": f"{A36}:lid:5", "naar": f"{A36}:lid:1", "vanLabel": "Artikel 36, lid 5"},
]
PLAATS = {"bron_iri": A36, "regeling": {"bwb_id": "BWBR0004770"}, "pad": [
    {"iri": f"{IW}:hoofdstuk:VI", "type": "Hoofdstuk", "nummer": "VI", "label": "Hoofdstuk VI"},
    {"iri": f"{IW}:hoofdstuk:VI:afdeling:1", "type": "Afdeling", "nummer": "1", "label": "Afdeling 1"},
    {"iri": A36, "type": "Artikel", "nummer": "36", "label": "Artikel 36"}]}
TITELS = {f"{IW}:hoofdstuk:VI": "Aansprakelijkheid"}
CITEER = {"BWBR0004770": "Invorderingswet 1990", "BWBR0024096": "Leidraad Invordering 2008", "BWBR0007168": "Wet belastingen op milieugrondslag"}


def detail(**over) -> BepalingDetail:
    args = {"uit": UIT, "reg": REG, "verw": VERW, "plaats": PLAATS, "titels": TITELS, "citeertitels": CITEER} | over
    return bepaling_detail.detail_uit(A36, **args)


def test_plaats_en_geldigheid_komen_letterlijk_uit_de_graaf():
    d = detail()
    assert [(p.soort, p.nummer, p.titel) for p in d.plaats] == [("hoofdstuk", "VI", "Aansprakelijkheid"), ("afdeling", "1", "")]
    assert (d.status, d.inwerking, d.gewijzigd_bij, d.geldig_vanaf) == ("goed", "2010-07-04", "Stb.2009-610", "2026-10-01")
    assert d.vindplaats.label == "Artikel 36" and d.vindplaats.regeling == "Invorderingswet 1990"
    assert d.definieert == ["bestuurder"] and d.beschikbaar


def test_uitgaande_verwijzingen_staan_een_keer_met_hun_anker_en_zeggen_of_het_doel_er_is():
    d = detail()
    assert [(v.van.label, v.naar.label, v.in_graaf) for v in d.verwijst_naar] == [
        ("Artikel 36, lid 1", "Artikel 1", True), ("Artikel 36, lid 8", "Artikel 45", False)]
    assert d.verwijst_naar[0].naar.regeling == "Wet belastingen op milieugrondslag"
    assert d.verwijst_naar[1].anker.startswith("Artikel 45, leden 4 en 5")


def test_verwezen_door_telt_bepalingen_eigen_regeling_eerst_en_niet_zichzelf():
    d = detail()
    assert d.verwezen_door.aantal == 2  # lid 5 van artikel 36 zelf telt niet, artikel 56 lid 1 één keer
    assert [(v.label, v.regeling) for v in d.verwezen_door.items] == [
        ("Artikel 56, lid 1", "Invorderingswet 1990"), ("Artikel 36.8", "Leidraad Invordering 2008")]


def test_een_telling_noemt_het_aantal_en_hoogstens_tien_voorbeelden():
    d = detail()
    assert d.bevoegdheid_voor.aantal == 12 and len(d.bevoegdheid_voor.items) == MAX_VOORBEELDEN
    assert d.grondslag_voor.aantal == 1 and d.grondslag_voor.items[0].label == "Uitvoeringsbesluit Invorderingswet 1990"
    assert d.genoemd_in.aantal == 1


def test_wat_de_graaf_niet_heeft_blijft_leeg():
    d = detail(uit=[], reg=[], verw=[], plaats={}, titels={})
    assert d.plaats == [] and d.inwerking is None and d.status == "" and d.geldig_vanaf is None
    assert d.verwijst_naar == [] and d.verwezen_door.aantal == 0 and d.beschikbaar


def test_het_contract_weigert_onbekende_velden():
    with pytest.raises(ValueError):
        BepalingDetail(bron_iri=A36, vindplaats={"iri": A36, "label": "Artikel 36"}, onbekend=1)


@pytest.mark.parametrize("iri", ["", "urn:bwb:nee", A36 + "> } DROP ALL #", "http://example.org/x"])
async def test_ongeldige_iri_komt_geen_query_in(iri):
    with pytest.raises(ValueError):
        await bepaling_detail.bepaling_detail(iri)


async def test_een_haperende_graaf_is_niet_beschikbaar_nooit_leeg(monkeypatch):
    async def faalt(client, query):
        raise httpx.ConnectError("weg")
    monkeypatch.setattr(bepaling_detail, "sparql_select", faalt)
    d = await bepaling_detail.bepaling_detail(A36)
    assert d.beschikbaar is False and d.vindplaats.label == "Artikel 36"


@pytest.fixture
async def route(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.config import get_settings
    from conftest import maak_testgebruikers
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("bepaling-route")
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield lambda **p: client.get("/v1/annotatie/bepaling", params=p, headers={"X-User-Id": "bepaling-route"})
    get_settings.cache_clear()
    await db.dispose_engine()


async def test_de_route(route, monkeypatch):
    async def nep(iri):
        return detail()
    monkeypatch.setattr(bepaling_detail, "bepaling_detail", nep)
    r = await route(bron_iri=A36)
    assert r.status_code == 200 and r.json()["inwerking"] == "2010-07-04" and r.json()["schema_versie"] == 1


async def test_de_route_weigert_een_ongeldige_iri(route):
    assert (await route(bron_iri="urn:bwb:nee")).status_code == 422
