"""Relatievoorstellen tussen markeringen (ADR-011 §*Voorstellen komen later, en eerst zonder model*).

Uit wat de keten van één bepaling al weet – de voorstellen, de kandidaten met hun bewijs, de nesting uit de fusie en
de UD-parse – volgen relaties tussen voorstellen. Geen model, geen geraden offset: een eindpunt is de lijst ankers van
een voorstel, precies zoals het naar de api gaat. De api zet die na het opslaan om naar het element-id
(`annotatie_v2_store.batch`).

Vier regels, in de volgorde van ADR-011, elk met een eigen code (verklaard in `verklaringen.yaml`, sectie `relatie`):

1. **`uitvoer`/`invoer` uit de functiedetector** (`REL_UITVOER_FUNCTIE`, `REL_INVOER_FUNCTIE`). Een afleidingsregel
   met bewijs `CALCULATION_QUANTITY` noemt in `Evidence.detail` de spans `uitkomst` en `invoer`. Een voorstel binnen de
   regel dat zo'n span overlapt (en de andere niet), hoort erbij; van geneste voorstellen telt het binnenste.
   `uitvoer` alleen als het er dan precies één is.
2. **`waarde` uit de nesting** (`REL_WAARDE_NESTING`): een parameterwaarde binnen een tijdsaanduiding die een parameter
   verbijzondert, of een parameter- of variabelewaarde binnen een parameter of variabele. De binnenste ouder telt.
3. **`operator_in` en `operand`** (`REL_OPERATOR_IN_NESTING`, `REL_OPERAND_WOORDVOLGORDE`): een operator in een
   voorwaarde of afleidingsregel; de naaste voorstellen links en rechts binnen die ouder zijn de operanden, met de
   woordvolgorde als `volgorde` (1 = links). Een andere operator ertussen breekt de reeks.
4. **`voorwaarde` uit de aanhechting** (`REL_VOORWAARDE_AANHECHTING`): een voorwaardelijke bijzin (`advcl` met een
   voorwaardelijk `mark`) aan het hoofdpredicaat (`root`) hangt aan de enige rechtsbetrekking of afleidingsregel die dat
   predicaat draagt.

Overal geldt: **bij twijfel geen voorstel.** Twee even goede kandidaten voor één plek, een gedegradeerde parse, een
eindpunt zonder klasse: dan komt er niets. En elk voorstel moet door de catalogus (`jas_relaties.toegestaan`: klassen,
richting, subtype), dezelfde regels die de api daarna nog eens toetst. Kenmerk, tijd en rollen doet deze module niet.

Deterministisch: dezelfde invoer geeft dezelfde lijst, in dezelfde volgorde.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..jas_relaties import toegestaan
from .detectoren.syntactisch import _VOORWAARDELIJK
from .fusie import Fusie
from .kandidaten import Candidate
from .taal import LinguisticAnalysis

VERSIE = "1"

REL_UITVOER_FUNCTIE = "REL_UITVOER_FUNCTIE"
REL_INVOER_FUNCTIE = "REL_INVOER_FUNCTIE"
REL_WAARDE_NESTING = "REL_WAARDE_NESTING"
REL_OPERATOR_IN_NESTING = "REL_OPERATOR_IN_NESTING"
REL_OPERAND_WOORDVOLGORDE = "REL_OPERAND_WOORDVOLGORDE"
REL_VOORWAARDE_AANHECHTING = "REL_VOORWAARDE_AANHECHTING"
#: Alle codes die deze module kan uitgeven; `tests/test_verklaringen.py` eist voor elk een verklaring.
CODES = (REL_UITVOER_FUNCTIE, REL_INVOER_FUNCTIE, REL_WAARDE_NESTING, REL_OPERATOR_IN_NESTING,
         REL_OPERAND_WOORDVOLGORDE, REL_VOORWAARDE_AANHECHTING)

AR, VW, OP, RB = "Afleidingsregel", "Voorwaarde", "Operator", "Rechtsbetrekking"
VAR, PAR, TIJD = "Variabele en variabelewaarde", "Parameter en parameterwaarde", "Tijdsaanduiding"
#: De bewijscodes van de functiedetector die een uitkomst- en een invoerspan noemen (`detectoren/functies.py`).
_FUNCTIE_SPANS = frozenset({"CALCULATION_QUANTITY"})


@dataclass(frozen=True)
class _El:
    """Eén voorstel als eindpunt: klasse, subtype en het ene lokale anker."""

    id: str
    klasse: str
    subtype: str
    bron_iri: str
    start: int
    eind: int
    ankers: tuple
    kandidaat: Candidate | None

    def bevat(self, ander: _El) -> bool:
        return (self.bron_iri == ander.bron_iri and self.start <= ander.start and ander.eind <= self.eind
                and (self.start, self.eind) != (ander.start, ander.eind))

    def overlapt(self, start: int, eind: int) -> bool:
        return self.start < eind and start < self.eind

    @property
    def lengte(self) -> int:
        return self.eind - self.start


def _elementen(voorstellen: list[dict[str, Any]], fusie: Fusie) -> list[_El]:
    """De voorstellen die een eindpunt kunnen zijn: met een klasse en één anker (zo levert de keten ze)."""
    per_id = fusie.per_id()
    uit = []
    for v in voorstellen:
        ankers = v.get("ankers") or []
        if not v.get("klasse") or len(ankers) != 1:
            continue
        a = ankers[0]
        kid = ((v.get("trace") or {}).get("kandidaat") or {}).get("id", "")
        uit.append(_El(id=str(v.get("id", "")), klasse=v["klasse"], subtype=v.get("jas_subtype") or "",
                       bron_iri=a["bron_iri"], start=a["start"], eind=a["eind"], ankers=tuple(ankers),
                       kandidaat=per_id.get(kid)))
    return sorted(uit, key=lambda e: (e.bron_iri, e.start, -e.eind, e.klasse, e.id))


def _voorstel(type_: str, van: _El, naar: _El, code: str, volgorde: int | None = None, **detail) -> dict[str, Any]:
    return {"van_ankers": [dict(a) for a in van.ankers], "naar_ankers": [dict(a) for a in naar.ankers],
            "type": type_, "volgorde": volgorde,
            "spoor": {"door": "regel", "regel": code, "versie": VERSIE, "van_element": van.id,
                      "naar_element": naar.id, **({"detail": detail} if detail else {})}}


def _enige(kandidaten: list[_El]) -> _El | None:
    return kandidaten[0] if len(kandidaten) == 1 else None


def _minimaal(kandidaten: list[_El]) -> list[_El]:
    """Zonder wat een ander omvat: de markering die de span het scherpst raakt ('volle maanden', niet ook de
    bijzin eromheen). Geneste markeringen zijn zo geen twijfel; twee naast elkaar wel."""
    return [k for k in kandidaten if not any(k.bevat(o) for o in kandidaten)]


def _binnenste(ouders: list[_El]) -> _El | None:
    """De kleinste ouder; twee even kleine (zelfde span, andere klasse) is twijfel."""
    if not ouders:
        return None
    kleinst = min(o.lengte for o in ouders)
    return _enige([o for o in ouders if o.lengte == kleinst])


def _past(type_: str, van: _El, naar: _El) -> bool:
    return van.id != naar.id and toegestaan(type_, van.klasse, naar.klasse, van.subtype, naar.subtype)


# --- 1. uitvoer en invoer uit de functiedetector -------------------------------------------------------------------

def _functiespans(k: Candidate) -> list[tuple[dict, dict]]:
    uit = []
    for e in k.evidence:
        if e.code not in _FUNCTIE_SPANS:
            continue
        try:
            d = json.loads(e.detail or "{}")
        except ValueError:
            continue
        u, i = d.get("uitkomst"), d.get("invoer")
        if all(isinstance(x, dict) and isinstance(x.get("start"), int) and isinstance(x.get("eind"), int)
               for x in (u, i)):
            uit.append((u, i))
    return uit


def _functie(els: list[_El]) -> list[dict[str, Any]]:
    uit = []
    for regel in (e for e in els if e.klasse == AR and e.kandidaat is not None):
        for u, i in _functiespans(regel.kandidaat):
            binnen = [x for x in els if regel.bevat(x)]
            uitkomst = _minimaal([x for x in binnen if x.overlapt(u["start"], u["eind"])
                                  and not x.overlapt(i["start"], i["eind"]) and _past("uitvoer", regel, x)])
            if (x := _enige(uitkomst)) is not None:
                uit.append(_voorstel("uitvoer", regel, x, REL_UITVOER_FUNCTIE, span=u.get("tekst", "")))
            for x in _minimaal([x for x in binnen if x.overlapt(i["start"], i["eind"])
                                and not x.overlapt(u["start"], u["eind"]) and _past("invoer", x, regel)]):
                uit.append(_voorstel("invoer", x, regel, REL_INVOER_FUNCTIE, span=i.get("tekst", "")))
    return uit


# --- nesting uit de fusie ------------------------------------------------------------------------------------------

def _genest(fusie: Fusie) -> set[tuple[str, str]]:
    """(buiten, binnen) per kandidaat-id: de `bevat`-relaties van de fusie."""
    return {(r.van, r.naar) for r in fusie.relaties if r.soort == "bevat"}


def _in(ouder: _El, kind: _El, genest: set[tuple[str, str]]) -> bool:
    """Genest volgens de fusie én volgens de ankers van de voorstellen (die een spanoptie kunnen dragen)."""
    return (ouder.kandidaat is not None and kind.kandidaat is not None
            and (ouder.kandidaat.id, kind.kandidaat.id) in genest and ouder.bevat(kind))


# --- 2. waarde -----------------------------------------------------------------------------------------------------

def _waardeouder(waarde: _El, ouder: _El) -> bool:
    if waarde.klasse == PAR and waarde.subtype == "parameterwaarde":
        return ((ouder.klasse == TIJD and ouder.subtype == "verbijzondert parameter")
                or (ouder.klasse == PAR and ouder.subtype in ("parameter", "")))
    if waarde.klasse == VAR and waarde.subtype == "variabelewaarde":
        return ouder.klasse == VAR and ouder.subtype in ("variabele", "")
    return False


def _waarde(els: list[_El], genest: set[tuple[str, str]]) -> list[dict[str, Any]]:
    uit = []
    for w in els:
        ouder = _binnenste([o for o in els if _in(o, w, genest) and _waardeouder(w, o)])
        if ouder is not None and _past("waarde", w, ouder):
            uit.append(_voorstel("waarde", w, ouder, REL_WAARDE_NESTING))
    return uit


# --- 3. operator en operanden --------------------------------------------------------------------------------------

def _operand(op: _El, ouder: _El, els: list[_El], links: bool) -> _El | None:
    andere_ops = [o for o in els if o.klasse == OP and o.id != op.id and o.bron_iri == op.bron_iri]
    kandidaten = []
    for x in els:
        if x.id in (op.id, ouder.id) or not ouder.bevat(x) or x.overlapt(op.start, op.eind):
            continue
        if links and x.eind > op.start or not links and x.start < op.eind:
            continue
        tussen = (x.eind, op.start) if links else (op.eind, x.start)
        if any(tussen[0] <= o.start and o.eind <= tussen[1] for o in andere_ops):
            continue                                   # een andere operator ertussen: niet meer de naaste
        if _past("operand", x, op):
            kandidaten.append(x)
    if not kandidaten:
        return None
    naast = max(x.eind for x in kandidaten) if links else min(x.start for x in kandidaten)
    dichtst = [x for x in kandidaten if (x.eind if links else x.start) == naast]
    # Van de groepen die even dicht staan, de volle: 'het bedrag van de aanslag', niet ook 'de aanslag'.
    grootst = max(x.lengte for x in dichtst)
    return _enige([x for x in dichtst if x.lengte == grootst])


def _operator(els: list[_El], genest: set[tuple[str, str]]) -> list[dict[str, Any]]:
    uit = []
    for op in (e for e in els if e.klasse == OP):
        ouder = _binnenste([o for o in els if o.klasse in (VW, AR) and _in(o, op, genest)])
        if ouder is None or not _past("operator_in", op, ouder):
            continue
        uit.append(_voorstel("operator_in", op, ouder, REL_OPERATOR_IN_NESTING))
        for volgorde, links in ((1, True), (2, False)):
            x = _operand(op, ouder, els, links)
            if x is not None:
                uit.append(_voorstel("operand", x, op, REL_OPERAND_WOORDVOLGORDE, volgorde))
    return uit


# --- 4. voorwaarde -------------------------------------------------------------------------------------------------

def _aanhechting(v: _El, a: LinguisticAnalysis) -> int | None:
    """Het hoofdpredicaat (`root`) waaraan de voorwaardelijke bijzin van `v` hangt, of None."""
    binnen = [t for t in a.tokens if v.start <= t.start and t.eind <= v.eind]
    koppen = [t for t in binnen if t.deprel == "advcl" and 0 <= t.head < len(a.tokens)
              and not (v.start <= a.tokens[t.head].start and a.tokens[t.head].eind <= v.eind)]
    if len(koppen) != 1:
        return None
    kop = koppen[0]
    if not any(a.tokens[m].deprel == "mark" and a.tokens[m].tekst.lower() in _VOORWAARDELIJK
               and v.start <= a.tokens[m].start for m in a.subboom(kop.i)):
        return None
    hoofd = a.tokens[kop.head]
    return hoofd.i if hoofd.deprel == "root" else None


def _voorwaarde(els: list[_El], analyses: Mapping[str, LinguisticAnalysis | None]) -> list[dict[str, Any]]:
    uit = []
    for v in (e for e in els if e.klasse == VW):
        a = analyses.get(v.bron_iri)
        if a is None or a.gedegradeerd:
            continue
        hoofd = _aanhechting(v, a)
        if hoofd is None:
            continue
        t = a.tokens[hoofd]
        drager = _enige([d for d in els if d.klasse in (RB, AR) and d.id != v.id and d.bron_iri == v.bron_iri
                         and d.start <= t.start and t.eind <= d.eind])
        if drager is not None and _past("voorwaarde", drager, v):
            uit.append(_voorstel("voorwaarde", drager, v, REL_VOORWAARDE_AANHECHTING, ud_pad="advcl+mark→root",
                                 predicaat=t.tekst))
    return uit


def stel_voor(voorstellen: list[dict[str, Any]], fusie: Fusie,
              analyses: Mapping[str, LinguisticAnalysis | None] | None = None) -> list[dict[str, Any]]:
    """De relatievoorstellen tussen `voorstellen` (de uitkomst van `keten.analyseer`), ontdubbeld en geordend."""
    els = _elementen(voorstellen, fusie)
    genest = _genest(fusie)
    alle = [*_functie(els), *_waarde(els, genest), *_operator(els, genest), *_voorwaarde(els, analyses or {})]
    uniek: dict[tuple, dict[str, Any]] = {}
    for r in alle:
        sleutel = (r["spoor"]["van_element"], r["spoor"]["naar_element"], r["type"], r["volgorde"])
        uniek.setdefault(sleutel, r)
    return [uniek[k] for k in sorted(uniek, key=lambda k: (k[2], k[0], k[1], k[3] or 0))]


def telling(relaties: list[dict[str, Any]]) -> dict[str, Any]:
    """Voor de meting: hoeveel voorstellen per regel."""
    per_regel: dict[str, int] = {}
    for r in relaties:
        per_regel[r["spoor"]["regel"]] = per_regel.get(r["spoor"]["regel"], 0) + 1
    return {"versie": VERSIE, "voorgesteld": len(relaties), "per_regel": dict(sorted(per_regel.items()))}
