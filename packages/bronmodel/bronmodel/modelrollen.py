"""De modelrollen van Lex: welk werk een eigen modelprofiel kan krijgen, de enige lijst voor de hele keten.

Elke modelaanroep van graph-qa draagt een rol (`agent/llm_stap.py`, `Rol`), en een subagent van de centrale agent draait
op zijn eigen klasse (`subagent`). De beheerder kiest per rol een modelprofiel (Instellingen → Beheer → Modelprofielen);
zonder keuze volgt de rol het standaardprofiel, en dan verandert er niets. De api bewaart de keuze
(`api/app/modelrollen.py`), graph-qa past hem toe (`agent/modelkeuze.py`). Lex neemt van een profiel alleen de
modelnaam over: endpoint en sleutel blijven die van de straat (besluit gebruiker 15 nov 2026).

Een rol die erbij komt, staat hier én in `Rol`: `tools/graph-qa/tests/test_modelkeuze.py` maakt verschil rood.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Modelrol:
    naam: str
    label: str
    groep: str
    beschrijving: str
    #: Leeg, of waarom een lichter model hier riskant is. De beheertab toont het bij de keuze.
    waarschuwing: str = ""


_OORDEEL = ("Hier velt het model een oordeel over wetgeving. Een lichter model verslechtert precies dat oordeel; "
            "kies alleen iets anders na een meting.")

#: De volgorde is die van de beheertab: per groep, de groepen in deze volgorde.
ROLLEN: tuple[Modelrol, ...] = (
    Modelrol("centraal", "Centrale agent", "Gesprek",
             "Beantwoordt een vraag zelf en zet voor groter werk subagents in.", _OORDEEL),
    Modelrol("supervisor", "Router", "Gesprek",
             "Kiest per vraag de route en de specialist. Kort werk; het antwoord wordt daarna in code gecontroleerd."),
    Modelrol("antwoord", "Specialisten", "Gesprek",
             "Definitie, duiding en algemeen: het antwoord met bronnen uit de kennisgraaf.", _OORDEEL),
    Modelrol("subagent", "Subagents", "Gesprek",
             "Werken één opdracht van de centrale agent uit en leveren een rapport."),
    Modelrol("stukcontrole", "Controle per stuk", "Gesprek",
             "Toetst elk stuk uit het rapport van een subagent aan de bron."),
    Modelrol("ophaal", "Bepaling ophalen", "Annoteren",
             "Zoekt met tools de bepaling op die geannoteerd wordt.",
             "Kiest dit model de verkeerde bepaling, dan is alles daarna brongetrouw én verkeerd. Kies alleen iets "
             "anders na een meting."),
    Modelrol("jas_classifier", "JAS-classifier", "Annoteren",
             "Kiest de JAS-klasse voor elke kandidaat.", _OORDEEL),
    Modelrol("jas_reviewer", "JAS-reviewer", "Annoteren",
             "Beoordeelt de twijfelgevallen van de classifier opnieuw.", _OORDEEL),
    Modelrol("bepaling_toelichting", "Toelichting bij een bepaling", "Annoteren",
             "Schrijft een korte toelichting bij een opgehaalde bepaling."),
    Modelrol("intake", "Werkgebied samenstellen", "Werkgebied",
             "Stelt de velden van een werkgebied voor in de vraagkaarten."),
    Modelrol("deelvragen_voorstel", "Deelvragen voorstellen", "Werkgebied",
             "Stelt de deelvragen bij een analysevraag voor."),
    Modelrol("deelvraag_verbeter", "Deelvraag verbeteren", "Werkgebied",
             "Maakt een bestaande deelvraag scherper."),
    Modelrol("begrip_kaart", "Begrip uitwerken", "Begrippen",
             "Werkt een begripskaart uit: definitie, betekenisverschil en voorbeelden."),
    Modelrol("kaartactie", "Kaartactie", "Begrippen",
             "Voert één actie op een begripskaart uit, vanuit het gesprek."),
    Modelrol("begrip_vergelijk", "Begrippen vergelijken", "Begrippen",
             "Vergelijkt begrippen bij het voorstellen van betekenisgroepen."),
)

NAMEN: tuple[str, ...] = tuple(r.naam for r in ROLLEN)
PER_NAAM: dict[str, Modelrol] = {r.naam: r for r in ROLLEN}


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
