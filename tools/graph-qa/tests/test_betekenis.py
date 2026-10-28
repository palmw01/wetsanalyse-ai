"""Het betekenisdossier en de toetsen erop (spoor M, M2), op casus A en B uit de graaf."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.begrippen_pipeline import betekenis, kaartacties as ka, signalen, toetsen
from agent.begrippen_pipeline.besluit import beslis_alle
from agent.begrippen_pipeline.keten import _kandidaten
from agent.begrippen_pipeline.model import (
    Besluit, Bron, Contextbron, Formulering, Fragment, Herkomst, Kaart, Manifest, Onderzoek, Reden, Rol, Taalanalyse,
    fragment_id,
)
from fakes import FakeLLM, response, tool_block

CASUS = json.loads((Path(__file__).resolve().parents[1] / "eval" / "betekenisonderzoek_casus.json").read_text())
NODES = {n["bron_iri"]: n for n in CASUS["nodes"]}
A = "urn:bwb:BWBR0002320:artikel:30fb"
B = "urn:bwb:BWBR0002320:artikel:30fc"


def _bron(iri: str, cls=Bron, **extra):
    n = NODES[iri]
    return cls(bron_iri=iri, tekst=n["tekst"], bron_hash=n["bron_hash"], label=f"art. {iri.split(':artikel:')[1]}",
               regeling="BWBR0002320", **extra)


def casus(c: str, met_onderzoek: bool = True) -> tuple[Manifest, Onderzoek | None]:
    fs = CASUS["casus"][c]["formuleringen"]
    m = Manifest(bronnen=tuple(_bron(i) for i in sorted({f["bron_iri"] for f in fs})),
                 formuleringen=tuple(Formulering(element_id=f"e{i}", **f) for i, f in enumerate(fs)))
    if not met_onderzoek:
        return m, None
    art = fs[0]["bron_iri"].rsplit(":lid:", 1)[0]
    eigen = {b.bron_iri for b in m.bronnen}
    ctx = tuple(_bron(i, Contextbron, rol=Rol.ONDERZOEK, reden=Reden.ZELFDE_ARTIKEL, voor=("e0",))
                for i in NODES if i.startswith(art + ":") and NODES[i]["tekst"] and i not in eigen)
    return m, Onderzoek(manifest_id=m.id, bronnen=ctx)


# --- de regels -------------------------------------------------------------------------------------

def _gevallen(soort: str):
    return [pytest.param(r, g, id=f"{r['id']}-{soort}-{i}")
            for r in betekenis.berekeningsregels() for i, g in enumerate(r["tests"][soort])]


@pytest.mark.parametrize("regel, geval", _gevallen("positief") + _gevallen("rand") + _gevallen("overlap"))
def test_een_berekeningsregel_vangt_haar_gevallen(regel, geval):
    assert betekenis._compileer(regel["patroon"], geval["term"]).search(geval["tekst"]), regel["id"]


@pytest.mark.parametrize("regel, geval", _gevallen("negatief"))
def test_een_berekeningsregel_matcht_niet_op_negatief(regel, geval):
    assert not betekenis._compileer(regel["patroon"], geval["term"]).search(geval["tekst"]), regel["id"]


# --- het dossier -----------------------------------------------------------------------------------

def test_casus_a_parallelle_leden_met_de_varianten():
    m, o = casus("A")
    d = betekenis.dossier(m, o, ("e0",), ["herziening"])
    [p] = d.met(betekenis.PARALLEL)
    assert p.bron_iris == tuple(f"{A}:lid:{n}" for n in (4, 1, 2, 3, 5, 6))
    assert set(p.specifiek) == {"positief", "negatief", "hoger", "lager", "kleiner", "groter"}
    assert any("specifiek geval" in v for v in d.vragen)
    assert d.met("GEEN_DEFINITIE_GEVONDEN")
    assert d.onderzoek_id == o.id and d.onderzocht == 7


def test_zonder_onderzoek_ziet_het_dossier_alleen_het_manifest():
    m, _ = casus("A", met_onderzoek=False)
    d = betekenis.dossier(m, None, ("e0",), ["herziening"])
    assert not d.met(betekenis.PARALLEL) and d.onderzoek_id == ""
    assert "alleen de bepalingen met de passages" in d.met("GEEN_DEFINITIE_GEVONDEN")[0].detail


def test_casus_b_de_kwalificatie_in_lid_7_is_een_samenstelling():
    m, o = casus("B")
    d = betekenis.dossier(m, o, ("e0", "e1"), ["belasting"])
    [s] = d.met(betekenis.SAMENGESTELD)
    assert s.bron_iris == (f"{B}:lid:7",) and "te betalen bedrag aan belasting" in s.detail
    # Voor de samenstelling zelf is lid 7 een kwalificatie binnen het bereik "dit artikel".
    [k] = d.met(betekenis.DEFINITIE)
    assert k.term == "te betalen bedrag aan belasting" and "alle passages binnen" in k.detail


def test_het_dossier_is_deterministisch_en_nooit_een_interpretatie():
    m, o = casus("A")
    een, twee = betekenis.dossier(m, o, ("e0",), ["herziening"]), betekenis.dossier(m, o, ("e0",), ["herziening"])
    assert een == twee and een.id == twee.id
    assert all(b.soort is not betekenis.Soort.INTERPRETATIE for b in een.bevindingen)
    # Elk genoemd fragment bestaat in de fragmentruimte van manifest + onderzoek.
    from agent.begrippen_pipeline import fragmenten
    ruimte = fragmenten.alle(m, o)
    assert all(f in ruimte for b in een.bevindingen for f in b.fragmenten)


def test_het_blok_noemt_context_bevindingen_en_vragen():
    m, o = casus("A")
    regels = betekenis.blok(betekenis.dossier(m, o, ("e0",), ["herziening"]))
    assert regels[0].startswith("ONDERZOCHTE CONTEXT: 7 bepalingen")
    assert any("PARALLELLE_BEPALINGEN" in r for r in regels) and any("OPEN VRAGEN" in r for r in regels)
    assert betekenis.blok(None)[0].startswith("ONDERZOCHTE CONTEXT: geen")


# --- de toetsen ------------------------------------------------------------------------------------

def _fr(iri: str, tekst: str) -> Fragment:
    s = NODES[iri]["tekst"].index(tekst)
    return Fragment(id=fragment_id(iri, s, s + len(tekst)), bron_iri=iri, start=s, eind=s + len(tekst), tekst=tekst)


def test_casus_a_een_toepassingsgeval_als_definitie_wordt_gemarkeerd():
    m, o = casus("A")
    d = betekenis.dossier(m, o, ("e0",), ["herziening"])
    fr = _fr(f"{A}:lid:4", "Bij herziening van een voorlopige aanslag inkomstenbelasting of vennootschapsbelasting "
                           "met een negatief bedrag tot een voorlopige aanslag met positief bedrag")
    slecht = Kaart(groep_id="G1", naam="herziening", herkomst=Herkomst.GEFORMULEERD, fragmenten=(fr,),
                   definitie="De wijziging van een voorlopige aanslag met een negatief bedrag tot een voorlopige "
                             "aanslag met een positief bedrag.")
    codes = toetsen.signalen(slecht, ["Rechtsfeit"], d)
    assert "ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE" in codes and "ONDERBOUWING_EEN_VOORKOMEN" in codes
    goed = slecht.model_copy(update={"definitie": "De wijziging van een voorlopige aanslag inkomstenbelasting of "
                                                  "vennootschapsbelasting in een andere voorlopige aanslag."})
    assert "ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE" not in toetsen.signalen(goed, ["Rechtsfeit"], d)


def test_casus_b_een_rechtsgevolg_in_de_definitie_en_tegenbewijs():
    m, o = casus("B")
    d = betekenis.dossier(m, o, ("e0", "e1"), ["belasting"])
    fr = _fr(f"{B}:lid:2", "De belastingrente wordt enkelvoudig berekend over het tijdvak dat aanvangt 6 maanden te "
                           "rekenen vanaf het einde van het tijdvak waarover de belasting wordt geheven en eindigt op de "
                           "dag voorafgaand aan de dag waarop de aanslag")
    kaart = Kaart(groep_id="G1", naam="belasting", herkomst=Herkomst.GEFORMULEERD, fragmenten=(fr,),
                  definitie="De inkomstenbelasting of vennootschapsbelasting die als grondslag voor de berekening van "
                            "belastingrente dient.")
    codes = toetsen.signalen(kaart, ["Rechtsobject"], d)
    assert {"RECHTSGEVOLG_IN_DEFINITIE", "TEGENBEWIJS_IN_ONDERZOEK"} <= set(codes)
    verrekening = kaart.model_copy(update={"definitie": "Het bedrag na de verrekening van de voorheffingen."})
    assert "AFLEIDING_IN_DEFINITIE" in toetsen.signalen(verrekening, ["Rechtsobject"], d)


def test_een_letterlijke_definitie_krijgt_geen_dossiersignalen_en_zonder_dossier_niets_nieuws():
    m, o = casus("B")
    d = betekenis.dossier(m, o, ("e0",), ["belasting"])
    letterlijk = Kaart(groep_id="G1", naam="te betalen bedrag aan belasting", herkomst=Herkomst.LETTERLIJK,
                       definitie="het bedrag na de verrekening ingevolge", definitie_bron_iri=f"{B}:lid:7")
    assert toetsen.signalen(letterlijk, ["Rechtsobject"], d) == []
    kaart = Kaart(groep_id="G1", naam="x", herkomst=Herkomst.GEFORMULEERD, definitie="grondslag voor iets",
                  fragmenten=(_fr(f"{B}:lid:7", "het bedrag na de verrekening ingevolge"),))
    assert toetsen.signalen(kaart, []) == ["DOOR_LEX_GEFORMULEERD"]


def test_de_garanties_gelden_over_manifest_en_onderzoek():
    m, o = casus("B")
    from agent.begrippen_pipeline import fragmenten
    fr = next(f for f in fragmenten.knip(o.bron(f"{B}:lid:7")) if f.tekst.startswith("het bedrag"))
    kaart = Kaart(groep_id="G1", naam="x", herkomst=Herkomst.SAMENGESTELD, definitie=fr.tekst, fragmenten=(fr,))
    assert toetsen.garanties(m, kaart) == ["FRAGMENT_ONBEKEND"]
    assert toetsen.garanties(m, kaart, o) == []
    vals = fr.model_copy(update={"tekst": "het bedrag na verrekening"})
    assert toetsen.garanties(m, kaart.model_copy(update={"fragmenten": (vals,), "definitie": vals.tekst}), o) == [
        "FRAGMENT_NIET_LETTERLIJK"]


# --- scherper met het dossier ----------------------------------------------------------------------

def _kant(m: Manifest) -> ka.Kant:
    return ka.Kant(id="b1", inhoud={"naam": "herziening"}, leden=("e0",))


def test_scherper_krijgt_het_dossier_en_de_context_en_bewaart_de_duiding():
    m, o = casus("A")
    frs = ka.fragmenten_voor(m, [_kant(m)], onderzoek=o)
    algemeen = next(f for f in frs if f.bron_iri == f"{A}:lid:1")
    llm = FakeLLM([response([tool_block("t", ka.TOOL_SCHERPER, {
        "herkomst": "geformuleerd", "fragmenten": [algemeen.id],
        "definitie": "De wijziging van een voorlopige aanslag inkomstenbelasting of vennootschapsbelasting in een "
                     "andere voorlopige aanslag.",
        "motivatie": "Alle leden delen de opening.", "soort": "begrip", "bereik": "algemeen", "voorkeursterm": "",
        "ontbreekt": ""})], "tool_use")])
    uit = ka.scherper(llm, "m", m, _kant(m), {}, o)
    [v] = uit.voorstellen
    assert v["duiding"] == {"soort": "begrip", "bereik": "algemeen", "voorkeursterm": "", "ontbreekt": ""}
    assert "ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE" not in v["aandachtspunten"]
    prompt = llm.calls[0]["messages"][0]["content"]
    assert "PARALLELLE_BEPALINGEN" in prompt and "OPEN VRAGEN" in prompt
    schema = llm.calls[0]["tools"][0]["input_schema"]
    assert {"soort", "bereik", "voorkeursterm", "ontbreekt"} <= set(schema["required"])


def test_scherper_ziet_af_met_een_reden():
    m, o = casus("A")
    frs = ka.fragmenten_voor(m, [_kant(m)], onderzoek=o)
    uit = ka.valideer_scherper(m, _kant(m), frs, {"herkomst": "geen", "fragmenten": [], "definitie": "",
                                                  "motivatie": "", "soort": "begrip", "bereik": "algemeen",
                                                  "voorkeursterm": "", "ontbreekt": "geen definitie in de wet"})
    assert uit.voorstellen == [] and uit.melding == "Onvoldoende bewijs: geen definitie in de wet"


def test_een_ongeldige_duiding_wordt_niet_geraden():
    assert betekenis.duiding_uit({"soort": "verzonnen"}) is None
    assert betekenis.duiding_uit({}).soort == "begrip"


# --- signalen in de keten --------------------------------------------------------------------------

def _taal(m: Manifest, term: str) -> dict[str, Taalanalyse]:
    return {f.element_id: Taalanalyse(element_id=f.element_id, kern=term, term=term) for f in m.formuleringen}


def test_een_berekening_op_de_term_maakt_zelfde_bepaling_een_vraag():
    tekst = "Het bijdrage-inkomen wordt verminderd met de aftrek. Over het bijdrage-inkomen is premie verschuldigd."
    b = Bron(bron_iri="urn:bwb:BWBR0018450:artikel:43:lid:3", tekst=tekst, bron_hash="h")
    s1, s2 = tekst.index("bijdrage-inkomen"), tekst.rindex("bijdrage-inkomen")
    m = Manifest(bronnen=(b,), formuleringen=(
        Formulering(element_id="a", bron_iri=b.bron_iri, start=s1, eind=s1 + 16, tekst="bijdrage-inkomen", jas_klasse="x"),
        Formulering(element_id="b", bron_iri=b.bron_iri, start=s2, eind=s2 + 16, tekst="bijdrage-inkomen", jas_klasse="x")))
    sig = signalen.zelfde_term(m, _taal(m, "bijdrage-inkomen"))
    assert [s.bewijs.code for s in sig] == ["ZELFDE_TERM", "ZELFDE_BEPALING", "BEREKENING_IN_BEPALING"]
    [besluit] = beslis_alle(_kandidaten(sig)).values()
    assert besluit.besluit is Besluit.POSSIBLE_LINK and besluit.regel == "Z-STERK-MET-TWIJFEL"


def test_een_contextdefinitie_verbindt_passages_binnen_haar_bereik():
    regeling = "urn:bwb:BWBR0000001"
    b1 = Bron(bron_iri=f"{regeling}:artikel:5:lid:1", tekst="De termijn loopt af.", bron_hash="1")
    b2 = Bron(bron_iri=f"{regeling}:artikel:6", tekst="Na de termijn volgt niets.", bron_hash="2")
    m = Manifest(bronnen=(b1, b2), formuleringen=(
        Formulering(element_id="a", bron_iri=b1.bron_iri, start=3, eind=10, tekst="termijn", jas_klasse="x"),
        Formulering(element_id="b", bron_iri=b2.bron_iri, start=6, eind=13, tekst="termijn", jas_klasse="x")))
    defbron = Contextbron(bron_iri=f"{regeling}:artikel:1", tekst="In deze wet wordt verstaan onder termijn: een "
                          "periode van zes weken.", bron_hash="d", rol=Rol.ONDERZOEK, reden=Reden.DEFINITIE_IN_REGELING)
    o = Onderzoek(manifest_id=m.id, bronnen=(defbron,))
    [s] = signalen.uit_contextdefinities(m, _taal(m, "termijn"), o)
    assert (s.bewijs.code, s.bewijs.bron_iri) == ("WETTELIJKE_TERM", defbron.bron_iri)
    assert signalen.uit_contextdefinities(m, _taal(m, "termijn"), None) == []
    smal = defbron.model_copy(update={"tekst": "Voor de toepassing van artikel 5 wordt verstaan onder termijn: zes weken."})
    [t] = signalen.uit_contextdefinities(m, _taal(m, "termijn"), Onderzoek(manifest_id=m.id, bronnen=(smal,)))
    assert t.bewijs.code == "BUITEN_BEREIK"
