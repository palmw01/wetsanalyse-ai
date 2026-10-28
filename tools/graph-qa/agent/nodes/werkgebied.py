"""De werkgebied-worker: Lex stelt met de analist een werkgebied samen (activiteit 1).

Eén beurt is één stap van de intake (`agent/werkgebied_intake.py`): de klik op een kaartje verwerken,
het volgende kaartje voorbereiden – voorstellen uit de graaf en, waar het helpt, een modelaanroep,
altijd met het hele dossier, en opnieuw zodra dat veranderde – en het uitsturen als `vraagkaart`-event naast een korte zin. Bij *Aanmaken* stuurt de
node alleen een `werkgebied_aanmaken`-event: het schrijven doet de beurt-driver, aan het eind van de
beurt, zoals bij een annotatie.

**Aanvullen** (`State.intake_modus == "aanvullen"`, door de supervisor gezet): het werkgebied van het
gesprek komt bij de api vandaan, de velden uit de vraag (`dossiervelden_in`) of anders de lege, en daarna
dezelfde kaartjes. Bij *Opslaan* stuurt de node een `werkgebied_wijzigen`-event; ook dat schrijft de
beurt-driver. Een praktijkvoorbeeld verzint Lex niet: die stap heeft geen voorstel en geen modelaanroep.

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


# Bij het aanvullen: dezelfde zinnen, behalve waar het samenstellen een begin of een einde aankondigt.
_ZIN_AANVULLEN = {
    "naam": "Eerst de naam.",
    "thema": "Dan het thema. Ik leid het af uit de rechtsgebieden van de bronnen.",
    "samenvatting": "Dit verandert er in het dossier.",
}


def _zin(intake: dict[str, Any]) -> str:
    if wi.is_aanvullen(intake):
        return _ZIN_AANVULLEN.get(intake["stap"]) or _ZIN[intake["stap"]]
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


def _eigen_bepalingen(b, intake: dict[str, Any], tekst: str, writer) -> tuple[list[dict[str, Any]], str]:
    """Wat de analist zelf op een bepalingenkaartje typte ("artikel 9 lid 1 en 5 Invorderingswet 1990"): per
    bepaling getoetst in de graaf. (bepalingen, "") als alles gevonden is; anders ([], een vraag) en blijft het
    kaartje staan. De regeling komt uit de tekst (naam of afkorting), anders uit de intake als die er één heeft –
    dezelfde regels als de bronselectie (`bronselectie.bepalingen_uit_tekst`)."""
    from ..bronnen_vinden import bepaling_in_graaf
    from ..bronselectie import bepalingen_uit_tekst
    from ..overzicht import regelingen_in_vraag
    from ..regelingnamen import regelingnamen

    gekozen = [r["bwb_id"] for r in (intake.get("antwoorden") or {}).get("regelingen") or []]
    _stap(writer, "Lex", "zoekt de bepaling die je noemde")
    try:
        verzoeken = bepalingen_uit_tekst(tekst, lambda t: regelingen_in_vraag(b.graph, t), gekozen)
        if isinstance(verzoeken, str):
            return [], f"{verzoeken} Of vink een voorstel aan."
        if not verzoeken:
            return [], ("Ik zie geen artikel in je tekst. Noem de bepaling, bijvoorbeeld ‘artikel 9 lid 2 "
                        "Invorderingswet 1990’, of vink een voorstel aan.")
        gevonden, mis = [], []
        for v in verzoeken:
            x = bepaling_in_graaf(b.graph, v["bwb_id"], v["artikel"], v.get("lid", ""))
            (gevonden if x else mis).append(x or v)
        if not mis:
            return gevonden, ""
        namen = regelingnamen(b.graph, {v["bwb_id"] for v in mis} | set(gekozen))
        zinnen = []
        for v in mis:
            wat = f"Artikel {v['artikel']}" + (f", lid {v['lid']}" if v.get("lid") else "")
            elders = [namen.get(r, r) for r in gekozen if r != v["bwb_id"]
                      and bepaling_in_graaf(b.graph, r, v["artikel"], v.get("lid", ""))]
            zinnen.append(f"{wat} staat niet in {namen.get(v['bwb_id'], v['bwb_id'])}"
                          + (f"; wel in {' en '.join(elders)} – bedoel je die?" if elders else "."))
        return [], " ".join(zinnen) + " Pas je tekst aan, of vink een voorstel aan."
    except Exception:  # noqa: BLE001 – een haperende graaf: niets aannemen, de analist kan het opnieuw proberen
        logger.warning("intake: getypte bepaling niet te toetsen", exc_info=True)
        return [], "Ik kon de bepaling die je noemde nu niet opzoeken; probeer het zo opnieuw, of vink een voorstel aan."


def _thema(b, intake: dict[str, Any], writer, user_id: str) -> dict[str, Any]:
    """Het kaartje van het thema (spoor I7): de voorstellen van de api (zonder model, uit de rechtsgebieden van de
    bronnen), plus het huidige thema; het eerste voorstel staat aangevinkt als er nog geen thema is."""
    from ..agents.uitvoering import draai
    from .agent_taak import _maak_api

    async def haal(_stuur):
        api = _maak_api(b, user_id)
        try:
            return await api.haal_thema_voorstel(intake["werkgebied_id"])
        finally:
            if (aclose := getattr(api, "aclose", None)) is not None:
                await aclose()

    try:
        voorstel = draai(haal, loop=b.loop, schrijf=writer) if b.settings.legt_zelf_vast else {}
    except Exception:  # noqa: BLE001 – zonder voorstel blijft het huidige thema te kiezen
        logger.warning("aanvullen: thema-voorstel niet opgehaald", extra={"categorie": "technisch"}, exc_info=True)
        voorstel = {}
    gebieden = ", ".join(voorstel.get("rechtsgebieden") or [])
    opties = [{"label": t["label"], "waarde": t["thema"], "bron": {},
               "omschrijving": f"voorstel van Lex, uit {gebieden}" if gebieden else "voorstel van Lex"}
              for t in voorstel.get("voorstel") or []][:3]
    huidig = ((intake.get("antwoorden") or {}).get("thema") or {})
    if huidig.get("uri") and huidig["uri"] not in {o["waarde"] for o in opties}:
        opties.append({"label": huidig.get("label") or huidig["uri"], "waarde": huidig["uri"], "bron": {},
                       "omschrijving": "het huidige thema"})
    melding = "" if opties else "Ik vond geen thema in de rechtsgebieden van de bronnen; kies het in Gegevens bewerken."
    intake = _met(_met(intake, "voorstellen", "thema", opties), "meldingen", "thema", melding)
    if not huidig.get("uri") and opties:
        intake = _met(intake, "vooringevuld", "thema", [opties[0]["waarde"]])
    return intake


def _bereid_voor(b, intake: dict[str, Any], writer, user_id: str = "") -> dict[str, Any]:
    """Wat het kaartje van de huidige stap nodig heeft – opnieuw zodra het dossier veranderde, anders
    niet (terugbladeren zonder iets te wijzigen kost geen aanroep)."""
    stap, sleutel = intake["stap"], wi.kaartsleutel(intake)
    # De keuzes op de bepalingen-kaartjes veranderen de zoekopdracht van een ander kaartje niet.
    h = wi.dossier_hash(intake, zonder=("bepalingen",) if stap == "bepalingen" else ())
    if stap not in (*wi.STAPPEN, "thema") or (intake.get("voorbereid") or {}).get(sleutel) == h:
        return intake
    intake = _met(_met(intake, "voorbereid", sleutel, h), "meldingen", sleutel, "")
    a = intake.get("antwoorden") or {}
    # Een naam stelt Lex voor bij een startzin met inhoud, of bij het aanvullen: dan ligt er een dossier.
    if stap == "naam" and (wi.is_aanvullen(intake) or wi.inhoud(intake.get("eerste_zin", ""))):
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
    elif stap == "thema" and wi.is_aanvullen(intake):
        intake = _thema(b, intake, writer, user_id)
    return intake


def _zeg(writer, tekst: str, **upd: Any) -> dict[str, Any]:
    writer({"type": "token", "content": tekst})
    return {**upd, "answer": tekst, "messages": [{"role": "assistant", "content": tekst}]}


ZONDER_WERKGEBIED = ("Het dossier vul ik aan in een werkgebied. Open het gesprek vanuit het werkgebied (Vraag Lex "
                     "in de kop), dan vraag ik wat er ontbreekt.")
WERKGEBIED_WEG = "Dat werkgebied bestaat niet meer, dus er valt niets aan te vullen."


def _haal_werkgebied(b, state: State, writer) -> tuple[dict[str, Any] | None, str]:
    """Het werkgebied van het gesprek, vers bij de api; anders (None, wat Lex zegt)."""
    from ..agents.uitvoering import draai
    from ..wetsanalyse_api import WetsanalyseApiFout
    from .agent_taak import STORING, ZONDER_API, _maak_api

    wid = state.get("werkgebied_id", "")
    if not wid:
        return None, ZONDER_WERKGEBIED
    if not b.settings.legt_zelf_vast:
        return None, ZONDER_API

    async def haal(_stuur):
        api = _maak_api(b, state.get("user_id", ""))
        try:
            return await api.haal_werkgebied(wid)
        finally:
            if (aclose := getattr(api, "aclose", None)) is not None:
                await aclose()

    try:
        return draai(haal, loop=b.loop, schrijf=writer), ""
    except WetsanalyseApiFout as fout:
        if fout.status == 404:
            return None, WERKGEBIED_WEG
        logger.warning("aanvullen: werkgebied niet opgehaald", extra={"categorie": "technisch",
                                                                      "http_status": fout.status})
    except Exception:  # noqa: BLE001 – een storing is een zin in het gesprek
        logger.warning("aanvullen: werkgebied niet opgehaald", extra={"categorie": "technisch"}, exc_info=True)
    return None, STORING


def _wat_er_staat(werkgebied: dict[str, Any]) -> str:
    """"Naam: Box 3; Analysevraag: Wie …?" – wat het dossier al heeft, kort."""
    delen = []
    for stap, veld in wi.DOSSIERVELD.items():
        waarde = " ".join(str(werkgebied.get(veld) or "").split())
        if waarde:
            delen.append(f"{wi.VELD_LABEL[stap]}: {waarde[:80]}{'…' if len(waarde) > 80 else ''}")
    return "; ".join(delen)


def _begin_aanvullen(b, state: State, writer) -> tuple[dict[str, Any] | None, str]:
    """De aanvul-intake op het werkgebied van het gesprek, met de zin waarmee Lex begint; of (None, wat Lex
    zegt) als er niets te vragen is."""
    vraag = state.get("question", "")
    werkgebied, melding = _haal_werkgebied(b, state, writer)
    if werkgebied is None:
        return None, melding
    genoemd = wi.dossiervelden_in(vraag)
    velden = genoemd or wi.lege_velden(werkgebied)
    if not velden:
        return None, (f"In het dossier van *{werkgebied.get('naam', '')}* staat alles al ingevuld – {_wat_er_staat(werkgebied)}. "
                      "Wil je iets wijzigen, noem dan het veld, bijvoorbeeld ‘pas de analysevraag aan’.")
    _stap(writer, "Lex", f"vult het dossier aan: {', '.join(wi.VELD_LABEL[s].lower() for s in velden)}")
    intake = wi.aanvul_intake(werkgebied, velden, vraag)
    if genoemd:
        return intake, "Laten we het dossier aanvullen."
    namen = [wi.VELD_LABEL[s].lower() for s in velden]
    lijst = namen[0] if len(namen) == 1 else ", ".join(namen[:-1]) + " en " + namen[-1]
    return intake, f"Laten we het dossier aanvullen. Er ontbreekt nog: {lijst}."


def _toon(writer, intake: dict[str, Any], tekst: str) -> dict[str, Any]:
    """De zin van Lex en het kaartje van de huidige stap."""
    kaart = wi.kaart(intake)
    writer({"type": "token", "content": tekst})
    writer({"type": "vraagkaart", "vraagkaart": kaart})
    return {"intake": intake, "answer": tekst,
            "messages": [{"role": "assistant", "content": f"{tekst}\n\n[Vraag: {kaart['vraag']}]".strip()}]}


def werkgebied_intake_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    vraag = state.get("question", "")
    actie = dict(state.get("intake_actie") or {})
    intake = dict(state.get("intake") or {})
    zinnen: list[str] = []

    if not actie and state.get("intake_modus") == "aanvullen":
        nieuw, zin = _begin_aanvullen(b, state, writer)
        if nieuw is None:
            return _zeg(writer, zin)
        intake = nieuw
        zinnen.append(zin)
        uitkomst = "begin"
    elif not actie and (wi.is_werkgebiedvraag(vraag) or not wi.is_open(intake)):
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
        # Een getypte bepaling op een bepalingenkaartje wordt hier een keuze, in de graaf getoetst; lukt dat niet,
        # dan blijft het kaartje staan met een vraag – nooit stil weg (spoor L). `eigen` komt nooit van de client.
        actie = {k: v for k, v in actie.items() if k != "eigen"}
        if (intake.get("stap") == "bepalingen" and actie.get("actie") == "antwoord" and actie.get("stap") == "bepalingen"
                and int(actie.get("deel") or 0) == int(intake.get("deel") or 0)
                and (tekst := " ".join(str(actie.get("tekst") or "").split()))
                and wi.ONBEKEND not in (actie.get("keuzes") or [])):
            eigen, vraag_terug = _eigen_bepalingen(b, intake, tekst, writer)
            if vraag_terug:
                # Het kaartje komt terug met wat de analist koos én typte (`concept`), om te verbeteren.
                concept = [*(str(k) for k in actie.get("keuzes") or []), tekst]
                return _toon(writer, {**intake, "concept": {wi.kaartsleutel(intake): concept}}, vraag_terug)
            actie = {**actie, "eigen": eigen}
        intake, uitkomst = wi.verwerk(intake, actie)

    aanvullen = wi.is_aanvullen(intake)
    if uitkomst == "afgebroken":
        return _zeg(writer, "Ik stop met aanvullen; er is niets gewijzigd." if aanvullen
                    else "Ik stop met samenstellen; er is geen werkgebied aangemaakt.", intake=intake)
    if uitkomst == "opslaan":
        # Eerst de stand van nu: veranderde het werkgebied terwijl de analist aanvulde, dan legt Lex zijn
        # antwoorden naast de nieuwe stand in plaats van een wijziging op een oude stand te sturen. Zo is
        # ook een tweede klik na een geslaagde opslag geen dubbele wijziging.
        werkgebied, melding = _haal_werkgebied(b, {**state, "werkgebied_id": intake.get("werkgebied_id", "")}, writer)
        if werkgebied is None and melding == WERKGEBIED_WEG:
            return _zeg(writer, melding, intake=intake)
        if werkgebied is None:
            # Een storing: het kaartje blijft, opnieuw klikken mag.
            return _toon(writer, {**intake, "stap": "samenvatting"}, f"{melding} Er is nog niets opgeslagen.")
        if int(werkgebied.get("revisie") or 0) != int(intake.get("revisie") or 0):
            intake = wi.op_nieuwe_stand(intake, werkgebied)
            return _toon(writer, intake, "Het werkgebied is intussen gewijzigd; er is nog niets opgeslagen. "
                         + ("Hieronder je antwoorden naast de stand van nu." if wi.wijzigingen(intake)
                            else "Het staat al zoals je het wilde."))
        _stap(writer, "Lex", "past het dossier van het werkgebied aan")
        writer({"type": "werkgebied_wijzigen", **wi.wijzigverzoek(intake)})
        # De tekst schrijft de beurt-driver, die weet wat de api ervan maakte.
        return {"intake": intake, "answer": "",
                "messages": [{"role": "assistant", "content": "Het dossier van het werkgebied aangepast."}]}
    if uitkomst == "aanmaken":
        _stap(writer, "Lex", "maakt het werkgebied aan")
        writer({"type": "werkgebied_aanmaken", **wi.aanmaakverzoek(intake)})
        # De tekst schrijft de beurt-driver, die weet wat de api ervan maakte.
        return {"intake": intake, "answer": "",
                "messages": [{"role": "assistant",
                              "content": f"Werkgebied ‘{intake['antwoorden'].get('naam', '')}’ aangemaakt."}]}
    if uitkomst == "verouderd":
        if intake.get("stap") == "klaar" and aanvullen:
            return _zeg(writer, "Dit aanvullen is al afgerond." if not intake.get("afgebroken") else
                        "Dit aanvullen is afgebroken. Vraag me opnieuw het dossier aan te vullen.", intake=intake)
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
        intake = _bereid_voor(b, intake, writer, state.get("user_id", ""))
        if uitkomst in ("verder", "begin"):
            zinnen.append(_zin(intake))
    return _toon(writer, intake, " ".join(zinnen))
