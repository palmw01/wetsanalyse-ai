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

    def voorstel(self, verwijzingen: list[dict] | None = None) -> list[dict]:
        ks = label_kandidaten(list(self.kandidaten.values()))
        fusie = Fusie(kandidaten=ks, relaties=nesting(ks))
        return R.stel_voor(self.voorstellen, fusie, {IRI: self.analyse},
                           verwijzingen={IRI: verwijzingen} if verwijzingen else None, teksten={IRI: self.tekst})


def kort(relaties: list[dict]) -> set[tuple]:
    """(type, tekst van, tekst naar, volgorde)."""
    return {(r["type"], r["van_ankers"][0]["tekst"], r.get("naar_bron") or r["naar_ankers"][0]["tekst"], r["volgorde"])
            for r in relaties}


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
    assert kort(z.voorstel()) == {("invoer", "volle maanden", AR_SPAN, 1)}


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
    # Twee markeringen naast elkaar op de invoer zijn twee invoeren, in de volgorde van de tekst (L-2-2).
    z = _aantal()
    z.markeer("er", VAR, nde=2)
    z.markeer("volle maanden", VAR)
    gevonden = {r for r in kort(z.voorstel()) if r[0] == "invoer"}
    assert gevonden == {("invoer", "er", AR_SPAN, 1), ("invoer", "volle maanden", AR_SPAN, 2)}


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
    # Een rechtsbetrekking en een afleidingsregel om hetzelfde predicaat: de bepaling draagt beide (M-2-1, L-2-2), en
    # de voorwaarde geldt voor allebei. Twee rechtsbetrekkingen erom blijven twijfel: geen voorstel.
    z = Zin(VERGUNNING, parser.analyseer(VERGUNNING))
    z.markeer("De gemeente verleent een vergunning", RB)
    z.markeer(VERGUNNING.rstrip("."), AR)
    z.markeer("indien de aanvrager een verklaring overlegt", VW)
    rs = [r for r in z.voorstel() if r["type"] == "voorwaarde"]
    assert {r["van_ankers"][0]["tekst"] for r in rs} == {"De gemeente verleent een vergunning", VERGUNNING.rstrip(".")}
    assert all(r["spoor"]["detail"]["twee_dragers"] for r in rs)
    z = Zin(VERGUNNING, parser.analyseer(VERGUNNING))
    z.markeer("De gemeente verleent een vergunning", RB)
    z.markeer(VERGUNNING.rstrip("."), RB)
    z.markeer("indien de aanvrager een verklaring overlegt", VW)
    assert not [r for r in z.voorstel() if r["type"] == "voorwaarde"]


# --- 5–7. rollen en voorwerp -----------------------------------------------------------------------------------------

def _rb(parser, tekst: str, klasse: str = RB) -> Zin:
    z = Zin(tekst, parser.analyseer(tekst))
    z.markeer(tekst.rstrip("."), klasse)
    return z


def _rollen(z: Zin, *types: str) -> set[tuple]:
    return {r for r in kort(z.voorstel()) if r[0] in types}


ROLLEN = ("rechthebbende", "plichthebbende", "verricht")


def rol_onderwerp_positief(parser):
    z = _rb(parser, "De ontvanger kan de aanslag verminderen.")
    z.markeer("De ontvanger", RS)
    assert _rollen(z, *ROLLEN) == {("rechthebbende", "De ontvanger", "De ontvanger kan de aanslag verminderen", None)}
    z = _rb(parser, "De ontvanger moet de aanslag verminderen.")
    z.markeer("De ontvanger", RS)
    assert {r[0] for r in _rollen(z, *ROLLEN)} == {"plichthebbende"}


def rol_onderwerp_negatief(parser):
    # Geen bevoegdheid en geen plicht in de zin: welke rol het onderwerp heeft, zegt de tekst niet. Ook zonder ontleding niets.
    z = _rb(parser, "De ontvanger vermindert de aanslag.")
    z.markeer("De ontvanger", RS)
    assert not _rollen(z, *ROLLEN)
    tekst = "De ontvanger kan de aanslag verminderen."
    z = Zin(tekst, NullProvider().analyseer(tekst))
    z.markeer(tekst.rstrip("."), RB)
    z.markeer("De ontvanger", RS)
    assert not z.voorstel()


def rol_onderwerp_rand(parser):
    # Een rechtsfeit: het onderwerp verricht het.
    z = _rb(parser, "De belastingschuldige betaalt de aanslag.", RF)
    z.markeer("De belastingschuldige", RS)
    assert _rollen(z, *ROLLEN) == {("verricht", "De belastingschuldige", "De belastingschuldige betaalt de aanslag", None)}


def rol_onderwerp_overlap(parser):
    # Het onderwerp van een voorwaarde binnen de betrekking is niet het onderwerp van de betrekking.
    tekst = "Indien de inspecteur dat vraagt, moet de belastingschuldige de aangifte doen."
    z = _rb(parser, tekst)
    z.markeer("Indien de inspecteur dat vraagt", VW)
    z.markeer("de inspecteur", RS)
    z.markeer("de belastingschuldige", RS)
    assert _rollen(z, *ROLLEN) == {("plichthebbende", "de belastingschuldige", tekst.rstrip("."), None)}


def rol_voorzetsel_positief(parser):
    tekst = "De belastingschuldige moet de aanslag betalen aan de ontvanger."
    z = _rb(parser, tekst)
    z.markeer("De belastingschuldige", RS)
    z.markeer("de ontvanger", RS)
    assert ("rechthebbende", "de ontvanger", tekst.rstrip("."), None) in _rollen(z, *ROLLEN)


def rol_voorzetsel_negatief(parser):
    # Zonder modaliteit is "aan" geen tegenpartij van een recht of plicht.
    z = _rb(parser, "De belastingschuldige betaalt de aanslag aan de ontvanger.")
    z.markeer("de ontvanger", RS)
    assert not _rollen(z, *ROLLEN)


def rol_voorzetsel_rand(parser):
    # Op verzoek van iemand een plicht: die iemand kan haar inroepen, en is rechthebbende.
    tekst = "Op verzoek van de belastingschuldige is de ontvanger verplicht te verrekenen."
    z = _rb(parser, tekst)
    z.markeer("de belastingschuldige", RS)
    z.markeer("de ontvanger", RS)
    assert _rollen(z, *ROLLEN) == {("rechthebbende", "de belastingschuldige", tekst.rstrip("."), None),
                                   ("plichthebbende", "de ontvanger", tekst.rstrip("."), None)}


def rol_voorzetsel_overlap(parser):
    # Bij een heffing noemt "van" de plichtige; bij een gewone zin zonder heffing niet.
    tekst = "Het winstaandeel wordt geheven van de houder."
    z = _rb(parser, tekst)
    z.markeer("de houder", RS)
    assert _rollen(z, *ROLLEN) == {("plichthebbende", "de houder", tekst.rstrip("."), None)}
    z = _rb(parser, "Het bericht wordt verstuurd van de houder.")
    z.markeer("de houder", RS)
    assert not _rollen(z, *ROLLEN)


def voorwerp_zinsdeel_positief(parser):
    tekst = "De ontvanger kan de aanslag verminderen."
    z = _rb(parser, tekst)
    z.markeer("de aanslag", RO)
    assert _rollen(z, "voorwerp") == {("voorwerp", tekst.rstrip("."), "de aanslag", None)}


def voorwerp_zinsdeel_negatief(parser):
    # Een rechtsobject in een voorzetselgroep is geen voorwerp.
    z = _rb(parser, "De ontvanger kan bij de aanslag een korting verlenen.")
    z.markeer("de aanslag", RO)
    assert not _rollen(z, "voorwerp")


def voorwerp_zinsdeel_rand(parser):
    # Een lijdende zin: het onderwerp is het voorwerp; de voorzetselgroep niet.
    tekst = "De belasting wordt geheven bij wege van aanslag."
    z = _rb(parser, tekst)
    z.markeer("De belasting", RO)
    z.markeer("aanslag", RO)
    assert _rollen(z, "voorwerp") == {("voorwerp", tekst.rstrip("."), "De belasting", None)}


def voorwerp_zinsdeel_overlap(parser):
    # Twee geneste rechtsobjecten: het kleinste dat het lijdend voorwerp draagt, niet de naamwoordgroep erin.
    tekst = "De ontvanger kan het bedrag van de aanslag verminderen."
    z = _rb(parser, tekst)
    z.markeer("het bedrag van de aanslag", RO)
    z.markeer("de aanslag", RO)
    assert _rollen(z, "voorwerp") == {("voorwerp", tekst.rstrip("."), "het bedrag van de aanslag", None)}


# --- 1b. kenmerk binnen de invoer (L-2-2) ------------------------------------------------------------------------------

DAGTEKENING = "De termijn vervalt in zoveel delen als er dagen na de dagtekening van het aanslagbiljet zijn."
DT_SPAN = "zoveel delen als er dagen na de dagtekening van het aanslagbiljet zijn"
DT_INVOER = "er dagen na de dagtekening van het aanslagbiljet zijn"


def _dagtekening() -> Zin:
    z = Zin(DAGTEKENING)
    z.markeer(DT_SPAN, AR, code="CALCULATION_QUANTITY", detail=z.aantal(DT_SPAN, "delen", DT_INVOER))
    return z


def kenmerk_positief():
    # De variabele is de invoer, het rechtsobject erin niet: dat krijgt een kenmerk ("geen waarde, weg").
    z = _dagtekening()
    z.markeer("de dagtekening van het aanslagbiljet", VAR)
    z.markeer("het aanslagbiljet", RO)
    assert {r for r in kort(z.voorstel()) if r[0] in ("invoer", "kenmerk")} == {
        ("invoer", "de dagtekening van het aanslagbiljet", DT_SPAN, 1),
        ("kenmerk", "de dagtekening van het aanslagbiljet", "het aanslagbiljet", None)}


def kenmerk_negatief():
    # Een rechtsobject dat alleen staat, blijft invoer: er is geen waarde om het kenmerk van te zijn.
    z = _dagtekening()
    z.markeer("het aanslagbiljet", RO)
    assert kort(z.voorstel()) == {("invoer", "het aanslagbiljet", DT_SPAN, 1)}


def kenmerk_rand():
    # Een tijdsaanduiding is ook een waarde en dus de invoer, maar de catalogus kent alleen een variabele als kenmerk.
    z = _dagtekening()
    z.markeer("de dagtekening van het aanslagbiljet", TIJD)
    z.markeer("het aanslagbiljet", RO)
    assert kort(z.voorstel()) == {("invoer", "de dagtekening van het aanslagbiljet", DT_SPAN, 1)}


def kenmerk_overlap():
    # Twee waarden naast elkaar zijn twee invoeren op volgorde; het object hoort bij de variabele waar het in staat.
    z = _dagtekening()
    z.markeer("dagen", VAR)
    z.markeer("de dagtekening van het aanslagbiljet", VAR)
    z.markeer("het aanslagbiljet", RO)
    assert {r for r in kort(z.voorstel()) if r[0] in ("invoer", "kenmerk")} == {
        ("invoer", "dagen", DT_SPAN, 1), ("invoer", "de dagtekening van het aanslagbiljet", DT_SPAN, 2),
        ("kenmerk", "de dagtekening van het aanslagbiljet", "het aanslagbiljet", None)}


# --- 8. uitzondering en toepassing naar een hele bepaling (M-1-1) -----------------------------------------------------

LID1 = "urn:bwb:BWBR0000001:artikel:9:lid:1"
AFWIJKING = "In afwijking van het eerste lid is de aanslag invorderbaar in termijnen."
EERSTE_LID = [{"anker": "het eerste lid", "naar": LID1}]


def uitzondering_positief():
    z = Zin(AFWIJKING)
    z.markeer(AFWIJKING.rstrip("."), RB)
    assert kort(z.voorstel(EERSTE_LID)) == {("uitzondering_op", AFWIJKING.rstrip("."), LID1, None)}


def uitzondering_negatief():
    # Zonder verwijzing uit de graaf geen doel; een anker ver van de formule hoort er niet bij.
    z = Zin(AFWIJKING)
    z.markeer(AFWIJKING.rstrip("."), RB)
    assert not [r for r in z.voorstel() if r["type"] == "uitzondering_op"]
    tekst = "In afwijking van de regels die hierna volgen en die gelden voor alle aanslagen, geldt het eerste lid."
    z = Zin(tekst)
    z.markeer(tekst.rstrip("."), RB)
    assert not [r for r in z.voorstel(EERSTE_LID) if r["type"] == "uitzondering_op"]


def uitzondering_rand():
    # De kleinste drager om de formule: een voorwaarde binnen de rechtsbetrekking.
    tekst = "Indien in afwijking in zoverre van het eerste lid wordt betaald, vervalt de aanslag."
    z = Zin(tekst)
    z.markeer(tekst.rstrip("."), RB)
    z.markeer("Indien in afwijking in zoverre van het eerste lid wordt betaald", VW)
    assert {r for r in kort(z.voorstel(EERSTE_LID)) if r[0] == "uitzondering_op"} == {
        ("uitzondering_op", "Indien in afwijking in zoverre van het eerste lid wordt betaald", LID1, None)}


def uitzondering_overlap():
    # Twee dragers op precies dezelfde span: welke? Twijfel, geen voorstel.
    z = Zin(AFWIJKING)
    z.markeer(AFWIJKING.rstrip("."), RB)
    z.markeer(AFWIJKING.rstrip("."), AR)
    assert not [r for r in z.voorstel(EERSTE_LID) if r["type"] == "uitzondering_op"]


TOEPASSING = "Indien de toepassing niet leidt tot meer dan één termijn, vindt het eerste lid toepassing."
TOEP_AR = "vindt het eerste lid toepassing"


def _toepassing(code="CALCULATION_APPLICABILITY", klasse=AR) -> Zin:
    z = Zin(TOEPASSING)
    regel = z.span("het eerste lid")
    detail = json.dumps({"toepasselijke_regel": {"start": regel.start, "eind": regel.eind, "tekst": "het eerste lid"}})
    z.markeer(TOEP_AR, klasse, code=code, detail=detail)
    return z


def toepassing_positief():
    assert kort(_toepassing().voorstel(EERSTE_LID)) == {("toepassing", TOEP_AR, LID1, None)}


def toepassing_negatief():
    # Een ander bewijs dan de toepassingskeuze, of een verwijzing buiten de regel: geen voorstel.
    assert not _toepassing(code="CALCULATION_PASSIVE").voorstel(EERSTE_LID)
    assert not _toepassing().voorstel([{"anker": "artikel 4", "naar": LID1}])


def toepassing_rand():
    # Alleen een afleidingsregel kiest een regel (catalogus: van Afleidingsregel).
    assert not [r for r in _toepassing(klasse=RB).voorstel(EERSTE_LID) if r["type"] == "toepassing"]


def toepassing_overlap():
    # Twee verwijzingen in de bepaling: die in de span van de regel telt.
    lid2 = "urn:bwb:BWBR0000001:artikel:9:lid:2"
    gevonden = kort(_toepassing().voorstel([{"anker": "termijn", "naar": lid2}, *EERSTE_LID]))
    assert gevonden == {("toepassing", TOEP_AR, LID1, None)}


# --- 9. tijd uit de nesting ----------------------------------------------------------------------------------------

BEHANDELING = "De aanvraag wordt binnen 48 uur behandeld door de inspecteur."


def tijd_positief():
    z = Zin(BEHANDELING)
    z.markeer(BEHANDELING.rstrip("."), RB)
    z.markeer("binnen 48 uur", TIJD)
    assert ("tijd", BEHANDELING.rstrip("."), "binnen 48 uur", None) in kort(z.voorstel())


def tijd_negatief():
    # Een tijdsaanduiding buiten elke rechtsbetrekking, en een die al operand is van een operator in de regel.
    z = Zin(BEHANDELING)
    z.markeer("binnen 48 uur", TIJD)
    assert not z.voorstel()
    tekst = "Indien de dag later valt dan 1 april, is de rente verschuldigd."
    z = Zin(tekst)
    z.markeer(tekst.rstrip("."), RB)
    z.markeer("Indien de dag later valt dan 1 april", VW)
    z.markeer("later valt dan", OP)
    z.markeer("1 april", TIJD)
    assert not [r for r in z.voorstel() if r["type"] == "tijd"]


def tijd_rand():
    # Een tijdsaanduiding in een tijdsaanduiding: alleen de buitenste.
    z = Zin(BEHANDELING)
    z.markeer(BEHANDELING.rstrip("."), RB)
    z.markeer("binnen 48 uur", TIJD)
    z.markeer("48 uur", TIJD)
    assert {r for r in kort(z.voorstel()) if r[0] == "tijd"} == {("tijd", BEHANDELING.rstrip("."), "binnen 48 uur", None)}


def tijd_overlap():
    # In een voorwaarde binnen de rechtsbetrekking: de rechtsbetrekking is de ouder (een voorwaarde heeft geen tijd).
    tekst = "Indien binnen 48 uur geen bericht komt, vervalt de aanvraag."
    z = Zin(tekst)
    z.markeer(tekst.rstrip("."), RB)
    z.markeer("Indien binnen 48 uur geen bericht komt", VW)
    z.markeer("binnen 48 uur", TIJD)
    assert {r for r in kort(z.voorstel()) if r[0] == "tijd"} == {("tijd", tekst.rstrip("."), "binnen 48 uur", None)}


GEVALLEN = {
    R.REL_UITVOER_FUNCTIE: (uitvoer_positief, uitvoer_negatief, uitvoer_rand, uitvoer_overlap),
    R.REL_INVOER_FUNCTIE: (invoer_positief, invoer_negatief, invoer_rand, invoer_overlap),
    R.REL_KENMERK_INVOER: (kenmerk_positief, kenmerk_negatief, kenmerk_rand, kenmerk_overlap),
    R.REL_UITZONDERING_VERWIJZING: (uitzondering_positief, uitzondering_negatief, uitzondering_rand, uitzondering_overlap),
    R.REL_TOEPASSING_VERWIJZING: (toepassing_positief, toepassing_negatief, toepassing_rand, toepassing_overlap),
    R.REL_TIJD_NESTING: (tijd_positief, tijd_negatief, tijd_rand, tijd_overlap),
    R.REL_WAARDE_NESTING: (waarde_positief, waarde_negatief, waarde_rand, waarde_overlap),
    R.REL_OPERATOR_IN_NESTING: (operator_in_positief, operator_in_negatief, operator_in_rand, operator_in_overlap),
    R.REL_OPERAND_WOORDVOLGORDE: (operand_positief, operand_negatief, operand_rand, operand_overlap),
    R.REL_VOORWAARDE_AANHECHTING: (voorwaarde_positief, voorwaarde_negatief, voorwaarde_rand, voorwaarde_overlap),
    R.REL_ROL_ONDERWERP: (rol_onderwerp_positief, rol_onderwerp_negatief, rol_onderwerp_rand, rol_onderwerp_overlap),
    R.REL_ROL_VOORZETSEL: (rol_voorzetsel_positief, rol_voorzetsel_negatief, rol_voorzetsel_rand, rol_voorzetsel_overlap),
    R.REL_VOORWERP_ZINSDEEL: (voorwerp_zinsdeel_positief, voorwerp_zinsdeel_negatief, voorwerp_zinsdeel_rand,
                              voorwerp_zinsdeel_overlap),
}
#: De regels die de zinsontleding lezen; de rest draait zonder model.
MET_ONTLEDING = (R.REL_VOORWAARDE_AANHECHTING, R.REL_ROL_ONDERWERP, R.REL_ROL_VOORZETSEL, R.REL_VOORWERP_ZINSDEEL)
SOORTEN = ("positief", "negatief", "rand", "overlap")


def test_een_datumregel_heeft_het_tijdstip_als_invoer_en_geen_uitvoer():
    """Meting bundel 3 (IW art. 52 lid 1): de datumregel kreeg geen invoer. De invoer is wat binnen het tijdstip ligt
    (de dagtekening), niet de tijdsaanduiding met de duur die het omvat; een uitvoer is er niet."""
    tekst = "Het bedrag is invorderbaar zes weken na de dagtekening van de beschikking."
    regel = "invorderbaar zes weken na de dagtekening van de beschikking"
    z = Zin(tekst)
    tijdstip = z.span("de dagtekening van de beschikking")
    detail = json.dumps({"toestand": "invorderbaar", "moment": "zes weken na de dagtekening van de beschikking",
                         "invoer": {"start": tijdstip.start, "eind": tijdstip.eind, "tekst": tijdstip.tekst}})
    z.markeer(regel, AR, code="DATE_ASSIGNMENT", detail=detail)
    z.markeer("zes weken na de dagtekening van de beschikking", TIJD, "verbijzondert parameter")
    z.markeer("de dagtekening van de beschikking", TIJD)
    assert {r for r in kort(z.voorstel()) if r[0] in ("invoer", "uitvoer")} == {
        ("invoer", "de dagtekening van de beschikking", regel, 1)}


def test_een_datumregel_heeft_de_toestand_als_uitvoer():
    """Keten-termijnpatroon (24 nov 2026, art. 9 lid 1): de toestand die op de datum intreedt ('invorderbaar') is de
    uitvoer, als die als variabele gemarkeerd is; de invoer blijft het tijdstip, niet de duur eromheen."""
    tekst = "Het bedrag is invorderbaar zes weken na de dagtekening van de beschikking."
    regel = "invorderbaar zes weken na de dagtekening van de beschikking"
    z = Zin(tekst)
    tijdstip, toestand = z.span("de dagtekening van de beschikking"), z.span("invorderbaar")
    detail = json.dumps({"toestand": "invorderbaar", "moment": "zes weken na de dagtekening van de beschikking",
                         "uitkomst": {"start": toestand.start, "eind": toestand.eind, "tekst": toestand.tekst},
                         "invoer": {"start": tijdstip.start, "eind": tijdstip.eind, "tekst": tijdstip.tekst}})
    z.markeer(regel, AR, code="DATE_ASSIGNMENT", detail=detail)
    z.markeer("invorderbaar", VAR, "variabele")
    z.markeer("zes weken na de dagtekening van de beschikking", TIJD, "verbijzondert parameter")
    z.markeer("de dagtekening van de beschikking", TIJD)
    assert {r for r in kort(z.voorstel()) if r[0] in ("invoer", "uitvoer")} == {
        ("uitvoer", regel, "invorderbaar", None), ("invoer", "de dagtekening van de beschikking", regel, 1)}


def test_de_uitvoer_van_een_regel_is_geen_operand_van_een_operator_erin():
    """Meting na de uitrol van #1837 (Awir 33 lid 4): 'invorderbaar' was de uitvoer van de datumregel en ook operand 1
    van 'na', omdat de operanden op positie binnen de regel gekozen worden. Een operator verbindt invoer; de uitvoer van
    de regel waarin hij staat, telt nooit mee. De invoer en de andere operand blijven."""
    tekst = "Het bedrag is invorderbaar zes weken na de dagtekening van de beschikking."
    regel = "invorderbaar zes weken na de dagtekening van de beschikking"
    z = Zin(tekst)
    tijdstip, toestand = z.span("de dagtekening van de beschikking"), z.span("invorderbaar")
    detail = json.dumps({"uitkomst": {"start": toestand.start, "eind": toestand.eind, "tekst": toestand.tekst},
                         "invoer": {"start": tijdstip.start, "eind": tijdstip.eind, "tekst": tijdstip.tekst}})
    z.markeer(regel, AR, code="DATE_ASSIGNMENT", detail=detail)
    z.markeer("invorderbaar", VAR, "variabele")
    z.markeer("na", OP)
    z.markeer("de dagtekening van de beschikking", TIJD)
    rel = kort(z.voorstel())
    assert ("uitvoer", regel, "invorderbaar", None) in rel
    assert {r for r in rel if r[0] == "operand"} == {("operand", "de dagtekening van de beschikking", "na", 2)}


def test_zonder_uitvoer_blijft_de_naaste_links_de_operand():
    """De uitsluiting geldt alleen de uitvoer: is dezelfde variabele geen uitvoer (geen `uitkomst` in het bewijs), dan
    blijft de woordvolgorde gelden."""
    tekst = "Het bedrag is invorderbaar zes weken na de dagtekening van de beschikking."
    regel = "invorderbaar zes weken na de dagtekening van de beschikking"
    z = Zin(tekst)
    z.markeer(regel, AR)
    z.markeer("invorderbaar", VAR, "variabele")
    z.markeer("na", OP)
    z.markeer("de dagtekening van de beschikking", TIJD)
    assert ("operand", "invorderbaar", "na", 1) in kort(z.voorstel())


def test_een_datumregel_zonder_variabele_op_de_toestand_heeft_geen_uitvoer():
    """Wees de jurist of het model de variabele af, dan wordt geen ander voorstel de uitvoer."""
    tekst = "Het bedrag is invorderbaar zes weken na de dagtekening van de beschikking."
    regel = "invorderbaar zes weken na de dagtekening van de beschikking"
    z = Zin(tekst)
    tijdstip, toestand = z.span("de dagtekening van de beschikking"), z.span("invorderbaar")
    detail = json.dumps({"uitkomst": {"start": toestand.start, "eind": toestand.eind, "tekst": toestand.tekst},
                         "invoer": {"start": tijdstip.start, "eind": tijdstip.eind, "tekst": tijdstip.tekst}})
    z.markeer(regel, AR, code="DATE_ASSIGNMENT", detail=detail)
    z.markeer("de dagtekening van de beschikking", TIJD)
    assert not {r for r in kort(z.voorstel()) if r[0] == "uitvoer"}


def test_een_ontkenning_heeft_een_operand_en_breekt_de_reeks_niet():
    """Termijnen (art. 9 lid 5 IW): 'niet' kreeg twee operanden, en 'meer dan' miste zijn eerste."""
    tekst = "Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn, vindt het eerste lid toepassing."
    vw = "Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn"
    z = Zin(tekst)
    z.markeer(vw, VW)
    for fragment, klasse in (("niet", OP), ("meer dan", OP), ("de toepassing van de eerste volzin", VAR),
                             ("één termijn", PAR)):
        z.markeer(fragment, klasse)
    assert {r for r in kort(z.voorstel()) if r[0] == "operand"} == {
        ("operand", "meer dan", "niet", 1),
        ("operand", "de toepassing van de eerste volzin", "meer dan", 1), ("operand", "één termijn", "meer dan", 2)}


def test_elke_regel_heeft_vier_testsoorten():
    assert set(GEVALLEN) == set(R.CODES)
    for code, gevallen in GEVALLEN.items():
        assert [g.__name__.rsplit("_", 1)[1] for g in gevallen] == list(SOORTEN), code


@pytest.mark.parametrize("geval", [g for code in R.CODES if code not in MET_ONTLEDING
                                   for g in GEVALLEN[code]], ids=lambda g: g.__name__)
def test_regel_zonder_zinsontleding(geval):
    geval()


@pytest.mark.parametrize("geval", [g for code in MET_ONTLEDING for g in GEVALLEN[code]], ids=lambda g: g.__name__)
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
