"""Pytest-plugin: draai één deel (shard) van een suite, voor de parallelle jobs in `poort.yml`.

    PYTEST_SHARD=2/3 uv run pytest -p pytest_shard      (met `scripts/` op PYTHONPATH)

Zonder `PYTEST_SHARD` doet de plugin niets. De verdeling gaat per testbestand – nooit een bestand
in twee shards, want module-fixtures en volgorde binnen een bestand horen bij elkaar – en is
deterministisch: elke shard rekent op dezelfde verzameling dezelfde indeling uit. Verdeeld wordt
op het aantal tests per bestand (grootste eerst, naar de lichtste shard), zodat de shards ongeveer
even lang duren zonder een lijst met tijden die moet worden bijgehouden.

Dat er niets wegvalt volgt uit de constructie: elk verzameld bestand komt in precies één shard.
`tests/poort/test_pytest_shard.py` bewaakt dat.
"""

from __future__ import annotations

import os


def verdeel(aantallen: dict[str, int], totaal: int) -> list[list[str]]:
    """Verdeel bestanden (pad → aantal tests) over `totaal` shards; grootste eerst, naar de lichtste."""
    shards: list[list[str]] = [[] for _ in range(totaal)]
    gewicht = [0] * totaal
    for pad in sorted(aantallen, key=lambda p: (-aantallen[p], p)):
        doel = min(range(totaal), key=lambda i: (gewicht[i], i))
        shards[doel].append(pad)
        gewicht[doel] += aantallen[pad]
    return shards


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
    mijn = set(verdeel(aantallen, n)[i - 1])
    gekozen = [it for it in items if it.nodeid.split("::", 1)[0] in mijn]
    weg = [it for it in items if it.nodeid.split("::", 1)[0] not in mijn]
    if weg:
        config.hook.pytest_deselected(items=weg)
    items[:] = gekozen


def pytest_report_header(config):
    shard = _lees_shard()
    if shard is not None:
        return f"shard {shard[0]}/{shard[1]} (scripts/pytest_shard.py)"
    return None
