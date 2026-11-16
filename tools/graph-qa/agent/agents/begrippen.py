"""De begrippen-agent (F3c): begrippen voorstellen, uitwerken, vergelijken en meedenken.

| Taak | Keten | Model |
|---|---|---|
| `voorstellen` | begrippenrun + keten (ADR-004), `begrippen_beurt.begrippen_kern` | nee |
| `meedenken` | de verdieping (`begrippen_verdieping.verdieping_kern`); zonder `bevestigd` het voorstel | ja, na bevestiging |
| `brondefinitie` | kaart-run, graafquery op `bwb:definieertBegrip` | nee |
| `scherper`, `uitleg`, `voorbeelden`, `betekenisverschil` | kaart-run, één strict tool + `toetsen` (`kaart_beurt.kaart_kern`) | ja, één stap |
| `uitwerken` | in één beurt (B-6): brondefinitie → zonder definitie scherper → uitleg in B1, toelichting en voorbeelden, op de overgenomen definitie of anders op de voorgestelde (die hun basis is) | waar de deelstap het heeft |
| `relaties` | de relaties en de voorstellen van de keten (`GET …/relaties`) | nee |

Het begrip komt van *Vraag Lex* (het onderwerp) of uit de vraag (de term, opgelost via de api). De
begrippenkennis staat in de skill (`references/begrippen.md`, rol `begrippen`). Een begrip is een
analyse-uitkomst en telt nooit als bron. Een vraag óver een wettelijke definitie, zonder vastgelegd begrip,
is geen taak van deze agent: die blijft bij de antwoord-worker (`definitie`).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from ..begrippen_beurt import begrippen_kern
from ..begrippen_verdieping import verdieping_kern
from ..kaart_beurt import _normaal, als_rij, begrip_artefact, kaart_kern, keuzekaart, los_op
from ..wetsanalyse_api import WetsanalyseApiFout
from . import Context, Uitkomst, geweigerd


#: Wat deze agent doet, met wat er níét bij hoort (ADR-010 contractpunt 1; de catalogus toont het, ADR-014).
DOEL = "Stelt begrippen voor, werkt één begrip uit (brondefinitie, scherper, uitleg, toelichting, voorbeelden, betekenisverschil, relaties) en denkt mee bij twijfel; elk resultaat is een voorstel."


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
    keuze = await _begrippen(ctx, invoer)
    if keuze.kaart:
        return Uitkomst(taak=taak, status="geweigerd", reden=keuze.kaart["vraag"], vraagkaart=keuze.kaart)
    begrip, ander = keuze.begrip, keuze.ander
    if begrip is None:
        return geweigerd(taak, keuze.zin)
    if taak in KAARTACTIES:
        return await kaart_kern(ctx, str(taak), begrip, ander)
    if taak is Taak.RELATIES:
        return await relaties(ctx, begrip)
    return await uitwerken(ctx, begrip)


@dataclass
class Keuze:
    begrip: dict[str, Any] | None = None
    ander: dict[str, Any] | None = None
    zin: str = ""
    kaart: dict[str, Any] | None = None


def _is_naam_van(term: str, b: dict[str, Any]) -> bool:
    return _normaal(term) in {_normaal(n) for n in [b["naam"], *(b.get("alternatieve_termen") or [])]}


async def _begrippen(ctx: Context, invoer: Invoer) -> Keuze:
    """Het begrip (en bij betekenisverschil het andere): aangewezen, anders uit de termen van de vraag. Noemt de
    vraag zelf twee begrippen, dan gaat de vraag voor op wat er aangewezen is: het onderwerp vult alleen aan wat de
    vraag niet noemt, en een term wordt nooit stil vervangen door iets anders (S1 in de e2e-test van 5 nov 2026)."""
    begrip = ander = None
    verschil = invoer.taak is Taak.BETEKENISVERSCHIL
    if invoer.begrip_id and invoer.werkgebied_id:
        begrip = await als_rij(ctx, invoer.werkgebied_id, invoer.begrip_id)
        if begrip is None:
            return Keuze(zin="Dat begrip bestaat niet (meer) in dit werkgebied.")
    if invoer.ander_id and (invoer.werkgebied_id or begrip):
        ander = await als_rij(ctx, invoer.werkgebied_id or begrip["werkgebied_id"], invoer.ander_id)
    # Wat nog ontbreekt, komt uit de termen van de vraag, in volgorde: eerst het begrip, dan bij
    # betekenisverschil het andere. De naam van een aangewezen begrip telt niet als het andere.
    termen = [t for t in invoer.termen if begrip is None or not _is_naam_van(t, begrip)]
    if verschil and len(termen) >= 2 and begrip is not None and not invoer.ander_id:
        begrip = None
    nodig = (0 if begrip else 1) + (1 if verschil and ander is None else 0)
    rest = termen[:nodig]
    if begrip is None and not rest:
        return Keuze(zin="Over welk begrip gaat het? Kies *Vraag Lex* bij het begrip, of noem het – bijvoorbeeld "
                         "“zoek de brondefinitie van het begrip termijn”.")
    gevonden: list[dict[str, Any]] = []
    for term in rest:
        wel = begrip or (gevonden[0] if gevonden else None)
        zonder = frozenset(r["id"] for r in (wel,) if r)
        uit = await los_op(ctx, term, invoer.werkgebied_id, zonder)
        if uit.opties:
            wid = invoer.werkgebied_id or uit.opties[0].get("werkgebied_id") or ""
            return Keuze(kaart=keuzekaart(str(invoer.taak), wid, term, uit.opties, wel))
        if uit.begrip is None:
            return Keuze(zin=uit.zin)
        gevonden.append(uit.begrip)
    if begrip is None:
        begrip, gevonden = gevonden[0], gevonden[1:]
    if ander is None and gevonden:
        ander = gevonden[0]
    return Keuze(begrip=begrip, ander=ander)


RELATIETYPE = {"kwalificatie": "kwalificeert", "inclusie": "omvat", "uitsluiting": "sluit uit",
               "hierarchie": "heeft als soort", "verwant": "is verwant met", "opvolging": "volgt op"}


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
    """Een begrip volledig uitwerken in één beurt (B-6, besluit 16 nov 2026), in de volgorde van de methode: eerst de
    brondefinitie; staat er dan nog geen definitie en vond Lex er geen, een scherpere (een definitievoorstel). Daarna
    de uitleg in B1 en de toelichting (als die er nog niet zijn) en de voorbeelden. Is er geen overgenomen
    definitie, dan rusten die op de voorgestelde: de api legt dat definitievoorstel vast als hun basis, en neemt de
    analist het niet of anders over, dan zijn ze verouderd. Alles blijft een voorstel per veld; relaties zijn een
    aparte stap. Aan het eind zegt Lex wat er nog open is."""
    taak = Taak.UITWERKEN
    b = (await als_rij(ctx, b["werkgebied_id"], b["id"])) or b          # met uitleg en toelichting van nu
    stappen: list[Uitkomst] = [await kaart_kern(ctx, "brondefinitie", b, volgende=False)]
    heeft_definitie = bool((b.get("definitie") or "").strip())
    if not heeft_definitie and not stappen[0].voorstellen and not ctx.gestopt():
        stappen.append(await kaart_kern(ctx, "scherper", b, volgende=False))
    basis: dict[str, Any] | None = None
    if not heeft_definitie and not ctx.gestopt():
        basis = await _voorgestelde_definitie(ctx, b, [r for s in stappen for r in s.voorstellen])
    op = "" if heeft_definitie else (basis or {}).get("id", "")
    if heeft_definitie or op:
        for actie, veld in (("uitleg", "uitleg"), ("toelichting", "context"), ("voorbeelden", "")):
            if ctx.gestopt() or (veld and (b.get(veld) or "").strip()):
                continue
            stappen.append(await kaart_kern(ctx, actie, b, volgende=False, op_voorstel=op))
    zinnen = [s.gesprekstekst for s in stappen if s.gesprekstekst]
    zinnen.append(_nog_open(heeft_definitie, basis))
    laatste = next((s.artefact for s in reversed(stappen) if s.artefact), None)
    status = "fout" if all(s.status == "fout" for s in stappen) else "ok"
    return Uitkomst(taak=taak, status=status, tekst="\n\n".join(zinnen),
                    voorstellen=[v for s in stappen for v in s.voorstellen],
                    artefact=laatste or begrip_artefact(b["werkgebied_id"], b["id"], b["naam"]),
                    meting={"stappen": [{"taak": s.taak, "status": s.status, **s.meting} for s in stappen],
                            "model": any(s.meting.get("model") for s in stappen),
                            "op_voorgestelde_definitie": bool(op)})


async def _voorgestelde_definitie(ctx: Context, b: dict[str, Any], runs: list[str]) -> dict[str, Any] | None:
    """Het definitievoorstel waarop de rest van de beurt rust: open en niet verouderd, bij voorkeur uit een run van
    deze beurt, en daarbinnen het eerste (de sterkste plaats, `kaartacties.brondefinities`). None als er geen is."""
    try:
        alle = (await ctx.api.haal_kaartvoorstellen(b["werkgebied_id"], b["id"])).get("voorstellen") or []
    except WetsanalyseApiFout:
        return None
    open_ = [v for v in alle if v.get("veld") == "definitie" and v.get("status") == "open" and not v.get("verouderd")]
    eigen = [v for v in open_ if v.get("run_id") in runs]
    kandidaten = eigen or open_
    return min(kandidaten, key=lambda v: (runs.index(v["run_id"]) if v.get("run_id") in runs else len(runs),
                                          v.get("volgorde", 0))) if kandidaten else None


def _nog_open(heeft_definitie: bool, basis: dict[str, Any] | None = None) -> str:
    """Wat er na deze beurt nog open is; relaties zijn altijd een aparte stap."""
    relaties = "Relaties met andere begrippen zijn een aparte stap: vraag erom als de rest staat."
    if heeft_definitie:
        return ("Nog open: neem de uitleg, de toelichting en de voorbeelden over die je goed vindt. " + relaties)
    if basis is None:
        return ("Nog open: er is geen definitievoorstel, dus ook geen uitleg, toelichting of voorbeelden. Geef het "
                "begrip een definitie op de begripskaart, en vraag het daarna opnieuw. " + relaties)
    tekst = ((basis.get("waarde") or {}).get("definitie") or "").strip()
    return ("Nog open: neem eerst de definitie over" + (f" (“{tekst[:200]}”)" if tekst else "") + ". De uitleg, "
            "de toelichting en de voorbeelden rusten op die voorgestelde definitie: neem je haar niet of anders over, "
            "dan vervallen ze en zie je dat op de begripskaart. " + relaties)
