"""WP-D: de SPARQL-bouwers produceren de juiste patronen en valideren invoer."""
from __future__ import annotations

import pytest

from agent.graph import queries as q


def test_fts_gebruikt_lucene_en_limit():
    sparql = q.fts("invordering AND belasting", 5)
    assert "inst:bwb_tekst" in sparql
    assert 'luc:query "invordering AND belasting"' in sparql
    assert "LIMIT 5" in sparql


def test_fts_limit_wordt_begrensd():
    assert "LIMIT 50" in q.fts("x", 999)
    assert "LIMIT 1" in q.fts("x", 0)


def test_list_regelingen_filtert_eigen_iri_ruimte():
    sparql = q.list_regelingen()
    assert "a bwb:Regeling" in sparql
    assert 'STRSTARTS(STR(?regeling), "urn:bwb:")' in sparql


def test_get_artikel_bouwt_iri_en_leden():
    sparql = q.get_artikel("BWBR0004770", "9")
    assert "<urn:bwb:BWBR0004770:artikel:9>" in sparql
    assert "bwb:heeftLid" in sparql


def test_get_lid_iri():
    assert "<urn:bwb:BWBR0004770:artikel:9:lid:1>" in q.get_lid("BWBR0004770", "9", "1")


def test_get_lid_levert_de_onderdelen_mee():
    """Een definitielid is zonder zijn onderdelen leeg.

    Artikel 2 lid 1 IW 1990 heeft als eigen tekst alleen "Deze wet verstaat onder:"; de definities
    (a t/m t, waaronder 'belastingschuldige') zitten in de onderdelen. Kwamen die niet mee, dan ging
    de agent het met raw_sparql-pogingen compenseren – acht beurten voor één definitievraag.
    """
    sparql = q.get_lid("BWBR0004770", "2", "1")
    # Het predicaat moet bestaan in de graaf. Dit stond op `bwb:bevat`, en dat schrijft de importer
    # nergens (hij schrijft HEEFT_ONDERDEEL → `bwb:heeftOnderdeel`), dus de subquery matchte nooit
    # iets en deze tool leverde nooit één onderdeel. Dat kon blijven bestaan omdat deze test alleen
    # de querytékst las: "staat het woord erin" is geen bewijs dat er data uitkomt. De echte guard
    # daarvoor is `tests/test_artikel_onderdelen.py`, dat een graafantwoord naspeelt.
    assert "bwb:heeftOnderdeel+" in sparql, "onderdelen hangen aan heeftOnderdeel, en genest"
    assert "bwb:bevat" not in sparql, "bwb:bevat bestaat niet in deze graaf"
    assert "GROUP_CONCAT" in sparql, "gebundeld, anders herhaalt de lidtekst per onderdeel"
    assert "ORDER BY ?o" in sparql, "volgorde a, b, c, … moet vastliggen"
    assert "bwb:jci ?oj" in sparql, "elk onderdeel krijgt zijn eigen vindplaats"
    assert 'STRBEFORE(?oj, "&z=")' in sparql, "zonder de datumstaart; die staat al in de lid-jci"


def test_get_artikel_levert_directe_onderdelen_mee():
    """Artikelen zonder leden hebben hun opsomming direct onder het artikel (heeftOnderdeel)."""
    sparql = q.get_artikel("BWBR0019237", "9a")
    assert "bwb:heeftOnderdeel" in sparql
    assert "bwb:heeftLid" in sparql, "de leden blijven ook meekomen"


def test_verwijzingen_met_en_zonder_lid():
    met = q.follow_verwijzingen("BWBR0004770", "9", "1")
    assert ":artikel:9:lid:1>" in met and "bwb:heeftVerwijzing" in met
    zonder = q.follow_verwijzingen("BWBR0004770", "9")
    assert ":artikel:9>" in zonder and ":lid:" not in zonder


def test_referenced_by_gebruikt_verwijzingdoor():
    assert "bwb:verwijzingDoor" in q.referenced_by("BWBR0004770", "9")


def test_count_by_type():
    sparql = q.count_by_type()
    assert "COUNT(DISTINCT ?s)" in sparql
    assert "STRSTARTS" in sparql


def test_context_subgraaf_dekt_alle_relaties():
    """De inbedding loopt over de ECHTE bevat-predicaten, niet over `bwb:bevat`.

    Deze test eiste tot 4 sep 2026 `"bwb:bevat" in sparql` – en dat predicaat bestaat niet. De tak
    "4-bevat-door" matchte dus nooit iets: de tool die "context" heet leverde alles behálve de
    structurele inbedding, en de test bevestigde de bug in plaats van hem te vangen. Precies wat er
    bij `get_lid` gebeurde. `tests/test_predicaat_dekking.py` vangt deze klasse fout nu breed.
    """
    sparql = q.context("BWBR0004770", "9")
    # node zelf + structuur + leden + uit-/ingaande verwijzingen in één query
    assert "<urn:bwb:BWBR0004770:artikel:9>" in sparql
    assert "bwb:bevat" not in sparql, "bwb:bevat bestaat niet in deze graaf"
    assert "bwb:heeftHoofdstuk" in sparql and "bwb:heeftAfdeling" in sparql
    assert "bwb:heeftLid" in sparql
    assert "bwb:heeftVerwijzing" in sparql
    assert "bwb:verwijzingDoor" in sparql
    assert "bwb:verwijstNaar" in sparql, "inkomende verwijzingen op bepalingniveau"
    assert "bwb:volgtOp" in sparql, "de buren in het document"
    assert "6-verwijst-naar-uit-lid" in sparql, (
        "verwijzingen hangen aan het lid; alleen de node zelf bevragen meldt er nul"
    )
    assert "UNION" in sparql


def test_context_lid_gebruikt_lid_iri_maar_verwijzingdoor_op_artikel():
    sparql = q.context("BWBR0004770", "9", "1")
    assert ":artikel:9:lid:1>" in sparql          # node = het lid
    # `verwijzingDoor` legt de redactie op ARTIKELniveau, dus die tak draait op ?art – en ?art is
    # bij een lid expliciet het artikel, niet de node. Sinds `node_patroon` is dat een BIND en geen
    # ingebakken IRI meer, want een divisie heeft geen artikel-IRI.
    assert "BIND(<urn:bwb:BWBR0004770:artikel:9> AS ?art)" in sparql
    assert "?art bwb:verwijzingDoor" in sparql


def test_resolve_begrip_escapet_term():
    # Een aanhalingsteken in de term mag de query niet breken.
    sparql = q.resolve_begrip('dwang"bevel')
    assert '\\"' in sparql
    assert "skos:prefLabel" in sparql


@pytest.mark.parametrize("bad", ["DROP", "BWBR", "', DELETE", "0004770"])
def test_ongeldig_bwb_id_wordt_geweigerd(bad):
    with pytest.raises(ValueError):
        q.get_regeling_info(bad)


@pytest.mark.parametrize("bad", ["9; DROP", "../x", "9 9"])
def test_ongeldig_artikel_wordt_geweigerd(bad):
    with pytest.raises(ValueError):
        q.get_artikel("BWBR0004770", bad)


# ---------------------------------------------------------------------------
# Artikelnummers met een dubbele punt (Algemene wet bestuursrecht)
# ---------------------------------------------------------------------------

def test_artikelnummer_met_dubbele_punt_wordt_aanvaard_en_gecodeerd():
    """De Awb nummert haar artikelen "3:40", "5:2", "8:36f" — en dat is geen randgeval.

    Gemeten in de graaf op 5 sep 2026: 570 van de 572 Awb-artikelen dragen een dubbele punt, oftewel
    49% van alle 1162 artikelen. `_ART_RE` weigerde die vorm, waardoor de hele wet wel doorzoekbaar
    was maar niet op te halen en niet te annoteren; twee eval-cases liepen erop vast met nul
    markeringen.

    De codering is de andere helft van de fix. De importer schrijft elk IRI-segment met
    `quote(s, safe="")`, dus de graaf heeft `…:artikel:5%3A2`. Deze module plakte de IRI met een
    f-string aaneen en maakte `…:artikel:5:2` — een andere node, en dus nul resultaten zonder
    foutmelding. De dubbele punt is bovendien het scheidingsteken van de URN zelf.
    """
    assert q.artikel_iri("BWBR0005537", "5:2") == "urn:bwb:BWBR0005537:artikel:5%3A2"
    assert q.lid_iri("BWBR0005537", "5:2", "1") == "urn:bwb:BWBR0005537:artikel:5%3A2:lid:1"
    assert q.artikel_iri("BWBR0005537", "8:36f") == "urn:bwb:BWBR0005537:artikel:8%3A36f"


def test_gewone_artikelnummers_veranderen_niet():
    """De codering mag geen enkele bestaande IRI verschuiven – anders wijst alles opeens naast."""
    assert q.artikel_iri("BWBR0004770", "9") == "urn:bwb:BWBR0004770:artikel:9"
    assert q.artikel_iri("BWBR0004770", "22a") == "urn:bwb:BWBR0004770:artikel:22a"
    assert q.lid_iri("BWBR0004770", "9", "1") == "urn:bwb:BWBR0004770:artikel:9:lid:1"


def test_de_twee_nummervormen_blijven_gescheiden():
    """Een decimaal divisienummer is iets anders dan een artikelnummer; ze mogen niet vervagen.

    `25.1` moet het divisie-pad kiezen (nummer-match binnen de regeling), `5:2` het artikel-pad
    (directe IRI). Zou `_nummer_vrij` de dubbele punt gaan accepteren, dan zou een Awb-artikel via
    de trage nummer-match lopen en bij ambiguïteit de verkeerde node kunnen raken.
    """
    assert q.is_artikelnummer("5:2") is True
    assert q.is_artikelnummer("25.1") is False
    with pytest.raises(ValueError):
        q._nummer_vrij("5:2")
    for ongeldig in (":", "5:", ":2", "a", "5::2"):
        with pytest.raises(ValueError):
            q._art(ongeldig)
