"""Noodherstel: de 2FA van de enige beheerder wissen, buiten de webapp om.

De gewone wegen staan in `users`: een herstelcode, of een reset door een andere beheerder met 2FA
(`reset_2fa`, via het beheer). Wie de enige beheerder is en zowel de authenticator als de codes kwijt is,
komt daar niet meer langs. Dit is de uitweg: `azure-infra` → actie `2fa-herstel` start dit als eenmalige job
in de straat, met het api-image dat er draait (zie `deploy/azure/herstel-2fa.bicep`).

Bewust geen route: de api krijgt geen achterdeur. Wie dit kan starten, heeft al toegang tot de workflow en
daarmee tot de secrets van de straat. Inloggen vraagt daarna nog steeds het wachtwoord, en het beheer gaat
pas weer open als het account opnieuw een app koppelt.

De weigeringen zijn het punt: dit is er alleen voor als er niemand anders is. Is er nog een actieve beheerder
met 2FA, dan hoort de reset via die beheerder te gaan, en dan doet deze module niets.

Starten: `python -m app.herstel_2fa`, met `HERSTEL_USERID` (het account) en `HERSTEL_DOOR` (wie het doet,
voor het log). De uitkomst staat op de regels `UITKOMST: <code>` en, bij een weigering, `UITLEG: <tekst>`,
zonder userid: de workflow haalt alleen die regels op, en zijn log is openbaar.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from sqlalchemy import func, select

from . import db, users

logger = logging.getLogger(__name__)

GERESET = "gereset"

# De codes van een weigering, met de uitleg die de workflow toont. Geen ervan noemt een account.
WEIGERINGEN = {
    "ongeldige_invoer": "De userid of de uitvoerder ontbreekt of is ongeldig.",
    "onbekend": "Dit account bestaat niet in deze straat.",
    "geen_beheerder": "Dit account is geen beheerder. Een andere beheerder reset het via het beheer.",
    "inactief": "Dit account is gedeactiveerd.",
    "geen_2fa": "Dit account heeft geen 2FA aanstaan; er valt niets te herstellen.",
    "andere_beheerder": (
        "Er is nog een andere actieve beheerder met 2FA. Die reset dit account in het beheer, bij Gebruikers."
    ),
}


class Weigering(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def _andere_beheerders_met_2fa(userid: str) -> int:
    async with db.get_engine().connect() as conn:
        return (await conn.execute(
            select(func.count()).select_from(db.users).where(
                db.users.c.role == "beheerder",
                db.users.c.active.is_(True),
                db.users.c.totp_enabled.is_(True),
                db.users.c.userid != userid,
            )
        )).scalar_one()


async def herstel(userid: str, *, door: str) -> None:
    """Wis de 2FA van `userid`, of weiger met een `Weigering`. Het effect is precies `users.reset_2fa`."""
    userid = (userid or "").strip().lower()
    if not users._USERID_RE.match(userid) or not (door or "").strip():
        raise Weigering("ongeldige_invoer")
    user = await users.get_user(userid)
    if user is None:
        raise Weigering("onbekend")
    if user.role != "beheerder":
        raise Weigering("geen_beheerder")
    if not user.active:
        raise Weigering("inactief")
    if not user.totp_enabled:
        raise Weigering("geen_2fa")
    if await _andere_beheerders_met_2fa(user.userid):
        raise Weigering("andere_beheerder")
    # `door` draagt een voorvoegsel met een dubbele punt (`github:<login>`). Dat is nooit een geldige userid,
    # dus de regel "niet op jezelf" in `reset_2fa` kan hier niet per ongeluk afgaan of omzeild worden.
    await users.reset_2fa(user.userid, door=door)


async def _draai(userid: str, door: str) -> str:
    from .config import get_settings

    db.init_engine(get_settings().database_url)
    try:
        await herstel(userid, door=door)
        return GERESET
    finally:
        await db.dispose_engine()


def main() -> int:
    from . import observability
    from .config import get_settings

    observability.setup(get_settings())
    userid = os.environ.get("HERSTEL_USERID", "")
    door = os.environ.get("HERSTEL_DOOR", "")
    try:
        uitkomst = asyncio.run(_draai(userid, door))
    except Weigering as w:
        logger.warning(
            "2FA-noodherstel geweigerd",
            extra={"categorie": "security", "actie": "2fa_noodherstel_geweigerd", "reden": w.code, "door": door},
        )
        print(f"UITKOMST: {w.code}", flush=True)
        print(f"UITLEG: {WEIGERINGEN[w.code]}", flush=True)
        return 2
    logger.warning(
        "2FA gereset via het noodherstel",
        extra={"categorie": "security", "actie": "2fa_reset", "route": "noodherstel",
               "userid": userid.strip().lower(), "door": door},
    )
    print(f"UITKOMST: {uitkomst}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
