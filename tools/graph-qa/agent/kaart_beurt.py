"""Lex naast de kaart, vanuit het gesprek (spoor D, fase F4; sinds F3c de kaarttaken van de
begrippen-agent, `agents/begrippen.py`).

Een kaartactie uit het gesprek komt uit bij dezelfde kaart-run als de knop op de begripskaart (fase E,
`begrip_kaart.kaart_stroom`). De voorstellen landen onder hun veld op de kaart; de uitkomst draagt een
begrippenartefact dat naar dát begrip wijst (`ref: {werkgebied_id, begrip_id, kaart_run_id, actie}`).

- **Welk begrip.** Het begrip dat de analist met *Vraag Lex* aanwees (`als_rij`), anders de term(en) uit de
  vraag (`termen_uit`) opgelost via de api (`los_op`: `GET /v1/begrippen`, het werkgebied van het gesprek
  eerst; alleen een exacte naam of alternatieve term telt). Meer kandidaten → Lex noemt ze en vraagt
  welke. Alleen een vervangen begrip → Lex noemt de opvolger en start niet.
- **Welke actie** kiest de supervisor (de taak), of een klik op een suggestie – geen tekstpatroon meer.
  `kaartactie_uit` blijft voor de metingen en de tests van de term.
- **Starten gaat direct**, net als een klik op de knop (besloten 19 okt 2026); de budgetpoort van de
  kaart-run blijft gelden. Loopt dezelfde actie al (de knop), dan wacht Lex op de uitkomst.
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from typing import Any

from .agents import Context, Uitkomst, geweigerd
from .begrip_kaart import MODEL_ACTIES, NAAM, kaart_stroom
from .wetsanalyse_api import WetsanalyseApiFout

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
# "wat is het betekenisverschil met betalingstermijn?" – bij een aangewezen begrip één term: het andere.
_MET = re.compile(r"\bmet\s+(.+?)\s*[?.!]*$")
# "werk het begrip termijn volledig uit": één woord na "het begrip", als niets anders de term noemt.
_HET_BEGRIP = re.compile(r"\bhet\s+begrip\s+(?!volledig\b|uit\b)([\w-]+)")
_LIDWOORD = re.compile(r"^(?:het\s+begrip|de\s+term|het|de|een)\s+")
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


def termen_uit(vraag: str, actie: str) -> list[str]:
    """De term(en) waar een kaartactie over gaat, uit de getypte vraag: tussen aanhalingstekens, na
    "tussen … en …" (betekenisverschil, twee termen) of na "van/bij/voor/op". Leeg als er geen staat."""
    q = (vraag or "").casefold()
    citaten = [c.strip() for c in _AANHALING.findall(vraag or "")]
    if actie == "betekenisverschil":
        if len(citaten) >= 2:
            termen = citaten[:2]
        elif m := _TUSSEN.search(q):
            termen = [m.group(1), m.group(2)]
        elif len(citaten) == 1:
            termen = citaten
        elif m := _MET.search(q):
            termen = [m.group(1)]
        else:
            return []
    elif citaten:
        termen = citaten[:1]
    elif m := _VAN.search(q):
        termen = [m.group(1)]
    elif m := _HET_BEGRIP.search(q):
        termen = [m.group(1)]
    else:
        return []
    termen = [_term(t) for t in termen]
    return termen if all(termen) else []


def kaartactie_uit(vraag: str) -> tuple[str, list[str]] | None:
    """De actie en de term(en), of None. Bij betekenisverschil twee termen."""
    q = (vraag or "").casefold()
    actie = next((a for a, patroon in _ACTIES if patroon.search(q)), None)
    if actie is None:
        return None
    termen = termen_uit(vraag, actie)
    if actie == "betekenisverschil" and len(termen) < 2:
        return None
    return (actie, termen) if termen else None


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


async def als_rij(ctx: Context, werkgebied_id: str, begrip_id: str) -> dict[str, Any] | None:
    """Een begrip dat de analist aanwees (het onderwerp), in de vorm van een rij uit `GET /v1/begrippen`.
    None als de api het niet (meer) kent."""
    try:
        b = await ctx.api.haal_begrip(werkgebied_id, begrip_id)
    except WetsanalyseApiFout as fout:
        if fout.status == 404:
            return None
        raise
    try:
        wg_naam = str((await ctx.api.haal_werkgebied(werkgebied_id)).get("naam") or "")
    except WetsanalyseApiFout:
        wg_naam = ""
    inhoud = b.get("inhoud") or {}
    return {"id": begrip_id, "naam": inhoud.get("naam") or "naamloos", "werkgebied_id": werkgebied_id,
            "werkgebied_naam": wg_naam, "status": b.get("status", ""), "definitie": inhoud.get("definitie") or "",
            "vervangen_door": b.get("vervangen_door") or {}}


async def los_op(ctx: Context, termen: list[str], eerst: str) -> tuple[list[dict[str, Any]], str]:
    """De begrippen bij deze termen (exacte naam of alternatieve term, het werkgebied `eerst` voorop). Lukt
    het niet, dan een lege lijst met de zin die Lex dan zegt."""
    gekozen: list[dict[str, Any]] = []
    for term in termen:
        rijen = (await ctx.api.zoek_begrippen(term, eerst)).get("resultaten") or []
        begrip, zin = kies(term, rijen, eerst)
        if begrip is None:
            return [], zin or (f"Ik vond geen vastgelegd begrip “{term}”. Begrippen staan per werkgebied op de "
                               "tab Begrippen; open het gesprek vanuit het begrip of noem het precies.")
        gekozen.append(begrip)
    return gekozen, ""


async def kaart_kern(ctx: Context, actie: str, b: dict[str, Any], ander: dict[str, Any] | None = None) -> Uitkomst:
    """Eén kaartactie op één begrip, als de knop op de begripskaart: `POST …/kaart-runs` en
    `begrip_kaart.kaart_stroom` (met zijn budgetpoort), of wachten als dezelfde actie al loopt. `b` en
    `ander` zijn rijen in de vorm van `GET /v1/begrippen`."""
    if b.get("status") == "vervangen":
        opvolger = (b.get("vervangen_door") or {}).get("naam", "")
        return geweigerd(actie, f"Het begrip *{b['naam']}* is vervangen" + (f" door *{opvolger}*" if opvolger else "")
                         + "; ik doe niets op een vervangen begrip. Vraag het voor de opvolger.")
    if actie == "betekenisverschil":
        if ander is None:
            return geweigerd(actie, f"Met welk begrip wil je *{b['naam']}* vergelijken? Noem het, of vraag het "
                                    "vanuit het andere begrip.")
        if ander["werkgebied_id"] != b["werkgebied_id"]:
            return geweigerd(actie, f"*{b['naam']}* en *{ander['naam']}* staan in verschillende werkgebieden; ik "
                                    "vergelijk alleen begrippen binnen één werkgebied.")
    wid, naam, wg_naam = b["werkgebied_id"], b["naam"], b.get("werkgebied_naam", "")
    ctx.melding(f"{NAAM.get(actie, actie)} voor “{naam}” (werkgebied {wg_naam})")
    try:
        kr = await ctx.api.start_kaart_run(wid, b["id"], actie, ander["id"] if ander else None)
    except WetsanalyseApiFout as fout:
        if fout.status not in (404, 409, 422):
            raise
        return geweigerd(actie, WEIGERING.get(fout.reden) or (fout.reden if fout.status == 404 else
                                                             "De api weigerde deze actie op dit begrip."))
    artefact = begrip_artefact(wid, b["id"], naam, kr["id"], actie)
    aantal, melding, al_gedaan = 0, "", False
    if kr.get("status") == "klaar":
        al_gedaan = True
    elif not kr.get("nieuw"):
        # Dezelfde actie loopt al (de knop op de kaart): wacht op die uitkomst.
        ctx.melding("Deze actie loopt al; ik wacht op de uitkomst")
        wacht, stand = 0.0, kr
        while stand.get("status") not in ("klaar", "mislukt") and wacht < WACHT_OP_ANDERE_RUN_S:
            if ctx.gestopt():
                break
            await asyncio.sleep(PEIL_S)
            wacht += PEIL_S
            stand = await ctx.api.haal_kaartrun_stand(wid, b["id"], kr["id"])
        if stand.get("status") != "klaar":
            return Uitkomst(taak=actie, status="fout", artefact=artefact,
                            reden="De actie die al liep, is niet afgerond. Vraag het straks nog eens.")
        melding, al_gedaan = stand.get("melding") or "", True
    else:
        async for ev in kaart_stroom(wid, b["id"], kr["id"], ctx.run, settings=ctx.settings, user_id=ctx.user_id,
                                     api=ctx.api):
            if ev.get("type") == "status":
                ctx.melding(str(ev.get("message", "")).removeprefix("Lex · "))
            elif ev.get("type") == "opgeslagen":
                aantal, melding = int(ev.get("voorstellen") or 0), str(ev.get("melding") or "")
            elif ev.get("type") == "error":
                return Uitkomst(taak=actie, status="fout", artefact=artefact,
                                reden=str(ev.get("message") or "De actie op het begrip mislukte; probeer het opnieuw."))
    return Uitkomst(taak=actie, tekst=samenvatting(actie, naam, wg_naam, aantal, melding, al_gedaan),
                    artefact=artefact, voorstellen=[kr["id"]] if aantal else [],
                    meting={"voorstellen": aantal, "model": actie in MODEL_ACTIES and not al_gedaan})
