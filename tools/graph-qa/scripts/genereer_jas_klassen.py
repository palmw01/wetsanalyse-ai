#!/usr/bin/env python3
"""Genereer het JAS_KLASSEN-blok in `agent/jas_klassen.py` uit de wetsanalyse-skill.

WAAROM DIT BESTAAT
------------------
De methode Wetsanalyse zat op twee plekken: als leesbare markdown in de skill
(`.claude/skills/wetsanalyse/`) en als Python-strings in `agent/jas_klassen.py`. Alleen de
klasse-*namen* waren tegen drift bewaakt; de inhoudelijke duiding eromheen niet — en die liep
aantoonbaar uit elkaar. De skill was op zeven plekken armer dan zijn eigen bron, het zwaarst bij
Delegatiebevoegdheid.

Sindsdien is `references/jas-klassen-referentie.md` de bron en is dit blok afgeleid. Wie de
methode wil bijsturen bewerkt de markdown en draait dit script; `tests/test_methode_drift.py`
faalt zodra dat vergeten is.

WAT HET NIET DOET
-----------------
Het schrijft geen prompt en het verkort niets. De referentie draagt de volledige bronvelden en
die komen ongewijzigd in de code terecht; hoeveel daarvan in een prompt terechtkomt beslist
`agent/annotatie_prompt.py`. Zo blijft "één bron van waarheid" gescheiden van "hoe groot mag de
prompt zijn" — twee vragen die anders door elkaar gaan lopen.

Alleen het blok tussen de GEGENEREERD-markers wordt vervangen. `REGELS`, `RegelType` en de
afgeleide `JAS_KLASSEN_VOLGORDE` blijven handwerk.

GEBRUIK
-------
    .venv/bin/python scripts/genereer_jas_klassen.py           # schrijf
    .venv/bin/python scripts/genereer_jas_klassen.py --check   # faal bij verschil (CI/test)
"""
from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[3]
REFERENTIE = WORTEL / ".claude" / "skills" / "wetsanalyse" / "references" / "jas-klassen-referentie.md"
DOEL = WORTEL / "tools" / "graph-qa" / "agent" / "jas_klassen.py"

BEGIN = "# --- BEGIN GEGENEREERD uit de wetsanalyse-skill (scripts/genereer_jas_klassen.py) ---"
EINDE = "# --- EINDE GEGENEREERD ---"

# De drie bronvelden per klasse, in de volgorde waarin ze in de dataclass staan.
VELDEN = ("Omschrijving", "Vraag", "Uitdrukkingswijze")


class ReferentieFout(RuntimeError):
    """De referentie is niet te lezen zoals verwacht – beter falen dan half genereren."""


def _schoon(tekst: str) -> str:
    """Markdown-opmaak eruit, whitespace platslaan.

    De referentie is voor mensen geschreven: vet voor nadruk, een tabel bij de klassen die de
    JAS-tabel apart nummert, en blockquotes voor eigen toevoegingen. Voor de code telt alleen de
    lopende tekst.
    """
    tekst = re.sub(r"^\s*>.*$", "", tekst, flags=re.M)          # blockquotes (eigen toevoegingen)
    tekst = re.sub(r"^\s*\|.*$", "", tekst, flags=re.M)         # tabelregels
    tekst = re.sub(r"\*\*(.+?)\*\*", r"\1", tekst, flags=re.S)  # vet
    tekst = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", tekst, flags=re.S)  # cursief
    tekst = re.sub(r"`([^`]+)`", r"\1", tekst)                  # code-spans
    tekst = re.sub(r"^\s*-\s+", "", tekst, flags=re.M)          # lijstbullets
    return " ".join(tekst.split())


def lees_klassen(pad: Path = REFERENTIE) -> list[tuple[str, str, str, str]]:
    """(naam, omschrijving, vraag, uitdrukkingswijze) per klasse, uit de skill-referentie."""
    if not pad.exists():
        raise ReferentieFout(f"referentie ontbreekt: {pad}")
    secties = re.split(r"\n## (?=\d+\. )", pad.read_text(encoding="utf-8"))[1:]
    if not secties:
        raise ReferentieFout(f"geen klasse-secties ('## N. Naam') gevonden in {pad}")

    uit: list[tuple[str, str, str, str]] = []
    for sectie in secties:
        naam = sectie.split("\n", 1)[0].split(". ", 1)[1].strip()
        waarden = []
        for veld in VELDEN:
            # "**Veld** (`H2:44`) — tekst", tot aan het volgende vetgedrukte kopje, een
            # blockquote, een nieuwe sectie of het eind.
            m = re.search(
                rf"\*\*{veld}\*\*[^—]*—\s*(.+?)(?=\n\n\*\*|\n\n>|\n\n##|\n---|\Z)",
                sectie, re.S,
            )
            if not m:
                raise ReferentieFout(f"klasse {naam!r}: veld {veld!r} niet gevonden")
            waarden.append(_schoon(m.group(1)))
        uit.append((naam, *waarden))
    return uit


def _escape(tekst: str) -> str:
    """Veilig in een dubbelgequote Python-string. De referentie citeert de bron letterlijk en
    gebruikt daarvoor rechte aanhalingstekens; zonder escapen breekt dat het gegenereerde bestand
    (dat gebeurde bij Delegatiebevoegdheid, de enige klasse met een citaat in de omschrijving)."""
    return tekst.replace("\\", "\\\\").replace('"', '\\"')


def _veld(naam: str, waarde: str, inspring: str = "        ") -> str:
    """Eén dataclass-veld, met regelafbreking als de waarde lang is."""
    kort = f'{inspring}{naam}="{_escape(waarde)}",'
    if len(kort) <= 110:
        return kort
    regels = textwrap.wrap(waarde, width=104 - len(inspring)) or [""]
    binnen = inspring + "    "
    body = "\n".join(f'{binnen}"{_escape(r)}{" " if i < len(regels) - 1 else ""}"'
                     for i, r in enumerate(regels))
    return f"{inspring}{naam}=(\n{body}\n{inspring}),"


def bouw_blok(klassen: list[tuple[str, str, str, str]]) -> str:
    delen = [
        BEGIN,
        "# Niet met de hand bijwerken: bewerk",
        "# .claude/skills/wetsanalyse/references/jas-klassen-referentie.md en draai",
        "# scripts/genereer_jas_klassen.py. De volledige bronvelden staan daar, met",
        "# regelverwijzingen naar docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md.",
        "JAS_KLASSEN: tuple[JasKlasse, ...] = (",
    ]
    for naam, omschrijving, vraag, uitdrukking in klassen:
        delen.append("    JasKlasse(")
        delen.append(_veld("naam", naam))
        delen.append(_veld("omschrijving", omschrijving))
        delen.append(_veld("vraag", vraag))
        delen.append(_veld("uitdrukkingswijze", uitdrukking))
        delen.append("    ),")
    delen.append(")")
    delen.append(EINDE)
    return "\n".join(delen)


def vervang(huidig: str, blok: str) -> str:
    start, stop = huidig.find(BEGIN), huidig.find(EINDE)
    if start == -1 or stop == -1:
        raise ReferentieFout(
            f"markers niet gevonden in {DOEL.name}; verwacht {BEGIN!r} en {EINDE!r}"
        )
    return huidig[:start] + blok + huidig[stop + len(EINDE):]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="niets schrijven; exitcode 1 als het bestand niet bij de skill past")
    args = p.parse_args()

    verwacht = vervang(DOEL.read_text(encoding="utf-8"), bouw_blok(lees_klassen()))
    if args.check:
        if verwacht != DOEL.read_text(encoding="utf-8"):
            print(f"{DOEL.relative_to(WORTEL)} loopt uit de pas met de skill-referentie.\n"
                  f"Draai: .venv/bin/python scripts/genereer_jas_klassen.py", file=sys.stderr)
            return 1
        print("jas_klassen.py komt overeen met de skill-referentie.")
        return 0

    DOEL.write_text(verwacht, encoding="utf-8")
    print(f"{DOEL.relative_to(WORTEL)} bijgewerkt uit {REFERENTIE.relative_to(WORTEL)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
