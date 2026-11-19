"""Het diagram rond een centrale klasse (deelactiviteit 2c): buurt, keuze van de diagrammen, ontbrekende rollen en layout."""
from __future__ import annotations

import json

import pytest

from app import diagram
from app.config import PROJECT_ROOT

PAD = PROJECT_ROOT / "frontend" / "lib" / "graaf" / "diagram.vectoren.json"


def _kant(sleutel: str, klassen: dict) -> dict:
    soort, id_ = sleutel.split(":", 1)
    return {"soort": soort, "id": id_, "klasse": klassen.get(id_, "Rechtssubject"), "tekst": id_}


def _relaties(geval: dict) -> list[dict]:
    return [{"id": f"R{i}", "type": t, "lifecycle": lc, "van": _kant(v, geval["klassen"]), "naar": _kant(n, geval["klassen"])}
            for i, (v, n, t, lc) in enumerate(geval["relaties"])]


@pytest.mark.skipif(not PAD.exists(), reason="de vectoren staan in de frontend; niet in het image")
def test_de_buurt_is_gelijk_aan_die_van_de_werkplek():
    VECTOREN = json.loads(PAD.read_text())
    assert VECTOREN["diepte"] == diagram.DIEPTE
    for g in VECTOREN["gevallen"]:
        assert sorted(diagram.buurt(g["centraal"], _relaties(g))) == g["buurt"], g["naam"]


def _m(id_: str, klasse: str, nr: int, lifecycle: str = "human_approved") -> dict:
    return {"id": id_, "klasse": klasse, "tekst": f"tekst van {id_}", "nr": nr, "lifecycle": lifecycle}


def _r(van: dict, naar: dict, type_: str, lifecycle: str = "human_approved", volgorde: int | None = None) -> dict:
    return {"id": f"{van['id']}-{type_}-{naar['id']}", "type": type_, "lifecycle": lifecycle, "volgorde": volgorde,
            "van": {**van, "soort": "element"}, "naar": {**naar, "soort": "element"}}


RB = _m("rb", "Rechtsbetrekking", 1)
ONTV = _m("ontv", "Rechtssubject", 2)
AANSLAG = _m("aanslag", "Rechtsobject", 3)
VW = _m("vw", "Voorwaarde", 4)
AR = _m("ar", "Afleidingsregel", 5)
UIT = _m("uit", "Variabele en variabelewaarde", 6)
LOS = _m("los", "Voorwaarde", 7)
KAAL = _m("kaal", "Voorwaarde", 8)


def test_een_voorwaarde_hoort_bij_haar_drager_en_elke_wortel_krijgt_een_diagram():
    relaties = [_r(ONTV, RB, "plichthebbende"), _r(RB, AANSLAG, "voorwerp"), _r(RB, VW, "voorwaarde"),
                _r(AR, UIT, "uitvoer"), _r(LOS, UIT, "invoer")]
    ds = diagram.diagrammen([RB, ONTV, AANSLAG, VW, AR, UIT, LOS, KAAL], relaties)
    assert [d.centraal for d in ds] == ["rb", "ar"]            # vw hangt bij rb, los bij ar (diepte 2), kaal heeft niets
    rb = ds[0]
    assert {k.id: k.zone for k in rb.knopen} == {"rb": "midden", "ontv": "links", "aanslag": "rechts", "vw": "boven"}
    assert rb.ontbreekt == ["rechthebbende"]
    assert ds[1].ontbreekt == ["invoer"]


def test_een_losse_voorwaarde_met_een_relatie_krijgt_een_eigen_diagram():
    op = _m("op", "Operator", 9)
    ds = diagram.diagrammen([KAAL, op], [_r(op, KAAL, "operator_in")])
    assert [d.centraal for d in ds] == ["kaal"]
    assert ds[0].ontbreekt == ["de drager waarvoor zij geldt"]


def test_verworpen_en_afgewezen_vallen_weg():
    weg = _m("weg", "Rechtssubject", 9, lifecycle="rejected")
    d = diagram.bouw(RB, [_r(weg, RB, "rechthebbende"), _r(RB, AANSLAG, "voorwerp", lifecycle="rejected")])
    assert [k.id for k in d.knopen] == ["rb"]
    assert d.ontbreekt == ["rechthebbende", "plichthebbende", "voorwerp"]


def test_info_vult_nummer_vindplaats_en_begrip():
    elders = {"aanslag": {"nr": 0, "elders": "art. 9 lid 1", "begrip": "belastingaanslag"}}
    d = diagram.bouw(RB, [_r(RB, AANSLAG, "voorwerp")], info=lambda k: elders.get(k["id"], {}))
    k = next(k for k in d.knopen if k.id == "aanslag")
    assert (k.nr, k.elders, k.begrip) == (0, "art. 9 lid 1", "belastingaanslag")
    kop, regels = diagram.knooptekst(k, "begrippen")
    assert kop == "Rechtsobject · art. 9 lid 1" and regels == ["belastingaanslag"]


def test_een_lang_fragment_wordt_begin_en_eind_nooit_een_parafrase():
    tekst = " ".join(f"woord{i}" for i in range(60))
    kort = diagram.ingekort(tekst)
    assert kort.startswith("woord0 ") and kort.endswith(" woord59") and " … " in kort
    assert all(w in tekst for w in kort.replace(" … ", " ").split())


def test_de_layout_is_vast_en_blijft_binnen_de_breedte():
    relaties = [_r(ONTV, RB, "plichthebbende"), _r(RB, AANSLAG, "voorwerp"), _r(RB, VW, "voorwaarde"),
                _r(RB, UIT, "tijd"), _r(_m("ext", "Rechtssubject", 10), RB, "rechthebbende")]
    d = diagram.bouw(RB, relaties)
    p1, p2 = diagram.plaats(d, 480), diagram.plaats(d, 480)
    assert p1 == p2
    for g in p1.knopen:
        assert 0 <= g.x and g.x + g.b <= 480 + 0.01 and 0 <= g.y and g.y + g.h <= p1.hoogte + 0.01
    pos = {g.knoop.id: g for g in p1.knopen}
    assert pos["vw"].y < pos["rb"].y < pos["uit"].y                                   # boven, midden, onder
    assert pos["ontv"].x < pos["rb"].x < pos["aanslag"].x                             # links, midden, rechts
    # Geen twee knopen over elkaar.
    ks = p1.knopen
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            assert a.x + a.b <= b.x or b.x + b.b <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y


def test_een_knoop_in_een_andere_bepaling_krijgt_haar_vindplaats_en_geen_nummer():
    waar = {"rb": ("lid1", 1), "vw": ("lid1", 4), "aanslag": ("onderdeel a", 2)}
    d = diagram.bouw(RB, [_r(RB, VW, "voorwaarde"), _r(RB, AANSLAG, "voorwerp")],
                     info=lambda k: {"nr": waar[k["id"]][1], "waar": waar[k["id"]][0], "waar_label": waar[k["id"]][0]})
    per = {k.id: (k.nr, k.elders) for k in d.knopen}
    assert per == {"rb": (1, ""), "vw": (4, ""), "aanslag": (0, "onderdeel a")}


def test_de_tekenaars_maken_pdf_svg_en_mermaid_uit_hetzelfde_model():
    from app import diagram_teken
    relaties = [_r(ONTV, RB, "plichthebbende"), _r(RB, AANSLAG, "voorwerp", lifecycle="voorgesteld"),
                _r(RB, VW, "voorwaarde"), _r(_m("op", "Operator", 9), VW, "operator_in")]
    d = diagram.bouw({**RB, "tekst": "De ontvanger is bevoegd – met “aanhalingstekens” en <tekens> [1]"}, relaties)
    tekening = diagram_teken.als_drawing(d, 480)
    assert tekening.width == 480 and tekening.height > 0
    kleiner = diagram_teken.als_drawing(d, 480, max_hoogte=50)
    assert kleiner.height == 50
    svg = diagram_teken.als_svg(d)
    assert svg.startswith("<?xml") and "plichthebbende" in svg
    md = diagram_teken.als_mermaid(d)
    assert md.startswith("```mermaid\nflowchart TB") and md.endswith("```")
    assert "#lt;tekens#gt;" in md and "#91;1#93;" in md and "<tekens>" not in md
    assert md.count("classDef") == len({k.klasse for k in d.knopen})
