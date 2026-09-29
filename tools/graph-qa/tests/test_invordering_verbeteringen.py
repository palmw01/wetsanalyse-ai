"""Graafcasussen en gemarkeerde synthetische tegenproeven; geen juridische goldset."""
import json
from pathlib import Path

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.taal import SpacyProvider

DOSSIER = Path(__file__).resolve().parents[3] / "docs/wetsanalyse/onderzoek-invordering-2026-09-29"
CASES = {c["id"]: c for c in json.loads((DOSSIER / "bronnen.json").read_text())["casussen"]}


@pytest.fixture(scope="module")
def parser():
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("Een synthetische controle.").gedegradeerd:
        pytest.skip("volledige parser vereist")
    return p


def detect(tekst, parser=None):
    return fuseer(detecteer_alles(BronTekst.van_tekst(
        "urn:synthetische-controle", tekst, analyse=parser.analyseer(tekst) if parser else None)))


@pytest.mark.parametrize("verwijzing", ["artikel 9.1", "artikel 3:4", "art. 4"])
def test_afleiding_beschermt_notatie_en_stopt_bij_volgende_zin(verwijzing):
    zin = f"Volgens {verwijzing} bedraagt de vergoeding € 1.000."
    ks = detect(zin + " De aanvraag vervalt.").kandidaten
    ar = [k for k in ks if "Afleidingsregel" in k.possible_classes]
    assert [k.span.tekst for k in ar] == [zin]


@pytest.mark.parametrize("datum,geldig", [
    ("31 december", True), ("29 februari", True), ("29 februari 2024", True),
    ("29 februari 2025", False), ("31 februari", False), ("31 april", False),
    ("0 januari", False), ("1\u00a0januari 2027", True),
])
def test_synthetische_kalenderdatum(datum, geldig):
    ks = detect(f"De termijn eindigt op {datum}. Daarna vervalt het recht.").kandidaten
    dates = [k for k in ks if any(e.code == "TEMPORAL_DATE" for e in k.evidence)]
    assert [k.span.tekst for k in dates] == ([f"op {datum}"] if geldig else [])


def test_datums_op_herhaalde_offsets_blijven_afzonderlijk():
    c = CASES["LI-9.1"]
    ks = detect(c["tekst"]).kandidaten
    dates = [k for k in ks if any(e.code == "TEMPORAL_DATE" for e in k.evidence)]
    assert len(dates) == 2
    assert len({k.span.start for k in dates}) == 2
    assert all("31 december" in k.span.tekst for k in dates)


def test_beide_toewijzingen_en_elliptische_voorwaarde(parser):
    ks = detect(CASES["LI-9.1"]["tekst"], parser).kandidaten
    assert len([k for k in ks if "Afleidingsregel" in k.possible_classes]) == 2
    assert any(k.span.tekst == "Bij afwijkende boekjaren" and "Voorwaarde" in k.possible_classes for k in ks)
    assert any(k.span.tekst == "de laatste dag van de maand" and "Tijdsaanduiding" in k.possible_classes for k in ks)


@pytest.mark.parametrize("tekst,ar", [
    ("De vervaldag wordt op 31 december gesteld.", True),
    ("De vervaldag wordt gesteld op 31 december.", True),
    ("Het boek wordt op tafel gelegd.", False),
    ("Bij ministeriële regeling worden regels gesteld.", False),
    ("Hij neemt zoveel boeken als hij wil.", False),
    ("De bijdrage kent zoveel delen als er maanden resteren.", True),
])
def test_synthetische_toewijzing_en_aantal(parser, tekst, ar):
    assert any("Afleidingsregel" in k.possible_classes for k in detect(tekst, parser).kandidaten) == ar


def test_berekening_en_nominalisatie_lid5(parser):
    ks = detect(CASES["IW-9-5"]["tekst"], parser).kandidaten
    assert any(k.span.start == 0 and "Afleidingsregel" in k.possible_classes for k in ks)
    n = [k for k in ks if k.span.start == 474 and any(e.code == "NOMINALIZED_ACTION" for e in k.evidence)]
    assert [k.span.tekst for k in n] == ["de dagtekening van het aanslagbiljet"]
    assert any(k.span.tekst == "telkens een maand later" and "Tijdsaanduiding" in k.possible_classes for k in ks)
    assert any(k.span.tekst.startswith("Indien") and "niet leidt tot meer dan één termijn" in k.span.tekst for k in ks)
    assert any(k.span.tekst.startswith("Indien") and k.span.tekst.endswith("vindt het eerste lid toepassing.")
               and "Afleidingsregel" in k.possible_classes for k in ks)


def test_nominalisatie_behoudt_gezamenlijke_start(parser):
    ks = detect("Na de verzending en de bekendmaking van het besluit begint de termijn.", parser).kandidaten
    assert any("de verzending en de bekendmaking van het besluit" in k.span.tekst for k in ks)


def test_kalenderpositie_en_brongetrouwheid(parser):
    tekst = CASES["LI-9.5"]["tekst"]
    ks = detect(tekst, parser).kandidaten
    assert any(k.span.tekst == "de dag die hetzelfde nummer heeft als dat van de dagtekening" and
               "Tijdsaanduiding" in k.possible_classes for k in ks)
    assert any(k.span.start == 556 and "Afleidingsregel" in k.possible_classes for k in ks)
    assert all(tekst[k.span.start:k.span.eind] == k.span.tekst for k in ks)
    assert not any(k.span.tekst == "als dat van de dagtekening" and "Voorwaarde" in k.possible_classes for k in ks)


def test_korte_tijdkern_krijgt_tijd_met_herleidbare_bijdrage(parser):
    f = detect(CASES["IW-9-1"]["tekst"], parser)
    kort = next(k for k in f.kandidaten if k.span.tekst == "zes weken")
    assert "Tijdsaanduiding" in kort.possible_classes
    assert any(b.kandidaat_id == kort.id and b.detector == "fusie" for b in f.bijdragen)
    assert any(b.kandidaat_id == kort.id and b.detector == "naamwoordgroep" for b in f.bijdragen)


# --- WP1 baseline: precisie, herkomst en contextblok ------------------------------------------

@pytest.mark.parametrize("tekst,code", [
    ("Het verzoek wordt op schrift gesteld en binnen de termijn ingediend.", "CALCULATION_ASSIGNMENT"),
    ("De aanvraag wordt ingediend op de datum waarop het besluit is gesteld.", "CALCULATION_ASSIGNMENT"),
    ("Indien de ontvanger een beschikking als bedoeld in artikel 3 neemt, vindt artikel 5 geen toepassing.",
     "CALCULATION_APPLICABILITY"),
    ("Als het college besluit, vinden de artikelen 4 en 5 overeenkomstige toepassing.", "CALCULATION_APPLICABILITY"),
    ("Artikel 4 vindt toepassing.", "CALCULATION_APPLICABILITY"),
])
def test_functiedetector_zonder_bekende_valse_positieven(parser, tekst, code):
    assert not any(e.code == code for k in detect(tekst, parser).kandidaten for e in k.evidence)


def test_toepassingskeuze_noemt_toepasselijke_regel(parser):
    ks = detect(CASES["IW-9-5"]["tekst"], parser).kandidaten
    e = next(e for k in ks for e in k.evidence if e.code == "CALCULATION_APPLICABILITY")
    assert json.loads(e.detail)["toepasselijke_regel"]["tekst"] == "het eerste lid"


def test_tijdkern_kopieert_geen_detectorbewijs(parser):
    f = detect(CASES["IW-9-1"]["tekst"], parser)
    kort = next(k for k in f.kandidaten if k.span.tekst == "zes weken")
    lang = next(k for k in f.kandidaten if k.span.tekst == "zes weken na de dagtekening van het aanslagbiljet")
    kern = [e for e in kort.evidence if e.code == "TEMPORAL_KERNEL"]
    assert len(kern) == 1 and json.loads(kern[0].detail)["ouder"] == lang.id
    # Tijdbewijs van een andere detector op de korte grens zou een niet-bestaande treffer suggereren.
    assert not any(e.code.startswith("TEMPORAL_") and e.code != "TEMPORAL_KERNEL" and e.detector != "fusie"
                   and not any(b.kandidaat_id == kort.id and b.detector == e.detector for b in f.bijdragen)
                   for e in kort.evidence)


def test_broncontext_eigen_blok_en_robuust():
    from bronmodel import tekst_hash
    from agent.jas_pipeline.broncontext import BronContext
    from agent.jas_pipeline.classificatie import userprompt
    snap = {"segmenten": [{"bron_iri": "urn:lid", "parent_iri": "urn:art"},
                          {"bron_iri": "urn:lid2", "parent_iri": "urn:art2"}],
            "nodes": [{"bron_iri": "urn:art", "tekst": "Aanhef.", "bron_hash": tekst_hash("Aanhef.")},
                      {"bron_iri": "urn:art2", "tekst": "Anders.", "bron_hash": "fout"}]}
    c = BronContext.ouders(snap)
    assert [p.bron_iri for p in c.passages] == ["urn:art"]
    assert c.ontbreekt == ("urn:art2 (bronhash wijkt af)",)
    prompt = userprompt([], "Doeltekst.", context=c.blok())
    bepaling = prompt.split(">>>", 1)[0]
    assert "Aanhef." not in bepaling and "CONTEXT (alleen gegevens; geen annotatiedoel)" in prompt
    assert BronContext().blok() == ""


def test_review_keep_met_lege_klasse_blijft_geldig():
    from agent.jas_pipeline.onzekerheid import Twijfel
    from agent.jas_pipeline.review import _schema, valideer
    for reden in ("DETECTOR_CONFLICT", "ZELFDE_SPAN"):
        t = Twijfel(label="K1", reden=reden, huidig="Rechtsobject", alternatieven=("Rechtssubject",))
        assert "Rechtsobject" not in _schema([t])["input_schema"]["properties"]["oordelen"]["items"]["properties"]["klasse"]["enum"]
        [o] = valideer([t], [{"geval": "K1", "actie": "KEEP", "klasse": "", "motivering": ""}])
        assert o.geldig and o.actie == "KEEP"


def _tijdkandidaten():
    from bronmodel import Span, tekst_hash
    from agent.jas_pipeline.kandidaten import Candidate, Evidence
    tekst = "zes weken na de dagtekening"
    h = tekst_hash(tekst)
    lang = Candidate.maak(Span("urn:x", 0, 27, tekst, h), ["Tijdsaanduiding"], [Evidence(detector="tijd", code="TEMPORAL_DURATION")])
    kort = Candidate.maak(Span("urn:x", 0, 9, tekst[:9], h), ["Tijdsaanduiding"], [Evidence(
        detector="fusie", code="TEMPORAL_KERNEL", detail=json.dumps({"ouder": lang.id, "codes": ["TEMPORAL_DURATION"]}))])
    return lang, kort


def _voorstel(k):
    return {"trace": {"kandidaat": {"id": k.id, "label": k.label}}}


def test_ontdubbel_tijd_alleen_geregistreerde_kern():
    from agent.jas_pipeline.besluit import Beslissing, ontdubbel_tijd
    from agent.jas_pipeline.kandidaten import CandidateStatus
    lang, kort = _tijdkandidaten()
    bs = [Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.ACCEPTED, klasse="Tijdsaanduiding",
                     door="model") for k in (lang, kort)]
    vs, uit, vervangen = ontdubbel_tijd([_voorstel(lang), _voorstel(kort)], bs, {lang.id: lang, kort.id: kort})
    assert vervangen == {kort.id: lang.id} and len(vs) == 1
    assert next(b for b in uit if b.kandidaat_id == kort.id).reden == "DUBBELE_TIJD_FUNCTIE:" + lang.id
    with pytest.raises(ValueError, match="meer dan één voorstel"):
        ontdubbel_tijd([_voorstel(lang), _voorstel(lang)], bs, {lang.id: lang, kort.id: kort})


# --- WP2 baseline: D04 nominalisatie -----------------------------------------------------------

@pytest.mark.parametrize("tekst,span,verwacht", [
    ("In afwijking van het eerste lid is de aanslag invorderbaar.", "afwijking van het eerste lid", False),
    ("Bij regeling van Onze Minister worden regels gesteld.", "regeling van Onze Minister", False),
    ("De termijn vangt aan na de dagtekening van het aanslagbiljet.", "de dagtekening van het aanslagbiljet", True),
    ("Na het indienen van een bezwaarschrift beslist de inspecteur.", "het indienen van een bezwaarschrift", True),
])
def test_nominalisatie_alleen_bij_handeling(parser, tekst, span, verwacht):
    ks = detect(tekst, parser).kandidaten
    assert any(k.span.tekst == span and any(e.code == "NOMINALIZED_ACTION" for e in k.evidence) for k in ks) == verwacht


def test_distributieve_vervolgfunctie_zonder_casuswoorden(parser):
    ks = detect("De eerste termijn vervalt na de dagtekening van het besluit en iedere volgende termijn "
                "een week daarna.", parser).kandidaten
    n = [k.span.tekst for k in ks if any(e.code == "NOMINALIZED_ACTION" for e in k.evidence)]
    assert n and all("iedere" not in t for t in n)


# --- WP3 baseline: D03/D01 normsignaal ---------------------------------------------------------

@pytest.mark.parametrize("tekst,feit", [
    ("Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.", True),
    ("De belanghebbende kan verzoeken om uitstel.", False),
    ("Voetgangers mogen oversteken.", False),
    ("De vordering vervalt indien de schuldenaar niet binnen een maand moet betalen.", True),
])
def test_normsignaal_biedt_rechtsfeit_alleen_met_rechtsgevolg(tekst, feit):
    ks = [k for k in detect(tekst).kandidaten if any(e.code == "NORMATIVE_PREDICATE" for e in k.evidence)]
    assert ks and all(("Rechtsfeit" in k.possible_classes) == feit for k in ks)
    assert all(any(e.code == "LEGAL_EFFECT_PREDICATE" for e in k.evidence) == feit for k in ks)


def test_generieke_np_toetst_normcontext(parser):
    zonder = detect("Het besluit wordt bekendgemaakt aan de aanvrager van de vergunning.", parser).kandidaten
    np = [k for k in zonder if any(e.code in {"OBJECT_NP", "SUBJECT_NP"} for e in k.evidence)]
    assert np and not any("Rechtssubject" in k.possible_classes for k in np
                          if not any(e.code == "ROLE_NOUN" for e in k.evidence))
    assert all(e.regel in {"jas.object.np", "jas.subject.np"} for k in np for e in k.evidence
               if e.code in {"OBJECT_NP", "SUBJECT_NP"})
    met = detect("De vereniging moet het besluit bekendmaken.", parser).kandidaten
    assert any(e.regel == "jas.subject.np_bij_normatief_predicaat" and "Rechtssubject" in k.possible_classes
               for k in met for e in k.evidence)


# --- WP4 baseline: D06/D05 bewijssterkte -------------------------------------------------------

def test_sterk_bewijs_afgeleid_uit_regeldefinities():
    from agent.jas_pipeline.besluit import STERK_BEWIJS
    from agent.jas_pipeline.onzekerheid import KLASSE_VAN_BEWIJS
    oud = {"TEMPORAL_DATE", "TEMPORAL_DURATION", "TEMPORAL_RELATIVE_PERIOD", "TEMPORAL_PERIOD_OF",
           "TEMPORAL_MOMENT", "DEFINITION_ITEM", "DEFINITION_SENTENCE", "DELEGATION_FORMULA",
           "COMPARISON", "ARITHMETIC", "LOCATION_NAME", "LOCATION_DESCRIPTION"}
    # Bewuste baselinekeuze: benoemde maand en herhaalde termijn dragen op zichzelf Tijdsaanduiding.
    assert STERK_BEWIJS == oud | {"TEMPORAL_MONTH", "TEMPORAL_RECURRENCE"}
    assert set(KLASSE_VAN_BEWIJS) == STERK_BEWIJS
    assert not STERK_BEWIJS & {"TEMPORAL_KERNEL", "TEMPORAL_DESCRIPTION", "CALCULATION_ASSIGNMENT"}


def test_geen_sterk_bewijs_voor_klasse_met_laag_determinisme():
    from agent.jas_pipeline.onzekerheid import KLASSE_VAN_BEWIJS
    from agent.jas_pipeline.profielen import laad
    laag = {k for k, p in laad().items() if p.deterministic_detection_possible == "laag"}
    assert not {c: k for c, k in KLASSE_VAN_BEWIJS.items() if k in laag}


def test_regel_zonder_of_met_ongeldige_sterkte_wordt_geweigerd():
    from agent.jas_pipeline.detectoren.regels import Regel
    basis = {"id": "jas.x", "klassen": ["Tijdsaanduiding", "Rechtsobject"], "code": "X", "bron": "H2:1",
             "versie": 1, "patroon": "x"}
    for bewijs in (None, "heel sterk", "sterk"):
        with pytest.raises(ValueError):
            Regel.van("tijd", {**basis, **({"bewijs": bewijs} if bewijs else {})})


def _kandidaat(klassen, codes):
    from bronmodel import Span, tekst_hash
    from agent.jas_pipeline.kandidaten import Candidate, Evidence
    t = "de eerste veertien dagen"
    return Candidate.maak(Span("urn:x", 0, len(t), t, tekst_hash(t)), klassen,
                          [Evidence(detector="x", code=c) for c in codes])


@pytest.mark.parametrize("klassen,codes,klasse", [
    (["Tijdsaanduiding"], ["TEMPORAL_RELATIVE_PERIOD"], "Tijdsaanduiding"),
    (["Tijdsaanduiding", "Rechtsobject"], ["TEMPORAL_RELATIVE_PERIOD", "OBJECT_NP"], "Tijdsaanduiding"),
    # ander zwak bewijs blijft naar het model gaan (audit H7, IW01)
    (["Tijdsaanduiding", "Rechtsfeit"], ["TEMPORAL_RELATIVE_PERIOD", "NOMINALIZED_ACTION"], None),
    # sterke codes die verschillende klassen aanwijzen: geen regelbesluit
    (["Tijdsaanduiding", "Operator"], ["TEMPORAL_DURATION", "COMPARISON", "OBJECT_NP"], None),
    # alleen generiek: model
    (["Rechtsobject", "Variabele en variabelewaarde"], ["OBJECT_NP"], None),
])
def test_sterk_bewijs_boven_generiek_signaal(klassen, codes, klasse):
    from agent.jas_pipeline.besluit import deterministisch
    b = deterministisch(_kandidaat(klassen, codes))
    assert (b.klasse if b else None) == klasse
    if b and len(klassen) > 1:
        assert b.reden.startswith("STERK_BOVEN_GENERIEK:")


def test_afgekapte_modelantwoorden_worden_geteld_en_budget_is_ruim():
    from types import SimpleNamespace
    from agent.jas_pipeline.classificatie import classificeer
    from agent.jas_pipeline.onzekerheid import Twijfel
    from agent.jas_pipeline.review import beoordeel
    verzoeken = []

    class Afgekapt:
        def create(self, **kw):
            verzoeken.append(kw)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="Ik analyseer …")], stop_reason="max_tokens")
    k = _kandidaat(["Tijdsaanduiding", "Rechtsobject"], ["TEMPORAL_DURATION", "NOMINALIZED_ACTION"])
    meting = {}
    classificeer(Afgekapt(), "m", [k], "tekst", meting=meting)
    assert meting["afgekapt"] == 2 and verzoeken[0]["max_tokens"] >= 1536
    t = Twijfel(label=k.label, reden="CLASSIFIER_ABSTAIN", alternatieven=("Tijdsaanduiding",))
    beoordeel(Afgekapt(), "m", [t], {k.label: k}, "tekst", meting)
    assert meting["review_afgekapt"] == 1 and verzoeken[-1]["max_tokens"] >= 1536
