"""De deelvragen-agent (F3c): deelvragen opstellen en verbeteren, bronnen zoeken, de dekking.

| Taak | Keten | Model |
|---|---|---|
| `voorstellen` | dossier → één strict tool → `valideer` → `POST …/deelvragen/voorstellen` | ja, één stap |
| `verbeteren` | deelvraag + dossier → één strict tool (herformuleer of splits) → validatie → voorstel | ja, één stap |
| `bronnen_zoeken` | de bronnenrun (`bronnen_run.bronnen_kern`, met de methode per deelvraag) | nee |
| `dekking` | per actieve deelvraag: bronnen, rol, open kandidaten, begrippen – uit de api | nee |

De methode – wat een goede deelvraag is, van deelvraag naar bronnen, wat dekking betekent – staat in de
skill (`references/deelvragen-en-bronnen.md`, rol `deelvragen`); de modelstappen krijgen haar mee en de
validatie in code volgt dezelfde tekst. Een *uitleg*-vraag over een deelvraag ("waarom hoort art. 9 bij
deelvraag 2?") is geen taak van deze agent: die gaat naar de antwoord-worker, met het onderwerp als context.

Bronnen per deelvraag op lidniveau komen met de intake (F3f); tot dan zoekt `bronnen_zoeken` met de
bestaande methoden en noemt het wat er bij de aangewezen deelvraag hoort.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..bronnen_run import bronnen_kern
from ..deelvragen import verbeteren_kern, voorstellen_kern
from ..wetsanalyse_api import WetsanalyseApiFout
from . import Context, Uitkomst, geweigerd


class Taak(StrEnum):
    VOORSTELLEN = "voorstellen"
    VERBETEREN = "verbeteren"
    BRONNEN_ZOEKEN = "bronnen_zoeken"
    DEKKING = "dekking"


#: Taken met een modelstap; de rest draait aantoonbaar zonder model.
MODEL_TAKEN = frozenset({Taak.VOORSTELLEN, Taak.VERBETEREN})
#: Taken over één deelvraag; zonder `deelvraag_id` vraagt Lex welke.
PER_DEELVRAAG = frozenset({Taak.VERBETEREN})


class Invoer(BaseModel):
    taak: Taak
    werkgebied_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")
    deelvraag_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")
    # "deelvraag 2" in de vraag: de tweede actieve deelvraag, in de volgorde van het werkgebied.
    deelvraag_nr: int | None = Field(default=None, ge=1, le=99)
    # Bij `verbeteren`: wat de analist vroeg; leeg = het model kiest.
    soort: Literal["", "herformuleer", "splits"] = ""


async def voer_uit(invoer: Invoer, ctx: Context) -> Uitkomst:
    taak = invoer.taak
    if not invoer.werkgebied_id:
        return geweigerd(taak, "Over welk werkgebied gaat het? Open het gesprek vanuit een werkgebied, of kies "
                               "*Vraag Lex* bij een deelvraag.")
    if invoer.deelvraag_nr is not None and not invoer.deelvraag_id:
        did, zin = await deelvraag_op_nummer(ctx, invoer.werkgebied_id, invoer.deelvraag_nr)
        if not did:
            return geweigerd(taak, zin)
        invoer = invoer.model_copy(update={"deelvraag_id": did})
    if taak in PER_DEELVRAAG and not invoer.deelvraag_id:
        return geweigerd(taak, "Welke deelvraag bedoel je? Kies *Vraag Lex* bij die deelvraag, of noem haar nummer.")
    if taak is Taak.VOORSTELLEN:
        return await voorstellen_kern(ctx, invoer.werkgebied_id)
    if taak is Taak.VERBETEREN:
        return await verbeteren_kern(ctx, invoer.werkgebied_id, invoer.deelvraag_id, invoer.soort)
    if taak is Taak.BRONNEN_ZOEKEN:
        return await bronnen_kern(ctx, invoer.werkgebied_id, invoer.deelvraag_id)
    return await dekking(ctx, invoer.werkgebied_id, invoer.deelvraag_id)


async def deelvraag_op_nummer(ctx: Context, werkgebied_id: str, nr: int) -> tuple[str, str]:
    """De n-de actieve deelvraag, zoals de werkplek ze nummert; anders leeg met de zin die Lex dan zegt."""
    try:
        wg = await ctx.api.haal_werkgebied(werkgebied_id)
    except WetsanalyseApiFout as fout:
        if fout.status == 404:
            return "", "Dit werkgebied bestaat niet (meer)."
        raise
    actief = [d for d in wg.get("deelvragen") or [] if d.get("status", "actief") == "actief"]
    if 1 <= nr <= len(actief):
        return str(actief[nr - 1]["id"]), ""
    return "", (f"Deelvraag {nr} ken ik niet: werkgebied *{wg.get('naam', '')}* heeft er {len(actief)}."
                if actief else f"Werkgebied *{wg.get('naam', '')}* heeft nog geen actieve deelvragen.")


STAND = {"gedekt": "gedekt", "geen_begrip": "nog geen geaccordeerd begrip", "geen_bron": "nog geen bron"}


def dekking_regel(nr: int, d: dict[str, Any], rollen: dict[str, str], open_: int) -> str:
    """Eén regel per deelvraag: de stand en wat er ontbreekt."""
    bronnen = d.get("bronnen") or []
    analyse = [b for b in bronnen if rollen.get(b.get("id", "")) == "analyseren"]
    delen = [STAND.get(d.get("stand", ""), d.get("stand", ""))]
    if bronnen:
        delen.append(f"{len(bronnen)} {'bron' if len(bronnen) == 1 else 'bronnen'}"
                     + ("" if analyse else ", alleen context"))
    if open_:
        delen.append(f"{open_} {'kandidaat' if open_ == 1 else 'kandidaten'} van Lex open")
    return f"{nr}. “{d.get('vraag', '')}” – {'; '.join(delen)}"


def dekkingstekst(naam: str, dek: dict[str, Any], wg: dict[str, Any], kandidaten: list[dict[str, Any]],
                  deelvraag_id: str = "") -> str:
    """Uit de api, geen model. Zegt wat er ontbreekt en maakt de dekking niet mooier dan ze is."""
    vragen = dek.get("deelvragen") or []
    if not vragen:
        return (f"Werkgebied *{naam}* heeft nog geen actieve deelvragen; dekking meet ik per deelvraag. Laat me "
                "deelvragen voorstellen bij de analysevraag.")
    rollen = {b.get("id", ""): b.get("rol", "") for b in wg.get("bronnen") or []}
    open_per: dict[str, int] = {}
    for k in kandidaten:
        if k.get("status") != "voorgesteld" or k.get("in_selectie"):
            continue
        for did in {(b.get("detail") or {}).get("deelvraag_id") for b in k.get("bewijs") or []} - {None, ""}:
            open_per[did] = open_per.get(did, 0) + 1
    regels = [dekking_regel(i, d, rollen, open_per.get(d.get("id", ""), 0)) for i, d in enumerate(vragen, 1)
              if not deelvraag_id or d.get("id") == deelvraag_id]
    if deelvraag_id and not regels:
        return "Die deelvraag is niet (meer) actief; dekking meet ik alleen voor actieve deelvragen."
    gedekt = sum(1 for d in vragen if d.get("stand") == "gedekt")
    kop = (f"Dekking van werkgebied *{naam}*: {gedekt} van {len(vragen)} "
           f"{'deelvraag' if len(vragen) == 1 else 'deelvragen'} gedekt." if not deelvraag_id
           else f"Dekking in werkgebied *{naam}*:")
    tekst = kop + "\n\n" + "\n".join(regels)
    if any(d.get("stand") == "geen_bron" for d in vragen if not deelvraag_id or d.get("id") == deelvraag_id):
        tekst += "\n\nBij een deelvraag zonder bron kan ik bepalingen zoeken; neem op wat erbij hoort."
    return tekst


async def dekking(ctx: Context, werkgebied_id: str, deelvraag_id: str = "") -> Uitkomst:
    taak = Taak.DEKKING
    try:
        wg = await ctx.api.haal_werkgebied(werkgebied_id)
        dek = await ctx.api.haal_deelvragen_dekking(werkgebied_id)
    except WetsanalyseApiFout as fout:
        if fout.status == 404:
            return geweigerd(taak, "Dit werkgebied bestaat niet (meer).")
        raise
    try:
        kandidaten = (await ctx.api.haal_kandidaten(werkgebied_id)).get("kandidaten") or []
    except WetsanalyseApiFout:
        kandidaten = []     # de kandidaten zijn een aanvulling; de stand zelf staat er dan wel
    naam = str(wg.get("naam") or "zonder naam")
    ctx.melding(f"Dekking van {dek.get('totaal', 0)} deelvragen in {naam}")
    from ..beurt import deelvraag_artefact, werkgebied_artefact
    d = next((x for x in wg.get("deelvragen") or [] if deelvraag_id and x.get("id") == deelvraag_id), None)
    return Uitkomst(taak=taak, tekst=dekkingstekst(naam, dek, wg, kandidaten, deelvraag_id),
                    artefact=deelvraag_artefact(werkgebied_id, d) if d else werkgebied_artefact(wg),
                    meting={"telling": dek.get("telling") or {}, "kandidaten": len(kandidaten), "model": False})
