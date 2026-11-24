"""Een begrippen- en regelbibliotheek inlezen en vergelijken (`eval/extern_bibliotheek.py`).

De fixtures zijn verzonnen: Confluence-achtige pagina's met de vorm van zo'n export, rond een niet-bestaande regeling
(Toeslagwet, BWBR0000001). Echt materiaal van derden hoort niet in deze repo.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from eval import extern_bibliotheek as eb

BWB = "BWBR0000001"
WIKI = "https://wiki.example/spaces/X/pages"


def _pagina(veldrijen: str, extra: str = "", traject: str = "Analyse Toeslag") -> str:
    return f"""<html><head><title>t</title></head><body><div id="main-content">
<p>Gebruikt in wetsanalysetraject(en): <a href="{WIKI}/100001/x">{traject}</a></p>
<div class="table-wrap"><table><thead><tr><th><p>Begripsnaam</p></th><th><p>{{naam}}</p></th></tr></thead>
<tbody>{veldrijen}</tbody></table></div>{extra}</div></body></html>"""


def _rij(kop: str, waarde: str) -> str:
    return f"<tr><th><p>{kop}</p></th><td><p>{waarde}</p></td></tr>"


BEGRIP_DATUM = _pagina(
    _rij("Begripsdefinitie", "datum waarop het besluit is gedagtekend")
    + _rij("Formulering uit de primaire juridische bron",
           f'<a href="https://wetten.overheid.nl/jci1.3:c:{BWB}&amp;artikel=12">Toeslagwet, Artikel 12</a>'
           "<br/>lid 3. De aanvrager ontvangt …")
    + _rij("Klasse", "Variabele") + _rij("Waarde", "Datum")
    + _rij("Opmerkingen", "Resultaat van de afleidingsregel bepaal uiterste datum")
).replace("{naam}", "dagtekening besluit")

BEGRIP_JA_NEE = _pagina(
    _rij("Begripsdefinitie", "situatie waarin het verzoek is afgewezen")
    + _rij("Klasse", "Variabele") + _rij("Waarde", "Boolean") + _rij("Interpretatie", "eigen lezing")
).replace("{naam}", "verzoek afgewezen")

BEGRIP_ANDER_TRAJECT = _pagina(_rij("Begripsdefinitie", "x") + _rij("Klasse", "Rechtsobject"),
                               traject="Analyse Iets Anders").replace("{naam}", "ander begrip")

REGEL = _pagina(
    _rij("Afleidingsregel",
         f'de <a href="{WIKI}/200003/uiterste+datum">uiterste datum</a> wordt berekend als de '
         f'<a href="dagtekening-besluit.200001.html">dagtekening besluit</a> plus acht weken indien<br/>'
         f'- het <a href="{WIKI}/200002/verzoek+afgewezen">verzoek afgewezen</a> is ONWAAR<br/>'
         f'de <a href="{WIKI}/200003/uiterste+datum">uiterste datum</a> wordt gesteld op leeg indien<br/>'
         f'- het <a href="{WIKI}/200002/verzoek+afgewezen">verzoek afgewezen</a> is WAAR')
    + _rij("Klasse", "Afleidingsregel")
    + _rij("Status", "afgestemd in werksessie"),
    extra="""<div class="table-wrap"><table><tbody>
<tr><td><p><strong>Voorbeelden</strong></p></td><td><p>1</p></td><td><p>2</p></td><td><p>3</p></td></tr>
<tr><td><p><strong>Invoer</strong></p></td><td></td><td></td><td></td></tr>
<tr><td><p>dagtekening besluit</p></td><td><p>01-03-2026</p></td><td><p>31-01-2026</p></td><td><p>30-02-2026</p></td></tr>
<tr><td><p>is invoer juist?</p></td><td><p>Ja</p></td><td><p>Ja</p></td><td><p>NVT</p></td></tr>
<tr><td><p><strong>Uitvoer (voorspelling)</strong></p></td><td></td><td></td><td></td></tr>
<tr><td><p>uiterste datum</p></td><td><p>26-04-2026</p></td><td><p>28-03-2026</p></td><td><p>NVT</p></td></tr>
<tr><td><p>Is voorspelling juridisch juist?</p></td><td><p>Ja</p></td><td><p>Nee</p></td><td><p>NVT</p></td></tr>
</tbody></table></div>""",
).replace("{naam}", "bepaal uiterste datum")

WERKBESTAND = f"""<html><body><div id="main-content">
<table><thead><tr><th><p>Klasse</p></th><th><p>Gemarkeerde tekst</p></th><th><p>Wet</p></th>
<th><p>Begripsnaam</p></th><th><p>Eventueel toelichting</p></th></tr></thead><tbody>
<tr><td><p>Variabele</p></td><td><p>de dagtekening<br/>de dagtekening van het besluit</p></td>
<td><p>TW, Art. 12 lid 3<br/>TW, Art. 12 lid 4.</p></td>
<td><p><a href="dagtekening-besluit.200001.html">dagtekening besluit</a></p></td><td></td></tr>
<tr><td><p>Variabele</p></td><td><p>het verzoek afwijst</p></td><td><p>TW, Art. 12 lid 3</p></td>
<td><p><a href="{WIKI}/200002/verzoek+afgewezen">verzoek afgewezen</a></p></td><td></td></tr>
<tr><td><p><s>Parameter</s></p></td><td><p><s>acht weken</s></p></td><td><p><s>TW, Art. 12 lid 3</s></p></td>
<td></td><td><p>is geen parameter</p></td></tr>
<tr><td><p>Parameter/Parameterwaarde</p></td><td><p>acht weken (2x)</p></td><td><p>TW, Art. 12 lid 3</p></td>
<td><p><a href="{WIKI}/200004/beslistermijn">beslistermijn</a></p></td><td></td></tr>
</tbody></table></div></body></html>"""


def _referentie(tmp_path: Path) -> dict:
    begrippen, regels = tmp_path / "b", tmp_path / "r"
    begrippen.mkdir()
    regels.mkdir()
    (begrippen / "dagtekening-besluit.200001.html").write_text(BEGRIP_DATUM, encoding="utf-8")
    (begrippen / "verzoek-afgewezen.200002.html").write_text(BEGRIP_JA_NEE, encoding="utf-8")
    (begrippen / "ander-begrip.200009.html").write_text(BEGRIP_ANDER_TRAJECT, encoding="utf-8")
    (begrippen / "index.html").write_text("<html><body><ul><li>x</li></ul></body></html>", encoding="utf-8")
    (regels / "bepaal-uiterste-datum.300001.html").write_text(REGEL, encoding="utf-8")
    wb = tmp_path / "werkbestand.html"
    wb.write_text(WERKBESTAND, encoding="utf-8")
    return eb.lees_bibliotheek(sorted(begrippen.glob("*.html")), sorted(regels.glob("*.html")), [wb], "Toeslag")


def test_een_begrippagina_wordt_een_neutraal_begrip():
    b = eb.lees_pagina(BEGRIP_DATUM, "dagtekening-besluit.200001.html")
    assert b["id"] == "200001" and b["soort"] == "begrip"
    assert b["naam"] == "dagtekening besluit"
    assert b["klasse"] == "Variabele" and b["waarde"] == "Datum"
    assert b["bron"] == [{"bwb_id": BWB, "artikel": "12", "lid": "3"}]
    assert b["trajecten"] == ["Analyse Toeslag"]
    assert b["opmerkingen"] and not b["interpretatie"]


def test_een_regelpagina_draagt_uitvoer_invoer_en_voorbeelden():
    r = eb.lees_pagina(REGEL, "bepaal-uiterste-datum.300001.html")
    assert r["soort"] == "regel" and r["uitvoer"] == "uiterste datum"
    # Elke begripsnaam één keer, met het id uit beide linkvormen.
    assert [v["id"] for v in r["verwijzingen"]] == ["200003", "200001", "200002"]
    assert eb._gevallen(r["tekst"]) == 2
    v = r["voorbeelden"]
    assert v["gevallen"] == 3
    assert [x["begrip"] for x in v["invoer"]] == ["dagtekening besluit"]
    assert v["oordeel_invoer"] == {"ja": 2, "nvt": 1}
    assert v["oordeel_uitvoer"] == {"ja": 1, "nee": 1, "nvt": 1}


def test_een_pagina_zonder_veldtabel_is_geen_begrip():
    assert eb.lees_pagina("<html><body><div id='main-content'><p>x</p></div></body></html>") is None


def test_de_vindplaats_uit_het_werkbestand():
    assert eb.vindplaats_uit("IW, Art. 9 lid 5") == {"afkorting": "IW", "artikel": "9", "lid": "5", "alinea": ""}
    assert eb.vindplaats_uit("Leidr. Inv., Art. 9.5. alinea 3") == {
        "afkorting": "Leidr. Inv.", "artikel": "9.5", "lid": "", "alinea": "3"}
    assert eb.vindplaats_uit("Awb, Art. 4:86 lid 2.")["artikel"] == "4:86"
    assert eb.vindplaats_uit("zomaar tekst") is None


def test_het_werkbestand_koppelt_formulering_plek_en_begrip_en_laat_doorhalingen_weg():
    f = eb.lees_werkbestand(WERKBESTAND)
    assert [x["tekst"] for x in f] == ["de dagtekening", "de dagtekening van het besluit", "het verzoek afwijst",
                                       "acht weken"]
    assert [x["vindplaatsen"][0]["lid"] for x in f[:2]] == ["3", "4"]  # per index gekoppeld
    assert f[3]["klasse"] == ["Parameter en parameterwaarde"]  # "(2x)" eraf, de doorgehaalde rij weg
    assert not any(x["dubbelzinnig"] for x in f)


def test_alleen_het_gevraagde_traject(tmp_path):
    ref = _referentie(tmp_path)
    assert {b["naam"] for b in ref["begrippen"]} == {"dagtekening besluit", "verzoek afgewezen"}
    assert [r["naam"] for r in ref["regels"]] == ["bepaal uiterste datum"]


def _element(eid: str, tekst: str, lid: str = "3", klasse: str = "Variabele en variabelewaarde") -> dict:
    iri = f"urn:bwb:{BWB}:artikel:12:lid:{lid}"
    return {"id": eid, "klasse": klasse, "tekst": tekst, "lifecycle": "human_approved", "eigenaar_iri": iri,
            "ankers": [{"bron_iri": iri, "tekst": tekst}]}


def _lex(elementen: list[dict], begrippen: list[tuple[str, str]], koppelingen: list[tuple[str, str]]):
    werkgebied = {"elementen": {"elementen": elementen}}
    b = {"begrippen": {"begrippen": [{"id": i, "status": "geaccordeerd", "inhoud": {"naam": n}} for i, n in begrippen]},
         "samenhang": {"koppelingen": [{"begrip_id": b, "element_id": e, "rol": "duiding", "beoordeling": "akkoord"}
                                       for b, e in koppelingen]}}
    return werkgebied, b


AFKORTINGEN = {"TW": BWB}


def test_een_begrip_op_dezelfde_formuleringen_is_gedekt(tmp_path):
    ref = _referentie(tmp_path)
    wg, b = _lex([_element("e1", "de dagtekening"), _element("e2", "de dagtekening van het besluit", "4"),
                  _element("e3", "het verzoek afwijst")],
                 [("L1", "dagtekening"), ("L2", "afwijzing")], [("L1", "e1"), ("L1", "e2")])
    r = eb.vergelijk_begrippen(ref, wg, b, AFKORTINGEN)
    per = {u["naam"]: u["uitkomst"] for u in r["begrippen"]}
    assert per == {"dagtekening besluit": "gedekt", "verzoek afgewezen": "zonder_begrip"}
    assert r["alleen_in_lex"] == ["afwijzing"]
    assert r["ja_nee"] == {"zonder_begrip": 1}


def test_een_begrip_dat_twee_referentiebegrippen_draagt_is_anders_gesneden(tmp_path):
    ref = _referentie(tmp_path)
    wg, b = _lex([_element("e1", "de dagtekening"), _element("e3", "het verzoek afwijst")],
                 [("L1", "besluitgegevens")], [("L1", "e1"), ("L1", "e3")])
    per = {u["naam"]: u["uitkomst"] for u in eb.vergelijk_begrippen(ref, wg, b, AFKORTINGEN)["begrippen"]}
    assert per == {"dagtekening besluit": "anders_gesneden", "verzoek afgewezen": "anders_gesneden"}


def test_een_formulering_zonder_element_en_een_omvattende_normzin(tmp_path):
    """De hele normzin om de formulering heen is een andere formulering: het begrip daarop telt niet."""
    ref = _referentie(tmp_path)
    zin = "De aanvrager ontvangt de toeslag binnen acht weken na de dagtekening, tenzij de inspecteur het verzoek afwijst"
    wg, b = _lex([_element("e9", zin, klasse="Rechtsbetrekking")], [("L9", "recht op toeslag")], [("L9", "e9")])
    per = {u["naam"]: u["uitkomst"] for u in eb.vergelijk_begrippen(ref, wg, b, AFKORTINGEN)["begrippen"]}
    assert per == {"dagtekening besluit": "niet_gemarkeerd", "verzoek afgewezen": "niet_gemarkeerd"}


def test_regelbegrippen_tellen_niet_als_begrip_van_een_formulering(tmp_path):
    ref = _referentie(tmp_path)
    wg, b = _lex([_element("e1", "de dagtekening")], [("L1", "dagtekening"), ("R1", "bepalen van de dagtekening")],
                 [("L1", "e1"), ("R1", "e1")])
    r = eb.vergelijk_begrippen(ref, wg, b, AFKORTINGEN)
    assert {u["naam"]: u["uitkomst"] for u in r["begrippen"]}["dagtekening besluit"] == "gedekt"
    assert r["regelbegrippen"] == 1


def test_een_regel_wordt_op_zijn_uitvoer_gevonden(tmp_path):
    ref = _referentie(tmp_path)
    wg, b = _lex([_element("e1", "de dagtekening")], [("L1", "dagtekening")], [("L1", "e1")])
    br = eb.vergelijk_begrippen(ref, wg, b, AFKORTINGEN)
    op_naam = [{"id": "x1", "naam": "bepalen van de uiterste datum", "uitvoer": "uiterste datum",
                "inhoud": {"uitvoer_begrip_id": "U", "invoer": [{"begrip_id": "L1"}]}}]
    r = eb.vergelijk_regels(ref, br, op_naam)
    assert r["regels"][0]["uitkomst"] == "gevonden"
    assert r["regels"][0]["invoer_overeen"] == 1 and r["regels"][0]["invoer_referentie"] == 2
    anders = [{"id": "x2", "naam": "bepalen van de termijn", "uitvoer": "termijn", "status": "concept",
               "inhoud": {"uitvoer_begrip_id": "U", "invoer": []}},
              {"id": "x3", "naam": "oud", "uitvoer": "uiterste datum", "status": "vervangen", "inhoud": {}}]
    r = eb.vergelijk_regels(ref, br, anders)
    assert r["regels"][0]["uitkomst"] == "ontbreekt" and r["alleen_in_lex"] == ["bepalen van de termijn"]


def test_de_vorm_van_de_referentie_zonder_inhoud(tmp_path):
    v = eb.vorm(_referentie(tmp_path))
    assert v["begrippen"] == 2 and v["regels"] == 1 and v["ja_nee"] == 1
    assert v["regels_met_voorbeelden"] == 1 and v["voorbeeldgevallen"] == 3
    assert v["regels_per_gevallen"] == {2: 1}


def test_het_manifest_noemt_geen_namen(tmp_path):
    _referentie(tmp_path)
    m = eb.manifest("set", [tmp_path / "b", tmp_path / "r"])
    tekst = json.dumps(m)
    assert [d["paginas"] for d in m["delen"]] == [4, 1]
    assert "dagtekening" not in tekst and "uiterste" not in tekst and ".html" not in tekst


def test_de_cli_leest_en_vergelijkt(tmp_path, capsys):
    ref = _referentie(tmp_path)
    (tmp_path / "ref.json").write_text(json.dumps(ref), encoding="utf-8")
    wg, b = _lex([_element("e1", "de dagtekening")], [("L1", "dagtekening")], [("L1", "e1")])
    (tmp_path / "wg.json").write_text(json.dumps(wg), encoding="utf-8")
    (tmp_path / "bg.json").write_text(json.dumps(b), encoding="utf-8")
    (tmp_path / "afk.json").write_text(json.dumps(AFKORTINGEN), encoding="utf-8")
    assert eb.main(["vergelijk", "--referentie", str(tmp_path / "ref.json"), "--werkgebied", str(tmp_path / "wg.json"),
                    "--begrippen", str(tmp_path / "bg.json"), "--afkortingen", str(tmp_path / "afk.json"),
                    "--uit", str(tmp_path / "rapport.json")]) == 0
    assert "Begrippen:" in capsys.readouterr().out
    assert json.loads((tmp_path / "rapport.json").read_text())["schema"] == "extern-bibliotheek-v1-rapport"


def test_de_module_kent_geen_lokaal_pad_en_geen_regeling():
    """Het materiaal staat lokaal; de code krijgt elk pad en elke afkorting als argument."""
    bron = Path(eb.__file__).read_text(encoding="utf-8")
    boom = ast.parse(bron)
    docs = {id(n.body[0].value) for n in ast.walk(boom)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    teksten = [n.value for n in ast.walk(boom) if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and id(n) not in docs]
    assert not any("Downloads" in t or t.startswith("/home") or "BWBR0" in t for t in teksten)
