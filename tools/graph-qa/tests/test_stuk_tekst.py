"""De pagina van de tekst van een stuk (`agent/tools/stuk_tekst.py`), gedeeld door elke leestool van een connector."""
from __future__ import annotations

import json

from agent.resultaat import BUDGET
from agent.tools.stuk_tekst import aangevuld, tekstpagina


def _rijen(n: int, lengte: int, secties: int = 2) -> list[dict]:
    return [{"nr": i + 1, "kop": f"Uitspraak › {i * secties // n + 1} Een lange sectietitel die zich herhaalt",
             "tekst": f"Alinea {i + 1} " + "x" * lengte} for i in range(n)]


def _pagina(rijen: list[dict], offset: int = 0) -> dict:
    return json.loads(tekstpagina(rijen, tool="get_stuk", args={"id": "s1"}, offset=offset, stuk={"id": "s1"}))


def test_de_kop_staat_alleen_waar_hij_verandert_en_de_lezer_vult_hem_aan():
    rijen = _rijen(6, 20)
    d = _pagina(rijen)
    assert [("kop" in r) for r in d["resultaten"]] == [True, False, False, True, False, False]
    assert d["zonder_herhaling"] == ["kop"]
    assert [r["kop"] for r in aangevuld(d)] == [r["kop"] for r in rijen]


def test_een_volgende_pagina_begint_met_de_kop():
    rijen = _rijen(60, 300, secties=1)
    eerste = _pagina(rijen)
    assert not eerste["volledig"]
    tweede = _pagina(rijen, offset=eerste["vervolg"]["args"]["offset"])
    assert tweede["resultaten"][0]["kop"] == rijen[0]["kop"]
    assert all("kop" not in r for r in tweede["resultaten"][1:])


def test_een_rij_zonder_kop_na_een_kop_laat_de_kop_staan():
    """Anders gaf aanvullen de rij zonder kop de kop van de rij ervoor."""
    rijen = [{"nr": 1, "kop": "A", "tekst": "een"}, {"nr": 2, "tekst": "twee"}, {"nr": 3, "kop": "A", "tekst": "drie"}]
    d = _pagina(rijen)
    assert "zonder_herhaling" not in d and [r.get("kop") for r in d["resultaten"]] == ["A", None, "A"]
    assert [r.get("kop") for r in aangevuld(d)] == ["A", None, "A"]


def test_zonder_inhoud_op_een_pagina_als_het_stuk_dan_helemaal_past():
    """Eén pagina scheelt het model een ronde (derde meting 10 nov 2026: de rest van de uitspraak, 72k in plaats van
    47k); de koppen staan dan al in de rijen."""
    def met_lengte(lengte: int) -> list[dict]:
        return [{"nr": i + 1, "kop": f"Uitspraak › {i + 1} Sectie", "tekst": "x" * lengte} for i in range(12)]
    # Zoek een omvang die alleen zonder inhoud op één pagina past.
    for lengte in range(400, 700, 5):
        d = _pagina(met_lengte(lengte))
        if "inhoud" not in d:
            break
    assert d["volledig"] and "inhoud" not in d and len(json.dumps(d, ensure_ascii=False)) <= BUDGET
    kort = _pagina(met_lengte(100))
    assert kort["volledig"] and kort["inhoud"], "past het mét inhoud, dan blijft de inhoud"
    lang = _pagina(met_lengte(1500))
    assert not lang["volledig"] and lang["inhoud"], "past het niet, dan wijst de inhoud de weg"


def test_een_stuk_zonder_tekst_is_niet_leesbaar():
    d = _pagina([])
    assert d["stuk"]["leesbaar"] is False and d["resultaten"] == []


def test_een_passage_midden_in_een_sectie_krijgt_haar_kop_in_het_blok_extern():
    from agent.sjablonen.extern import blokken
    rijen = _rijen(6, 20)
    pagina = tekstpagina(rijen, tool="get_uitspraak", args={"id": "ECLI:NL:HR:2022:50"}, offset=0,
                         stuk={"id": "ECLI:NL:HR:2022:50", "label": "Hoge Raad 21 januari 2022, ECLI:NL:HR:2022:50",
                               "bron_hash": "h"})
    [blok] = blokken([{"id": "ECLI:NL:HR:2022:50", "van_nr": 2, "tot_nr": 3}], [("get_uitspraak", pagina)])
    assert [p.kop for p in blok.passages] == [rijen[1]["kop"], rijen[2]["kop"]]
