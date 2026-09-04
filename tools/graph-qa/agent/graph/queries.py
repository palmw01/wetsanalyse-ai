"""
Geparametriseerde SPARQL-bouwers voor de kennisgraaf.

Deze module is de code-vorm van de queryrecepten; ze stonden eerder als proza in de
system-prompt stonden: de eigen-IRI-ruimte-filters die owl:sameAs-tweelingen
ontdubbelen, de directe artikel-/lid-IRI-patronen, de Lucene-FTS en de
verwijzings-/SKOS-vormen. De invoer wordt gevalideerd/ge-escaped zodat het model
geen SPARQL kan injecteren via een tool-argument.

Bron van de patronen: de eerdere agent/prompts.py (kennisgraaf-verkenning).
"""
from __future__ import annotations

import re

from ..namespace import BASIS, ONTOLOGIE, SEP

PREFIXES = f"""PREFIX bwb: <{ONTOLOGIE}>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX luc: <http://www.ontotext.com/connectors/lucene#>
PREFIX inst: <http://www.ontotext.com/connectors/lucene/instance#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

# Eigen IRI-ruimte – filter hierop om owl:sameAs-tweelingen (wetten.overheid.nl)
# buiten tellingen/resultaten te houden.
NS = BASIS

# De bevat-relatie is geen predicaat maar een alternatie. `bwb:bevat` BESTAAT NIET – de importer
# schrijft per niveau een eigen `heeft…`-predicaat (`tools/bwb-import/app/ontology.py`). Dat was tot
# 4 sep 2026 de stille bug in `context()`: de tak "4-bevat-door" matchte nooit iets en de agent kreeg
# de structurele inbedding van een bepaling dus nóóit te zien. Zelfde fout als `get_lid` had.
#
# Ze zijn alle negen `rdfs:subPropertyOf eli:has_part`, maar daarop bevragen zou afhangen van een
# ruleset die subPropertyOf materialiseert; de alternatie hangt nergens van af.
# `tests/test_predicaat_dekking.py` bewaakt dat elke naam hier echt bestaat.
BEVAT = (
    "bwb:heeftHoofdstuk|bwb:heeftTiteldeel|bwb:heeftAfdeling|bwb:heeftParagraaf"
    "|bwb:heeftArtikel|bwb:heeftLid|bwb:heeftOnderdeel|bwb:heeftDivisie|bwb:heeftBijlage"
)

# Alleen de containerniveaus – voor een inhoudsopgave wil je geen leden en onderdelen meenemen.
STRUCTUUR = (
    "bwb:heeftHoofdstuk|bwb:heeftTiteldeel|bwb:heeftAfdeling|bwb:heeftParagraaf"
    "|bwb:heeftArtikel|bwb:heeftDivisie"
)

# De CONCRETE knooptypes. `?node a ?type` levert ook de gematerialiseerde superklassen op – een
# onderdeel is tegelijk bwb:Onderdeel, bwb:Citeerbaar, eli:LegalResource én
# eli:LegalResourceSubdivision – en zonder deze filter komt elke treffer dus twee tot vier keer terug.
# Live gezien op acceptatie: `zoek_definitie` gaf dezelfde node als "Onderdeel" én als "Citeerbaar".
#
# Bewust een expliciete lijst en geen `FILTER NOT EXISTS { ?sub rdfs:subClassOf ?t ... }`: die vorm
# is correcter in theorie maar hangt af van hoe de ruleset de hiërarchie materialiseert, en hij kost
# een geneste scan per rij. `tests/test_predicaat_dekking.py` bewaakt dat deze namen bestaan.
CONCRETE_TYPES = (
    "bwb:Regeling", "bwb:Hoofdstuk", "bwb:Titeldeel", "bwb:Afdeling", "bwb:Paragraaf",
    "bwb:Artikel", "bwb:Lid", "bwb:Onderdeel", "bwb:Divisie", "bwb:Bijlage",
)

# De velden van de Lucene-connector `bwb_tekst`. Deze lijst MOET gelijk zijn aan
# `_FTS_VELDEN` + "label" in `tools/bwb-import/app/graphdb_writer.py`; `tests/test_fts_velden.py`
# bewaakt dat. Zonder die namen kan het model niet veldgericht zoeken en is de index
# een platte tekstzoeker met negen velden op één hoop.
FTS_VELDEN = (
    "tekst", "titel", "citeertitel", "opschrift", "aanhef",
    "considerans", "voetnoot", "definieertBegrip", "label",
)

_BWB_RE = re.compile(r"^BWBR\d+$")
_ART_RE = re.compile(r"^[0-9]+[a-z]*$", re.IGNORECASE)
_NUM_RE = re.compile(r"^[0-9]+[a-z]*$", re.IGNORECASE)
# Vrij bepaling-nummer: staat decimale (divisie-)vormen en letters toe: "9", "9.1", "22a", "22bis".
#
# Letters mogen op ELK segment staan, niet alleen op het laatste. De oudere vorm
# `^[0-9]+(\.[0-9]+)*[a-z]*$` eiste dat elk segment ná de eerste punt puur numeriek was, en wees
# daarmee 52 bestaande Leidraad-bepalingen af: "7a.1", "22bis.1", "73.3a.2", "25.3a.1", "44a.2" …
# Die gaven geen "niets gevonden" maar een 400 OngeldigeVindplaats – een tikfout-melding voor een
# bepaling die gewoon bestaat. Een puur alfabetisch segment ("14.4.5.a", "25.2.2.a") komt ook voor.
_NUMMER_VRIJ_RE = re.compile(r"^[0-9]+[a-z]*(\.(?:[0-9]+[a-z]*|[a-z]+))*$", re.IGNORECASE)


def _bwb(value: str) -> str:
    v = str(value).strip()
    if not _BWB_RE.match(v):
        raise ValueError(f"Ongeldig BWB-id: {value!r} (verwacht 'BWBR' gevolgd door cijfers).")
    return v


def _art(value: str) -> str:
    v = str(value).strip()
    if not _ART_RE.match(v):
        raise ValueError(f"Ongeldig artikelnummer: {value!r}.")
    return v


def _num(value: str) -> str:
    v = str(value).strip()
    if not _NUM_RE.match(v):
        raise ValueError(f"Ongeldig nummer: {value!r}.")
    return v


def _nummer_vrij(value: str) -> str:
    v = str(value).strip()
    if not _NUMMER_VRIJ_RE.match(v):
        raise ValueError(
            f"Ongeldig bepaling-nummer: {value!r} (verwacht bv. '9', '9.1', '22a', '73.3a.2')."
        )
    return v


def _lit(text: str) -> str:
    """Veilige SPARQL-stringliteral."""
    s = str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return f'"{s}"'


# ------------------------------------------------------------------
# IRI-bouwers
# ------------------------------------------------------------------

def regeling_iri(bwb_id: str) -> str:
    return f"{NS}{_bwb(bwb_id)}"


def artikel_iri(bwb_id: str, artikel: str) -> str:
    return f"{NS}{_bwb(bwb_id)}{SEP}artikel{SEP}{_art(artikel)}"


def lid_iri(bwb_id: str, artikel: str, lid: str) -> str:
    return f"{artikel_iri(bwb_id, artikel)}{SEP}lid{SEP}{_num(lid)}"


def is_artikelnummer(aanduiding: str) -> bool:
    """True voor '9', '22a' – False voor '9.1', '73.3a.2' (divisies van een beleidsregel)."""
    return bool(_ART_RE.match(str(aanduiding).strip()))


def node_patroon(bwb_id: str, aanduiding: str, lid: str | None = None) -> str:
    """Graafpatroon dat `?node` bindt aan één bepaling – artikel én divisie.

    Waarom dit bestaat. `follow_verwijzingen`, `referenced_by` en `context` bouwden alle drie
    rechtstreeks op `artikel_iri`, en die weigert een punt. Voor de ~800 divisies van de Leidraad
    Invordering 2008 werkte dus GEEN van de drie: geen verwijzingen, geen inbedding, geen context —
    terwijl het corpus-pad (`get_bepaling_corpus`) die bepalingen al jaren gewoon oplevert. Een
    jurist die een Leidraad-bepaling opent kreeg daardoor een half platform.

    Twee vormen, één uitkomst:
    - **artikelnummer** ('9', '22a') → een directe IRI. Geen zoekwerk, geen ambiguïteit.
    - **decimaal nummer** ('9.1', '73.3a.2') → matchen op `bwb:nummer` binnen de regelingscope.
      Een nummer kan meer dan één node raken, dus net als in `get_bepaling_corpus` kiest een
      subquery er precies één, met voorrang voor de node die eigen tekst draagt. Zonder die keuze
      vermenigvuldigt elke tak van een UNION zich met het aantal kandidaten.

    Let op de asymmetrie die blijft: een `lid` heeft bij een divisie geen betekenis (die kent
    subdivisies, geen leden) en wordt daar genegeerd — `_leden_en_corpus` vouwt subbepalingen om
    dezelfde reden tot leden-rijen in.
    """
    if is_artikelnummer(aanduiding):
        iri = lid_iri(bwb_id, aanduiding, lid) if lid else artikel_iri(bwb_id, aanduiding)
        return f"BIND(<{iri}> AS ?node)"
    lit = _lit(_nummer_vrij(aanduiding))
    scope = f"{NS}{_bwb(bwb_id)}"
    return f"""{{ SELECT DISTINCT ?node ?nodetekst WHERE {{
      ?node bwb:nummer {lit} .
      FILTER(STRSTARTS(STR(?node), "{scope}"))
      OPTIONAL {{ ?node bwb:tekst ?nodetekst }}
      OPTIONAL {{ ?node {BEVAT} ?nodekind }}
      FILTER(BOUND(?nodetekst) || BOUND(?nodekind))
    }} ORDER BY DESC(BOUND(?nodetekst)) LIMIT 1 }}"""


# ------------------------------------------------------------------
# Query-bouwers
# ------------------------------------------------------------------

# De knooptypes waarop de FTS-connector indexeert; tevens de toegestane waarden van `soort`.
FTS_TYPES = (
    "Regeling", "Hoofdstuk", "Titeldeel", "Afdeling", "Paragraaf",
    "Artikel", "Lid", "Onderdeel", "Divisie", "Bijlage",
)


def fts(
    query: str,
    limit: int = 10,
    veld: str | None = None,
    bwb_id: str | None = None,
    soort: str | None = None,
    offset: int = 0,
) -> str:
    """Full-text search via de Lucene-index `inst:bwb_tekst`.

    De index is rijker dan deze query lang gebruikte. Hij draagt **negen benoemde velden**
    (`FTS_VELDEN`) over tien knooptypes, met de Nederlandse analyzer — en de query bevroeg hem als
    één platte tekstbak. Drie dingen zijn daarmee toegevoegd, elk met een eigen reden:

    - **`veld`** — veldgericht zoeken. `definieertBegrip:"bestuurder"` vindt precies het tekstdeel
      waar de wet dat begrip definieert; `tekst:` daarentegen vindt elke bepaling die het woord
      gebruikt. Dat verschil is voor een definitievraag het hele antwoord.
    - **`bwb_id`/`soort`** — afbakenen. Zonder scope levert een zoekvraag over de Leidraad ook
      treffers in de Invorderingswet, en moet het model zelf gaan zeven.
    - **de vindplaats in het resultaat** — een treffer droeg `node/score/label/tekst` en verder
      niets. Het BWB-id, de citeertitel, het knooptype en de jci ontbraken, dus was een treffer
      **niet citeerbaar** zonder nóg een call. Nu is één zoekactie genoeg om te kunnen citeren.

    `offset` bestaat omdat 50 treffers een harde muur waren: voorbij de eerste pagina was er geen
    weg. De ORDER BY is daarom deterministisch (score, dan IRI) — zonder tweede sorteersleutel kan
    dezelfde rij op twee pagina's staan of op geen enkele.
    """
    lim = max(1, min(int(limit), 50))
    off = max(0, int(offset))
    zoek = query
    if veld:
        v = str(veld).strip()
        if v not in FTS_VELDEN:
            raise ValueError(f"Onbekend zoekveld: {veld!r} (kies uit: {', '.join(FTS_VELDEN)}).")
        # Haakjes eromheen zodat een meerwoordige query in zijn geheel op het veld slaat:
        # `tekst:aansprakelijk bestuurder` zou anders alleen het eerste woord binden.
        zoek = f"{v}:({query})"
    filters = ""
    if bwb_id:
        filters += f'\n  FILTER(STRSTARTS(STR(?node), "{NS}{_bwb(bwb_id)}"))'
    if soort:
        srt = str(soort).strip()
        if srt not in FTS_TYPES:
            raise ValueError(f"Onbekend soort: {soort!r} (kies uit: {', '.join(FTS_TYPES)}).")
        filters += f"\n  ?node a bwb:{srt} ."
    return PREFIXES + f"""SELECT ?node ?score ?soort ?label ?tekst ?jci ?bwbId ?citeertitel WHERE {{
  [] a inst:bwb_tekst ; luc:query {_lit(zoek)} ; luc:entities ?node .
  ?node luc:score ?score .{filters}
  OPTIONAL {{ ?node rdfs:label ?label }}
  OPTIONAL {{ ?node bwb:tekst ?tekst }}
  OPTIONAL {{ ?node bwb:jci ?jci }}
  OPTIONAL {{ ?node a ?t . FILTER(?t IN ({", ".join(CONCRETE_TYPES)})) BIND(STRAFTER(STR(?t), "{ONTOLOGIE}") AS ?soort) }}
  BIND(SUBSTR(STR(?node), {len(NS) + 1}) AS ?rest)
  BIND(IF(CONTAINS(?rest, "{SEP}"), STRBEFORE(?rest, "{SEP}"), ?rest) AS ?bwbId)
  OPTIONAL {{ ?reg a bwb:Regeling ; bwb:bwbId ?bwbId ; bwb:citeertitel ?citeertitel }}
}} ORDER BY DESC(?score) ?node LIMIT {lim} OFFSET {off}"""


def list_regelingen() -> str:
    return PREFIXES + f"""SELECT DISTINCT ?regeling ?citeertitel ?soort WHERE {{
  ?regeling a bwb:Regeling .
  FILTER(STRSTARTS(STR(?regeling), "{NS}"))
  OPTIONAL {{ ?regeling bwb:citeertitel ?citeertitel }}
  OPTIONAL {{ ?regeling bwb:soort ?soort }}
}} ORDER BY ?citeertitel"""


def get_artikel(bwb_id: str, artikel: str) -> str:
    """Artikel met zijn leden, plus de onderdelen die rechtstreeks onder het artikel hangen.

    Die directe onderdelen (`heeftOnderdeel`) zijn er bij artikelen zónder leden – een opsomming
    a/b/c direct onder het artikel – en ontbraken volledig. Onderdelen die onder een *lid* hangen
    komen bewust niet mee: bij een definitieartikel zijn dat er tientallen en dan kapt de
    8000-tekenslimiet het resultaat af. Daarvoor is `get_lid`, dat ze wél levert.
    """
    iri = artikel_iri(bwb_id, artikel)
    return PREFIXES + f"""SELECT ?tekst ?jci ?lid ?lidnummer ?lidtekst ?onderdeel ?onderdeeltekst WHERE {{
  OPTIONAL {{ <{iri}> bwb:tekst ?tekst }}
  OPTIONAL {{ <{iri}> bwb:jci ?jci }}
  OPTIONAL {{
    <{iri}> bwb:heeftLid ?lid .
    FILTER(STRSTARTS(STR(?lid), "{NS}"))
    OPTIONAL {{ ?lid bwb:nummer ?lidnummer }}
    OPTIONAL {{ ?lid bwb:tekst ?lidtekst }}
    # Numeriek sorteren, niet lexicaal: anders staat lid 10 vóór lid 2. Dezelfde valkuil die
    # `artikel._lidsleutel` voor het corpus oplost; hier moet SPARQL het doen, want de tool levert
    # zijn rijen rechtstreeks aan het model. "1a" telt als 1 en houdt zijn plaats via ?lid.
    BIND(xsd:integer(REPLACE(STR(?lidnummer), "[^0-9].*$", "")) AS ?lidsort)
  }}
  OPTIONAL {{
    <{iri}> bwb:heeftOnderdeel ?o .
    FILTER(STRSTARTS(STR(?o), "{NS}"))
    OPTIONAL {{ ?o bwb:nummer ?onderdeel }}
    OPTIONAL {{ ?o bwb:tekst ?onderdeeltekst }}
  }}
}} ORDER BY ?lidsort ?lid ?o"""


def get_artikel_corpus(bwb_id: str, artikel: str) -> str:
    """Artikel met leden én onderdelen – de bron voor het annotatiecorpus en het documentpaneel.

    Waarom naast `get_artikel` en niet erin. `get_artikel` voedt óók de gelijknamige tool, en
    tool-resultaten gaan door `truncate` (8000 tekens). Bij een definitieartikel met 25 onderdelen
    kapt dat juist de laatste definities af — dat was destijds de reden om lid-onderdelen daar weg
    te laten, en die reden geldt nog. Het corpus gaat níet door `truncate`, dus hier kan het wel.

    Waarom niet de `?onderdelen`-cel van `get_lid` hergebruiken: die bakt de jci in de tekst
    (`"a. … [jci…]"`) zodat de agent per onderdeel een vindplaats kan citeren. Nuttig voor een
    antwoord, onbruikbaar als corpus — een markering die zo'n regel citeert zou een jci-fragment
    bevatten en dan liegt de letterlijkheidscontrole.

    Eén rij per (lid, onderdeel). De UNION scheidt twee gevallen die elkaar uitsluiten: onderdelen
    onder een lid, en onderdelen rechtstreeks onder het artikel (een opsomming bij een artikel
    zónder leden). Met twee losse OPTIONALs zou dat het cartesisch product opleveren en herhaalde
    elke lidtekst zich per onderdeel.

    `heeftOnderdeel+` omdat de importer een boom schrijft: 'aa.' hangt onder het lid, '1°' onder
    'aa.'.

    De derde tak (`?sub`) is er voor een aanduiding met een héél getal die bij een beleidsregel op
    een container uitkomt. `artikel_iri("BWBR0024096", "25")` bestaat namelijk wél – de Leidraad
    geeft haar top-divisies een `:artikel:`-IRI – dus deze query levert rijen, `leden` is niet leeg
    en `_bepaling_fallback` springt juist níet aan. Zonder deze tak was het resultaat een
    inhoudsopgave van acht streepjes met een 200 eronder. Zie `get_bepaling_corpus` voor de rest
    van de redenering; het decimale pad (`25.1.1`) loopt daar langs.
    """
    iri = artikel_iri(bwb_id, artikel)
    return PREFIXES + f"""SELECT ?tekst ?jci ?soort ?lid ?lidnummer ?lidtekst ?sub ?subnummer ?subtekst
       ?o ?ouder ?onummer ?otekst WHERE {{
  OPTIONAL {{ <{iri}> bwb:tekst ?tekst }}
  OPTIONAL {{ <{iri}> bwb:jci ?jci }}
  OPTIONAL {{ <{iri}> a ?soort . FILTER(?soort IN (bwb:Artikel, bwb:Divisie)) }}
  OPTIONAL {{
    {{
      <{iri}> bwb:heeftLid ?lid .
      FILTER(STRSTARTS(STR(?lid), "{NS}"))
      OPTIONAL {{ ?lid bwb:nummer ?lidnummer }}
      OPTIONAL {{ ?lid bwb:tekst ?lidtekst }}
      OPTIONAL {{
        ?lid bwb:heeftOnderdeel+ ?o .
        FILTER(STRSTARTS(STR(?o), "{NS}"))
        OPTIONAL {{ ?ouder bwb:heeftOnderdeel ?o }}
        OPTIONAL {{ ?o bwb:nummer ?onummer }}
        OPTIONAL {{ ?o bwb:tekst ?otekst }}
      }}
    }} UNION {{
      <{iri}> bwb:heeftOnderdeel+ ?o .
      FILTER(STRSTARTS(STR(?o), "{NS}"))
      OPTIONAL {{ ?ouder bwb:heeftOnderdeel ?o }}
      OPTIONAL {{ ?o bwb:nummer ?onummer }}
      OPTIONAL {{ ?o bwb:tekst ?otekst }}
    }} UNION {{
      <{iri}> (bwb:heeftDivisie|bwb:heeftArtikel)+ ?sub .
      FILTER(STRSTARTS(STR(?sub), "{NS}"))
      OPTIONAL {{ ?sub bwb:nummer ?subnummer }}
      OPTIONAL {{ ?sub bwb:tekst ?subtekst }}
      OPTIONAL {{
        ?sub bwb:heeftOnderdeel+ ?o .
        FILTER(STRSTARTS(STR(?o), "{NS}"))
        OPTIONAL {{ ?ouder bwb:heeftOnderdeel ?o }}
        OPTIONAL {{ ?o bwb:nummer ?onummer }}
        OPTIONAL {{ ?o bwb:tekst ?otekst }}
      }}
    }}
  }}
}} ORDER BY ?lid ?sub ?o"""


def get_lid(bwb_id: str, artikel: str, lid: str) -> str:
    """Lid mét zijn onderdelen.

    Zonder de onderdelen is een definitielid nagenoeg leeg: artikel 2, lid 1 IW 1990 heeft als
    eigen tekst alleen "Deze wet verstaat onder:" – de 25 definities zitten in de onderdelen a t/m
    t. De agent ging dat compenseren met een reeks raw_sparql-pogingen (acht beurten voor één
    definitievraag).

    LET OP HET PREDICAAT. Dit stond op `bwb:bevat` met de toelichting "vlak opgeslagen, dus dit
    haalt ook geneste onderdelen op". Dat predicaat bestaat niet: de importer schrijft
    `HEEFT_ONDERDEEL` (`bwb-import/app/collect.py:356`), wat via `rdf_vocab._camel` het predicaat
    `bwb:heeftOnderdeel` wordt, en de ontologie kent geen `bevat` – ook niet af te leiden, want de
    ruleset kan alleen materialiseren wat gedeclareerd is. De subquery matchte dus nooit iets en
    deze tool heeft nooit één onderdeel geleverd; `tests/test_queries.py` toetste alleen de
    querytekst, niet of er data terugkwam.

    En het is géén vlakke opslag maar een boom: `collect.py:361` roept zichzelf recursief aan voor
    `subonderdelen`, dus 'aa.' hangt onder het lid en '1°' onder 'aa.'. Vandaar het pad `+`.
    """
    iri = lid_iri(bwb_id, artikel, lid)
    # De onderdelen in één cel (GROUP_CONCAT) i.p.v. één rij per onderdeel: anders herhaalt de
    # lidtekst zich per onderdeel en loopt een definitielid tegen de 8000-tekenslimiet, waarna juist
    # de laatste onderdelen wegvallen. De subquery met ORDER BY houdt de volgorde a, b, c, …
    return PREFIXES + f"""SELECT ?nummer ?tekst ?jci
       (GROUP_CONCAT(?regel; separator=" ⏐ ") AS ?onderdelen) WHERE {{
  OPTIONAL {{ <{iri}> bwb:nummer ?nummer }}
  OPTIONAL {{ <{iri}> bwb:tekst ?tekst }}
  OPTIONAL {{ <{iri}> bwb:jci ?jci }}
  OPTIONAL {{
    {{ SELECT ?regel WHERE {{
        <{iri}> bwb:heeftOnderdeel+ ?o .
        FILTER(STRSTARTS(STR(?o), "{NS}"))
        OPTIONAL {{ ?o bwb:nummer ?on }}
        OPTIONAL {{ ?o bwb:tekst ?ot }}
        OPTIONAL {{ ?o bwb:jci ?oj }}
        # De jci van het onderdeel zélf meegeven, niet die van het lid: anders citeert de agent
        # "onderdeel k" maar verwijst de vindplaats naar het hele definitielid. Ook geneste
        # onderdelen hebben er een (…&o=aa&o=1).
        #
        # Zonder de datumstaart (&z=…&g=…): die is voor 25 onderdelen ~700 tekens aan herhaling en
        # staat al in de jci van het lid hierboven. Wat overblijft is een geldige jci-verwijzing.
        BIND(IF(BOUND(?oj),
                IF(CONTAINS(?oj, "&z="), STRBEFORE(?oj, "&z="), ?oj),
                "") AS ?ojk)
        BIND(CONCAT(COALESCE(?on, ""), " ", COALESCE(?ot, ""),
                    IF(?ojk != "", CONCAT(" [", ?ojk, "]"), "")) AS ?regel)
      }} ORDER BY ?o }}
  }}
}} GROUP BY ?nummer ?tekst ?jci"""


def get_bepaling(bwb_id: str, nummer: str) -> str:
    """Haal een bepaling op via haar `bwb:nummer` binnen de regeling – werkt voor artikelen ("9",
    "25", "22a") én divisies/decimale nummers ("9.1") van beleidsregels/circulaires (bv. de Leidraad
    Invordering 2008), waar het artikel/lid-IRI-patroon niet opgaat.

    **`bwb:tekst` is OPTIONEEL, en dat is geen finesse.** De query eiste hem hard, en daardoor gaf
    deze tool niets terug voor een bepaling die wél bestaat: Leidraad-bepaling 25.1 heeft nul tekens
    eigen tekst en vijftien subdivisies met 7842 tekens eronder (live gemeten, 4 sep 2026). De
    ophaal-agent moet volgens zijn instructie "eindigen met een geslaagde get_bepaling-call die de
    tekst teruggaf" – en dat kón niet, voor precies de bepalingen waar een jurist mee werkt.
    `get_bepaling_corpus` had deze fix al; de tool-variant was achtergebleven.

    **Een container noemt zijn subdivisies.** Alleen de eigen tekst teruggeven zou bij zo'n bepaling
    een lege regel opleveren met een `200` eromheen — stil onvolledig, het gevaarlijkste geval. De
    `?sub`-tak levert daarom nummer + label + het begin van de tekst per subdivisie, zodat het model
    ziet dát er inhoud is en waar hij die kan ophalen. Bewust alleen het BEGIN (200 tekens): dit
    resultaat gaat door `truncate`, en de volledige tekst hoort in het corpus, niet in een tool.

    De subquery kiest één node, met voorrang voor die mét eigen tekst — een nummer kan binnen een
    regeling meer dan één node raken, en dan wil je de inhoudelijke.
    """
    lit = _lit(_nummer_vrij(nummer))
    scope = f"{NS}{_bwb(bwb_id)}"
    return PREFIXES + f"""SELECT ?nummer ?tekst ?label ?jci ?soort ?sub ?subnummer ?sublabel ?subbegin WHERE {{
  {{ SELECT DISTINCT ?node ?tekst WHERE {{
      ?node bwb:nummer {lit} .
      FILTER(STRSTARTS(STR(?node), "{scope}"))
      OPTIONAL {{ ?node bwb:tekst ?tekst }}
      OPTIONAL {{ ?node {BEVAT} ?kind }}
      FILTER(BOUND(?tekst) || BOUND(?kind))
    }} ORDER BY DESC(BOUND(?tekst)) LIMIT 1 }}
  BIND({lit} AS ?nummer)
  OPTIONAL {{ ?node rdfs:label ?label }}
  OPTIONAL {{ ?node bwb:jci ?jci }}
  OPTIONAL {{ ?node a ?t . FILTER(?t IN ({", ".join(CONCRETE_TYPES)})) BIND(STRAFTER(STR(?t), "{ONTOLOGIE}") AS ?soort) }}
  OPTIONAL {{
    ?node (bwb:heeftDivisie|bwb:heeftArtikel) ?sub .
    FILTER(STRSTARTS(STR(?sub), "{scope}"))
    OPTIONAL {{ ?sub bwb:nummer ?subnummer }}
    OPTIONAL {{ ?sub rdfs:label ?sublabel }}
    OPTIONAL {{ ?sub bwb:tekst ?subtekst . BIND(SUBSTR(STR(?subtekst), 1, 200) AS ?subbegin) }}
  }}
}} ORDER BY ?sub LIMIT 40"""


def get_bepaling_corpus(bwb_id: str, nummer: str) -> str:
    """Een bepaling mét haar onderdelen – de corpusvariant van `get_bepaling`.

    Waarom naast en niet in `get_bepaling`: die voedt óók de gelijknamige tool, en tool-resultaten
    gaan door `truncate` (8000 tekens). Bepaling 26.1.9 van de Leidraad heeft 221 tekens eigen tekst
    en 16 onderdelen met 6128 tekens; in de tool zouden juist de laatste voorwaarden wegvallen.
    Dezelfde afweging als bij `get_artikel` / `get_artikel_corpus`.

    Een divisie hangt aan haar onderdelen met hetzelfde `heeftOnderdeel` als een lid
    (`bwb-import/app/collect.py:_divisies` roept dezelfde `_onderdelen` aan), en net zo recursief –
    vandaar het pad `+`.

    EERST ÉÉN NODE KIEZEN, dan pas de onderdelen. `get_bepaling` matcht op `bwb:nummer` en houdt
    `LIMIT 5` aan omdat een nummer binnen een regeling meer dan één node kan raken. Met één rij per
    onderdeel zou zo'n limiet de opsomming afkappen – precies de fout die deze query moet oplossen.
    De subquery met `LIMIT 1` maakt de keuze eenmalig, waarna het aantal rijen alleen nog van het
    aantal onderdelen afhangt.

    `bwb:tekst` is hier OPTIONEEL, anders dan in `get_bepaling`. Zes bepalingen in de Leidraad
    hebben geen eigen tekst maar wél onderdelen (14.2.4, 14.2a, 25.4.6, 73.3a.2, …); met tekst als
    harde eis gaf de query niets terug en waren die bepalingen niet te openen en niet te annoteren.
    De `FILTER(BOUND(...))` eist daarom inhoud in de een óf de ander, en de `ORDER BY` geeft
    voorrang aan een node mét eigen tekst — een nummer kan binnen een regeling meer dan één node
    raken, en dan wil je de inhoudelijke.

    **De `?sub`-tak: een bepaling kan een container zijn.** De importer schrijft voor een circulaire
    twee bomen: `heeftDivisie` voor divisie→subdivisie en `heeftOnderdeel` voor de opsomming ván één
    divisie. Alleen `heeftOnderdeel+` volgen levert bij een container dus de inhoudsopgave en niets
    meer: bepaling 25 van de Leidraad heeft 76 tekens eigen tekst en acht opsommingsstreepjes,
    terwijl er 81 subdivisies met 43.622 tekens onder hangen. Geen fout, geen 404 — stil onvolledig,
    en dat is precies het gevaarlijke geval.

    `heeftArtikel` zit in hetzelfde pad omdat een divisie eigen artikelen kan dragen (elf in de
    Leidraad, onder 22bis en 79). Het pad is transitief en gaat níet één niveau: bepaling 25 heeft
    negen directe subdivisies met samen nul tekens eigen tekst — de inhoud zit pas een laag dieper.
    Lege tussenlagen leveren gewoon geen corpusregel op.

    `ORDER BY ?sub ?o` groepeert de rijen per subbepaling; de eigen onderdelen van de node zelf
    (`?sub` ongebonden) komen eerst. De echte volgorde legt `artikel._boomvolgorde` op.
    """
    lit = _lit(_nummer_vrij(nummer))
    scope = f"{NS}{_bwb(bwb_id)}"
    return PREFIXES + f"""SELECT ?nummer ?tekst ?jci ?soort ?sub ?subnummer ?subtekst
       ?o ?ouder ?onummer ?otekst WHERE {{
  {{ SELECT DISTINCT ?node ?tekst WHERE {{
      ?node bwb:nummer {lit} .
      FILTER(STRSTARTS(STR(?node), "{scope}"))
      OPTIONAL {{ ?node bwb:tekst ?tekst }}
      OPTIONAL {{ ?node bwb:heeftOnderdeel ?enig }}
      OPTIONAL {{ ?node bwb:heeftDivisie|bwb:heeftArtikel ?enigkind }}
      FILTER(BOUND(?tekst) || BOUND(?enig) || BOUND(?enigkind))
    }} ORDER BY DESC(BOUND(?tekst)) LIMIT 1 }}
  BIND({lit} AS ?nummer)
  OPTIONAL {{ ?node bwb:jci ?jci }}
  OPTIONAL {{ ?node a ?soort . FILTER(?soort IN (bwb:Artikel, bwb:Divisie)) }}
  OPTIONAL {{
    {{
      ?node bwb:heeftOnderdeel+ ?o .
      FILTER(STRSTARTS(STR(?o), "{scope}"))
      OPTIONAL {{ ?ouder bwb:heeftOnderdeel ?o }}
      OPTIONAL {{ ?o bwb:nummer ?onummer }}
      OPTIONAL {{ ?o bwb:tekst ?otekst }}
    }} UNION {{
      ?node (bwb:heeftDivisie|bwb:heeftArtikel)+ ?sub .
      FILTER(STRSTARTS(STR(?sub), "{scope}"))
      OPTIONAL {{ ?sub bwb:nummer ?subnummer }}
      OPTIONAL {{ ?sub bwb:tekst ?subtekst }}
      OPTIONAL {{
        ?sub bwb:heeftOnderdeel+ ?o .
        FILTER(STRSTARTS(STR(?o), "{scope}"))
        OPTIONAL {{ ?ouder bwb:heeftOnderdeel ?o }}
        OPTIONAL {{ ?o bwb:nummer ?onummer }}
        OPTIONAL {{ ?o bwb:tekst ?otekst }}
      }}
    }}
  }}
}} ORDER BY ?sub ?o"""


def get_regeling_info(bwb_id: str) -> str:
    """Metadata van één regeling, inclusief de WTI-verrijking – in ÉÉN rij.

    `afkorting`, `alternatieveTitel`, `eerstverantwoordelijke`, `dossier`, de publicatiegegevens en
    de `toestandUrl` stonden al in de graaf maar kwamen er niet uit. Die laatste is niet cosmetisch:
    hij zegt wélke toestand er geïmporteerd is, en dat is de vraag die elke annotatie impliciet
    beantwoordt.

    **Meerwaardige velden worden gebundeld, niet vermenigvuldigd.** Met losse OPTIONALs levert elk
    extra meerwaardig veld een cartesisch product: de Invorderingswet heeft 2 afkortingen ("IW",
    "Iw 1990") en 3 ondertekenaars, en dat gaf **zes** vrijwel identieke rijen (live gemeten,
    4 sep 2026). Het model kreeg zo zes keer dezelfde wet voorgeschoteld en kon er niet uit aflezen
    wat nu de afkorting ís. Dit patroon bestond al vóór de WTI-velden erbij kwamen; die maakten het
    alleen zichtbaar.

    Dezelfde oplossing als in `get_lid` voor de onderdelen: `GROUP_CONCAT` per meerwaardig veld.
    `SAMPLE` voor de rest is veilig omdat die velden per regeling één waarde hebben — en waar dat
    onverhoopt niet zo is, is één waarde nog altijd beter dan een rijenexplosie.

    Let op `agent/artikel.py`, dat `info[0]["citeertitel"]` leest: dat blijft werken en wordt
    betrouwbaarder, want er ís nu maar één rij.
    """
    iri = regeling_iri(bwb_id)
    return PREFIXES + f"""SELECT
       (SAMPLE(?ct) AS ?citeertitel) (SAMPLE(?op) AS ?opschrift)
       (GROUP_CONCAT(DISTINCT ?afk; separator=" | ") AS ?afkorting)
       (GROUP_CONCAT(DISTINCT ?alt; separator=" | ") AS ?alternatieveTitel)
       (SAMPLE(?srt) AS ?soort) (SAMPLE(?gv) AS ?geldigVanaf) (SAMPLE(?gt) AS ?geldigTot)
       (SAMPLE(?tu) AS ?toestandUrl)
       (GROUP_CONCAT(DISTINCT ?orgl; separator=" | ") AS ?organisatie)
       (SAMPLE(?ev) AS ?eerstverantwoordelijke)
       (GROUP_CONCAT(DISTINCT ?ondl; separator=" | ") AS ?ondertekenaar)
       (SAMPLE(?od) AS ?ondertekeningsdatum) (SAMPLE(?ud) AS ?uitgiftedatum)
       (SAMPLE(?pj) AS ?publicatiejaar) (SAMPLE(?pn) AS ?publicatienr) (SAMPLE(?ds) AS ?dossier)
    WHERE {{
  OPTIONAL {{ <{iri}> bwb:citeertitel ?ct }}
  OPTIONAL {{ <{iri}> bwb:opschrift ?op }}
  OPTIONAL {{ <{iri}> bwb:afkorting ?afk }}
  OPTIONAL {{ <{iri}> bwb:alternatieveTitel ?alt }}
  OPTIONAL {{ <{iri}> bwb:soort ?srt }}
  OPTIONAL {{ <{iri}> bwb:geldigVanaf ?gv }}
  OPTIONAL {{ <{iri}> bwb:geldigTot ?gt }}
  OPTIONAL {{ <{iri}> bwb:toestandUrl ?tu }}
  OPTIONAL {{ <{iri}> bwb:eerstverantwoordelijke ?ev }}
  OPTIONAL {{ <{iri}> bwb:ondertekeningsdatum ?od }}
  OPTIONAL {{ <{iri}> bwb:uitgiftedatum ?ud }}
  OPTIONAL {{ <{iri}> bwb:publicatiejaar ?pj }}
  OPTIONAL {{ <{iri}> bwb:publicatienr ?pn }}
  OPTIONAL {{ <{iri}> bwb:dossier ?ds }}
  OPTIONAL {{ <{iri}> bwb:uitgegevenDoor ?org . OPTIONAL {{ ?org rdfs:label ?orgl }} }}
  OPTIONAL {{ <{iri}> bwb:ondertekendDoor ?ond . OPTIONAL {{ ?ond rdfs:label ?ondl }} }}
}}"""


def follow_verwijzingen(bwb_id: str, artikel: str, lid: str | None = None) -> str:
    """Uitgaande verwijzingen — van de bepaling ZELF én van haar leden en onderdelen.

    **Waarom die uitbreiding.** Verwijzingen hangen in deze graaf overwegend aan het lid, niet aan
    het artikel. Graafbreed gemeten op 4 sep 2026: 1386 op leden, 940 op divisies, 589 op
    onderdelen, 431 op artikelen, 142 op bijlagen. Deze tool keek alleen naar het artikel en zag dus
    ongeveer een zesde van alles wat er staat. Voor artikel 36 IW 1990 — het aansprakelijkheids-
    artikel — betekende dat: nul verwijzingen gemeld, vijf aanwezig.

    Dat is geen randgeval maar de hoofdvraag van het volg-beleid ("waar verwijst deze bepaling
    naartoe"), en het antwoord was stil onvolledig: geen fout, geen lege tool, gewoon "niets
    gevonden" op een artikel dat vol verwijzingen staat.

    `?vanuit` zegt uit welk lid of onderdeel de verwijzing komt, want zonder die kolom kan het model
    de vindplaats niet noemen en lijkt het alsof het artikel als geheel verwijst. Geef je een `lid`
    mee, dan blijft de tool scherp op dat lid en zijn onderdelen.

    `?naar` was daarnaast een kale IRI, waardoor het model per verwijzing moest raden waar hij heen
    wees. Label, jci, BWB-id en citeertitel van het doel komen nu mee. Het doel hoeft niet in de
    graaf te zitten (open-world: een verwijzing naar een nog niet geïmporteerde wet), vandaar dat
    alles OPTIONAL is — een verwijzing met alleen een IRI is nog steeds een verwijzing.
    """
    return PREFIXES + f"""SELECT ?vanuit ?ankerTekst ?naar ?soort ?doelSoort ?doelLabel ?doelJci ?doelBwb ?doelRegeling WHERE {{
  {node_patroon(bwb_id, artikel, lid)}
  {{ ?node bwb:heeftVerwijzing ?v . BIND("de bepaling zelf" AS ?vanuit) }}
  UNION {{ ?node (bwb:heeftLid|bwb:heeftOnderdeel)+ ?deel . ?deel bwb:heeftVerwijzing ?v .
    FILTER(STRSTARTS(STR(?deel), "{NS}"))
    OPTIONAL {{ ?deel rdfs:label ?deellabel }}
    BIND(COALESCE(?deellabel, STR(?deel)) AS ?vanuit) }}
  OPTIONAL {{ ?v bwb:ankerTekst ?ankerTekst }}
  OPTIONAL {{ ?v bwb:soort ?soort }}
  OPTIONAL {{ ?v bwb:doelSoort ?doelSoort }}
  OPTIONAL {{
    ?v bwb:naar ?naar .
    # COALESCE(rdfs:label, bwb:doelLabel): een geïmporteerd doel draagt zijn eigen naam, een
    # nog-niet-geïmporteerd doel het leesbare fallback-label dat de importer meegaf. Die fallback
    # stond tot 4 sep 2026 óók op rdfs:label, en omdat elke wet in een eigen named graph zit
    # verscheen hij náást het echte label — waarna deze query elke verwijzing dubbel opleverde.
    OPTIONAL {{ ?naar rdfs:label ?eigenLabel }}
    OPTIONAL {{ ?naar bwb:doelLabel ?stubLabel }}
    BIND(COALESCE(?eigenLabel, ?stubLabel) AS ?doelLabel)
    OPTIONAL {{ ?naar bwb:jci ?doelJci }}
    # Het BWB-id staat als property alléén op de Regeling, niet op het artikel. Afleiden uit de
    # IRI is hier betrouwbaar omdat `rdf_vocab.by_ref_key` het altijd als eerste segment na de
    # basis zet: urn:bwb:BWBR0002471:artikel:9 → BWBR0002471.
    BIND(SUBSTR(STR(?naar), {len(NS) + 1}) AS ?rest)
    BIND(IF(CONTAINS(?rest, "{SEP}"), STRBEFORE(?rest, "{SEP}"), ?rest) AS ?doelBwb)
    OPTIONAL {{ ?dr a bwb:Regeling ; bwb:bwbId ?doelBwb ; bwb:citeertitel ?doelRegeling }}
  }}
}}"""


def verwijst_naar_deze(bwb_id: str, artikel: str, lid: str | None = None, limit: int = 50) -> str:
    """INKOMENDE verwijzingen op bepalingniveau: welke tekstdelen citeren dit artikel/lid?

    Dit is niet hetzelfde als `referenced_by`, en het verschil is het hele punt. `referenced_by`
    bevraagt `bwb:verwijzingDoor`, een WTI-relatie die naar een **Regeling** wijst: "de
    Uitvoeringsregeling verwijst ergens naar dit artikel". Bruikbaar, maar het antwoord op
    "wáár dan" ontbreekt.

    Deze query loopt de feitelijke citatiegraaf terug — `?bron bwb:verwijstNaar <node>` en de
    gereïficeerde vorm `?v bwb:naar <node>` — en levert de citerende bepaling zelf, mét haar
    ankertekst. Dat is de vraag die het volg-beleid voor verwijzingen stelt bij het afbakenen van
    een werkgebied, en hij was tot nu toe onbeantwoordbaar terwijl de data er lag.

    Beide vormen in één UNION omdat de importer ze allebei schrijft en ze niet altijd samenvallen:
    de directe `verwijstNaar` staat op het citerende tekstdeel, de reïficatie draagt de metadata.
    `DISTINCT` vangt de overlap.
    """
    lim = max(1, min(int(limit), 200))
    return PREFIXES + f"""SELECT DISTINCT ?bron ?bronLabel ?bronJci ?ankerTekst ?soort WHERE {{
  {node_patroon(bwb_id, artikel, lid)}
  {{
    ?bron bwb:verwijstNaar ?node .
  }} UNION {{
    ?v bwb:naar ?node .
    ?bron bwb:heeftVerwijzing ?v .
    OPTIONAL {{ ?v bwb:ankerTekst ?ankerTekst }}
    OPTIONAL {{ ?v bwb:soort ?soort }}
  }}
  FILTER(STRSTARTS(STR(?bron), "{NS}"))
  OPTIONAL {{ ?bron rdfs:label ?eigenLabel }}
  OPTIONAL {{ ?bron bwb:doelLabel ?stubLabel }}
  BIND(COALESCE(?eigenLabel, ?stubLabel) AS ?bronLabel)
  OPTIONAL {{ ?bron bwb:jci ?bronJci }}
}} ORDER BY ?bron LIMIT {lim}"""


def referenced_by(bwb_id: str, artikel: str) -> str:
    """Welke REGELINGEN naar dit tekstdeel verwijzen (WTI-relatie `verwijzingDoor`).

    Regelingniveau, bewust: dit is de vogelvlucht. Wil je de citerende bepaling zelf zien, gebruik
    dan `verwijst_naar_deze`.
    """
    return PREFIXES + f"""SELECT DISTINCT ?regeling ?citeertitel WHERE {{
  {node_patroon(bwb_id, artikel)}
  ?node bwb:verwijzingDoor ?regeling .
  FILTER(STRSTARTS(STR(?regeling), "{NS}"))
  OPTIONAL {{ ?regeling bwb:citeertitel ?citeertitel }}
}} ORDER BY ?citeertitel"""


def resolve_begrip(term: str) -> str:
    return PREFIXES + f"""SELECT DISTINCT ?concept ?label ?related WHERE {{
  ?concept a skos:Concept .
  {{ ?concept skos:prefLabel ?label }} UNION {{ ?concept rdfs:label ?label }}
  FILTER(CONTAINS(LCASE(STR(?label)), LCASE({_lit(term)})))
  OPTIONAL {{ ?concept skos:related|skos:broader|skos:narrower ?related }}
}} LIMIT 25"""


def count_by_type() -> str:
    return PREFIXES + f"""SELECT ?type (COUNT(DISTINCT ?s) AS ?aantal) WHERE {{
  ?s a ?type .
  FILTER(STRSTARTS(STR(?s), "{NS}"))
}} GROUP BY ?type ORDER BY DESC(?aantal)"""


def context(bwb_id: str, artikel: str, lid: str | None = None) -> str:
    """GraphRAG-subgraaf: de bepaling met haar structurele buurt in één query.

    Levert per relatie-soort (?relatie) een rij: de bepaling zelf (label/tekst/jci), de bevattende
    structuurdelen, de leden, de uitgaande verwijzingen, wie ernaar verwijst en de buren in het
    document. Zo ziet het model de bepaling ingebed in samenhang i.p.v. losse triples. Eén
    round-trip via UNION.

    TWEE REPARATIES die je moet kennen bij het lezen van oude antwoorden:

    1. **`4-bevat-door` matchte nooit iets.** De tak stond op `?p bwb:bevat <node>`, en `bwb:bevat`
       bestaat niet — de importer schrijft per niveau een eigen `heeft…`-predicaat. Van alle takken
       was juist die de reden dat deze tool "context" heet, en hij is altijd leeg geweest. Nu loopt
       hij over `BEVAT`, met een tweede tak voor de grootouder: het hoofdstuk waar het artikel in
       zit is voor een jurist relevanter dan de vaststelling dat een lid in een artikel zit.
    2. **Divisies deden niet mee.** `artikel_iri` weigert een punt, dus voor elke Leidraad-bepaling
       gaf deze tool niets. Nu via `node_patroon`.

    `7-verwezen-door` blijft op het ARTIKEL staan (`?art`), niet op het lid: `verwijzingDoor` is een
    WTI-relatie die de redactie op artikelniveau legt. Bij een divisie valt `?art` samen met `?node`.
    """
    node = node_patroon(bwb_id, artikel, lid)
    # Het artikel als aparte binding: bij een lid wil je de verwijzingen náár het ARTIKEL zien,
    # want `verwijzingDoor` legt de redactie op artikelniveau. Bij een divisie of zonder lid valt
    # het artikel samen met de node zelf.
    art = (
        f"BIND(<{artikel_iri(bwb_id, artikel)}> AS ?art)"
        if lid and is_artikelnummer(artikel)
        else "BIND(?node AS ?art)"
    )
    return PREFIXES + f"""SELECT ?relatie ?a ?b WHERE {{
  {node}
  {art}
  {{ BIND("1-zelf-label" AS ?relatie) ?node rdfs:label ?a . }}
  UNION {{ BIND("2-zelf-tekst" AS ?relatie) ?node bwb:tekst ?a . }}
  UNION {{ BIND("3-zelf-jci" AS ?relatie) ?node bwb:jci ?a . }}
  UNION {{ BIND("4-bevat-door" AS ?relatie) ?p {BEVAT} ?node .
    FILTER(STRSTARTS(STR(?p), "{NS}"))
    OPTIONAL {{ ?p rdfs:label ?pl }} OPTIONAL {{ ?p bwb:titel ?pt }}
    BIND(COALESCE(?pl, ?pt) AS ?a) BIND(STR(?p) AS ?b) }}
  UNION {{ BIND("4-bevat-door-2" AS ?relatie) ?g {BEVAT} ?tussen . ?tussen {BEVAT} ?node .
    FILTER(STRSTARTS(STR(?g), "{NS}"))
    OPTIONAL {{ ?g rdfs:label ?gl }} OPTIONAL {{ ?g bwb:titel ?gt }}
    BIND(COALESCE(?gl, ?gt) AS ?a) BIND(STR(?g) AS ?b) }}
  UNION {{ BIND("5-lid" AS ?relatie) ?node bwb:heeftLid ?l .
    FILTER(STRSTARTS(STR(?l), "{NS}")) OPTIONAL {{ ?l bwb:nummer ?a }} OPTIONAL {{ ?l bwb:tekst ?b }} }}
  UNION {{ BIND("6-verwijst-naar" AS ?relatie) ?node bwb:heeftVerwijzing ?v .
    OPTIONAL {{ ?v bwb:ankerTekst ?a }} OPTIONAL {{ ?v bwb:naar ?b }} }}
  UNION {{ BIND("7-verwezen-door" AS ?relatie) ?art bwb:verwijzingDoor ?r .
    FILTER(STRSTARTS(STR(?r), "{NS}")) OPTIONAL {{ ?r bwb:citeertitel ?a }} BIND(STR(?r) AS ?b) }}
  UNION {{ BIND("8-verwezen-door-bepaling" AS ?relatie) ?bron bwb:verwijstNaar ?node .
    FILTER(STRSTARTS(STR(?bron), "{NS}"))
    OPTIONAL {{ ?bron rdfs:label ?a }} BIND(STR(?bron) AS ?b) }}
  UNION {{ BIND("9-volgt-op" AS ?relatie) ?node bwb:volgtOp ?vorige .
    OPTIONAL {{ ?vorige rdfs:label ?a }} BIND(STR(?vorige) AS ?b) }}
  UNION {{ BIND("9-gevolgd-door" AS ?relatie) ?volgende bwb:volgtOp ?node .
    OPTIONAL {{ ?volgende rdfs:label ?a }} BIND(STR(?volgende) AS ?b) }}
}} ORDER BY ?relatie"""


# ------------------------------------------------------------------
# Structuur, begrippen, herkomst en tijd
#
# Deze bouwers ontsluiten wat de importer wél schrijft maar de toollaag lang niet bevroeg. De
# ontologie van `tools/bwb-import` telt ~24 object- en ~45 dataproperties; de agent raakte er een
# kleine helft van. Wat niet in een tool zit, bestaat voor het model niet — en `raw_sparql` hielp
# daar niet tegen, want de predicaatnamen stonden nergens waar het model ze kon lezen.
# ------------------------------------------------------------------

def inhoudsopgave(bwb_id: str, vanaf: str | None = None, diepte: int = 2) -> str:
    """De structuur van een regeling (of van één structuurdeel): wat zit waarin?

    Er was geen enkele manier om een regeling te verkennen. Een jurist die een werkgebied afbakent
    begint bij "welke hoofdstukken heeft deze wet en welke artikelen zitten in hoofdstuk VI" — en de
    agent kon dat niet beantwoorden, terwijl `heeftHoofdstuk`/`heeftAfdeling`/`heeftArtikel` gewoon
    in de graaf staan. Hij moest dan full-text gaan zoeken naar iets waarvan hij de naam nog niet wist.

    Alleen containerniveaus (`STRUCTUUR`): leden en onderdelen horen bij de tekst van een bepaling,
    niet bij de kaart van de regeling. Die haal je met `get_artikel`/`get_lid`.

    **Diepte is een UNION per niveau, geen `+`-pad.** Een transitief pad geeft geen niveau terug en
    dus geen boom, alleen een platte verzameling waarin een artikel en een hoofdstuk naast elkaar
    staan. Met een tak per niveau draagt elke rij haar `?niveau` en haar `?ouder`, en is de boom te
    reconstrueren. De prijs is dat de diepte begrensd moet zijn — vandaar de cap op 4.

    `?volgtOp` komt mee omdat de documentvolgorde niet uit de IRI valt af te leiden: `ORDER BY` is
    hier lexicaal (artikel 10 vóór artikel 2) en dat is een bekende valkuil in dit project. De
    consument sorteert zelf numeriek; `artikel._onderdeelsleutel` doet dat al voor het corpus.
    """
    d = max(1, min(int(diepte), 4))
    wortel = node_patroon(bwb_id, vanaf) if vanaf else f'BIND(<{regeling_iri(bwb_id)}> AS ?node)'
    takken = []
    for n in range(1, d + 1):
        pad = " . ".join(f"?t{i} {STRUCTUUR} ?t{i + 1}" for i in range(n))
        pad = pad.replace("?t0", "?node").replace(f"?t{n}", "?deel")
        ouder = "?node" if n == 1 else f"?t{n - 1}"
        takken.append(
            f'  {{ BIND("{n}" AS ?niveau) {pad} .\n'
            f"    FILTER(STRSTARTS(STR(?deel), \"{NS}\"))\n"
            f"    BIND(STR({ouder}) AS ?ouder) }}"
        )
    return PREFIXES + f"""SELECT ?niveau ?ouder ?deel ?soort ?nummer ?titel ?label ?jci ?volgtOp WHERE {{
  {wortel}
{chr(10).join('  UNION ' + t.lstrip() if i else t for i, t in enumerate(takken))}
  OPTIONAL {{ ?deel bwb:nummer ?nummer }}
  OPTIONAL {{ ?deel bwb:titel ?titel }}
  OPTIONAL {{ ?deel rdfs:label ?label }}
  OPTIONAL {{ ?deel bwb:jci ?jci }}
  OPTIONAL {{ ?deel bwb:volgtOp ?v . BIND(STR(?v) AS ?volgtOp) }}
  OPTIONAL {{ ?deel a ?t . FILTER(?t IN ({", ".join(CONCRETE_TYPES)})) BIND(STRAFTER(STR(?t), "{ONTOLOGIE}") AS ?soort) }}
}} ORDER BY ?niveau ?deel"""


def zoek_definitie(term: str, bwb_id: str | None = None, limit: int = 25) -> str:
    """Waar DEFINIEERT de wet dit begrip? – via `bwb:definieertBegrip`.

    De parser haalt per lid en per onderdeel op welke begrippen daar worden gedefinieerd
    (`parser.py:_definities`), en het is bovendien een geïndexeerd FTS-veld. Geen tool bevroeg het.
    De definitie-specialist moest dus definitieartikelen raden ("staat meestal in artikel 1 of 2")
    in plaats van te vragen waar het begrip wordt gedefinieerd.

    Dit is iets anders dan `resolve_begrip`: dat gaat over de SKOS-thesaurus uit de WTI — de
    trefwoorden die de redactie aan een regeling hangt — en niet over de wettelijke definitie zelf.
    Twee vragen, twee bronnen; verwar ze niet, want alleen deze levert een citeerbare vindplaats.

    De vindplaats komt van het ONDERDEEL waar de definitie staat, niet van het definitielid: dat is
    dezelfde regel die `get_lid` volgt, en de reden is dat "onderdeel k" citeren met de jci van het
    hele lid naar de verkeerde tekst wijst.
    """
    lim = max(1, min(int(limit), 100))
    scope = f'\n  FILTER(STRSTARTS(STR(?node), "{NS}{_bwb(bwb_id)}"))' if bwb_id else ""
    return PREFIXES + f"""SELECT ?node ?begrip ?tekst ?jci ?bwbId ?citeertitel ?nummer ?inLabel WHERE {{
  ?node bwb:definieertBegrip ?begrip .
  FILTER(CONTAINS(LCASE(STR(?begrip)), LCASE({_lit(term)}))){scope}
  OPTIONAL {{ ?node bwb:tekst ?tekst }}
  OPTIONAL {{ ?node bwb:jci ?jci }}
  OPTIONAL {{ ?node bwb:nummer ?nummer }}
  OPTIONAL {{ ?in {BEVAT} ?node . OPTIONAL {{ ?in rdfs:label ?inLabel }} }}
  BIND(SUBSTR(STR(?node), {len(NS) + 1}) AS ?rest)
  BIND(IF(CONTAINS(?rest, "{SEP}"), STRBEFORE(?rest, "{SEP}"), ?rest) AS ?bwbId)
  OPTIONAL {{ ?reg a bwb:Regeling ; bwb:bwbId ?bwbId ; bwb:citeertitel ?citeertitel }}
}} ORDER BY ?node LIMIT {lim}"""


def grondslagen(bwb_id: str, aanduiding: str | None = None) -> str:
    """Waar berust dit op, en wat berust hierop? – de WTI-delegatierelaties.

    `heeftGrondslag`, `grondslagVoor`, `bevoegdheidVoor` en `inFamilie` lagen ongebruikt in de
    graaf. Dat is niet zomaar metadata: `grondslagVoor` en `bevoegdheidVoor` hangen aan een
    **tekstdeel**, en de vraag die ze beantwoorden – "welke regeling berust op dit artikel" – is
    exact de vraag achter de JAS-klasse *Delegatiebevoegdheid*. Het platform kon hem niet stellen.

    Zonder `aanduiding` gaat het over de regeling (waarop berust zij, en wie berust op haar); mét
    een aanduiding over die ene bepaling. De richting staat in `?relatie`, want beide kanten zijn
    even relevant en ze in twee tools splitsen zou betekenen dat het model de goede moet raden.
    """
    node = node_patroon(bwb_id, aanduiding) if aanduiding else f'BIND(<{regeling_iri(bwb_id)}> AS ?node)'
    return PREFIXES + f"""SELECT ?relatie ?doel ?citeertitel ?label WHERE {{
  {node}
  {{ BIND("berust-op" AS ?relatie) ?node bwb:heeftGrondslag ?doel . }}
  UNION {{ BIND("grondslag-voor" AS ?relatie) ?node bwb:grondslagVoor ?doel . }}
  UNION {{ BIND("bevoegdheid-voor" AS ?relatie) ?node bwb:bevoegdheidVoor ?doel . }}
  UNION {{ BIND("in-familie" AS ?relatie) ?node bwb:inFamilie ?doel . }}
  UNION {{ BIND("berust-op-mij" AS ?relatie) ?doel bwb:heeftGrondslag ?node . }}
  FILTER(STRSTARTS(STR(?doel), "{NS}"))
  OPTIONAL {{ ?doel bwb:citeertitel ?citeertitel }}
  OPTIONAL {{ ?doel rdfs:label ?label }}
}} ORDER BY ?relatie ?citeertitel"""


def geldigheid(bwb_id: str, aanduiding: str | None = None, lid: str | None = None) -> str:
    """Welke TOESTAND lees ik, en wanneer kreeg deze tekst zijn huidige inhoud?

    Per tekstdeel staan `inwerking`, `terugwerkendTot`, `wijzigingsbronnen`, `bron`, `effect` en
    `status` in de graaf; per regeling `geldigVanaf`/`geldigTot` en `toestandUrl`. Alleen die
    laatste twee waren zichtbaar. Voor een platform waarvan brongetrouwheid het uitgangspunt is, is
    "welke toestand annoteer ik" geen randinformatie: een annotatie zonder toestand is niet
    reproduceerbaar, en terugwerkende kracht verandert wat er op een peildatum gold.

    De regelinggegevens komen altijd mee, ook als je naar één bepaling vraagt: een inwerkingsdatum
    zonder het geldigheidsvenster van de toestand waarin hij staat is geen antwoord.
    """
    node = node_patroon(bwb_id, aanduiding, lid) if aanduiding else f'BIND(<{regeling_iri(bwb_id)}> AS ?node)'
    reg = regeling_iri(bwb_id)
    return PREFIXES + f"""SELECT ?bepalingInwerking ?terugwerkendTot ?bron ?effect ?status ?wijzigingsbron
       ?geldigVanaf ?geldigTot ?toestandUrl ?ondertekeningsdatum ?uitgiftedatum ?dossier WHERE {{
  {node}
  OPTIONAL {{ ?node bwb:inwerking ?bepalingInwerking }}
  OPTIONAL {{ ?node bwb:terugwerkendTot ?terugwerkendTot }}
  OPTIONAL {{ ?node bwb:bron ?bron }}
  OPTIONAL {{ ?node bwb:effect ?effect }}
  OPTIONAL {{ ?node bwb:status ?status }}
  OPTIONAL {{ ?node bwb:wijzigingsbronnen ?wijzigingsbron }}
  OPTIONAL {{ <{reg}> bwb:geldigVanaf ?geldigVanaf }}
  OPTIONAL {{ <{reg}> bwb:geldigTot ?geldigTot }}
  OPTIONAL {{ <{reg}> bwb:toestandUrl ?toestandUrl }}
  OPTIONAL {{ <{reg}> bwb:ondertekeningsdatum ?ondertekeningsdatum }}
  OPTIONAL {{ <{reg}> bwb:uitgiftedatum ?uitgiftedatum }}
  OPTIONAL {{ <{reg}> bwb:dossier ?dossier }}
}} LIMIT 50"""


def bijlagen(bwb_id: str, sleutel: str | None = None) -> str:
    """De bijlagen van een regeling, of de inhoud van één bijlage.

    `Bijlage` zit in de FTS-index en `heeftBijlage` in de ontologie, maar geen tool haalde ze op:
    een zoekactie kon dus in een bijlage landen waarna de tekst onbereikbaar was. Een bijlage is
    bovendien citeerbaar (eigen jci) en kan eigen artikelen en onderdelen dragen — met tarieven en
    tabellen die inhoudelijk meetellen.

    **De sleutel is een nummer óf een stuk van het label**, want niet elke bijlage heeft een nummer.
    Live gemeten (4 sep 2026): de Awb heeft er drie mét nummer (1, 2, 3), de Uitvoeringsregeling
    Invorderingswet één **zonder** — "Bijlage – behorend bij artikel 1cb". Sleutelen op alleen
    `bwb:nummer` maakte die bijlage onbereikbaar: hij stond in de lijst en was niet te openen.
    """
    if sleutel is None:
        return PREFIXES + f"""SELECT ?bijlage ?nummer ?titel ?label ?jci WHERE {{
  <{regeling_iri(bwb_id)}> bwb:heeftBijlage ?bijlage .
  FILTER(STRSTARTS(STR(?bijlage), "{NS}"))
  OPTIONAL {{ ?bijlage bwb:nummer ?nummer }}
  OPTIONAL {{ ?bijlage bwb:titel ?titel }}
  OPTIONAL {{ ?bijlage rdfs:label ?label }}
  OPTIONAL {{ ?bijlage bwb:jci ?jci }}
}} ORDER BY ?bijlage"""
    lit = _lit(str(sleutel).strip())
    scope = f"{NS}{_bwb(bwb_id)}"
    return PREFIXES + f"""SELECT ?nummer ?titel ?label ?tekst ?jci ?deel ?deelnummer ?deeltekst WHERE {{
  {{ SELECT DISTINCT ?node WHERE {{
      <{regeling_iri(bwb_id)}> bwb:heeftBijlage ?node .
      OPTIONAL {{ ?node bwb:nummer ?n }}
      OPTIONAL {{ ?node rdfs:label ?l }}
      OPTIONAL {{ ?node bwb:titel ?t }}
      FILTER(?n = {lit}
             || CONTAINS(LCASE(STR(COALESCE(?l, ""))), LCASE({lit}))
             || CONTAINS(LCASE(STR(COALESCE(?t, ""))), LCASE({lit})))
    }} LIMIT 1 }}
  OPTIONAL {{ ?node bwb:nummer ?nummer }}
  OPTIONAL {{ ?node bwb:titel ?titel }}
  OPTIONAL {{ ?node rdfs:label ?label }}
  OPTIONAL {{ ?node bwb:tekst ?tekst }}
  OPTIONAL {{ ?node bwb:jci ?jci }}
  OPTIONAL {{
    ?node (bwb:heeftArtikel|bwb:heeftOnderdeel|bwb:heeftDivisie)+ ?deel .
    FILTER(STRSTARTS(STR(?deel), "{scope}"))
    OPTIONAL {{ ?deel bwb:nummer ?deelnummer }}
    OPTIONAL {{ ?deel bwb:tekst ?deeltekst }}
  }}
}} ORDER BY ?deel"""


def ontologie() -> str:
    """De T-Box: welke klassen en predicaten bestaan er, en wat betekenen ze?

    De ontologie staat als named graph ín de kennisgraaf, met `rdfs:label` en `rdfs:comment` per
    klasse en per property — precies de landkaart die `raw_sparql` nodig heeft. Zonder deze query
    moest het model predicaatnamen raden, en een geraden predicaat matcht niets zónder foutmelding.
    Dat is dezelfde stille onvolledigheid als de `bwb:bevat`-bug, alleen dan door het model
    veroorzaakt in plaats van door ons.

    `?soort` scheidt klassen van object- en dataproperties, zodat het model weet of een term aan de
    positie van een type of van een predicaat hoort.
    """
    return PREFIXES + f"""PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?soort ?term ?label ?comment WHERE {{
  {{ ?t a owl:Class . BIND("klasse" AS ?soort) }}
  UNION {{ ?t a owl:ObjectProperty . BIND("relatie" AS ?soort) }}
  UNION {{ ?t a owl:DatatypeProperty . BIND("eigenschap" AS ?soort) }}
  FILTER(STRSTARTS(STR(?t), "{ONTOLOGIE}"))
  BIND(CONCAT("bwb:", STRAFTER(STR(?t), "{ONTOLOGIE}")) AS ?term)
  OPTIONAL {{ ?t rdfs:label ?label }}
  OPTIONAL {{ ?t rdfs:comment ?comment }}
}} ORDER BY ?soort ?term"""
