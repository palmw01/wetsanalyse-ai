"""De beslistabel van de begrippenketen (ADR-004): van bewijs naar link, non-link of possible link.

Drie uitkomsten, naar Fellegi–Sunter. Er wordt niets opgeteld: een rij kijkt alleen naar welke
richting en sterkte er in het bewijs voorkomen. De rijen worden van boven naar beneden gelezen;
de eerste die past, beslist. Elke beslissing noemt haar rij.

Twee families, omdat het gewicht van bewijs verschilt:

- **zelfde betekenis** (wordt een groep). Sterk tegenbewijs wint altijd. Een kale gelijke term
  is een vraag aan de jurist, geen voorstel: "termijnen" kan twee dingen betekenen.
- **relatie** (kwalificatie, inclusie, uitsluiting, hiërarchie). Zwak bewijs alleen levert géén
  voorstel op: het kopsignaal van een samenstelling zou anders elke "-aanslag" onder "aanslag"
  hangen, terwijl de wet ze als zusters opsomt.

Daarna één regel over families heen: is een paar met een relatie verbonden, dan wordt het geen
groep. Wat de wet als soort of als gelijkgesteld noemt, is per definitie niet hetzelfde begrip.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .model import Besluit, Beslissing, Hypothese, Kandidaat, Polariteit, Sterkte

VERSIE = "1"


@dataclass(frozen=True)
class Profiel:
    """Welke combinaties van richting en sterkte er in het bewijs van een kandidaat zitten."""

    combinaties: frozenset[tuple[Polariteit, Sterkte]]
    codes: frozenset[str]

    @classmethod
    def van(cls, k: Kandidaat) -> Profiel:
        return cls(frozenset((b.polariteit, b.sterkte) for b in k.bewijs),
                   frozenset(b.code for b in k.bewijs))

    def heeft(self, pol: Polariteit, *sterktes: Sterkte) -> bool:
        return any((pol, s) in self.combinaties for s in (sterktes or tuple(Sterkte)))


@dataclass(frozen=True)
class Rij:
    id: str
    voor: str                                  # "zelfde" | "relatie"
    past: Callable[[Profiel], bool]
    besluit: Besluit
    reden: str


S, T, O = Polariteit.STEUN, Polariteit.TEGEN, Polariteit.ONBESLIST
STERK, MIDDEL, ZWAK = Sterkte.STERK, Sterkte.MIDDEL, Sterkte.ZWAK

TABEL: tuple[Rij, ...] = (
    Rij("Z-TEGEN-STERK", "zelfde", lambda p: p.heeft(T, STERK), Besluit.NON_LINK,
        "sterk tegenbewijs: niet hetzelfde begrip"),
    Rij("Z-STERK-SCHOON", "zelfde", lambda p: p.heeft(S, STERK) and not p.heeft(T) and not p.heeft(O),
        Besluit.LINK, "sterk bewijs, niets ertegen"),
    Rij("Z-STERK-MET-TWIJFEL", "zelfde", lambda p: p.heeft(S, STERK), Besluit.POSSIBLE_LINK,
        "sterk bewijs, maar ook tegenbewijs of een open punt"),
    Rij("Z-ANDERS", "zelfde", lambda p: True, Besluit.POSSIBLE_LINK,
        "geen sterk bewijs: een vraag aan de jurist"),
    Rij("R-TEGEN", "relatie", lambda p: p.heeft(T, STERK, MIDDEL), Besluit.NON_LINK,
        "tegenbewijs tegen deze relatie"),
    Rij("R-STERK", "relatie", lambda p: p.heeft(S, STERK) and not p.heeft(T), Besluit.LINK,
        "de wet noemt de relatie zelf"),
    Rij("R-MIDDEL", "relatie", lambda p: p.heeft(S, MIDDEL), Besluit.POSSIBLE_LINK,
        "aanwijzing voor een relatie, niet uit de definitie zelf"),
    Rij("R-TE-ZWAK", "relatie", lambda p: True, Besluit.NON_LINK,
        "alleen zwak bewijs: geen voorstel"),
)
RELATIE_GAAT_VOOR = Rij("Z-RELATIE-GAAT-VOOR", "zelfde", lambda p: True, Besluit.POSSIBLE_LINK,
                        "het paar heeft ook een relatie volgens de wet: geen groep")


def beslis(k: Kandidaat) -> Beslissing:
    familie = "zelfde" if k.hypothese is Hypothese.ZELFDE_BETEKENIS else "relatie"
    p = Profiel.van(k)
    rij = next(r for r in TABEL if r.voor == familie and r.past(p))
    return Beslissing(kandidaat_id=k.id, besluit=rij.besluit, regel=rij.id, reden=rij.reden)


def beslis_alle(kandidaten: list[Kandidaat]) -> dict[str, Beslissing]:
    """Per kandidaat een beslissing; daarna gaat een vastgestelde relatie voor op een groep."""
    uit = {k.id: beslis(k) for k in kandidaten}
    verbonden = {frozenset(k.leden) for k in kandidaten
                 if k.hypothese is not Hypothese.ZELFDE_BETEKENIS and uit[k.id].besluit is Besluit.LINK}
    for k in kandidaten:
        if k.hypothese is Hypothese.ZELFDE_BETEKENIS and uit[k.id].besluit is Besluit.LINK \
                and frozenset(k.leden) in verbonden:
            uit[k.id] = Beslissing(kandidaat_id=k.id, besluit=RELATIE_GAAT_VOOR.besluit,
                                   regel=RELATIE_GAAT_VOOR.id, reden=RELATIE_GAAT_VOOR.reden)
    return uit
