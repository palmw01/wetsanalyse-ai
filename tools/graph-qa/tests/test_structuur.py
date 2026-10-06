"""De inhoudsopgave als boom: documentvolgorde, bereiken, hele niveaus, en altijd een ingang voor de rest.

De oude tool gaf de Invorderingswet als ~20k tekens TSV op IRI-volgorde (artikel 1, 10, 11 … 2), die op
8000 tekens werd afgeknipt; het model vulde de gaten met "…". `tests/fixtures/inhoudsopgave_iw.json`
is de echte uitvoer van `queries.inhoudsopgave` voor de IW (153 rijen, gemeten op 7 okt 2026).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.graph.structuur import inhoudsopgave_resultaat, natuurlijke_sleutel
from agent.resultaat import BUDGET

IW = "BWBR0004770"
_RIJEN_IW = json.loads((Path(__file__).parent / "fixtures" / "inhoudsopgave_iw.json").read_text(encoding="utf-8"))


def _iw(rijen=_RIJEN_IW, **kw) -> dict:
    return json.loads(inhoudsopgave_resultaat(rijen, bwb_id=IW, wortel=f"urn:bwb:{IW}", args={"bwb_id": IW},
                                              query_diepte=4, **kw))


def test_de_hele_iw_past_volledig_en_in_documentvolgorde():
    data = _iw()
    assert data["volledig"] is True and "vervolg" not in data
    assert data["telling"] == {"Hoofdstuk": 12, "Afdeling": 8, "Artikel": 133}
    hoofdstukken = [r["nummer"] for r in data["resultaten"] if r.get("soort") == "Hoofdstuk"]
    assert hoofdstukken == ["I", "II", "III", "IV", "V", "VI", "VII", "VIIa", "VIIbis", "VIII", "IX", "X"]
    # Elk artikel staat erin, met zijn eigen nummer: de nummerreeksen dekken alle 133.
    nummers = [n for r in data["resultaten"] if "nummers" in r for n in r["nummers"].split(", ")]
    assert len(nummers) == len(set(nummers)) == 133
    assert sum(r["bepalingen"] for r in data["resultaten"] if "nummers" in r) == 133


def test_de_lexicale_invoervolgorde_maakt_niet_uit():
    # De query sorteert op IRI; de boom volgt bwb:volgtOp. Omgekeerde invoer, zelfde uitkomst.
    assert _iw(list(reversed(_RIJEN_IW)))["resultaten"] == _iw()["resultaten"]


def test_nummerreeksen_volgen_de_keten_niet_de_nummers():
    rijen = _iw()["resultaten"]
    afdeling1_vi = rijen.index({"niveau": 2, "soort": "Afdeling", "nummer": "1", "titel": "Aansprakelijkheid"})
    reeks = rijen[afdeling1_vi + 1]
    assert reeks["nummers"].startswith("32, 33, 33a, 34") and reeks["nummers"].endswith("48, 48a")
    assert reeks["bepalingen"] == 32
    # Hoofdstuk V begint bij 27quinquies (de keten), niet bij 27a (de nummervolgorde); hoofdstuk VII
    # heeft 62, 62bis, 62a – zo staat het in de wet.
    nummers = " | ".join(r["nummers"] for r in rijen if "nummers" in r)
    assert "27quinquies, 27a, 28" in nummers and "62, 62bis, 62a, 63" in nummers


def test_een_gat_in_de_nummering_blijft_zichtbaar():
    w = f"urn:bwb:{IW}"
    rijen = [{"niveau": "1", "ouder": w, "deel": f"{w}:artikel:{n}", "soort": "Artikel", "nummer": n,
              "volgtOp": f"{w}:artikel:{v}" if v else ""} for n, v in (("32", ""), ("33", "32"), ("35", "33"))]
    data = _iw(rijen)
    assert data["resultaten"] == [{"niveau": 1, "soort": "Artikel", "nummers": "32, 33, 35", "bepalingen": 3}]


def test_past_het_niet_dan_hele_niveaus_met_een_ingang_per_ingeklapt_deel():
    data = _iw(budget=3300)
    assert data["volledig"] is True, "ingeklapt is verdieping, geen onvolledigheid"
    ingeklapt = [r for r in data["resultaten"] if "openen" in r]
    assert ingeklapt, "iets moet ingeklapt zijn bij deze begroting"
    for r in ingeklapt:
        assert r["openen"]["tool"] == "inhoudsopgave" and r["openen"]["args"]["bwb_id"] == IW
        assert r["openen"]["args"]["vanaf"].startswith(f"urn:bwb:{IW}:hoofdstuk:") and r["onderdelen"] >= 1
    # Nooit een half niveau: alle twaalf hoofdstukken staan er.
    assert len([r for r in data["resultaten"] if r.get("soort") == "Hoofdstuk"]) == 12


def _leidraadvorm(n: int = 800) -> list[dict]:
    """Zoals de Leidraad: honderden divisies op het bovenste niveau, elk met een eigen titel."""
    w = "urn:bwb:BWBR0024096"
    return [{"niveau": "1", "ouder": w, "deel": f"{w}:artikel:{i}", "soort": "Divisie", "nummer": str(i),
             "titel": f"Titel van bepaling {i} over een onderwerp uit de invordering",
             "volgtOp": f"{w}:artikel:{i - 1}" if i > 1 else ""} for i in range(1, n + 1)]


def test_een_te_breed_bovenste_niveau_wordt_gepagineerd_zonder_gat_of_overlap():
    rijen, w = _leidraadvorm(), "urn:bwb:BWBR0024096"
    gezien, offset = [], 0
    for _ in range(100):
        data = json.loads(inhoudsopgave_resultaat(rijen, bwb_id="BWBR0024096", wortel=w,
                                                  args={"bwb_id": "BWBR0024096"}, query_diepte=4, offset=offset))
        assert len(json.dumps(data, ensure_ascii=False, separators=(",", ":"))) <= BUDGET
        gezien += [r["nummer"] for r in data["resultaten"]]
        if data["volledig"]:
            break
        offset = data["vervolg"]["args"]["offset"]
        assert data["vervolg"]["tool"] == "inhoudsopgave"
    assert gezien == [str(i) for i in range(1, 801)]


def test_een_deel_op_de_diepste_laag_zonder_onderdelen_is_ingeklapt_niet_leeg():
    w = "urn:bwb:BWBR0005537"
    rijen = [
        {"niveau": "1", "ouder": w, "deel": f"{w}:hoofdstuk:1", "soort": "Hoofdstuk", "nummer": "1", "titel": "H"},
        {"niveau": "2", "ouder": f"{w}:hoofdstuk:1", "deel": f"{w}:hoofdstuk:1:titeldeel:1.1", "soort": "Titeldeel", "nummer": "1.1"},
    ]
    data = json.loads(inhoudsopgave_resultaat(rijen, bwb_id="BWBR0005537", wortel=w, args={"bwb_id": "BWBR0005537"},
                                              query_diepte=2))
    titeldeel = data["resultaten"][1]
    assert titeldeel["openen"]["args"]["vanaf"] == f"{w}:hoofdstuk:1:titeldeel:1.1"
    assert titeldeel["onderdelen"] == "niet opgehaald"


@pytest.mark.parametrize(("a", "b"), [("II", "IV"), ("IV", "IX"), ("VII", "VIIa"), ("9", "10"), ("27", "27a"),
                                      ("10.2", "10.10"), ("3:40", "3:100")])
def test_natuurlijke_volgorde(a: str, b: str):
    assert natuurlijke_sleutel(a) < natuurlijke_sleutel(b)
