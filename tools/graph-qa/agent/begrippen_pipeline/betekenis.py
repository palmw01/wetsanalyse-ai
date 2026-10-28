"""Het betekenisdossier (spoor M): wat de context over een begrip zegt, vóór er een definitie komt.

Wetsanalyse stap 3a vraagt een begrip te lezen in zijn context: andere leden en regelingen, een
homoniem door een berekening, en een omschrijving met de wezenlijke kenmerken – geen afleiding, geen
rechtsgevolg. Deze module legt per groep (of per begrip bij een kaartactie) vast wat de manifest- en
contextbronnen daarover zeggen, **zuiver en deterministisch**: dezelfde invoer, hetzelfde dossier.

Elke bevinding heeft een `soort`:

- `bronfeit` – iets wat letterlijk in de bron staat (een definitie, een voorkomen);
- `signaal` – een patroon dat aandacht vraagt (parallelle leden, een berekening op de term);
- `interpretatie` – alleen van een model, en daarom hier nooit gemaakt.

| code | soort | wat |
|---|---|---|
| `VOORKOMENS` | bronfeit | waar de term nog meer staat in manifest en onderzoek |
| `PARALLELLE_BEPALINGEN` | signaal | ≥ 2 bepalingen met dezelfde opening tot en met de term en verschillende vervolgen |
| `DEFINITIE_IN_CONTEXT` | bronfeit | een definitie of kwalificatie van de term, met bereik en per lid binnen of buiten |
| `KWALIFICATIE_SAMENGESTELD` | bronfeit | "geldt als het te betalen bedrag aan belasting": een eigen begrip naast de kale term |
| `BEREKENING_OP_TERM` | signaal | de term wordt in de bepaling bewerkt (op nihil gesteld, verminderd met …) |
| `ROL_IN_BEPALING` | signaal | de formulering staat in een voorwaarde of is de grondslag van een berekening |
| `AFLEIDINGSREGEL` | signaal | een passage in dezelfde bepaling is een afleidingsregel: een eigen begrip "bepalen …" |
| `GEEN_DEFINITIE_GEVONDEN` | bronfeit | binnen de onderzochte context, met wat niet onderzocht is |

Een bevinding is nooit `Bewijs` in de beslistabel: het dossier gaat naar de prompt en naar de toetsen
(`toetsen.signalen`), niet naar `besluit.py`. De open vragen hebben een vaste formulering.
"""
from __future__ import annotations

import hashlib
import re
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from . import definities, fragmenten as fragmenten_mod
from .model import DUIDING_SOORTEN, Bron, Duiding, Manifest, Onderzoek

VERSIE = "1"
REGELS = Path(__file__).parent / "betekenisregels"
TESTSOORTEN = ("positief", "negatief", "rand", "overlap")
_MACRO = {"LW": r"(?:de|het|een|die|deze|dat|dit)"}

_STOP = frozenset("""de het een en of van in op met tot aan voor door bij als die dat dit deze is zijn wordt worden
te ter zake naar over om uit dan niet ook nog al wel zo er hij zij ze zich wat welke waarop waarover waarbij
eerder onderscheidenlijk ingevolge bedoeld artikel lid""".split())
STOPWOORDEN = _STOP
_VOORWAARDE = re.compile(r"(?:^|[.;:]\s+|,\s+)(?:bij|indien|ingeval|in het geval|wanneer|voor zover|zodra)\b[^.;:]*$",
                         re.IGNORECASE)
_GRONDSLAG = re.compile(r"\b(?:als|tot)\s+grondslag\s+(?:\w+\s+){0,4}$", re.IGNORECASE)
_KWALIFICATIE = re.compile(r"\b(?:geldt|gelden)\s+(?:mede\s+)?als\s+(?:(?:de|het|een)\s+)?(?P<term>[^:;.]{1,80}?)\s*:\s",
                           re.IGNORECASE)
_MAX_OPENING_WOORDEN = 12

# De codes van het dossier, als namen: wie ze leest (`toetsen`), noemt ze zo.
VOORKOMENS = "VOORKOMENS"
PARALLEL = "PARALLELLE_BEPALINGEN"
DEFINITIE = "DEFINITIE_IN_CONTEXT"
SAMENGESTELD = "KWALIFICATIE_SAMENGESTELD"


class Soort(str, Enum):
    BRONFEIT = "bronfeit"
    SIGNAAL = "signaal"
    INTERPRETATIE = "interpretatie"


class _Vast(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Bevinding(_Vast):
    code: str
    soort: Soort
    regel: str                         # "betekenis.parallel.opening"
    versie: str
    term: str
    detail: str
    bron_iris: tuple[str, ...] = ()
    fragmenten: tuple[str, ...] = ()   # fragment-id's (manifest + onderzoek) die de bevinding dragen
    specifiek: tuple[str, ...] = ()    # bij PARALLELLE_BEPALINGEN: woorden die alleen in sommige varianten staan


class Dossier(_Vast):
    termen: tuple[str, ...]
    bevindingen: tuple[Bevinding, ...]
    vragen: tuple[str, ...]
    onderzoek_id: str = ""
    onderzocht: int = 0                # aantal contextbronnen
    ontbrekend: tuple[str, ...] = ()   # "budget: 3", "niet_in_graaf: 1", …

    @property
    def id(self) -> str:
        return "D" + hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:12]

    def met(self, code: str) -> list[Bevinding]:
        return [b for b in self.bevindingen if b.code == code]


def _norm(t: str) -> str:
    return " ".join((t or "").lower().split())


def _woorden(t: str) -> list[str]:
    return re.findall(r"[a-zà-ÿ0-9][a-zà-ÿ0-9-]*", (t or "").lower())


def inhoudswoorden(t: str) -> set[str]:
    return {w for w in _woorden(t) if len(w) >= 4 and w not in _STOP}


def _vind(tekst: str, term: str) -> re.Match | None:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", tekst, re.IGNORECASE) if term else None


def _label(b: Bron) -> str:
    return b.label or b.bron_iri


# ---------------------------------------------------------------------------------------------
# Berekeningspatronen (betekenisregels/berekening.yaml)
# ---------------------------------------------------------------------------------------------

def _compileer(patroon: str, term: str) -> re.Pattern:
    vorm = re.sub(r"\{([A-Z]+)\}", lambda m: re.escape(term) if m.group(1) == "TERM" else _MACRO[m.group(1)], patroon)
    return re.compile(vorm, re.IGNORECASE)


@cache
def berekeningsregels() -> tuple[dict[str, Any], ...]:
    regels = yaml.safe_load((REGELS / "berekening.yaml").read_text(encoding="utf-8"))
    for r in regels:
        if set(r) != {"id", "code", "bron", "versie", "patroon", "tests"}:
            raise ValueError(f"{r.get('id', '?')}: onjuiste velden")
        if missend := [s for s in TESTSOORTEN if not r["tests"].get(s)]:
            raise ValueError(f"{r['id']}: ontbrekende tests {missend}")
        if "{TERM}" not in r["patroon"]:
            raise ValueError(f"{r['id']}: een berekeningspatroon noemt {{TERM}}")
    return tuple(regels)


def berekening(tekst: str, term: str) -> tuple[str, str] | None:
    """(regel-id, gevangen tekst) als `term` in `tekst` bewerkt wordt; anders None."""
    for r in berekeningsregels():
        if m := _compileer(r["patroon"], term).search(tekst):
            return r["id"], m.group(0)
    return None


# ---------------------------------------------------------------------------------------------
# Het dossier
# ---------------------------------------------------------------------------------------------

def _fragmenten_met(bron: Bron, term: str) -> tuple[str, ...]:
    return tuple(f.id for f in fragmenten_mod.knip(bron) if _vind(f.tekst, term))


def _opening(tekst: str, term: str) -> tuple[str, str] | None:
    """(opening tot en met de term, vervolg tot de eerste komma of persoonsvorm) als de term vroeg in de
    eerste zin staat. Het vervolg is wat de varianten van elkaar onderscheidt ("met een positief bedrag
    tot … een hoger positief bedrag"); wat daarna komt, is het rechtsgevolg."""
    m = _vind(tekst, term)
    if not m:
        return None
    opening = _norm(tekst[:m.end()])
    if len(opening.split()) > _MAX_OPENING_WOORDEN or re.search(r"[.;:]", tekst[:m.start()]):
        return None
    vervolg = re.split(r"[,;:.]|\b(?:wordt|worden|is|zijn|geldt|gelden)\b", tekst[m.end():], maxsplit=1)[0]
    return opening, _norm(vervolg)


def _parallel(term: str, bronnen: list[Bron]) -> Bevinding | None:
    per_opening: dict[str, list[tuple[Bron, str]]] = {}
    for b in bronnen:
        if o := _opening(b.tekst, term):
            per_opening.setdefault(o[0], []).append((b, o[1]))
    for opening, groep in sorted(per_opening.items(), key=lambda x: (-len(x[1]), x[0])):
        vervolgen = {v for _, v in groep}
        if len(groep) < 2 or len(vervolgen) < 2:
            continue
        sets = [inhoudswoorden(v) for v in vervolgen]
        gemeen = set.intersection(*sets)
        specifiek = sorted(set.union(*sets) - gemeen)
        labels = "; ".join(_label(b) for b, _ in groep)
        return Bevinding(
            code="PARALLELLE_BEPALINGEN", soort=Soort.SIGNAAL, regel="betekenis.parallel.opening", versie=VERSIE,
            term=term, detail=f'{len(groep)} bepalingen beginnen met "{opening}" en verschillen daarna ({labels})',
            bron_iris=tuple(b.bron_iri for b, _ in groep),
            fragmenten=tuple(f for b, _ in groep for f in _fragmenten_met(b, term)[:1]), specifiek=tuple(specifiek))
    return None


def _definities(term: str, bronnen: list[Bron], leden_iris: list[str]) -> tuple[list[Bevinding], list[str]]:
    uit: list[Bevinding] = []
    vragen: list[str] = []
    for b in bronnen:
        d = definities.definitie_van(b)
        kw = _KWALIFICATIE.search(b.tekst)
        gevonden: list[tuple[str, definities.Bereik, str]] = []
        if d and term in d[0]:
            gevonden.append((term, d[2], d[1]))
        if kw:
            kwterm = _norm(kw.group("term"))
            bereik = definities.bereik_uit(b.tekst[:kw.end()], b.bron_iri)
            if kwterm == term:
                gevonden.append((term, bereik, "kwalificatie"))
            elif _vind(kwterm, term):
                uit.append(Bevinding(
                    code="KWALIFICATIE_SAMENGESTELD", soort=Soort.BRONFEIT, regel="betekenis.kwalificatie.samengesteld",
                    versie=VERSIE, term=term,
                    detail=f'{_label(b)} kwalificeert "{kwterm}" ({bereik.formule or "bereik onbekend"}); '
                           f'dat is een samenstelling met "{term}", niet de kale term',
                    bron_iris=(b.bron_iri,), fragmenten=_fragmenten_met(b, kwterm)[:2]))
                vragen.append(f'"{kwterm}" krijgt in {_label(b)} een eigen kwalificatie. Is dat een ander begrip '
                              f'dan "{term}", en hoort het een eigen kaart te krijgen?')
        for t, bereik, soort in gevonden:
            binnen = [i for i in leden_iris if bereik.omvat(i)]
            buiten = [i for i in leden_iris if bereik.omvat(i) is False]
            detail = f'{_label(b)}: {soort} van "{t}" ({bereik.formule or bereik.soort})'
            if buiten:
                detail += f"; {len(buiten)} passage(s) buiten dat bereik"
                vragen.append(f'De definitie van "{t}" in {_label(b)} geldt niet voor elke passage. Gaat het daar '
                              f"om hetzelfde begrip?")
            elif binnen:
                detail += "; alle passages binnen dat bereik"
            uit.append(Bevinding(code="DEFINITIE_IN_CONTEXT", soort=Soort.BRONFEIT, regel="betekenis.definitie.context",
                                 versie=VERSIE, term=t, detail=detail, bron_iris=(b.bron_iri,),
                                 fragmenten=tuple(f.id for f in fragmenten_mod.knip(b))[:3]))
    return uit, vragen


def dossier(manifest: Manifest, onderzoek: Onderzoek | None, leden: tuple[str, ...],
            termen: list[str] | tuple[str, ...]) -> Dossier:
    """Het dossier over één groep of begrip. `termen` zijn de namen (naam, alternatieve termen, de
    termen van de taalstap); de teksten van de leden komen er vanzelf bij."""
    leden = tuple(e for e in leden if e in {f.element_id for f in manifest.formuleringen})
    alle_termen = list(dict.fromkeys(t for t in (*map(_norm, termen),
                                                 *(_norm(manifest.formulering(e).tekst) for e in leden)) if t))
    kale = alle_termen[0] if alle_termen else ""
    bronnen: list[Bron] = [*manifest.bronnen, *(onderzoek.bronnen if onderzoek else ())]
    leden_iris = list(dict.fromkeys(manifest.formulering(e).bron_iri for e in leden))
    eigen = [manifest.bron(i) for i in leden_iris]
    bevindingen: list[Bevinding] = []
    vragen: list[str] = []

    for t in alle_termen:
        waar = [b for b in bronnen if _vind(b.tekst, t)]
        if len(waar) > 1:
            bevindingen.append(Bevinding(
                code="VOORKOMENS", soort=Soort.BRONFEIT, regel="betekenis.voorkomens", versie=VERSIE, term=t,
                detail=f'"{t}" staat in {len(waar)} onderzochte bepalingen', bron_iris=tuple(b.bron_iri for b in waar)))

    if kale and (p := _parallel(kale, bronnen)):
        bevindingen.append(p)
        hier = [_label(manifest.bron(i)) for i in leden_iris if i in p.bron_iris]
        daar = [_label(next(b for b in bronnen if b.bron_iri == i)) for i in p.bron_iris if i not in leden_iris]
        if hier and daar:
            vragen.append(f'Duidt "{kale}" in {"; ".join(hier)} hetzelfde aan als in {"; ".join(daar)}, '
                          f"of een specifiek geval daarvan?")

    defs, dvragen = [], []
    for t in alle_termen:
        d, v = _definities(t, bronnen, leden_iris)
        defs += d
        dvragen += v
    bevindingen += list(dict.fromkeys(defs))
    vragen += list(dict.fromkeys(dvragen))

    for b in eigen:
        for t in alle_termen[:1]:
            if hit := berekening(b.tekst, t):
                bevindingen.append(Bevinding(
                    code="BEREKENING_OP_TERM", soort=Soort.SIGNAAL, regel=hit[0], versie=VERSIE, term=t,
                    detail=f'{_label(b)} bewerkt "{t}": "{_norm(hit[1])}"', bron_iris=(b.bron_iri,),
                    fragmenten=_fragmenten_met(b, t)[:2]))
                vragen.append(f'In {_label(b)} wordt "{t}" bewerkt. Is het resultaat daarvan hetzelfde begrip, '
                              f"of een eigen begrip (een berekeningsresultaat)?")

    for e in leden:
        f = manifest.formulering(e)
        b = manifest.bron(f.bron_iri)
        voor = b.tekst[:f.start]
        rol = ("voorwaarde" if _VOORWAARDE.search(voor) else
               "grondslag van een berekening" if _GRONDSLAG.search(voor) else "")
        if rol:
            bevindingen.append(Bevinding(
                code="ROL_IN_BEPALING", soort=Soort.SIGNAAL, regel="betekenis.rol.zin", versie=VERSIE, term=_norm(f.tekst),
                detail=f'"{f.tekst}" staat in {_label(b)} in een {rol}; wat de bepaling daar regelt, hoort niet in de '
                       f"definitie", bron_iris=(b.bron_iri,), fragmenten=_fragmenten_met(b, f.tekst)[:1]))

    afleiding = [f for f in manifest.formuleringen if f.bron_iri in leden_iris and f.jas_klasse == "Afleidingsregel"
                 and f.element_id not in leden]
    for f in afleiding[:3]:
        bevindingen.append(Bevinding(
            code="AFLEIDINGSREGEL", soort=Soort.SIGNAAL, regel="betekenis.afleidingsregel", versie=VERSIE, term=kale,
            detail=f'In {_label(manifest.bron(f.bron_iri))} staat een afleidingsregel ("{f.tekst[:120]}"); die is een '
                   f'eigen begrip ("bepalen …"), geen deel van de definitie', bron_iris=(f.bron_iri,)))

    ontbrekend: dict[str, int] = {}
    for o in (onderzoek.ontbrekend if onderzoek else ()):
        ontbrekend[o.reden] = ontbrekend.get(o.reden, 0) + 1
    if not any(b.code == "DEFINITIE_IN_CONTEXT" for b in bevindingen):
        wat = (f"{len(onderzoek.bronnen)} contextbepalingen onderzocht" if onderzoek
               else "alleen de bepalingen met de passages onderzocht")
        if ontbrekend:
            wat += "; niet onderzocht: " + ", ".join(f"{n}× {r}" for r, n in sorted(ontbrekend.items()))
        bevindingen.append(Bevinding(code="GEEN_DEFINITIE_GEVONDEN", soort=Soort.BRONFEIT,
                                     regel="betekenis.definitie.geen", versie=VERSIE, term=kale,
                                     detail=f'Geen definitie van "{kale}" gevonden ({wat})'))

    return Dossier(termen=tuple(alle_termen), bevindingen=tuple(bevindingen), vragen=tuple(dict.fromkeys(vragen)),
                   onderzoek_id=onderzoek.id if onderzoek else "", onderzocht=len(onderzoek.bronnen) if onderzoek else 0,
                   ontbrekend=tuple(f"{r}: {n}" for r, n in sorted(ontbrekend.items())))


def blok(d: Dossier | None) -> list[str]:
    """Het dossier als promptregels: eerst wat er onderzocht is, dan de bevindingen, dan de vragen."""
    if d is None:
        return ["ONDERZOCHTE CONTEXT: geen (alleen de bepalingen met de passages)"]
    regels = [f"ONDERZOCHTE CONTEXT: {d.onderzocht} bepalingen naast de passages"
              + (f"; niet onderzocht: {', '.join(d.ontbrekend)}" if d.ontbrekend else "")]
    if d.bevindingen:
        regels.append("BEVINDINGEN (bronfeit = staat in de wet; signaal = vraagt aandacht)")
        regels += [f"  - [{b.soort.value}] {b.code}: {b.detail}" for b in d.bevindingen]
    if d.vragen:
        regels.append("OPEN VRAGEN (beantwoord ze niet in de definitie; laat ze zien in de motivatie)")
        regels += [f"  - {v}" for v in d.vragen]
    return regels


# ---------------------------------------------------------------------------------------------
# Gedeeld door de kaart en de kaartacties: de regels in de prompt en de duiding in het schema
# ---------------------------------------------------------------------------------------------

CONTEXTREGELS = (
    "Lees het begrip in zijn context (de BEVINDINGEN). Een definitie geeft de wezenlijke kenmerken en, waar "
    "de tekst het zegt, het doel – niet wat de bepaling met het begrip doet: geen rechtsgevolg (wat er in "
    "rekening wordt gebracht of vergoed), geen voorwaarde uit één lid, en geen afleiding of verrekening (die "
    "is een eigen begrip, 'bepalen …'). Staan er parallelle bepalingen, kies dan: een algemene definitie die "
    "voor alle varianten geldt, of een specifiek begrip met een eigen naam (`voorkeursterm`). Een kwalificatie "
    "van een samenstelling ('geldt als het te betalen bedrag aan belasting') definieert de kale term niet. "
    "Zeg in `soort` wat je definieert (begrip, berekeningsresultaat, afleidingsregel of toepassingsgeval) en "
    "in `bereik` of het algemeen of specifiek is. Is er onvoldoende bewijs, kies dan `geen` en zeg in "
    "`ontbreekt` wat er ontbreekt. Noem open vragen in de motivatie; beantwoord ze niet stilzwijgend."
)

DUIDING_EIGENSCHAPPEN = {
    "soort": {"type": "string", "enum": list(DUIDING_SOORTEN)},
    "bereik": {"type": "string", "enum": ["algemeen", "specifiek"]},
    "voorkeursterm": {"type": "string"},
    "ontbreekt": {"type": "string"},
}


def duiding_uit(item: dict[str, Any]) -> Duiding | None:
    """De duiding uit een tool-antwoord; ongeldig of afwezig = None (een interpretatie raden we niet)."""
    try:
        return Duiding(soort=str(item.get("soort") or "begrip"), bereik=str(item.get("bereik") or "algemeen"),
                       voorkeursterm=" ".join(str(item.get("voorkeursterm") or "").split())[:200],
                       ontbreekt=" ".join(str(item.get("ontbreekt") or "").split())[:1000])
    except ValueError:
        return None
