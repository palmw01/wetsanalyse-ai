"""De werkgebied-worker: Lex stelt met de analist een werkgebied samen (activiteit 1).

Eén beurt is één stap van de intake (`agent/werkgebied_intake.py`): de klik op een kaartje verwerken,
het volgende kaartje voorbereiden – voorstellen uit de graaf en, waar het helpt, een modelaanroep,
altijd met het hele dossier, en opnieuw zodra dat veranderde – en het uitsturen als `vraagkaart`-event naast een korte zin. Bij *Aanmaken* stuurt de
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
    "aanleiding": "Eerst waarom we analyseren: de aanleiding.",
    "context": "En de situatie eromheen.",
    "doel": "Wat moet de analyse opleveren?",
    "analysevraag": "Dan de vraag die het werkgebied moet beantwoorden.",
    "praktijkvoorbeeld": "Een voorbeeld uit de praktijk helpt om scherp te krijgen wat erbij hoort.",
    "deelvragen": "Nu maken we de analysevraag concreet.",
    "buiten": "Is er iets dat je bewust buiten het werkgebied laat?",
    "regelingen": "Nu de bronnen: om welke wet- en regelgeving gaat het?",
    "bepalingen": "Nu per deelvraag de bepalingen die erbij horen.",
    "samenvatting": "Dit is het werkgebied zoals we het hebben samengesteld.",
}


def _zin(intake: dict[str, Any]) -> str:
    deel = int(intake.get("deel") or 0)
    if intake["stap"] == "bepalingen" and deel:
        return f"Dan deelvraag {deel + 1}."
    if intake["stap"] == "bepalingen" and wi.deelvraagteksten(intake.get("antwoorden") or {}) == [None]:
        return "Nu de bepalingen die bij de analysevraag horen."
    return _ZIN[intake["stap"]]


def _model(b, intake: dict[str, Any], writer) -> dict[str, Any]:
    """De voorstellen van het model bij het dossier zoals het nu is: één aanroep per stand van het
    dossier, gedeeld door de stappen die hem nodig hebben."""
    h = wi.dossier_hash(intake)
    if intake.get("model_hash") == h:
        return intake
    _stap(writer, "Lex", "stelt voorstellen op bij wat er ligt")
    return {**intake, "model": wi.stel_voor(b.llm, b.model_router, intake), "model_hash": h}


def _met(intake: dict[str, Any], sleutel: str, stap: str, waarde: Any) -> dict[str, Any]:
    return {**intake, sleutel: {**(intake.get(sleutel) or {}), stap: waarde}}


def _deelvragen(b, intake: dict[str, Any], writer) -> dict[str, Any]:
    """Voorstellen voor deelvragen uit het hele dossier (`agent/deelvragen.py`, op het sterke model). Wat
    de analist al koos van Lex blijft kiesbaar; zijn eigen deelvragen staan in het tekstveld."""
    from .. import deelvragen as dv

    a = intake.get("antwoorden") or {}
    vragen: list[str] = []
    if not (a.get("analysevraag") or "").strip():
        intake = _met(intake, "meldingen", "deelvragen",
                      "Zonder analysevraag stel ik geen deelvragen voor; je kunt ze wel zelf toevoegen.")
    else:
        _stap(writer, "Lex", "stelt deelvragen voor bij de analysevraag")
        try:
            vragen = dv.vraag_model(b.llm, b.model, wi.als_werkgebied(intake), {})
        except Exception:  # noqa: BLE001 – een voorstel is een gemak, geen voorwaarde
            logger.warning("intake: geen deelvragen van het model", exc_info=True)
            intake = _met(intake, "meldingen", "deelvragen",
                          "Ik kon nu geen deelvragen voorstellen; voeg ze zelf toe of sla deze stap over.")
    opties = wi.tekst_opties(vragen, "voorstel van Lex")
    nieuw = {wi.normaliseer(v) for v in vragen}
    eerder = [d["vraag"] for d in a.get("deelvragen") or []
              if d["herkomst"] == "lex" and wi.normaliseer(d["vraag"]) not in nieuw]
    return _met(intake, "voorstellen", "deelvragen", wi.tekst_opties(eerder, "eerder gekozen") + opties)


def _regelingen(b, intake: dict[str, Any], zoek: str, writer, *, per_deelvraag: bool) -> dict[str, Any]:
    """Regelingen uit de graaf, gezocht met wat er ligt: het onderwerp, de deelvragen, de regelingen die
    het dossier bij naam noemt, en zonder wat buiten het werkgebied valt."""
    from ..bronnen_vinden import onderwerp_van_deelvraag
    from ..werkgebied_context import uitsluitstammen

    a = intake.get("antwoorden") or {}
    wg = wi.als_werkgebied(intake)
    # Waar een regeling bij naam genoemd kan zijn – niet in wat erbuiten valt.
    genoemd_in = " ".join([intake.get("eerste_zin", ""), *(wg[k] for k in ("naam", "aanleiding", "context", "doel",
                                                                        "analysevraag", "praktijkvoorbeeld")),
                           *(d["vraag"] for d in wg["deelvragen"])])
    deelvragen = [(d["vraag"], o) for d in wg["deelvragen"] if (o := onderwerp_van_deelvraag(d["vraag"]))] \
        if per_deelvraag else []
    _stap(writer, "Lex", f"zoekt regelingen bij: {zoek[:80]}" + (
        f" en {len(deelvragen)} {'deelvraag' if len(deelvragen) == 1 else 'deelvragen'}" if deelvragen else "")
          if zoek or deelvragen else "zoekt de genoemde regelingen")
    try:
        opties, voorop, weg = wi.regeling_opties(b.graph, zoek, genoemd_in=genoemd_in, deelvragen=deelvragen,
                                                 buiten=uitsluitstammen(a.get("buiten", "")))
    except Exception:  # noqa: BLE001 – geen graaf: dan alleen eigen tekst en "weet ik niet"
        logger.warning("intake: regelingen niet opgehaald", exc_info=True)
        opties, voorop, weg = [], [], []
    # Wat de analist al koos, blijft te kiezen: een nieuwe zoekronde vervangt het niet stil.
    gevonden = {o["waarde"] for o in opties}
    opties = [{"label": r["label"], "waarde": r["bwb_id"], "bron": {"bwb_id": r["bwb_id"]}, "omschrijving": "eerder gekozen"}
              for r in a.get("regelingen") or [] if r["bwb_id"] not in gevonden] + opties
    melding = "" if opties else (
        f"Ik vond geen regeling bij ‘{zoek}’." if zoek else "Ik kon nog geen regeling voorstellen.")
    if weg:
        melding = (f"{melding} Ik liet {len(weg)} {'deel' if len(weg) == 1 else 'delen'} weg die raken aan wat buiten "
                   f"het werkgebied valt ({', '.join(weg[:3])}{' …' if len(weg) > 3 else ''}).").strip()
    intake = _met(intake, "meldingen", "regelingen", melding)
    return _met(_met(intake, "voorstellen", "regelingen", opties), "vooringevuld", "regelingen", voorop)


def _bepalingen(b, intake: dict[str, Any], writer) -> dict[str, Any]:
    """De bepalingen bij de deelvraag van dit kaartje (`bronnen_vinden.bepaling_opties`, zonder model),
    binnen de gekozen regelingen. Wat de analist hier al koos blijft kiesbaar; wat raakt aan wat buiten
    het werkgebied valt, staat onderaan en wordt niet aangevinkt."""
    from ..bronnen_vinden import bepaling_opties
    from ..werkgebied_context import uitsluitstammen

    a = intake.get("antwoorden") or {}
    sleutel = wi.kaartsleutel(intake)
    deel = int(intake.get("deel") or 0)
    vraag = wi.deelvraagteksten(a)[deel] if deel < len(wi.deelvraagteksten(a)) else None
    _stap(writer, "Lex", f"zoekt bepalingen bij deelvraag {deel + 1}" if vraag else "zoekt bepalingen bij de analysevraag")
    gevonden = bepaling_opties(b.graph, regelingen=[r["bwb_id"] for r in a.get("regelingen") or []],
                               deelvraag=vraag, dossier=wi.als_werkgebied(intake),
                               buiten=uitsluitstammen(a.get("buiten", "")), limit=wi.MAX_BEPALINGEN)
    opties = [{"label": o["label"], "waarde": o["bron_iri"], "bron": {"bwb_id": o["bwb_id"], "iri": o["bron_iri"]},
               "omschrijving": o["omschrijving"]} for o in gevonden]
    al = {o["waarde"] for o in opties}
    x = (a.get("bepalingen") or {}).get(wi.deel_sleutel(vraag)) or {}
    eerder = [{"label": o["label"], "waarde": o["bron_iri"], "bron": {"bwb_id": o.get("bwb_id", ""), "iri": o["bron_iri"]},
               "omschrijving": "eerder gekozen"} for o in x.get("bronnen") or [] if o["bron_iri"] not in al]
    buiten = sum(1 for o in gevonden if o["buiten"])
    if not gevonden:
        melding = ("Ik vond hierbij geen bepalingen in de gekozen regeling(en); noem ze zelf of kies "
                   "‘Weet ik (nog) niet’.")
    elif buiten:
        melding = (f"Onderaan {'staat 1 bepaling die raakt' if buiten == 1 else f'staan {buiten} bepalingen die raken'} "
                   "aan wat buiten het werkgebied valt; ik heb ze niet aangevinkt.")
    else:
        melding = ""
    return _met(_met(intake, "meldingen", sleutel, melding), "voorstellen", sleutel, eerder + opties)


def _bereid_voor(b, intake: dict[str, Any], writer) -> dict[str, Any]:
    """Wat het kaartje van de huidige stap nodig heeft – opnieuw zodra het dossier veranderde, anders
    niet (terugbladeren zonder iets te wijzigen kost geen aanroep)."""
    stap, sleutel = intake["stap"], wi.kaartsleutel(intake)
    # De keuzes op de bepalingen-kaartjes veranderen de zoekopdracht van een ander kaartje niet.
    h = wi.dossier_hash(intake, zonder=("bepalingen",) if stap == "bepalingen" else ())
    if stap not in wi.STAPPEN or (intake.get("voorbereid") or {}).get(sleutel) == h:
        return intake
    intake = _met(_met(intake, "voorbereid", sleutel, h), "meldingen", sleutel, "")
    a = intake.get("antwoorden") or {}
    if stap == "naam" and wi.inhoud(intake.get("eerste_zin", "")):
        intake = _model(b, intake, writer)
        if (namen := intake["model"].get("naam")):
            intake = _met(_met(intake, "voorstellen", "naam", wi.tekst_opties(namen)), "vooringevuld", "naam", namen[:1])
    elif stap in ("aanleiding", "doel"):
        intake = _model(b, intake, writer)
        intake = _met(intake, "vooringevuld", stap, list(intake["model"].get(stap) or []))
    elif stap == "analysevraag":
        intake = _model(b, intake, writer)
        intake = _met(intake, "voorstellen", "analysevraag", wi.tekst_opties(intake["model"].get("analysevraag") or []))
    elif stap == "deelvragen":
        intake = _deelvragen(b, intake, writer)
    elif stap == "regelingen":
        intake = _model(b, intake, writer)
        intake = _regelingen(b, intake, intake["model"].get("onderwerp") or a.get("naam", ""), writer, per_deelvraag=True)
    elif stap == "bepalingen":
        intake = _bepalingen(b, intake, writer)
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
        uitkomst = "verder"
    else:
        if not actie:
            # De supervisor herkende een getypt antwoord op het open kaartje.
            actie = {"intake_id": intake.get("id"), "stap": intake.get("stap"), "deel": intake.get("deel", 0),
                     "actie": "antwoord", "tekst": vraag}
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
        intake = _regelingen(b, intake, intake.get("zoekterm", ""), writer, per_deelvraag=False)
        zinnen.append(f"Dit vond ik bij ‘{intake.get('zoekterm', '')}’." if intake["voorstellen"]["regelingen"]
                      else "Probeer een andere naam of een ander onderwerp, of kies ‘Weet ik (nog) niet’.")

    if uitkomst != "zoek":
        intake = _bereid_voor(b, intake, writer)
        if uitkomst == "verder":
            zinnen.append(_zin(intake))
    kaart = wi.kaart(intake)
    tekst = " ".join(zinnen)
    writer({"type": "token", "content": tekst})
    writer({"type": "vraagkaart", "vraagkaart": kaart})
    return {"intake": intake, "answer": tekst,
            "messages": [{"role": "assistant", "content": f"{tekst}\n\n[Vraag: {kaart['vraag']}]".strip()}]}
