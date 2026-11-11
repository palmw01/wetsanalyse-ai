"""De tekst van een paragraaf zonder artikelen (`<structuurtekst>`) komt helemaal in de graaf.

Het Besluit Bestuurlijke Boeten Belastingdienst (BWBR0038145) deelt zijn tekst in paragrafen in, elk met een
`<structuurtekst>` van genummerde punten, zonder `<artikel>`. De lezer kende die structuur niet, en de hele tekst viel weg
(dekking 0%, iteratie wetgeving_live 11 nov 2026, I12). Nu is zo'n structuurtekst een divisie onder de paragraaf, met haar
nummer en titel: dezelfde node als een divisie van een circulaire.
"""
from __future__ import annotations

from pathlib import Path

from bronmodel.bwb.boom import divisies, model_tekens
from bronmodel.bwb.dekking import bron_tekens
from bronmodel.bwb.parser import ToestandParser
from rdflib import Literal

from app.dekking import meet
from app.graphdb_writer import GraphDbWriter
from app.rdf_vocab import Vocab

FIXTURE = Path(__file__).parent / "fixtures" / "sample_structuurtekst.xml"


def test_een_structuurtekst_is_een_divisie_onder_de_paragraaf() -> None:
    wet = ToestandParser().parse(FIXTURE)
    assert not wet.overgeslagen
    paragraaf = wet.structuurdelen[0].subdelen[0]
    assert paragraaf.soort == "paragraaf" and not paragraaf.artikelen
    [d] = paragraaf.divisies
    assert (d.nummer, d.label, d.titel) == ("1", "§ 1", "Reikwijdte")
    assert d.tekst == "Dit besluit regelt het testbeleid."
    assert [o.nummer for o in d.onderdelen] == ["1.", "2."]
    # De verwijzing staat in punt 1, dus bij dat onderdeel (zoals bij een circulaire), niet bij de divisie.
    assert d.bron == "Stcrt.2026-27767" and not d.verwijzingen and d.onderdelen[0].verwijzingen
    assert [x.nummer for x in divisies(wet)] == ["1", "2"]


def test_alle_tekst_van_de_structuurtekst_haalt_de_graaf() -> None:
    wet = ToestandParser().parse(FIXTURE)
    assert model_tekens(wet) == bron_tekens(FIXTURE) > 0
    dekking = meet(FIXTURE)
    assert dekking.ontbrekend == 0, dekking.regel()


def test_de_graaf_draagt_de_divisie_met_haar_tekst_onder_de_paragraaf() -> None:
    vocab = Vocab()
    graaf = GraphDbWriter(url="o", repository="o", vocab=vocab).build_graph(ToestandParser().parse(FIXTURE))[0]
    teksten = {str(o) for o in graaf.objects(None, vocab.p("tekst"))} if hasattr(vocab, "p") else {
        str(o) for s, p, o in graaf if str(p).endswith("tekst") and isinstance(o, Literal)}
    assert "In dit besluit wordt verstaan onder boete: een bestuurlijke boete." in teksten
    assert any("Het geldt voor de heffing van de AWR." in t for t in teksten)
