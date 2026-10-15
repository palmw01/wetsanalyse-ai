"""De model-laag van de begrippenketen (spoor D, fase C): twijfelparen, concept-kaart, toetsen.

Geen echt model: `FakeLLM` speelt de tool-aanroepen af. Wat hier vastligt, zijn de garanties – het
model kiest alleen op id, een ongeldige keuze wordt onbeslist of "geen definitie", een regel-besluit
verandert nooit, en elke letterlijke of samengestelde tekst staat zo in de bron.
"""
from __future__ import annotations

import hashlib

import pytest

from agent.begrippen_pipeline import classificatie, fragmenten, kaart, keten, toetsen, verdieping
from agent.begrippen_pipeline.model import (
    Aandacht, Begripstype, Besluit, Bron, Formulering, Fragment, Herkomst, Kaart, Manifest, ModelOordeel,
    Oordeel, fragment_id,
)
from agent.jas_pipeline.taal.provider import NullProvider
from tests.fakes import FakeLLM, response, text_block, tool_block


def _h(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


A = "De ontvanger verzendt de aanslag binnen zes weken. Daarna volgt de betaling."
B = "Tegen de aanslag kan bezwaar worden gemaakt; de inspecteur beslist."
I1, I2 = "urn:bwb:BWBR1:artikel:1", "urn:bwb:BWBR2:artikel:4"


def _f(eid: str, iri: str, tekst: str, deel: str, klasse: str = "Rechtsobject") -> Formulering:
    s = tekst.index(deel)
    return Formulering(element_id=eid, bron_iri=iri, start=s, eind=s + len(deel), tekst=deel, jas_klasse=klasse)


@pytest.fixture
def manifest() -> Manifest:
    return Manifest(
        bronnen=(Bron(bron_iri=I1, tekst=A, bron_hash=_h(A), label="art. 1 X", regeling="BWBR1"),
                 Bron(bron_iri=I2, tekst=B, bron_hash=_h(B), label="art. 4 Y", regeling="BWBR2")),
        formuleringen=(_f("e1", I1, A, "de aanslag"), _f("e2", I2, B, "de aanslag"),
                       _f("e3", I1, A, "De ontvanger", "Rechtssubject")))


@pytest.fixture
def uitkomst(manifest):
    return keten.analyseer(manifest, NullProvider())


def _antwoord(tool: str, sleutel: str, items: list[dict]) -> object:
    return response([tool_block("t1", tool, {sleutel: items})], "tool_use")


# --- twijfelparen ------------------------------------------------------------------------------

def test_er_is_een_twijfelpaar_en_geen_groep(uitkomst):
    assert [v.regel for v in uitkomst.vragen] == ["Z-ANDERS"] and not uitkomst.groepen


def test_het_schema_laat_alleen_bestaande_paren_en_uitkomsten_toe(uitkomst):
    schema = classificatie.toolschema(list(uitkomst.vragen))
    item = schema["input_schema"]["properties"]["oordelen"]["items"]["properties"]
    assert item["paar"]["enum"] == [uitkomst.vragen[0].kandidaat_id]
    assert set(item["uitkomst"]["enum"]) == {o.value for o in Oordeel}
    assert schema["strict"] is True


def test_de_prompt_draagt_de_bronzin_en_de_verklaring_van_het_signaal(manifest, uitkomst):
    p = classificatie.userprompt(manifest, list(uitkomst.vragen))
    assert "De ontvanger verzendt [[de aanslag]] binnen zes weken." in p
    assert "Tegen [[de aanslag]] kan bezwaar worden gemaakt;" in p
    assert "Alleen een aanleiding om te vergelijken" in p          # verklaring van ZELFDE_TERM


@pytest.mark.parametrize("items, reden", [
    (None, "MODEL_GEEN_UITVOER"),
    ([], "MODEL_OMITTED"),
    ([{"paar": "Pander", "uitkomst": "zelfde_betekenis", "motivatie": ""}], "MODEL_OMITTED"),
    ([{"paar": "{id}", "uitkomst": "misschien", "motivatie": ""}], "MODEL_ONGELDIGE_UITKOMST:misschien"),
])
def test_ongeldige_uitvoer_wordt_onbeslist_met_reden(uitkomst, items, reden):
    vid = uitkomst.vragen[0].kandidaat_id
    if items:
        items = [{**i, "paar": i["paar"].replace("{id}", vid)} for i in items]
    [o] = classificatie.valideer(list(uitkomst.vragen), items)
    assert (o.oordeel, o.reden) == (Oordeel.ONBESLIST, reden)


def test_zonder_tool_aanroep_een_tweede_poging_dan_onbeslist(manifest, uitkomst):
    llm = FakeLLM([response([text_block("hm")], "end_turn")] * 2)
    [o] = classificatie.vergelijk(llm, "m", manifest, list(uitkomst.vragen))
    assert len(llm.calls) == 2 and o.reden == "MODEL_GEEN_UITVOER"


def test_zelfde_betekenis_van_het_model_maakt_een_gele_groep(manifest, uitkomst):
    vid = uitkomst.vragen[0].kandidaat_id
    her = verdieping.hergroepeer(manifest, uitkomst, [
        ModelOordeel(kandidaat_id=vid, oordeel=Oordeel.ZELFDE_BETEKENIS, motivatie="Beide de belastingaanslag.")])
    [g] = her.groepen
    assert g.leden == ("e1", "e2") and g.aandacht is Aandacht.GEEL
    assert any("Lex: Beide de belastingaanslag." in r for r in g.uitleg)
    assert not her.vragen


@pytest.mark.parametrize("oordeel", [Oordeel.BETEKENISVERSCHIL, Oordeel.VERWANT_ANDER_BEGRIP])
def test_een_verschil_van_het_model_laat_de_vraag_staan_met_advies(manifest, uitkomst, oordeel):
    """Een foute scheiding mag niet onzichtbaar worden: de jurist houdt de vraag."""
    vid = uitkomst.vragen[0].kandidaat_id
    her = verdieping.hergroepeer(manifest, uitkomst, [ModelOordeel(kandidaat_id=vid, oordeel=oordeel)])
    assert not her.groepen and [v.kandidaat_id for v in her.vragen] == [vid]
    assert [o.oordeel for o in her.oordelen] == [oordeel]


def test_onbeslist_laat_de_vraag_staan(manifest, uitkomst):
    vid = uitkomst.vragen[0].kandidaat_id
    her = verdieping.hergroepeer(manifest, uitkomst, [ModelOordeel(kandidaat_id=vid, oordeel=Oordeel.ONBESLIST)])
    assert [v.kandidaat_id for v in her.vragen] == [vid]


def test_het_model_raakt_een_regelbesluit_nooit_aan(manifest, uitkomst):
    """Een oordeel over een kandidaat die geen vraag is (of niet bestaat) verandert niets."""
    andere = [b for b in uitkomst.beslissingen if b.besluit is not Besluit.POSSIBLE_LINK]
    oordelen = [ModelOordeel(kandidaat_id=b.kandidaat_id, oordeel=Oordeel.ZELFDE_BETEKENIS) for b in andere]
    oordelen.append(ModelOordeel(kandidaat_id="Pbestaatniet", oordeel=Oordeel.ZELFDE_BETEKENIS))
    her = verdieping.hergroepeer(manifest, uitkomst, oordelen)
    assert her.groepen == uitkomst.groepen and her.vragen == uitkomst.vragen


def test_een_wettelijke_relatie_gaat_niet_naar_het_model(uitkomst):
    vraag = uitkomst.vragen[0].model_copy(update={"regel": "Z-RELATIE-GAAT-VOOR"})
    gewijzigd = uitkomst.__class__(**{**uitkomst.__dict__, "vragen": (vraag,)})
    assert verdieping.te_vergelijken(gewijzigd) == []


def test_batches_zijn_stabiel(uitkomst):
    vragen = list(uitkomst.vragen) * 1
    assert classificatie.batches(vragen) == classificatie.batches(list(reversed(vragen)))
    a = verdieping.batch_id("vraag", ["P2", "P1"], "v", "m")
    assert a == verdieping.batch_id("vraag", ["P1", "P2"], "v", "m")
    assert a != verdieping.batch_id("vraag", ["P1", "P2"], "v", "ander-model")


# --- fragmenten --------------------------------------------------------------------------------

def test_fragmenten_zijn_letterlijk_en_breken_niet_op_afkortingen():
    t = "Onder aanslag wordt verstaan: de aanslag als bedoeld in art. 2 AWR; ook de navordering. Klaar."
    b = Bron(bron_iri=I1, tekst=t, bron_hash=_h(t))
    frs = fragmenten.knip(b)
    assert [f.tekst for f in frs] == ["Onder aanslag wordt verstaan", "de aanslag als bedoeld in art. 2 AWR",
                                      "ook de navordering", "Klaar"]
    assert all(t[f.start:f.eind] == f.tekst and f.id == fragment_id(I1, f.start, f.eind) for f in frs)


# --- de concept-kaart --------------------------------------------------------------------------

def _opdracht(manifest, uitkomst):
    her = verdieping.hergroepeer(manifest, uitkomst, [
        ModelOordeel(kandidaat_id=uitkomst.vragen[0].kandidaat_id, oordeel=Oordeel.ZELFDE_BETEKENIS)])
    kaarten, opdrachten = verdieping.kaartopdrachten(manifest, uitkomst, her.groepen)
    [o] = opdrachten
    return kaarten[o.kaart.groep_id], o


def test_de_basiskaart_zonder_model(manifest, uitkomst):
    k, o = _opdracht(manifest, uitkomst)
    assert k.naam == "aanslag" and k.begripstype is Begripstype.ENTITEIT and k.begripstype_door == "regel"
    assert k.context == "Komt voor in art. 1 X; art. 4 Y."
    assert k.definitie == "" and "GEEN_DEFINITIE" in k.aandachtspunten and k.aandacht is Aandacht.GEEL
    assert o.fragmenten and not o.type_open


def test_samengesteld_is_alleen_brontekst_wat_het_model_ook_typt(manifest, uitkomst):
    k, o = _opdracht(manifest, uitkomst)
    fr = next(f for f in o.fragmenten if f.tekst.startswith("Tegen de aanslag"))
    [uit] = kaart.valideer(manifest, [o], [{"groep": k.groep_id, "herkomst": "samengesteld", "fragmenten": [fr.id],
                                             "definitie": "verzonnen tekst", "begripstype": "", "motivatie": "m"}],
                           {k.groep_id: True})
    assert uit.herkomst is Herkomst.SAMENGESTELD and uit.definitie == fr.tekst
    assert toetsen.garanties(manifest, uit) == []


def test_geformuleerd_is_geel_en_noemt_zijn_fragmenten(manifest, uitkomst):
    k, o = _opdracht(manifest, uitkomst)
    fr = o.fragmenten[0]
    [uit] = kaart.valideer(manifest, [o], [{"groep": k.groep_id, "herkomst": "geformuleerd", "fragmenten": [fr.id],
                                             "definitie": "Een beschikking die een belastingschuld vaststelt.",
                                             "begripstype": "", "motivatie": "m"}], {k.groep_id: False})
    assert uit.herkomst is Herkomst.GEFORMULEERD and uit.fragmenten == (fr,) and uit.aandacht is Aandacht.GEEL
    assert "DOOR_LEX_GEFORMULEERD" in uit.aandachtspunten


@pytest.mark.parametrize("item", [
    {"herkomst": "geformuleerd", "fragmenten": [], "definitie": "Iets."},          # zonder onderbouwing
    {"herkomst": "geformuleerd", "fragmenten": ["{fr}"], "definitie": "  "},      # leeg
    {"herkomst": "samengesteld", "fragmenten": ["Fbestaatniet"], "definitie": ""},  # onbekend fragment
    {"herkomst": "samengesteld", "fragmenten": ["{fr}", "{fr}"], "definitie": ""},  # dubbel
    {"herkomst": "geen", "fragmenten": [], "definitie": ""},
])
def test_zonder_bruikbaar_voorstel_geen_definitie(manifest, uitkomst, item):
    k, o = _opdracht(manifest, uitkomst)
    item = {"groep": k.groep_id, "begripstype": "", "motivatie": "m",
            **{x: ([v.replace("{fr}", o.fragmenten[0].id) for v in y] if isinstance(y, list) else y)
               for x, y in item.items()}}
    [uit] = kaart.valideer(manifest, [o], [item], {k.groep_id: True})
    assert uit.definitie == "" and uit.herkomst is None and "MODEL_GEEN_DEFINITIE" in uit.aandachtspunten


def test_een_ontbrekende_groep_houdt_de_basiskaart(manifest, uitkomst):
    k, o = _opdracht(manifest, uitkomst)
    [uit] = kaart.valideer(manifest, [o], None, {k.groep_id: True})
    assert uit.definitie == "" and "MODEL_GEEN_DEFINITIE" in uit.aandachtspunten


def test_het_begripstype_kiest_het_model_alleen_als_het_open_is(manifest, uitkomst):
    k, o = _opdracht(manifest, uitkomst)
    item = {"groep": k.groep_id, "herkomst": "geen", "fragmenten": [], "definitie": "", "begripstype": "actor",
            "motivatie": ""}
    [dicht] = kaart.valideer(manifest, [o], [item], {k.groep_id: True})
    assert dicht.begripstype is Begripstype.ENTITEIT
    open_ = kaart.Opdracht(k.model_copy(update={"begripstype": None, "begripstype_door": ""}), o.leden,
                           o.fragmenten, True)
    [gekozen] = kaart.valideer(manifest, [open_], [item], {k.groep_id: True})
    assert (gekozen.begripstype, gekozen.begripstype_door) == (Begripstype.ACTOR, "model")


def test_letterlijk_uit_een_begripsbepaling_zonder_model():
    aanhef, t = "Deze wet verstaat onder:", "aanslag: de beschikking waarbij de belasting wordt vastgesteld;"
    t2 = "De aanslag wordt binnen drie jaar vastgesteld."
    iri, iri2 = "urn:bwb:BWBR1:artikel:1:o:a", "urn:bwb:BWBR1:artikel:5"
    m = Manifest(bronnen=(Bron(bron_iri=iri, tekst=t, bron_hash=_h(t), aanhef=aanhef, label="art. 1 a"),
                          Bron(bron_iri=iri2, tekst=t2, bron_hash=_h(t2), label="art. 5")),
                 formuleringen=(_f("d1", iri, t, "aanslag", "Brondefinitie"), _f("d2", iri2, t2, "De aanslag")))
    u = keten.analyseer(m, NullProvider())
    [g] = u.groepen
    kaarten, opdrachten = verdieping.kaartopdrachten(m, u, u.groepen)
    k = kaarten[g.id]
    assert k.herkomst is Herkomst.LETTERLIJK and k.definitie == "de beschikking waarbij de belasting wordt vastgesteld"
    assert toetsen.garanties(m, k) == [] and opdrachten == []
    assert k.aandacht is (Aandacht.GROEN if g.aandacht is Aandacht.GROEN else Aandacht.GEEL)


# --- toetsen -----------------------------------------------------------------------------------

def test_garanties_vangen_een_gefingeerd_of_verschoven_fragment(manifest):
    echt = fragmenten.knip(manifest.bron(I1))[0]
    nep = Fragment(id=fragment_id(I1, 0, 5), bron_iri=I1, start=0, eind=5, tekst="De on")
    scheef = echt.model_copy(update={"tekst": echt.tekst.upper()})
    for fr, code in ((nep, "FRAGMENT_ONBEKEND"), (scheef, "FRAGMENT_NIET_LETTERLIJK")):
        k = Kaart(groep_id="G1", naam="x", definitie=fr.tekst, herkomst=Herkomst.SAMENGESTELD, fragmenten=(fr,))
        assert code in toetsen.garanties(manifest, k)


def test_een_letterlijke_definitie_die_niet_in_de_bron_staat(manifest):
    k = Kaart(groep_id="G1", naam="x", definitie="niet in de bron", herkomst=Herkomst.LETTERLIJK,
              definitie_bron_iri=I1)
    assert toetsen.garanties(manifest, k) == ["LETTERLIJK_NIET_IN_BRON"]


@pytest.mark.parametrize("definitie, klassen, code", [
    ("De aanslag die is opgelegd.", ["Rechtsobject"], "CIRCULAIR"),
    ("Het bedrag bedraagt 5% van de schuld.", ["Rechtsobject"], "REKENREGEL"),
    ("Een beschikking.", ["Rechtsobject", "Rechtssubject"], "GEMENGDE_KLASSEN"),
    ("Zes weken.", ["Tijdsaanduiding"], "GEEN_BEGRIP"),
])
def test_signalen(definitie, klassen, code):
    k = Kaart(groep_id="G1", naam="aanslag", definitie=definitie, herkomst=Herkomst.GEFORMULEERD,
              fragmenten=(Fragment(id=fragment_id(I1, 0, 3), bron_iri=I1, start=0, eind=3, tekst="De "),))
    assert code in toetsen.signalen(k, klassen)


def test_elke_toetscode_heeft_een_tekst_en_omgekeerd():
    import inspect
    import re
    bron = inspect.getsource(kaart) + inspect.getsource(toetsen)
    zonder_tabel = bron.replace(bron[bron.index("TEKST: dict"):bron.index("GARANTIES =")], "")
    codes = set(re.findall(r'"([A-Z]{4,}(?:_[A-Z]+)*)"', zonder_tabel))
    assert codes == set(toetsen.TEKST)


def test_een_geformuleerde_kaart_kan_niet_groen_zijn():
    fr = Fragment(id=fragment_id(I1, 0, 3), bron_iri=I1, start=0, eind=3, tekst="De ")
    with pytest.raises(ValueError):
        Kaart(groep_id="G1", naam="x", definitie="d", herkomst=Herkomst.GEFORMULEERD, fragmenten=(fr,),
              aandacht=Aandacht.GROEN)


# --- alles samen -------------------------------------------------------------------------------

def test_verdiep_doorloopt_vraag_en_kaart(manifest, uitkomst):
    vid = uitkomst.vragen[0].kandidaat_id

    class Script(FakeLLM):
        def create(self, **kw):
            self._leg_vast(kw)
            if kw["tools"][0]["name"] == classificatie.TOOL:
                return _antwoord(classificatie.TOOL, "oordelen",
                                 [{"paar": vid, "uitkomst": "zelfde_betekenis", "motivatie": "Zelfde aanslag."}])
            groep = kw["tools"][0]["input_schema"]["properties"]["kaarten"]["items"]["properties"]["groep"]["enum"][0]
            fr = kw["tools"][0]["input_schema"]["properties"]["kaarten"]["items"]["properties"]["fragmenten"]["items"]["enum"][0]
            return _antwoord(kaart.TOOL, "kaarten", [{"groep": groep, "herkomst": "geformuleerd", "fragmenten": [fr],
                                                      "definitie": "Een beschikking tot betaling.",
                                                      "begripstype": "", "motivatie": "m"}])

    llm = Script([])
    v = verdieping.verdiep(manifest, uitkomst, llm, "m")
    [g] = v.hergroepering.groepen
    assert v.kaarten[g.id].herkomst is Herkomst.GEFORMULEERD and v.meting["llm_calls"] == 2
    assert all(toetsen.garanties(manifest, k) == [] for k in v.kaarten.values())


def test_het_meetharnas_zonder_bruikbaar_model_meet_de_keten():
    """Offline: een model dat nooit de tool aanroept, laat alles zoals de keten het zag."""
    pytest.importorskip("spacy")
    from eval import begrippen_eval as be
    llm = FakeLLM([response([text_block("geen")], "end_turn")] * 200)
    r = be.meet_model(be.ACTUELE_VERSIE, 1, llm, "nep")
    [run] = r["runs"]
    assert run["bcubed"] == r["zonder_model"]["bcubed"] and run["garantiefouten"] == 0
    assert run["samengevoegd_verschillend"] == []
    assert "Begrippenketen + model" in be.rapport_model(r)


def test_signalen_bekritiseren_de_wet_niet():
    k = Kaart(groep_id="G1", naam="onze minister", definitie="Onze Minister van Financiën",
              herkomst=Herkomst.LETTERLIJK, definitie_bron_iri=I1)
    assert toetsen.signalen(k, ["Rechtssubject"]) == []
    jaar = k.model_copy(update={"naam": "berekeningsjaar", "definitie": "het kalenderjaar"})
    assert toetsen.signalen(jaar, ["Tijdsaanduiding"]) == []


def test_een_geformuleerde_cirkel_wordt_niet_overgenomen(manifest, uitkomst):
    k, o = _opdracht(manifest, uitkomst)
    [uit] = kaart.valideer(manifest, [o], [{"groep": k.groep_id, "herkomst": "geformuleerd",
                                             "fragmenten": [o.fragmenten[0].id],
                                             "definitie": "Een aanslag is een aanslag als bedoeld in de wet.",
                                             "begripstype": "", "motivatie": "m"}], {k.groep_id: True})
    assert uit.definitie == "" and "CIRCULAIR_VERWORPEN" in uit.aandachtspunten
