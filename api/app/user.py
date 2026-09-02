"""Domeinmodel voor een login-account (plain Pydantic; persistentie via de store, zie users.py).

De API is de identiteitsbron van de webapp: hier leven de accounts, het wachtwoord-hash en het
(optionele) TOTP-secret. De frontend (Auth.js) houdt alleen de browsersessie. Het wachtwoord-hash
en het versleutelde TOTP-secret verlaten de server nooit via de API – responses tonen alleen
afgeleide booleans (`totp_enabled`, `active`).
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

# De twee rollen: een beheerder mag /beheer (incl. gebruikersbeheer), een analist de rest.
ROLLEN = ("beheerder", "analist")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(BaseModel):
    userid: str
    email: str = ""
    password_hash: str = ""
    role: str = "analist"
    # Versleuteld TOTP-secret (Fernet-token). None ⇒ geen 2FA gekoppeld.
    totp_secret_enc: str | None = None
    totp_enabled: bool = False
    active: bool = True
    # Sessie-epoch: JWT-sessies met een inlogmoment vóór deze tijd zijn ongeldig (revocatie bij
    # wachtwoordwijziging/-reset). None ⇒ nooit gewijzigd → geen revocatie.
    sessions_valid_from: datetime | None = None

    created: datetime = Field(default_factory=_utcnow)
    updated: datetime = Field(default_factory=_utcnow)


# De twee statussen die een zelfregistratie-aanvraag kan hebben. "afgewezen" staat er bewust NIET
# bij: afwijzen verwijdert de rij, zodat het e-mailadres en het volgnummer meteen weer vrij zijn.
REGISTRATIE_STATUSSEN = ("aangevraagd", "goedgekeurd")


class Registratie(BaseModel):
    """Een aanvraag voor een account, in afwachting van (of na) het besluit van een beheerder.

    Dit is nadrukkelijk géén account: zolang de status `aangevraagd` is bestaat er geen rij in
    `users` en kan er niet mee worden ingelogd. Het wachtwoord-hash ligt hier al klaar zodat de
    goedgekeurde gebruiker meteen met zijn eigen wachtwoord kan inloggen.
    """

    id: int = 0
    voornaam: str = ""
    achternaam: str = ""
    email: str = ""
    userid_voorstel: str = ""
    password_hash: str = ""
    status: str = "aangevraagd"
    # Afwijsreden: gaat naar het security-log, niet naar de database – de rij verdwijnt immers.
    reden: str | None = None
    # De uiteindelijk toegekende userid; pas gevuld bij goedkeuring.
    userid: str | None = None
    besloten_door: str | None = None
    besloten_op: datetime | None = None

    created: datetime = Field(default_factory=_utcnow)
    updated: datetime = Field(default_factory=_utcnow)
