"""De werkgebied-worker: Lex stelt met de analist een werkgebied samen (activiteit 1).

Eén beurt is één stap van de intake (`agent/werkgebied_intake.py`): de klik op een kaartje verwerken,
het volgende kaartje voorbereiden – voorstellen uit de graaf en, waar het helpt, één kleine
modelaanroep – en het uitsturen als `vraagkaart`-event naast een korte zin. Bij *Aanmaken* stuurt de
node alleen een `werkgebied_aanmaken`-event: het schrijven doet de beurt-driver, aan het eind van de
beurt, zoals bij een annotatie.

Geen verify/finalize: er wordt niets over wetgeving beweerd, alleen gevraagd en voorgesteld.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from .. import werkgebied_intake as wi
from ..narratie import _stap
from ..state import State

logger = logging.getLogger("graph_qa.werkgebied")

_ZIN = {
    "naam": "Laten we het werkgebied samen bepalen; ik stel je een paar korte vragen.",
    "analysevraag": "Dan de vraag die het werkgebied moet beantwoorden.",
    "regelingen": "Nu de afbakening: om welke wet- en regelgeving gaat het?",
    "onderdelen": "Welke delen daarvan horen erbij?",
    "buiten": "Is er iets dat je bewust buiten het werkgebied laat?",
    "samenvatting": "Dit is het werkgebied zoals we het hebben samengesteld.",
}


def _voorstellen(b, intake: dict[str, Any], writer) -> dict[str, Any]:
    """Het model vraagt om voorstellen (naam, analysevraag, onderwerp) en neemt ze op in de intake."""
    _stap(writer, "Lex", "stelt voorstellen op")
    vs = wi.stel_voor(b.llm, b.model_router, intake)
    voorstellen = dict(intake.get("voorstellen") or {})
    vooringevuld = dict(intake.get("vooringevuld") or {})
    a = intake.get("antwoorden") or {}
    if vs["naam"] and "naam" not in a:
        voorstellen["naam"] = wi.tekst_opties(vs["naam"])
        vooringevuld["naam"] = vs["naam"][:1]
    if vs["analysevraag"] and "analysevraag" not in a:
        voorstellen["analysevraag"] = wi.tekst_opties(vs["analysevraag"])
    return {**intake, "voorstellen": voorstellen, "vooringevuld": vooringevuld,
            "onderwerp": vs["onderwerp"] or intake.get("onderwerp", "")}


def _regelingen(b, intake: dict[str, Any], zoek: str, writer) -> dict[str, Any]:
    a = intake.get("antwoorden") or {}
    genoemd_in = " ".join([intake.get("eerste_zin", ""), a.get("naam", ""), a.get("analysevraag", "")])
    _stap(writer, "Lex", f"zoekt regelingen bij: {zoek[:80]}" if zoek else "zoekt de genoemde regelingen")
    try:
        opties, delen, voorop = wi.regeling_opties(b.graph, zoek, genoemd_in=genoemd_in)
    except Exception:  # noqa: BLE001 – geen graaf: dan alleen eigen tekst en "weet ik niet"
        logger.warning("intake: regelingen niet opgehaald", exc_info=True)
        opties, delen, voorop = [], {}, []
    melding = "" if opties else (
        f"Ik vond geen regeling bij ‘{zoek}’." if zoek else "Ik kon nog geen regeling voorstellen.")
    return {**intake, "melding": melding,
            "voorstellen": {**intake.get("voorstellen", {}), "regelingen": opties},
            "vooringevuld": {**intake.get("vooringevuld", {}), "regelingen": voorop},
            "delen": {**intake.get("delen", {}), **delen}}


def _bereid_voor(b, intake: dict[str, Any], writer) -> dict[str, Any]:
    """Wat het kaartje van de huidige stap nodig heeft."""
    stap, a = intake["stap"], intake.get("antwoorden") or {}
    intake = {**intake, "melding": ""}
    if stap == "analysevraag" and not intake.get("voorstellen", {}).get("analysevraag") and a.get("naam"):
        intake = _voorstellen(b, intake, writer)
    elif stap == "regelingen":
        if a.get("analysevraag") and not intake.get("onderwerp_uit_vraag"):
            intake = {**_voorstellen(b, intake, writer), "onderwerp_uit_vraag": True}
        intake = _regelingen(b, intake, intake.get("onderwerp") or a.get("naam", ""), writer)
    elif stap == "onderdelen":
        opties = wi.onderdeel_opties(a.get("regelingen") or [], intake.get("delen") or {})
        intake = {**intake, "voorstellen": {**intake.get("voorstellen", {}), "onderdelen": opties}}
    return intake


def werkgebied_intake_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    vraag = state.get("question", "")
    actie = dict(state.get("intake_actie") or {})
    intake = dict(state.get("intake") or {})
    zinnen: list[str] = []

    if not actie and (wi.is_werkgebiedvraag(vraag) or not wi.is_open(intake)):
        intake = wi.nieuwe_intake(vraag)
        _stap(writer, "Lex", "begint met het samenstellen van een werkgebied")
        if wi.is_wetsanalysevraag(vraag):
            zinnen.append(wi.UITLEG)
        if wi.inhoud(vraag):
            intake = _voorstellen(b, intake, writer)
        uitkomst = "verder"
    else:
        if not actie:
            # De supervisor herkende een getypt antwoord op het open kaartje.
            actie = {"intake_id": intake.get("id"), "stap": intake.get("stap"), "actie": "antwoord", "tekst": vraag}
        if not intake.get("id") or actie.get("intake_id") != intake.get("id"):
            tekst = ("Dit kaartje hoort bij een samenstelling die niet meer loopt. Vraag me opnieuw een "
                     "werkgebied samen te stellen om te beginnen.")
            writer({"type": "token", "content": tekst})
            return {"answer": tekst, "messages": [{"role": "assistant", "content": tekst}]}
        intake, uitkomst = wi.verwerk(intake, actie)

    if uitkomst == "afgebroken":
        tekst = "Ik stop met samenstellen; er is geen werkgebied aangemaakt."
        writer({"type": "token", "content": tekst})
        return {"intake": intake, "answer": tekst, "messages": [{"role": "assistant", "content": tekst}]}
    if uitkomst == "aanmaken":
        _stap(writer, "Lex", "maakt het werkgebied aan")
        writer({"type": "werkgebied_aanmaken", **wi.aanmaakverzoek(intake)})
        # De tekst schrijft de beurt-driver, die weet wat de api ervan maakte.
        return {"intake": intake, "answer": "",
                "messages": [{"role": "assistant",
                              "content": f"Werkgebied ‘{intake['antwoorden'].get('naam', '')}’ aangemaakt."}]}
    if uitkomst == "verouderd":
        if intake.get("stap") == "klaar":
            tekst = ("Deze samenstelling is al afgerond." if not intake.get("afgebroken") else
                     "Deze samenstelling is afgebroken. Vraag me opnieuw een werkgebied samen te stellen.")
            writer({"type": "token", "content": tekst})
            return {"intake": intake, "answer": tekst, "messages": [{"role": "assistant", "content": tekst}]}
        zinnen.append("Dat kaartje is al beantwoord. Hier waren we gebleven:")
    elif uitkomst == "naam_nodig":
        zinnen.append("Een werkgebied heeft een naam nodig; die kan ik niet overslaan.")
    elif uitkomst == "zoek":
        intake = _regelingen(b, intake, intake.get("zoekterm", ""), writer)
        zinnen.append(f"Dit vond ik bij ‘{intake.get('zoekterm', '')}’." if intake["voorstellen"]["regelingen"]
                      else "Probeer een andere naam of een ander onderwerp, of kies ‘Weet ik (nog) niet’.")

    if uitkomst != "zoek":
        intake = _bereid_voor(b, intake, writer)
        if uitkomst == "verder":
            zinnen.append(_ZIN[intake["stap"]])
    kaart = wi.kaart(intake)
    tekst = " ".join(zinnen)
    writer({"type": "token", "content": tekst})
    writer({"type": "vraagkaart", "vraagkaart": kaart})
    return {"intake": intake, "answer": tekst,
            "messages": [{"role": "assistant", "content": f"{tekst}\n\n[Vraag: {kaart['vraag']}]".strip()}]}
