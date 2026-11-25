"""De modelkeuzes van Lex: welk werk een eigen modelprofiel kan krijgen, de enige lijst voor de hele keten.

Het model hoort op het agentprofiel, zoals `model:` bij een subagent van Claude Code (besluit gebruiker 15 nov 2026). Een
sleutel is daarom:

- `agent:<profiel>` voor elk agentprofiel van Lex (`.claude/lex-agents/<profiel>.md`): de specialisten, de centrale agent
  en de ophaal-agent. Een profiel houdt zijn keuze, of het nu als specialist of als subagent draait;
- `stap:<rol>` voor elke modelstap zonder agentprofiel (de waarden van `llm_stap.Rol` zonder toollus: classifier,
  reviewer, …), plus `stap:subagent` voor een subagent waarvan het profiel geen eigen keuze heeft.

De keuze is configuratie in het beheer, niet in het profielbestand: de beheerder wijzigt hem zonder uitrol. De api
bewaart hem (`api/app/modelkeuzes.py`), graph-qa past hem toe (`agent/modelkeuze.py`). Zonder keuze volgt een sleutel het
standaardprofiel. Lex neemt van een profiel alleen de modelnaam over: endpoint en sleutel blijven die van de straat.

Een profiel of rol die erbij komt, staat hier ook: `tools/graph-qa/tests/test_modelkeuze.py` maakt verschil rood.
"""
from __future__ import annotations

from dataclasses import dataclass

AGENTS = "Agents"
STAPPEN = "Stappen zonder agentprofiel"


@dataclass(frozen=True)
class Modelkeuze:
    sleutel: str
    label: str
    groep: str
    beschrijving: str
    #: Leeg, of waarom een lichter model hier riskant is. De beheertab toont het bij de keuze.
    waarschuwing: str = ""

    @property
    def soort(self) -> str:
        return self.sleutel.split(":", 1)[0]

    @property
    def naam(self) -> str:
        """De profielnaam of de rol, zonder het voorvoegsel."""
        return self.sleutel.split(":", 1)[1]


_OORDEEL = ("Hier velt het model een oordeel over wetgeving. Een lichter model verslechtert precies dat oordeel; "
            "kies alleen iets anders na een meting.")
_OPHALEN = ("Kiest dit model de verkeerde bepaling, dan is alles daarna brongetrouw én verkeerd. Kies alleen iets "
            "anders na een meting.")


def _agent(naam: str, label: str, beschrijving: str, waarschuwing: str = "") -> Modelkeuze:
    return Modelkeuze(f"agent:{naam}", label, AGENTS, beschrijving, waarschuwing)


def _stap(rol: str, label: str, beschrijving: str, waarschuwing: str = "") -> Modelkeuze:
    return Modelkeuze(f"stap:{rol}", label, STAPPEN, beschrijving, waarschuwing)


#: De volgorde is die van de beheertab: eerst de agents, dan de stappen.
KEUZES: tuple[Modelkeuze, ...] = (
    _agent("centraal", "Centrale agent", "Beantwoordt een vraag zelf en zet voor groter werk subagents in."),
    _agent("centraal_breed", "Centrale agent, alle tools",
           "Dezelfde centrale agent met de tools buiten de kernset (na `meer_tools`)."),
    _agent("rechtspraak_lezen", "Rechtspraak lezen",
           "Subagent: doorloopt de uitspraken bij een bepaling en geeft per uitspraak de kern met een passage."),
    _agent("wetsgeschiedenis_lezen", "Wetsgeschiedenis lezen",
           "Subagent: leest de Kamerstukken en bekendmakingen bij een bepaling en vat per stuk samen."),
    _agent("bepalingen_duiden", "Bepalingen duiden",
           "Subagent: doorloopt een reeks bepalingen en geeft per bepaling de kern met een passage."),
    _agent("algemeen", "Algemeen", "Beantwoordt de overige vragen over wet- en regelgeving uit de kennisgraaf."),
    _agent("duiding", "Duiding", "Legt uit wat een bepaling betekent en hoe bepalingen samenhangen."),
    _agent("annotaties_lezen", "Annotaties lezen", "Beantwoordt vragen over bestaande annotaties; wijzigt niets."),
    _agent("begrippen_lezen", "Begrippen lezen", "Beantwoordt vragen over de vastgelegde begrippen; wijzigt niets."),
    _agent("regels_lezen", "Afleidingsregels lezen",
           "Beantwoordt vragen over de vastgelegde afleidingsregels; wijzigt niets."),
    _agent("contenttoets", "Contenttoets",
           "Toetst content, zoals een webtekst, op juistheid en volledigheid tegen de wet- en regelgeving."),
    _agent("retrieval", "Bepaling ophalen", "Zoekt met tools de bepaling op die geannoteerd wordt.", _OPHALEN),
    _stap("subagent", "Subagents",
          "Een subagent van de centrale agent, als zijn agentprofiel geen eigen keuze heeft."),
    _stap("stukcontrole", "Controle per stuk", "Toetst elk stuk uit het rapport van een subagent aan de bron."),
    _stap("deelvraag_keuze", "Bronnen per deelvraag kiezen (proef)",
          "Kiest de bepalingen bij een deelvraag uit wat de zoekmachine vond. Een proef, standaard uit.", _OPHALEN),
    _stap("wetstermen", "Deelvraag in wetstermen (proef)",
          "Vertaalt een deelvraag naar zoektermen in de taal van de wet. Een proef, standaard uit.", _OPHALEN),
    _stap("jas_classifier", "JAS-classifier", "Kiest de JAS-klasse voor elke kandidaat.", _OORDEEL),
    _stap("jas_reviewer", "JAS-reviewer", "Beoordeelt de twijfelgevallen van de classifier opnieuw.", _OORDEEL),
    _stap("bepaling_toelichting", "Toelichting bij een bepaling",
          "Schrijft een korte toelichting bij een opgehaalde bepaling."),
    _stap("intake", "Werkgebied samenstellen", "Stelt de velden van een werkgebied voor in de vraagkaarten."),
    _stap("deelvragen_voorstel", "Deelvragen voorstellen", "Stelt de deelvragen bij een analysevraag voor."),
    _stap("deelvraag_verbeter", "Deelvraag verbeteren", "Maakt een bestaande deelvraag scherper."),
    _stap("begrip_kaart", "Begrip uitwerken",
          "Werkt een begripskaart uit: definitie, betekenisverschil en voorbeelden."),
    _stap("kaartactie", "Kaartactie", "Voert één actie op een begripskaart uit, vanuit het gesprek."),
    _stap("begrip_vergelijk", "Begrippen vergelijken",
          "Vergelijkt begrippen bij het voorstellen van betekenisgroepen."),
)

SLEUTELS: tuple[str, ...] = tuple(k.sleutel for k in KEUZES)
PER_SLEUTEL: dict[str, Modelkeuze] = {k.sleutel: k for k in KEUZES}


def bruikbaar_voor_lex(model: str, api_base: str, straat_api_base: str) -> str:
    """Leeg als Lex dit profiel kan gebruiken, anders waarom niet.

    Lex praat met het Anthropic-endpoint van de straat en neemt alleen de modelnaam over. Een profiel met een eigen
    endpoint zou dus stil op het endpoint van de straat draaien; dat weigeren we liever zichtbaar."""
    if not model.strip():
        return "Het profiel heeft geen model."
    if not model.strip().startswith("claude-"):
        return "Lex draait alleen Claude-modellen (een modelnaam die met 'claude-' begint)."
    eigen, straat = api_base.strip().rstrip("/"), straat_api_base.strip().rstrip("/")
    if eigen and straat and eigen != straat:
        return "Het profiel heeft een ander endpoint dan de straat; Lex neemt alleen de modelnaam over."
    return ""
