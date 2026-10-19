"""Lex naast de kaart, vanuit het gesprek (spoor D, fase F4): "zoek de brondefinitie van termijn".

Een harde route, zoals de begrippenroute: wie in het gesprek om een kaartactie op een begrip vraagt, komt
uit bij dezelfde kaart-run als de knop op de begripskaart (fase E, `begrip_kaart.kaart_stroom`). De
voorstellen landen onder hun veld op de kaart; het bericht draagt een begrippenartefact dat naar dát
begrip wijst (`ref: {werkgebied_id, begrip_id, kaart_run_id, actie}`).

- **Herkennen** (`kaartactie_uit`): een van de vier acties plus de term (of twee termen bij
  betekenisverschil). De route geldt binnen een werkgebied, of als de vraag het woord "begrip" noemt.
- **Het begrip oplossen** via de api (`GET /v1/begrippen`, het werkgebied van het gesprek eerst): alleen
  een exacte naam of alternatieve term telt. Eén treffer → starten. Meer → Lex noemt ze en vraagt welke.
  Alleen een vervangen begrip → Lex noemt de opvolger en start niet. Geen → zonder het woord "begrip" is
  het een gewone vraag (de antwoordroute neemt het over); mét het woord zegt Lex dat hij het niet vond.
- **Starten gaat direct**, net als een klik op de knop (besloten 19 okt 2026); de budgetpoort van de
  kaart-run blijft gelden. Loopt dezelfde actie al (de knop), dan wacht deze beurt op de uitkomst.
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from typing import Any, AsyncIterator, Callable

from .begrip_kaart import NAAM, kaart_stroom
from .config import Settings
from .wetsanalyse_api import GesprekVerdwenen, WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger("graph_qa.kaart_beurt")

WACHT_OP_ANDERE_RUN_S = 180.0
PEIL_S = 2.0

_ACTIES = (
    ("brondefinitie", re.compile(r"\bbrondefinitie\w*\b")),
    ("betekenisverschil", re.compile(r"\bbetekenisverschil\w*\b|\bverschil in betekenis\b|\bverschil\b.*\btussen\b")),
    ("scherper", re.compile(r"\b(aanscherp\w*|verscherp\w*|scherper\w*|scherp)\b.*\bdefinitie|\bdefinitie\b.*\b(aanscherp\w*|verscherp\w*|scherper\w*|scherp)\b")),
    ("voorbeelden", re.compile(r"\bvoorbeeld(en)?\b")),
)
_AANHALING = re.compile(r"[\"“”'‘’]([^\"“”'‘’]{2,80})[\"“”'‘’]")
_TUSSEN = re.compile(r"\btussen\s+(.+?)\s+en\s+(.+?)\s*[?.!]*$")
_VAN = re.compile(r"\b(?:van|bij|voor|op)\s+(.+?)\s*[?.!]*$")
_LIDWOORD = re.compile(r"^(?:het\s+begrip|de\s+term|het|de|een)\s+")
_BEGRIP = re.compile(r"\bbegrip\w*\b")
# "maak de definitie van termijn scherper": de handeling hoort niet bij de term.
_STAART = re.compile(r"\s+(?:scherper|scherp|aanscherpen|verscherpen|aan te scherpen|maken)$")

WEIGERING = {
    "geen_definitie": "Voorbeelden toetsen een definitie; geef het begrip eerst een definitie.",
    "geen_passages": "Dit begrip heeft nog geen actuele dragende passage; daar kan ik niets op baseren.",
    "inventaris_onvolledig": "Niet elke bron van het werkgebied kon worden opgehaald; probeer het zo opnieuw.",
}


def _normaal(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst or "")
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).casefold().split())


def _term(t: str) -> str:
    t = _STAART.sub("", _LIDWOORD.sub("", t.strip().strip("\"“”'‘’").strip()))
    return " ".join(t.split()[:6])


def kaartactie_uit(vraag: str) -> tuple[str, list[str]] | None:
    """De actie en de term(en), of None. Bij betekenisverschil twee termen."""
    q = (vraag or "").casefold()
    actie = next((a for a, patroon in _ACTIES if patroon.search(q)), None)
    if actie is None:
        return None
    citaten = [c.strip() for c in _AANHALING.findall(vraag or "")]
    if actie == "betekenisverschil":
        if len(citaten) >= 2:
            termen = citaten[:2]
        elif m := _TUSSEN.search(q):
            termen = [m.group(1), m.group(2)]
        else:
            return None
    elif citaten:
        termen = citaten[:1]
    elif m := _VAN.search(q):
        termen = [m.group(1)]
    else:
        return None
    termen = [_term(t) for t in termen]
    return (actie, termen) if all(termen) else None


def is_kaartvraag(vraag: str, werkgebied_id: str | None) -> bool:
    return kaartactie_uit(vraag) is not None and (bool(werkgebied_id) or bool(_BEGRIP.search((vraag or "").casefold())))


def begrip_artefact(werkgebied_id: str, begrip_id: str, naam: str, kaart_run_id: str = "", actie: str = "") -> dict[str, Any]:
    """In de vorm van `api/app/gesprek_contracts.Artefact` (soort begrippen, één begrip)."""
    ref = {"werkgebied_id": werkgebied_id, "begrip_id": begrip_id,
           **({"kaart_run_id": kaart_run_id} if kaart_run_id else {}), **({"actie": actie} if actie else {})}
    return {"soort": "begrippen", "titel": naam[:300], "ref": ref}


def exacte(term: str, rijen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    t = _normaal(term)
    return [r for r in rijen if _normaal(r.get("naam", "")) == t
            or t in {_normaal(x) for x in r.get("alternatieve_termen") or []}]


def kies(term: str, rijen: list[dict[str, Any]], eerst: str) -> tuple[dict[str, Any] | None, str]:
    """Het begrip voor deze term, of None met de zin die Lex dan zegt ("" = niets gevonden)."""
    gevonden = exacte(term, rijen)
    actief = [r for r in gevonden if r.get("status") != "vervangen"]
    if eerst and len(actief) > 1 and sum(r.get("werkgebied_id") == eerst for r in actief) == 1:
        actief = [r for r in actief if r.get("werkgebied_id") == eerst]
    if len(actief) == 1:
        return actief[0], ""
    if len(actief) > 1:
        opties = "; ".join(f"*{r['naam']}* in werkgebied {r.get('werkgebied_naam', '')} ({r.get('status', '')})"
                           for r in actief[:5])
        return None, f"Er zijn meer begrippen “{term}”: {opties}. Over welk werkgebied gaat het? Open het gesprek vanuit dat werkgebied, of noem het."
    if gevonden:
        r = gevonden[0]
        opvolger = (r.get("vervangen_door") or {}).get("naam", "")
        return None, (f"Het begrip *{r['naam']}* is vervangen" + (f" door *{opvolger}*" if opvolger else "")
                      + "; ik doe niets op een vervangen begrip. Vraag het voor de opvolger.")
    return None, ""


def _status(bericht: str) -> dict[str, Any]:
    return {"type": "status", "message": f"Lex · {bericht}"}


def samenvatting(actie: str, naam: str, werkgebied: str, aantal: int, melding: str, al_gedaan: bool) -> str:
    plek = {"brondefinitie": "onder de definitie", "scherper": "onder de definitie",
            "betekenisverschil": "bij de uitleg", "voorbeelden": "bij de voorbeelden"}.get(actie, "op de kaart")
    kop = f"{NAAM.get(actie, actie)} voor *{naam}* (werkgebied {werkgebied})"
    if al_gedaan:
        return f"{kop}: dit had ik voor deze stand van het begrip al gedaan; de voorstellen staan nog open {plek} op de begripskaart."
    if aantal:
        woord = "voorstel staat" if aantal == 1 else "voorstellen staan"
        return f"{kop}: {aantal} {woord} {plek} op de begripskaart. Neem over, pas aan of wijs af."
    return f"{kop}: geen voorstel. {melding}".strip()


async def kaart_beurt(request: Any, run: Any, *, settings: Settings, user_id: str,
                      terugval: Callable[[], AsyncIterator[dict[str, Any]]],
                      api: WetsanalyseApi | None = None, stroom=kaart_stroom) -> AsyncIterator[dict[str, Any]]:
    """De eventstroom van een kaartactie uit het gesprek; legt zelf vast, zoals `begrippen_beurt`."""
    actie, termen = kaartactie_uit(request.question) or ("", [])
    eerst = request.werkgebied_id or ""
    gesprek_id: str = request.conversation_id or ""
    run_id: str = getattr(run, "run_id", "") or ""
    noemt_begrip = bool(_BEGRIP.search(request.question.casefold()))
    denk: list[str] = []

    def status(bericht: str) -> dict[str, Any]:
        denk.append(f"· {bericht}")
        return _status(bericht)

    eigen_api = api is None
    api = api or WetsanalyseApi(settings, user_id)
    try:
        artefact: dict[str, Any] | None = None
        gekozen: list[dict[str, Any]] = []
        tekst = ""
        for term in termen:
            rijen = (await api.zoek_begrippen(term, eerst)).get("resultaten") or []
            begrip, zin = kies(term, rijen, eerst)
            if begrip is None:
                if not zin and not noemt_begrip:
                    # Geen vastgelegd begrip en de vraag noemt er ook geen: een gewone vraag over de wet.
                    async for ev in terugval():
                        yield ev
                    return
                tekst = zin or f"Ik vond geen vastgelegd begrip “{term}”. Begrippen staan per werkgebied op de tab Begrippen."
                break
            gekozen.append(begrip)
        if not tekst and actie == "betekenisverschil" and gekozen[0]["werkgebied_id"] != gekozen[1]["werkgebied_id"]:
            tekst = (f"*{gekozen[0]['naam']}* en *{gekozen[1]['naam']}* staan in verschillende werkgebieden; ik vergelijk "
                     "alleen begrippen binnen één werkgebied.")
        if not tekst:
            b = gekozen[0]
            wid, naam, wg_naam = b["werkgebied_id"], b["naam"], b.get("werkgebied_naam", "")
            yield status(f"{NAAM.get(actie, actie)} voor “{naam}” (werkgebied {wg_naam})")
            try:
                kr = await api.start_kaart_run(wid, b["id"], actie, gekozen[1]["id"] if len(gekozen) > 1 else None)
            except WetsanalyseApiFout as fout:
                if fout.status not in (404, 409, 422):
                    raise
                tekst = WEIGERING.get(fout.reden) or (fout.reden if fout.status == 404 else
                                                      "De api weigerde deze actie op dit begrip.")
            else:
                aantal, melding, al_gedaan = 0, "", False
                if kr.get("status") == "klaar":
                    al_gedaan = True
                elif not kr.get("nieuw"):
                    # Dezelfde actie loopt al (de knop op de kaart): wacht op die uitkomst.
                    yield status("Deze actie loopt al; ik wacht op de uitkomst")
                    wacht, stand = 0.0, kr
                    while stand.get("status") not in ("klaar", "mislukt") and wacht < WACHT_OP_ANDERE_RUN_S:
                        if run is not None and run.stop_gevraagd:
                            break
                        await asyncio.sleep(PEIL_S)
                        wacht += PEIL_S
                        stand = await api.haal_kaartrun_stand(wid, b["id"], kr["id"])
                    if stand.get("status") != "klaar":
                        tekst = "De actie die al liep, is niet afgerond. Vraag het straks nog eens."
                    melding = stand.get("melding") or ""
                    al_gedaan = stand.get("status") == "klaar"
                else:
                    async for ev in stroom(wid, b["id"], kr["id"], run, settings=settings, user_id=user_id, api=api):
                        if ev.get("type") == "status":
                            denk.append("· " + str(ev.get("message", "")).removeprefix("Lex · "))
                            yield ev
                        elif ev.get("type") == "opgeslagen":
                            aantal, melding = int(ev.get("voorstellen") or 0), str(ev.get("melding") or "")
                        elif ev.get("type") == "error":
                            yield ev
                            yield {"type": "done"}
                            return
                if not tekst:
                    tekst = samenvatting(actie, naam, wg_naam, aantal, melding, al_gedaan)
                artefact = begrip_artefact(wid, b["id"], naam, kr["id"], actie)

        if run is not None and run.stop_gevraagd:
            yield {"type": "done"}
            return
        yield {"type": "token", "content": tekst}
        extra = {"artefact": artefact} if artefact else {}
        bericht = {"rol": "assistant", "tekst": tekst, "denk": "\n".join(denk), "run_id": run_id, **extra}
        try:
            await api.voeg_bericht_toe(gesprek_id, bericht)
        except GesprekVerdwenen:
            yield {"type": "done"}
            return
        yield {"type": "opgeslagen", "run_id": run_id, **extra}
        yield {"type": "done"}
    except WetsanalyseApiFout as fout:
        logger.error("kaartbeurt: api-fout", extra={"categorie": "technisch", "run_id": run_id, "http_status": fout.status})
        yield {"type": "error", "message": "De actie op het begrip kon niet worden gestart of bewaard; probeer het opnieuw.",
               "soort": "api", "status": fout.status}
        yield {"type": "done"}
    finally:
        if eigen_api:
            await api.aclose()
