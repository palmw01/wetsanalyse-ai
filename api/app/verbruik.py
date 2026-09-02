"""Service-laag voor het tokenbudget: boeken, optellen, begrenzen.

Het dragende idee: **verbruik is een journaal, de stand is een som.** Er wordt nergens een teller
opgeslagen en nooit iets gereset. Elke LLM-call levert één rij in `token_verbruik`; hoeveel iemand
nu verbruikt heeft is `sum(...) WHERE userid = ? AND tijdstip >= venster_start`.

Dat is geen stijlkeuze maar de reden dat drie dingen kloppen:

- **Werk weggooien geeft geen tokens terug.** Een gesprek of annotatiedocument verwijderen wist zijn
  eigen rijen (`gesprek_store.verwijder_gesprek`, `annotatie_store.verwijder_document`), maar raakt
  het journaal niet: `userid` is de enige harde sleutel, `gesprek_id`/`run_id` zijn losse metadata.
- **De reset kan niet mislukken.** Er is geen periodieke taak die de tellers nulzet; het vensterbegin
  wordt uit het anker gerekend. Draait de dienst een week niet, dan klopt de stand daarna nog steeds.
- **Elk getal is navraagbaar**, tot op de call.

Wat meetelt: invoer + uitvoer + cache_lees + cache_schrijf, dus het **volle promptvolume**. Een
cache-read kost bij de provider ~0,1×, maar het is wél tekst die het model verwerkte. Het budget
begrenst dus gebruik, niet de factuur; de vier getallen staan apart in de tabel zodat een gewogen
variant later een rekenregel is en geen migratie.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, insert, select, update

from . import db
from .config import Settings, get_settings
from .user import _utcnow
from .verbruik_contracts import VOL, WAARSCHUWINGSDREMPEL, BudgetBeleid, Verbruiksstand

logger = logging.getLogger(__name__)

# Er is precies één beleidsrij.
_BELEID_ID = 1


# --- beleid --------------------------------------------------------------------

def _row_to_beleid(row) -> BudgetBeleid:
    m = dict(row)
    return BudgetBeleid(
        tokens=m["tokens"],
        periode_dagen=m["periode_dagen"],
        anker=db.aware(m["anker"]),
        actief=m["actief"],
        updated_by=m["updated_by"],
        updated=db.aware(m["updated"]),
    )


async def ensure_seeded(settings: Settings | None = None) -> None:
    """Zet bij de allereerste start één beleidsrij uit de env-waarden (idempotent).

    Daarna is de tabel de waarheid: een beheerder past het beleid aan via `/v1/admin/budget` en de
    env-waarden doen niets meer. Zelfde afspraak als bij de modelprofielen.
    """
    async with db.get_engine().begin() as conn:
        bestaat = (await conn.execute(
            select(func.count()).select_from(db.budget_beleid)
        )).scalar() or 0
        if bestaat:
            return
        s = settings or get_settings()
        now = _utcnow()
        await conn.execute(insert(db.budget_beleid).values(
            id=_BELEID_ID,
            tokens=s.token_budget,
            periode_dagen=s.token_budget_dagen,
            # Het anker is het moment van seeden. Vanaf hier telt elk venster; dat maakt de eerste
            # resetdatum meteen noembaar zonder dat iemand iets hoeft in te stellen.
            anker=now,
            actief=True,
            updated_by="seed",
            updated=now,
        ))


async def get_beleid() -> BudgetBeleid:
    """Het huidige beleid; valt terug op de defaults als er (nog) geen rij is."""
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.budget_beleid).where(db.budget_beleid.c.id == _BELEID_ID)
        )).mappings().first()
    return _row_to_beleid(row) if row is not None else BudgetBeleid()


async def zet_beleid(
    *, tokens: int, periode_dagen: int, actief: bool, anker: datetime | None = None, actor: str = "",
) -> BudgetBeleid:
    """Werk het beleid bij. `anker` weglaten laat het staan – dat is bijna altijd wat je wilt.

    Het anker verschuiven verplaatst ieders venster (en dus ieders resetdatum) in één klap; dat is
    een aparte, bewuste handeling en geen bijvangst van "budget omhoog".
    """
    if tokens < 0:
        raise ValueError("Een budget kan niet negatief zijn.")
    if periode_dagen < 1:
        raise ValueError("De resetperiode is minimaal één dag.")
    now = _utcnow()
    waarden = {
        "tokens": tokens, "periode_dagen": periode_dagen, "actief": actief,
        "updated_by": actor, "updated": now,
    }
    if anker is not None:
        waarden["anker"] = anker
    async with db.get_engine().begin() as conn:
        res = await conn.execute(
            update(db.budget_beleid).where(db.budget_beleid.c.id == _BELEID_ID).values(**waarden)
        )
        if res.rowcount == 0:
            # Nog niet geseed (bv. een verse test-DB): maak de rij alsnog. `waarden` draagt het
            # anker alleen als de aanroeper het meegaf; anders wordt het `now`.
            waarden.setdefault("anker", now)
            await conn.execute(insert(db.budget_beleid).values(id=_BELEID_ID, **waarden))
    return await get_beleid()


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


async def _eigen_budget(userid: str) -> int | None:
    async with db.get_engine().connect() as conn:
        return (await conn.execute(
            select(db.users.c.token_budget).where(db.users.c.userid == userid)
        )).scalar()


def _maak_stand(userid: str, gebruikt: int, budget: int, beleid: BudgetBeleid,
                *, eigen: bool, nu: datetime | None = None) -> Verbruiksstand:
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
        eigen_budget=eigen,
    )


async def stand(userid: str, beleid: BudgetBeleid | None = None) -> Verbruiksstand:
    """Waar deze gebruiker staat in het huidige venster."""
    userid = (userid or "").strip().lower()
    beleid = beleid or await get_beleid()
    eigen = await _eigen_budget(userid)
    gebruikt = await _gebruikt(userid, venster_start(beleid))
    budget = eigen if eigen is not None else beleid.tokens
    return _maak_stand(userid, gebruikt, budget, beleid, eigen=eigen is not None)


async def standen() -> list[Verbruiksstand]:
    """De stand van alle gebruikers, de zwaarste verbruiker eerst.

    Eén query voor het verbruik en één voor de budgetten, in plaats van `stand()` per gebruiker:
    dat scheelt twee queries per rij en houdt het beheerscherm ook bij een groeiende groep snel.
    """
    beleid = await get_beleid()
    vanaf = venster_start(beleid)
    kolommen = db.token_verbruik.c
    som = func.sum(kolommen.invoer + kolommen.uitvoer + kolommen.cache_lees + kolommen.cache_schrijf)
    async with db.get_engine().connect() as conn:
        verbruik = {
            r[0]: r[1] or 0
            for r in (await conn.execute(
                select(kolommen.userid, som).where(kolommen.tijdstip >= vanaf)
                .group_by(kolommen.userid)
            )).all()
        }
        gebruikers = (await conn.execute(
            select(db.users.c.userid, db.users.c.token_budget)
        )).all()
    standen = [
        _maak_stand(
            userid,
            verbruik.get(userid, 0),
            eigen if eigen is not None else beleid.tokens,
            beleid,
            eigen=eigen is not None,
        )
        for userid, eigen in gebruikers
    ]
    return sorted(standen, key=lambda s: (-s.gebruikt, s.userid))
