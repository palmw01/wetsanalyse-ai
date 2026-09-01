"""Het annotatiecorpus draagt de onderdelen van een lid.

Waarom deze test bestaat, en waarom hij een graafantwoord naspeelt in plaats van een querytekst te
lezen. Een definitielid ís zonder zijn onderdelen leeg: artikel 2, lid 1 IW 1990 heeft als eigen
tekst alleen "Deze wet verstaat onder:" en 21 definities in de onderdelen eronder. Toch stond er
tot 1 sep 2026 alleen die aanhef in het corpus, én leverde de tool `get_lid` nooit één onderdeel —
die bevroeg `bwb:bevat`, een predicaat dat de importer nergens schrijft.

Dat kon anderhalve maand blijven bestaan omdat de enige test ernaar `"bwb:bevat" in sparql` deed.
Een querytekst toetsen bewijst niet dat er data uitkomt. Een jurist liep er wél tegenaan: hij vroeg
"annoteer artikel 6, neem ook de onderdelen mee", de agent kreeg alleen de aanhef terug en ging
zoeken naar een omweg — met een onopenbaar annotatiedocument als resultaat.

Deze test voedt daarom een FakeGraph met rijen zoals de graaf ze levert, en kijkt naar het corpus.
"""
from __future__ import annotations

from agent.artikel import artikel_corpus, haal_artikel_sync
from fakes import FakeGraph

# Zoals `get_artikel_corpus` het teruggeeft: één rij per (lid, onderdeel). Lid 1 is een
# definitieaanhef met drie onderdelen, waarvan één (`aa.`) een lege container met een genest kind.
CORPUS_TSV = (
    "?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\t?o\t?onummer\t?otekst\n"
    '""\t""\t"urn:bwb:X:artikel:2:lid:1"\t"1"\t"Deze wet verstaat onder:"'
    '\t"urn:bwb:X:artikel:2:lid:1:o:a"\t"a."\t"rijksbelastingen: belastingen als bedoeld in artikel 1;"\n'
    '""\t""\t"urn:bwb:X:artikel:2:lid:1"\t"1"\t"Deze wet verstaat onder:"'
    '\t"urn:bwb:X:artikel:2:lid:1:o:aa"\t"aa."\t""\n'
    '""\t""\t"urn:bwb:X:artikel:2:lid:1"\t"1"\t"Deze wet verstaat onder:"'
    '\t"urn:bwb:X:artikel:2:lid:1:o:aa:o:1"\t"1°."\t"het eerste genest onderdeel;"\n'
    '""\t""\t"urn:bwb:X:artikel:2:lid:2"\t"2"\t"Het tweede lid zonder onderdelen."\t""\t""\t""\n'
)


def test_onderdelen_staan_in_het_corpus():
    corpus = artikel_corpus("BWBR0004770", "2", FakeGraph(result=CORPUS_TSV))
    assert "Deze wet verstaat onder:" in corpus
    assert "a. rijksbelastingen: belastingen als bedoeld in artikel 1;" in corpus
    assert "1°. het eerste genest onderdeel;" in corpus, "geneste onderdelen horen er ook in"


def test_de_lidtekst_herhaalt_zich_niet_per_onderdeel():
    """De query levert één rij per (lid, onderdeel); die worden weer één lid."""
    corpus = artikel_corpus("BWBR0004770", "2", FakeGraph(result=CORPUS_TSV))
    assert corpus.count("Deze wet verstaat onder:") == 1


def test_leeg_onderdeel_wordt_overgeslagen():
    """'aa.' is een container voor de geneste onderdelen eronder en heeft zelf geen tekst.

    Zonder deze regel staat er een kale "aa." in de wettekst die de jurist leest — en dan kan een
    markering daarop landen die nergens naar verwijst.
    """
    corpus = artikel_corpus("BWBR0004770", "2", FakeGraph(result=CORPUS_TSV))
    assert "aa." not in corpus


def test_onderdelen_staan_onder_hun_eigen_lid():
    corpus = artikel_corpus("BWBR0004770", "2", FakeGraph(result=CORPUS_TSV))
    lid1, lid2 = corpus.split("\n\n")
    assert lid1.startswith("1. Deze wet verstaat onder:")
    assert "a. rijksbelastingen" in lid1
    assert lid2 == "2. Het tweede lid zonder onderdelen."
    assert "rijksbelastingen" not in lid2


def test_lid_scoping_neemt_de_onderdelen_mee():
    """Vraagt de jurist één lid, dan hoort dát lid compleet te zijn — inclusief onderdelen."""
    corpus = artikel_corpus("BWBR0004770", "2", FakeGraph(result=CORPUS_TSV), lid="1")
    assert corpus.startswith("1. Deze wet verstaat onder:")
    assert "a. rijksbelastingen" in corpus
    assert "Het tweede lid" not in corpus


def test_het_documentpaneel_krijgt_dezelfde_tekst():
    """`GET /v1/artikel` en het annotatiecorpus delen één functie; die eenheid is de invariant.

    Loopt dit uiteen, dan annoteert de agent op andere tekst dan de jurist ziet — en dan wijzen de
    ankers naar posities die in het paneel niet bestaan.
    """
    graaf = FakeGraph(result=CORPUS_TSV)
    resultaat = haal_artikel_sync("BWBR0004770", "2", graaf)
    leden = resultaat["leden_teksten"]
    uit_leden = "\n\n".join(
        f'{ld["lid"]}. {ld["tekst"]}' if ld["lid"] else ld["tekst"] for ld in leden
    )
    assert uit_leden == artikel_corpus("BWBR0004770", "2", FakeGraph(result=CORPUS_TSV))
