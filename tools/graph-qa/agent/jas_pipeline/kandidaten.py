"""Het kandidaatmodel (ADR-001 PR 5): wat een detector vindt, nog zonder juridisch oordeel.

Een kandidaat is een **bronspan plus bewijs**. Hij zegt welke JAS-klassen mogelijk zijn
(`possible_classes`, uit de detectieprofielen) en waarom (`evidence`), en welke andere grenzen er
in aanmerking komen (`span_options`). Of hij een annotatie wordt, beslist een latere stap; tot die
tijd staat hij op `UNHANDLED`, en de dekkingsboekhouding (PR 10) eist dat elke kandidaat daar
vanaf komt.

Twee identiteiten, met opzet:

- `id` is een hash van bron-IRI en offsets. Dezelfde span krijgt in elke run hetzelfde id, welke
  detector hem ook als eerste vond – daarop koppelen fusie, provenance en de stabiliteitsmeting.
- `label` ("C001", "C002", …) wordt na de fusie in bronvolgorde uitgedeeld en is wat een model in
  een prompt ziet. Het model antwoordt met het label; code vertaalt terug naar het id. Een model
  typt dus nooit een span en nooit een offset.
"""
from __future__ import annotations

import hashlib
from enum import Enum

from bronmodel import Span
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..jas_klassen import GELDIGE_JAS_KLASSEN

GEEN_ANNOTATIE = "Geen annotatie"


class CandidateStatus(str, Enum):
    """Waar een kandidaat eindigt. Alleen `UNHANDLED` is een tussentoestand."""

    UNHANDLED = "UNHANDLED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class _Vast(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BronSpan(_Vast):
    """`bronmodel.Span` in pydantic-vorm, zodat hij in de agent-state en in JSON past."""

    bron_iri: str
    start: int = Field(ge=0)
    eind: int = Field(gt=0)
    tekst: str
    bron_hash: str

    @classmethod
    def van(cls, span: Span) -> BronSpan:
        return cls(bron_iri=span.bron_iri, start=span.start, eind=span.eind, tekst=span.tekst,
                   bron_hash=span.bron_hash)

    def sleutel(self) -> tuple[str, int, int]:
        return (self.bron_iri, self.start, self.eind)


class Evidence(_Vast):
    """Eén waarneming die de kandidaat ondersteunt; herleidbaar tot detector, regel en taalanalyse."""

    detector: str                      # "temporeel", "conditioneel", …
    code: str                          # "TEMPORAL_DURATION", "CONDITIONAL_CLAUSE", …
    regel: str = ""                    # id uit een detectieprofiel ("jas.tijd.duur"), als die er is
    relatie: str = ""                  # UD-relatie van het kopwoord, als de parse meesprak
    detail: str = ""


class SpanOption(_Vast):
    """Een alternatieve grens voor dezelfde kandidaat; het model kiest er hooguit één van."""

    soort: str                         # "kern", "np", "np_kern", "bijzin", "zin", "regel"
    span: BronSpan


def kandidaat_id(bron_iri: str, start: int, eind: int) -> str:
    return "K" + hashlib.sha256(f"{bron_iri}\x1f{start}\x1f{eind}".encode()).hexdigest()[:12]


class Candidate(_Vast):
    id: str
    span: BronSpan
    possible_classes: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    span_options: tuple[SpanOption, ...] = ()
    status: CandidateStatus = CandidateStatus.UNHANDLED
    label: str = ""                    # "C001"; pas na de fusie gezet
    gedegradeerd: bool = False         # gevonden zonder volledige taalanalyse

    @field_validator("possible_classes")
    @classmethod
    def _klassen(cls, klassen: tuple[str, ...]) -> tuple[str, ...]:
        onbekend = [k for k in klassen if k not in GELDIGE_JAS_KLASSEN]
        if onbekend:
            raise ValueError(f"onbekende JAS-klasse: {onbekend}")
        if not klassen:
            raise ValueError("een kandidaat zonder mogelijke klasse is geen kandidaat")
        return tuple(dict.fromkeys(klassen))          # ontdubbeld, volgorde behouden

    @field_validator("evidence")
    @classmethod
    def _bewijs(cls, bewijs: tuple[Evidence, ...]) -> tuple[Evidence, ...]:
        if not bewijs:
            raise ValueError("een kandidaat zonder bewijs is een gok")
        return bewijs

    @classmethod
    def maak(cls, span: Span, possible_classes: tuple[str, ...] | list[str],
             evidence: list[Evidence] | tuple[Evidence, ...],
             span_options: list[SpanOption] | tuple[SpanOption, ...] = (),
             gedegradeerd: bool = False) -> Candidate:
        return cls(id=kandidaat_id(span.bron_iri, span.start, span.eind), span=BronSpan.van(span),
                   possible_classes=tuple(possible_classes), evidence=tuple(evidence),
                   span_options=tuple(span_options), gedegradeerd=gedegradeerd)

    def toegestane_beslissingen(self) -> tuple[str, ...]:
        """Wat een classifier over deze kandidaat mag zeggen: een van zijn klassen, of niets."""
        return (*self.possible_classes, GEEN_ANNOTATIE)


class DetectorResult(_Vast):
    """De opbrengst van één detector op één bronnode, inclusief wat hij níet kon."""

    detector: str
    versie: str
    bron_iri: str
    kandidaten: tuple[Candidate, ...] = ()
    overgeslagen: bool = False         # draaide niet (bv. geen parse beschikbaar)
    reden: str = ""                    # waarom overgeslagen of gedegradeerd


def label_kandidaten(kandidaten: list[Candidate] | tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    """Deel labels uit in bronvolgorde (node, start, langste eerst). Deterministisch."""
    geordend = sorted(kandidaten, key=lambda k: (k.span.bron_iri, k.span.start, -k.span.eind, k.id))
    return tuple(k.model_copy(update={"label": f"C{i:03d}"}) for i, k in enumerate(geordend, 1))
