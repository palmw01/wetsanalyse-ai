"""Het corpus van een bepaling (beleidsregel met decimaal nummer) draagt haar onderdelen.

Waarom deze test bestaat. Bij zo'n bepaling zit de inhoud vaak in de opsomming eronder. Gemeten in
de Leidraad Invordering 2008: 153 van de 800 bepalingen hebben onderdelen, samen goed voor 99.329
tekens — méér dan hun eigen tekst bij elkaar (87.255). Bepaling 26.1.9 heeft 221 tekens eigen tekst
("Er wordt geen kwijtschelding verleend als:") en 16 onderdelen met 6.128 tekens; wie die annoteerde
markeerde de aankondiging en miste alle zestien voorwaarden.

Zes bepalingen hebben zelfs alléén onderdelen en geen eigen tekst (14.2.4, 14.2a, 25.4.6, 73.3a.2).
`get_bepaling` eiste `bwb:tekst`, dus die gaven niets terug: niet te openen, niet te annoteren.

Zoals `test_artikel_onderdelen.py` speelt deze test een graafantwoord na in plaats van een
querytekst te lezen. Dat onderscheid is niet academisch: de `bwb:bevat`-bug kon anderhalve maand
blijven bestaan omdat de enige test ernaar `"bwb:bevat" in sparql` deed.
"""
from __future__ import annotations

from agent.artikel import artikel_corpus
from fakes import FakeGraph

KOP = "?nummer\t?tekst\t?jci\t?o\t?onummer\t?otekst\n"

# Bepaling 26.1.9: eigen aankondiging + onderdelen met een en-dash als opsommingsteken, zoals de
# Leidraad ze nummert.
MET_TEKST = KOP + (
    '"26.1.9"\t"Er wordt geen kwijtschelding verleend als:"\t""'
    '\t"urn:bwb:X:id:Li1"\t"–"\t"voor de desbetreffende belastingaanslag zekerheid is gesteld;"\n'
    '"26.1.9"\t"Er wordt geen kwijtschelding verleend als:"\t""'
    '\t"urn:bwb:X:id:Li2"\t"–"\t"er sprake is van meer dan één belastingschuldige;"\n'
)

# Een bepaling zónder eigen tekst: alleen onderdelen.
ZONDER_TEKST = KOP + (
    '"14.2.4"\t""\t""\t"urn:bwb:X:id:Li1"\t"–"\t"Het beslag wordt gelegd op zoveel zaken als nodig is."\n'
    '"14.2.4"\t""\t""\t"urn:bwb:X:id:Li2"\t"–"\t"De deurwaarder maakt daarvan proces-verbaal op."\n'
)


def test_onderdelen_staan_in_het_bepaling_corpus():
    corpus = artikel_corpus("BWBR0024096", "26.1.9", FakeGraph(result=MET_TEKST))
    assert corpus.startswith("Er wordt geen kwijtschelding verleend als:")
    assert "– voor de desbetreffende belastingaanslag zekerheid is gesteld;" in corpus
    assert "– er sprake is van meer dan één belastingschuldige;" in corpus


def test_het_opsommingsteken_komt_mee_zoals_de_bron_het_geeft():
    """De Leidraad nummert met een en-dash, niet met "a." of "1°.".

    Overnemen zoals de bron het geeft: bij een voorwaardenlijst draagt de opsommingsstructuur
    betekenis, en de jurist ziet in het paneel wat er in de wet staat.
    """
    corpus = artikel_corpus("BWBR0024096", "26.1.9", FakeGraph(result=MET_TEKST))
    assert corpus.count("– ") == 2


def test_de_eigen_tekst_herhaalt_zich_niet_per_onderdeel():
    corpus = artikel_corpus("BWBR0024096", "26.1.9", FakeGraph(result=MET_TEKST))
    assert corpus.count("Er wordt geen kwijtschelding verleend als:") == 1


def test_bepaling_zonder_eigen_tekst_is_niet_leeg():
    """Zes bepalingen in de Leidraad bestaan alléén uit hun opsomming.

    Die gaven niets terug zolang `bwb:tekst` een harde eis was — geen documentpaneel, geen corpus,
    dus niet te annoteren. Er stond geen foutmelding tegenover: de bepaling leek simpelweg leeg.
    """
    corpus = artikel_corpus("BWBR0024096", "14.2.4", FakeGraph(result=ZONDER_TEKST))
    assert corpus, "een bepaling met alleen onderdelen hoort een corpus te hebben"
    assert "– Het beslag wordt gelegd op zoveel zaken als nodig is." in corpus
    assert "– De deurwaarder maakt daarvan proces-verbaal op." in corpus


def test_bepaling_krijgt_geen_lidnummer_voorvoegsel():
    """Een bepaling heeft geen lid; `regelsVan` in de frontend rendert een lege `lid` zonder prefix.

    Zou er toch een nummer voor komen, dan staat elk fragment één voorvoegsel verschoven ten
    opzichte van wat de jurist ziet.
    """
    corpus = artikel_corpus("BWBR0024096", "26.1.9", FakeGraph(result=MET_TEKST))
    assert not corpus.startswith("26.1.9.")
    assert not corpus.startswith(". ")
