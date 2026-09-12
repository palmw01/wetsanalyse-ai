#!/usr/bin/env python3
"""Genereer klassendefinities en het methodepakket uit de wetsanalyse-skill.

De volledige klassevelden komen uit references/jas-klassen-referentie.md.
agentrollen.json selecteert expliciete secties voor het standalone methodepakket.
De metadata in SKILL.md bevat de enige machineleesbare methodeversie.
REGELS en afgeleide klassevolgorde blijven buiten het gegenereerde klasseblok.

Gebruik: .venv/bin/python scripts/genereer_jas_klassen.py [--check]
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
    delen.extend([
        "# Compatibiliteitsnamen; inhoud staat uitsluitend in het methodepakket.",
        "from .methodepakket import PAKKET as _METHODEPAKKET",
        "ANNOTATIEPROTOCOL_VERSIE = _METHODEPAKKET['versie']",
        "ANNOTATIEPROTOCOL = {naam: _METHODEPAKKET['secties']['annotatie-' + key]['tekst']",
        "    for naam, key in [('Gedeeld', 'gedeeld'), ('Kandidaten', 'kandidaten'),",
        "                      ('Classificatie', 'classificatie'), ('Review', 'review')]}",
    ])
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

    sys.path.insert(0, str(DOEL.parents[1]))
    from scripts.genereer_methodepakket import DOEL as PAKKET_DOEL, genereer
    pakket = genereer()  # Valideer alles vóór een van beide bestanden te schrijven.
    verwacht = vervang(DOEL.read_text(encoding="utf-8"), bouw_blok(lees_klassen()))
    if args.check and (not PAKKET_DOEL.exists() or PAKKET_DOEL.read_text() != pakket):
        print("methodepakket.py wijkt af: draai scripts/genereer_jas_klassen.py", file=sys.stderr)
        return 1
    if not args.check:
        PAKKET_DOEL.write_text(pakket, encoding="utf-8")
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
