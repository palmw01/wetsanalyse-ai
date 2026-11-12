"""De validator van een methode-skill (ADR-016 §B2, poort 1): de Agent Skills-specificatie plus de regels van Lex.

Eén validator voor de generator van het methodepakket (`tools/graph-qa/scripts/genereer_methodepakket.py`) en voor de
werkplaats, die een skill bij elke opslag toetst. Wat de werkplaats accepteert, landt dus ook in de generator, en de
werkplaats weigert wat de generator zou weigeren. Een skill is hier een afbeelding van pad naar tekst: de generator leest
hem van schijf (`lees_map`), de werkplaats uit een opgeslagen versie.

**De specificatie** (een skill is een map met `SKILL.md`, zoals Claude Code hem leest):
- `name`: kleine letters, cijfers en losse koppeltekens, hoogstens 64 tekens, gelijk aan de mapnaam;
- `description`: verplicht, hoogstens 1024 tekens. Dit is wat een agent van de skill ziet voordat hij hem laadt;
- `license`, `compatibility` en `metadata` (tekst naar tekst) mogen; andere velden niet.

**De regels van Lex** bovenop de specificatie:
- `metadata.methode_versie` en precies de vijf `metadata.lex_*`-velden (soort, label, herkomst, licentie, letterlijk);
- letterlijke tekst van derden vraagt een `BRON.md` met de licentie (de repo is publiek);
- `agentrollen.json` wijst de methodesecties aan en verdeelt ze over de rollen. Een skill vult alleen rollen die
  bestaan: een nieuwe rol vraagt code en een meting (ADR-014 §5);
- elke sectie noemt broncodes uit het bronregister van de skill (`references/bronnen.md`);
- sectie-id's en broncodes zijn uniek over alle skills heen (`toets_samen`);
- een skill geeft geen tools (`allowed-tools`): wat mag, zegt het agentprofiel (ADR-016 §A2);
- een grens op de omvang: een skill gaat als tekst in de context van een model.

Regels uit een skill (`regels/`) toetst de generator zelf: die leunen op de ketens van graph-qa en blijven buiten de
werkplaats (ADR-016 §B2).
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .methodesectie import MAX_TEKENS, SectieFout, lees_sectie
from .validatie import Bevinding, ValidatieFout, frontmatter, uniek

HOOFDBESTAND = "SKILL.md"
ROLBESTAND = "agentrollen.json"
BRONREGISTER = "references/bronnen.md"
BRONBESTAND = "BRON.md"

#: De Agent Skills-specificatie.
NAAM = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_NAAM = 64
MAX_BESCHRIJVING = 1024
MAX_COMPATIBILITEIT = 500
SPEC_VELDEN = frozenset({"name", "description", "license", "compatibility", "metadata", "allowed-tools"})

#: De basis-skill: hij vult alle methoderollen; een andere skill vult een deel.
BASIS = "wetsanalyse"
#: De methoderollen die bestaan. Een rol hoort hier alleen als een modelaanroep hem draagt (`llm_stap.Rol` in graph-qa,
#: bewaakt door `tests/test_methoderollen.py`); een skill kan er geen maken (ADR-014 §5). Geen annotatierollen: de
#: annotatieketen (ADR-001) gebruikt geen generatieve prompts met methodetekst. `agent` is de generieke rol van de
#: centrale agent (ADR-016 §A2). Eén lijst voor de generator van het methodepakket en voor de werkplaats in de api.
ROLLEN = frozenset({"supervisor", "retrieval", "definitie", "duiding", "algemeen", "deelvragen", "agent"})

#: De regels van Lex.
LEX_VELDEN = frozenset({"soort", "label", "herkomst", "licentie", "letterlijk"})
SOORT = "methode"
BRONCODE = re.compile(r"^\| ([A-Z]{1,3}\d+) \|", re.M)
SECTIE_VELDEN = frozenset({"bestand", "bronnen"})

#: De omvang. `SKILL.md` is de router en blijft kort (de specificatie raadt 500 regels aan); een sectie gaat letterlijk
#: in een systeemprompt (`methodesectie.MAX_TEKENS`).
MAX_REGELS_HOOFDBESTAND = 500
MAX_TEKENS_BESTAND = 100_000
MAX_TEKENS_SKILL = 1_000_000
MAX_BESTANDEN = 200


def sha(tekst: str) -> str:
    return hashlib.sha256(tekst.encode()).hexdigest()


@dataclass(frozen=True)
class Skill:
    """Een gevalideerde methode-skill: wat het methodepakket en de catalogus van hem nodig hebben."""

    naam: str
    #: `metadata.methode_versie`.
    versie: str
    #: De `lex_*`-velden zonder voorvoegsel, plus `beschrijving` (de `description`).
    lex: dict[str, str]
    #: Per rol de sectie-id's die hij krijgt, in volgorde.
    rollen: dict[str, list[str]]
    #: Per sectie-id: `bestand`, `bronnen`, `tekst`, `sha256` en `skill`.
    secties: dict[str, dict[str, Any]]
    #: De bestanden die het gedrag bepalen: de identiteit van het pakket rust op hun hash.
    bestanden: frozenset[str]


def lees_map(pad: Path) -> dict[str, str]:
    """De skill op schijf als afbeelding van pad naar tekst. Een skill van Lex bevat alleen tekst."""
    uit: dict[str, str] = {}
    for p in sorted(pad.rglob("*")):
        if not p.is_file():
            continue
        naam = p.relative_to(pad).as_posix()
        try:
            uit[naam] = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ValidatieFout(pad.name, [Bevinding("tekst", "het bestand is geen tekst (UTF-8)", naam)]) from None
    return uit


def is_methode(hoofdbestand: str) -> bool:
    """Of een `SKILL.md` zich een methode-skill van Lex noemt (`metadata.lex_soort`). Een skill die alleen voor Claude
    Code is, telt niet mee. Is de frontmatter onleesbaar maar noemt hij `lex_soort`, dan telt hij wel: `toets` meldt
    dan wat er mis is, in plaats van dat de skill stil uit het pakket valt."""
    try:
        kop, _ = frontmatter(hoofdbestand)
    except ValueError:
        return "lex_soort" in hoofdbestand
    metadata = kop.get("metadata")
    return isinstance(metadata, dict) and metadata.get("lex_soort") == SOORT


def _omvang(bestanden: Mapping[str, str]) -> list[Bevinding]:
    uit = []
    if len(bestanden) > MAX_BESTANDEN:
        uit.append(Bevinding("omvang", f"meer dan {MAX_BESTANDEN} bestanden"))
    for naam, tekst in bestanden.items():
        if len(tekst) > MAX_TEKENS_BESTAND:
            uit.append(Bevinding("omvang", f"langer dan {MAX_TEKENS_BESTAND} tekens", naam))
    if sum(len(t) for t in bestanden.values()) > MAX_TEKENS_SKILL:
        uit.append(Bevinding("omvang", f"de skill is langer dan {MAX_TEKENS_SKILL} tekens"))
    if len(bestanden.get(HOOFDBESTAND, "").splitlines()) > MAX_REGELS_HOOFDBESTAND:
        uit.append(Bevinding("omvang", f"langer dan {MAX_REGELS_HOOFDBESTAND} regels", HOOFDBESTAND))
    return uit


def _specificatie(naam: str, kop: dict[str, Any]) -> list[Bevinding]:
    """De Agent Skills-specificatie op de frontmatter."""
    def fout(code: str, melding: str) -> Bevinding:
        return Bevinding(code, melding, HOOFDBESTAND)

    uit = []
    if vreemd := sorted(set(kop) - SPEC_VELDEN):
        uit.append(fout("frontmatter", f"onbekende velden {vreemd}; toegestaan zijn {sorted(SPEC_VELDEN)}"))
    name = kop.get("name")
    if not isinstance(name, str) or not NAAM.fullmatch(name) or len(name) > MAX_NAAM:
        uit.append(fout("naam", f"name: kleine letters, cijfers en losse koppeltekens, hoogstens {MAX_NAAM} tekens"))
    elif name != naam:
        uit.append(fout("naam", f"name is {name!r}, maar de map heet {naam!r}"))
    beschrijving = kop.get("description")
    if not isinstance(beschrijving, str) or not beschrijving.strip():
        uit.append(fout("beschrijving", "description is verplicht"))
    elif len(beschrijving) > MAX_BESCHRIJVING:
        uit.append(fout("beschrijving", f"description is langer dan {MAX_BESCHRIJVING} tekens"))
    if "license" in kop and (not isinstance(kop["license"], str) or not kop["license"].strip()):
        uit.append(fout("frontmatter", "license is tekst"))
    if "compatibility" in kop:
        c = kop["compatibility"]
        if not isinstance(c, str) or not 1 <= len(c) <= MAX_COMPATIBILITEIT:
            uit.append(fout("frontmatter", f"compatibility is tekst van hoogstens {MAX_COMPATIBILITEIT} tekens"))
    metadata = kop.get("metadata", {})
    if not isinstance(metadata, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()):
        uit.append(fout("metadata", "metadata beeldt tekst af op tekst (zet een waarde tussen aanhalingstekens)"))
    return uit


def _lex(kop: dict[str, Any], bestanden: Mapping[str, str]) -> list[Bevinding]:
    """De velden van Lex in de frontmatter. Gaat uit van een metadata die de specificatie haalt."""
    def fout(code: str, melding: str) -> Bevinding:
        return Bevinding(code, melding, HOOFDBESTAND)

    uit = []
    metadata = kop.get("metadata", {})
    if not metadata.get("methode_versie", "").strip() or "\n" in metadata["methode_versie"]:
        uit.append(fout("versie", "metadata.methode_versie is verplicht"))
    lex = {k.removeprefix("lex_"): v for k, v in metadata.items() if k.startswith("lex_")}
    if set(lex) != LEX_VELDEN or not all(v.strip() for v in lex.values()):
        uit.append(fout("lex", f"metadata.lex_*: precies {sorted(LEX_VELDEN)} vereist, elk met een waarde"))
    elif lex["soort"] != SOORT:
        uit.append(fout("lex", f"metadata.lex_soort is {SOORT!r}"))
    elif lex["letterlijk"] not in ("ja", "nee"):
        uit.append(fout("lex", "metadata.lex_letterlijk is 'ja' of 'nee'"))
    elif lex["letterlijk"] == "ja" and BRONBESTAND not in bestanden:
        uit.append(Bevinding("licentie", f"letterlijke tekst van derden vraagt een {BRONBESTAND} met de licentie"))
    if "allowed-tools" in kop:
        uit.append(fout("tools", "een skill geeft geen tools (allowed-tools); wat mag, zegt het agentprofiel"))
    return uit


def _rolbestand(bestanden: Mapping[str, str]) -> tuple[dict[str, Any] | None, list[Bevinding]]:
    def fout(melding: str) -> tuple[None, list[Bevinding]]:
        return None, [Bevinding("rolbestand", melding, ROLBESTAND)]

    if ROLBESTAND not in bestanden:
        return fout("ontbreekt")
    try:
        mapping = json.loads(bestanden[ROLBESTAND])
    except json.JSONDecodeError as f:
        return fout(f"geen geldige JSON: {f}")
    if not isinstance(mapping, dict) or set(mapping) != {"secties", "rollen"} \
            or not isinstance(mapping["secties"], dict) or not isinstance(mapping["rollen"], dict):
        return fout("precies de velden 'secties' en 'rollen' vereist")
    return mapping, []


def _pad(bestand: Any, bestanden: Mapping[str, str]) -> str | None:
    """Het pad van een sectiebestand binnen de skill, of None als het erbuiten wijst of niet bestaat."""
    if not isinstance(bestand, str):
        return None
    pad = PurePosixPath(bestand)
    if pad.is_absolute() or ".." in pad.parts or pad.as_posix() not in bestanden:
        return None
    return pad.as_posix()


def _secties(naam: str, mapping: dict[str, Any], bestanden: Mapping[str, str]) -> tuple[dict[str, dict], list[Bevinding]]:
    uit: list[Bevinding] = []
    if BRONREGISTER not in bestanden:
        uit.append(Bevinding("bronregister", "ontbreekt", BRONREGISTER))
    bekend = set(BRONCODE.findall(bestanden.get(BRONREGISTER, "")))
    secties: dict[str, dict] = {}
    for key, spec in mapping["secties"].items():
        if not isinstance(spec, dict) or set(spec) != SECTIE_VELDEN:
            uit.append(Bevinding("sectie", f"sectie {key}: precies {sorted(SECTIE_VELDEN)} vereist", ROLBESTAND))
            continue
        pad = _pad(spec["bestand"], bestanden)
        if pad is None:
            uit.append(Bevinding("pad", f"sectie {key}: het bestand {spec['bestand']!r} staat niet in de skill", ROLBESTAND))
            continue
        try:
            inhoud = lees_sectie(bestanden[pad], key)
        except SectieFout as f:
            uit.append(Bevinding("sectie", str(f), pad))
            continue
        if len(inhoud) > MAX_TEKENS:
            uit.append(Bevinding("omvang", f"sectie {key} is langer dan {MAX_TEKENS} tekens", pad))
        bronnen = spec["bronnen"]
        if not isinstance(bronnen, list) or not bronnen or not set(bronnen) <= bekend:
            uit.append(Bevinding("broncode", f"sectie {key}: lege of onbekende broncodes (zie {BRONREGISTER})", ROLBESTAND))
            continue
        secties[key] = {**spec, "tekst": inhoud, "sha256": sha(inhoud), "skill": naam}
    return secties, uit


def _rollen(mapping: dict[str, Any], secties: Collection[str], rollen: Collection[str], basis: bool) -> list[Bevinding]:
    uit = []
    if basis and set(mapping["rollen"]) != set(rollen):
        uit.append(Bevinding("rol", f"de basis-skill vult precies de rollen {sorted(rollen)}", ROLBESTAND))
    # Een skill zonder rollen mag: dan staat hij in het pakket en de catalogus, maar verandert hij geen prompt. Zo komt
    # een nieuwe methode binnen zonder het gedrag van Lex te raken; de koppeling aan een rol volgt na een meting.
    if not basis and not set(mapping["rollen"]) <= set(rollen):
        uit.append(Bevinding("rol", f"een skill vult alleen bestaande rollen aan ({sorted(rollen)})", ROLBESTAND))
    for rol, ids in mapping["rollen"].items():
        if not isinstance(ids, list) or not ids or not uniek(ids) or not set(ids) <= set(secties):
            uit.append(Bevinding("rol", f"rol {rol}: een lege, dubbele of onbekende sectieselectie", ROLBESTAND))
    return uit


def toets(naam: str, bestanden: Mapping[str, str], *, rollen: Collection[str] = ROLLEN,
          basis: bool = False) -> tuple[Skill | None, list[Bevinding]]:
    """De skill `naam` (de mapnaam) tegen de specificatie en de regels van Lex. Geeft de skill en alle bevindingen; de
    skill is None zodra er één bevinding is.

    `rollen` zijn de methoderollen die bestaan (de generator kent ze; een skill kan er geen maken). De basis-skill
    vult ze allemaal, een andere skill een deel."""
    uit = _omvang(bestanden)
    if HOOFDBESTAND not in bestanden:
        return None, [*uit, Bevinding("frontmatter", "ontbreekt", HOOFDBESTAND)]
    try:
        kop, _ = frontmatter(bestanden[HOOFDBESTAND])
    except ValueError as f:
        return None, [*uit, Bevinding("frontmatter", str(f), HOOFDBESTAND)]
    spec = _specificatie(naam, kop)
    uit += spec
    # De velden van Lex staan in de metadata: zonder geldige metadata valt daar niets over te zeggen.
    if not any(b.code == "metadata" for b in spec):
        uit += _lex(kop, bestanden)
    mapping, fouten = _rolbestand(bestanden)
    uit += fouten
    secties: dict[str, dict] = {}
    if mapping is not None:
        secties, fouten = _secties(naam, mapping, bestanden)
        uit += fouten
        # Een sectie die zelf al een bevinding heeft, hoeft bij haar rol niet nog eens te vallen.
        uit += _rollen(mapping, mapping["secties"] if fouten else secties, rollen, basis)
    if uit or mapping is None:
        return None, uit
    metadata = kop["metadata"]
    lex = {k.removeprefix("lex_"): v for k, v in metadata.items() if k.startswith("lex_")}
    vast = {HOOFDBESTAND, ROLBESTAND, BRONREGISTER} | {s["bestand"] for s in secties.values()}
    return Skill(
        naam=naam, versie=metadata["methode_versie"], lex=lex | {"beschrijving": kop["description"]},
        rollen={r: list(ids) for r, ids in mapping["rollen"].items()}, secties=secties,
        bestanden=frozenset(vast | ({BRONBESTAND} if BRONBESTAND in bestanden else set())),
    ), []


def valideer(naam: str, bestanden: Mapping[str, str], *, rollen: Collection[str] = ROLLEN,
             basis: bool = False) -> Skill:
    """Zoals `toets`, maar gooit `ValidatieFout` met alle bevindingen."""
    skill, bevindingen = toets(naam, bestanden, rollen=rollen, basis=basis)
    if skill is None:
        raise ValidatieFout(naam, bevindingen)
    return skill


def toets_samen(skills: list[Skill]) -> list[Bevinding]:
    """Wat alleen over de skills heen te toetsen is: een sectie-id en een broncode zijn van één skill. De eerste skill
    in de lijst houdt hem; de bevinding valt bij de latere."""
    uit = []
    secties: dict[str, str] = {}
    codes: dict[str, str] = {}
    for skill in skills:
        if dubbel := sorted(k for k in skill.secties if secties.get(k, skill.naam) != skill.naam):
            uit.append(Bevinding("sectie", f"{skill.naam}: sectie-id al in gebruik: {dubbel}", ROLBESTAND))
        for c in sorted({c for s in skill.secties.values() for c in s["bronnen"]}):
            if codes.get(c, skill.naam) != skill.naam:
                uit.append(Bevinding("broncode", f"{skill.naam}: broncode {c} is al van {codes[c]}", ROLBESTAND))
        secties |= {k: skill.naam for k in skill.secties if k not in secties}
        codes |= {c: skill.naam for s in skill.secties.values() for c in s["bronnen"] if c not in codes}
    return uit
