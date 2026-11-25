"""Een rekenvoorbeeld is geen norm, maar wel bron (`jas_pipeline/voorbeeld.py`; plan-lessen-termijnen-bibliotheek V8/M2).

De zinnen hier zijn verzonnen of komen uit andere regelingen dan waarop de regel is gevonden: de herkenning mag niets
weten van één bepaling. Per signaal positief, negatief, rand en overlap, zoals bij de detectorregels.
"""
from __future__ import annotations

import pytest
from bronmodel import CorpusMap, tekst_hash

from agent.config import Settings
from agent.jas_pipeline import voorbeeld as V
from agent.jas_pipeline.besluit import deterministisch
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import BronSpan, Candidate, CandidateStatus, Evidence, kandidaat_id, label_kandidaten
from agent.jas_pipeline.keten import analyseer
from agent.jas_pipeline.taal import NullProvider, SpacyProvider
from agent.jas_pipeline.uitleg import toelichting
from eval.onderzoek_invordering import KeuzeFake

IRI = "urn:test:voorbeeld"


def _signalen(tekst: str, analyse=None) -> list[tuple[str, str]]:
    return [(v.signaal, tekst[v.start:v.eind]) for v in V.herken(IRI, tekst, analyse)]


@pytest.fixture(scope="module", params=["null", "spacy"])
def analyse(request):
    """Beide wegen: zonder parser splitst de stap zelf de zinnen, met parser volgt hij die van het taalmodel."""
    if request.param == "null":
        return NullProvider().analyseer
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd (uv sync --extra nlp)")
    return p.analyseer


# --- herkennen ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("zin, signaal", [
    ("Wordt de beschikking bijvoorbeeld op 3 juni bekendgemaakt, dan eindigt de bezwaartermijn dus op 15 juli.",
     "inleiding"),
    ("Bedraagt het inkomen bijvoorbeeld € 30.000, dan is de korting € 1.200.", "inleiding"),
    ("Stel dat de aanvraag op 2 januari binnenkomt, dan eindigt de beslistermijn op 2 april.", "inleiding"),
    ("Als de aanvraag op 2 januari binnenkomt, beslist het college uiterlijk op 2 april.", "uitkomst"),
    ("Valt de verzenddatum op 30 april, dan eindigt de termijn op 11 juni.", "uitkomst"),
])
def test_positief_een_voorbeeldzin(zin, signaal, analyse):
    assert _signalen(zin, analyse(zin)) == [(signaal, zin)]


@pytest.mark.parametrize("zin", [
    "Deze wet treedt in werking op 1 januari 2027.",
    # Een datum als grens in de voorwaarde is een norm, ook met een datum in de hoofdzin (overgangsrecht).
    "Indien de aanslag is gedagtekend vóór 1 april 2025, vervalt de termijn op 1 juli 2025.",
    "De aangifte wordt gedaan vóór 1 april en vóór 1 oktober.",
    # Een duur zonder datum of bedrag: dat is elke termijnnorm.
    "Als de termijn zes weken is, vervalt hij zes weken na de dagtekening.",
    # Een inleiding zonder concrete waarde is geen rekenvoorbeeld.
    "Een zaak is bijvoorbeeld een auto of een woning.",
    "De vergoeding bedraagt € 150 per jaar.",
    # Een bedrag in voorwaarde én hoofdzin is even vaak een drempel in een norm; zonder inleiding geen voorbeeld.
    "Bedraagt de schuld meer dan € 900, dan is de rente € 45.",
    "Indien de schuld betaling in 24 termijnen van € 20 niet toelaat, kan de ontvanger termijnen van € 10 toestaan.",
    # "dus" met alleen grensdata: een overgangsregeling, geen voorbeeld.
    "Betalingen die na 1 juli worden gedaan en die zien op een periode vóór 1 juli 2012 (en dus vóór 1 juli 2012 "
    "verschuldigd zijn) volgen de oude regeling.",
    # Een datum in een verwijzing naar een besluit, en "dus" in een andere zin.
    "Verwezen wordt naar het besluit van 15 november 1999. Er is dus sprake van eigendom.",
    # De datum staat vóór de inleiding: een vermelding, geen voorbeeld.
    "Het besluit van 15 november 1999 regelt dus de voorwaarden.",
])
def test_negatief_geen_voorbeeldzin(zin, analyse):
    assert _signalen(zin, analyse(zin)) == []


def test_rand_een_conclusie_begint_het_voorbeeld_bij_de_inleiding(analyse):
    zin = ("Als de bezwaartermijn zes weken bedraagt, dan houdt dat in dat als het besluit op 10 mei is verzonden, "
           "de termijn op 21 juni eindigt.")
    (signaal, stuk), = _signalen(zin, analyse(zin))
    assert signaal == "conclusie" and stuk.startswith("dan houdt dat in dat") and stuk.endswith("21 juni eindigt.")
    # De regel ervóór ("zes weken") hoort niet bij het voorbeeld.
    assert "zes weken" not in stuk


def test_rand_dit_betekent_dat(analyse):
    zin = "Dit betekent dat een aanvraag van 4 maart uiterlijk op 4 juni is afgehandeld."
    assert _signalen(zin, analyse(zin)) == [("conclusie", zin)]


def test_overlap_alleen_de_voorbeeldzinnen_van_een_alinea(analyse):
    norm = "De termijn vervalt een maand na de dagtekening van het aanslagbiljet."
    vb = "Is de dagtekening bijvoorbeeld 14 mei, dan vervalt de termijn dus op 14 juni."
    tekst = f"{norm} {vb} {norm}"
    assert _signalen(tekst, analyse(tekst)) == [("inleiding", vb)]


# --- wat een concrete waarde is ------------------------------------------------------------------------------

@pytest.mark.parametrize("tekst", ["op 31 oktober", "15 maart", "op 1 juli 2025", "€ 1.250,50", "1200 euro",
                                   "ten bedrage van € 45"])
def test_een_waarde(tekst):
    assert V.is_waarde(tekst)


@pytest.mark.parametrize("tekst", ["het jaartal", "een schrikkeljaar", "de laatste dag van de maand", "een maand later",
                                   "zes weken na de dagtekening", "de dagtekening", "vervalt op",
                                   # Een duur in een voorbeeld noemt de parameter zelf ("de termijn van zes weken").
                                   "zes weken", "één maand", "21 dagen"])
def test_geen_waarde(tekst):
    """Een kenmerk, een operator of een duur is geen concrete waarde."""
    assert not V.is_waarde(tekst)


# --- wat de stap met de kandidaten doet ----------------------------------------------------------------------

TEKST = "De termijn vervalt een maand na de dagtekening. Is de dagtekening bijvoorbeeld 14 mei, dan vervalt hij dus op 14 juni."


def _k(fragment: str, klassen: tuple[str, ...], code: str = "NP_OBJECT", na: int = 0) -> Candidate:
    s = TEKST.index(fragment, na)
    e = s + len(fragment)
    return Candidate(id=kandidaat_id(IRI, s, e), span=BronSpan(bron_iri=IRI, start=s, eind=e, tekst=fragment,
                                                                 bron_hash=tekst_hash(TEKST)),
                     possible_classes=klassen, evidence=(Evidence(detector="test", code=code),))


def _toegepast(*kandidaten: Candidate) -> list[Candidate]:
    return list(V.pas_toe(label_kandidaten(kandidaten), V.herken(IRI, TEKST)))


def test_een_datum_in_het_voorbeeld_wordt_niet_los_voorgesteld():
    k, = _toegepast(_k("op 14 juni", ("Tijdsaanduiding",), "TEMPORAL_DATE"))
    assert k.status is CandidateStatus.REJECTED and k.evidence[-1].code == V.CODE_WAARDE
    b = deterministisch(k)
    assert b.status is CandidateStatus.REJECTED and b.reden == V.REGEL_WAARDE


def test_het_kenmerk_blijft_en_draagt_in_een_voorbeeld():
    k, = _toegepast(_k("de dagtekening", ("Variabele en variabelewaarde", "Rechtsobject"), na=48))
    assert k.status is CandidateStatus.UNHANDLED
    assert k.possible_classes == ("Variabele en variabelewaarde", "Rechtsobject")
    assert k.evidence[-1].code == V.CODE_IN
    # De jurist ziet het in de toelichting.
    assert "voorbeeld" in toelichting(k, "Variabele en variabelewaarde", "model").lower()


def test_een_voorbeeld_stelt_geen_norm():
    zin = "Is de dagtekening bijvoorbeeld 14 mei, dan vervalt hij dus op 14 juni."
    alleen_norm, = _toegepast(_k(zin, ("Afleidingsregel", "Voorwaarde")))
    assert alleen_norm.status is CandidateStatus.REJECTED and alleen_norm.evidence[-1].code == V.CODE_GEEN_NORM
    gemengd, = _toegepast(_k("dan vervalt hij", ("Rechtsbetrekking", "Rechtsobject")))
    assert gemengd.possible_classes == ("Rechtsobject",)
    assert {e.code for e in gemengd.evidence} >= {V.CODE_IN, V.CODE_GEEN_NORM}


def test_een_operator_in_een_voorbeeld_vervalt():
    """De operator verbindt in een voorbeeld de waarden van het voorbeeld, geen kenmerken die een regel nodig heeft."""
    op, = _toegepast(_k("vervalt hij", ("Operator",), "VALUE_EQUATION", na=48))
    assert op.status is CandidateStatus.REJECTED and op.evidence[-1].code == V.CODE_GEEN_NORM
    assert deterministisch(op).reden == V.REGEL_GEEN_NORM
    buiten, = _toegepast(_k("vervalt", ("Operator",), "VALUE_EQUATION"))
    assert buiten.status is CandidateStatus.UNHANDLED and buiten.possible_classes == ("Operator",)


def test_buiten_het_voorbeeld_verandert_niets():
    norm = _k("een maand", ("Tijdsaanduiding",), "TEMPORAL_DURATION")
    over_de_grens = _k("de dagtekening. Is de dagtekening", ("Rechtsobject",))
    assert _toegepast(norm, over_de_grens) == list(label_kandidaten((norm, over_de_grens)))


def test_het_kenmerk_houdt_een_vast_besluit_niet_tegen():
    """IN_VOORBEELD is geen bewijs voor een klasse: een sterke regel beslist zoals zonder voorbeeld."""
    bron = BronTekst.van_tekst(IRI, TEKST)
    f = fuseer(detecteer_alles(bron))
    voor = {k.span.tekst: deterministisch(k) for k in f.kandidaten}
    na = {k.span.tekst: deterministisch(k) for k in V.pas_toe(f.kandidaten, V.herken(IRI, TEKST))}
    for tekst, b in voor.items():
        if b is not None and b.status is CandidateStatus.ACCEPTED and not V.is_waarde(tekst):
            assert na[tekst] is not None and na[tekst].klasse == b.klasse


# --- door de hele keten --------------------------------------------------------------------------------------

def test_de_keten_stelt_geen_data_uit_een_voorbeeld_voor():
    node = {"bron_iri": IRI, "parent_iri": "urn:test", "tekst": TEKST, "bron_hash": tekst_hash(TEKST), "type": "Lid",
            "nummer": "1", "volgorde": 1}
    ouder = {"bron_iri": "urn:test", "tekst": "", "parent_iri": "", "volgorde": 0, "type": "Artikel"}
    snap = {"schema_versie": 2, "snapshot_id": "s1", "doel": node, "nodes": [ouder, node], "segmenten": [node]}
    cm = CorpusMap(snap["segmenten"])
    settings = Settings(classifier_granulariteit="universeel", classifier_parallel=1, gerichte_review=False,
                        taal_provider="null")
    uit = analyseer(snapshot=snap, corpus_segmenten=cm.als_dicts(), corpus=cm.corpus, llm=KeuzeFake({}), model="nep",
                    settings=settings)
    teksten = {v["tekst"] for v in uit.voorstellen}
    assert "een maand na de dagtekening" in teksten or "een maand" in teksten     # de norm blijft
    assert not teksten & {"14 mei", "op 14 juni", "14 juni"}
    assert uit.meting["voorbeelden"] == {"versie": V.VERSIE, "aantal": 1, "afgewezen": uit.meting["voorbeelden"]["afgewezen"]}
    assert uit.meting["voorbeelden"]["afgewezen"] >= 2


def test_zonder_voorbeeld_blijft_de_meting_gelijk():
    tekst = "De termijn vervalt een maand na de dagtekening."
    bron = BronTekst.van_tekst(IRI, tekst)
    assert V.herken(IRI, tekst) == [] and fuseer(detecteer_alles(bron)).kandidaten == V.pas_toe(
        fuseer(detecteer_alles(bron)).kandidaten, [])
