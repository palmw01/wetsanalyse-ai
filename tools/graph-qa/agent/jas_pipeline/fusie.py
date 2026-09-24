"""Kandidaatfusie (ADR-001 PR 8): één kandidaat per span, met al het bewijs.

Meerdere detectoren vinden vaak dezelfde of een overlappende span ('zes weken' als duur én als
naamwoordgroep). De fusie:

- **ontdubbelt** op kandidaat-id (bron + offsets) en voegt bewijs, mogelijke klassen en spanopties
  samen – de volgorde van klassen is die van het eerste bewijs, daarna aanvullingen;
- **verandert nooit een offset**: een kandidaat en zijn opties houden exact hun bronspan;
- **legt relaties vast** tussen kandidaten op dezelfde bron (`bevat` bij nesting, `overlapt` bij
  gedeeltelijke overlap) – JAS staat overlap toe voor verschillende functies, dus niets wordt
  hier weggegooid omdat het overlapt;
- **bewaart wat niet draaide**: overgeslagen detectoren en hun reden gaan mee naar de provenance.

Daarna past `specificiteit.pas_toe` de voorrangsregels van JAS toe, en krijgen de kandidaten hun
labels (C001…). Deterministisch: dezelfde invoer levert byte-voor-byte dezelfde uitvoer.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .kandidaten import Candidate, DetectorResult, label_kandidaten


class Relatie(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    van: str            # kandidaat-id
    naar: str
    soort: str          # "bevat" (van omvat naar) of "overlapt"


class Overgeslagen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detector: str
    bron_iri: str
    reden: str


class Fusie(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kandidaten: tuple[Candidate, ...]
    relaties: tuple[Relatie, ...] = ()
    overgeslagen: tuple[Overgeslagen, ...] = ()
    detectoren: tuple[tuple[str, str], ...] = ()      # (naam, versie), voor de provenance

    def per_id(self) -> dict[str, Candidate]:
        return {k.id: k for k in self.kandidaten}

    def per_label(self) -> dict[str, Candidate]:
        return {k.label: k for k in self.kandidaten}


def _samen(oud: Candidate, nieuw: Candidate) -> Candidate:
    bewijs = tuple(dict.fromkeys((*oud.evidence, *nieuw.evidence)))
    opties = {o.span.sleutel(): o for o in (*oud.span_options, *nieuw.span_options)
              if o.span.sleutel() != oud.span.sleutel()}
    return oud.model_copy(update={
        "possible_classes": tuple(dict.fromkeys((*oud.possible_classes, *nieuw.possible_classes))),
        "evidence": bewijs,
        "span_options": tuple(sorted(opties.values(), key=lambda o: (o.span.start, o.span.eind, o.soort))),
        "gedegradeerd": oud.gedegradeerd and nieuw.gedegradeerd,
    })


def relaties(kandidaten: tuple[Candidate, ...] | list[Candidate]) -> tuple[Relatie, ...]:
    uit = []
    per_bron: dict[str, list[Candidate]] = {}
    for k in kandidaten:
        per_bron.setdefault(k.span.bron_iri, []).append(k)
    for groep in per_bron.values():
        groep = sorted(groep, key=lambda k: (k.span.start, -k.span.eind, k.id))
        for i, a in enumerate(groep):
            for b in groep[i + 1:]:
                if b.span.start >= a.span.eind:
                    break
                if b.span.eind <= a.span.eind:
                    uit.append(Relatie(van=a.id, naar=b.id, soort="bevat"))
                elif (a.span.start, a.span.eind) == (b.span.start, b.span.eind):
                    continue                           # na ontdubbelen onmogelijk
                else:
                    uit.append(Relatie(van=a.id, naar=b.id, soort="overlapt"))
    return tuple(uit)


def fuseer(resultaten: list[DetectorResult]) -> Fusie:
    from .specificiteit import pas_toe

    samen: dict[str, Candidate] = {}
    for r in resultaten:
        for k in r.kandidaten:
            samen[k.id] = _samen(samen[k.id], k) if k.id in samen else _samen(k, k)
    kandidaten = label_kandidaten(pas_toe(tuple(samen.values())))
    return Fusie(
        kandidaten=kandidaten,
        relaties=relaties(kandidaten),
        overgeslagen=tuple(Overgeslagen(detector=r.detector, bron_iri=r.bron_iri, reden=r.reden)
                           for r in resultaten if r.overgeslagen),
        detectoren=tuple(sorted({(r.detector, r.versie) for r in resultaten})),
    )
