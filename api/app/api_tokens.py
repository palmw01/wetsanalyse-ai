"""Service-laag over genereerbare API-tokens (DB-backed) voor programmatische admin-toegang.

Naast de statische env-admin-tokens (`WETSANALYSE_ADMIN_TOKENS`) kan een beheerder via /beheer een
API-token **genereren** – bijvoorbeeld voor de admin-MCP. Alleen de **sha256-hash** van het token
wordt bewaard (tokens zijn hoog-entropie, dus geen bcrypt nodig); de plaintext wordt één keer bij
aanmaken teruggegeven en nergens opgeslagen. Intrekken zet `active=False`.

`verify()` is het aanknopingspunt voor `auth.require_admin`: het hasht het aangeboden token en zoekt
een actief token; bij een treffer werkt het `last_used` best-effort bij en geeft het een admin-id
terug (voor de audit). Tokens worden nooit gelogd.

Naast die admin-tokens (scope `admin`) bestaan **accounttokens** (scope `gebruiker`, prefix `wa_pat_`):
die horen bij één account, verlopen, en openen `/v1/admin` nooit. Ze bewijzen alleen wie je bent:
`verify_gebruiker()` is de weg waarlangs de BFF ze inwisselt voor een gewone sessie, en wat die sessie
mag volgt uit het account. De twee scopes kruisen niet: `verify()` kijkt alleen naar `admin`.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import insert, select, update

from . import db, users
from .user import _utcnow

# Herkenbaar prefix + 256 bits entropie (token_urlsafe(32)). Het volledige token verlaat de server
# alleen bij aanmaken; daarna leeft alleen de hash in de DB.
TOKEN_PREFIX = "wa_admin_"
GEBRUIKER_PREFIX = "wa_pat_"
SCOPE_ADMIN = "admin"
SCOPE_GEBRUIKER = "gebruiker"
GELDIGHEID_GEBRUIKER = timedelta(days=90)
_PREFIX_SHOW = 16  # zoveel tekens bewaren we als herkenbaar (niet-bruikbaar) prefix voor de UI


class ApiTokenError(ValueError):
    """Ongeldige token-operatie (onbekend/ingetrokken)."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _row_to_dict(row) -> dict:
    m = dict(row)
    return {
        "id": m["id"],
        "label": m["label"],
        "token_prefix": m["token_prefix"],
        "scope": m["scope"],
        "active": bool(m["active"]),
        "created_by": m["created_by"],
        "created": db.aware(m["created"]),
        "last_used": db.aware(m["last_used"]) if m["last_used"] is not None else None,
        "userid": m.get("userid"),
        "verloopt": db.aware(m.get("verloopt")),
    }


async def create(label: str, *, created_by: str = "", scope: str = SCOPE_ADMIN) -> tuple[dict, str]:
    """Genereer een nieuw token. Geeft (record-zonder-geheim, plaintext-token). Plaintext één keer."""
    return await _maak(TOKEN_PREFIX, label, created_by=created_by, scope=scope)


async def create_gebruiker(label: str, userid: str, *, created_by: str = "") -> tuple[dict, str]:
    """Genereer een token dat als `userid` inlogt. Een onbekend of inactief account krijgt er geen."""
    user = await users.get_user(userid)
    if user is None or not user.active:
        raise ApiTokenError(f"Onbekend of inactief account: {userid}")
    return await _maak(GEBRUIKER_PREFIX, label, created_by=created_by, scope=SCOPE_GEBRUIKER,
                       userid=user.userid, verloopt=_utcnow() + GELDIGHEID_GEBRUIKER)


async def _maak(prefix: str, label: str, *, created_by: str, scope: str, userid: str | None = None,
                verloopt=None) -> tuple[dict, str]:
    plaintext = prefix + secrets.token_urlsafe(32)
    now = _utcnow()
    row = {
        "id": uuid4().hex,
        "label": (label or "").strip()[:128],
        "token_hash": _hash(plaintext),
        "token_prefix": plaintext[:_PREFIX_SHOW],
        "scope": scope,
        "active": True,
        "created_by": created_by,
        "created": now,
        "last_used": None,
        "userid": userid,
        "verloopt": verloopt,
    }
    async with db.get_engine().begin() as conn:
        await conn.execute(insert(db.api_tokens).values(**row))
    return _row_to_dict(row), plaintext


async def list_tokens() -> list[dict]:
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(
            select(db.api_tokens).order_by(db.api_tokens.c.created.desc())
        )).mappings().all()
    return [_row_to_dict(r) for r in rows]


async def revoke(token_id: str) -> None:
    async with db.get_engine().begin() as conn:
        res = await conn.execute(
            update(db.api_tokens).where(db.api_tokens.c.id == token_id).values(active=False)
        )
    if res.rowcount == 0:
        raise ApiTokenError(f"Onbekend token: {token_id}")


async def _touch_last_used(token_id: str) -> None:
    """Best-effort `last_used`-bijwerking, geïsoleerd van de auth-beslissing: een schrijffout mag een
    al-gevalideerd token nooit alsnog ongeldig maken (geen 401 door een metadata-hapering)."""
    try:
        async with db.get_engine().begin() as conn:
            await conn.execute(
                update(db.api_tokens).where(db.api_tokens.c.id == token_id).values(last_used=_utcnow())
            )
    except Exception:  # noqa: BLE001 – puur metadata; stil falen
        pass


async def verify(presented: str | None) -> str | None:
    """Valideer een aangeboden token tegen de actieve DB-tokens. Geeft een admin-id of None.

    De auth-beslissing komt uit een read-only lookup; de `last_used`-update is een aparte, best-effort
    stap (zie `_touch_last_used`) zodat een schrijffout de geldigheid niet ongedaan maakt.
    """
    if not presented or not presented.startswith(TOKEN_PREFIX):
        return None
    token_hash = _hash(presented)
    try:
        async with db.get_engine().connect() as conn:
            row = (await conn.execute(
                select(db.api_tokens).where(
                    db.api_tokens.c.token_hash == token_hash,
                    db.api_tokens.c.active.is_(True),
                    db.api_tokens.c.scope == SCOPE_ADMIN,
                )
            )).mappings().first()
    except Exception:  # noqa: BLE001 – een DB-hapering mag geen 500 worden; behandel als 'geen match'
        return None
    if row is None:
        return None
    admin_id = f"apitoken:{row['label'] or row['id'][:8]}"
    try:
        await _touch_last_used(row["id"])
    except Exception:  # noqa: BLE001 – dubbele vangnet; de touch is nooit auth-bepalend
        pass
    return admin_id


async def _geldig_account(row) -> users.User | None:
    """Het account achter een accounttoken, als het token en het account allebei nog gelden."""
    if not row["active"] or row["scope"] != SCOPE_GEBRUIKER or not row["userid"]:
        return None
    if row["verloopt"] is None or db.aware(row["verloopt"]) <= _utcnow():
        return None
    user = await users.get_user(row["userid"])
    return user if user is not None and user.active else None


async def verify_gebruiker(presented: str | None) -> dict | None:
    """Valideer een accounttoken. Geeft token-id, userid, e-mail en rol, of None.

    Een fout in de opslag wordt hier geen 'geen match': dan zou een storing eruitzien als een afwijzing.
    """
    if not presented or not presented.startswith(GEBRUIKER_PREFIX):
        return None
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.api_tokens).where(db.api_tokens.c.token_hash == _hash(presented))
        )).mappings().first()
    user = await _geldig_account(row) if row is not None else None
    if user is None:
        return None
    await _touch_last_used(row["id"])
    return {"token_id": row["id"], "userid": user.userid, "email": user.email, "role": user.role}


async def gebruiker_geldig(token_id: str) -> bool:
    """Geldt dit accounttoken nog? De BFF vraagt dit periodiek, zodat intrekken een sessie beëindigt."""
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(
            select(db.api_tokens).where(db.api_tokens.c.id == token_id)
        )).mappings().first()
    return row is not None and await _geldig_account(row) is not None
