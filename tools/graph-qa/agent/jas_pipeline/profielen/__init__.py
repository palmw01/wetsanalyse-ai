"""Detectieprofielen per JAS-klasse (ADR-001 PR 4).

Per klasse één YAML-bestand met de velden uit §3 van de opdracht: welke grammaticale, lexicale,
structurele en semantische signalen een kandidaat opleveren, met welke klassen hij verward kan
worden, wat er uitdrukkelijk géén kandidaat is, en welk deel een taalmodel nog moet beslissen.

**De officiële tekst staat hier niet in.** Definitie, herkenningsvraag en uitdrukkingswijze komen bij
het laden uit `jas_klassen.JAS_KLASSEN`, dat op zijn beurt uit de skill en `H2-JAS.md` wordt
gegenereerd. Een profiel draagt alleen de regelverwijzingen (`H2:NN`), en een drift-test controleert
dat die regels in `H2-JAS.md` precies het veld van die klasse bevatten. Zo kan een profiel de
officiële tekst niet stilletjes herschrijven.

**Een signaal is geen classificatie.** Een profiel beschrijft waar een kandidaat vandaan kan komen,
niet dat die kandidaat die klasse ís (ADR-001 §4). `possible_classes` op een kandidaat komt uit het
profiel; de beslissing valt later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from ...jas_klassen import JAS_KLASSEN, JAS_KLASSEN_VOLGORDE, REGELS

MAP = Path(__file__).parent


def _docs() -> Path:
    """De docs-map van de repo. Bestaat alleen in een werkkopie, niet in het image (/app/agent/…):
    daarom lui en pas bij gebruik – de profielen zelf hebben hem niet nodig."""
    for ouder in Path(__file__).resolve().parents:
        if (ouder / "docs" / "wetsanalyse").is_dir():
            return ouder / "docs" / "wetsanalyse"
    raise ProfielFout("docs/wetsanalyse niet gevonden: alleen beschikbaar in een werkkopie van de repo")


def h2_pad() -> Path:
    return _docs() / "wetsanalyse-rijk" / "H2-JAS.md"


def referentieset_pad() -> Path:
    return _docs() / "referentieset" / "cases.json"

VELDEN = (
    "jas_class", "bron", "begrippen", "syntactic_signals", "lexical_signals", "semantic_signals",
    "structural_signals", "candidate_rules", "confusable_classes", "negative_patterns",
    "required_context", "deterministic_detection_possible", "llm_needed_for", "test_cases",
)
DETERMINISME = ("hoog", "middel", "laag")
REGELSTATUS = ("gepland", "geïmplementeerd")
TESTSTATUS = ("provisional", "synthetic")
VERWACHT = ("kandidaat", "geen")


class ProfielFout(ValueError):
    pass


@dataclass(frozen=True)
class Profiel:
    jas_class: str
    official_definition: str
    official_recognition_intent: str
    official_expression_patterns: str
    bron: dict[str, str]
    data: dict[str, Any]

    def __getattr__(self, naam: str) -> Any:          # de §3-velden als attributen
        try:
            return self.__dict__["data"][naam]
        except KeyError as exc:
            raise AttributeError(naam) from exc


def _fout(bestand: str, bericht: str) -> ProfielFout:
    return ProfielFout(f"{bestand}: {bericht}")


def _controleer(bestand: str, d: dict[str, Any]) -> None:
    ontbreekt = [v for v in VELDEN if v not in d]
    extra = [k for k in d if k not in VELDEN]
    if ontbreekt or extra:
        raise _fout(bestand, f"velden ontbreken {ontbreekt} of onbekend {extra}")
    if d["jas_class"] not in JAS_KLASSEN_VOLGORDE:
        raise _fout(bestand, f"onbekende JAS-klasse {d['jas_class']!r}")
    if set(d["bron"]) != {"omschrijving", "vraag", "uitdrukkingswijze"}:
        raise _fout(bestand, "bron moet omschrijving, vraag en uitdrukkingswijze verwijzen")
    if d["deterministic_detection_possible"] not in DETERMINISME:
        raise _fout(bestand, f"deterministic_detection_possible moet een van {DETERMINISME} zijn")
    for c in d["confusable_classes"]:
        if c["klasse"] not in JAS_KLASSEN_VOLGORDE or c["klasse"] == d["jas_class"]:
            raise _fout(bestand, f"ongeldige verwarbare klasse {c['klasse']!r}")
        if c.get("regel") and c["regel"] not in {r.id for r in REGELS}:
            raise _fout(bestand, f"verwijst naar onbekende JAS-regel {c['regel']!r}")
    for r in d["candidate_rules"]:
        if r.get("status") not in REGELSTATUS or not r.get("id", "").startswith("jas."):
            raise _fout(bestand, f"ongeldige kandidaatregel {r!r}")
    for t in d["test_cases"]:
        if t.get("verwacht") not in VERWACHT or t.get("status") not in TESTSTATUS:
            raise _fout(bestand, f"ongeldige testcasus {t!r}")


def _officieel(naam: str):
    return next(k for k in JAS_KLASSEN if k.naam == naam)


@cache
def laad() -> dict[str, Profiel]:
    """Alle profielen, gesleuteld op JAS-klasse, in de canonieke volgorde."""
    per_klasse: dict[str, Profiel] = {}
    for pad in sorted(MAP.glob("*.yaml")):
        d = yaml.safe_load(pad.read_text(encoding="utf-8"))
        _controleer(pad.name, d)
        if d["jas_class"] in per_klasse:
            raise _fout(pad.name, f"tweede profiel voor {d['jas_class']}")
        k = _officieel(d["jas_class"])
        per_klasse[d["jas_class"]] = Profiel(d["jas_class"], k.omschrijving, k.vraag,
                                             k.uitdrukkingswijze, d["bron"], d)
    return {k: per_klasse[k] for k in JAS_KLASSEN_VOLGORDE if k in per_klasse}


def referentietekst(casus_id: str) -> str:
    """De analysetekst van een ontwikkelcasus. Een held-out casus is hier uitdrukkelijk verboden."""
    for c in json.loads(referentieset_pad().read_text(encoding="utf-8")):
        if c["id"] == casus_id:
            if c["split"] != "ontwikkeling":
                raise ProfielFout(f"{casus_id} is held-out en mag niet in een profiel")
            return c["tekst"]
    raise ProfielFout(f"onbekende referentiecasus {casus_id}")


def casustekst(t: dict[str, Any]) -> str:
    bron = str(t.get("bron", ""))
    return referentietekst(bron.split(":", 1)[1]) if bron.startswith("referentieset:") else t["tekst"]
