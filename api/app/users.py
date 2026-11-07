"""Service-laag over de login-accounts in de database.

Verantwoordelijkheden:
  - Wachtwoord-hashing (bcrypt) + verificatie (constant-tijd via bcrypt zelf).
  - `verify_credentials`: **userid** + wachtwoord (+ optionele TOTP) → `User` of een reden-code,
    gebruikt door de auth-router waar de BFF (Auth.js) op inlogt. Inloggen gaat uitsluitend met de
    userid; `email` is een verplicht, uniek registratiegegeven (geen inlog-identiteit).
  - Eenmalige registratie: `needs_setup`/`bootstrap_admin` maken de allereerste beheerder zolang
    de tabel leeg is; daarna sluit die route.
  - Admin-CRUD voor gebruikersbeheer in /beheer, met de beleidsgaranties (laatste actieve
    beheerder mag niet verdwijnen).
  - 2FA (TOTP): koppelen (`begin_2fa`, met het wachtwoord), bevestigen (`activate_2fa`) en losmaken
    (`disable_2fa`). Het secret staat versleuteld (Fernet, zie secrets_crypto). Optioneel, behalve voor
    een beheerder: zonder 2FA geen beheer (`moet_2fa_koppelen`).
  - Herstel bij een verloren authenticator: herstelcodes (`maak_herstelcodes`) en een reset door een
    andere beheerder (`reset_2fa`).

Het wachtwoord-hash en het versleutelde TOTP-secret blijven binnen deze laag; de routers geven ze
nooit terug.
"""

from __future__ import annotations

import base64
import asyncio
import hashlib
import hmac
import json
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

import bcrypt
import pyotp
from fastapi import HTTPException, status
from sqlalchemy import delete, func, insert, or_, select, text, update

from . import db
from .secrets_crypto import crypto_beschikbaar, decrypt, decrypt_ttl, encrypt
from .user import ROLLEN, User, _utcnow

T = TypeVar("T")

# TTL's voor de stateless auth-tokens (Fernet stempelt zelf de timestamp).
_LOGIN_TICKET_TTL_S = 5 * 60            # login-ticket: 5 min tussen wachtwoord- en 2FA-stap
_TRUSTED_DEVICE_TTL_S = 30 * 24 * 3600  # trusted device: 30 dagen 2FA overslaan

# Issuer-naam in de authenticator-app (bij het scannen van de QR zichtbaar als "Wetsanalyse").
_TOTP_ISSUER = "Wetsanalyse"

# Herstelcodes: tien stuks van 80 bits, dus sha256 volstaat (zoals bij de API-tokens) en bcrypt zou
# per poging alleen tien keer de kost zijn.
_HERSTELCODE_AANTAL = 10
_HERSTELCODE_BYTES = 10
_HERSTELCODE_TEKENS = 16  # base32 van 10 bytes, zonder opvulling
_BASE32 = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")

# Userid: 3–64 tekens, kleine letters/cijfers en . _ - (genormaliseerd lowercase).
_USERID_RE = re.compile(r"^[a-z0-9._-]{3,64}$")


class UserError(ValueError):
    """Ongeldige gebruiker-operatie (onbekend, dubbel, laatste beheerder, ongeldige rol, e.d.)."""


class TotpActiefError(UserError):
    """Een nieuwe 2FA-koppeling terwijl 2FA aanstaat: eerst uitzetten, met een code."""


def moet_2fa_koppelen(user: User) -> bool:
    """Staat dit account onder de 2FA-plicht en voldoet het nog niet?

    Bewust afgeleide toestand en geen controle bij elke ingang: `/setup`, promotie, een nieuw account
    en een goedgekeurde aanvraag vallen zo vanzelf onder dezelfde regel. De webapp houdt zo'n
    beheerder buiten het beheer (`proxy()` in de BFF), maar het account werkt verder als analist,
    want koppelen vraagt een sessie.
    """
    return user.role == "beheerder" and not user.totp_enabled


def _norm_userid(userid: str) -> str:
    return userid.strip().lower()


def _norm_email(email: str) -> str:
    return email.strip().lower()


def _row_to_user(row) -> User:
    m = dict(row)
    return User(
        userid=m["userid"],
        email=m["email"],
        password_hash=m["password_hash"],
        role=m["role"],
        totp_secret_enc=m["totp_secret_enc"],
        totp_enabled=m["totp_enabled"],
        active=m["active"],
        sessions_valid_from=db.aware(m["sessions_valid_from"]),
        created=db.aware(m["created"]),
        updated=db.aware(m["updated"]),
    )


# --- wachtwoord-hashing --------------------------------------------------------

def hash_password(plain: str) -> str:
    # bcrypt kapt op 72 bytes; afdoende voor wachtwoorden. Hash bevat de salt.
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("ascii"))
    except ValueError:
        return False


# bcrypt kost op deze replica's honderden milliseconden CPU en laat de GIL los. Op de event loop zou elke
# inlogpoging, ook een anonieme, alle andere verzoeken stilzetten. Daarom een eigen kleine pool, met een grens op
# de wachtrij: anders verplaatst de wachtrij het probleem alleen en wacht de echte gebruiker achter een golf pogingen.
_BCRYPT_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bcrypt")
_BCRYPT_MAX_WACHTEND = 20
_bcrypt_wachtend = 0


async def _in_bcrypt_pool(fn: Callable[..., T], *args) -> T:
    global _bcrypt_wachtend
    if _bcrypt_wachtend >= _BCRYPT_MAX_WACHTEND:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Het is even druk; probeer het zo opnieuw.",
                            headers={"Retry-After": "5"})
    _bcrypt_wachtend += 1
    try:
        return await asyncio.get_running_loop().run_in_executor(_BCRYPT_POOL, fn, *args)
    finally:
        _bcrypt_wachtend -= 1


async def hash_wachtwoord(plain: str) -> str:
    return await _in_bcrypt_pool(hash_password, plain)


async def controleer_wachtwoord(plain: str, hashed: str) -> bool:
    return await _in_bcrypt_pool(verify_password, plain, hashed)


# Vaste dummy-hash om bij een onbekende/inactieve gebruiker toch de bcrypt-kost te betalen
# (constant-tijd responspad), zodat login-timing geen "bestaat + actief"-oracle wordt. Eén keer
# bij import berekend.
_DUMMY_HASH = hash_password("x")


def genereer_wachtwoord() -> str:
    """Tijdelijk wachtwoord bij aanmaken/resetten door een beheerder (eenmalig getoond)."""
    return secrets.token_urlsafe(12)


# --- lezen ---------------------------------------------------------------------

async def get_user(userid: str) -> User | None:
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.users).where(db.users.c.userid == _norm_userid(userid))
        )).mappings().first()
    return _row_to_user(row) if row is not None else None


async def get_user_by_email(email: str) -> User | None:
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.users).where(db.users.c.email == _norm_email(email))
        )).mappings().first()
    return _row_to_user(row) if row is not None else None


async def list_users() -> list[User]:
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(db.users).order_by(db.users.c.userid))).mappings().all()
    return [_row_to_user(r) for r in rows]


async def _count() -> int:
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(func.count()).select_from(db.users))).scalar() or 0


async def _aantal_actieve_beheerders() -> int:
    async with db.get_engine().connect() as conn:
        return (await conn.execute(
            select(func.count()).select_from(db.users).where(
                db.users.c.role == "beheerder", db.users.c.active.is_(True)
            )
        )).scalar() or 0


async def needs_setup() -> bool:
    """True zolang er nog geen enkel account is (de eenmalige-registratie-route is dan open)."""
    return await _count() == 0


# --- credential-verificatie ----------------------------------------------------

def _nu() -> float:
    """De klok voor TOTP. Een functie, zodat de tests de tijd kunnen laten verstrijken."""
    return time.time()


def _totp_stap(user: User, code: str) -> int | None:
    """De tijdstap waarvoor deze code geldt, of None. Eén stap ervoor en erna telt mee: dat vangt
    klok-drift van ±30 s op (hetzelfde venster als `valid_window=1` in pyotp)."""
    if not user.totp_secret_enc:
        return None
    totp = pyotp.TOTP(decrypt(user.totp_secret_enc))
    nu = int(_nu()) // totp.interval
    code = code.strip()
    for stap in (nu - 1, nu, nu + 1):
        if hmac.compare_digest(totp.generate_otp(stap), code):
            return stap
    return None


async def _verbruik_totp(user: User, code: str) -> bool:
    """Klopt de code, én is hij nog niet gebruikt? Dan legt dit hem vast als gebruikt.

    Zonder dit bleef een code zo'n 90 seconden herbruikbaar: wie hem afkeek (over de schouder, uit
    een log, via een phishingpagina die hem doorgeeft) kon er binnen dat venster zelf mee inloggen.
    Het vastleggen is één voorwaardelijke UPDATE, zodat twee gelijktijdige pogingen met dezelfde
    code er nooit allebei doorkomen: alleen de eerste verhoogt de stap.
    """
    stap = _totp_stap(user, code)
    if stap is None:
        return False
    kolom = db.users.c.totp_laatste_stap
    async with db.get_engine().begin() as conn:
        res = await conn.execute(
            update(db.users)
            .where(db.users.c.userid == user.userid, or_(kolom.is_(None), kolom < stap))
            .values(totp_laatste_stap=stap)
        )
    return res.rowcount == 1


# --- herstelcodes ---------------------------------------------------------------

def _norm_herstelcode(code: str) -> str | None:
    """De kale code als de invoer de vorm van een herstelcode heeft, anders None.

    De vorm kiest de route: een herstelcode raakt de Fernet-sleutel niet, dus hij werkt ook als het
    TOTP-secret door een geroteerde `LLM_CONFIG_SECRET` niet meer te lezen is.
    """
    kaal = code.strip().upper().replace("-", "").replace(" ", "")
    if len(kaal) != _HERSTELCODE_TEKENS or not _BASE32.issuperset(kaal):
        return None
    return kaal


def _herstelcode_hash(userid: str, kaal: str) -> str:
    return hashlib.sha256(f"{userid}|{kaal}".encode()).hexdigest()


def _nieuwe_herstelcode() -> str:
    kaal = base64.b32encode(secrets.token_bytes(_HERSTELCODE_BYTES)).decode("ascii")
    return "-".join(kaal[i:i + 4] for i in range(0, _HERSTELCODE_TEKENS, 4))


async def _vervang_herstelcodes(conn, userid: str) -> list[str]:
    """Vervang de hele set binnen de transactie van de aanroeper; geeft de nieuwe codes (eenmalig)."""
    codes = [_nieuwe_herstelcode() for _ in range(_HERSTELCODE_AANTAL)]
    nu = _utcnow()
    await conn.execute(delete(db.herstelcodes).where(db.herstelcodes.c.userid == userid))
    await conn.execute(insert(db.herstelcodes), [
        {"userid": userid, "code_hash": _herstelcode_hash(userid, _norm_herstelcode(c)), "created": nu}
        for c in codes
    ])
    return codes


async def aantal_herstelcodes(userid: str) -> int:
    async with db.get_engine().connect() as conn:
        return (await conn.execute(
            select(func.count()).select_from(db.herstelcodes)
            .where(db.herstelcodes.c.userid == _norm_userid(userid))
        )).scalar() or 0


async def _verbruik_herstelcode(user: User, kaal: str) -> bool:
    """Eén voorwaardelijke DELETE: van twee gelijktijdige pogingen met dezelfde code haalt er één het."""
    async with db.get_engine().begin() as conn:
        res = await conn.execute(
            delete(db.herstelcodes).where(
                db.herstelcodes.c.userid == user.userid,
                db.herstelcodes.c.code_hash == _herstelcode_hash(user.userid, kaal),
            )
        )
    return res.rowcount == 1


async def _verbruik_tweede_factor(user: User, code: str) -> str | None:
    """Verbruik een TOTP-code of een herstelcode. Geeft "totp", "herstelcode" of None."""
    kaal = _norm_herstelcode(code)
    if kaal is not None:
        return "herstelcode" if await _verbruik_herstelcode(user, kaal) else None
    return "totp" if await _verbruik_totp(user, code) else None


# --- stateless auth-tokens (login-ticket + trusted device) ---------------------
#
# Beide zijn Fernet-tokens (hergebruiken de LLM-master-key; 2FA vereist die toch al). Er is GEEN
# serverstate: het login-ticket draagt de al-geverifieerde userid naar het aparte 2FA-scherm zodat
# het wachtwoord daar niet nodig is; het trusted-device-token slaat de 2FA-prompt 30 dagen over en
# is gebonden aan sha256(password_hash + totp_secret_enc) – wijzigt het wachtwoord of gaat 2FA uit,
# dan verandert die binding en is het token vanzelf ongeldig (geen revocatielijst nodig).

def maak_login_ticket(userid: str) -> str | None:
    """Kortlevend bewijs 'wachtwoord geverifieerd voor userid X'. None als er geen master key is."""
    if not crypto_beschikbaar():
        return None
    return encrypt(json.dumps({"t": "ticket", "userid": userid}))


def lees_login_ticket(token: str | None) -> str | None:
    """Userid uit een geldig, niet-verlopen login-ticket; anders None."""
    return _lees_ticket(token, "ticket")


def maak_2fa_ticket(userid: str) -> str | None:
    """Kortlevend bewijs 'wachtwoord én 2FA geverifieerd voor userid X'.

    Bestaat omdat een TOTP-code nu maar één keer geldt. Het aparte 2FA-scherm verifieert de code
    (`/v1/auth/verify` via de BFF-route `login-2fa`), en daarna zet Auth.js de sessie met een
    tweede `/verify` – die de code dan niet opnieuw kan gebruiken. Dit ticket draagt de geslaagde
    eerste controle naar de tweede. Zelfde TTL als het login-ticket.
    """
    if not crypto_beschikbaar():
        return None
    return encrypt(json.dumps({"t": "2fa", "userid": userid}))


def lees_2fa_ticket(token: str | None) -> str | None:
    """Userid uit een geldig, niet-verlopen 2FA-ticket; anders None."""
    return _lees_ticket(token, "2fa")


def _lees_ticket(token: str | None, soort: str) -> str | None:
    if not token:
        return None
    plain = decrypt_ttl(token, _LOGIN_TICKET_TTL_S)
    if not plain:
        return None
    try:
        data = json.loads(plain)
    except ValueError:
        return None
    return data.get("userid") if data.get("t") == soort else None


def _device_bind(user: User) -> str:
    """Bindwaarde die verandert bij wachtwoordwijziging of 2FA-uit → maakt een trusted-token dan
    automatisch ongeldig."""
    basis = f"{user.password_hash or ''}|{user.totp_secret_enc or ''}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def maak_trusted_device(user: User) -> str | None:
    """30-daags token dat op dit apparaat de 2FA-prompt overslaat. None zonder master key."""
    if not crypto_beschikbaar():
        return None
    return encrypt(json.dumps({"t": "trusted", "userid": user.userid, "bind": _device_bind(user)}))


async def valideer_trusted_device(token: str | None) -> str | None:
    """Userid als het trusted-device-token geldig, niet-verlopen en nog gebonden is (user actief,
    2FA aan, bind-match); anders None."""
    if not token:
        return None
    plain = decrypt_ttl(token, _TRUSTED_DEVICE_TTL_S)
    if not plain:
        return None
    try:
        data = json.loads(plain)
    except ValueError:
        return None
    if data.get("t") != "trusted" or not data.get("userid"):
        return None
    user = await get_user(data["userid"])
    if user is None or not user.active or not user.totp_enabled:
        return None
    if data.get("bind") != _device_bind(user):
        return None
    return user.userid


async def _aanvraag_status(userid: str, password: str) -> str:
    """Reden-code voor een inlogpoging op een userid die (nog) geen account is.

    Wie via het portaal toegang heeft aangevraagd kreeg zijn voorgestelde userid te zien. Probeert
    hij daarmee in te loggen, dan is "onbekende gebruiker" onbehulpzaam. We vertellen dat de
    aanvraag nog loopt – maar **alleen bij het juiste wachtwoord**, zodat dit geen middel wordt om
    te ontdekken welke aanvragen er liggen.

    Voor een afgewezen aanvraag is er niets te melden: die is verwijderd, dus dit pad geeft dan
    gewoon "invalid".
    """
    from . import registraties  # lokaal: registraties importeert deze module

    aanvraag = await registraties.openstaand_voor_userid(userid)
    if aanvraag is None or not await controleer_wachtwoord(password, aanvraag.password_hash):
        return "invalid"
    return "aanvraag_open"


async def verify_credentials(
    userid: str, password: str, totp: str | None = None,
    *, ticket: str | None = None, trusted_token: str | None = None,
) -> tuple[User | None, str]:
    """Valideer inloggegevens (uitsluitend op userid). Geeft (user, "ok") of (None, reden).

    Reden-codes: "invalid" (onbekend/inactief/verkeerd wachtwoord – bewust niet onderscheiden om
    niets te lekken), "totp_required" (wachtwoord klopt, maar 2FA staat aan en de code ontbreekt
    of is onjuist) en "aanvraag_open" (er is nog geen account, maar wel een openstaande
    zelfregistratie-aanvraag met dit voorgestelde userid – zie `_aanvraag_status`).
    Geslaagd is "ok", of "ok_totp"/"ok_herstelcode" als daarvoor zojuist een code is verbruikt: dan
    geeft de route een 2FA-ticket mee (`maak_2fa_ticket`), omdat diezelfde code geen tweede keer geldt.

    Twee alternatieve bewijzen naast het wachtwoord:
    - `ticket`: een geldig login-ticket voor deze userid telt als wachtwoord-bewijs, een geldig
      2FA-ticket als bewijs van wachtwoord én tweede factor (voor het aparte
      2FA-scherm, dat het wachtwoord niet vasthoudt);
    - `trusted_token`: een geldig trusted-device-token slaat bij een 2FA-account de TOTP-stap over.
    """
    user = await get_user(userid)
    # Een 2FA-ticket bewijst wachtwoord én tweede factor (de code is al gebruikt, zie
    # `maak_2fa_ticket`); een login-ticket alleen het wachtwoord.
    tweede_factor_ok = ticket is not None and lees_2fa_ticket(ticket) == userid
    # Wachtwoord-bewijs via een geldig ticket voor DEZE userid, anders via het wachtwoord.
    ticket_ok = tweede_factor_ok or (ticket is not None and lees_login_ticket(ticket) == userid)
    if user is None or not user.active:
        if not ticket_ok:
            # Constant-tijd: betaal de bcrypt-kost ook bij een onbekende/inactieve user.
            await controleer_wachtwoord(password, _DUMMY_HASH)
        if user is None:
            return None, await _aanvraag_status(userid, password)
        return None, "invalid"
    if not ticket_ok and not await controleer_wachtwoord(password, user.password_hash):
        return None, "invalid"
    if user.totp_enabled:
        if await valideer_trusted_device(trusted_token) == userid:
            return user, "ok"  # vertrouwd apparaat → 2FA overgeslagen
        if tweede_factor_ok:
            return user, "ok"  # de code is net al gecontroleerd (en verbruikt)
        factor = await _verbruik_tweede_factor(user, totp) if totp else None
        if factor is None:
            return None, "totp_required"
        return user, f"ok_{factor}"
    return user, "ok"


# --- validatie + insert --------------------------------------------------------

def _valideer_userid(userid: str) -> str:
    norm = _norm_userid(userid)
    if not _USERID_RE.match(norm):
        raise UserError("Ongeldige userid (3–64 tekens: kleine letters, cijfers, . _ -).")
    return norm


def _valideer_email(email: str) -> str:
    norm = _norm_email(email)
    if not norm or "@" not in norm:
        raise UserError("Ongeldig e-mailadres.")
    return norm


async def insert_user_met_hash(userid: str, email: str, password_hash: str, *, role: str) -> User:
    """Maak een account met een AL berekende bcrypt-hash.

    Bestaat voor de goedkeuring van een zelfregistratie: de aanvrager koos zijn wachtwoord bij de
    aanvraag, dus de hash ligt er al en er hoeft geen tijdelijk wachtwoord te worden rondgestuurd.
    `_insert_user` is de gewone weg (hasht zelf) en loopt hier doorheen.
    """
    if role not in ROLLEN:
        raise UserError(f"Onbekende rol: {role!r}")
    norm_id = _valideer_userid(userid)
    norm_email = _valideer_email(email)
    # Vooraf-checks op de twee unieke velden, voor duidelijke meldingen (de DB-constraints zijn de
    # uiteindelijke vangrail bij een race).
    if await get_user(norm_id) is not None:
        raise UserError(f"Userid bestaat al: {norm_id}")
    if await get_user_by_email(norm_email) is not None:
        raise UserError(f"E-mailadres bestaat al: {norm_email}")
    now = _utcnow()
    user = User(
        userid=norm_id, email=norm_email, password_hash=password_hash,
        role=role, created=now, updated=now,
    )
    try:
        async with db.get_engine().begin() as conn:
            await conn.execute(insert(db.users).values(
                userid=user.userid, email=user.email, password_hash=user.password_hash,
                role=user.role, totp_secret_enc=None, totp_enabled=False, active=True,
                created=now, updated=now,
            ))
    except Exception as e:  # IntegrityError op dubbele userid/email (race)
        raise UserError("Userid of e-mailadres bestaat al.") from e
    return user


async def _insert_user(userid: str, email: str, password: str, *, role: str) -> User:
    return await insert_user_met_hash(userid, email, await hash_wachtwoord(password), role=role)


# --- eenmalige registratie (bootstrap) -----------------------------------------

async def bootstrap_admin(userid: str, email: str, password: str) -> User:
    """Maak de allereerste beheerder – alleen zolang de tabel leeg is (anders UserError)."""
    if await _count() > 0:
        raise UserError("Er bestaat al een account; registratie is gesloten.")
    return await _insert_user(userid, email, password, role="beheerder")


# --- admin-CRUD ----------------------------------------------------------------

async def create_user(userid: str, email: str, role: str = "analist") -> tuple[User, str]:
    """Maak een account met een tijdelijk wachtwoord (eenmalig teruggegeven aan de beheerder)."""
    tijdelijk = genereer_wachtwoord()
    user = await _insert_user(userid, email, tijdelijk, role=role)
    return user, tijdelijk


async def _require_user(userid: str) -> User:
    user = await get_user(userid)
    if user is None:
        raise UserError(f"Onbekende gebruiker: {userid}")
    return user


async def set_role(userid: str, role: str) -> User:
    if role not in ROLLEN:
        raise UserError(f"Onbekende rol: {role!r}")
    user = await _require_user(userid)
    # Laatste actieve beheerder niet kunnen degraderen.
    if user.role == "beheerder" and role != "beheerder" and user.active:
        if await _aantal_actieve_beheerders() <= 1:
            raise UserError("Kan de laatste actieve beheerder niet degraderen.")
    await _update(user.userid, role=role)
    user.role = role
    return user


async def set_active(userid: str, active: bool) -> User:
    user = await _require_user(userid)
    if user.role == "beheerder" and user.active and not active:
        if await _aantal_actieve_beheerders() <= 1:
            raise UserError("Kan de laatste actieve beheerder niet deactiveren.")
    await _update(user.userid, active=active)
    user.active = active
    return user


async def patch_user(userid: str, *, role: str | None = None, active: bool | None = None) -> User:
    """Combineer een rol- en/of active-wijziging in ÉÉN transactie, met de 'laatste actieve
    beheerder'-invariant getoetst op de EIND-toestand. Zo kan een gelijktijdige rol+active-patch
    (of twee parallelle patches) de laatste beheerder niet via twee losse checks laten verdwijnen
    (TOCTOU). Op Postgres serialiseert een advisory xact-lock de check+write; op SQLite (tests) zijn
    writes al geserialiseerd.
    """
    if role is not None and role not in ROLLEN:
        raise UserError(f"Onbekende rol: {role!r}")
    user = await _require_user(userid)
    waarden: dict = {}
    if role is not None:
        waarden["role"] = role
    if active is not None:
        waarden["active"] = active
    if not waarden:
        return user
    nieuw_role = role if role is not None else user.role
    nieuw_active = active if active is not None else user.active
    was_actieve_beheerder = user.role == "beheerder" and user.active
    wordt_actieve_beheerder = nieuw_role == "beheerder" and nieuw_active
    waarden["updated"] = _utcnow()
    async with db.get_engine().begin() as conn:
        if was_actieve_beheerder and not wordt_actieve_beheerder:
            if db.get_engine().url.get_backend_name() == "postgresql":
                await conn.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": "actieve-beheerders"}
                )
            aantal = (await conn.execute(
                select(func.count()).select_from(db.users).where(
                    db.users.c.role == "beheerder", db.users.c.active.is_(True)
                )
            )).scalar() or 0
            if aantal <= 1:
                raise UserError("Kan de laatste actieve beheerder niet degraderen of deactiveren.")
        await conn.execute(update(db.users).where(db.users.c.userid == userid).values(**waarden))
    user.role, user.active = nieuw_role, nieuw_active
    return user


async def reset_password(userid: str) -> tuple[User, str]:
    """Zet een nieuw tijdelijk wachtwoord (eenmalig teruggegeven) en revoke alle sessies."""
    user = await _require_user(userid)
    tijdelijk = genereer_wachtwoord()
    await _update(user.userid, password_hash=await hash_wachtwoord(tijdelijk), sessions_valid_from=_utcnow())
    return user, tijdelijk


async def change_own_password(userid: str, current: str, nieuw: str) -> None:
    """Self-service wachtwoordwijziging: verifieer het huidige wachtwoord en zet een nieuw. Bumpt de
    sessie-epoch zodat bestaande sessies op andere apparaten vervallen (het acterende apparaat logt
    zelf opnieuw in)."""
    user = await _require_user(userid)
    if not user.active or not await controleer_wachtwoord(current, user.password_hash):
        raise UserError("Huidig wachtwoord onjuist.")
    await _update(user.userid, password_hash=await hash_wachtwoord(nieuw), sessions_valid_from=_utcnow())


async def delete_user(userid: str) -> None:
    user = await _require_user(userid)
    if user.role == "beheerder" and user.active and await _aantal_actieve_beheerders() <= 1:
        raise UserError("Kan de laatste actieve beheerder niet verwijderen.")
    async with db.get_engine().begin() as conn:
        # Een nieuw account met dezelfde userid mag de accounttokens van het oude niet erven.
        await conn.execute(
            update(db.api_tokens).where(db.api_tokens.c.userid == user.userid).values(active=False)
        )
        await conn.execute(delete(db.herstelcodes).where(db.herstelcodes.c.userid == user.userid))
        await conn.execute(delete(db.users).where(db.users.c.userid == user.userid))


async def _update(userid: str, **waarden) -> None:
    waarden["updated"] = _utcnow()
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.users).where(db.users.c.userid == userid).values(**waarden))


# --- 2FA (TOTP) ----------------------------------------------------------------

async def begin_2fa(userid: str, password: str) -> str:
    """Genereer een (nog niet actief) TOTP-secret en geef de otpauth://-URI voor de QR-code.

    Het secret wordt versleuteld opgeslagen maar `totp_enabled` blijft False tot `activate_2fa`
    één geldige code bevestigt. Opnieuw aanroepen vervangt een nog niet bevestigd secret.

    Koppelen vraagt het wachtwoord: een sessie alleen is geen bewijs, want wie er één kaapt zou de
    eigenaar anders met een eigen authenticator buitensluiten. Actieve 2FA blijft onaangeroerd
    (`TotpActiefError`); uitzetten kan alleen met een code (`disable_2fa`). Die weigering zit in de
    UPDATE zelf, zodat een gelijktijdige `activate_2fa` er niet tussendoor valt.
    """
    user = await _require_user(userid)
    if not user.active or not await controleer_wachtwoord(password, user.password_hash):
        raise UserError("Huidig wachtwoord onjuist.")
    secret = pyotp.random_base32()
    async with db.get_engine().begin() as conn:
        res = await conn.execute(
            update(db.users)
            .where(db.users.c.userid == user.userid, db.users.c.totp_enabled.is_(False))
            .values(totp_secret_enc=encrypt(secret), updated=_utcnow())
        )
    if res.rowcount != 1:
        raise TotpActiefError("2FA staat al aan. Schakel het eerst uit om een nieuwe app te koppelen.")
    # In de authenticator toont het account de userid; issuer = Wetsanalyse.
    return pyotp.TOTP(secret).provisioning_uri(name=user.userid, issuer_name=_TOTP_ISSUER)


async def activate_2fa(userid: str, code: str) -> list[str]:
    """Bevestig de koppeling. Geeft de herstelcodes terug: die verlaten de server alleen hier."""
    user = await _require_user(userid)
    if not user.totp_secret_enc:
        raise UserError("Geen 2FA-aanmelding gestart; vraag eerst een nieuwe code aan.")
    if not await _verbruik_totp(user, code):
        raise UserError("Onjuiste of verlopen code.")
    async with db.get_engine().begin() as conn:
        await conn.execute(
            update(db.users).where(db.users.c.userid == user.userid)
            .values(totp_enabled=True, updated=_utcnow())
        )
        return await _vervang_herstelcodes(conn, user.userid)


async def disable_2fa(userid: str, code: str) -> None:
    """Zet 2FA uit met een TOTP-code of een herstelcode. Dat laatste is de weg bij een nieuwe telefoon:
    koppelen kan pas weer als 2FA uit staat. Een beheerder mag dit ook, en valt dan onder
    `moet_2fa_koppelen` tot er opnieuw een app gekoppeld is."""
    user = await _require_user(userid)
    if not user.totp_enabled:
        raise UserError("2FA staat niet aan.")
    if await _verbruik_tweede_factor(user, code) is None:
        raise UserError("Onjuiste of verlopen 2FA-code.")
    await _wis_2fa(user.userid)


async def _wis_2fa(userid: str, **extra) -> None:
    async with db.get_engine().begin() as conn:
        await conn.execute(
            update(db.users).where(db.users.c.userid == userid)
            .values(totp_secret_enc=None, totp_enabled=False, updated=_utcnow(), **extra)
        )
        await conn.execute(delete(db.herstelcodes).where(db.herstelcodes.c.userid == userid))


async def vervang_herstelcodes(userid: str, code: str) -> list[str]:
    """Een nieuwe set, op vertoon van een TOTP-code of een herstelcode. De oude vervalt."""
    user = await _require_user(userid)
    if not user.totp_enabled:
        raise UserError("2FA staat niet aan.")
    if await _verbruik_tweede_factor(user, code) is None:
        raise UserError("Onjuiste of verlopen 2FA-code.")
    async with db.get_engine().begin() as conn:
        return await _vervang_herstelcodes(conn, user.userid)


async def reset_2fa(userid: str, *, door: str) -> User:
    """Haal 2FA van een ander account, voor wie zijn authenticator én codes kwijt is.

    Niet op jezelf: dat zou 2FA uitzetten zonder code, en daarvoor zijn de herstelcodes er. De sessies
    van het account vervallen; trusted devices doen dat vanzelf, want hun binding bevat het secret.
    """
    user = await _require_user(userid)
    if user.userid == _norm_userid(door):
        raise UserError("Je eigen 2FA reset je niet; gebruik een herstelcode.")
    if not user.totp_enabled:
        raise UserError("2FA staat niet aan.")
    await _wis_2fa(user.userid, sessions_valid_from=_utcnow())
    user.totp_enabled, user.totp_secret_enc = False, None
    return user
