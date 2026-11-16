"""Groepen zonder ruis, en relatievoorstellen uit wat er al ligt (S5)."""
from __future__ import annotations

from agent.begrippen_pipeline import besluit, signalen, taal as taal_mod
from agent.begrippen_pipeline.definities import WettelijkeTerm, Bereik
from agent.begrippen_pipeline.model import Bron, Formulering, Hypothese, Manifest, Taalanalyse


def maak(*ankers, tekst=None):
    """`ankers`: (id, tekst, klasse, term, kern)."""
    t = tekst or " ".join(a[1] for a in ankers)
    fs, taal, pos = [], {}, 0
    for i, woorden, klasse, term, kern in ankers:
        start = t.index(woorden, pos)
        fs.append(Formulering(element_id=i, bron_iri="urn:bwb:BWBR1:artikel:1", start=start, eind=start + len(woorden),
                              tekst=woorden, jas_klasse=klasse))
        taal[i] = Taalanalyse(element_id=i, term=term, kern=kern)
        pos = start + len(woorden)
    return Manifest(bronnen=[Bron(bron_iri="urn:bwb:BWBR1:artikel:1", tekst=t, bron_hash="h")], formuleringen=fs), taal


def ids(sigs):
    return {(s.van, s.naar) for s in sigs}


def test_operatoren_en_functiewoorden_groeperen_niet():
    m, taal = maak(("a", "en", "Rechtsobject", "en", "en"), ("b", "en", "Rechtsobject", "en", "en"),
                   ("c", "niet meer dan", "Operator", "niet meer dan", "dan"), ("d", "niet meer dan", "Operator", "niet meer dan", "dan"),
                   ("e", "het kader", "Rechtsobject", "kader", "kader"), ("f", "het kader", "Rechtsobject", "kader", "kader"))
    assert signalen.zelfde_term(m, taal) == []


def test_een_bepaling_bij_een_ander_woord_groepeert_niet_maar_de_term_wel():
    m, taal = maak(("a", "van een gemeente", "Rechtssubject", "gemeente", "gemeente"),
                   ("b", "de gemeente", "Rechtssubject", "gemeente", "gemeente"),
                   ("c", "een gemeente", "Rechtssubject", "gemeente", "gemeente"))
    assert ids(signalen.zelfde_term(m, taal)) == {("b", "c")}


def test_een_samengestelde_term_met_het_woord_erin_is_geen_ruis():
    f = Formulering(element_id="a", bron_iri="urn:x", start=0, eind=5, tekst="kader", jas_klasse="Rechtsobject")
    assert taal_mod.geen_begrip(f, Taalanalyse(element_id="a", term="kader", kern="kader"))
    assert not taal_mod.geen_begrip(f, Taalanalyse(element_id="a", term="toetsingskader", kern="toetsingskader"))


def test_specialisatie_in_de_term_is_een_geel_voorstel():
    m, taal = maak(("a", "de bankrekening", "Rechtsobject", "bankrekening", "bankrekening"),
                   ("b", "andere bankrekening", "Rechtsobject", "andere bankrekening", "bankrekening"))
    sigs = signalen.specialisatie_in_term(m, taal)
    assert ids(sigs) == {("a", "b")} and sigs[0].hypothese is Hypothese.HIERARCHIE
    assert sigs[0].bewijs.sterkte.value == "middel"


def test_twee_termen_uit_een_opsomming_zijn_nevenschikt():
    m, taal = maak(("a", "de aanslag", "Rechtsobject", "aanslag", "aanslag"),
                   ("b", "voorlopige aanslag", "Rechtsobject", "voorlopige aanslag", "aanslag"))
    bereik = Bereik("regeling", "urn:bwb:BWBR1")
    wts = [WettelijkeTerm(t, "urn:d", bereik, "opsomming") for t in ("aanslag", "voorlopige aanslag")]
    assert signalen.specialisatie_in_term(m, taal, wts) == []


def _met_definitie(definitie, aanhef="Deze wet verstaat onder:"):
    iri = "urn:bwb:BWBR1:artikel:2"
    m, taal = maak(("a", "de aanslag", "Rechtsobject", "aanslag", "aanslag"),
                   ("b", "het besluit", "Rechtsobject", "besluit", "besluit"))
    return m.model_copy(update={"bronnen": (*m.bronnen, Bron(bron_iri=iri, tekst=definitie, bron_hash="d", aanhef=aanhef))}), taal


def test_het_soortbegrip_uit_een_definitie():
    m, taal = _met_definitie("aanslag: het besluit dat de belasting vaststelt;")
    sigs = signalen.genus_in_definitie(m, taal, None)
    assert ids(sigs) == {("b", "a")} and sigs[0].bewijs.code == "GENUS_IN_DEFINITIE"


def test_een_opsomming_is_geen_soortbegrip():
    m, taal = _met_definitie("aanslag: het besluit, de beschikking en de uitspraak;")
    assert signalen.genus_in_definitie(m, taal, None) == []


def test_middel_bewijs_wordt_een_voorstel_geen_besluit():
    m, taal = maak(("a", "de bankrekening", "Rechtsobject", "bankrekening", "bankrekening"),
                   ("b", "andere bankrekening", "Rechtsobject", "andere bankrekening", "bankrekening"))
    from agent.begrippen_pipeline.model import Besluit, Kandidaat

    s = signalen.specialisatie_in_term(m, taal)[0]
    assert besluit.beslis(Kandidaat.maak(s.hypothese, s.van, s.naar, [s.bewijs])).besluit is Besluit.POSSIBLE_LINK
