"""De routeringstabel (ADR-010, ADR-014 §7): elke vaste weg die de supervisor zonder model kiest.

Een route is een **ingang**: een herkenner in code die één onderdeel kiest, vóór of na de modelstap van de supervisor.
De volgorde staat in `nodes/supervisie._kies`, omdat dezelfde herkenner op meer plekken voorkomt (een eerste vraag, een
vervolgvraag met de herschreven vraag, met en zonder werkgebied). Deze tabel zegt wát er is. `tests/test_catalogus.py`
houdt tabel en code gelijk:
- elke herkenner hier bestaat en wordt in `supervisie.py` aangeroepen;
- elke herkenner die `supervisie.py` importeert of definieert (`is_…`, `lees_…`, `wijst_…`, `_heeft_…` en de helpers
  `_lijst`, `_bron_uit`, `_te_lezen`, `_doorvraag`, `_buiten_graaf_melding`) staat hier;
- elk doel staat in de catalogus, en een route kiest precies één doel.

Een nieuwe route is: een herkenner, een tak in `_kies`, een rij hier en de rijen in `eval/golden_routering.jsonl`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Moment = Literal["vóór het model", "na het model", "vóór en na het model"]


@dataclass(frozen=True)
class Route:
    naam: str
    label: str
    #: `module:functie`, opgelost in de test; geen import hier (de herkenners importeren zwaar, en supervisie importeert
    #: ze al).
    herkenner: str
    #: Het onderdeel dat de route kiest: een workflow of een agent uit de catalogus.
    doel: str
    moment: Moment
    doel_zin: str


ROUTES: tuple[Route, ...] = (
    Route("annotatie_doel", "Een aangewezen bepaling annoteren", "agent.doel:_heeft_opgegeven_doel",
          "workflow/annotatieketen", "vóór het model",
          "De werkplek gaf de bepaling mee: geen ophaal-agent, de keten annoteert precies die bepaling."),
    Route("werkgebied_samenstellen", "Een werkgebied samenstellen", "agent.werkgebied_intake:is_werkgebiedvraag",
          "workflow/werkgebied_intake", "vóór het model", "Vraagkaarten in de volgorde van de methode."),
    Route("bronselectie", "De bronnen per deelvraag bepalen", "agent.bronselectie:is_bronselectievraag",
          "workflow/bronselectie", "vóór het model", "Binnen een werkgebied: de deelvragen één voor één."),
    Route("dekking", "De dekking van de deelvragen", "agent.agents.deelvragen:is_dekkingsvraag",
          "agent/deelvragen", "vóór en na het model", "De taak dekking van de deelvragen-agent, zonder model."),
    Route("annotaties_lezen", "Een vraag over bestaande annotaties", "agent.tools.annotatie_tools:is_leesvraag",
          "specialist/annotaties_lezen", "vóór en na het model",
          "Eerst zoekt de code in de opgeslagen annotaties, dan formuleert de specialist."),
    Route("begrippen_lezen", "Een vraag over vastgelegde begrippen", "agent.tools.begrip_tools:is_begrip_leesvraag",
          "specialist/begrippen_lezen", "vóór en na het model",
          "Eerst zoekt de code in de begrippen, dan formuleert de specialist."),
    Route("overzicht", "Welke artikelen gaan over …", "agent.overzicht:is_overzichtsvraag",
          "workflow/overzicht", "vóór en na het model", "Overzicht en tekst uit de graaf, zonder model."),
    Route("bepaling", "De tekst van één bepaling", "agent.bepaling_workflow:lees",
          "workflow/bepaling", "vóór en na het model",
          "De tekst uit de graaf; het model schrijft alleen de toelichting."),
    Route("bepaling_buiten_graaf", "De tekst van een bepaling buiten de graaf", "agent.bepaling_workflow:lees_buiten",
          "workflow/bepaling", "vóór en na het model",
          "Live gelezen bij overheid.nl, met dezelfde workflow."),
    Route("genoemd_stuk", "Een stuk dat de vraag bij id noemt", "agent.nodes.supervisie:_te_lezen",
          "workflow/bron_lezen", "vóór het model", "De leestool van de connector in code, vóór de specialist."),
    Route("stuk_aangewezen", "De vraag wijst een stuk aan", "agent.bepaling_workflow:wijst_stuk_aan",
          "workflow/bron_lezen", "vóór het model", "Een stuk gaat voor op de bepalingsroute."),
    Route("lijstvraag", "Een lijst- of telvraag over een bron naast de wet", "agent.nodes.supervisie:_lijst",
          "workflow/bron_lijst", "vóór en na het model", "De zoektool in code, het blok stukken, zonder model."),
    Route("bron_uit", "Een vraag over een bron die uit staat", "agent.nodes.supervisie:_bron_uit",
          "workflow/vaste_melding", "vóór en na het model", "Een melding met de reden en wie hem aanzet."),
    Route("buiten_graaf", "Een regeling buiten de graaf", "agent.nodes.supervisie:_buiten_graaf_melding",
          "workflow/vaste_melding", "vóór het model", "Een melding of een keuzevraag, zonder model."),
    Route("meerdere_artikelen", "Annoteren van meer artikelen tegelijk", "agent.aanwijzing:lees_aanwijzing",
          "workflow/vaste_melding", "na het model", "Eén artikel per annotatievraag: een melding, zonder model."),
    Route("doorvraag", "Een doorvraag op het vorige antwoord", "agent.nodes.supervisie:_doorvraag",
          "workflow/vaste_melding", "vóór het model", "De keuzevraag van het vorige antwoord opnieuw, zonder model."),
)
