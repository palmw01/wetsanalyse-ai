"""Service-laag voor het tokenbudget: boeken, optellen, begrenzen.

Het dragende idee: **verbruik is een journaal, de stand is een som.** Er wordt nergens een teller
opgeslagen en het journaal verandert nooit. Elke LLM-call levert één rij in `token_verbruik`; hoeveel
iemand nu verbruikt heeft is `sum(...) WHERE userid = ? AND tijdstip >= vanaf`, en `vanaf` is het
begin van het venster, of de laatste reset door een beheerder als die later ligt.

Dat is geen stijlkeuze maar de reden dat drie dingen kloppen:

- **Werk weggooien geeft geen tokens terug.** Een gesprek of annotatiedocument verwijderen wist zijn
  eigen rijen (`gesprek_store.verwijder_gesprek`, `annotatie_v2_store.verwijder_weergave`), maar raakt
  het journaal niet: `userid` is de enige harde sleutel, `gesprek_id`/`run_id` zijn losse metadata.
- **De reset kan niet mislukken.** Er is geen periodieke taak die de tellers nulzet; het vensterbegin
  wordt uit het anker gerekend. Draait de dienst een week niet, dan klopt de stand daarna nog steeds.
- **Elk getal is navraagbaar**, tot op de call.

Een reset door een beheerder is daarom een **begrenzing van de som** en geen wijziging van het
journaal: er komt een rij in `budget_audit` en de som begint daarna later. Een tegenboeking in het
journaal kan dat niet: die maakt van elke rij een call behalve de ene die er geen is, en wat later
over de calls wordt geteld (de schatting per beurt, een gewogen variant) moet hem dan overal uitsluiten.
In het volgende venster doet de reset vanzelf niets meer: dan ligt hij vóór het begin.

**Het budget van iemand volgt uit zijn rol** (`budget_rol`), en uit niets anders: een rolwissel geeft
meteen het budget van de nieuwe rol. Alleen wie geen account of rolrij heeft, valt terug op de seedwaarde.

Wat meetelt: invoer + uitvoer + cache_lees + cache_schrijf, dus het **volle promptvolume**. Een
cache-read kost bij de provider ~0,1×, maar het is wél tekst die het model verwerkte. Het budget
begrenst dus gebruik, niet de factuur; de vier getallen staan apart in de tabel zodat een gewogen
variant later een rekenregel is en geen migratie.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from . import db
from .config import Settings, get_settings
from .user import ROLLEN, _utcnow
from .verbruik_contracts import VOL, WAARSCHUWINGSDREMPEL, BudgetBeleid, RolBudget, Verbruiksstand

logger = logging.getLogger(__name__)

# Er is precies één beleidsrij.
_BELEID_ID = 1

# De acties in `budget_audit`.
ACTIE_RESET = "verbruik_reset"
ACTIE_ROLBUDGET = "rolbudget_gewijzigd"
ACTIE_BELEID = "beleid_gewijzigd"


async def _audit(conn: AsyncConnection, actie: str, *, door: str, doel: str = "", **details: Any) -> None:
    """Eén regel in `budget_audit`, in de transactie van de wijziging zelf."""
    await conn.execute(insert(db.budget_audit).values(
        actie=actie, doel=doel, door=door, details=details, tijdstip=_utcnow(),
    ))


# --- beleid --------------------------------------------------------------------

def _row_to_beleid(row) -> BudgetBeleid:
    m = dict(row)
    return BudgetBeleid(
        periode_dagen=m["periode_dagen"],
        anker=db.aware(m["anker"]),
        actief=m["actief"],
        updated_by=m["updated_by"],
        updated=db.aware(m["updated"]),
    )


async def ensure_seeded(settings: Settings | None = None) -> None:
    """Zet bij de allereerste start de beleidsrij en per rol een budget uit de env (idempotent).

    Daarna zijn de tabellen de waarheid: een beheerder past ze aan en de env-waarden doen niets meer.
    Zelfde afspraak als bij de modelprofielen. Per rol apart, zodat een rol die er later bij komt ook
    een rij krijgt.
    """
    s = settings or get_settings()
    now = _utcnow()
    async with db.get_engine().begin() as conn:
        bestaat = (await conn.execute(
            select(func.count()).select_from(db.budget_beleid)
        )).scalar() or 0
        if not bestaat:
            await conn.execute(insert(db.budget_beleid).values(
                id=_BELEID_ID,
                periode_dagen=s.token_budget_dagen,
                # Het anker is het moment van seeden. Vanaf hier telt elk venster; dat maakt de eerste
                # resetdatum meteen noembaar zonder dat iemand iets hoeft in te stellen.
                anker=now,
                actief=True,
                updated_by="seed",
                updated=now,
            ))
        aanwezig = set((await conn.execute(select(db.budget_rol.c.rol))).scalars().all())
        for rol in ROLLEN:
            if rol not in aanwezig:
                await conn.execute(insert(db.budget_rol).values(
                    rol=rol, tokens=s.token_budget, updated_by="seed", updated=now,
                ))


async def get_beleid() -> BudgetBeleid:
    """Het huidige beleid; valt terug op de defaults als er (nog) geen rij is."""
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.budget_beleid).where(db.budget_beleid.c.id == _BELEID_ID)
        )).mappings().first()
    return _row_to_beleid(row) if row is not None else BudgetBeleid()


async def zet_beleid(
    *, periode_dagen: int, actief: bool, anker: datetime | None = None, actor: str = "",
) -> BudgetBeleid:
    """Werk het beleid bij. `anker` weglaten laat het staan – dat is bijna altijd wat je wilt.

    Het anker verschuiven verplaatst ieders venster (en dus ieders resetdatum) in één klap; dat is
    een aparte, bewuste handeling en geen bijvangst van een andere periode.
    """
    if periode_dagen < 1:
        raise ValueError("De resetperiode is minimaal één dag.")
    now = _utcnow()
    waarden = {"periode_dagen": periode_dagen, "actief": actief, "updated_by": actor, "updated": now}
    if anker is not None:
        waarden["anker"] = anker
    async with db.get_engine().begin() as conn:
        oud = (await conn.execute(
            select(db.budget_beleid.c.periode_dagen, db.budget_beleid.c.actief)
            .where(db.budget_beleid.c.id == _BELEID_ID)
        )).mappings().first()
        await _audit(
            conn, ACTIE_BELEID, door=actor, oud=dict(oud) if oud is not None else None,
            nieuw={"periode_dagen": periode_dagen, "actief": actief,
                   "anker": anker.isoformat() if anker is not None else None},
        )
        res = await conn.execute(
            update(db.budget_beleid).where(db.budget_beleid.c.id == _BELEID_ID).values(**waarden)
        )
        if res.rowcount == 0:
            # Nog niet geseed (bv. een verse test-DB): maak de rij alsnog. `waarden` draagt het
            # anker alleen als de aanroeper het meegaf; anders wordt het `now`.
            waarden.setdefault("anker", now)
            await conn.execute(insert(db.budget_beleid).values(id=_BELEID_ID, **waarden))
    return await get_beleid()


# --- budget per rol ------------------------------------------------------------

async def rolbudgetten() -> list[RolBudget]:
    """Het budget van elke rol. Een rol zonder rij (nog niet geseed) staat op de seedwaarde."""
    async with db.get_engine().connect() as conn:
        rijen = {r["rol"]: r for r in (await conn.execute(select(db.budget_rol))).mappings().all()}
    return [
        RolBudget(
            rol=rol, tokens=rijen[rol]["tokens"], updated_by=rijen[rol]["updated_by"],
            updated=db.aware(rijen[rol]["updated"]),
        ) if rol in rijen else RolBudget(rol=rol, tokens=get_settings().token_budget)
        for rol in ROLLEN
    ]


async def zet_rolbudget(rol: str, tokens: int, *, actor: str) -> RolBudget:
    """Zet het budget van een rol. Het geldt meteen voor iedereen met die rol."""
    if rol not in ROLLEN:
        raise ValueError(f"Onbekende rol: {rol}")
    if tokens < 1:
        raise ValueError("Een budget is minimaal één token.")
    now = _utcnow()
    waarden = {"tokens": tokens, "updated_by": actor, "updated": now}
    async with db.get_engine().begin() as conn:
        oud = (await conn.execute(
            select(db.budget_rol.c.tokens).where(db.budget_rol.c.rol == rol)
        )).scalar()
        await _audit(conn, ACTIE_ROLBUDGET, door=actor, doel=rol, oud=oud, nieuw=tokens)
        res = await conn.execute(update(db.budget_rol).where(db.budget_rol.c.rol == rol).values(**waarden))
        if res.rowcount == 0:
            await conn.execute(insert(db.budget_rol).values(rol=rol, **waarden))
    return RolBudget(rol=rol, tokens=tokens, updated_by=actor, updated=now)


# --- het venster ---------------------------------------------------------------

def venster_start(beleid: BudgetBeleid, nu: datetime | None = None) -> datetime:
    """Begin van het venster waarin `nu` valt: anker + n × periode.

    Vóór het anker (kan bij een handmatig verschoven anker) is het venster het anker zelf – dan telt
    er nog niets mee en staat de teller op nul.
    """
    nu = nu or _utcnow()
    periode = timedelta(days=max(1, beleid.periode_dagen))
    verstreken = nu - beleid.anker
    if verstreken.total_seconds() < 0:
        return beleid.anker
    n = int(verstreken // periode)
    return beleid.anker + n * periode


def venster_einde(beleid: BudgetBeleid, nu: datetime | None = None) -> datetime:
    """Wanneer de teller weer op nul staat – de resetdatum die de gebruiker te zien krijgt."""
    return venster_start(beleid, nu) + timedelta(days=max(1, beleid.periode_dagen))


# --- boeken --------------------------------------------------------------------

async def boek(
    userid: str,
    *,
    bron: str,
    model: str = "",
    invoer: int = 0,
    uitvoer: int = 0,
    cache_lees: int = 0,
    cache_schrijf: int = 0,
    gesprek_id: str = "",
    run_id: str = "",
) -> bool:
    """Schrijf één verbruiksregel. Geeft False als er niets te boeken viel of het al geboekt was.

    **Idempotent op (`run_id`, `bron`)**: een agent-beurt kan zijn verbruik opnieuw melden (een
    herhaalde SSE-afsluiting, een retry van de client) en dat mag niet dubbel tellen. Zonder
    `run_id` – zoals bij de verbindingstest – is er niets te ontdubbelen en wordt altijd geboekt.
    """
    userid = (userid or "").strip().lower()
    totaal = invoer + uitvoer + cache_lees + cache_schrijf
    if not userid or totaal <= 0:
        return False

    now = _utcnow()
    async with db.get_engine().begin() as conn:
        if run_id:
            # Check-then-insert binnen dezelfde transactie, net als bij `voeg_bericht_toe`. Geen
            # unieke index: `reconcile_schema` voegt die op een bestaande tabel niet toe.
            al = (await conn.execute(
                select(func.count()).select_from(db.token_verbruik).where(
                    db.token_verbruik.c.run_id == run_id,
                    db.token_verbruik.c.bron == bron,
                )
            )).scalar() or 0
            if al:
                return False
        await conn.execute(insert(db.token_verbruik).values(
            userid=userid, bron=bron, model=model,
            invoer=invoer, uitvoer=uitvoer,
            cache_lees=cache_lees, cache_schrijf=cache_schrijf,
            gesprek_id=gesprek_id or None, run_id=run_id or None,
            tijdstip=now,
        ))
    logger.info(
        "verbruik geboekt",
        extra={"categorie": "functioneel", "actie": "verbruik_geboekt", "userid": userid,
               "bron": bron, "model": model, "verbruikt": totaal, "run_id": run_id},
    )
    return True


# --- stand ---------------------------------------------------------------------

async def _gebruikt(userid: str, vanaf: datetime) -> int:
    kolommen = db.token_verbruik.c
    som = func.sum(kolommen.invoer + kolommen.uitvoer + kolommen.cache_lees + kolommen.cache_schrijf)
    async with db.get_engine().connect() as conn:
        return (await conn.execute(
            select(som).where(kolommen.userid == userid, kolommen.tijdstip >= vanaf)
        )).scalar() or 0


async def _budget_van(userid: str) -> tuple[int, str]:
    """Het budget van deze gebruiker en zijn rol. Alleen de rol bepaalt het.

    Elke keer vers uit de tabel, dus een rolwissel werkt meteen door. Geen account (een boeking op een
    tokenlabel) of geen rolrij betekent de seedwaarde.
    """
    gebruikers, rollen = db.users, db.budget_rol
    async with db.get_engine().connect() as conn:
        rij = (await conn.execute(
            select(gebruikers.c.role, rollen.c.tokens)
            .select_from(gebruikers.outerjoin(rollen, rollen.c.rol == gebruikers.c.role))
            .where(gebruikers.c.userid == userid)
        )).first()
    rol, tokens = rij if rij is not None else ("", None)
    return (tokens if tokens is not None else get_settings().token_budget), rol


async def reset_in_venster(userid: str, venster: datetime) -> datetime | None:
    """De laatste reset van deze gebruiker binnen het venster dat op `venster` begint."""
    a = db.budget_audit.c
    async with db.get_engine().connect() as conn:
        moment = (await conn.execute(
            select(func.max(a.tijdstip)).where(
                a.actie == ACTIE_RESET, a.doel == userid, a.tijdstip >= venster,
            )
        )).scalar()
    return db.aware(moment) if moment is not None else None


def _maak_stand(userid: str, gebruikt: int, budget: int, rol: str, beleid: BudgetBeleid,
                *, gereset_op: datetime | None = None, gereset_door: str = "",
                nu: datetime | None = None) -> Verbruiksstand:
    percentage = min(VOL, int(gebruikt * 100 / budget)) if budget > 0 else VOL
    vol = budget > 0 and gebruikt >= budget
    return Verbruiksstand(
        userid=userid,
        gebruikt=gebruikt,
        budget=budget,
        percentage=percentage,
        resterend=max(0, budget - gebruikt),
        reset_op=venster_einde(beleid, nu),
        waarschuwing=percentage >= WAARSCHUWINGSDREMPEL,
        # Staat de begrenzing uit, dan blijft de meter gewoon lopen maar houdt niets iemand tegen.
        geblokkeerd=bool(beleid.actief and vol),
        actief=beleid.actief,
        rol=rol,
        gereset_op=gereset_op,
        gereset_door=gereset_door,
    )


async def stand(userid: str, beleid: BudgetBeleid | None = None) -> Verbruiksstand:
    """Waar deze gebruiker staat in het huidige venster."""
    userid = (userid or "").strip().lower()
    beleid = beleid or await get_beleid()
    venster = venster_start(beleid)
    gereset_op = await reset_in_venster(userid, venster)
    gebruikt = await _gebruikt(userid, gereset_op or venster)
    budget, rol = await _budget_van(userid)
    return _maak_stand(userid, gebruikt, budget, rol, beleid, gereset_op=gereset_op)


async def reset_verbruik(userid: str, *, door: str) -> Verbruiksstand:
    """Geef een gebruiker zijn volledige budget terug voor de rest van dit venster.

    Het journaal blijft zoals het is: er komt alleen een rij in `budget_audit`, met de stand van vlak
    ervoor, en de som begint vanaf dat moment. Wat daarna geboekt wordt telt weer mee, ook als het een
    beurt is die al liep. Het einde van het venster verandert niet.
    """
    userid = (userid or "").strip().lower()
    voor = await stand(userid)
    async with db.get_engine().begin() as conn:
        await _audit(conn, ACTIE_RESET, door=door, doel=userid, gebruikt=voor.gebruikt, budget=voor.budget)
    return await stand(userid)


async def standen() -> list[Verbruiksstand]:
    """De stand van alle gebruikers, de zwaarste verbruiker eerst.

    Vaste queries in plaats van `stand()` per gebruiker: dat houdt het beheerscherm ook bij een
    groeiende groep snel.
    """
    beleid = await get_beleid()
    vanaf = venster_start(beleid)
    k = db.token_verbruik.c
    a = db.budget_audit.c
    som = func.sum(k.invoer + k.uitvoer + k.cache_lees + k.cache_schrijf)
    resets = (
        select(a.doel, func.max(a.tijdstip).label("op"))
        .where(a.actie == ACTIE_RESET, a.tijdstip >= vanaf)
        .group_by(a.doel)
        .subquery()
    )
    async with db.get_engine().connect() as conn:
        verbruik = {
            r[0]: r[1] or 0
            for r in (await conn.execute(
                select(k.userid, som)
                .select_from(db.token_verbruik.outerjoin(resets, resets.c.doel == k.userid))
                .where(k.tijdstip >= vanaf, or_(resets.c.op.is_(None), k.tijdstip >= resets.c.op))
                .group_by(k.userid)
            )).all()
        }
        # Oud naar nieuw: de laatste reset van iemand overschrijft de eerdere.
        laatste_reset = {
            doel: (tijdstip, door)
            for doel, tijdstip, door in (await conn.execute(
                select(a.doel, a.tijdstip, a.door)
                .where(a.actie == ACTIE_RESET, a.tijdstip >= vanaf)
                .order_by(a.tijdstip, a.id)
            )).all()
        }
        gebruikers = (await conn.execute(select(db.users.c.userid, db.users.c.role))).all()
    per_rol = {r.rol: r.tokens for r in await rolbudgetten()}
    uit = []
    for userid, rol in gebruikers:
        gereset_op, gereset_door = laatste_reset.get(userid, (None, ""))
        uit.append(_maak_stand(
            userid, verbruik.get(userid, 0), per_rol.get(rol, get_settings().token_budget), rol, beleid,
            gereset_op=db.aware(gereset_op), gereset_door=gereset_door,
        ))
    return sorted(uit, key=lambda s: (-s.gebruikt, s.userid))
