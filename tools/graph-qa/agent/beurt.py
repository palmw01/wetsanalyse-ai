"""
De beurt-driver: vangt de eventstroom op en legt de uitkomst vast.

De driver staat achter de run, niet in de browser: een gesloten tabblad mag het werk van een beurt
niet kosten.

Bewust **buiten** de LangGraph-code: de driver leest alleen de eventstroom van `answer_stream`, dus
`orchestrator.py` blijft ongemoeid. Dat scheelt risico op de plek waar het duurst is.

Twee volgorde-eisen die je niet mag omdraaien:

1. **`done` gaat er pas uit als er is weggeschreven.** Anders ziet een client die precies op dat
   moment herlaadt noch de lopende run, noch het bericht – en dan lijkt de beurt verdampt.
2. **Er wordt pas aan het eind geschreven.** `emit_node` is terminaal: vóór dat punt zijn er geen
   elementen. Een laag die al bij het `doel`-event ontstond, zou bij elke afgebroken run als leeg
   skelet in de werkvoorraad blijven staan.

Een annotatiebeurt schrijft één batch naar de gedeelde laag van de bronnode
(`POST /v1/annotatie/lagen/batch`), idempotent op het run-id. De bronstand (`snapshot_id`,
`verwachte_revisies`) reist mee op het `doel`-event.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from .annotatie import sleutel_van
from .config import Settings
from .models import Verbruiksmeter
from .wetsanalyse_api import GesprekVerdwenen, WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger("graph_qa.beurt")


def _titel(doel: dict[str, Any]) -> str:
    """Het leesbare label van de annotatie, zoals de werkplek het toont.

    Reist mee met het bericht zodat de kaart in het gesprek zichzelf kan benoemen als het document
    later verwijderd wordt – er is geen foreign key die dat afdwingt."""
    naam = doel.get("citeertitel") or doel.get("bwbId") or ""
    lid = doel.get("lid") or ""
    return f"{naam} – art. {doel.get('artikel', '')}" + (f" lid {lid}" if lid else "")


class BeurtSchrijver:
    """Verzamelt wat er in één beurt binnenkomt en legt het aan het eind vast."""

    def __init__(self) -> None:
        self.doel: dict[str, Any] | None = None
        self.elementen: list[dict[str, Any]] = []
        self.run: dict[str, Any] | None = None
        self.kandidaten: list[dict[str, Any]] = []
        self.hergebruik: dict[str, Any] = {}
        self.dekking: dict[str, Any] = {}
        self.overzicht: dict[str, Any] = {}
        self.tekst = ""
        self.denk = ""
        self.bronnen: list[dict[str, Any]] = []
        self.tool_executions: list[dict[str, Any]] = []

    def verwerk(self, event: dict[str, Any]) -> None:
        """Eén event bijhouden. Dezelfde toewijzing als de handlers in de werkplek."""
        soort = event.get("type")
        if soort == "token":
            self.tekst += event.get("content", "")
        elif soort == "status":
            self.denk += ("\n" if self.denk else "") + "· " + event.get("message", "")
        elif soort == "reason":
            self.denk += event.get("content", "")
        elif soort == "sources":
            self.bronnen = event.get("sources") or []
        elif soort == "doel":
            self.doel = event.get("doel") or {}
        elif soort == "element":
            self._voeg_element_toe(event.get("element") or {})
        elif soort == "run":
            self.run = event.get("run") or {}
        elif soort == "kandidaten":
            self.kandidaten = event.get("kandidaten") or []
        elif soort == "hergebruik":
            self.hergebruik = event.get("hergebruik") or {}
        elif soort == "dekking":
            self.dekking = event.get("dekking") or {}
        elif soort == "overzicht":
            self.overzicht = event.get("overzicht") or {}
        elif soort == "tool_execution":
            self._voeg_tool_toe({k: v for k, v in event.items() if k != "type"})

    def _voeg_tool_toe(self, event: dict[str, Any]) -> None:
        """Eén regel per aanroep: het eind-event werkt het start-event bij.

        Elke aanroep geeft een start- én een eind-event met hetzelfde `call_id`
        (`tool_execution.execute_tool`). Die werden hier los bewaard; de werkplek liet ze na
        herladen dan allebei zien en telde het dubbele ("10 aanroepen" voor vijf). Dezelfde regel
        als `mergeToolExecution` in de werkplek: een laat binnengekomen start draait een afgeronde
        aanroep niet terug.
        """
        sleutel = (event.get("run_id", ""), event.get("call_id", ""))
        if sleutel[1]:
            for i, bestaand in enumerate(self.tool_executions):
                if (bestaand.get("run_id", ""), bestaand.get("call_id", "")) != sleutel:
                    continue
                if event.get("phase") == "start" and bestaand.get("phase") != "start":
                    return
                self.tool_executions[i] = {**bestaand, **event}
                return
        self.tool_executions.append(event)

    def _voeg_element_toe(self, element: dict[str, Any]) -> None:
        """Ontdubbeld verzamelen: komt hetzelfde element opnieuw binnen, dan wint de laatste versie.

        Dezelfde regel als `mergeVoorstellen` in de werkplek en als de merge in de api: eerst op
        `id`, anders op de canonieke inhoudssleutel (`sleutel_van` – genormaliseerde tekst + lid).
        Niet op rúwe tekst in één tuple mét het id: dan levert een witruimteverschil een tweede
        kaart op en matcht een herziening zonder id nooit.
        """
        if not element:
            return

        def zelfde(bestaand: dict[str, Any]) -> bool:
            eigen_id, ander_id = element.get("id") or "", bestaand.get("id") or ""
            if eigen_id and ander_id:
                return eigen_id == ander_id
            if element.get("ankers") or bestaand.get("ankers"):
                def anker_sleutel(value):
                    return tuple((a.get("bron_iri"), a.get("start"), a.get("eind")) for a in value.get("ankers", []))
                return (element.get("klasse") == bestaand.get("klasse") and
                        anker_sleutel(element) == anker_sleutel(bestaand))
            return sleutel_van(element.get("tekst") or "", element.get("lid") or "") == sleutel_van(
                bestaand.get("tekst") or "", bestaand.get("lid") or ""
            )

        for i, bestaand in enumerate(self.elementen):
            if zelfde(bestaand):
                self.elementen[i] = element
                return
        self.elementen.append(element)

    @property
    def is_annotatie(self) -> bool:
        return bool(self.doel and (self.doel.get("bron_iri") or self.doel.get("bwbId"))
                    and (self.elementen or self.volledig_hergebruikt or self.run))

    @property
    def volledig_hergebruikt(self) -> bool:
        """Alles kwam uit de gedeelde laag: geen nieuwe voorstellen, wel een annotatie."""
        return bool(self.hergebruik.get("volledig")) and not self.elementen


async def voer_beurt_uit(
    stroom: AsyncIterator[dict[str, Any]],
    *,
    settings: Settings,
    run,
    gesprek_id: str,
    user_id: str,
    meter: Verbruiksmeter | None = None,
    reeks: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Draai één beurt: stuur de events door, en leg aan het eind de uitkomst vast.

    `reeks` markeert een beurt als onderdeel van een reeks (`agent/reeks.py`): het bericht draagt
    dan `{run_id, index, totaal}`, zodat de werkplek de berichten van één reeks samen toont.

    `run` is het run-object uit het register; we lezen er het stopverzoek en het `run_id` uit.

    Kan graph-qa niet zelf wegschrijven (geen api geconfigureerd, of geen gesprek/gebruiker bekend),
    dan is dit puur een doorgeefluik. Leverde de beurt wél markeringen op, dan **zeggen we dat**:
    de werkplek heeft geen eigen schrijfpad, dus zwijgen zou betekenen dat een annotatie van
    anderhalve minuut spoorloos verdwijnt.
    """
    schrijver = BeurtSchrijver()
    try:
        async for event in stroom:
            if event.get("type") == "done":
                # Vasthouden: `done` is voor de client het teken dat de beurt vastligt.
                break
            schrijver.verwerk(event)
            yield event
    finally:
        # Het verbruik boeken gebeurt óók als de beurt op een fout eindigde of werd gestopt: die
        # tokens zijn wel degelijk verbruikt. Vandaar een `finally` en geen plek verderop in het
        # geslaagde pad.
        await _boek_verbruik(
            meter, settings=settings, run=run, gesprek_id=gesprek_id, user_id=user_id,
        )

    # Is er om stoppen gevraagd, dan is de graaf er zelf op een nodegrens uitgestapt (`stop_check` →
    # `BeurtGestopt`). We breken hier dus NIET af: dan zouden we de generator halverwege dichtgooien
    # en het lopende werk alsnog weggooien – precies wat we wilden afschaffen. De prijs is dat
    # stoppen tijd kost; dat hoort de UI te tonen.
    gestopt = bool(run.stop_gevraagd)

    mag_vastleggen = settings.legt_zelf_vast and bool(gesprek_id) and bool(user_id)
    if mag_vastleggen:
        async for na in _leg_vast(schrijver, settings=settings, run=run, reeks=reeks,
                                  gesprek_id=gesprek_id, gestopt=gestopt, user_id=user_id):
            yield na
    elif schrijver.is_annotatie:
        logger.warning(
            "beurt: markeringen niet vastgelegd (geen schrijfpad)",
            extra={"categorie": "functioneel", "run_id": run.run_id,
                   "elementen": len(schrijver.elementen)},
        )
        yield {
            "type": "error",
            "message": ("Deze markeringen zijn niet vastgelegd: deze agent heeft geen verbinding "
                        "met de wetsanalyse-API."),
        }
    yield {"type": "done"}


async def _boek_verbruik(
    meter: Verbruiksmeter | None,
    *,
    settings: Settings,
    run,
    gesprek_id: str,
    user_id: str,
) -> None:
    """Meld het tokenverbruik van deze beurt aan de api (best-effort).

    Stil falen is hier de juiste keuze: de beurt is klaar en het werk staat er. Een hapering in de
    boekhouding mag geen foutmelding opleveren die de jurist niets zegt – het log draagt het.
    """
    if meter is None or meter.totaal <= 0:
        return
    if not (settings.legt_zelf_vast and user_id):
        return
    try:
        api = WetsanalyseApi(settings, user_id)
        try:
            await api.boek_verbruik(
                meter.als_dict(),
                model=settings.llm_model,
                gesprek_id=gesprek_id,
                run_id=getattr(run, "run_id", "") or "",
            )
        finally:
            await api.aclose()
    except Exception:  # noqa: BLE001 – boekhouding mag de beurt niet laten mislukken
        logger.warning(
            "verbruik niet geboekt",
            extra={"categorie": "functioneel", "run_id": getattr(run, "run_id", "")},
            exc_info=True,
        )


async def _leg_vast(
    schrijver: BeurtSchrijver,
    *,
    settings: Settings,
    run,
    gesprek_id: str,
    gestopt: bool,
    user_id: str,
    reeks: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Schrijf de markeringen naar de gedeelde laag en het chatbericht weg; meld de uitkomst."""
    api = WetsanalyseApi(settings, user_id)
    try:
        bericht: dict[str, Any] = {"rol": "assistant", "run_id": run.run_id,
                                 "tool_executions": schrijver.tool_executions,
                                 **({"reeks": reeks} if reeks else {})}
        slug = ""
        annotatie_bewaard = False
        opgeslagen_doel = None

        if schrijver.is_annotatie:
            # Eén batch naar de laag van de bronnode. Vanaf hier kan een deel geslaagd zijn – de laag
            # staat er, het chatbericht nog niet – en dat hoort in de foutmelding. Anders draait de
            # jurist de beurt van 60-90 seconden opnieuw voor iets wat al bewaard is.
            doel = schrijver.doel or {}
            laag = await api.zet_bronnode_batch({
                "batch_id": run.run_id,
                "doel": {"bron_iri": doel["bron_iri"]}, "snapshot_id": doel["snapshot_id"],
                "verwachte_revisies": doel.get("verwachte_revisies") or {},
                "elementen": schrijver.elementen,
                "dekking": {"voltooid": not gestopt, "bereik": doel.get("bereik") or [],
                            "parent_context": not gestopt,
                            # Wat de keten wel en niet kon bekijken (dimensies, ongedekte
                            # zinsdelen met offsets, procesdekking) – de api toont het in de
                            # weergave en projecteert het naar de graaf.
                            "structureel": schrijver.dekking.get("per_bron", {}),
                            "proces": schrijver.dekking.get("proces", {})},
                "run": schrijver.run or {},
                # Per kandidaat de uitkomst, ook de afgewezen (validatieplan V4). De api bewaart het
                # bij de batch; het staat niet op de elementen, want dan draagt elk element de hele
                # lijst.
                "beslissingen": schrijver.dekking.get("beslissingen") or [],
            })
            slug = str(laag.get("slug", ""))
            annotatie_bewaard = True
            opgeslagen_doel = {"bron_iri": doel["bron_iri"], "label": doel.get("label", ""),
                               "snapshot_id": doel["snapshot_id"]}
            bericht |= {
                # Wat Lex over de annotatie zei (hoogstens vier zinnen, `annotatie_samenvatting`).
                # Zonder dit veld zag je hem alleen live: na herladen of op een ander apparaat
                # stond er alleen de kaart.
                "tekst": schrijver.tekst.strip(),
                "annotatie_slug": slug,
                "annotatie_titel": _titel(doel),
                "denk": schrijver.denk,
                **({"hergebruik": schrijver.hergebruik} if schrijver.hergebruik else {}),
                # Zonder het beslisregister: dat hoort bij de batch, niet in de gespreksgeschiedenis.
                **({"dekking": {k: v for k, v in schrijver.dekking.items() if k != "beslissingen"}}
                   if schrijver.dekking else {}),
                "annotatie_doel": opgeslagen_doel,
            }
        else:
            tekst = schrijver.tekst.strip()
            if gestopt:
                # Weggooien wat de agent al schreef is niet wat "stoppen" betekent. Maar beloof ook
                # geen half resultaat dat er niet is: `emit_node` is terminaal, dus stoppen vóór dat
                # punt levert écht nul voorstellen op – dan is dat wat er staat.
                tekst = f"{tekst}\n\n_(gestopt)_" if tekst else "_Gestopt – er waren nog geen voorstellen._"
            bericht |= {
                "tekst": tekst or "(geen antwoord)",
                "denk": schrijver.denk,
                "bronnen": schrijver.bronnen,
                # Het overzicht uit de graaf (`agent/overzicht.py`): zonder dit veld toonde de werkplek
                # na herladen alleen de duiding, en het blok en de 3D-doelen waren weg.
                **({"overzicht": schrijver.overzicht} if schrijver.overzicht else {}),
            }

        await api.voeg_bericht_toe(gesprek_id, bericht)
        logger.info(
            "beurt vastgelegd",
            extra={"categorie": "functioneel", "run_id": run.run_id,
                   "chat_session_id": gesprek_id, "annotatie_slug": slug},
        )
        # De client hoeft de inhoud niet mee te krijgen: hij haalt het document bij de api op. Zo
        # blijft er één bron van waarheid en groeit het SSE-contract niet mee met het datamodel.
        yield {"type": "opgeslagen", "annotatie_slug": slug, "run_id": run.run_id,
               **({"annotatie_doel": bericht["annotatie_doel"]} if bericht.get("annotatie_doel") else {})}
    except GesprekVerdwenen:
        # De jurist verwijderde het gesprek terwijl de beurt liep. Dat is geen fout om over te
        # klagen – alarm slaan over iemands eigen handeling leert mensen meldingen negeren.
        #
        # Het annotatiedocument blijft wél staan: annotaties zijn eersteklas objecten die los van
        # hun gesprek bestaan (zie /annotaties), dus dat is bewaard werk, geen wees.
        logger.info(
            "gesprek verdwenen tijdens de beurt",
            extra={"categorie": "functioneel", "run_id": run.run_id, "chat_session_id": gesprek_id},
        )
    except (WetsanalyseApiFout, Exception) as exc:
        logger.exception(
            "beurt niet vastgelegd",
            extra={"categorie": "technisch", "run_id": run.run_id, "chat_session_id": gesprek_id,
                   "annotatie_slug": slug},
        )
        # Zichtbaar falen: de jurist moet weten dat dit werk niet bewaard is, niet later ontdekken
        # dat het gesprek een gat heeft. Wél eerlijk zijn over wat er al staat: "probeer opnieuw" is
        # een slecht advies als de annotatie er al is.
        #
        # Het geval "document bestaat, markeringen niet" is er niet meer: de laag en haar
        # markeringen gaan in één PUT. Mislukt die, dan is er geen slug en valt dit in de laatste tak.
        if annotatie_bewaard:
            yield {
                "type": "error",
                "message": ("De annotatie is bewaard, alleen het bericht in dit gesprek niet. "
                            "Je vindt hem terug bij Annotaties."),
                "annotatie_slug": slug,
                **({"annotatie_doel": opgeslagen_doel} if opgeslagen_doel else {}),
            }
        elif isinstance(exc, WetsanalyseApiFout) and exc.status == 409 and "Heropen" in exc.reden:
            # De laag werd afgerond terwijl de beurt liep (vooraf controleert de annotatie-route
            # dat al). Opnieuw proberen helpt dan niet; heropenen wel.
            yield {"type": "error", "foutcode": "annotatie_afgerond",
                   "message": "Deze annotatie is afgerond. De nieuwe voorstellen zijn niet opgeslagen; "
                              "heropen de annotatie in het paneel als je Lex hem opnieuw wilt laten annoteren."}
        elif isinstance(exc, WetsanalyseApiFout) and exc.status in (409, 412):
            yield {"type": "error", "foutcode": "annotatie_conflict",
                   "message": "De bron of annotatielaag is intussen gewijzigd. De nieuwe voorstellen "
                              "zijn niet opgeslagen; laad de annotatie opnieuw."}
        else:
            yield {
                "type": "error",
                "message": "Het antwoord is gemaakt, maar niet opgeslagen. Probeer de vraag opnieuw.",
            }
    finally:
        await api.aclose()
