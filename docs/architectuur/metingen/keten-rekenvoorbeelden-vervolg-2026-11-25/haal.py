"""Haal de huidige toestand van regelingen bij overheid.nl en schrijf elke node met eigen tekst weg (alleen lezen).

Dezelfde lezer als de importer (`bronmodel.bwb`, via `agent.adapters.sru_bwb`). Draai vanuit tools/graph-qa:

    uv run python ../../docs/architectuur/metingen/keten-rekenvoorbeelden-vervolg-2026-11-25/haal.py teksten.json \\
        BWBR0004770 BWBR0024096 BWBR0002320 BWBR0005537
"""
import dataclasses
import json
import sys

from agent.adapters.sru_bwb import SruBwb


def nodes(x, bwb: str, uit: list) -> None:
    """Elke node van het model met een eigen tekst en een id, in documentvolgorde."""
    if dataclasses.is_dataclass(x):
        t = getattr(x, "tekst", None)
        if isinstance(t, str) and len(t) > 20 and getattr(x, "id", None):
            uit.append({"bwb": bwb, "id": x.id, "tekst": t})
        for f in dataclasses.fields(x):
            nodes(getattr(x, f.name), bwb, uit)
    elif isinstance(x, (list, tuple)):
        for y in x:
            nodes(y, bwb, uit)


def main() -> None:
    uit: list = []
    sru = SruBwb()
    for bwb in sys.argv[2:]:
        gelezen = sru.lees(sru.toestand_op(bwb))
        nodes(gelezen.wet, bwb, uit)
        print(bwb, gelezen.toestand.versie, file=sys.stderr)
    with open(sys.argv[1], "w") as f:
        json.dump(uit, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
