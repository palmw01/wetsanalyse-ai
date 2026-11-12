"""Pytest-plugin: draai één deel (shard) van een suite, voor de parallelle jobs in `poort.yml`.

    PYTEST_SHARD=2/3 uv run pytest -p pytest_shard      (met `scripts/` op PYTHONPATH)

Zonder `PYTEST_SHARD` doet de plugin niets. De verdeling gaat per testbestand – nooit een bestand
in twee shards, want module-fixtures en volgorde binnen een bestand horen bij elkaar – en is
deterministisch: elke shard rekent op dezelfde verzameling dezelfde indeling uit. Verdeeld wordt op
gewicht, grootste eerst naar de lichtste shard. Het gewicht is de gemeten duur uit
`pytest_shard_duur.json` (één bestand kan een shard domineren: in graph-qa duurt
`test_resultaatcontract.py` 88 van de 252 s); een bestand dat daar niet in staat weegt als de mediaan.
Zonder metingen voor de suite telt het aantal tests per bestand.

Dat er niets wegvalt volgt uit de constructie: elk verzameld bestand komt in precies één shard; de
tijden sturen alleen de balans. `tests/poort/test_poort_parallel.py` bewaakt dat. Elke shard print aan
het eind de duur per bestand (`pytest_shard duur per bestand: {...}`), de grondstof om de tijden bij te
werken.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def verdeel(gewichten: dict[str, float], totaal: int) -> list[list[str]]:
    """Verdeel bestanden (pad → gewicht) over `totaal` shards; grootste eerst, naar de lichtste."""
    shards: list[list[str]] = [[] for _ in range(totaal)]
    gewicht = [0.0] * totaal
    for pad in sorted(gewichten, key=lambda p: (-gewichten[p], p)):
        doel = min(range(totaal), key=lambda i: (gewicht[i], i))
        shards[doel].append(pad)
        gewicht[doel] += gewichten[pad]
    return shards


def gewichten(aantallen: dict[str, int], gemeten: dict[str, float] | None) -> dict[str, float]:
    """Het gewicht per bestand: de gemeten duur, anders de mediaan; zonder metingen het aantal tests."""
    if not gemeten:
        return {p: float(n) for p, n in aantallen.items()}
    bekend = sorted(gemeten.values())
    mediaan = bekend[len(bekend) // 2]
    return {p: float(gemeten.get(p, mediaan)) for p in aantallen}


def _gemeten(rootpath: Path) -> dict[str, float] | None:
    """De tijden van deze suite uit `pytest_shard_duur.json`, op het pad vanaf de projectroot."""
    bron = Path(__file__).with_name("pytest_shard_duur.json")
    try:
        suite = rootpath.resolve().relative_to(Path(__file__).resolve().parents[1]).as_posix()
        return json.loads(bron.read_text(encoding="utf-8")).get(suite)
    except (OSError, ValueError):
        return None


def _lees_shard() -> tuple[int, int] | None:
    waarde = os.environ.get("PYTEST_SHARD", "").strip()
    if not waarde:
        return None
    index, _, totaal = waarde.partition("/")
    i, n = int(index), int(totaal)
    if not 1 <= i <= n:
        raise ValueError(f"PYTEST_SHARD={waarde!r}: verwacht i/n met 1 <= i <= n")
    return i, n


def pytest_collection_modifyitems(config, items):
    shard = _lees_shard()
    if shard is None:
        return
    i, n = shard
    aantallen: dict[str, int] = {}
    for item in items:
        pad = item.nodeid.split("::", 1)[0]
        aantallen[pad] = aantallen.get(pad, 0) + 1
    mijn = set(verdeel(gewichten(aantallen, _gemeten(config.rootpath)), n)[i - 1])
    gekozen = [it for it in items if it.nodeid.split("::", 1)[0] in mijn]
    weg = [it for it in items if it.nodeid.split("::", 1)[0] not in mijn]
    if weg:
        config.hook.pytest_deselected(items=weg)
    items[:] = gekozen


_DUUR: dict[str, float] = {}


def pytest_runtest_logreport(report):
    if _lees_shard() is not None:
        pad = report.nodeid.split("::", 1)[0]
        _DUUR[pad] = _DUUR.get(pad, 0.0) + report.duration


def pytest_terminal_summary(terminalreporter):
    """De duur per bestand, als JSON-regel: de grondstof voor `pytest_shard_duur.json`."""
    if _lees_shard() is not None and _DUUR:
        terminalreporter.write_line("pytest_shard duur per bestand: "
                                    + json.dumps({k: round(v, 1) for k, v in sorted(_DUUR.items())}))


def pytest_report_header(config):
    shard = _lees_shard()
    if shard is not None:
        return f"shard {shard[0]}/{shard[1]} (scripts/pytest_shard.py)"
    return None
