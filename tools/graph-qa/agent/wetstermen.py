"""De deelvraag in de taal van de wet (`Zoekprofiel.wetstermen`, een proef, standaard uit).

Waarom. De meting `bronselectie-2026-11-17-drie-rondes` liet 36 van de 172 nodige bepalingen zien die de zoekmachine
helemaal niet vindt: de deelvraag gebruikt andere woorden dan de wet ("geld bijvragen" waar de wet over navordering
spreekt). Het offline onderzoek `bronselectie-2026-11-17-signalen` mat dat vertalen naar de wetsterm de grootste knop is
(de gebeurtenis als wetsterm, recall @30 0,39 → 0,59; een vertaling per deelvraag als bovengrens 0,68).

Hoe. Eén kleine modelstap per deelvraag (`Rol.WETSTERMEN`) krijgt de deelvraag, het dossier en de namen van de regelingen
in het zoekbereik, en geeft met één strict tool de woorden waarmee de wet het onderwerp benoemt. Het model typt alleen
zoektermen: geen bepaling, geen iri, geen tekst. De code maakt er inhoudswoorden van (`zoektermen`), laat vulwoorden en
woorden die al in de deelvraag staan weg, en houdt alleen wat in de regelingen van het zoekbereik voorkomt (de
documentfrequentie, `deelvraag_zoeken.q_aantal`): een term die er niet staat, vindt niets, en zo is de wet zelf de toets
dat het een wetsterm is. Daarna zoekt de bestaande index op die termen naast de woorden van de deelvraag
(`deelvraag_zoeken.kandidatenpool(wetstermen=)`), en raakt een kandidaat uit de pool rond de gebeurtenis ze ook
(`zoekvragen.opties_bij_deelvraag(wetstermen=)`). Faalt de stap, dan zoekt de code zoals zonder de vlag."""
from __future__ import annotations

import logging
from typing import Any

from .llm_stap import Rol, vraag_tool
from .ports import GraphPort

logger = logging.getLogger(__name__)

#: Hoeveel termen het model mag noemen (de code kapt af), en hoeveel woorden er na de toets overblijven.
MAX_GENOEMD = 8
MAX_WETSTERMEN = 6
MAX_TOKENS = 512

SYSTEEM = (
    "Je helpt een jurist bij de bronselectie van een wetsanalyse. Een zoekmachine zoekt op woorden in de tekst van de "
    "regelingen. Een deelvraag gebruikt vaak andere woorden dan de wet: de analist schrijft 'de huur opzeggen', de wet "
    "spreekt van 'opzegging' en 'huurovereenkomst'. Geef de woorden waarmee de genoemde regelingen zelf het onderwerp "
    "van de deelvraag benoemen: de juridische termen, begrippen en handelingen zoals ze in wettekst staan. Ook de "
    "termen voor wat er in de wet direct mee samenhangt (de beslissing, de termijn, de sanctie, het rechtsmiddel) als "
    "de deelvraag erom vraagt. Geen artikelnummers, geen namen van regelingen, geen uitleg en geen woorden die al in "
    "de deelvraag staan. Eén term per item, één of twee woorden. Hoogstens acht; minder mag.")


def prompt(vraag: str, dossier: dict[str, Any], regelingnamen: list[str]) -> str:
    velden = [("Werkgebied", dossier.get("naam")), ("Analysevraag", dossier.get("analysevraag")),
              ("Praktijkvoorbeeld", dossier.get("praktijkvoorbeeld")), ("Gebeurtenis", dossier.get("gebeurtenis")),
              ("Buiten de afbakening", dossier.get("afbakening") or dossier.get("buiten"))]
    kop = "\n".join(f"{n}: {' '.join(str(w).split())}" for n, w in velden if w)
    regelingen = "\n".join(f"- {n}" for n in regelingnamen)
    delen = [kop, f"Regelingen in het zoekbereik:\n{regelingen}" if regelingen else "", f"Deelvraag: {vraag}",
             "Geef met de tool de zoektermen in de taal van deze regelingen."]
    return "\n\n".join(d for d in delen if d)


def schema() -> dict[str, Any]:
    return {"name": "geef_wetstermen", "description": "Zoektermen in de taal van de wet, één of twee woorden per item.",
            "strict": True,
            "input_schema": {"type": "object", "additionalProperties": False, "required": ["termen"], "properties": {
                "termen": {"type": "array", "items": {"type": "string"}}}}}


def _haal(invoer: dict[str, Any]) -> list[str] | None:
    termen = invoer.get("termen")
    return [t for t in termen if isinstance(t, str)] if isinstance(termen, list) else None


def vraag(llm: Any, model: str, vraag_: str, dossier: dict[str, Any], regelingnamen: list[str],
          meting: dict[str, Any] | None = None) -> list[str] | None:
    """De termen zoals het model ze noemt, hoogstens `MAX_GENOEMD`. `None` als het model geen bruikbaar antwoord gaf of
    de aanroep faalde."""
    verzoek = dict(model=model, max_tokens=MAX_TOKENS, system=SYSTEEM, tools=[schema()],
                   tool_choice={"type": "tool", "name": "geef_wetstermen"},
                   messages=[{"role": "user", "content": prompt(vraag_, dossier, regelingnamen)}])
    try:
        uit = vraag_tool(llm, Rol.WETSTERMEN, verzoek=verzoek, pogingen=1, meting=meting, haal=_haal)
    except Exception:  # noqa: BLE001 – een vertaling die faalt, kost alleen de extra termen
        logger.warning("wetstermen mislukt", exc_info=True, extra={"categorie": "technisch"})
        return None
    return None if uit.waarde is None else uit.waarde[:MAX_GENOEMD]


def als_zoektermen(genoemd: list[str], vraag_: str) -> list[str]:
    """De inhoudswoorden van wat het model noemde, in zijn volgorde, zonder vulwoorden en zonder de woorden die de
    deelvraag zelf al zoekt."""
    from .zoektermen import zoektermen
    from .zoekvragen import LEGE_WOORDEN, METHODEWOORDEN

    eigen = set(zoektermen(vraag_))
    uit: list[str] = []
    for t in genoemd:
        for w in zoektermen(t):
            if w not in eigen and w not in LEGE_WOORDEN and w not in METHODEWOORDEN and w not in uit:
                uit.append(w)
    return uit


def in_regelingen(graph: GraphPort, termen: list[str], regelingen: list[str]) -> list[str]:
    """De termen die in de regelingen voorkomen, in hun volgorde, hoogstens `MAX_WETSTERMEN`. Hapert de graaf, dan geen
    termen: een storing kost de vertaling, niet het zoeken."""
    from .bepaling_namen import rijen
    from .deelvraag_zoeken import STANDAARD_PROFIEL, _term_lucene, q_aantal

    uit: list[str] = []
    try:
        for w in termen:
            if len(uit) >= MAX_WETSTERMEN:
                break
            r = rijen(graph, q_aantal("tekst:" + _term_lucene(w, "", STANDAARD_PROFIEL), [b for b in regelingen if b]))
            if r and int(r[0].get("aantal") or 0) > 0:
                uit.append(w)
    except Exception:  # noqa: BLE001
        logger.warning("wetstermen niet getoetst", extra={"categorie": "technisch"}, exc_info=True)
        return []
    return uit


def wetstermen(graph: GraphPort, llm: Any, model: str, vraag_: str, dossier: dict[str, Any], regelingen: list[str],
               meting: dict[str, Any] | None = None) -> list[str]:
    """De zoektermen in de taal van de wet bij één deelvraag: de modelstap, dan de toets in code. Een lege lijst als er
    niets bruikbaars is."""
    from .zoekvragen import _regelingnamen

    if not (vraag_ or "").strip():
        return []
    namen = _regelingnamen(graph, [b for b in regelingen if b])
    genoemd = vraag(llm, model, vraag_, dossier, [namen.get(b, b) for b in regelingen if b], meting)
    if not genoemd:
        return []
    termen = in_regelingen(graph, als_zoektermen(genoemd, vraag_), regelingen)
    logger.info("wetstermen", extra={"categorie": "functioneel", "genoemd": len(genoemd), "termen": len(termen)})
    return termen
