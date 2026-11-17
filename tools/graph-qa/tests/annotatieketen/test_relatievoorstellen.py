"""Relatievoorstellen van de keten (ADR-011, `jas_pipeline/relaties.py`): vier regels, geen model.

Per code vier testsoorten, zoals bij de detectorregels (ADR-001): positief, negatief, rand en overlap. De zinnen zijn
zelf bedacht. Regels 1–3 lezen alleen kandidaten, bewijs en nesting; die bouwen we hier met de hand, zodat de test
precies één regel raakt. Regel 4 leest de zinsontleding en draait daarom op het echte spaCy-model (anders overgeslagen).
"""
from __future__ import annotations

import json

import pytest
from bronmodel import CorpusMap, Span, tekst_hash

from agent.config import Settings
from agent.jas_pipeline import relaties as R
from agent.jas_pipeline.fusie import Fusie, relaties as nesting
from agent.jas_pipeline.kandidaten import Candidate, Evidence, label_kandidaten
from agent.jas_pipeline.keten import analyseer
from agent.jas_pipeline.taal import NullProvider, SpacyProvider
from agent.jas_relaties import toegestaan
from eval.onderzoek_invordering import KeuzeFake

IRI = "urn:test:lid:1"
AR, VW, OP, RB, RF = "Afleidingsregel", "Voorwaarde", "Operator", "Rechtsbetrekking", "Rechtsfeit"
VAR, PAR, TIJD, RS, RO = ("Variabele en variabelewaarde", "Parameter en parameterwaarde", "Tijdsaanduiding",
                          "Rechtssubject", "Rechtsobject")


@pytest.fixture(scope="module")
def parser():
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd (uv sync --extra nlp)")
    return p


class Zin:
    """Eén bepaling met met de hand gekozen markeringen: `markeer(fragment, klasse, …)` maakt kandidaat én voorstel."""

    def __init__(self, tekst: str, analyse=None):
        self.tekst, self.analyse = tekst, analyse
        self.kandidaten: dict[str, Candidate] = {}
        self.voorstellen: list[dict] = []

    def span(self, fragment: str, nde: int = 1) -> Span:
        start = -1
        for _ in range(nde):
            start = self.tekst.index(fragment, start + 1)
        return Span(IRI, start, start + len(fragment), fragment, tekst_hash(self.tekst))

    def markeer(self, fragment: str, klasse: str, subtype: str = "", *, nde: int = 1, code: str = "TEST",
                detail: str = "") -> dict:
        span = self.span(fragment, nde)
        k = self.kandidaten.get(fragment) or Candidate.maak(span, [klasse], [Evidence(detector="test", code=code,
                                                                                       detail=detail)])
        self.kandidaten[fragment] = k
        v = {"id": f"{klasse[:3]}:{fragment}", "klasse": klasse, "jas_subtype": subtype, "tekst": fragment,
             "ankers": [span.anker()], "trace": {"kandidaat": {"id": k.id}}}
        self.voorstellen.append(v)
        return v

    def aantal(self, regel: str, uitkomst: str, invoer: str) -> str:
        """Het bewijs dat de functiedetector bij 'zoveel … als …' geeft: de spans van uitkomst en invoer."""
        def s(fragment):
            sp = self.span(fragment)
            return {"start": sp.start, "eind": sp.eind, "tekst": fragment}
        return json.dumps({"uitkomst": s(uitkomst), "invoer": s(invoer)}, sort_keys=True)

    def voorstel(self) -> list[dict]:
        ks = label_kandidaten(list(self.kandidaten.values()))
        fusie = Fusie(kandidaten=ks, relaties=nesting(ks))
        return R.stel_voor(self.voorstellen, fusie, {IRI: self.analyse})


def kort(relaties: list[dict]) -> set[tuple]:
    """(type, tekst van, tekst naar, volgorde)."""
    return {(r["type"], r["van_ankers"][0]["tekst"], r["naar_ankers"][0]["tekst"], r["volgorde"]) for r in relaties}


# --- 1. uitvoer en invoer uit de functiedetector -------------------------------------------------------------------

AANTAL = "Er worden zoveel termijnen in rekening gebracht als er volle maanden overblijven."
AR_SPAN = "zoveel termijnen in rekening gebracht als er volle maanden overblijven"
UITKOMST, INVOER = "termijnen in rekening gebracht", "er volle maanden overblijven"


def _aantal(code="CALCULATION_QUANTITY") -> Zin:
    z = Zin(AANTAL)
    z.markeer(AR_SPAN, AR, code=code, detail=z.aantal(AR_SPAN, UITKOMST, INVOER) if code == "CALCULATION_QUANTITY" else "")
    return z


def uitvoer_positief():
    z = _aantal()
    z.markeer("zoveel termijnen", VAR)
    z.markeer("volle maanden", VAR)
    assert ("uitvoer", AR_SPAN, "zoveel termijnen", None) in kort(z.voorstel())


def uitvoer_negatief():
    # Zonder het bewijs van de functiedetector geen uitvoer; en een rechtsbetrekking is geen uitvoer (catalogus).
    z = _aantal(code="CALCULATION_PASSIVE")
    z.markeer("zoveel termijnen", VAR)
    assert not z.voorstel()
    z = _aantal()
    z.markeer("termijnen in rekening gebracht", RB)
    assert not [r for r in z.voorstel() if r["type"] == "uitvoer"]


def uitvoer_rand():
    # Geneste markeringen zijn geen twijfel: de binnenste raakt de span het scherpst. Een markering buiten de regel
    # telt niet, ook al overlapt ze de span.
    z = _aantal()
    z.markeer("zoveel termijnen", VAR)
    z.markeer("termijnen", VAR)
    z.markeer("Er worden zoveel termijnen", RO)
    assert {r[2] for r in kort(z.voorstel()) if r[0] == "uitvoer"} == {"termijnen"}


def uitvoer_overlap():
    # Twee markeringen naast elkaar op de uitkomst: twijfel, dus geen uitvoer. Een markering over uitkomst én invoer
    # hoort bij geen van beide.
    z = _aantal()
    z.markeer("zoveel termijnen", VAR)
    z.markeer("rekening", RO)
    z.markeer("gebracht als er volle", VAR)
    assert not [r for r in z.voorstel() if r["type"] in ("uitvoer", "invoer")]


def invoer_positief():
    z = _aantal()
    z.markeer("volle maanden", VAR)
    assert kort(z.voorstel()) == {("invoer", "volle maanden", AR_SPAN, None)}


def invoer_negatief():
    # Een operator is geen invoer (catalogus); een markering op de uitkomst evenmin.
    z = _aantal()
    z.markeer("overblijven", OP)
    z.markeer("termijnen", VAR)
    assert not [r for r in z.voorstel() if r["type"] == "invoer"]


def invoer_rand():
    # De bijzin eromheen telt niet naast de variabele erbinnen; 'als' grenst aan de invoer zonder hem te overlappen.
    z = _aantal()
    z.markeer("als er volle maanden overblijven", VW)
    z.markeer("volle maanden", VAR)
    z.markeer("gebracht als", VAR)
    assert {r[1] for r in kort(z.voorstel()) if r[0] == "invoer"} == {"volle maanden"}


def invoer_overlap():
    # Twee markeringen naast elkaar op de invoer zijn twee invoeren, zonder volgorde.
    z = _aantal()
    z.markeer("er", VAR, nde=2)
    z.markeer("volle maanden", VAR)
    gevonden = {r for r in kort(z.voorstel()) if r[0] == "invoer"}
    assert gevonden == {("invoer", "er", AR_SPAN, None), ("invoer", "volle maanden", AR_SPAN, None)}


# --- 2. waarde -----------------------------------------------------------------------------------------------------

TERMIJN = "De aanvraag wordt binnen 48 uur behandeld tegen een inkomen van 30.000 euro."


def waarde_positief():
    z = Zin(TERMIJN)
    z.markeer("binnen 48 uur", TIJD, "verbijzondert parameter")
    z.markeer("48", PAR, "parameterwaarde")
    z.markeer("een inkomen van 30.000 euro", VAR, "variabele")
    z.markeer("30.000 euro", VAR, "variabelewaarde")
    assert kort(z.voorstel()) == {("waarde", "48", "binnen 48 uur", None),
                                  ("waarde", "30.000 euro", "een inkomen van 30.000 euro", None)}


def waarde_negatief():
    # Zonder het subtype dat het verband draagt geen waarde: een kale tijdsaanduiding, een getal zonder subtype, of een
    # variabelewaarde in een parameter.
    z = Zin(TERMIJN)
    z.markeer("binnen 48 uur", TIJD)
    z.markeer("48", PAR, "parameterwaarde")
    z.markeer("een inkomen van 30.000 euro", PAR, "parameter")
    z.markeer("30.000 euro", VAR, "variabelewaarde")
    assert not z.voorstel()
    z = Zin(TERMIJN)
    z.markeer("binnen 48 uur", TIJD, "verbijzondert parameter")
    z.markeer("48", PAR)
    assert not z.voorstel()


def waarde_rand():
    # Twee tijdsaanduidingen om hetzelfde getal: alleen de binnenste is de grootheid.
    z = Zin(TERMIJN)
    z.markeer("binnen 48 uur", TIJD, "verbijzondert parameter")
    z.markeer("48 uur", TIJD, "verbijzondert parameter")
    z.markeer("48", PAR, "parameterwaarde")
    assert kort(z.voorstel()) == {("waarde", "48", "48 uur", None)}


def waarde_overlap():
    # Twee even kleine ouders (dezelfde span, twee klassen): twijfel, geen voorstel.
    z = Zin(TERMIJN)
    z.markeer("48 uur", TIJD, "verbijzondert parameter")
    z.markeer("48 uur", PAR, "parameter")
    z.markeer("48", PAR, "parameterwaarde")
    assert not z.voorstel()


# --- 3. operator en operanden --------------------------------------------------------------------------------------

DREMPEL = "Indien het inkomen meer bedraagt dan de drempel, is de aanvrager een bijdrage verschuldigd."
VOORW = "Indien het inkomen meer bedraagt dan de drempel"


def _drempel() -> Zin:
    z = Zin(DREMPEL)
    z.markeer(VOORW, VW)
    z.markeer("meer bedraagt dan", OP)
    return z


def operator_in_positief():
    assert ("operator_in", "meer bedraagt dan", VOORW, None) in kort(_drempel().voorstel())


def operator_in_negatief():
    # Een operator in een rechtsbetrekking krijgt geen ouder, en dus ook geen operanden.
    z = Zin(DREMPEL)
    z.markeer(DREMPEL, RB)
    z.markeer("meer bedraagt dan", OP)
    z.markeer("het inkomen", VAR)
    assert not z.voorstel()


def operator_in_rand():
    # Een voorwaarde binnen een afleidingsregel: de binnenste ouder gebruikt de operator.
    z = _drempel()
    z.markeer(DREMPEL.rstrip("."), AR)
    assert {r for r in kort(z.voorstel()) if r[0] == "operator_in"} == {("operator_in", "meer bedraagt dan", VOORW, None)}


def operator_in_overlap():
    # Dezelfde span als voorwaarde én als afleidingsregel: welke ouder? Twijfel, geen voorstel.
    z = _drempel()
    z.markeer(VOORW, AR)
    z.markeer("het inkomen", VAR)
    assert not z.voorstel()


def operand_positief():
    z = _drempel()
    z.markeer("het inkomen", VAR)
    z.markeer("de drempel", PAR, "parameter")
    assert {r for r in kort(z.voorstel()) if r[0] == "operand"} == {
        ("operand", "het inkomen", "meer bedraagt dan", 1), ("operand", "de drempel", "meer bedraagt dan", 2)}


def operand_negatief():
    # Een brondefinitie is geen operand (catalogus); wat buiten de voorwaarde staat evenmin.
    z = _drempel()
    z.markeer("de drempel", "Brondefinitie")
    z.markeer("de aanvrager", RS)
    assert not [r for r in z.voorstel() if r["type"] == "operand"]


def operand_rand():
    # Van twee markeringen die even dicht bij de operator eindigen telt de volle groep.
    z = _drempel()
    z.markeer("het inkomen", VAR)
    z.markeer("inkomen", VAR)
    assert {r for r in kort(z.voorstel()) if r[0] == "operand"} == {("operand", "het inkomen", "meer bedraagt dan", 1)}


def operand_overlap():
    # Twee operatoren: de korting staat tussen beide en is van allebei operand; het inkomen alleen van de eerste,
    # want er staat een operator tussen hem en de tweede.
    tekst = "Indien het inkomen verminderd met de korting meer bedraagt dan de drempel, is een bijdrage verschuldigd."
    z = Zin(tekst)
    z.markeer("Indien het inkomen verminderd met de korting meer bedraagt dan de drempel", VW)
    for fragment, klasse in (("verminderd met", OP), ("meer bedraagt dan", OP), ("het inkomen", VAR),
                             ("de korting", VAR), ("de drempel", PAR)):
        z.markeer(fragment, klasse)
    assert {r for r in kort(z.voorstel()) if r[0] == "operand"} == {
        ("operand", "het inkomen", "verminderd met", 1), ("operand", "de korting", "verminderd met", 2),
        ("operand", "de korting", "meer bedraagt dan", 1), ("operand", "de drempel", "meer bedraagt dan", 2)}


# --- 4. voorwaarde -------------------------------------------------------------------------------------------------

VERGUNNING = "De gemeente verleent een vergunning, indien de aanvrager een verklaring overlegt."


def voorwaarde_positief(parser):
    z = Zin(VERGUNNING, parser.analyseer(VERGUNNING))
    z.markeer("De gemeente verleent een vergunning", RB)
    z.markeer("indien de aanvrager een verklaring overlegt", VW)
    r, = z.voorstel()
    assert kort([r]) == {("voorwaarde", "De gemeente verleent een vergunning",
                          "indien de aanvrager een verklaring overlegt", None)}
    assert r["spoor"]["detail"]["ud_pad"] == "advcl+mark→root" and r["spoor"]["detail"]["predicaat"] == "verleent"


def voorwaarde_negatief(parser):
    # Een redengevende bijzin is geen voorwaarde-aanhechting; zonder zinsontleding komt er niets.
    tekst = "De gemeente verleent een vergunning, omdat de aanvrager een verklaring overlegt."
    z = Zin(tekst, parser.analyseer(tekst))
    z.markeer("De gemeente verleent een vergunning", RB)
    z.markeer("omdat de aanvrager een verklaring overlegt", VW)
    assert not z.voorstel()
    z = Zin(VERGUNNING, NullProvider().analyseer(VERGUNNING))
    z.markeer("De gemeente verleent een vergunning", RB)
    z.markeer("indien de aanvrager een verklaring overlegt", VW)
    assert not z.voorstel()


def voorwaarde_rand(parser):
    # Het predicaat wordt gedragen door een rechtsfeit, niet door een rechtsbetrekking of regel: geen drager.
    z = Zin(VERGUNNING, parser.analyseer(VERGUNNING))
    z.markeer("De gemeente verleent een vergunning", RF)
    z.markeer("indien de aanvrager een verklaring overlegt", VW)
    assert not z.voorstel()


def voorwaarde_overlap(parser):
    # Twee dragers om hetzelfde predicaat (de norm en de hele zin als afleidingsregel): twijfel, geen voorstel.
    z = Zin(VERGUNNING, parser.analyseer(VERGUNNING))
    z.markeer("De gemeente verleent een vergunning", RB)
    z.markeer(VERGUNNING.rstrip("."), AR)
    z.markeer("indien de aanvrager een verklaring overlegt", VW)
    assert not [r for r in z.voorstel() if r["type"] == "voorwaarde"]


GEVALLEN = {
    R.REL_UITVOER_FUNCTIE: (uitvoer_positief, uitvoer_negatief, uitvoer_rand, uitvoer_overlap),
    R.REL_INVOER_FUNCTIE: (invoer_positief, invoer_negatief, invoer_rand, invoer_overlap),
    R.REL_WAARDE_NESTING: (waarde_positief, waarde_negatief, waarde_rand, waarde_overlap),
    R.REL_OPERATOR_IN_NESTING: (operator_in_positief, operator_in_negatief, operator_in_rand, operator_in_overlap),
    R.REL_OPERAND_WOORDVOLGORDE: (operand_positief, operand_negatief, operand_rand, operand_overlap),
    R.REL_VOORWAARDE_AANHECHTING: (voorwaarde_positief, voorwaarde_negatief, voorwaarde_rand, voorwaarde_overlap),
}
SOORTEN = ("positief", "negatief", "rand", "overlap")


def test_elke_regel_heeft_vier_testsoorten():
    assert set(GEVALLEN) == set(R.CODES)
    for code, gevallen in GEVALLEN.items():
        assert [g.__name__.rsplit("_", 1)[1] for g in gevallen] == list(SOORTEN), code


@pytest.mark.parametrize("geval", [g for code in R.CODES if code != R.REL_VOORWAARDE_AANHECHTING
                                   for g in GEVALLEN[code]], ids=lambda g: g.__name__)
def test_regel_zonder_zinsontleding(geval):
    geval()


@pytest.mark.parametrize("geval", GEVALLEN[R.REL_VOORWAARDE_AANHECHTING], ids=lambda g: g.__name__)
def test_regel_met_zinsontleding(geval, parser):
    geval(parser)


def test_elk_voorstel_past_in_de_catalogus_en_draagt_zijn_regel():
    z = _drempel()
    z.markeer("het inkomen", VAR)
    z.markeer("de drempel", PAR, "parameter")
    for r in z.voorstel():
        van = next(v for v in z.voorstellen if v["ankers"] == r["van_ankers"])
        naar = next(v for v in z.voorstellen if v["ankers"] == r["naar_ankers"])
        assert toegestaan(r["type"], van["klasse"], naar["klasse"], van["jas_subtype"], naar["jas_subtype"])
        assert r["spoor"]["door"] == "regel" and r["spoor"]["regel"] in R.CODES
        assert (r["spoor"]["van_element"], r["spoor"]["naar_element"]) == (van["id"], naar["id"])


def test_een_markering_zonder_klasse_is_geen_eindpunt():
    z = _drempel()
    z.markeer("het inkomen", VAR)["klasse"] = ""
    assert not [r for r in z.voorstel() if r["type"] == "operand"]


def test_deterministisch():
    def een():
        z = _drempel()
        z.markeer("het inkomen", VAR)
        z.markeer("de drempel", PAR)
        return z.voorstel()
    assert een() == een()


# --- de keten: zonder vlag bitgelijk, met vlag de voorstellen -------------------------------------------------------

def _snapshot(tekst: str) -> dict:
    node = {"bron_iri": IRI, "parent_iri": "urn:test", "tekst": tekst, "bron_hash": tekst_hash(tekst), "type": "Lid",
            "nummer": "1", "volgorde": 1}
    ouder = {"bron_iri": "urn:test", "tekst": "", "parent_iri": "", "volgorde": 0, "type": "Artikel"}
    return {"schema_versie": 2, "snapshot_id": "s1", "doel": node, "nodes": [ouder, node], "segmenten": [node]}


def _keten(vlag: bool):
    snap = _snapshot(VERGUNNING)
    cm = CorpusMap(snap["segmenten"])
    keuzes = {"De gemeente verleent een vergunning": RB, "indien de aanvrager een verklaring overlegt": VW}

    class Kies(KeuzeFake):
        """Kiest per label de klasse uit `keuzes` op de tekst van de kandidaat (de labels bestaan pas na de fusie)."""

        def create(self, **request):
            import re
            for label, tekst in re.findall(r'^(C\d{3}) \| "(.*?)" \| toegestaan', request["messages"][0]["content"], re.M):
                self.keuzes.setdefault(label, keuzes.get(tekst, "Geen annotatie"))
            return super().create(**request)

    llm = Kies({})
    settings = Settings(classifier_granulariteit="universeel", classifier_parallel=1, gerichte_review=False,
                        relatie_voorstellen=vlag)
    return analyseer(snapshot=snap, corpus_segmenten=cm.als_dicts(), corpus=cm.corpus, llm=llm, model="nep",
                     settings=settings)


def _zonder_duur(meting: dict) -> dict:
    return {k: v for k, v in meting.items() if k != "fasen"} | {"fasen": [
        {k: v for k, v in f.items() if k != "ms"} for f in meting.get("fasen", [])]}


def test_zonder_vlag_is_de_uitkomst_bitgelijk(parser):
    uit, aan = _keten(False), _keten(True)
    assert uit.relaties == [] and "relaties" not in uit.meting
    assert "Relaties" not in [f["fase"] for f in uit.meting["fasen"]]
    assert uit.voorstellen == aan.voorstellen
    assert uit.beslissingen == aan.beslissingen
    zonder = _zonder_duur(aan.meting)
    zonder.pop("relaties")
    zonder["fasen"] = [f for f in zonder["fasen"] if f["fase"] != "Relaties"]
    assert _zonder_duur(uit.meting) == zonder


def test_met_vlag_levert_de_keten_de_voorstellen(parser):
    aan = _keten(True)
    klassen = {v["tekst"]: v["klasse"] for v in aan.voorstellen}
    if klassen.get("De gemeente verleent een vergunning") != RB or VW not in klassen.values():
        pytest.skip(f"de nep-classifier koos anders dan verwacht: {klassen}")
    assert ("voorwaarde", "De gemeente verleent een vergunning") in {(r["type"], r["van_ankers"][0]["tekst"])
                                                                    for r in aan.relaties}
    assert aan.meting["relaties"]["per_regel"].get(R.REL_VOORWAARDE_AANHECHTING, 0) >= 1


# --- emit en de driver ---------------------------------------------------------------------------------------------

def test_emit_neemt_alleen_relaties_naar_uitgestuurde_elementen_mee_in_contractvorm():
    from agent.bron_annotatie import lokale_relaties
    from agent.models import RelatieVoorstel
    z = _drempel()
    z.markeer("het inkomen", VAR)
    z.markeer("de drempel", PAR, "parameter")
    relaties = z.voorstel()
    snap = _snapshot(DREMPEL)
    uitgestuurd = [v for v in z.voorstellen if v["tekst"] != "de drempel"]       # bv. een hergebruikte bronnode
    lokaal = lokale_relaties(relaties, uitgestuurd, {"bron_snapshot": snap})
    assert lokaal and all("de drempel" not in (r["van_ankers"][0]["tekst"], r["naar_ankers"][0]["tekst"])
                          for r in lokaal)
    assert len(lokaal) == len(relaties) - 1
    assert [RelatieVoorstel.model_validate(r).model_dump() for r in lokaal] == lokaal
    assert lokale_relaties([], uitgestuurd, {}) == []


def test_de_driver_verzamelt_het_relaties_event():
    from agent.beurt import BeurtSchrijver
    s = BeurtSchrijver()
    assert s.relaties == []
    s.verwerk({"type": "relaties", "relaties": [{"type": "operand"}]})
    assert s.relaties == [{"type": "operand"}]


def test_de_proefvlag_staat_standaard_uit():
    assert Settings().relatie_voorstellen is False
    assert Settings.from_env({"RELATIE_VOORSTELLEN": "true"}).relatie_voorstellen is True
