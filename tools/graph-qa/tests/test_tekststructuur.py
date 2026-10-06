"""Technische acceptatiegevallen en laageigenschappen; geen juridische goldset."""
import re

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles, standaard_detectoren
from agent.jas_pipeline.detectoren.regels import maskers
from agent.jas_pipeline.detectoren.structuur import BetekenisDetector, DefinitieDetector
from agent.jas_pipeline.detectoren.syntactisch import NormDetector
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.taal import NullProvider
from agent.jas_pipeline.taal.grenzen import analyseer_grenzen
from agent.jas_pipeline.taal.structuur import herken_onderdelen


@pytest.mark.parametrize("notatie", ["artikel 3:4", "artikel 9.1", "art. 4", "€ 1.000", "€ 1.000,50", "3,5%"])
@pytest.mark.parametrize("volgorde", ["voor", "na"])
def test_norm_en_terugval_splitsen_geen_notatie_en_behouden_volgende_zin(notatie, volgorde):
    eerste = (f"Volgens {notatie} moet hij betalen." if volgorde == "voor"
              else f"Hij moet betalen volgens {notatie}.")
    tweede = "Daarna mag hij vertrekken."
    tekst = eerste + " " + tweede
    bron = BronTekst.van_tekst("urn:test", tekst)
    assert [k.span.tekst for k in NormDetector().detecteer(bron).kandidaten] == [eerste, tweede]
    analyse = NullProvider().analyseer(tekst)
    assert [tekst[z.start:z.eind] for z in analyse.zinnen] == [eerste, tweede]


def test_bescherming_en_onderdrukking_zijn_verschillende_toepassingen():
    tekst = "Hij moet volgens artikel 9.1 € 1.000 betalen; daarna mag hij gaan."
    g = analyseer_grenzen(tekst)
    beschermd = {(tekst[b.start:b.eind], b.reden) for b in g.beschermd}
    assert ("artikel 9.1", "verwijzing:artikel") in beschermd
    assert ("1.000", "numeriek") in beschermd
    assert [(b.start, b.eind) for b in g.beschermd if b.reden == "verwijzing:artikel"] == maskers(tekst)["verwijzing"]
    # Geld blijft kandidaat, ondanks bescherming van de duizendpunt.
    ks = [k for r in detecteer_alles(BronTekst.van_tekst("test", tekst)) for k in r.kandidaten]
    assert any(k.span.tekst == "€ 1.000" for k in ks)
    assert not any(k.span.tekst == "9.1" for k in ks)


def test_zinsgrenzen_segmentgrenzen_en_labels_hebben_eigen_redenen():
    tekst = "a. Hij moet betalen: € 1.000; daarna mag hij gaan."
    g = analyseer_grenzen(tekst)
    assert len(g.zinnen(tekst)) == 1 and len(g.segmenten(tekst)) == 3
    assert {b.reden for b in g.beschermd} >= {"onderdeelnummer", "numeriek"}
    assert {b.reden for b in g.segmentgrenzen} == {"leesteken::", "leesteken:;", "leesteken:."}
    assert [k.span.tekst for k in NormDetector().detecteer(BronTekst.van_tekst("test", tekst)).kandidaten] == [
        "Hij moet betalen", "daarna mag hij gaan."]


@pytest.mark.parametrize("tekst,verwacht", [
    ("Zie bijv. de aanvraag. Hij mag gaan.", ["Zie bijv. de aanvraag.", "Hij mag gaan."]),
    ("Hij mag gaan enz. Daarna moet hij betalen.", ["Hij mag gaan enz.", "Daarna moet hij betalen."]),
    ("Mr. Jansen mag gaan. Hij moet betalen.", ["Mr. Jansen mag gaan.", "Hij moet betalen."]),
    ("1°. Hij moet volgens\nart. 4 betalen. Hij mag gaan.",
     ["1°. Hij moet volgens\nart. 4 betalen.", "Hij mag gaan."]),
    ("Hij mag gaan\n\nHij moet betalen", ["Hij mag gaan", "Hij moet betalen"]),
    ("Hij gaat af. Zij mag gaan.", ["Hij gaat af.", "Zij mag gaan."]),
])
def test_afkorting_nummering_en_tekstomloop(tekst, verwacht):
    assert [tekst[z.start:z.eind] for z in NullProvider().analyseer(tekst).zinnen] == verwacht


DEFINITIE = "In deze wet wordt verstaan onder:"
BETEKENIS = "Bij voetgangerslichten betekent:"


@pytest.mark.parametrize("detector,aanhef,verwacht", [
    (DefinitieDetector(), DEFINITIE, ["aanvraag: het verzoek;", "besluit: de beslissing."]),
    (BetekenisDetector(), BETEKENIS, ["aanvraag", "besluit"]),
])
@pytest.mark.parametrize("opmaak", ["één regel", "regels", "kindnodes"])
def test_onderdelen_onafhankelijk_van_opmaak(detector, aanhef, verwacht, opmaak):
    onderdelen = ["a. aanvraag: het verzoek;", "b. besluit: de beslissing."]
    if opmaak == "kindnodes":
        bronnen = [BronTekst.van_tekst(f"urn:kind:{i}", t, context=aanhef) for i, t in enumerate(onderdelen)]
    else:
        sep = " " if opmaak == "één regel" else "\n"
        bronnen = [BronTekst.van_tekst("urn:ouder", sep.join([aanhef, *onderdelen]))]
    ks = [k for b in bronnen for k in detector.detecteer(b).kandidaten]
    assert [k.span.tekst for k in ks] == verwacht
    for k in ks:
        bron = next(b for b in bronnen if b.bron_iri == k.span.bron_iri)
        assert bron.tekst[k.span.start:k.span.eind] == k.span.tekst


@pytest.mark.parametrize("context", [True, False])
def test_ongelabeld_onderdeel_en_meerledige_omschrijving(context):
    onderdeel = "aanvraag: een verzoek\nmet als toelichting: betaal tijdig; ook de bijlage hoort erbij."
    tekst = onderdeel if context else DEFINITIE + " " + onderdeel
    bron = BronTekst.van_tekst("urn:kind", tekst, context=DEFINITIE if context else "")
    [k] = DefinitieDetector().detecteer(bron).kandidaten
    assert k.span.tekst == onderdeel
    delen = herken_onderdelen(tekst, bron.context, re.compile("wordt verstaan onder:"))
    [deel] = delen
    assert deel.aanhef.bron == ("ouder" if context else "eigen")
    assert tekst[deel.omschrijving.start:deel.omschrijving.eind].startswith("een verzoek\n")


@pytest.mark.parametrize("tekst", [
    "Toelichting: een verzoek; gevolg: een besluit.",
    "a. aanvraag: het verzoek; b. besluit: de beslissing.",
    "Hij zegt: betaal tijdig.",
])
def test_dubbele_punt_en_nummering_zonder_aanhef_zijn_geen_definitie_of_betekenis(tekst):
    for detector in (DefinitieDetector(), BetekenisDetector()):
        assert detector.detecteer(BronTekst.van_tekst("test", tekst)).kandidaten == ()


def test_geen_onderdelen_voor_de_aanhef_en_geen_oudertekst_als_span():
    tekst = "Toelichting: iets anders. " + DEFINITIE + " aanvraag: een verzoek."
    [k] = DefinitieDetector().detecteer(BronTekst.van_tekst("test", tekst)).kandidaten
    assert k.span.tekst == "aanvraag: een verzoek."
    assert not DefinitieDetector().detecteer(BronTekst.van_tekst("test", "", context=tekst)).kandidaten


@pytest.mark.parametrize("tekst", [
    "", " \n\t", "😀 Hij moet volgens artikel 3:4 € 1.000 betalen. Daarna mag hij gaan.",
    DEFINITIE + " a. coöperatie: een éénheid; b. éé́nheid: een geheel.",
    BETEKENIS + " a. groen licht: voetgangers mogen\noversteken; b. rood licht: stoppen.",
])
def test_hele_detectielaag_is_brongetrouw_reproduceerbaar_en_herleidbaar(tekst):
    bron = BronTekst.van_tekst("urn:eigenschap", tekst, analyse=NullProvider().analyseer(tekst))
    rs = detecteer_alles(bron)
    assert rs == detecteer_alles(bron)
    f = fuseer(rs)
    assert f == fuseer(detecteer_alles(bron))
    for detector, r in zip(standaard_detectoren(), rs):
        assert (r.detector, r.versie) == (detector.naam, detector.versie)
        assert not r.overgeslagen or (r.reden and not r.kandidaten)
        for k in r.kandidaten:
            bs = [b for b in r.bijdragen if b.kandidaat_id == k.id]
            assert bs and all((b.detector, b.versie) == (r.detector, r.versie) for b in bs)
            assert set(k.evidence) == {e for b in bs for e in b.bewijs}
        assert all(b in f.bijdragen for b in r.bijdragen)
    for k in f.kandidaten:
        for s in [k.span, *(o.span for o in k.span_options)]:
            assert 0 <= s.start < s.eind <= len(tekst)
            assert s.tekst == tekst[s.start:s.eind]
            assert (s.bron_iri, s.bron_hash) == (bron.bron_iri, bron.bron_hash)


@pytest.mark.parametrize("afwijking", [{"detector": "ander"}, {"versie": "oud"}, {"bron_iri": "andere-bron"}])
def test_detectoruitvoering_weigert_identiteitsdrift(afwijking):
    class Kapot(NormDetector):
        def detecteer(self, bron):
            return super().detecteer(bron).model_copy(update=afwijking)
    with pytest.raises(ValueError, match="detectorcontract"):
        detecteer_alles(BronTekst.van_tekst("test", "Hij moet betalen."), [Kapot()])


def test_detectoruitvoering_verbergt_geen_technische_fout():
    class Kapot(NormDetector):
        def detecteer(self, bron):
            raise RuntimeError("defecte detector")
    with pytest.raises(RuntimeError, match="defecte detector"):
        detecteer_alles(BronTekst.van_tekst("test", "tekst"), [Kapot()])


def test_parse_zinnen_en_dependencies_worden_niet_achteraf_herschreven():
    from test_taalanalyse import _analyse
    a = _analyse()
    vooraf = repr(a)
    detecteer_alles(BronTekst.van_tekst("test", a.tekst, analyse=a))
    assert repr(a) == vooraf and not a.gedegradeerd


@pytest.mark.parametrize("analyse", [None, NullProvider().analyseer(""), "volledig"])
def test_versies_zijn_gelijk_bij_overslaan_en_nul_treffers(analyse):
    from agent.jas_pipeline.taal import LinguisticAnalysis
    if analyse == "volledig":
        analyse = LinguisticAnalysis("", (), (), "hand")
    rs = detecteer_alles(BronTekst.van_tekst("test", "", analyse=analyse))
    assert not any(r.kandidaten for r in rs)
    assert {r.detector: r.versie for r in rs} == {d.naam: d.versie for d in standaard_detectoren()}
    assert sum(r.overgeslagen for r in rs) == (0 if analyse and not analyse.gedegradeerd else 6)
