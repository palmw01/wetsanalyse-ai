"""
Specialisten voor het supervisor-patroon (multi-agent).

Een specialist is een **declaratieve config**: een focus-prompt bovenop SYSTEM_PROMPT +
een toegestane tool-subset. De router (agent/orchestrator.py) kiest er één per vraag; de
agent-node draait daarna de gewone agent↔tools-lus met die config. Zo delen alle
specialisten dezelfde tool-laag, grounding en geheugen – het verschil zit in gedrag en
tool-bereik. Uitbreiden = een entry toevoegen (bv. later een regelspraak-specialist).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from bronmodel.connectors import CONNECTORS

from .methode import instructies


@dataclass(frozen=True)
class Specialist:
    system: str
    tools: frozenset[str] | None  # None = alle tools
    # De sjablonen waarmee deze specialist afrondt (`agent/sjablonen`, ADR-008).
    sjablonen: frozenset[str] = frozenset()
    # Wat hij doet, in één zin met wat er níét bij hoort (ADR-010 contractpunt 1); de catalogus toont het (ADR-014).
    doel: str = ""


# De OPHAAL-agent: vindt en haalt de EXACTE bepaling op die geannoteerd moet worden. Geen annotatie —
# alleen retrieval + een doel-JSON. Overschrijft bewust de QA-antwoordinstructies uit SYSTEM_PROMPT.
_RETRIEVAL_SYSTEM = (
    "LET OP – je BEANTWOORDT deze vraag niet en je annoteert niet. Je enige taak is de EXACTE wettelijke "
    "bepaling OPHALEN die de gebruiker wil laten annoteren, zodat een volgende stap die kan analyseren.\n"
    "WERKWIJZE:\n"
    "- Bepaal om welke regeling + bepaling het gaat. Ken je de bwbId nog niet, zoek die met "
    "search_wetgeving/semantic_search; met veld='citeertitel' vind je een regeling op naam. "
    "Weet je de regeling maar niet welk artikel, gebruik dan inhoudsopgave.\n"
    "- Haal de tekst van precies die bepaling op:\n"
    "  • gewone wet met leden en een lid is genoemd → get_lid(bwb_id, artikel, lid);\n"
    "  • heel artikel → get_artikel(bwb_id, artikel);\n"
    "  • beleidsregel/circulaire of een DECIMAAL nummer zoals '9.1' (bv. de Leidraad Invordering 2008), "
    "of als get_lid/get_artikel niets geven → get_bepaling(bwb_id, nummer) met dat nummer "
    "(bv. '9.1', '22a'). Let op: 'artikel 9 lid 1' van een beleidsregel bedoelt vaak bepaling '9.1'.\n"
    "- Je MOET eindigen met een geslaagde get_lid/get_artikel/get_bepaling-call die de tekst teruggaf.\n"
    "Geef daarna UITSLUITEND deze JSON terug (geen proza):\n"
    "Voor een onderdeel, paragraaf, bijlage of andere specifieke bronnode voeg je 'bron_iri' toe "
    "met de exacte IRI uit het toolresultaat. Verzin geen IRI; de bronresolver controleert haar.\n"
    '{"bwbId": "<BWBR…>", "nummer": "<het opgehaalde nummer, bv. 9.1>", "artikel": "<artikelnr of leeg>", '
    '"lid": "<lidnummer of leeg>", "citeertitel": "<naam van de regeling>"}\n'
    "\n"
    "MEER DAN ÉÉN ARTIKEL – noemt de gebruiker meerdere artikelen ('artikel 8 en 9', 'art. 8 lid 2 en "
    "art. 9', 'de artikelen 8 t/m 10'), haal dan NIETS op en kies er GEEN uit; geef alleen deze JSON:\n"
    '{"meerdere": ["<artikelnr>", "<artikelnr>"]}\n'
    "Meerdere leden of subbepalingen van hetzelfde artikel ('artikel 9 lid 1 en 3', '9.1 en 9.5') zijn "
    "wél één artikel: haal dan het artikel op (get_artikel of get_bepaling met het artikelnummer).\n"
    "\n"
    "UITZONDERING – de gebruiker noemt GEEN bepaling maar een ONDERWERP ('alles over aansprakelijkheid "
    "van de bestuurder', 'de bepalingen over uitstel van betaling'). Kies er dan NIET zelf één uit: "
    "zoek met zoek_opbouw en semantic_search/search_wetgeving en leg de gevonden bepalingen als keuze voor. Haal in "
    "dat geval GEEN tekst op en geef deze JSON terug:\n"
    '{"kandidaten": [{"bwbId": "<BWBR…>", "artikel": "<nr>", "lid": "<nr of leeg>", '
    '"citeertitel": "<regeling>"}]}\n'
    "Maximaal 8 kandidaten, de meest relevante eerst. Twijfel je of het een onderwerp of een concrete "
    "bepaling is, en wijst de vraag één bepaling aan? Dan is het een concrete bepaling – haal die op."
)


# Een vraag naar de tekst van een bepaling rondt met het sjabloon af, bij elke specialist die zulke vragen krijgt.
_AFRONDEN_BEPALING = (
    "AFRONDEN: vraagt de gebruiker wat er in een bepaling staat of wat ze regelt, dan schrijf je geen antwoord in "
    "tekst. Je haalt de bepaling op met get_artikel, get_lid of get_bepaling en roept als laatste stap "
    "antwoord_bepaling aan: de werkplek toont de wettekst en de vindplaats zelf. Gaat de vraag om meer dan de tekst "
    "(uitleg, samenhang, toepassing op een geval), of vond je de bepaling niet, dan antwoord je gewoon in tekst."
)


# De duiding-specialist heeft twee afrondingen: de wettekst zelf, of uitleg die op aangewezen passages rust.
_AFRONDEN_DUIDING = (
    "AFRONDEN: je schrijft geen antwoord in tekst, je rondt als laatste stap af met een sjabloontool.\n"
    "- Vraagt de gebruiker alleen wat er in een bepaling staat → antwoord_bepaling.\n"
    "- Vraagt de gebruiker om uitleg (hoe werkt X, hoe verhoudt Y zich tot Z, wat betekent dit voor een geval) → "
    "antwoord_duiding. Citeren kan alleen uit de hele tekst van een bepaling: haal elke bepaling waarop je leunt op met "
    "get_artikel, get_lid of get_bepaling; get_context en zoekresultaten tonen de samenhang maar zijn daarvoor niet genoeg. "
    "Noem je in je uitleg een bepaling, wijs er dan een passage uit aan.\n"
    "- Vond je geen bepaling die de vraag draagt, dan antwoord je in tekst en zeg je dat."
)


SPECIALISTS: dict[str, Specialist] = {
    "annotaties_lezen": Specialist(
        doel="Beantwoordt vragen over bestaande annotaties door ze te zoeken en te lezen; maakt of wijzigt er geen.",
        system=("Je raadpleegt uitsluitend bestaande annotaties. De eerste zoekopdracht is al voor "
                "je uitgevoerd en staat als toolresultaat in dit gesprek; bouw je antwoord daarop. "
                "Gebruik get_annotatie voor detail, overzicht_annotaties voor 'welke … zijn er' per "
                "klasse, of search_annotaties met ándere filters – "
                "herhaal niet dezelfde zoekopdracht. Maak of wijzig nooit een annotatie. "
                "Rapporteer toegepaste filters, omvang, paginatie en onvolledige dekking. "
                "Een toolfout of gedeeltelijk resultaat betekent niet dat niets bestaat. "
                "Annotaties en beoordelingen zijn afgeleide duiding, geen wettelijke bron. "
                "Haal bij inhoudelijke wetsclaims de bepaling afzonderlijk op met een brontool. "
                "Gebruik zoekresultaten uit wetgeving nooit als vervanging voor annotatiezoekresultaten.\n"
                "AFRONDEN: vraagt de gebruiker welke annotaties of markeringen er zijn, dan schrijf je geen antwoord in "
                "tekst maar roep je als laatste stap antwoord_annotaties aan: de werkplek toont de treffers uit je laatste "
                "zoekopdracht zelf, met of ze compleet zijn. Gaat de vraag om meer (waarom deze klasse, hoe verhouden ze zich), "
                "dan antwoord je in tekst."),
        tools=frozenset({"search_annotaties", "overzicht_annotaties", "get_annotatie", "get_annotatiedekking",
                         "get_artikel", "get_lid", "get_bepaling", "list_regelingen", "inhoudsopgave"}),
        sjablonen=frozenset({"antwoord_annotaties"}),
    ),
    "begrippen_lezen": Specialist(
        doel="Beantwoordt vragen over de vastgelegde begrippen van de werkgebieden; zoekt en leest, wijzigt niets.",
        system=("Je raadpleegt de begrippen die juristen in werkgebieden vastlegden. De eerste zoekopdracht is al "
                "voor je uitgevoerd en staat als toolresultaat in dit gesprek; bouw je antwoord daarop. Gebruik "
                "get_begrip voor de passages en relaties van één begrip, of search_begrippen met een ándere "
                "zoekterm of status – herhaal niet dezelfde zoekopdracht. Maak of wijzig nooit een begrip. "
                "Noem per begrip de status en het werkgebied; bij een vervangen begrip de opvolger. Een begrip is "
                "een analyse-uitkomst, geen wettelijke definitie: zet de definitie niet tussen aanhalingstekens, "
                "en haal bij inhoudelijke wetsclaims de bepaling afzonderlijk op met een brontool. Een toolfout "
                "of onvolledig resultaat betekent niet dat een begrip niet bestaat.\n"
                "AFRONDEN: vraagt de gebruiker welke begrippen er liggen of of een term is vastgelegd, dan schrijf je "
                "geen antwoord in tekst maar roep je als laatste stap antwoord_begrip aan met een leeg begrip: de werkplek "
                "toont de begrippen uit je laatste zoekopdracht zelf. Wil de gebruiker ook weten wat de wet zegt, zoek "
                "dan met zoek_definitie en noem het begrip. Gaat de vraag om meer (passages, relaties), dan antwoord je in tekst."),
        tools=frozenset({"search_begrippen", "get_begrip", "zoek_definitie", "get_artikel", "get_lid",
                         "get_bepaling", "list_regelingen"}),
        sjablonen=frozenset({"antwoord_begrip"}),
    ),
    "definitie": Specialist(
        doel="Zoekt de wettelijke definitie van een begrip en geeft die letterlijk, met vindplaats.",
        system=(
            "Je bent de DEFINITIE-specialist. Je herleidt en verklaart juridische begrippen. "
            "AFRONDEN: vraagt de gebruiker wat een begrip betekent, dan schrijf je geen antwoord in tekst. "
            "Je roept als laatste stap antwoord_begrip aan: de werkplek toont de definities, hun vindplaats "
            "en de vastgelegde begrippen zelf. Alleen een vraag die om meer gaat dan de betekenis van één "
            "begrip (een vergelijking, de toepassing op een geval) beantwoord je in tekst; citeer de "
            "brondefinitie dan letterlijk met vindplaats en benoem of het een wettelijke definitie of "
            "een interpretatie is.\n"
            "BEGIN BIJ zoek_definitie: die vindt het tekstdeel waar de wet het begrip zélf "
            "definieert, mét jci en citeertitel. Pas als dat niets geeft: resolve_begrip (de "
            "SKOS-thesaurus – redactionele trefwoorden, géén wettelijke definitie) of "
            "search_wetgeving met veld='definieertBegrip'.\n"
            "Haal de gevonden definitiebepaling op. Het definitie-artikel zelf bevat vaak alleen "
            "de aanhef ('Deze wet verstaat onder:') – de definities zitten in de onderdelen van het "
            "lid, die get_lid meelevert. Citeer de vindplaats van het ONDERDEEL (…&o=k), niet die "
            "van het hele lid.\n"
            "Wil de gebruiker weten hoe het begrip wordt toegepast, gebruik dan verwijst_naar_deze "
            "op de definitiebepaling: dat toont welke artikelen eraan refereren."
        ),
        tools=frozenset({
            "zoek_definitie", "resolve_begrip", "search_wetgeving", "semantic_search",
            "get_artikel", "get_lid", "verwijst_naar_deze", "graph_schema", "raw_sparql",
            # Een vastgelegd begrip (fase F4) naast de wettelijke definitie – gescheiden gehouden.
            "search_begrippen", "get_begrip",
        }),
        sjablonen=frozenset({"antwoord_begrip"}),
    ),
    "duiding": Specialist(
        doel="Legt uit wat een bepaling betekent en hoe bepalingen samenhangen, onderbouwd met letterlijke passages.",
        system=(
            "Je bent de DUIDINGS-specialist. Je legt de betekenis, structuur en samenhang van een "
            "bepaling uit.\n" + _AFRONDEN_DUIDING + "\n"
            "- get_context: de bepaling met haar inbedding, leden en verwijzingen in één call – "
            "begin daar voor de samenhang;\n"
            "- follow_verwijzingen (waarheen) en verwijst_naar_deze (wie citeert dit) om "
            "kruisverwijzingen in beide richtingen te volgen; referenced_by geeft alleen de "
            "regelingen, dus grofmaziger;\n"
            "- inhoudsopgave om te zien waar de bepaling in de opbouw van de regeling staat – de "
            "plaats in een hoofdstuk kleurt de uitleg;\n"
            "- grondslagen bij delegatie: waarop berust deze bepaling, en welke regeling berust "
            "op haar;\n"
            "- geldigheid als de vraag over een peildatum, een versie of terugwerkende kracht gaat, "
            "of als je wilt melden op welke toestand je uitleg berust."
        ),
        tools=frozenset({
            "get_context", "get_artikel", "get_lid", "get_bepaling", "follow_verwijzingen",
            "verwijst_naar_deze", "referenced_by", "inhoudsopgave", "grondslagen", "geldigheid",
            "bijlagen", "list_regelingen", "get_regeling_info",
            "search_wetgeving", "semantic_search", "zoek_opbouw", "overzicht_onderwerp", "graph_schema", "raw_sparql",
            # Duiding is ook de rol voor vragen óver een gemaakte markering ("waarom deze klasse?",
            # advies). Zonder deze tools kon hij het spoor en de alternatieven van de markering niet
            # lezen, en de klasse-omschrijving alleen raden.
            "get_annotatie", "jas_klasse_opvragen",
        }),
        sjablonen=frozenset({"antwoord_bepaling", "antwoord_duiding"}),
    ),
    "algemeen": Specialist(doel="Beantwoordt de overige vragen over wet- en regelgeving uit de kennisgraaf.", system=_AFRONDEN_BEPALING, tools=None, sjablonen=frozenset({"antwoord_bepaling"})),
    # De OPHAAL-agent voor de annotatie-flow: dezelfde volledige retrieval-kist als Lex + get_bepaling,
    # zodat hij de EXACTE bepaling vindt (ook beleidsregels/circulaires met decimale nummers zoals "9.1").
    # Hij annoteert NIET; hij levert alleen het doel (JSON). De annoteer-stap doet daarna de JAS-analyse.
    "retrieval": Specialist(
        doel="Vindt de exacte bepaling die geannoteerd moet worden en haalt die op; beantwoordt en annoteert zelf niet.",
        system=_RETRIEVAL_SYSTEM,
        tools=frozenset({
            "search_wetgeving", "semantic_search", "zoek_opbouw", "overzicht_onderwerp", "get_context", "get_artikel", "get_lid",
            "get_bepaling", "get_regeling_info", "list_regelingen", "resolve_begrip",
            "follow_verwijzingen",
            # `inhoudsopgave` hoort hier omdat een bepaling AANWIJZEN iets anders is dan zoeken:
            # "het artikel over bestuurdersaansprakelijkheid in hoofdstuk VI" is een structuurvraag.
            # `grondslagen`/`geldigheid` juist NIET – die duiden, en deze rol duidt niet.
            "inhoudsopgave",
        }),
    ),
}



def _met_connectors(specs: dict[str, Specialist]) -> dict[str, Specialist]:
    """De tools van elke bronconnector (ADR-013) bij de rollen die zijn beschrijving noemt. Of hij in een beurt
    aanstaat, beslist `tools.toegestane_tools`; hier staat alleen wie hem mág krijgen. `tools=None` (algemeen) heeft
    ze al."""
    for c in CONNECTORS.values():
        for rol in c.specialisten:
            if specs[rol].tools is not None:
                specs[rol] = replace(specs[rol], tools=specs[rol].tools | c.tools)
    return specs


SPECIALISTS = _met_connectors(SPECIALISTS)

DEFAULT = "algemeen"


def get(name: str | None) -> Specialist:
    """Specialist op naam; valt terug op 'algemeen' bij onbekend/leeg."""
    rol = (name or "").strip().lower()
    rol = rol if rol in SPECIALISTS else DEFAULT
    spec = SPECIALISTS[rol]
    return replace(spec, system=instructies(methoderol(rol)) + "\n\n" + spec.system)


def methoderol(name: str | None) -> str:
    """De rol uit de skill waarvan de specialist de methodetekst krijgt (`llm_stap` toetst dat hij er staat)."""
    rol = (name or "").strip().lower()
    rol = rol if rol in SPECIALISTS else DEFAULT
    return "algemeen" if rol in ("annotaties_lezen", "begrippen_lezen") else rol
