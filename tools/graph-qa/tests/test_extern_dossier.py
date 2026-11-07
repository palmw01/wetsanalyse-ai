"""Een externe wetsanalyse inlezen en vergelijken (`eval/extern_dossier.py`).

De fixture is verzonnen: een Confluence-achtige pagina met de vorm van zo'n export, rond een niet-bestaande
regeling. Echt materiaal van derden hoort niet in deze repo; het staat lokaal in `docs/acceptatie/lokaal/`.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from eval import extern_dossier as ed

BWB = "BWBR0000001"
CITAAT = ("3 De aanvrager ontvangt de toeslag binnen acht weken na de dagtekening van het besluit, "
          "tenzij de inspecteur het verzoek afwijst of de termijn verlengt.")

ACTIVITEIT_2 = f"""
<html><body><div class="content">
<h2 id="x"><span><a href="https://wetten.overheid.nl/jci1.3:c:{BWB}&amp;hoofdstuk=2&amp;artikel=12&amp;z=2026-01-01">Toeslagwet, Artikel 12 lid 3</a></span></h2>
<div class="table-wrap"><table><tbody><tr><th><p>Status</p></th><td><p>definitief</p></td></tr></tbody></table></div>
<p>{CITAAT}</p>
<div class="table-wrap"><table class="confluenceTable"><thead><tr><th><p>Klasse</p></th><th><p>Formulering uit wettekst</p></th><th><p>Toelichting</p></th></tr></thead>
<tbody>
<tr><td><p>Rechtssubject</p></td><td><p>De aanvrager</p><p>nvt</p></td><td><p>Impliciet:<br/>de inspecteur<br/>Op te maken uit "afwijst".</p></td></tr>
<tr><td><p>(Rechts)object</p></td><td><p>de toeslag</p><p>het besluit</p></td><td><p><br/></p></td></tr>
<tr><td><p>Rechtsbetrekking</p></td><td><p>De aanvrager ontvangt de toeslag:<br/>a. binnen acht weken</p></td><td></td></tr>
<tr><td><p>Variabele</p></td><td><p>de dagtekening<br/>waar<br/>onwaar</p></td><td></td></tr>
<tr><td><p>Operator</p></td><td><p>tenzij<br/>of<br/>afwijst ... verlengt</p></td><td></td></tr>
<tr><td><p>Tijdsaanduiding</p></td><td><p>binnen acht weken na de dagtekening van het besluit</p><p>acht weken (2x)</p></td><td></td></tr>
<tr><td><p>Plaatsaanduiding</p></td><td><p><br/></p></td><td></td></tr>
</tbody></table></div>
<h2><a href="https://wetten.overheid.nl/{BWB}/2026-01-01/0#Circulaire.divisie4_Circulaire.divisie4.2">Beleidsregel, 4.2 Uitstel</a></h2>
<div class="table-wrap"><table><tbody><tr><th><p>Status</p></th><td><p>to do</p></td></tr></tbody></table></div>
<p>Uitstel wordt verleend voor ten hoogste drie maanden.</p>
<div class="table-wrap"><table><thead><tr><th><p>Klasse</p></th><th><p>Formulering uit wettekst</p></th><th><p>Toelichting</p></th></tr></thead>
<tbody><tr><td><p>Parameter</p></td><td><p>drie maanden</p></td><td></td></tr></tbody></table></div>
<h2>Een kop zonder tabel</h2><p>Tekst.</p>
</div></body></html>
"""

ACTIVITEIT_1 = f"""
<html><body>
<table><thead><tr><th><p>TW</p></th><th><p>Mogelijk relevant</p></th><th><p>Deelvraag</p></th></tr></thead><tbody>
<tr><td><p><a href="https://wetten.overheid.nl/jci1.3:c:{BWB}&amp;artikel=12">Artikel 12 lid 3.</a></p><p>De aanvrager ontvangt …</p></td><td><p>verklarend</p></td><td><p>(1) (2)</p></td></tr>
<tr><td><p><a href="https://wetten.overheid.nl/jci1.3:c:{BWB}&amp;artikel=4">Artikel 4. Uitstel lid 4.2 Uitstel</a></p></td><td><p>verklarend</p></td><td><p>(2)</p></td></tr>
<tr><td><p><a href="https://wetten.overheid.nl/jci1.3:c:{BWB}&amp;artikel=4">Artikel 4. Uitstel lid 4.3 Kosten</a></p></td><td><p>niet</p></td><td><p></p></td></tr>
</tbody></table>
</body></html>
"""


@pytest.fixture
def referentie():
    return ed.toets_letterlijk({"schema": "extern-dossier-v1", "bepalingen": ed.lees_annotaties(ACTIVITEIT_2),
                                "bronnen": ed.lees_bronnen(ACTIVITEIT_1)})


def _el(klasse, tekst, iri=f"urn:bwb:{BWB}:artikel:12:lid:3", id_="e"):
    return {"id": id_, "klasse": klasse, "tekst": tekst, "eigenaar_iri": iri, "ankers": [{"bron_iri": iri}]}


# --- Inlezen --------------------------------------------------------------------------------------------------

def test_een_kop_met_jas_tabel_is_een_bepaling_met_bron_en_status(referentie):
    b = referentie["bepalingen"]
    assert [x["label"] for x in b] == ["Toeslagwet, Artikel 12 lid 3", "Beleidsregel, 4.2 Uitstel"]
    assert b[0]["bron"] == {"bwb_id": BWB, "artikel": "12", "lid": "3"}
    assert b[1]["bron"] == {"bwb_id": BWB, "artikel": "4.2", "lid": ""}
    assert [x["status_soort"] for x in b] == ["definitief", "concept"]


def test_elke_regel_is_een_fragment_met_de_platformklasse(referentie):
    els = {(e["klasse"], e["tekst"]) for e in referentie["bepalingen"][0]["elementen"]}
    assert ("Rechtsobject", "de toeslag") in els  # "(Rechts)object"
    assert ("Variabele en variabelewaarde", "waar") in els  # een <br> begint een fragment
    assert ("Operator", "of") in els
    # Een opsommingsonderdeel hoort bij de regel ervoor, zoals in de wettekst.
    assert ("Rechtsbetrekking", "De aanvrager ontvangt de toeslag: a. binnen acht weken") in els
    assert not any(t in ("nvt", "") for _, t in els)
    assert not any(k == "Plaatsaanduiding" for k, _ in els)


def test_telling_en_ellips(referentie):
    els = referentie["bepalingen"][0]["elementen"]
    acht = next(e for e in els if e["tekst"] == "acht weken")
    assert acht["herhaling"] == 2
    ellips = next(e for e in els if e["klasse"] == "Operator" and "verlengt" in e["tekst"])
    assert ellips["delen"] == ["afwijst", "verlengt"]
    assert ellips["letterlijk"]


def test_een_impliciet_rechtssubject_komt_uit_de_toelichting_en_telt_niet_als_letterlijk(referentie):
    els = referentie["bepalingen"][0]["elementen"]
    impliciet = [e for e in els if e["impliciet"]]
    assert [e["tekst"] for e in impliciet] == ["de inspecteur"]
    assert not impliciet[0]["letterlijk"]


def test_letterlijk_tegen_het_citaat_of_de_brontekst(referentie):
    b = referentie["bepalingen"][0]
    assert b["getoetst_tegen"] == "citaat"
    niet = {e["tekst"] for e in b["elementen"] if not e["letterlijk"] and not e["impliciet"]}
    assert niet == {"waar", "onwaar", "De aanvrager ontvangt de toeslag: a. binnen acht weken"}
    # Met de wettekst uit de graaf telt die, en een woord binnen een langer woord telt niet.
    opnieuw = ed.toets_letterlijk(json.loads(json.dumps(referentie)),
                                  {f"{BWB}/12/3": "De aanvrager ontvangt de toeslagen niet."})
    b2 = opnieuw["bepalingen"][0]
    assert b2["getoetst_tegen"] == "bron"
    assert not next(e for e in b2["elementen"] if e["tekst"] == "de toeslag")["letterlijk"]


def test_bronnentabel_met_deelvragen(referentie):
    bronnen = referentie["bronnen"]
    assert [(b["bron"]["artikel"], b["bron"]["lid"], b["deelvragen"]) for b in bronnen] == [
        ("12", "3", [1, 2]), ("4.2", "", [2]), ("4.3", "", [])]


# --- Toewijzen ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("iri, bron, past", [
    (f"urn:bwb:{BWB}:artikel:12:lid:3", {"bwb_id": BWB, "artikel": "12", "lid": "3"}, True),
    (f"urn:bwb:{BWB}:artikel:12:lid:30", {"bwb_id": BWB, "artikel": "12", "lid": "3"}, False),
    (f"urn:bwb:{BWB}:artikel:12a:lid:3", {"bwb_id": BWB, "artikel": "12", "lid": "3"}, False),
    (f"urn:bwb:{BWB}:artikel:4%3A86:lid:2", {"bwb_id": BWB, "artikel": "4:86", "lid": "2"}, True),
    (f"urn:bwb:{BWB}:id:{BWB}%2FCirculaire.divisie4%2FCirculaire.divisie4.2", {"bwb_id": BWB, "artikel": "4.2"}, True),
    (f"urn:bwb:{BWB}:id:{BWB}%2FCirculaire.divisie4%2FCirculaire.divisie4.21", {"bwb_id": BWB, "artikel": "4.2"}, False),
    (f"urn:bwb:BWBR0000002:artikel:12:lid:3", {"bwb_id": BWB, "artikel": "12", "lid": "3"}, False),
])
def test_iri_past_bij_de_bepaling(iri, bron, past):
    assert ed._iri_past(iri, bron) is past


def test_wat_bij_geen_bepaling_hoort_valt_niet_stil_weg(referentie):
    vreemd = _el("Operator", "ergens anders", iri="urn:bwb:BWBR0000009:artikel:1")
    per, los = ed.wijs_toe(referentie["bepalingen"], [vreemd])
    assert los == [vreemd] and not any(per.values())


# --- Vergelijken ----------------------------------------------------------------------------------------------

def test_recall_per_klasse_verwisseling_en_wat_alleen_het_platform_vond(referentie):
    platform = {"elementen": {"elementen": [  # de vorm van werkgebied_lezen
        _el("Rechtsobject", "de toeslag", id_="a"),
        _el("Rechtssubject", "het besluit", id_="b"),       # zelfde plek, andere klasse
        _el("Tijdsaanduiding", "binnen acht weken na de dagtekening van het besluit", id_="c"),
        _el("Rechtsfeit", "de inspecteur het verzoek afwijst", id_="d"),  # niet in de referentie
    ]}}
    r = ed.vergelijk(referentie, platform)
    a = r["annotaties"]
    assert r["platform_elementen"] == 4
    assert a["per_klasse_strikt"]["Rechtsobject"] == {"n": 2, "gedekt": 1, "streng": 1, "exact": 1, "voorstellen": 1,
                                                       "raak": 1, "recall": 0.5, "recall_streng": 0.5}
    b = a["bepalingen"][0]
    assert {"tekst": "het besluit", "referentie": "Rechtsobject", "platform": ["Rechtssubject"]} in b["klasse_verwisseld"]
    assert [x["id"] for x in b["buiten_referentie"]] == ["d"]
    # "het besluit" als Rechtssubject staat op een referentieplek, maar met een andere klasse: geen tegenhanger.
    assert {x["id"] for x in b["zonder_tegenhanger"]} == {"b", "d"}
    assert b["impliciet"] == ["de inspecteur"]
    # Strikt telt alleen wat letterlijk in de bron staat; ruim telt ook de rest.
    assert "Variabele en variabelewaarde" in a["per_klasse_ruim"]
    assert a["per_klasse_ruim"]["Variabele en variabelewaarde"]["n"] > a["per_klasse_strikt"]["Variabele en variabelewaarde"]["n"]
    assert set(a["per_status_strikt"]) == {"definitief", "concept"}


def test_een_telling_is_een_markering(referentie):
    ref = ed._referentie(referentie["bepalingen"][0], strikt=True)
    assert sum(1 for r in ref if r["tekst"] == "acht weken") == 1


def test_platform_elementen_in_elke_vorm():
    els = [{"klasse": "Operator", "tekst": "of"}]
    assert ed.platform_elementen({"elementen": els}) == els
    assert ed.platform_elementen({"elementen": {"elementen": els}, "audit": []}) == els
    assert ed.platform_elementen({"schema_versie": 3, "lagen": [], "elementen": els}) == els
    assert ed.platform_elementen({"niets": 1}) == []


def test_relaties_eindpuntdekking_per_type():
    relaties = {"bepalingen": [{"bron": {"bwb_id": BWB, "artikel": "12", "lid": "3"}, "knopen": [
        {"id": "s", "klasse": "rechtssubject", "label": "de inspecteur", "letterlijk": "impliciet"},
        {"id": "a", "klasse": "rechtssubject", "label": "De aanvrager", "letterlijk": "ja"},
        {"id": "rb", "klasse": "rechtsbetrekking", "label": "De aanvrager ontvangt de toeslag", "letterlijk": "ja"},
        {"id": "o", "klasse": "rechtsobject", "label": "de toeslag", "letterlijk": "ja"},
    ], "kanten": [
        {"van": "a", "naar": "rb", "type": "rechthebbende van"},
        {"van": "s", "naar": "rb", "type": "plichthebbende van"},
        {"van": "rb", "naar": "o", "type": "heeft als voorwerp"},
    ]}]}
    els = [_el("Rechtssubject", "De aanvrager"), _el("Rechtsobject", "de toeslag")]
    r = ed.vergelijk_relaties(ed.lees_relaties(relaties), els)["per_type"]
    assert r["rechthebbende van"] == {"n": 1, "beide": 0, "een": 1, "geen": 0, "niet_meetbaar": 0}
    assert r["plichthebbende van"]["niet_meetbaar"] == 1
    assert r["heeft als voorwerp"]["een"] == 1


def test_een_kant_naar_een_onbekende_knoop_is_een_fout():
    with pytest.raises(ValueError, match="onbekende knoop"):
        ed.lees_relaties({"bepalingen": [{"bron": {}, "knopen": [{"id": "a", "klasse": "operator", "label": "of"}],
                                          "kanten": [{"van": "a", "naar": "b", "type": "invoer"}]}]})


def test_bronselectie_per_deelvraagnummer(referentie):
    werkgebied = {"werkgebied": {
        "bronnen": [{"id": "s1", "bron_iri": f"urn:bwb:{BWB}:artikel:12"},
                    {"id": "s2", "bron_iri": f"urn:bwb:{BWB}:id:{BWB}%2FCirculaire.divisie4%2FCirculaire.divisie4.2"}],
        "deelvragen": [{"vraag": "Eén?", "status": "actief", "bronnen": ["s1"]},
                       {"vraag": "Weg?", "status": "vervangen", "bronnen": []},
                       {"vraag": "Twee?", "status": "actief", "bronnen": ["s2"]}]}}
    r = ed.vergelijk_bronnen(referentie, werkgebied)
    assert [(d["deelvraag"], d["vraag"], d["gevonden"], d["verwacht"]) for d in r] == [
        (1, "Eén?", 1, 1),     # een selectie op het artikel omvat het lid
        (2, "Twee?", 1, 2)]
    assert r[1]["gemist"] == ["tw Artikel 12 lid 3."]


def test_cli_lees_en_vergelijk(tmp_path, capsys):
    (tmp_path / "a2.html").write_text(ACTIVITEIT_2, encoding="utf-8")
    (tmp_path / "a1.html").write_text(ACTIVITEIT_1, encoding="utf-8")
    ref = tmp_path / "ref.json"
    assert ed.main(["lees", "--export", str(tmp_path), "--uit", str(ref)]) == 0
    (tmp_path / "els.json").write_text(json.dumps({"elementen": [_el("Rechtsobject", "de toeslag")]}))
    assert ed.main(["vergelijk", "--referentie", str(ref), "--platform", str(tmp_path / "els.json"),
                    "--uit", str(tmp_path / "rapport.json")]) == 0
    assert "Recall per klasse" in capsys.readouterr().out
    assert json.loads((tmp_path / "rapport.json").read_text())["schema"] == "extern-vergelijking-v1"


def test_de_module_kent_geen_lokaal_pad():
    """Het materiaal staat lokaal en hoort niet in de repo; de code krijgt elk pad als argument."""
    bron = Path(ed.__file__).read_text(encoding="utf-8")
    boom = ast.parse(bron)
    docs = {id(n.body[0].value) for n in ast.walk(boom)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    teksten = [n.value for n in ast.walk(boom) if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and id(n) not in docs]
    assert not any(t for t in teksten if "lokaal" in t or "Downloads" in t or t.startswith("/home"))


def test_annotatie_volgt_een_expliciete_golden(tmp_path):
    """Een lokale set (uit een extern dossier) draait met `run_eval.py --annotatie --golden <pad>`."""
    import argparse

    from eval import run_eval
    eigen = tmp_path / "set.jsonl"
    ns = lambda **kw: argparse.Namespace(**{"concept": False, "golden": run_eval.GOLDEN, **kw})  # noqa: E731
    assert run_eval.annotatieset(ns()) == run_eval.GOLDEN_ANNOTATIE
    assert run_eval.annotatieset(ns(golden=eigen)) == eigen
    assert run_eval.annotatieset(ns(golden=eigen, concept=True)) == run_eval.GOLDEN_CONCEPT


def test_streng_telt_een_lange_markering_niet_als_raak(referentie):
    """"Zelfde plek" is soepel: een markering van een hele zin dekt elk fragment erin. Streng eist de grens."""
    lang = _el("Tijdsaanduiding", CITAAT[2:])
    a = ed.vergelijk(referentie, {"elementen": [lang]})["annotaties"]["per_klasse_strikt"]["Tijdsaanduiding"]
    assert a["gedekt"] >= 1 and a["streng"] == 0


BELEID = f"urn:bwb:{BWB}:id:{BWB}%2FCirculaire.divisie4%2FCirculaire.divisie4.2"


def test_een_verbijzonderende_tijdsaanduiding_dekt_de_parameter_op_die_plek(referentie):
    """De referentie markeert "drie maanden" als Parameter; het platform markeert de duur één keer, als
    Tijdsaanduiding met subtype "verbijzondert parameter" (H2:107, ADR-001 PR 8). Dat dekt de Parameter; zonder
    subtype niet. Het blijft één voorstel, van de eigen klasse."""
    met = {**_el("Tijdsaanduiding", "drie maanden", iri=BELEID), "jas_subtype": "verbijzondert parameter"}
    a = ed.vergelijk(referentie, {"elementen": [met]})["annotaties"]
    p = a["per_klasse_strikt"]["Parameter en parameterwaarde"]
    assert (p["n"], p["gedekt"], p["streng"], p["exact"], p["voorstellen"]) == (1, 1, 1, 1, 0)
    assert a["per_klasse_strikt"]["Tijdsaanduiding"]["voorstellen"] == 1
    b = a["bepalingen"][1]
    assert b["gemist"] == [] and b["zonder_tegenhanger"] == [] and b["klasse_verwisseld"] == []

    zonder = _el("Tijdsaanduiding", "drie maanden", iri=BELEID)
    a = ed.vergelijk(referentie, {"elementen": [zonder]})["annotaties"]
    assert a["per_klasse_strikt"]["Parameter en parameterwaarde"]["gedekt"] == 0
    assert a["bepalingen"][1]["klasse_verwisseld"] == [
        {"tekst": "drie maanden", "referentie": "Parameter en parameterwaarde", "platform": ["Tijdsaanduiding"]}]


def test_alleen_de_tijdsaanduiding_verbijzondert(referentie):
    """Het subtype geldt per klasse: een Rechtsobject met dat subtype dekt niets extra. De export v3 draagt het
    subtype onder `herkomst_regels`."""
    vreemd = {**_el("Rechtsobject", "drie maanden", iri=BELEID), "jas_subtype": "verbijzondert parameter"}
    a = ed.vergelijk(referentie, {"elementen": [vreemd]})["annotaties"]
    assert a["per_klasse_strikt"]["Parameter en parameterwaarde"]["gedekt"] == 0
    export = {**_el("Tijdsaanduiding", "drie maanden", iri=BELEID), "herkomst_regels": {"subtype": "verbijzondert parameter"}}
    a = ed.vergelijk(referentie, {"elementen": [export]})["annotaties"]
    assert a["per_klasse_strikt"]["Parameter en parameterwaarde"]["gedekt"] == 1
