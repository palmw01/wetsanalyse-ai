"""Het anker ligt in het lid dat het element zelf noemt.

Waarom deze test bestaat. `_verwerk` bepaalde het lid en de positie langs gescheiden wegen: het lid
kwam van het model (of van `scope_lid`), de positie was het *eerste* voorkomen in het *hele* corpus.
Bij een artikel van meerdere leden lopen die uit elkaar zodra een fragment vaker voorkomt — en dan
belooft de vindplaats iets anders dan de werkplek aanwijst.

Gemeten op de annotatie van artikel 6 Uitvoeringsregeling Awir van 1 sep 2026: van de 43 markeringen
kwamen er 9 meer dan eens in het corpus voor, en 2 daarvan kregen een anker in het verkeerde lid.
Het scherpste geval is "derde" (9x in het corpus): het element gaat over het rechtssubject in lid 2
("van een derde die:"), maar het anker landde op offset 43 — het rangtelwoord in "artikel 25, derde
lid, van de wet" in lid 1. Dat is niet alleen de verkeerde plek maar ook de verkeerde woordsoort.

Het corpus hieronder is de letterlijke tekst zoals `artikel_corpus` hem opbouwt, inclusief de
onderdelen die sinds #395 meekomen.
"""
from __future__ import annotations

from agent.annotatie import _lid_segmenten, _verwerk

LEDEN = [
    ('1', 'Als gevallen als bedoeld in artikel 25, derde lid, van de wet worden aangewezen uitbetalingen door de Dienst Toeslagen:\na. van kinderopvangtoeslag op de bankrekening van een onderneming als bedoeld in de Handelsregisterwet 2007, die een of meerdere kindercentra of een of meerdere gastouderbureaus exploiteert, als bedoeld in artikel 1.1, eerste lid, van de Wet kinderopvang en kwaliteitseisen peuterspeelzalen;\nb. van huurtoeslag op de bankrekening van een toegelaten instelling, als bedoeld in artikel 19 van de Woningwet;\nc. van zorgtoeslag op de bankrekening van een zorgverzekeraar, als bedoeld in artikel 1, onderdeel b, van de Zorgverzekeringswet; voor zover de onderneming, instelling of zorgverzekeraar voor dit doel een convenant heeft afgesloten met de Dienst Toeslagen.'),
    ('2', 'Als gevallen als bedoeld in artikel 25, derde lid, van de wet worden voorts aangewezen uitbetalingen door de Dienst Toeslagen op de bankrekening:\na. van een lid van de Nederlandse Vereniging voor Volkskrediet voor zover de uitbetaling plaatsvindt in het kader van de uitvoering van een schuldregelingsovereenkomst in de zin van de Gedragscode Schuldregeling of een overeenkomst tot budgetbeheer in de zin van de Gedragscode Budgetbeheer;\nb. van een gemeente op grond van een schuldregelingsovereenkomst in de zin van de Gedragscode Schuldregeling of een overeenkomst tot budgetbeheer in de zin van de Gedragscode Budgetbeheer van de Nederlandse Vereniging voor Volkskrediet of overeenkomsten met dezelfde strekking;\nc. van een derde die: voor zover de uitbetaling plaatsvindt in het kader van de uitvoering van een schuldregelingsovereenkomst in de zin van de Gedragscode Schuldregeling of een overeenkomst tot budgetbeheer in de zin van de Gedragscode Budgetbeheer of overeenkomsten met dezelfde strekking;\n1°. een subsidiebeschikking heeft ontvangen van een gemeente dan wel een overeenkomst heeft met een Wlz-uitvoerder voor het leveren van zorg in natura ingevolge de Wet langdurige zorg; en\n2°. voldoet aan de norm NEN-ISO 9001;\nd. van een curator in een faillissement;\ne. van een bewindvoerder in een schuldsaneringsregeling natuurlijke personen;\nf. van een derde, die meerderjarig en handelingsbekwaam is, indien een belanghebbende niet beschikt over een bankrekening die op zijn naam staat, naar het oordeel van de Dienst Toeslagen niet in staat is een bankrekening op zijn naam te openen door zijn lichamelijke of geestelijke toestand, en de belanghebbende hierom verzoekt.'),
    ('3', 'Bij gevallen als bedoeld artikel 7a, vierde lid, van de Invorderingswet 1990 is artikel 25, eerste lid, tweede volzin, van de wet niet van toepassing.'),
    ('4', 'Indien op grond van artikel 25, derde lid, van de wet de uitbetaling van een voorschot of een tegemoetkoming plaatsvindt op een andere bankrekening dan die van de belanghebbende of diens partner, vindt het gegevensverkeer met betrekking tot de uitbetaling tussen de Dienst Toeslagen en die rekeninghouder plaats met gebruikmaking van het burgerservicenummer van de belanghebbende.'),
    ('5', 'Bij toepassing van het tweede lid, onderdelen a tot en met c, wijst het aldaar bedoelde lid, de aldaar bedoelde gemeente of de aldaar bedoelde derde aan op welke bankrekening wordt uitbetaald, ten behoeve van welke belanghebbende en voor welke uitbetaling. Voorts wordt melding gemaakt van de beëindiging van de in het tweede lid, onderdelen a tot en met c, bedoelde overeenkomst.'),
]
CORPUS = "\n\n".join(f"{lid}. {tekst}" for lid, tekst in LEDEN)

# De twee markeringen uit de live-annotatie die in het verkeerde lid landden, plus een derde
# ("Dienst Toeslagen") die vandaag toevallig goed gaat omdat zijn eerste voorkomen al in lid 1 ligt.
ELEMENTEN = """{"elementen": [
  {"klasse": "Rechtssubject", "tekst": "derde", "lid": "2", "toelichting": "het rechtssubject in onderdeel c"},
  {"klasse": "Rechtsobject", "tekst": "bankrekening", "lid": "4", "toelichting": "de rekening waarop wordt uitbetaald"},
  {"klasse": "Rechtssubject", "tekst": "Dienst Toeslagen", "lid": "1", "toelichting": "het uitvoerende bestuursorgaan"}
]}"""


def _per_klasse(voorstellen):
    return {v.tekst: v for v in voorstellen}


def _lid_van_offset(offset: int) -> str:
    for nummer, start, eind in _lid_segmenten(CORPUS):
        if start <= offset < eind:
            return nummer
    return ""


def test_anker_ligt_in_het_lid_dat_het_element_noemt():
    """De regressie zelf: zonder lid-scoping landt "derde" op offset 43, in lid 1."""
    voorstellen, _ = _verwerk(ELEMENTEN, CORPUS, "BWBR0019237", "6")
    derde = _per_klasse(voorstellen)["derde"]
    assert derde.lid == "2"
    assert _lid_van_offset(derde.anker.start) == "2", (
        f"anker op {derde.anker.start} ligt in lid {_lid_van_offset(derde.anker.start)}"
    )
    assert CORPUS[derde.anker.start:derde.anker.eind] == "derde"


def test_zonder_onderdeel_blijft_een_kort_fragment_ambigu():
    """Lid-scoping garandeert het juiste lid, niet het juiste voorkomen bínnen dat lid.

    Lid 2 opent met dezelfde verwijzing als lid 1 ("artikel 25, derde lid"), dus zonder verdere
    aanwijzing landt "derde" op het rangtelwoord in plaats van op het rechtssubject in onderdeel c.
    De volgende test laat zien dat een `onderdeel` dat wél oplost.
    """
    voorstellen, _ = _verwerk(ELEMENTEN, CORPUS, "BWBR0019237", "6")
    derde = _per_klasse(voorstellen)["derde"]
    assert derde.anker.start != 43, "dit is het voorkomen in lid 1 – dat moet gerepareerd zijn"
    assert _lid_van_offset(derde.anker.start) == "2"
    assert CORPUS[derde.anker.start:derde.anker.eind] == "derde"
    lid2 = _lid_segmenten(CORPUS)[1]
    assert CORPUS.count("derde", *lid2[1:]) == 3, "de restambiguïteit binnen lid 2"


def test_het_onderdeel_wijst_het_juiste_voorkomen_aan():
    """Het model noemt het onderdeel al in zijn prozatoelichting ("in onderdeel c"); dit is het
    veld waarin het terechtkomt. Met die aanwijzing landt "derde" op het rechtssubject."""
    llm = '{"elementen": [{"klasse": "Rechtssubject", "tekst": "derde", "lid": "2", "onderdeel": "c"}]}'
    (v,) = _verwerk(llm, CORPUS, "BWBR0019237", "6")[0]
    assert CORPUS[v.anker.start:v.anker.eind] == "derde"
    assert CORPUS[v.anker.start - 11:v.anker.start] == "c. van een ", "het rechtssubject in onderdeel c"


def test_onderdeelnummer_mag_geschreven_worden_zoals_het_model_wil():
    """"c", "c." en "onderdeel c" wijzen naar hetzelfde onderdeel."""
    plekken = set()
    for geschreven in ("c", "c.", "onderdeel c", "C."):
        llm = ('{"elementen": [{"klasse": "Rechtssubject", "tekst": "derde", "lid": "2",'
               f' "onderdeel": "{geschreven}"}}]}}')
        (v,) = _verwerk(llm, CORPUS, "BWBR0019237", "6")[0]
        plekken.add(v.anker.start)
    assert len(plekken) == 1, f"verschillende schrijfwijzen gaven verschillende ankers: {plekken}"


def test_een_onbekend_onderdeel_verliest_niets_en_raakt_het_lid_niet():
    """Een fout onderdeel is een fijnere claim dan het lid; die mag het lid niet omgooien."""
    llm = '{"elementen": [{"klasse": "Rechtssubject", "tekst": "gemeente", "lid": "2", "onderdeel": "z"}]}'
    voorstellen, verworpen = _verwerk(llm, CORPUS, "BWBR0019237", "6")
    assert not verworpen
    (v,) = voorstellen
    assert v.lid == "2"
    assert _lid_van_offset(v.anker.start) == "2"


def test_een_kort_fragment_landt_niet_middenin_een_woord():
    """De Operator "en" komt 59x voor in lid 2; het eerste voorkomen zit in "Als gevallen".

    Live op 1 sep 2026 ankerde die markering op offset 799 – de lettergreep, niet het voegwoord.
    """
    llm = '{"elementen": [{"klasse": "Operator", "tekst": "en", "lid": "2"}]}'
    (v,) = _verwerk(llm, CORPUS, "BWBR0019237", "6")[0]
    assert CORPUS[v.anker.start:v.anker.eind] == "en"
    assert CORPUS[v.anker.start - 1] == " ", "links van het voegwoord hoort witruimte te staan"
    assert not CORPUS[v.anker.eind].isalpha(), "rechts van het voegwoord hoort geen letter te staan"


def test_de_woordgrens_is_een_voorkeur_geen_eis():
    """Komt een fragment alleen middenin een woord voor, dan blijft de markering staan.

    Brongetrouwe tekst weggooien omdat de plaatsbepaling niet scherp te krijgen is, zou erger zijn
    dan een minder scherpe plaatsbepaling – dezelfde afweging als bij het lid.
    """
    corpus = "1. De belastingschuldige betaalt."
    llm = '{"elementen": [{"klasse": "Rechtsobject", "tekst": "schuld", "lid": "1"}]}'
    voorstellen, verworpen = _verwerk(llm, corpus, "BWBR0004770", "9")
    assert not verworpen
    (v,) = voorstellen
    assert corpus[v.anker.start:v.anker.eind] == "schuld"


def test_geen_enkel_anker_spreekt_zijn_eigen_lid_tegen():
    """De invariant, niet één geval: lid en anker zijn één beslissing."""
    voorstellen, _ = _verwerk(ELEMENTEN, CORPUS, "BWBR0019237", "6")
    assert voorstellen
    for v in voorstellen:
        assert _lid_van_offset(v.anker.start) == v.lid, (
            f"{v.tekst!r} zegt lid {v.lid} maar ankert in lid {_lid_van_offset(v.anker.start)}"
        )


def test_de_vindplaats_volgt_het_gecorrigeerde_lid():
    """Staat het fragment niet in het geclaimde lid, dan wint het anker – en de vindplaats mee.

    De markering blijft behouden: de tekst is brongetrouw, alleen de lid-claim van het model was
    fout. Hem verwerpen zou letterlijke wettekst weggooien wegens een boekhoudfout.
    """
    llm = '{"elementen": [{"klasse": "Rechtsobject", "tekst": "convenant", "lid": "4"}]}'
    voorstellen, verworpen = _verwerk(llm, CORPUS, "BWBR0019237", "6")
    assert not verworpen
    (v,) = voorstellen
    assert v.lid == "1", "'convenant' staat alleen in lid 1"
    assert v.vindplaats.endswith("lid 1")
    assert _lid_van_offset(v.anker.start) == "1"


def test_scope_lid_blijft_leidend():
    """Met een lid-gescopet corpus is er één segment en verandert er niets aan het bestaande gedrag."""
    corpus = f"2. {dict(LEDEN)['2']}"
    llm = '{"elementen": [{"klasse": "Rechtssubject", "tekst": "derde", "lid": ""}]}'
    voorstellen, _ = _verwerk(llm, corpus, "BWBR0019237", "6", scope_lid="2")
    (v,) = voorstellen
    assert v.lid == "2"
    assert corpus[v.anker.start:v.anker.eind] == "derde"


def test_lid_segmenten_volgt_de_corpusopbouw():
    segmenten = _lid_segmenten(CORPUS)
    assert [nummer for nummer, _, _ in segmenten] == ["1", "2", "3", "4", "5"]
    for nummer, start, eind in segmenten:
        assert CORPUS[start:eind].startswith(f"{nummer}. ")


def test_bepaling_zonder_lidnummers_wordt_niet_gescoped():
    """Een bepaling (Leidraad) heeft geen leden; dan is er niets om op te scopen."""
    corpus = "Er wordt geen kwijtschelding verleend als:\n– er sprake is van meer dan één belastingschuldige;"
    llm = '{"elementen": [{"klasse": "Voorwaarde", "tekst": "er sprake is van meer dan één belastingschuldige", "lid": ""}]}'
    voorstellen, _ = _verwerk(llm, corpus, "BWBR0024096", "26.1.9")
    (v,) = voorstellen
    assert v.anker is not None
    assert corpus[v.anker.start:v.anker.eind].startswith("er sprake is van")
