"""Definities, hun bereik en verwijzingen (ADR-004): wat de wet zelf over haar termen zegt.

Een **wettelijke term** is een term die de wet vastlegt: de term van een begripsbepaling ("Deze
wet verstaat onder: belastingaanslag: …"), of een onderdeel van een opsommende definitie ("de
voorlopige aanslag, de aanslag, …"). Gebruik van zo'n term binnen het bereik van die definitie
is sterk bewijs dat het om hetzelfde begrip gaat; hetzelfde gewone woord elders is dat niet.

**Bereik** volgt uit de vaste formules van de Aanwijzingen voor de regelgeving, in de aanhef van
de houder of in de bepaling zelf:

| formule | bereik |
|---|---|
| "deze wet verstaat (mede) onder", "in deze wet … wordt verstaan onder" | de regeling |
| "… en de daarop berustende bepalingen" | idem (uitvoeringsregelingen vallen buiten het manifest) |
| "in dit artikel", "voor de toepassing van artikel N" | dat artikel |
| "in dit lid" | dat lid |
| "in dit hoofdstuk / deze afdeling / deze paragraaf …" | **onbekend**: de opbouw staat niet in de IRI |
| geen formule | de regeling: zonder beperking geldt een begripsbepaling voor de hele regeling |

Een definitie is ook "onder X wordt (mede/niet) verstaan …", met of zonder dubbele punt.

Definities buiten het werkgebied komen als contextbron in het manifest; deze module doet zelf
geen graafverkeer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bronmodel.definities import geldigheid_uit, losse_termen

from .model import Bron, Formulering, Manifest, Taalanalyse

VERSIE = "3"

_DEF_AANHEF = re.compile(r"\b(?:verstaat|wordt|worden)\s+(?:(mede|niet)\s+)?(?:verstaan\s+)?onder\s*:?\s*$",
                         re.IGNORECASE)
_DEF_INLINE = re.compile(r"\bwordt\s+(?:(mede|niet)\s+)?verstaan\s+onder\s+([^:]{1,80}?)\s*:\s*",
                         re.IGNORECASE)
# "Onder X wordt/worden (mede/niet) verstaan …", ook zonder dubbele punt en met "wordt" eerder in de
# zin ("In aanvulling op … wordt … onder partner mede verstaan degene die …").
_DEF_ONDER = re.compile(r"\bonder\s+(?P<term>[^:,;]{1,60}?)\s+(?:(?:wordt|worden)\s+)?"
                        r"(?:(?P<soort>mede|niet|tevens|ook)\s+)?verstaan\b\s*:?\s*", re.IGNORECASE)
_WORDT = re.compile(r"\b(?:wordt|worden)\b", re.IGNORECASE)
_TERM_DUBBELPUNT = re.compile(r"^([^:]{1,80}?):\s+")

_RANG = {"eerste": 1, "tweede": 2, "derde": 3, "vierde": 4, "vijfde": 5, "zesde": 6, "zevende": 7,
         "achtste": 8, "negende": 9, "tiende": 10, "elfde": 11, "twaalfde": 12}
_BEDOELD = re.compile(
    r"^[\s,]*(?:als\s+)?bedoeld\s+in\s+"
    r"(?:artikel\s+(?P<art>[0-9]+[a-z]*)(?:,\s+(?P<lid>\w+)\s+lid)?(?:,\s+onderdeel\s+(?P<od>[a-z]+))?"
    r"|(?:het\s+|de\s+)?(?P<lid2>\w+)\s+lid(?:,\s+onderdeel\s+(?P<od2>[a-z]+))?"
    r"|onderdeel\s+(?P<od3>[a-z]+))",
    re.IGNORECASE)


@dataclass(frozen=True)
class Bereik:
    soort: str                 # "regeling" | "artikel" | "lid" | "onbekend"
    prefix: str = ""           # IRI-prefix waarbinnen de definitie geldt; leeg bij onbekend
    formule: str = ""          # de herkende formule, voor de uitleg

    def omvat(self, bron_iri: str) -> bool | None:
        """True/False als het bereik bekend is, None als het dat niet is."""
        if self.soort == "onbekend":
            return None
        return bron_iri == self.prefix or bron_iri.startswith(self.prefix + ":")


@dataclass(frozen=True)
class WettelijkeTerm:
    term: str                  # genormaliseerd (zoals `Taalanalyse.term`)
    bron_iri: str              # de definitie
    bereik: Bereik
    soort: str                 # "definitie" | "mede" | "niet" | "opsomming"
    anker: str = ""            # element_id van de formulering die de term vastlegt, als die er is
    definitie_anker: str = ""  # bij een opsomming: de term van de definitie (de bovenliggende soort)


def regeling_van(bron_iri: str) -> str:
    delen = bron_iri.split(":")
    return ":".join(delen[:3])                      # "urn:bwb:BWBR0004770"


def _artikel_van(bron_iri: str) -> str:
    m = re.match(r"^(.*?:artikel:[^:]+)", bron_iri)
    return m.group(1) if m else bron_iri


def _lid_van(bron_iri: str) -> str:
    m = re.match(r"^(.*?:lid:[^:]+)", bron_iri)
    return m.group(1) if m else _artikel_van(bron_iri)


def bereik_uit(formule: str, bron_iri: str) -> Bereik:
    g = geldigheid_uit(formule)
    if g.soort == "artikel_n":
        return Bereik("artikel", f"{regeling_van(bron_iri)}:artikel:{g.waarde}", g.formule)
    if g.soort == "artikel":
        return Bereik("artikel", _artikel_van(bron_iri), g.formule)
    if g.soort == "lid":
        return Bereik("lid", _lid_van(bron_iri), g.formule)
    if g.soort == "structuur":
        return Bereik("onbekend", "", g.formule)
    # Geen formule: een begripsbepaling geldt dan voor de hele regeling (Aanwijzingen).
    return Bereik("regeling", regeling_van(bron_iri), g.formule)


def termen_van(ruw: str) -> list[str]:
    """De termen in een opsomming, zoals de graaf ze als één begrip draagt."""
    return _termen(ruw)


def _termen(ruw: str) -> list[str]:
    """"directeur, inspecteur of ontvanger" → drie termen; kleine letters, gewone spaties."""
    return [t.lower() for t in losse_termen(ruw)]


@dataclass(frozen=True)
class _Definitie:
    bron: Bron
    termen: tuple[str, ...]
    term_eind: int             # waar de term in de brontekst ophoudt; daarna begint de definiens
    soort: str
    bereik: Bereik


def _definitie(bron: Bron) -> _Definitie | None:
    if (m := _DEF_AANHEF.search(bron.aanhef)) and (t := _TERM_DUBBELPUNT.match(bron.tekst)):
        soort = (m.group(1) or "definitie").lower()
        return _Definitie(bron, tuple(_termen(t.group(1))), t.end(),
                          "definitie" if soort == "definitie" else soort,
                          bereik_uit(bron.aanhef, bron.bron_iri))
    if m := _DEF_INLINE.search(bron.tekst):
        soort = (m.group(1) or "definitie").lower()
        return _Definitie(bron, tuple(_termen(m.group(2))), m.end(),
                          "definitie" if soort == "definitie" else soort,
                          bereik_uit(bron.tekst[:m.start()] + " " + m.group(0), bron.bron_iri))
    for m in _DEF_ONDER.finditer(bron.tekst):
        zin_begin = max(bron.tekst.rfind(".", 0, m.start()), 0)
        if not (_WORDT.search(m.group(0)) or _WORDT.search(bron.tekst[zin_begin:m.start()])):
            continue
        soort = {"tevens": "mede", "ook": "mede"}.get((m.group("soort") or "").lower(),
                                                       (m.group("soort") or "definitie").lower())
        return _Definitie(bron, tuple(_termen(m.group("term"))), m.end(), soort,
                          bereik_uit(bron.tekst[zin_begin:m.end()], bron.bron_iri))
    return None


def definitie_van(bron: Bron) -> tuple[tuple[str, ...], str, Bereik] | None:
    """(termen, soort, bereik) als deze bron een begripsbepaling is; anders None (spoor M, het dossier)."""
    d = _definitie(bron)
    return (d.termen, d.soort, d.bereik) if d else None


def soort_van(bron: Bron) -> str | None:
    """`definitie`, `mede`, `niet` – wat voor bepaling dit is –, of None als het er geen is."""
    d = _definitie(bron)
    return d.soort if d else None


def gedefinieerde_termen(bron: Bron) -> tuple[str, ...]:
    """De termen die deze bron definieert (elke soort), genormaliseerd; leeg als ze geen definitie is."""
    d = _definitie(bron)
    return d.termen if d else ()


def definiens(bron: Bron) -> str | None:
    """De letterlijke definiens van een begripsbepaling – de tekst na de term –, of None.

    Alleen bij een echte definitie (niet "mede", "niet" of een opsomming): dat is wat een analist als
    letterlijke brondefinitie kan overnemen. De keten zelf gebruikt dit niet; de run in graph-qa
    (`agent/begrippen_run.py`) zet het bij een groep als voorstel."""
    d = _definitie(bron)
    if d is None or d.soort != "definitie":
        return None
    rest = bron.tekst[d.term_eind:].strip().lstrip(":").strip().rstrip(";").strip()
    return rest or None


# "de ontvanger, bedoeld in artikel 2, eerste lid, onderdeel i, van de Invorderingswet 1990": de definitie staat elders.
_DOORVERWIJZING = re.compile(r"^(?:(?:de|het|een)\s+)?(?P<term>[^,]{0,80}?),?\s+(?:(?:als|zoals)\s+)?bedoeld\s+in\b",
                             re.IGNORECASE)


def verwijst_door(definiens_: str, termen) -> bool:
    """Noemt deze definiens alleen de term zelf en waar die geregeld is? Dan is ze circulair: de betekenis staat op
    de plek waarnaar ze verwijst."""
    m = _DOORVERWIJZING.match((definiens_ or "").strip())
    return bool(m) and " ".join(m.group("term").lower().split()) in {" ".join(t.lower().split()) for t in termen}


def wettelijke_termen(manifest: Manifest, taal: dict[str, Taalanalyse]) -> list[WettelijkeTerm]:
    """Alle termen die de wet in dit manifest vastlegt, met bereik en (waar aanwezig) anker."""
    uit: list[WettelijkeTerm] = []
    per_bron: dict[str, list[Formulering]] = {}
    for f in manifest.formuleringen:
        per_bron.setdefault(f.bron_iri, []).append(f)
    for bron in manifest.bronnen:
        d = _definitie(bron)
        if d is None:
            continue
        fs = sorted(per_bron.get(bron.bron_iri, []), key=lambda f: (f.start, -f.eind))
        voor_term = [f for f in fs if f.eind <= d.term_eind and f.element_id in taal]
        ankers = {taal[f.element_id].term: f.element_id for f in voor_term}
        for ruw in d.termen:
            # De term zoals de taalstap hem normaliseert (meervoud → lemma), via zijn anker.
            anker = next((f.element_id for f in voor_term if " ".join(f.tekst.lower().split()) == ruw), "")
            term = taal[anker].term if anker else ruw
            uit.append(WettelijkeTerm(term, bron.bron_iri, d.bereik, d.soort, anker or ankers.get(term, "")))
        ankers |= {w.term: w.anker for w in uit if w.bron_iri == bron.bron_iri and w.anker}
        # Een opsommende definitie: twee of meer niet-overlappende formuleringen in de definiens,
        # en een lijstteken. Die onderdelen zijn zelf wettelijke termen (soorten van de term).
        definiens = [f for f in fs if f.start >= d.term_eind]
        los = [f for i, f in enumerate(definiens) if all(
            g.eind <= f.start or g.start >= f.eind for g in definiens[:i])]
        if d.soort == "definitie" and len(los) >= 2 and "," in bron.tekst[d.term_eind:]:
            boven = next((w.anker for w in uit if w.bron_iri == bron.bron_iri and w.soort == "definitie"),
                         "") if len(d.termen) == 1 else ""
            for f in los:
                t = taal.get(f.element_id)
                if t and not t.beperkt:
                    uit.append(WettelijkeTerm(t.term, bron.bron_iri, d.bereik, "opsomming",
                                              f.element_id, boven))
    return uit


def genus_van_mede(manifest: Manifest, wt: WettelijkeTerm) -> str:
    """Bij "verstaat mede onder X: Y …": de eerste formulering in de definiens (Y)."""
    bron = manifest.bron(wt.bron_iri)
    d = _definitie(bron)
    if d is None:
        return ""
    kandidaten = sorted((f for f in manifest.formuleringen
                         if f.bron_iri == wt.bron_iri and f.start >= d.term_eind),
                        key=lambda f: (f.start, -f.eind))
    return kandidaten[0].element_id if kandidaten else ""


def verwijzing_na(manifest: Manifest, bron_iri: str, tekst: str) -> str:
    """Het doel van een "(als) bedoeld in …" aan het begin van `tekst`, als IRI-prefix; anders ""."""
    m = _BEDOELD.match(tekst)
    if not m:
        return ""
    regeling, artikel, lid = regeling_van(bron_iri), _artikel_van(bron_iri), _lid_van(bron_iri)
    if m.group("art"):
        doel = f"{regeling}:artikel:{m.group('art')}"
        if m.group("lid"):
            if m.group("lid").lower() not in _RANG:
                return ""
            doel += f":lid:{_RANG[m.group('lid').lower()]}"
        if m.group("od"):
            doel += f":o:{m.group('od').lower()}"
        return doel
    if m.group("lid2"):
        if m.group("lid2").lower() not in _RANG:
            return ""
        doel = f"{artikel}:lid:{_RANG[m.group('lid2').lower()]}"
        return doel + (f":o:{m.group('od2').lower()}" if m.group("od2") else "")
    return f"{lid}:o:{m.group('od3').lower()}"


def bronnen_onder(manifest: Manifest, prefix: str) -> list[Bron]:
    return [b for b in manifest.bronnen if b.bron_iri == prefix or b.bron_iri.startswith(prefix + ":")]
