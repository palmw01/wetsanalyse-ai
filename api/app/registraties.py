"""Service-laag voor zelfregistratie met beheerdersgoedkeuring.

Een bezoeker vraagt via het portaal toegang aan: naam, e-mailadres en een zelfgekozen wachtwoord.
Het systeem leidt daaruit een userid af (zie `leid_userid_af`). De aanvraag is géén account – pas
als een beheerder goedkeurt ontstaat er een rij in `users`, met het wachtwoord dat de aanvrager
zelf koos. Zo hoeft de beheerder geen userid te verzinnen en geen tijdelijk wachtwoord door te
geven.

Afwijzen **verwijdert** de aanvraag in plaats van hem af te stempelen: het e-mailadres en het
volgnummer komen zo meteen weer vrij, en de beheerder hoeft er geen tweede handeling voor te doen.
Wat er van de afwijzing overblijft is de regel in het security-log.

Het wachtwoord-hash leeft in deze laag en verlaat de API nooit; `RegistratieOut` in de router toont
het niet.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import delete, func, insert, select, update

from . import db
from .user import REGISTRATIE_STATUSSEN, Registratie, User, _utcnow
from .users import (
    UserError,
    _norm_email,
    _norm_userid,
    _valideer_email,
    get_user,
    get_user_by_email,
    hash_password,
    insert_user_met_hash,
)

# Minimale wachtwoordlengte; gelijk aan de eis op /v1/auth/setup en de client-validatie.
_MIN_WACHTWOORD = 8

# Alles wat niet in een userid mag (het userid-alfabet is [a-z0-9._-]).
_ONGELDIG = re.compile(r"[^a-z0-9]+")

# Zoveel letters van de achternaam gaan in de userid.
_ACHTERNAAM_LETTERS = 4


# --- userid-afleiding ----------------------------------------------------------

def _plat(tekst: str) -> str:
    """Naar het userid-alfabet: diakrieten weg, lowercase, alleen letters en cijfers over."""
    ontleed = unicodedata.normalize("NFKD", tekst or "")
    zonder_accent = "".join(c for c in ontleed if not unicodedata.combining(c))
    return _ONGELDIG.sub("", zonder_accent.lower())


def leid_userid_af(voornaam: str, achternaam: str, volgnummer: int = 1) -> str:
    """De huisvorm: vier letters achternaam + eerste letter voornaam + tweecijferig volgnummer.

    "Willard Palm" → `palmw01`; een tweede Willard Palm (of een andere W. Palm) → `palmw02`.
    Kortere namen leveren gewoon een kortere stam op ("Li Wu" → `liw01`); de userid-regex eist
    minstens drie tekens, wat met het volgnummer altijd gehaald wordt.
    """
    stam = _plat(achternaam)[:_ACHTERNAAM_LETTERS] + _plat(voornaam)[:1]
    if not stam:
        raise UserError("Uit deze naam is geen gebruikersnaam af te leiden.")
    # Boven de 99 wordt het volgnummer gewoon langer (`palmw100`) in plaats van te botsen.
    return f"{stam}{volgnummer:02d}"


async def _userid_bezet(userid: str) -> bool:
    """Bezet zodra een account óf een aanvraag hem claimt.

    Er is geen statusfilter nodig: een afgewezen aanvraag wordt verwijderd, dus elke rij die er nog
    staat houdt zijn volgnummer terecht vast.
    """
    if await get_user(userid) is not None:
        return True
    async with db.get_engine().connect() as conn:
        n = (await conn.execute(
            select(func.count()).select_from(db.registratie_aanvragen).where(
                db.registratie_aanvragen.c.userid_voorstel == userid,
            )
        )).scalar() or 0
    return n > 0


async def unieke_userid(voornaam: str, achternaam: str) -> str:
    """`leid_userid_af` met het eerste vrije volgnummer."""
    for volgnummer in range(1, 100):
        kandidaat = leid_userid_af(voornaam, achternaam, volgnummer)
        if not await _userid_bezet(kandidaat):
            return kandidaat
    raise UserError("Er zijn te veel gebruikers met deze naam.")


# --- lezen ---------------------------------------------------------------------

def _row_to_registratie(row) -> Registratie:
    m = dict(row)
    return Registratie(
        id=m["id"],
        voornaam=m["voornaam"],
        achternaam=m["achternaam"],
        email=m["email"],
        userid_voorstel=m["userid_voorstel"],
        password_hash=m["password_hash"],
        status=m["status"],
        reden=m["reden"],
        userid=m["userid"],
        besloten_door=m["besloten_door"],
        besloten_op=db.aware(m["besloten_op"]),
        created=db.aware(m["created"]),
        updated=db.aware(m["updated"]),
    )


async def get(aanvraag_id: int) -> Registratie | None:
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.registratie_aanvragen).where(db.registratie_aanvragen.c.id == aanvraag_id)
        )).mappings().first()
    return _row_to_registratie(row) if row is not None else None


async def get_by_email(email: str) -> Registratie | None:
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.registratie_aanvragen).where(
                db.registratie_aanvragen.c.email == _norm_email(email)
            )
        )).mappings().first()
    return _row_to_registratie(row) if row is not None else None


async def lijst(status: str | None = None) -> list[Registratie]:
    """Aanvragen, oudste eerst (wie het langst wacht staat bovenaan)."""
    q = select(db.registratie_aanvragen).order_by(db.registratie_aanvragen.c.created)
    if status:
        if status not in REGISTRATIE_STATUSSEN:
            raise UserError(f"Onbekende status: {status!r}")
        q = q.where(db.registratie_aanvragen.c.status == status)
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(q)).mappings().all()
    return [_row_to_registratie(r) for r in rows]


async def aantal_open() -> int:
    async with db.get_engine().connect() as conn:
        return (await conn.execute(
            select(func.count()).select_from(db.registratie_aanvragen).where(
                db.registratie_aanvragen.c.status == "aangevraagd"
            )
        )).scalar() or 0


async def openstaand_voor_userid(userid: str) -> Registratie | None:
    """De nog niet beoordeelde aanvraag die deze userid voorstelt, als die er is.

    Voedt de statusmelding bij het inloggen: wie zijn voorgestelde userid al kreeg te zien en
    probeert in te loggen, hoort dat zijn aanvraag nog op goedkeuring wacht. Voor een afgewezen
    aanvraag bestaat die melding niet meer – de rij is dan weg.
    """
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.registratie_aanvragen).where(
                db.registratie_aanvragen.c.userid_voorstel == _norm_userid(userid),
                db.registratie_aanvragen.c.status == "aangevraagd",
            ).order_by(db.registratie_aanvragen.c.created.desc())
        )).mappings().first()
    return _row_to_registratie(row) if row is not None else None


# --- aanvragen -----------------------------------------------------------------

async def maak_aanvraag(voornaam: str, achternaam: str, email: str, wachtwoord: str) -> Registratie:
    """Leg een nieuwe aanvraag vast. UserError bij een dubbel adres of ongeldige invoer."""
    voornaam = (voornaam or "").strip()
    achternaam = (achternaam or "").strip()
    if not voornaam or not achternaam:
        raise UserError("Vul je voor- en achternaam in.")
    if len(voornaam) > 120 or len(achternaam) > 120:
        raise UserError("Naam is te lang.")
    if len(wachtwoord or "") < _MIN_WACHTWOORD:
        raise UserError(f"Kies een wachtwoord van minimaal {_MIN_WACHTWOORD} tekens.")
    norm_email = _valideer_email(email)
    # Vooraf-checks voor een duidelijke melding; de unique-constraints zijn de vangrail bij een race.
    if await get_user_by_email(norm_email) is not None:
        raise UserError("Er bestaat al een account met dit e-mailadres.")
    if await get_by_email(norm_email) is not None:
        raise UserError("Er ligt al een aanvraag voor dit e-mailadres.")

    now = _utcnow()
    aanvraag = Registratie(
        voornaam=voornaam,
        achternaam=achternaam,
        email=norm_email,
        userid_voorstel=await unieke_userid(voornaam, achternaam),
        password_hash=hash_password(wachtwoord),
        status="aangevraagd",
        created=now,
        updated=now,
    )
    try:
        async with db.get_engine().begin() as conn:
            res = await conn.execute(insert(db.registratie_aanvragen).values(
                voornaam=aanvraag.voornaam,
                achternaam=aanvraag.achternaam,
                email=aanvraag.email,
                userid_voorstel=aanvraag.userid_voorstel,
                password_hash=aanvraag.password_hash,
                status="aangevraagd",
                reden=None,
                userid=None,
                besloten_door=None,
                besloten_op=None,
                created=now,
                updated=now,
            ))
    except Exception as e:  # IntegrityError op een dubbel e-mailadres (race)
        raise UserError("Er ligt al een aanvraag voor dit e-mailadres.") from e
    aanvraag.id = int(res.inserted_primary_key[0])
    return aanvraag


# --- besluiten -----------------------------------------------------------------

async def _open_aanvraag(aanvraag_id: int) -> Registratie:
    aanvraag = await get(aanvraag_id)
    if aanvraag is None:
        raise UserError("Onbekende aanvraag.")
    if aanvraag.status != "aangevraagd":
        raise UserError("Deze aanvraag is al afgehandeld.")
    return aanvraag


async def keur_goed(
    aanvraag_id: int, *, userid: str | None = None, role: str = "analist", actor: str = "",
) -> User:
    """Maak het account aan en markeer de aanvraag als goedgekeurd.

    De beheerder mag een andere userid opgeven dan het voorstel. Het account krijgt het wachtwoord
    dat de aanvrager zelf koos (de hash gaat ongewijzigd over), dus hij kan direct inloggen.
    """
    aanvraag = await _open_aanvraag(aanvraag_id)
    gekozen = _norm_userid(userid) if userid else aanvraag.userid_voorstel
    # `insert_user_met_hash` valideert de userid, het e-mailadres en de rol, en gooit UserError bij
    # een botsing – dus vóór we de aanvraag afstempelen.
    user = await insert_user_met_hash(
        gekozen, aanvraag.email, aanvraag.password_hash, role=role,
    )
    now = _utcnow()
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.registratie_aanvragen).where(
            db.registratie_aanvragen.c.id == aanvraag_id
        ).values(
            status="goedgekeurd", userid=user.userid, reden=None,
            besloten_door=actor, besloten_op=now, updated=now,
        ))
    return user


async def wijs_af(aanvraag_id: int, *, reden: str = "", actor: str = "") -> Registratie:
    """Wijs af én verwijder de aanvraag, zodat e-mailadres en volgnummer meteen weer vrij zijn.

    Er blijft dus geen rij achter met een afgewezen-status. Het spoor van de afwijzing – wie, wat,
    waarom – gaat naar het security-log; de router schrijft dat met de teruggegeven `Registratie`.
    """
    aanvraag = await _open_aanvraag(aanvraag_id)
    async with db.get_engine().begin() as conn:
        await conn.execute(
            delete(db.registratie_aanvragen).where(db.registratie_aanvragen.c.id == aanvraag_id)
        )
    aanvraag.reden = (reden or "").strip() or None
    aanvraag.besloten_door = actor
    aanvraag.besloten_op = _utcnow()
    return aanvraag


async def verwijder(aanvraag_id: int) -> None:
    """Ruim een afgehandelde (goedgekeurde) aanvraag op uit het archief.

    Afwijzen verwijdert zelf al; dit is er voor de rijen die als spoor van een goedkeuring blijven
    staan.
    """
    async with db.get_engine().begin() as conn:
        res = await conn.execute(
            delete(db.registratie_aanvragen).where(db.registratie_aanvragen.c.id == aanvraag_id)
        )
    if res.rowcount == 0:
        raise UserError("Onbekende aanvraag.")
