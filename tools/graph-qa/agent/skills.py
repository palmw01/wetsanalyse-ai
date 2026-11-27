"""Skills laden in drie niveaus (ADR-016 §A2), uit het bronpakket dat in het image zit (`bronpakket.json`, §B1).

1. **Naam en beschrijving** van elke methode-skill staan in het vaste voorvoegsel van de centrale agent
   (`beschrijvingen`): zo werkt een nieuwe skill zonder code.
2. **De kern** laadt de agent met `laad_skill(skill)`: de secties die de skill aan de rol `agent` geeft
   (`agentrollen.json`), en zonder zulke secties de tekst van `SKILL.md` zonder de frontmatter.
3. **Een reference** leest hij met `lees_skill(skill, sectie)`: `references/<sectie>.md`.

Skilltekst is methode, geen bron: het resultaat komt niet in de `source_trace` en niet in het bronregister (het is het
toolresultaat van een overdracht, zoals een rapport). Een skill geeft geen tools: wat mag, zegt het profiel.
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path

from bronmodel.plugins import SKILLS as PLUGIN_SKILLS

PAKKET = Path(__file__).resolve().parent / "bronpakket.json"
#: Hoeveel tekens een reference hoogstens meegeeft; de rest staat er niet, en het resultaat zegt dat.
MAX_REFERENCE = 20_000
#: Hoeveel tekens een beschrijving in het voorvoegsel hoogstens heeft (~honderd tokens per skill).
MAX_BESCHRIJVING = 500

_FRONT = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


@functools.cache
def _skills() -> dict[str, dict[str, str]]:
    """Per methode-skill de bestanden (pad → tekst), uit het bronpakket."""
    onderdelen = json.loads(PAKKET.read_text(encoding="utf-8")).get("onderdelen") or {}
    return {o["naam"]: dict(o.get("bestanden") or {}) for o in onderdelen.values() if o.get("soort") == "skill"}


def namen() -> tuple[str, ...]:
    """De methode-skills die de centrale agent kent. Een plugin-skill (`bronmodel.plugins.SKILLS`) niet: die werkt via
    de route van zijn plugin, en staat zo niet in het vaste voorvoegsel (plan contenttoets, C2)."""
    return tuple(sorted(n for n in _skills() if n not in PLUGIN_SKILLS))


def _frontmatter(tekst: str) -> tuple[str, str]:
    m = _FRONT.match(tekst or "")
    return (m.group(1), tekst[m.end():]) if m else ("", tekst or "")


def beschrijving(skill: str) -> str:
    """De `description` uit de frontmatter van `SKILL.md`, op één regel."""
    kop, _ = _frontmatter(_skills()[skill].get("SKILL.md", ""))
    m = re.search(r"^description:\s*+(.+?)(?=(?:^\S)|\Z)", kop, re.S | re.M)
    tekst = " ".join((m.group(1) if m else "").split()).strip("'\"")
    return tekst if len(tekst) <= MAX_BESCHRIJVING else tekst[:MAX_BESCHRIJVING].rsplit(" ", 1)[0] + " …"


def beschrijvingen() -> str:
    """Het blok SKILLS voor het vaste voorvoegsel: per skill de naam en de beschrijving, en hoe je ze laadt."""
    regels = [f"- {n}: {beschrijving(n)}" for n in namen()]
    return ("SKILLS: de methodes die Lex kent. Laad de kern van een skill met laad_skill als de vraag om die methode "
            "gaat, en lees een reference met lees_skill als je een onderdeel nodig hebt. Skilltekst is methode, geen "
            "bron: citeer hem niet als vindplaats.\n" + "\n".join(regels))


def references(skill: str) -> list[str]:
    return sorted(p.removeprefix("references/").removesuffix(".md") for p in _skills().get(skill, {})
                  if p.startswith("references/") and p.endswith(".md"))


def kern(skill: str) -> str:
    """Niveau 2: de secties van de rol `agent` uit `agentrollen.json`, anders `SKILL.md` zonder frontmatter."""
    bestanden = _skills()[skill]
    try:
        rollen = json.loads(bestanden.get("agentrollen.json") or "{}")
    except ValueError:
        rollen = {}
    ids = (rollen.get("rollen") or {}).get("agent") or [] if isinstance(rollen.get("rollen"), dict) else []
    secties = rollen.get("secties") or {}
    if ids and all(isinstance(secties.get(i), dict) for i in ids):
        delen = []
        for i in ids:
            s = secties[i]
            bron = bestanden.get(str(s.get("bestand") or ""), "")
            delen.append(f"[{i}]\n{_sectie(bron, i)}")
        tekst = "\n\n".join(d for d in delen if d.strip())
    else:
        tekst = _frontmatter(bestanden.get("SKILL.md", ""))[1].strip()
    lijst = references(skill)
    return (f"SKILL {skill} (methode, geen bron)\n\n{tekst}"
            + (f"\n\nReferences (lees_skill): {', '.join(lijst)}" if lijst else ""))


def _sectie(tekst: str, sectie_id: str) -> str:
    """De tekst tussen de methodemarkers van een sectie (`<!-- methode:<id>:begin -->` … `<!-- methode:<id>:end -->`)."""
    m = re.search(rf"<!--\s*methode:{re.escape(sectie_id)}:begin\s*-->(.*?)<!--\s*methode:{re.escape(sectie_id)}:end\s*-->",
                  tekst, re.S)
    return m.group(1).strip() if m else ""


def lees(skill: str, sectie: str) -> str | None:
    """Niveau 3: `references/<sectie>.md`, begrensd op `MAX_REFERENCE` tekens; None als hij niet bestaat."""
    naam = sectie.strip().removeprefix("references/").removesuffix(".md")
    tekst = _skills().get(skill, {}).get(f"references/{naam}.md")
    if tekst is None:
        return None
    if len(tekst) > MAX_REFERENCE:
        tekst = tekst[:MAX_REFERENCE].rsplit("\n", 1)[0] + "\n[… de rest van deze reference staat er niet bij]"
    return f"SKILL {skill}, reference {naam} (methode, geen bron)\n\n{tekst}"


def antwoord(soort: str, skill: str, sectie: str = "") -> tuple[str, bool]:
    """(de tekst voor het model, geslaagd)."""
    if skill not in namen():
        return f"De skill '{skill}' bestaat niet. Kies uit: {', '.join(namen())}.", False
    if soort == "laad":
        return kern(skill), True
    tekst = lees(skill, sectie)
    if tekst is None:
        return (f"De skill {skill} heeft geen reference '{sectie}'. Kies uit: {', '.join(references(skill))}.", False)
    return tekst, True


