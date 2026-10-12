"""Wat de kennisgraaf over één knoop weet: gegroepeerd, ontdubbeld, letterlijk – en ruw als vangnet."""
import httpx
import pytest

from app import db, knoopinfo

IW = "urn:bwb:BWBR0004770"
A9 = f"{IW}:artikel:9"
BWB, ELI = knoopinfo.BWB, knoopinfo.ELI


def t(p, o, iri=False, naam="", functie=""):
    return {"p": p, "o": o, "isIri": "true" if iri else "false", "naam": naam, "functie": functie}


UIT = [
    t(knoopinfo.RDF_TYPE, BWB + "Artikel", iri=True), t(knoopinfo.RDF_TYPE, BWB + "Citeerbaar", iri=True),
    t(knoopinfo.RDF_TYPE, ELI + "LegalResource", iri=True),
    t(BWB + "inwerking", "2026-07-01"), t(BWB + "bron", "Stb.2022-330"), t(BWB + "effect", "wijziging"),
    t(BWB + "bronUrl", "https://wetten.overheid.nl/jci1.3:c:BWBR0004770&artikel=9", iri=True),
    t(knoopinfo.OWL_SAMEAS, "https://wetten.overheid.nl/jci1.3:c:BWBR0004770&artikel=9", iri=True),
    t(BWB + "verwijzingDoor", "urn:bwb:BWBR0002320", iri=True, naam="Algemene wet inzake rijksbelastingen"),
    t(BWB + "verwijzingDoor", "urn:bwb:BWBR0002320", iri=True, naam="Algemene wet inzake rijksbelastingen"),
    t(BWB + "verwijzingDoor", "urn:bwb:BWBR0047704", iri=True),
    t(BWB + "tekst", "De ontvanger vordert in."), t(BWB + "nummer", "9"),
    t(ELI + "has_part", f"{A9}:lid:1", iri=True, naam="Lid 1"),
]
REG = [t(BWB + "geldigVanaf", "2026-10-01"), t(BWB + "toestandUrl", "http://wetten.overheid.nl/id/BWBR0004770/2026-10-01/0", iri=True)]
INN = [{"o": "urn:bwb:BWBR0044722", "naam": "Uitvoeringsregeling Invorderingswet 2008"}]
VERW = [{"richting": "uit", "van": A9, "naar": f"{IW}:artikel:107", "anker": "artikel 107", "soort": "tekstueel",
         "doelSoort": "artikel", "betrouwbaarheid": "laag"}] * 2


def feiten(info):
    return {(g["naam"], f["eigenschap"]): f["waarden"] for g in info["groepen"] for f in g["feiten"]}


def test_groepen_namen_en_ontdubbeling():
    info = knoopinfo.knoop_info_uit(A9, UIT, INN, REG, VERW)
    f = feiten(info)
    assert [g["naam"] for g in info["groepen"]] == ["Geldigheid", "Herkomst van de tekst", "Grondslag en bevoegdheid", "Genoemd in", "Vindplaats"]
    assert f[("Geldigheid", "In werking")] == [{"tekst": "2026-07-01"}]
    # Van de regeling erboven: welke toestand je leest.
    assert f[("Geldigheid", "Toestand geldig vanaf")] == [{"tekst": "2026-10-01"}]
    assert f[("Geldigheid", "Toestand")][0]["link"].startswith("http://wetten.overheid.nl/id/")
    assert f[("Herkomst van de tekst", "Wijzigingspublicatie")] == [{"tekst": "Stb.2022-330"}]
    # Twee keer dezelfde regeling is één waarde; zonder naam blijft het BWB-id staan.
    assert f[("Genoemd in", "Genoemd in")] == [
        {"tekst": "Algemene wet inzake rijksbelastingen", "iri": "urn:bwb:BWBR0002320"},
        {"tekst": "BWBR0047704", "iri": "urn:bwb:BWBR0047704"}]
    # bronUrl en sameAs: één link.
    assert len(f[("Vindplaats", "Op wetten.overheid.nl")]) == 1
    # Type zonder Citeerbaar, compact.
    assert f[("Vindplaats", "Type in de graaf")] == [{"tekst": "bwb:Artikel"}, {"tekst": "eli:LegalResource"}]
    assert f[("Grondslag en bevoegdheid", "Berust hierop")] == [
        {"tekst": "Uitvoeringsregeling Invorderingswet 2008", "iri": "urn:bwb:BWBR0044722"}]


def test_tekst_en_structuur_niet_in_de_groepen_wel_ruw():
    info = knoopinfo.knoop_info_uit(A9, UIT, [], [], [])
    alle = [w["tekst"] for g in info["groepen"] for f in g["feiten"] for w in f["waarden"]]
    assert "De ontvanger vordert in." not in alle and "Lid 1" not in alle
    ruw = {(r["predicaat"], r["waarde"]) for r in info["ruw"]}
    assert ("bwb:tekst", "De ontvanger vordert in.") in ruw and ("eli:has_part", f"{A9}:lid:1") in ruw
    assert len(info["ruw"]) == len(UIT)


def test_een_regeling_houdt_haar_eigen_geldigheid():
    eigen = [t(BWB + "geldigVanaf", "2020-01-01"), t(BWB + "citeertitel", "Invorderingswet 1990"),
             t(BWB + "ondertekendDoor", "urn:bwb:ondertekenaar:x", iri=True, naam="A. Kosto", functie="Staatssecretaris")]
    f = feiten(knoopinfo.knoop_info_uit(IW, eigen, [], [t(BWB + "geldigVanaf", "2026-10-01")], []))
    assert f[("Geldigheid", "Toestand geldig vanaf")] == [{"tekst": "2020-01-01"}]
    assert f[("Regeling", "Citeertitel")] == [{"tekst": "Invorderingswet 1990"}]
    assert f[("Herkomst van de tekst", "Ondertekend door")][0]["tekst"] == "A. Kosto (Staatssecretaris)"


def test_verwijzingen_met_soort_en_betrouwbaarheid_ontdubbeld():
    info = knoopinfo.knoop_info_uit(A9, [], [], [], VERW)
    assert info["verwijzingen"] == [{"richting": "uit", "van": A9, "naar": f"{IW}:artikel:107", "anker": "artikel 107",
                                     "soort": "tekstueel", "doel_soort": "artikel", "doel_pad": "", "betrouwbaarheid": "laag"}]


def test_een_knoop_buiten_de_graaf_geeft_lege_groepen():
    info = knoopinfo.knoop_info_uit("urn:bwb:BWBR0002320:artikel:3", [], [], [], [])
    assert info["groepen"] == [] and info["ruw"] == [] and info["beschikbaar"]


@pytest.mark.parametrize("iri", ["", "urn:bwb:nee", A9 + "> } DROP ALL #", "http://example.org/x", f"{A9} x"])
async def test_ongeldige_iri_komt_geen_query_in(iri):
    with pytest.raises(ValueError):
        await knoopinfo.knoop_info(iri)


@pytest.fixture
async def route(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.config import get_settings
    from conftest import maak_testgebruikers
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("knoop-route")
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield lambda **p: client.get("/v1/annotatie/knoop", params=p, headers={"X-User-Id": "knoop-route"})
    get_settings.cache_clear()
    await db.dispose_engine()


async def test_de_route(route, monkeypatch):
    async def rijen(iri):
        return UIT, INN, REG, VERW
    monkeypatch.setattr(knoopinfo, "_rijen", rijen)
    r = await route(bron_iri=A9)
    assert r.status_code == 200 and r.json()["groepen"][0]["naam"] == "Geldigheid"
    assert (await route(bron_iri="urn:bwb:nee")).status_code == 422


async def test_de_route_zonder_graaf(route, monkeypatch):
    async def faalt(iri):
        raise httpx.ConnectError("weg")
    monkeypatch.setattr(knoopinfo, "_rijen", faalt)
    r = await route(bron_iri=A9)
    assert r.status_code == 503 and "tijdelijk niet beschikbaar" in r.json()["detail"]
