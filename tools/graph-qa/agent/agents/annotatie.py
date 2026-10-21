"""De annotatie-agent, voor zover hij een taak op een werkgebied heeft (F3c).

Eén bepaling annoteren blijft de annotatieketen in de graaf (`annoteer → emit`, ADR-001). Wat hier staat is
het werkgebied als geheel (`werkgebied`) of alleen de bronnen onder de deelvragen (`deelvragen`; met een
aangewezen of genoemde deelvraag alleen die): de getypte vraag levert het voorstel met een bevestiging
(`werkgebied_annotatie.werkgebied_voorstel`), zonder model. Starten doet de bevestiging,
met `bevestigd`: die run annoteert per bepaling een gewone beurt en loopt daarom als eigen stroom
(`werkgebied_annotatie_beurt`), niet als taak in een node.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ..werkgebied_annotatie import werkgebied_voorstel
from . import Context, Uitkomst, geweigerd
from .deelvragen import deelvraag_op_nummer


class Taak(StrEnum):
    WERKGEBIED = "werkgebied"
    DEELVRAGEN = "deelvragen"


MODEL_TAKEN: frozenset[Taak] = frozenset()


class Invoer(BaseModel):
    taak: Taak
    werkgebied_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")
    # Alleen bij `deelvragen`: de aangewezen deelvraag, of "deelvraag 2" uit de vraag.
    deelvraag_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")
    deelvraag_nr: int | None = Field(default=None, ge=1, le=99)


async def voer_uit(invoer: Invoer, ctx: Context) -> Uitkomst:
    if not invoer.werkgebied_id:
        return geweigerd(invoer.taak, "Welk werkgebied wil je laten annoteren? Open het gesprek vanuit het werkgebied; "
                                      "één bepaling annoteren kan ook: noem dan het artikel.")
    if invoer.taak is Taak.WERKGEBIED:
        return await werkgebied_voorstel(ctx, invoer.werkgebied_id)
    did = invoer.deelvraag_id
    if invoer.deelvraag_nr is not None and not did:
        did, zin = await deelvraag_op_nummer(ctx, invoer.werkgebied_id, invoer.deelvraag_nr)
        if not did:
            return geweigerd(invoer.taak, zin)
    return await werkgebied_voorstel(ctx, invoer.werkgebied_id, "deelvragen", did)
