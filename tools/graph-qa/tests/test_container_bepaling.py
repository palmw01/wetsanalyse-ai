"""Een bepaling kan een *container* zijn: haar inhoud hangt eronder, niet erin.

Waarom deze test bestaat. De importer schrijft voor een circulaire twee bomen — `heeftDivisie` voor
divisie→subdivisie en `heeftOnderdeel` voor de opsomming ván één divisie. De corpusqueries volgden
alleen `heeftOnderdeel+`. Bij bepaling 25 van de Leidraad Invordering 2008 leverde dat 76 tekens
eigen tekst plus acht opsommingsstreepjes die samen een inhoudsopgave vormen, terwijl er 81
subdivisies met ruim 43.000 tekens onder hangen. Geen fout en geen 404: `GET /v1/artikel` gaf 200
met een inhoudsopgave, en wie dat annoteerde markeerde een inhoudsopgave zonder het te merken.

De twee gevallen lopen langs verschillende queries en moeten allebei werken:

* een héél getal ("25") gaat via `get_artikel_corpus`, want `urn:bwb:BWBR0024096:artikel:25`
  bestáát — de Leidraad geeft haar top-divisies een `:artikel:`-IRI. `leden` is daardoor niet leeg
  en `_bepaling_fallback` springt juist níet aan;
* een decimaal nummer ("25.1") gaat via `_bepaling_fallback` → `get_bepaling_corpus`, omdat
  `artikel_iri` een punt weigert.

Zoals de omliggende corpus-tests speelt dit een graafantwoord na in plaats van een querytekst te
lezen: de `bwb:bevat`-bug kon anderhalve maand blijven bestaan omdat de enige test ernaar
`"bwb:bevat" in sparql` deed.
"""
from __future__ import annotations

from agent.artikel import artikel_corpus, haal_artikel_sync
from fakes import FakeGraph

# Kolommen van get_artikel_corpus (heel getal).
KOP_ARTIKEL = (
    "?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\t?sub\t?subnummer\t?subtekst"
    "\t?o\t?ouder\t?onummer\t?otekst\n"
)
# Kolommen van get_bepaling_corpus (decimaal nummer).
KOP_BEPALING = "?nummer\t?tekst\t?jci\t?sub\t?subnummer\t?subtekst\t?o\t?ouder\t?onummer\t?otekst\n"

AANHEF = "In aansluiting op artikel 25 van de wet beschrijft dit artikel het beleid over:"

# Bepaling 25: eigen aanhef, twee opsommingsstreepjes (de "inhoudsopgave"), en daaronder een lege
# tussenlaag (25.1, geen eigen tekst) met een tekstdragende subdivisie eronder (25.1.1). Die lege
# laag is geen randgeval: de negen directe subdivisies van bepaling 25 hebben samen nul tekens
# eigen tekst — de inhoud zit pas een niveau dieper.
CONTAINER = KOP_ARTIKEL + (
    f'"{AANHEF}"\t""\t""\t""\t""\t""\t""\t""'
    '\t"urn:bwb:X:id:Li1"\t""\t"–"\t"de algemene uitgangspunten van het uitstelbeleid;"\n'
    f'"{AANHEF}"\t""\t""\t""\t""\t""\t""\t""'
    '\t"urn:bwb:X:id:Li2"\t""\t"–"\t"uitstel in verband met betalingsproblemen;"\n'
    f'"{AANHEF}"\t""\t""\t""\t""\t"urn:bwb:X:id:d25.1"\t"25.1"\t""'
    '\t""\t""\t""\t""\n'
    f'"{AANHEF}"\t""\t""\t""\t""\t"urn:bwb:X:id:d25.1.1"\t"25.1.1"'
    '\t"Gedurende de behandeling van het verzoek handelt de ontvanger overeenkomstig het beleid."'
    '\t""\t""\t""\t""\n'
    f'"{AANHEF}"\t""\t""\t""\t""\t"urn:bwb:X:id:d25.2"\t"25.2"'
    '\t"De ontvanger verleent uitstel als bezwaar is gemaakt."\t""\t""\t""\t""\n'
)


def test_subdivisies_komen_in_het_corpus():
    """De inhoud onder een container komt mee, niet alleen de inhoudsopgave erboven."""
    corpus = artikel_corpus("BWBR0024096", "25", FakeGraph(result=CONTAINER))
    assert AANHEF in corpus
    assert "de algemene uitgangspunten van het uitstelbeleid;" in corpus
    assert "Gedurende de behandeling van het verzoek" in corpus
    assert "De ontvanger verleent uitstel als bezwaar is gemaakt." in corpus


def test_lege_tussenlaag_levert_geen_regel():
    """25.1 heeft geen eigen tekst en geen onderdelen; die mag geen kale regel worden."""
    info = haal_artikel_sync("BWBR0024096", "25", FakeGraph(result=CONTAINER))
    nummers = [ld["lid"] for ld in info["leden_teksten"]]
    assert "25.1" not in nummers
    assert nummers == ["", "25.1.1", "25.2"]


def test_subdivisies_staan_in_documentvolgorde():
    """Per punt-segment numeriek: 25.2 komt vóór 25.10, niet erna (lexicaal zou dat omdraaien)."""
    rijen = CONTAINER + (
        f'"{AANHEF}"\t""\t""\t""\t""\t"urn:bwb:X:id:d25.10"\t"25.10"'
        '\t"De laatste subdivisie."\t""\t""\t""\t""\n'
    )
    info = haal_artikel_sync("BWBR0024096", "25", FakeGraph(result=rijen))
    assert [ld["lid"] for ld in info["leden_teksten"]] == ["", "25.1.1", "25.2", "25.10"]


def test_onderdelen_van_een_subdivisie_horen_bij_die_subdivisie():
    """Anders zou de opsomming van 25.2 als losse opsomming van bepaling 25 worden gelezen."""
    rijen = KOP_ARTIKEL + (
        f'"{AANHEF}"\t""\t""\t""\t""\t"urn:bwb:X:id:d25.2"\t"25.2"'
        '\t"De ontvanger verleent uitstel als:"'
        '\t"urn:bwb:X:id:d25.2/Li1"\t""\t"–"\t"het bezwaar tijdig is ingediend;"\n'
    )
    info = haal_artikel_sync("BWBR0024096", "25", FakeGraph(result=rijen))
    leden = {ld["lid"]: ld["tekst"] for ld in info["leden_teksten"]}
    assert "– het bezwaar tijdig is ingediend;" in leden["25.2"]
    # De aanhef van de container blijft schoon: het onderdeel hoort niet bij háár.
    assert "het bezwaar tijdig is ingediend" not in leden[""]


def test_lid_filter_scopet_naar_een_subbepaling():
    """Het bestaande lid-filter is de weg om één subbepaling te annoteren."""
    info = haal_artikel_sync("BWBR0024096", "25", FakeGraph(result=CONTAINER), lid="25.2")
    assert [ld["lid"] for ld in info["leden_teksten"]] == ["25.2"]
    assert info["corpus"].startswith("25.2. ")
    # 25.1.1 mag hier niet in meeliften: op alleen het eerste segment vergelijken zou dat wel doen.
    assert "Gedurende de behandeling" not in info["corpus"]


def test_decimale_container_via_de_bepaling_fallback():
    """Hetzelfde gedrag langs de andere query: '25.1' weigert `artikel_iri` wegens de punt."""
    # `artikel_iri` weigert de punt, dus get_artikel_corpus wordt niet eens uitgevoerd; de enige
    # query die de graaf bereikt is get_bepaling_corpus.
    bepaling = KOP_BEPALING + (
        '"25.1"\t""\t""\t"urn:bwb:X:id:d25.1.1"\t"25.1.1"'
        '\t"Gedurende de behandeling van het verzoek handelt de ontvanger."\t""\t""\t""\t""\n'
        '"25.1"\t""\t""\t"urn:bwb:X:id:d25.1.2"\t"25.1.2"'
        '\t"De ontvanger wijst het verzoek af als de belangen van de Staat worden geschaad."'
        '\t""\t""\t""\t""\n'
    )
    corpus = artikel_corpus("BWBR0024096", "25.1", FakeGraph(result=bepaling))
    assert "Gedurende de behandeling van het verzoek" in corpus
    assert "belangen van de Staat" in corpus


def test_gewoon_artikel_blijft_ongewijzigd():
    """Geen regressie: een artikel met leden mag geen subbepalingsrijen krijgen."""
    rijen = KOP_ARTIKEL + (
        '""\t""\t"urn:bwb:Y:artikel:9:lid:1"\t"1"\t"De ontvanger kan uitstel verlenen."'
        '\t""\t""\t""\t""\t""\t""\t""\n'
        '""\t""\t"urn:bwb:Y:artikel:9:lid:2"\t"2"\t"Het uitstel wordt schriftelijk verleend."'
        '\t""\t""\t""\t""\t""\t""\t""\n'
    )
    info = haal_artikel_sync("BWBR0004770", "9", FakeGraph(result=rijen))
    assert [ld["lid"] for ld in info["leden_teksten"]] == ["1", "2"]
    assert info["corpus"] == (
        "1. De ontvanger kan uitstel verlenen.\n\n2. Het uitstel wordt schriftelijk verleend."
    )


def test_vindplaats_noemt_een_divisie_geen_artikel():
    """"art. 25.1 lid 2" is een vindplaats die niet bestaat: een divisie heeft geen leden."""
    from agent.annotatie import aanduiding_in_woorden

    assert aanduiding_in_woorden("9", "1", "Artikel") == "art. 9 lid 1"
    assert aanduiding_in_woorden("25", "", "Divisie") == "bepaling 25"
    assert aanduiding_in_woorden("25", "25.1.1", "Divisie") == "bepaling 25, 25.1.1"
    # Onbekend soort valt terug op wat er stond — bij de zes wet-achtige regelingen is dat juist.
    assert aanduiding_in_woorden("9", "1", "") == "art. 9 lid 1"


def test_soort_komt_uit_de_graaf_mee():
    """Het knooptype reist met het corpus mee, zodat er geen tweede SPARQL-call voor nodig is."""
    rijen = KOP_ARTIKEL.replace("?tekst\t", "?tekst\t?soort\t", 1) + (
        f'"{AANHEF}"\t"urn:bwb-ns:Divisie"\t""\t""\t""\t""\t"urn:bwb:X:id:d25.2"\t"25.2"'
        '\t"De ontvanger verleent uitstel."\t""\t""\t""\t""\n'
    )
    info = haal_artikel_sync("BWBR0024096", "25", FakeGraph(result=rijen))
    assert info["soort"] == "Divisie"
