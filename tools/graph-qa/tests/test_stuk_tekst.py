"""De pagina van de tekst van een stuk (`agent/tools/stuk_tekst.py`), gedeeld door elke leestool van een connector."""
from __future__ import annotations

import json

from agent.resultaat import BUDGET
import pytest

from agent import tools
from agent.tools.stuk_tekst import INHOUD_ARG, MAX_BEGIN, MAX_INHOUD, aangevuld, begin_van, inhoud_van, inhoudpagina, tekstpagina


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


@pytest.mark.parametrize("tekst,begin,afgekapt", [
    ("De Wet wordt als volgt gewijzigd:", "De Wet wordt als volgt gewijzigd:", False),
    ("  twee   spaties ", "twee spaties", False),
    ("woord " * 40, ("woord " * 26).strip(), True),
])
def test_het_begin_van_een_alinea_is_letterlijk_en_eindigt_op_een_woordgrens(tekst, begin, afgekapt):
    stuk, af = begin_van(tekst)
    assert (stuk, af) == (begin, afgekapt) and len(stuk) <= MAX_BEGIN
    assert "…" not in stuk, "geen weglatingsteken: het begin is de bron, de vlag zegt dat er meer is"


def _verzamelwet(n: int) -> list[dict]:
    rijen = []
    for i in range(n):
        rijen.append({"nr": len(rijen) + 1, "kop": f"Artikel {i + 1}",
                      "tekst": f"In artikel {i}, eerste lid, van de Regeling nummer {i} met een lange naam wordt, onder "
                               "vervanging van de punt aan het slot door een puntkomma, een onderdeel toegevoegd:"})
        rijen += [{"nr": len(rijen) + 1, "kop": f"Artikel {i + 1} › A", "tekst": "x" * 200}]
    return rijen


MAX_INHOUD_PLUS = 45


def test_een_ingekorte_inhoud_wijst_naar_de_hele_inhoud():
    """Hermeting 11 nov 2026, B16: de eerste pagina noemde 11 van de 30 artikelen, zonder weg naar de rest."""
    rijen = _verzamelwet(30)
    d = _pagina(rijen)
    assert len(d["inhoud"]) == 30 and all("begint" not in i for i in d["inhoud"]), "eerst alle koppen, dan het begin"
    assert d["inhoud_zonder_begin"] and d["inhoud_openen"] == {"tool": "get_stuk", "args": {"id": "s1", "inhoud": True}}
    veel = _pagina(_verzamelwet(MAX_INHOUD_PLUS))
    assert veel["inhoud_ingekort"] and "inhoud_zonder_begin" not in veel and veel["inhoud_openen"]
    alles = json.loads(inhoudpagina(rijen, tool="get_stuk", args={"id": "s1"}, offset=0, stuk={"id": "s1"}))
    assert alles["volledig"] and "inhoud_openen" not in alles and [i["kop"] for i in alles["resultaten"]] == [f"Artikel {i + 1}" for i in range(30)]
    assert all(i["tekst"] == rijen[i["offset"]]["tekst"] and i["nr"] == rijen[i["offset"]]["nr"]
               for i in alles["resultaten"]), "de aanhef helemaal, als rij: te citeren"
    lang = [{"nr": 1, "kop": "Artikel 1", "tekst": "woord " * 400}, {"nr": 2, "kop": "Artikel 2", "tekst": "kort"}]
    eerste, tweede = json.loads(inhoudpagina(lang, tool="get_stuk", args={"id": "s1"}, offset=0,
                                             stuk={"id": "s1"}))["resultaten"]
    assert "tekst" not in eerste and eerste["begint_afgekapt"], "boven MAX_AANHEF alleen het begin"
    assert tweede == {"nr": 2, "kop": "Artikel 2", "offset": 1, "tekst": "kort"}


def test_een_gefilterde_lezing_draagt_de_inhoud_van_de_publicatie():
    rijen = _verzamelwet(3)
    d = json.loads(tekstpagina(rijen[2:4], tool="get_stuk", args={"id": "s1", "artikel": "2"}, offset=0,
                               stuk={"id": "s1"}, publicatie=rijen))
    assert "inhoud" not in d, "de koppen van de gefilterde rijen wijzen nergens heen"
    assert [i["offset"] for i in d["inhoud_publicatie"] if " › " not in i["kop"]] == [0, 2, 4]
    leeg = json.loads(tekstpagina([], tool="get_stuk", args={"id": "s1"}, offset=0, stuk={"id": "s1"}, publicatie=rijen))
    assert leeg["stuk"].get("leesbaar") is not False, "een filter zonder treffer maakt het stuk niet onleesbaar"


@pytest.mark.parametrize("naam", ["get_kamerstuk", "get_bekendmaking", "get_uitspraak"])
def test_elke_leestool_leest_de_inhoud_apart(naam):
    schema = next(t for t in tools.TOOLS if t["name"] == naam)["input_schema"]
    assert schema["properties"]["inhoud"] is INHOUD_ARG


def test_een_inhoud_die_met_het_begin_past_heeft_geen_verwijzing():
    rijen = [{"nr": 1, "kop": "Artikel I", "tekst": "De Wet wordt als volgt gewijzigd:"},
             {"nr": 2, "kop": "Artikel II", "tekst": "Dit besluit treedt in werking."}]
    d = json.loads(tekstpagina(rijen, tool="get_stuk", args={"id": "s1"}, offset=0, stuk={"id": "s1"}))
    assert "inhoud_openen" not in d and "inhoud_zonder_begin" not in d


def test_de_inhoud_van_een_stuk_zonder_koppen_zegt_dat_en_wijst_naar_de_tekst():
    """Ronde 1 Kamerstukken (11 nov 2026, K07/K16): een leeg resultaat las als "geen tekst", en het model bladerde."""
    rijen = [{"nr": 1, "tekst": "Een alinea."}, {"nr": 2, "tekst": "Nog een."}, {"nr": 3, "soort": "voetnoot", "tekst": "n"}]
    d = json.loads(inhoudpagina(rijen, tool="get_stuk", args={"id": "s1"}, offset=0, stuk={"id": "s1"}))
    assert d["resultaten"] == [] and d["volledig"] and d["zonder_koppen"] is True and d["alineas"] == 2
    assert d["lezen"] == {"tool": "get_stuk", "args": {"id": "s1", "offset": 0}}
    assert d["stuk"].get("leesbaar") is not False and "2 alinea’s" in d["toelichting"]
    leeg = json.loads(inhoudpagina([], tool="get_stuk", args={"id": "s1"}, offset=0, stuk={"id": "s1"}))
    assert leeg["stuk"]["leesbaar"] is False and "zonder_koppen" not in leeg


def test_de_inhoud_neemt_het_diepste_niveau_dat_past_ook_onder_het_tweede():
    """Een begroting heeft vijf niveaus; niveau 3 past (ronde 2 Kamerstukken, K15: kst-36200-IX-2 kreeg de zeven koppen
    van niveau 2, en het model zocht "Artikel 1 Belastingen" met vijf offsets)."""
    rijen = []
    for d in "AB":
        for h in range(1, 5):
            for a in range(1, 5):
                for p in range(1, 4):  # niveau 4: 2·4·4·3 = 96 koppen, te veel
                    rijen.append({"nr": len(rijen) + 1, "kop": f"{d} › {h}. Hoofdstuk › Artikel {h}.{a} › §{p}",
                                  "tekst": "Een alinea."})
    lijst, ingekort, _ = inhoud_van(rijen)
    assert not ingekort and len(lijst) == 32 <= MAX_INHOUD
    assert {k["kop"].count(" › ") for k in lijst} == {2}, "niveau 3, niet niveau 2"
    assert lijst[5] == {"kop": "A › 2. Hoofdstuk › Artikel 2.2", "offset": 15}
