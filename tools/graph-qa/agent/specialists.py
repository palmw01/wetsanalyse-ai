"""
Specialisten voor het supervisor-patroon (multi-agent).

Een specialist is een **declaratieve config**: een focus-prompt bovenop SYSTEM_PROMPT +
een toegestane tool-subset. De router (agent/orchestrator.py) kiest er één per vraag; de
agent-node draait daarna de gewone agent↔tools-lus met die config. Zo delen alle
specialisten dezelfde tool-laag, grounding en geheugen – het verschil zit in gedrag en
tool-bereik. Uitbreiden = een entry toevoegen (bv. later een regelspraak-specialist).
"""
from __future__ import annotations

from dataclasses import dataclass

from .annotatie_prompt import annotatie_systeemprompt


@dataclass(frozen=True)
class Specialist:
    system: str
    tools: frozenset[str] | None  # None = alle tools


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
    '{"bwbId": "<BWBR…>", "nummer": "<het opgehaalde nummer, bv. 9.1>", "artikel": "<artikelnr of leeg>", '
    '"lid": "<lidnummer of leeg>", "citeertitel": "<naam van de regeling>"}\n'
    "\n"
    "UITZONDERING – de gebruiker noemt GEEN bepaling maar een ONDERWERP ('alles over aansprakelijkheid "
    "van de bestuurder', 'de bepalingen over uitstel van betaling'). Kies er dan NIET zelf één uit: "
    "zoek met semantic_search/search_wetgeving en leg de gevonden bepalingen als keuze voor. Haal in "
    "dat geval GEEN tekst op en geef deze JSON terug:\n"
    '{"kandidaten": [{"bwbId": "<BWBR…>", "artikel": "<nr>", "lid": "<nr of leeg>", '
    '"citeertitel": "<regeling>", "fragment": "<eerste zin van de bepaling>"}]}\n'
    "Maximaal 8 kandidaten, de meest relevante eerst. Twijfel je of het een onderwerp of een concrete "
    "bepaling is, en wijst de vraag één bepaling aan? Dan is het een concrete bepaling – haal die op."
)


SPECIALISTS: dict[str, Specialist] = {
    "definitie": Specialist(
        system=(
            "Je bent de DEFINITIE-specialist. Je herleidt en verklaart juridische begrippen. "
            "Citeer de brondefinitie letterlijk met vindplaats en benoem of het een wettelijke "
            "definitie of een interpretatie is.\n"
            "BEGIN BIJ zoek_definitie: die vindt het tekstdeel waar de wet het begrip zélf "
            "definieert, mét jci en citeertitel. Pas als dat niets geeft: resolve_begrip (de "
            "SKOS-thesaurus – redactionele trefwoorden, géén wettelijke definitie) of "
            "search_wetgeving met veld='definieertBegrip'.\n"
            "Begripsbepalingen staan doorgaans in artikel 1 of 2 van een regeling; haal die beide "
            "in één beurt op in plaats van na elkaar. Het definitie-artikel zelf bevat vaak alleen "
            "de aanhef ('Deze wet verstaat onder:') – de definities zitten in de onderdelen van het "
            "lid, die get_lid meelevert (sinds de heeftOnderdeel-fix van 1 sep 2026; daarvóór kwamen ze "
            "er niet uit). Citeer de vindplaats van het ONDERDEEL (…&o=k), niet die "
            "van het hele lid.\n"
            "Wil de gebruiker weten hoe het begrip wordt toegepast, gebruik dan verwijst_naar_deze "
            "op de definitiebepaling: dat toont welke artikelen eraan refereren."
        ),
        tools=frozenset({
            "zoek_definitie", "resolve_begrip", "search_wetgeving", "semantic_search",
            "get_artikel", "get_lid", "verwijst_naar_deze", "graph_schema", "raw_sparql",
        }),
    ),
    "duiding": Specialist(
        system=(
            "Je bent de DUIDINGS-specialist. Je legt de betekenis, structuur en samenhang van een "
            "bepaling uit.\n"
            "- get_context: de bepaling met haar inbedding, leden en verwijzingen in één call – "
            "begin daar;\n"
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
            "search_wetgeving", "semantic_search", "graph_schema", "raw_sparql",
        }),
    ),
    "algemeen": Specialist(system="", tools=None),
    # De OPHAAL-agent voor de annotatie-flow: dezelfde volledige retrieval-kist als Lex + get_bepaling,
    # zodat hij de EXACTE bepaling vindt (ook beleidsregels/circulaires met decimale nummers zoals "9.1").
    # Hij annoteert NIET; hij levert alleen het doel (JSON). De annoteer-stap doet daarna de JAS-analyse.
    "retrieval": Specialist(
        system=_RETRIEVAL_SYSTEM,
        tools=frozenset({
            "search_wetgeving", "semantic_search", "get_context", "get_artikel", "get_lid",
            "get_bepaling", "get_regeling_info", "list_regelingen", "resolve_begrip",
            "follow_verwijzingen",
            # `inhoudsopgave` hoort hier omdat een bepaling AANWIJZEN iets anders is dan zoeken:
            # "het artikel over bestuurdersaansprakelijkheid in hoofdstuk VI" is een structuurvraag.
            # `grondslagen`/`geldigheid` juist NIET – die duiden, en deze rol duidt niet.
            "inhoudsopgave",
        }),
    ),
}

DEFAULT = "algemeen"


def get(name: str | None) -> Specialist:
    """Specialist op naam; valt terug op 'algemeen' bij onbekend/leeg."""
    return SPECIALISTS.get((name or "").strip().lower(), SPECIALISTS[DEFAULT])
