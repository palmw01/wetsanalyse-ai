"""De begrippen-agent (F3c): begrippen voorstellen, uitwerken, vergelijken en meedenken.

| Taak | Keten | Model |
|---|---|---|
| `voorstellen` | begrippenrun + keten (ADR-004), `begrippen_beurt.begrippen_kern` | nee |
| `meedenken` | de verdieping (`begrippen_verdieping.verdieping_kern`); zonder `bevestigd` het voorstel | ja, na bevestiging |
| `brondefinitie` | kaart-run, graafquery op `bwb:definieertBegrip` | nee |
| `scherper`, `uitleg`, `voorbeelden`, `betekenisverschil` | kaart-run, één strict tool + `toetsen` (`kaart_beurt.kaart_kern`) | ja, één stap |
| `uitwerken` | brondefinitie → zonder definitie een definitievoorstel → uitleg in B1 en voorbeelden alleen op een overgenomen definitie | waar de deelstap het heeft |
| `relaties` | de relaties en de voorstellen van de keten (`GET …/relaties`) | nee |

Het begrip komt van *Vraag Lex* (het onderwerp) of uit de vraag (de term, opgelost via de api). De
begrippenkennis staat in de skill (`references/begrippen.md`, rol `begrippen`). Een begrip is een
analyse-uitkomst en telt nooit als bron. Een vraag óver een wettelijke definitie, zonder vastgelegd begrip,
is geen taak van deze agent: die blijft bij de antwoord-worker (`definitie`).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from ..begrippen_beurt import begrippen_kern
from ..begrippen_verdieping import verdieping_kern
from ..kaart_beurt import als_rij, begrip_artefact, kaart_kern, los_op
from ..wetsanalyse_api import WetsanalyseApiFout
from . import Context, Uitkomst, geweigerd


class Taak(StrEnum):
    VOORSTELLEN = "voorstellen"
    MEEDENKEN = "meedenken"
    BRONDEFINITIE = "brondefinitie"
    SCHERPER = "scherper"
    UITLEG = "uitleg"
    VOORBEELDEN = "voorbeelden"
    BETEKENISVERSCHIL = "betekenisverschil"
    UITWERKEN = "uitwerken"
    RELATIES = "relaties"


#: Taken op het hele werkgebied; de rest gaat over één begrip.
OP_WERKGEBIED = frozenset({Taak.VOORSTELLEN, Taak.MEEDENKEN})
#: Taken die het model kunnen gebruiken (meedenken pas na bevestiging).
MODEL_TAKEN = frozenset({Taak.MEEDENKEN, Taak.SCHERPER, Taak.UITLEG, Taak.VOORBEELDEN, Taak.BETEKENISVERSCHIL,
                         Taak.UITWERKEN})
KAARTACTIES = frozenset({Taak.BRONDEFINITIE, Taak.SCHERPER, Taak.UITLEG, Taak.VOORBEELDEN, Taak.BETEKENISVERSCHIL})

_ID = r"^[A-Za-z0-9-]{0,64}$"


class Invoer(BaseModel):
    taak: Taak
    werkgebied_id: str = Field(default="", pattern=_ID)
    begrip_id: str = Field(default="", pattern=_ID)
    # Het andere begrip bij betekenisverschil, als de analist het aanwees.
    ander_id: str = Field(default="", pattern=_ID)
    # De term(en) uit de vraag, als er geen begrip is aangewezen (bij betekenisverschil twee).
    termen: list[str] = Field(default_factory=list, max_length=2)
    bevestigd: int | None = Field(default=None, ge=0, le=100_000)
    werkvoorraad_id: str = Field(default="", pattern=r"^(W[0-9a-f]{16})?$")


async def voer_uit(invoer: Invoer, ctx: Context) -> Uitkomst:
    taak = invoer.taak
    if taak in OP_WERKGEBIED:
        if not invoer.werkgebied_id:
            return geweigerd(taak, "Over welk werkgebied gaat het? Begrippen stel ik voor binnen een werkgebied; open "
                                   "het gesprek vanuit een werkgebied.")
        if taak is Taak.VOORSTELLEN:
            return await begrippen_kern(ctx, invoer.werkgebied_id)
        return await verdieping_kern(ctx, invoer.werkgebied_id, invoer.bevestigd, invoer.werkvoorraad_id)
    begrip, ander, zin = await _begrippen(ctx, invoer)
    if begrip is None:
        return geweigerd(taak, zin)
    if taak in KAARTACTIES:
        return await kaart_kern(ctx, str(taak), begrip, ander)
    if taak is Taak.RELATIES:
        return await relaties(ctx, begrip)
    return await uitwerken(ctx, begrip)


async def _begrippen(ctx: Context, invoer: Invoer) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """Het begrip (en bij betekenisverschil het andere): aangewezen, anders uit de termen van de vraag."""
    begrip = ander = None
    if invoer.begrip_id and invoer.werkgebied_id:
        begrip = await als_rij(ctx, invoer.werkgebied_id, invoer.begrip_id)
        if begrip is None:
            return None, None, "Dat begrip bestaat niet (meer) in dit werkgebied."
    if invoer.ander_id and (invoer.werkgebied_id or begrip):
        ander = await als_rij(ctx, invoer.werkgebied_id or begrip["werkgebied_id"], invoer.ander_id)
    # Wat nog ontbreekt, komt uit de termen van de vraag, in volgorde: eerst het begrip, dan bij
    # betekenisverschil het andere. De naam van een aangewezen begrip telt niet als het andere.
    nodig = (0 if begrip else 1) + (1 if invoer.taak is Taak.BETEKENISVERSCHIL and ander is None else 0)
    rest = [t for t in invoer.termen if begrip is None or t.casefold() != begrip["naam"].casefold()][:nodig]
    if begrip is None and not rest:
        return None, None, ("Over welk begrip gaat het? Kies *Vraag Lex* bij het begrip, of noem het – bijvoorbeeld "
                            "“zoek de brondefinitie van het begrip termijn”.")
    gevonden, zin = await los_op(ctx, rest, invoer.werkgebied_id) if rest else ([], "")
    if rest and not gevonden:
        return None, None, zin
    if begrip is None:
        begrip, gevonden = gevonden[0], gevonden[1:]
    if ander is None and gevonden:
        ander = gevonden[0]
    return begrip, ander, ""


RELATIETYPE = {"kwalificatie": "kwalificeert", "inclusie": "omvat", "uitsluiting": "sluit uit",
               "hierarchie": "is een soort van", "verwant": "is verwant met", "opvolging": "volgt op"}


def _relatieregel(r: dict[str, Any]) -> str:
    return f"*{r.get('van_naam', '')}* {RELATIETYPE.get(r.get('type', ''), r.get('type', ''))} *{r.get('naar_naam', '')}*"


async def relaties(ctx: Context, b: dict[str, Any]) -> Uitkomst:
    """Wat er vastligt en wat de keten voorstelt; de voorstellen leg je vast op de tab Samenhang of de kaart."""
    taak = Taak.RELATIES
    try:
        data = await ctx.api.haal_relaties(b["werkgebied_id"], b["id"])
    except WetsanalyseApiFout as fout:
        if fout.status == 404:
            return geweigerd(taak, "Dat begrip of werkgebied bestaat niet (meer).")
        raise
    vast = [r for r in data.get("relaties") or [] if r.get("beoordeling") == "akkoord"]
    voorstel = data.get("voorstellen") or []
    ctx.melding(f"Relaties van “{b['naam']}”: {len(vast)} vastgelegd, {len(voorstel)} voorgesteld")
    delen = []
    if vast:
        delen.append("Vastgelegd: " + "; ".join(_relatieregel(r) for r in vast[:8]) + ".")
    if voorstel:
        delen.append(f"Ik stel {len(voorstel)} {'relatie' if len(voorstel) == 1 else 'relaties'} voor: "
                     + "; ".join(_relatieregel(r) for r in voorstel[:8])
                     + ". Leg vast wat klopt, of wijs af met een reden.")
    if not delen:
        delen.append("De begrippenketen ziet nu geen relatie van dit begrip met een ander begrip in dit werkgebied, en "
                     "er is er nog geen vastgelegd.")
    return Uitkomst(taak=taak, tekst=f"Relaties van *{b['naam']}*. " + " ".join(delen),
                    voorstellen=[str(r["id"]) for r in voorstel if r.get("id")],
                    artefact=begrip_artefact(b["werkgebied_id"], b["id"], b["naam"]),
                    meting={"vastgelegd": len(vast), "voorgesteld": len(voorstel), "model": False})


async def uitwerken(ctx: Context, b: dict[str, Any]) -> Uitkomst:
    """Een begrip volledig uitwerken, in de volgorde van de methode (spoor I2): eerst de brondefinitie; staat er
    dan nog geen definitie, een definitievoorstel; op een overgenomen definitie de uitleg in B1 (als die er nog
    niet is) en voorbeelden – een uitleg en een voorbeeld rusten op een definitie, dus zonder definitie is er
    niets uit te leggen of te toetsen. Aan het eind zegt Lex wat er nog open is."""
    taak = Taak.UITWERKEN
    stappen: list[Uitkomst] = [await kaart_kern(ctx, "brondefinitie", b, volgende=False)]
    heeft_definitie = bool((b.get("definitie") or "").strip())
    if not heeft_definitie and not stappen[0].voorstellen and not ctx.gestopt():
        stappen.append(await kaart_kern(ctx, "scherper", b, volgende=False))
    if heeft_definitie and not (b.get("uitleg") or "").strip() and not ctx.gestopt():
        stappen.append(await kaart_kern(ctx, "uitleg", b, volgende=False))
    if heeft_definitie and not ctx.gestopt():
        stappen.append(await kaart_kern(ctx, "voorbeelden", b, volgende=False))
    zinnen = [s.gesprekstekst for s in stappen if s.gesprekstekst]
    zinnen.append(_nog_open(heeft_definitie))
    laatste = next((s.artefact for s in reversed(stappen) if s.artefact), None)
    status = "fout" if all(s.status == "fout" for s in stappen) else "ok"
    return Uitkomst(taak=taak, status=status, tekst="\n\n".join(zinnen),
                    voorstellen=[v for s in stappen for v in s.voorstellen],
                    artefact=laatste or begrip_artefact(b["werkgebied_id"], b["id"], b["naam"]),
                    meting={"stappen": [{"taak": s.taak, "status": s.status, **s.meting} for s in stappen],
                            "model": any(s.meting.get("model") for s in stappen)})


def _nog_open(heeft_definitie: bool) -> str:
    """Het volgende logische stuk: zonder definitie eerst die, daarna uitleg en voorbeelden, en dan relaties."""
    if not heeft_definitie:
        return ("Nog open: neem een definitie over op de begripskaart. Daarna schrijf ik de uitleg in B1 en maak ik "
                "voorbeelden.")
    return ("Nog open: neem de uitleg en de voorbeelden over die je goed vindt. Daarna kan ik relaties met andere "
            "begrippen voorstellen.")
