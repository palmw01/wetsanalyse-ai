"""Drift-guard: elk `bwb:`-term in onze SPARQL bestaat ook echt in de graaf.

Waarom deze test bestaat. Een predicaat dat niet in de graaf bestaat – zoals `bwb:bevat`; de importer
schrijft `HEEFT_ONDERDEEL`, wat via `rdf_vocab._camel` `bwb:heeftOnderdeel` wordt – laat een subquery
nooit iets matchen, en de tool levert dan géén enkel onderdeel. Een test die alleen de querytekst leest
(`"bwb:bevat" in sparql`) ziet dat niet: een query kan syntactisch perfect zijn en semantisch nergens
over gaan.

Dat is de faalmodus die deze guard afvangt: **stille onvolledigheid**. Geen foutmelding, geen leeg
resultaat waar iemand van opkijkt — gewoon een antwoord dat minder weet dan de graaf. Bij een
platform waarvan brongetrouwheid het uitgangspunt is, is dat de duurste soort bug.

De guard is puur statisch en kost niets: hij leest de ontologie van de importer als **tekst** en
vergelijkt de namen. Importeren kan niet en mag niet — `tools/bwb-import` is een los pakket dat niet
in het graph-qa-image zit. Dezelfde aanpak als `test_methode_drift.py`, dat de skill-markdown leest.

Ontbreekt de ontologie (draaien vanuit een deelkopie van de repo), dan slaat de test over in plaats
van rood te worden: hij bewaakt de repo, niet de werkkopie.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from agent.graph import queries

ONTOLOGIE = Path(__file__).resolve().parents[3] / "tools" / "bwb-import" / "app" / "ontology.py"

# Termen die niet uit de BWB-ontologie komen maar wel in onze queries staan.
# Elke uitzondering hoort hier met een reden; een lege lijst is de gewenste eindtoestand.
UITZONDERINGEN: dict[str, str] = {}


def _ontologie_namen() -> set[str]:
    """Klassen + object-/dataproperties uit de ontologie van de importer.

    De drie dicts (`_KLASSEN`, `_OBJECT_PROPS`, `_DATA_PROPS`) hebben allemaal de vorm
    `"naam": (...)` op één inspringniveau, dus één regex dekt ze alle drie. Ruimer matchen dan nodig
    is hier veilig: een naam te veel maakt de guard hooguit milder, een naam te weinig zou 'm
    onterecht rood maken.
    """
    tekst = ONTOLOGIE.read_text(encoding="utf-8")
    return set(re.findall(r'^\s{4}"([A-Za-z]+)":', tekst, re.M))


def _gebruikte_namen() -> set[str]:
    """De `bwb:`-termen in de daadwerkelijke SPARQL, zonder proza.

    Twee soorten ruis moeten eruit, anders meldt de guard fouten die er niet zijn:
    - **docstrings en commentaar** noemen predicaten om ze uit te leggen (`bwb:bevat bestaat niet`);
    - **IRI's in voorbeelden** – `urn:bwb:BWBR0002471` levert anders de "term" BWBR op.

    De lookahead `(?![0-9])` vangt het tweede; `ast` het eerste. Liever iets te ruim wegfilteren
    dan een valse melding: een guard die vals alarm slaat wordt uitgezet, en dan bewaakt hij niets.
    """
    namen: set[str] = set()
    # Niet alleen `queries.py`: de bouwers bij hun domein horen er ook bij (`agent/` rglob op `bwb:`).
    for pad in Path(queries.__file__).parents[1].rglob("*.py"):
        namen |= _namen_in(pad.read_text(encoding="utf-8"))
    return namen


def _namen_in(bron: str) -> set[str]:
    boom = ast.parse(bron)
    docstrings = []
    for node in ast.walk(boom):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            tekst = ast.get_docstring(node, clean=False)
            if tekst:
                docstrings.append(tekst)
    for tekst in docstrings:
        bron = bron.replace(tekst, "")
    regels = [r for r in bron.splitlines() if not r.strip().startswith("#")]
    return set(re.findall(r"(?<![:\w])bwb:([A-Za-z]+)(?![0-9])", "\n".join(regels)))


@pytest.mark.skipif(not ONTOLOGIE.exists(), reason=f"ontologie niet beschikbaar: {ONTOLOGIE}")
def test_elke_bwb_term_in_queries_bestaat_in_de_ontologie():
    onbekend = _gebruikte_namen() - _ontologie_namen() - set(UITZONDERINGEN)
    assert not onbekend, (
        "queries.py gebruikt bwb:-termen die de importer niet schrijft: "
        f"{sorted(onbekend)}.\n"
        "Zo'n query matcht nooit iets en faalt STIL. Controleer de naam in "
        "tools/bwb-import/app/ontology.py (let op: HEEFT_ONDERDEEL wordt bwb:heeftOnderdeel) "
        "of zet 'm met reden in UITZONDERINGEN."
    )


@pytest.mark.skipif(not ONTOLOGIE.exists(), reason=f"ontologie niet beschikbaar: {ONTOLOGIE}")
def test_de_ontologie_is_leesbaar():
    """Vangt het geval dat de vorm van ontology.py verandert en de guard stil niets meer vindt."""
    namen = _ontologie_namen()
    assert len(namen) > 50, f"onverwacht weinig termen uit de ontologie gelezen: {len(namen)}"
    for kern in ("heeftOnderdeel", "heeftLid", "verwijstNaar", "tekst", "jci"):
        assert kern in namen, f"bekende term {kern!r} niet gevonden – parse-regressie?"


# ---------------------------------------------------------------------------
# Kardinaliteit: een query mag niet méér rijen opleveren dan er antwoorden zijn
# ---------------------------------------------------------------------------
#
# De tweede les van de live-meting, naast "een predicaat dat niet bestaat".
# Vijf van de zeven gevonden defecten leverden gewoon rijen op — ze leverden er te véél op:
#
#   - `?node a ?type` matcht ook de gematerialiseerde superklassen (Citeerbaar, eli:LegalResource),
#     dus kwam elke zoektreffer twee tot vier keer terug;
#   - losse OPTIONALs op meerwaardige properties vermenigvuldigen elkaar: 2 afkortingen x 3
#     ondertekenaars gaf zes vrijwel identieke rijen voor één regeling.
#
# Beide glippen door élke leegte-controle heen, en met een FakeGraph zijn ze onzichtbaar: die geeft
# terug wat je hem voert. Vandaar deze statische guards, plus `max_rijen` in de retrieval-smoke.


def _query_bronnen() -> str:
    return Path(queries.__file__).read_text(encoding="utf-8")


def test_elke_soort_binding_is_gefilterd_op_concrete_types():
    """`STRAFTER(STR(?t), …)` zonder type-filter betekent één rij per superklasse."""
    bron = _query_bronnen()
    for regel in bron.splitlines():
        if "AS ?soort" not in regel or "a ?t" not in regel:
            continue
        assert "?t IN (" in regel, (
            "een ?soort-binding zonder type-filter levert elke knoop meerdere keren op "
            f"(Citeerbaar, eli:LegalResource, …):\n  {regel.strip()}\n"
            "Gebruik FILTER(?t IN ({...})) met queries.CONCRETE_TYPES."
        )


def test_concrete_types_bestaan_allemaal():
    """Een tikfout in CONCRETE_TYPES filtert stilzwijgend álles weg."""
    namen = {t.removeprefix("bwb:") for t in queries.CONCRETE_TYPES}
    onbekend = namen - _ontologie_namen() if ONTOLOGIE.exists() else set()
    assert not onbekend, f"onbekende klassen in CONCRETE_TYPES: {sorted(onbekend)}"


def test_regeling_info_bundelt_meerwaardige_velden():
    """Eén regeling hoort één rij te zijn.

    De Invorderingswet heeft 2 afkortingen en 3 ondertekenaars; met losse OPTIONALs zijn dat zes
    rijen, en het model kreeg de wet zes keer voorgeschoteld en kon er niet uit aflezen wát nu de afkorting is.
    """
    sparql = queries.get_regeling_info("BWBR0004770")
    for veld in ("?afkorting", "?ondertekenaar", "?organisatie", "?alternatieveTitel"):
        naam = veld.lstrip("?")
        assert f"AS {veld}" in sparql, f"{veld} moet een geaggregeerde projectie zijn"
        assert f"GROUP_CONCAT(DISTINCT" in sparql and naam in sparql, (
            f"{veld} is meerwaardig en moet met GROUP_CONCAT worden gebundeld"
        )
    assert "SAMPLE(" in sparql, "enkelwaardige velden horen ook geaggregeerd, anders groepeert niets"


def test_geldigheid_is_een_rij_per_bepaling():
    """Eén bepaling hoort één rij te zijn, met haar eigen Kamerdossiers.

    De dossiers kwamen uit een subquery in een OPTIONAL, die op `?drager` moest aansluiten: een variabele uit een
    `BIND(COALESCE(…))`. In de graaf sloot die niet aan. Voor artikel 28 van de Invorderingswet 1990 gaf de query 974
    rijen, elk met de dossiers van een ándere bepaling (meting ADR-016 ronde 3: B01 las vier pagina's, K17 ging over op
    eigen SPARQL). Nu staat alles over de drager in één OPTIONAL en worden de dossiers op het buitenste niveau
    samengevoegd. Tegen de echte graaf toetst `eval/retrieval_smoke.py` het (`max_rijen=1`)."""
    for args in (("BWBR0004770", "28"), ("BWBR0004770", "36", "4"), ("BWBR0004770",), ("BWBR0024096", "25.1")):
        sparql = queries.geldigheid(*args)
        buiten, _, binnen = sparql.partition("WHERE {")
        assert 'GROUP_CONCAT(DISTINCT ?ds; separator=" | ") AS ?dossiersBepaling' in buiten, "de dossiers horen in de buitenste projectie"
        assert "BIND(COALESCE" not in sparql and "GROUP BY ?drager" not in sparql
        # Alles wat de drager nodig heeft, staat in het blok dat hem bindt.
        blok = binnen[binnen.index("?drager (bwb:heeftLid|bwb:heeftOnderdeel)* ?node"):binnen.index("OPTIONAL { ?node bwb:inwerking")]
        for patroon in ("FILTER NOT EXISTS { ?boven (bwb:heeftLid|bwb:heeftOnderdeel) ?drager }", "?drager bwb:dossier ?ds",
                        "?drager bwb:inwerkingtredingsbron ?inwerkingtredingsbron", "?drager bwb:opmerking ?opmerking"):
            assert patroon in blok, patroon
        assert binnen.count("?drager") == blok.count("?drager"), "?drager wordt buiten zijn blok gebruikt"
        # Elke kolom die geen aggregaat is, staat in de GROUP BY: anders groepeert de graaf niet.
        groep = sparql[sparql.rindex("GROUP BY"):sparql.rindex("ORDER BY")]
        for kolom in ("?bepalingInwerking", "?terugwerkendTot", "?bron", "?effect", "?status", "?wijzigingsbron",
                      "?inwerkingtredingsbron", "?opmerking", "?geldigVanaf", "?geldigTot", "?toestandUrl",
                      "?ondertekeningsdatum", "?uitgiftedatum", "?dossier"):
            assert kolom in groep.split() and kolom in buiten, kolom


def test_geen_subquery_in_een_optional():
    """Een subquery in een OPTIONAL rekent de graaf los van de rest uit; sluit ze aan op een variabele uit een BIND,
    dan sluit ze niet aan en vermenigvuldigen de rijen zich (zie `geldigheid`). Samenvoegen hoort op het buitenste niveau."""
    import re
    from test_sparql_syntax import GEVALLEN
    for naam, bouw in GEVALLEN:
        assert not re.search(r"OPTIONAL\s*\{\s*SELECT", bouw), naam
