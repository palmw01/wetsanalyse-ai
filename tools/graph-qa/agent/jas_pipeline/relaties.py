"""Relatievoorstellen tussen markeringen (ADR-011 §*Voorstellen komen later, en eerst zonder model*).

Uit wat de keten van één bepaling al weet – de voorstellen, de kandidaten met hun bewijs, de nesting uit de fusie en
de UD-parse – volgen relaties tussen voorstellen. Geen model, geen geraden offset: een eindpunt is de lijst ankers van
een voorstel, precies zoals het naar de api gaat. De api zet die na het opslaan om naar het element-id
(`annotatie_v2_store.batch`).

Vier regels, in de volgorde van ADR-011, elk met een eigen code (verklaard in `verklaringen.yaml`, sectie `relatie`):

1. **`uitvoer`/`invoer` uit de functiedetector** (`REL_UITVOER_FUNCTIE`, `REL_INVOER_FUNCTIE`). Een afleidingsregel
   met bewijs `CALCULATION_QUANTITY` noemt in `Evidence.detail` de spans `uitkomst` en `invoer`. Een voorstel binnen de
   regel dat zo'n span overlapt (en de andere niet), hoort erbij; bij de uitvoer telt van geneste voorstellen het
   binnenste, `uitvoer` alleen als het er dan precies één is. **De invoer is een waarde** (L-2-2, Termijnen 19 nov 2026):
   draagt de invoerspan een variabele, parameter of tijdsaanduiding, dan is de grootste daarvan de invoer, en een
   rechtsobject erbinnen niet ('de dagtekening van het aanslagbiljet': de dagtekening). Dat rechtsobject krijgt een
   `kenmerk` van de variabele (`REL_KENMERK_INVOER`). Zonder waarde blijft het binnenste voorstel de invoer. De invoer
   krijgt de woordvolgorde als `volgorde` (1 = de eerste).
2. **`waarde` uit de nesting** (`REL_WAARDE_NESTING`): een parameterwaarde binnen een tijdsaanduiding die een parameter
   verbijzondert, of een parameter- of variabelewaarde binnen een parameter of variabele. De binnenste ouder telt.
3. **`operator_in` en `operand`** (`REL_OPERATOR_IN_NESTING`, `REL_OPERAND_WOORDVOLGORDE`): een operator in een
   voorwaarde of afleidingsregel; de naaste voorstellen links en rechts binnen die ouder zijn de operanden, met de
   woordvolgorde als `volgorde` (1 = links). Een andere operator ertussen breekt de reeks. Een ontkenning ('niet',
   'geen'; `EEN_OPERAND`) heeft één operand, de naaste rechts, op plek 1; ze breekt de reeks van een andere operator
   niet en is zelf nooit diens linkeroperand (M04 H2 *Operator*; Termijnen: "'niet' heeft één operand").
4. **`voorwaarde` uit de aanhechting** (`REL_VOORWAARDE_AANHECHTING`): een voorwaardelijke bijzin (`advcl` met een
   voorwaardelijk `mark`) aan het hoofdpredicaat (`root`) hangt aan de enige rechtsbetrekking of afleidingsregel die dat
   predicaat draagt. Dragen precies één rechtsbetrekking en één afleidingsregel het predicaat samen (een bepaling met
   een recht én een rekenregel, M-2-1), dan gaat het voorstel naar beide, met `twee_dragers` in het spoor.

5. **Rollen via onderwerp en modaliteit** (`REL_ROL_ONDERWERP`, ADR-011 stap 7): binnen een rechtsbetrekking zegt de
   modaliteit wie het onderwerp is – rechthebbende bij een bevoegdheid ("kan", "mag", "is bevoegd"), plichthebbende
   bij een plicht ("moet", "is verplicht"). Het onderwerp is het rechtssubject dat het `nsubj`-token draagt. Een
   rechtsfeit: wie het onderwerp is, verricht het. Een zin met beide soorten woorden is twijfel.
6. **De tegenpartij via het voorzetsel** (`REL_ROL_VOORZETSEL`): een rechtssubject na "aan", "ten aanzien van",
   "jegens" of "tegenover" heeft de andere rol dan het onderwerp; na "op verzoek van" is het rechthebbende van een
   plicht; na "van" bij een heffing of invordering ("wordt geheven van") plichthebbende.
7. **Het voorwerp** (`REL_VOORWERP_ZINSDEEL`): het rechtsobject dat het lijdend voorwerp (`obj`) draagt, of in een
   lijdende of naamwoordelijke zin het onderwerp ("Winstaandeel wordt geheven", "is een aanslag invorderbaar"),
   met wat daarmee is nevengeschikt.

Wat in een voorwaarde binnen de rechtsbetrekking staat, telt voor de regels 5 tot en met 7 niet mee: dat is het
onderwerp van de voorwaarde, niet van de betrekking.

Overal geldt: **bij twijfel geen voorstel.** Twee even goede kandidaten voor één plek, een gedegradeerde parse, een
eindpunt zonder klasse: dan komt er niets. En elk voorstel moet door de catalogus (`jas_relaties.toegestaan`: klassen,
richting, subtype), dezelfde regels die de api daarna nog eens toetst. Een kenmerk alleen binnen de invoer van een
regel (regel 1); tijd, `uitzondering_op` en `toepassing` doet deze module nog niet (die laatste twee wachten op een
bron als eindpunt, M-1-1).

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

VERSIE = "3"

REL_UITVOER_FUNCTIE = "REL_UITVOER_FUNCTIE"
REL_INVOER_FUNCTIE = "REL_INVOER_FUNCTIE"
REL_WAARDE_NESTING = "REL_WAARDE_NESTING"
REL_OPERATOR_IN_NESTING = "REL_OPERATOR_IN_NESTING"
REL_OPERAND_WOORDVOLGORDE = "REL_OPERAND_WOORDVOLGORDE"
REL_VOORWAARDE_AANHECHTING = "REL_VOORWAARDE_AANHECHTING"
REL_ROL_ONDERWERP = "REL_ROL_ONDERWERP"
REL_ROL_VOORZETSEL = "REL_ROL_VOORZETSEL"
REL_VOORWERP_ZINSDEEL = "REL_VOORWERP_ZINSDEEL"
REL_KENMERK_INVOER = "REL_KENMERK_INVOER"
#: Alle codes die deze module kan uitgeven; `tests/test_verklaringen.py` eist voor elk een verklaring.
CODES = (REL_UITVOER_FUNCTIE, REL_INVOER_FUNCTIE, REL_WAARDE_NESTING, REL_OPERATOR_IN_NESTING,
         REL_OPERAND_WOORDVOLGORDE, REL_VOORWAARDE_AANHECHTING, REL_ROL_ONDERWERP, REL_ROL_VOORZETSEL,
         REL_VOORWERP_ZINSDEEL, REL_KENMERK_INVOER)

AR, VW, OP, RB, RF = "Afleidingsregel", "Voorwaarde", "Operator", "Rechtsbetrekking", "Rechtsfeit"
RS, RO = "Rechtssubject", "Rechtsobject"
VAR, PAR, TIJD = "Variabele en variabelewaarde", "Parameter en parameterwaarde", "Tijdsaanduiding"
#: De bewijscodes van de functiedetector die een uitkomst- en een invoerspan noemen (`detectoren/functies.py`).
_FUNCTIE_SPANS = frozenset({"CALCULATION_QUANTITY"})
#: Klassen die een waarde dragen: daarmee rekent een regel (de invoer), een rechtsobject niet.
WAARDEN = (VAR, PAR, TIJD)
#: Operatoren met één operand: de ontkenning (M04 H2 *Operator*). Op de tekst van de markering, zonder hoofdletters.
EEN_OPERAND = frozenset({"niet", "geen"})


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
            kandidaten = [x for x in binnen if x.overlapt(i["start"], i["eind"]) and not x.overlapt(u["start"], u["eind"])]
            invoer, kenmerken = _invoer(kandidaten, regel)
            for volgorde, x in enumerate(sorted(invoer, key=lambda e: (e.start, e.eind)), start=1):
                uit.append(_voorstel("invoer", x, regel, REL_INVOER_FUNCTIE, volgorde, span=i.get("tekst", "")))
            for var, obj in kenmerken:
                uit.append(_voorstel("kenmerk", var, obj, REL_KENMERK_INVOER))
    return uit


def _invoer(kandidaten: list[_El], regel: _El) -> tuple[list[_El], list[tuple[_El, _El]]]:
    """De invoer binnen de invoerspan, en de kenmerken die een waarde aan haar rechtsobject geven.

    Een waarde is de invoer, de grootste als ze genest zijn ('de dagtekening van het aanslagbiljet', niet ook 'het
    aanslagbiljet'); wat erbinnen ligt, is geen invoer meer. Een rechtsobject binnen een variabele is daarvan het
    kenmerk. Buiten de waarden blijft het binnenste voorstel, zoals altijd."""
    waarden = [x for x in kandidaten if x.klasse in WAARDEN and _past("invoer", x, regel)]
    groot = [w for w in waarden if not any(o.bevat(w) for o in waarden)]
    binnen_waarde = [x for x in kandidaten if any(w.bevat(x) for w in groot)]
    # Wat een waarde omvat ('als er volle maanden overblijven' om 'volle maanden') is evenmin invoer.
    rest = _minimaal([x for x in kandidaten if x not in groot and x not in binnen_waarde
                      and not any(x.bevat(w) for w in groot) and _past("invoer", x, regel)])
    kenmerken = [(_binnenste([w for w in groot if w.bevat(x)]), x) for x in binnen_waarde if x.klasse == RO]
    return [*groot, *rest], [(w, x) for w, x in kenmerken if w is not None and _past("kenmerk", w, x)]


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

def _een_operand(op: _El) -> bool:
    return op.klasse == OP and str(op.ankers[0].get("tekst", "")).strip().lower() in EEN_OPERAND


def _operand(op: _El, ouder: _El, els: list[_El], links: bool, unair: set[str] = frozenset()) -> _El | None:
    # Een ontkenning breekt de reeks niet: 'de toepassing … niet leidt tot meer dan één termijn' heeft links van
    # 'meer dan' de toepassing, niet de ontkenning.
    andere_ops = [o for o in els if o.klasse == OP and o.id != op.id and o.bron_iri == op.bron_iri and o.id not in unair]
    kandidaten = []
    for x in els:
        if x.id in (op.id, ouder.id) or not ouder.bevat(x) or x.overlapt(op.start, op.eind):
            continue
        if links and x.id in unair:
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
    unair = {e.id for e in els if _een_operand(e)}
    for op in (e for e in els if e.klasse == OP):
        ouder = _binnenste([o for o in els if o.klasse in (VW, AR) and _in(o, op, genest)])
        if ouder is None or not _past("operator_in", op, ouder):
            continue
        uit.append(_voorstel("operator_in", op, ouder, REL_OPERATOR_IN_NESTING))
        plekken = ((1, False),) if op.id in unair else ((1, True), (2, False))
        for volgorde, links in plekken:
            x = _operand(op, ouder, els, links, unair)
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
        dragers = [d for d in els if d.klasse in (RB, AR) and d.id != v.id and d.bron_iri == v.bron_iri
                   and d.start <= t.start and t.eind <= d.eind]
        twee = len(dragers) == 2 and {d.klasse for d in dragers} == {RB, AR}
        for drager in (dragers if twee else [d for d in [_enige(dragers)] if d is not None]):
            if _past("voorwaarde", drager, v):
                uit.append(_voorstel("voorwaarde", drager, v, REL_VOORWAARDE_AANHECHTING, ud_pad="advcl+mark→root",
                                     predicaat=t.tekst, **({"twee_dragers": True} if twee else {})))
    return uit


# --- 5–7. rollen en voorwerp (ADR-011 stap 7: een lexicon van predicaten) ------------------------------------------

#: Lemma's die een bevoegdheid of recht maken van de betrekking: het onderwerp is rechthebbende.
RECHT = frozenset({"kunnen", "mogen", "bevoegd", "gerechtigd", "aanspraak", "recht"})
#: Lemma's die een plicht maken van de betrekking: het onderwerp is plichthebbende.
PLICHT = frozenset({"moeten", "verplichten", "verplicht", "gehouden", "dienen", "verschuldigd"})
#: Woorden vlak voor een rechtssubject die de tegenpartij aanwijzen: de andere rol dan het onderwerp.
TEGENPARTIJ = ("ten aanzien van", "tegenover", "jegens", "aan")
#: Werkwoorden (deelwoord) waarbij "van X" de plichtige noemt: "wordt geheven van de houder".
HEFFEN = ("geheven", "ingevorderd", "geïnd", "gevorderd")


def _woorden(tekst: str) -> str:
    return " ".join(tekst.lower().split())


def _modaliteit(drager: _El, a: LinguisticAnalysis, uitgezonderd: list[_El]) -> str | None:
    """`recht`, `plicht` of None (geen van beide, of beide: twijfel), uit de lemma's binnen de drager buiten de voorwaarden."""
    lemmas = {t.lemma.lower() for t in a.tokens if drager.start <= t.start and t.eind <= drager.eind
              and not any(u.start <= t.start and t.eind <= u.eind for u in uitgezonderd)}
    recht, plicht = bool(lemmas & RECHT), bool(lemmas & PLICHT)
    return "recht" if recht and not plicht else "plicht" if plicht and not recht else None


def _drager_van(token, kandidaten: list[_El]) -> _El | None:
    """De kleinste markering die het token draagt; twee even kleine is twijfel."""
    return _binnenste([k for k in kandidaten if k.start <= token.start and token.eind <= k.eind])


def _voor(tekst: str, el: _El, drager: _El, woorden: tuple[str, ...]) -> str | None:
    """Welk van `woorden` vlak vóór de markering staat, binnen de drager (op woordgrens)."""
    voor = _woorden(tekst[drager.start:el.start])
    return next((w for w in woorden if voor == w or voor.endswith(" " + w)), None)


def _rollen(els: list[_El], analyses: Mapping[str, LinguisticAnalysis | None]) -> list[dict[str, Any]]:
    uit = []
    for drager in (e for e in els if e.klasse in (RB, RF)):
        a = analyses.get(drager.bron_iri)
        if a is None or a.gedegradeerd:
            continue
        binnen = [x for x in els if drager.bevat(x) and x.bron_iri == drager.bron_iri]
        voorwaarden = [x for x in binnen if x.klasse == VW]
        binnen = [x for x in binnen if not any(v.bevat(x) or v.id == x.id for v in voorwaarden)]
        subjecten = [x for x in binnen if x.klasse == RS]
        objecten = [x for x in binnen if x.klasse == RO]
        tokens = [t for t in a.tokens if drager.start <= t.start and t.eind <= drager.eind
                  and not any(v.start <= t.start and t.eind <= v.eind for v in voorwaarden)]
        modaliteit = _modaliteit(drager, a, voorwaarden) if drager.klasse == RB else None
        tekst = a.tekst
        # 5. Het onderwerp.
        onderwerp = _enige(list({d.id: d for t in tokens if t.deprel == "nsubj"
                                 and (d := _drager_van(t, subjecten)) is not None}.values()))
        rol_onderwerp = ("verricht" if drager.klasse == RF else
                         "rechthebbende" if modaliteit == "recht" else "plichthebbende" if modaliteit == "plicht" else None)
        if onderwerp is not None and rol_onderwerp and _past(rol_onderwerp, onderwerp, drager):
            uit.append(_voorstel(rol_onderwerp, onderwerp, drager, REL_ROL_ONDERWERP, modaliteit=modaliteit or "feit"))
        # 6. De tegenpartij en de plichtige van een heffing.
        if drager.klasse == RB:
            heffing = any(w in _woorden(tekst[drager.start:drager.eind]).split() for w in HEFFEN)
            for s in subjecten:
                if onderwerp is not None and s.id == onderwerp.id:
                    continue
                rol = None
                if _voor(tekst, s, drager, ("op verzoek van",)) and modaliteit == "plicht":
                    rol = "rechthebbende"
                elif _voor(tekst, s, drager, TEGENPARTIJ) and modaliteit:
                    rol = "plichthebbende" if modaliteit == "recht" else "rechthebbende"
                elif heffing and _voor(tekst, s, drager, ("van",)):
                    rol = "plichthebbende"
                if rol and _past(rol, s, drager):
                    uit.append(_voorstel(rol, s, drager, REL_ROL_VOORZETSEL,
                                         voorzetsel=_voor(tekst, s, drager, ("op verzoek van", *TEGENPARTIJ, "van")) or ""))
        # 7. Het voorwerp: het lijdend voorwerp, of het onderwerp van een lijdende of naamwoordelijke zin.
        lijdend = {t.i for t in tokens if t.deprel == "obj"}
        lijdend |= {t.i for t in tokens if t.deprel == "nsubj:pass"}
        if drager.klasse == RB and not subjecten:
            # Een naamwoordelijke zin: het onderwerp van het koppelwerkwoord, of – als de ontleding het zelfstandig
            # naamwoord tot kern maakt ("is een aanslag … invorderbaar") – die kern zelf.
            lijdend |= {t.i for t in tokens if t.deprel == "nsubj" and t.head >= 0
                        and any(a.tokens[k].deprel == "cop" for k in a.kinderen(t.head))}
            lijdend |= {t.i for t in tokens if t.deprel == "root" and t.upos in ("NOUN", "PROPN")
                        and any(a.tokens[k].deprel == "cop" for k in a.kinderen(t.i))}
        lijdend |= {t.i for t in tokens if t.deprel == "conj" and t.head in lijdend}
        gezien: set[str] = set()
        for i in sorted(lijdend):
            o = _drager_van(a.tokens[i], objecten)
            if o is not None and o.id not in gezien and _past("voorwerp", drager, o):
                gezien.add(o.id)
                uit.append(_voorstel("voorwerp", drager, o, REL_VOORWERP_ZINSDEEL, zinsdeel=a.tokens[i].deprel))
    return uit


def stel_voor(voorstellen: list[dict[str, Any]], fusie: Fusie,
              analyses: Mapping[str, LinguisticAnalysis | None] | None = None) -> list[dict[str, Any]]:
    """De relatievoorstellen tussen `voorstellen` (de uitkomst van `keten.analyseer`), ontdubbeld en geordend."""
    els = _elementen(voorstellen, fusie)
    genest = _genest(fusie)
    alle = [*_functie(els), *_waarde(els, genest), *_operator(els, genest), *_voorwaarde(els, analyses or {}),
            *_rollen(els, analyses or {})]
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
