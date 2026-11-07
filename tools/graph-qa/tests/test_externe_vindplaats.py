"""ADR-013: vindplaatsen buiten de wettekst (Kamerstukken, bekendmakingen, uitspraken, EU-recht).

Een externe bron is citeerbaar met haar eigen officiële identifier. Ze is een bron, maar geen wettekst:
`vindplaats` blijft over de BWB gaan, `extern` draagt de rest.
"""
from __future__ import annotations

import pytest

from bronmodel.extern import BRONTYPEN, externe_verwijzingen, externe_vindplaats
from bronmodel.vindplaats import vindplaats

from agent.grounding import check_grounding, curate_sources
from agent.models import Source
from agent.provenance import citations_in, collect_sources

VECTOREN = [
    # (verwijzing, brontype, id, label)
    ("kst-36123-3", "kamerstuk", "kst-36123-3", "Kamerstukken 36123, nr. 3"),
    ("kst-36200-VII-2", "kamerstuk", "kst-36200-VII-2", "Kamerstukken 36200 VII, nr. 2"),
    ("h-tk-20232024-12-3", "kamerstuk", "h-tk-20232024-12-3", "Handelingen II 2023/24, nr. 12, item 3"),
    ("ah-ek-20232024-5", "kamerstuk", "ah-ek-20232024-5", "Aanhangsel Handelingen I 2023/24, nr. 5"),
    ("stb-2023-123", "bekendmaking", "stb-2023-123", "Stb. 2023, 123"),
    ("stcrt-2023-12345", "bekendmaking", "stcrt-2023-12345", "Stcrt. 2023, 12345"),
    ("ECLI:NL:HR:2020:1234", "uitspraak", "ECLI:NL:HR:2020:1234", "ECLI:NL:HR:2020:1234"),
    ("ecli:nl:rvs:2021:567", "uitspraak", "ECLI:NL:RVS:2021:567", "ECLI:NL:RVS:2021:567"),
    ("ECLI:EU:C:2019:123", "uitspraak", "ECLI:EU:C:2019:123", "ECLI:EU:C:2019:123"),
    ("CELEX:32016R0679", "eu", "CELEX:32016R0679", "Verordening (EU) 2016/679"),
    ("celex:32019L1024", "eu", "CELEX:32019L1024", "Richtlijn (EU) 2019/1024"),
    ("https://data.europa.eu/eli/reg/2016/679/oj", "eu", "http://data.europa.eu/eli/reg/2016/679/oj",
     "Verordening 2016/679"),
]


@pytest.mark.parametrize("ref,brontype,ident,label", VECTOREN)
def test_externe_vindplaats(ref, brontype, ident, label):
    vp = externe_vindplaats(ref)
    assert vp is not None and (vp.brontype, vp.id, vp.label) == (brontype, ident, label)
    assert vp.brontype in BRONTYPEN
    # Een externe identifier is nooit een BWB-vindplaats, en omgekeerd.
    assert vindplaats(ref) is None


@pytest.mark.parametrize("ref", ["BWBR0004770", "jci1.3:c:BWBR0004770&artikel=9", "kst-", "12345",
                                 "32016R0679", "ECLI:NL", "mkst-36123-3", "urn:bwb:BWBR0004770:artikel:9"])
def test_geen_externe_vindplaats(ref):
    assert externe_vindplaats(ref) is None


def test_wettekst_is_het_brontype_van_de_bwb():
    assert vindplaats("BWBR0004770").brontype == "wettekst"


def test_publieke_links():
    assert externe_vindplaats("kst-36123-3").uri == "https://zoek.officielebekendmakingen.nl/kst-36123-3"
    assert externe_vindplaats("ECLI:NL:HR:2020:1234").uri.startswith("https://deeplink.rechtspraak.nl/")
    assert externe_vindplaats("ECLI:EU:C:2019:123").uri == ""
    assert externe_vindplaats("CELEX:32016R0679").uri.startswith("https://eur-lex.europa.eu/")


def test_verwijzingen_in_tekst_ontdubbeld_en_zonder_leestekens():
    tekst = "Zie kst-36123-3 en ECLI:NL:HR:2020:1234. Ook (CELEX:32016R0679), en weer kst-36123-3."
    assert [v.id for v in externe_verwijzingen(tekst)] == [
        "kst-36123-3", "ECLI:NL:HR:2020:1234", "CELEX:32016R0679"]


def test_externe_bron_uit_toolresultaat():
    bronnen = collect_sources([("get_kamerstuk", "MvT bij kst-36123-3, p. 4"),
                               ("get_artikel", "<urn:bwb:BWBR0004770:artikel:9>")])
    kst = next(b for b in bronnen if b.uri == "kst-36123-3")
    assert (kst.brontype, kst.label, kst.link, kst.bwb_id) == (
        "kamerstuk", "Kamerstukken 36123, nr. 3", "https://zoek.officielebekendmakingen.nl/kst-36123-3", None)
    iw = next(b for b in bronnen if b.uri == "urn:bwb:BWBR0004770:artikel:9")
    assert iw.brontype is None  # wettekst, zoals voorheen


def test_label_uit_toolrij_wint():
    rij = '{"status": "ok", "volledig": true, "aantal": 1, "resultaten": [{"id": "kst-36123-3", "label": "Memorie van toelichting"}]}'
    [bron] = collect_sources([("get_kamerstuk", rij)])
    assert bron.label == "Memorie van toelichting"


def test_externe_id_in_antwoord_telt_als_citatie():
    assert "ECLI:NL:HR:2020:1234" in citations_in("Zo oordeelde de Hoge Raad (ECLI:NL:HR:2020:1234).")


def test_opgehaalde_uitspraak_is_gegrond():
    rapport = check_grounding("Zie ECLI:NL:HR:2020:1234.", [("get_uitspraak", "ecli:nl:hr:2020:1234 tekst")])
    assert rapport.grounded and rapport.unsupported == []


def test_verzonnen_kamerstuk_is_ongegrond():
    rapport = check_grounding("Volgens kst-36123-3 is dat zo.", [("get_kamerstuk", "kst-36123-4")])
    assert not rapport.grounded and rapport.unsupported == ["kst-36123-3"]
    assert rapport.niveau == "ongegrond"


def test_celex_of_eli_van_dezelfde_handeling_blijven_twee_ids():
    # Bewust: CELEX en ELI zijn verschillende identifiers; de tool die de tekst levert noemt de vorm die
    # het antwoord mag citeren.
    rapport = check_grounding("Zie CELEX:32016R0679.", [("get_eu", "http://data.europa.eu/eli/reg/2016/679/oj")])
    assert rapport.unsupported == ["CELEX:32016R0679"]


def test_curate_houdt_genoemde_externe_bron():
    iw = Source(label="Artikel 9", uri="urn:bwb:BWBR0004770:artikel:9")
    kst = Source(label="Kamerstukken 36123, nr. 3", uri="kst-36123-3", brontype="kamerstuk")
    ander = Source(label="Kamerstukken 1, nr. 1", uri="kst-1-1", brontype="kamerstuk")
    uit = curate_sources([iw, kst, ander], "Art. 9 (BWBR0004770); zie de MvT, kst-36123-3.")
    assert [s.uri for s in uit] == [iw.uri, kst.uri]


def test_curate_zonder_regeling_laat_alles_staan():
    kst = Source(label="Kamerstukken 36123, nr. 3", uri="kst-36123-3", brontype="kamerstuk")
    assert curate_sources([kst], "Een antwoord zonder vindplaats.") == [kst]
