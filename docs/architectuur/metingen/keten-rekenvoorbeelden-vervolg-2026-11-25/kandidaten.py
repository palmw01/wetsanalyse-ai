"""Per tekst de kandidaten na detectie, fusie en de voorbeeldstap, met het deterministische besluit (zonder model).

Draai het met de code van master (PYTHONPATH naar een checkout van master) en met die van de branch, en vergelijk met
`verschil.py`. Alleen teksten die het patroon (argument 3) raakt:

    uv run --extra nlp python …/kandidaten.py teksten.json na.json '<patroon>'
"""
import json
import re
import sys

import agent
from agent.jas_pipeline import voorbeeld
from agent.jas_pipeline.besluit import deterministisch
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.taal import maak_provider


def main() -> None:
    print(agent.__file__, file=sys.stderr)       # welke code er draait
    patroon = re.compile(sys.argv[3], re.I)
    provider = maak_provider("spacy")
    uit: dict = {}
    with open(sys.argv[1]) as f:
        teksten = json.load(f)
    for x in teksten:
        sleutel = x["bwb"] + x["id"]
        if not patroon.search(x["tekst"]) or sleutel in uit:
            continue
        bron = BronTekst.van_tekst(sleutel, x["tekst"], analyse=provider.analyseer(x["tekst"]))
        fusie, _ = voorbeeld.op_fusie(fuseer(detecteer_alles(bron)), [bron])
        rijen = []
        for k in fusie.kandidaten:
            b = deterministisch(k)
            rijen.append([k.span.start, k.span.eind, k.span.tekst, sorted(k.possible_classes), k.status.value,
                          sorted({e.code for e in k.evidence}), f"{b.status.value}:{b.klasse or ''}" if b else ""])
        uit[sleutel] = {"tekst": x["tekst"], "k": sorted(rijen)}
    with open(sys.argv[2], "w") as f:
        json.dump(uit, f, ensure_ascii=False)
    print(len(uit), file=sys.stderr)


if __name__ == "__main__":
    main()
