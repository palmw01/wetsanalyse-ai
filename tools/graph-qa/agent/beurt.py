"""
De beurt-driver: vangt de eventstroom op en legt de uitkomst vast.

Dit is het spiegelbeeld van wat de werkplek vroeger deed. Daar verzamelde `verstuur()` de events in
closure-variabelen en schreef ná de stream het document, de elementen en het chatbericht weg – met
als gevolg dat een gesloten tabblad al dat werk kostte. Diezelfde logica staat nu hier, achter de
run, waar geen browser bij nodig is.

Bewust **buiten** de LangGraph-code: de driver leest alleen de eventstroom van `answer_stream`, dus
`orchestrator.py` blijft ongemoeid. Dat scheelt risico op de plek waar het duurst is.

Twee volgorde-eisen die je niet mag omdraaien:

1. **`done` gaat er pas uit als er is weggeschreven.** Anders ziet een client die precies op dat
   moment herlaadt noch de lopende run, noch het bericht – en dan lijkt de beurt verdampt.
2. **Er wordt pas aan het eind geschreven.** `emit_node` is terminaal: vóór dat punt zijn er geen
   elementen. Een laag die al bij het `doel`-event ontstond, zou bij elke afgebroken run als leeg
   skelet in de werkvoorraad blijven staan.

Sinds 22 sep 2026 schrijft een annotatiebeurt naar de **gedeelde laag van het artikel**
(`PUT /v1/annotatie/lagen/{bwbId}/{artikel}/elementen`), niet meer naar een eigen document per
beurt: één laag per artikel voor iedereen, zodat een artikel dat al geannoteerd is niet opnieuw
hoeft. De lidstand (hash + IRI per lid) en de artikelhash reizen mee op het `doel`-event.
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
        elif soort == "tool_execution":
            self.tool_executions.append({k: v for k, v in event.items() if k != "type"})

    def _voeg_element_toe(self, element: dict[str, Any]) -> None:
        """Ontdubbeld verzamelen: de annoteerder ⇄ Critic-lus kan hetzelfde element opnieuw sturen,
        en dan wint de laatste versie.

        Dezelfde regel als `mergeVoorstellen` in de werkplek en als de merge in de api: eerst op
        `id`, anders op de canonieke inhoudssleutel (`sleutel_van` – genormaliseerde tekst + lid).
        Dat laatste stond hier eerder als rúwe tekst in één tuple mét het id, waardoor een
        witruimteverschil een tweede kaart opleverde en een herziening zonder id nooit matchte.
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
) -> AsyncIterator[dict[str, Any]]:
    """Draai één beurt: stuur de events door, en leg aan het eind de uitkomst vast.

    `run` is het run-object uit het register; we lezen er het stopverzoek en het `run_id` uit.

    Kan graph-qa niet zelf wegschrijven (geen api geconfigureerd, of geen gesprek/gebruiker bekend),
    dan is dit puur een doorgeefluik. Leverde de beurt wél markeringen op, dan **zeggen we dat**:
    de werkplek nam dat vroeger stilzwijgend over met een eigen schrijfpad, en dat tweede pad is
    weg. Zwijgen zou nu betekenen dat een annotatie van anderhalve minuut spoorloos verdwijnt.
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
        async for na in _leg_vast(schrijver, settings=settings, run=run,
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
) -> AsyncIterator[dict[str, Any]]:
    """Schrijf de markeringen naar de gedeelde laag en het chatbericht weg; meld de uitkomst."""
    api = WetsanalyseApi(settings, user_id)
    try:
        bericht: dict[str, Any] = {"rol": "assistant", "run_id": run.run_id,
                                 "tool_executions": schrijver.tool_executions}
        slug = ""
        annotatie_bewaard = False
        opgeslagen_doel = None

        if schrijver.is_annotatie:
            # Eén PUT naar de gedeelde laag van het artikel: de api maakt hem aan als hij er nog
            # niet is. Vanaf hier kan een deel geslaagd zijn – de laag staat er, het chatbericht
            # nog niet – en dat hoort in de foutmelding. Anders draait de jurist de beurt van 60-90
            # seconden opnieuw voor iets wat al bewaard is.
            doel = schrijver.doel or {}
            run_info = schrijver.run or {}
            aanduiding = str(doel.get("artikel") or doel.get("nummer") or "")
            if doel.get("schema_versie") == 2:
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
                    # Per kandidaat de uitkomst, ook de afgewezen (validatieplan V4). De api bewaart
                    # het bij de batch; het staat niet op de elementen, want dan draagt elk element
                    # de hele lijst.
                    "beslissingen": schrijver.dekking.get("beslissingen") or [],
                })
            elif schrijver.volledig_hergebruikt:
                # Niets nieuws om te mergen; alleen vastleggen dát er hergebruikt is.
                laag = await api.hergebruik(
                    bwb_id=str(doel.get("bwbId", "")), artikel=aanduiding,
                    citeertitel=str(doel.get("citeertitel") or ""),
                    leden=list(doel.get("leden") or []), run=schrijver.run,
                )
            else:
                laag = await api.zet_laag_elementen(
                    bwb_id=str(doel.get("bwbId", "")),
                    artikel=aanduiding,
                    citeertitel=str(doel.get("citeertitel") or ""),
                    elementen=schrijver.elementen,
                    run=schrijver.run,
                    leden=list(doel.get("leden") or []),
                    bron_hash=str(doel.get("bron_hash") or ""),
                    modus="opnieuw" if run_info.get("modus") == "opnieuw" else "auto",
                )
            slug = str(laag.get("slug", ""))
            annotatie_bewaard = True
            if doel.get("schema_versie") == 2:
                opgeslagen_doel = {"bron_iri": doel["bron_iri"], "label": doel.get("label", ""),
                                   "snapshot_id": doel["snapshot_id"]}
            if getattr(api, "hergebruikt", None):
                # De graaf zag deze leden niet als geannoteerd, de api wel: de projectie liep
                # achter (meestal net na een GraphDB-herstart). Dat kostte tokens, geen werk –
                # maar het moet meetbaar zijn, anders valt een haperende projectie nooit op.
                logger.warning(
                    "hergebruik_gemist",
                    extra={"categorie": "functioneel", "run_id": run.run_id,
                           "leden": api.hergebruikt, "annotatie_slug": slug},
                )
                # Het vangnet van de api: dit lid was al geannoteerd en is niet veranderd, dus
                # deze voorstellen zijn niet toegevoegd. Geen fout – de bestaande annotatie staat
                # er – maar de jurist moet weten waarom zijn nieuwe voorstellen er niet bij staan.
                leden = ", ".join(api.hergebruikt)
                yield {
                    "type": "waarschuwing",
                    "message": (f"Lid {leden} was al geannoteerd en is sindsdien niet veranderd. De "
                                "bestaande annotatie is behouden; deze nieuwe voorstellen zijn niet "
                                "toegevoegd. Vraag om opnieuw annoteren als je ze er toch bij wilt."),
                }
            if getattr(api, "verworpen", 0):
                # Niet als `error`: de beurt is geslaagd en de rest staat er. Maar wél zeggen —
                # anders ziet de jurist dertien markeringen en weet hij niet dat het er vijftien
                # hadden moeten zijn. Een stil verlies is erger dan een luide fout.
                aantal = api.verworpen
                yield {
                    "type": "waarschuwing",
                    "message": (f"{aantal} markering{'en' if aantal > 1 else ''} kon niet worden "
                                f"opgeslagen en {'staan' if aantal > 1 else 'staat'} niet in de "
                                f"annotatie. Wat er wél is, vind je hieronder."),
                }
            bericht |= {
                "annotatie_slug": slug,
                "annotatie_titel": _titel(doel),
                "denk": schrijver.denk,
                **({"hergebruik": schrijver.hergebruik} if schrijver.hergebruik else {}),
                # Zonder het beslisregister: dat hoort bij de batch, niet in de gespreksgeschiedenis.
                **({"dekking": {k: v for k, v in schrijver.dekking.items() if k != "beslissingen"}}
                   if schrijver.dekking else {}),
                **({"annotatie_doel": {"bron_iri": doel["bron_iri"],
                                       "label": doel.get("label", ""),
                                       "snapshot_id": doel["snapshot_id"]}}
                   if doel.get("schema_versie") == 2 else {}),
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
