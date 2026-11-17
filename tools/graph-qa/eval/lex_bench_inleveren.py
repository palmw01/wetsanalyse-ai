"""Lex Bench: de opdracht en het formulier via de runmap, buiten de context van de coördinator (pilot LB3, bevinding 1).

In de pilot ging de opdracht (17.000 tot 30.000 tekens) letterlijk in de prompt van de agent, en kwam het formulier als
laatste bericht terug in de context van de coördinator. Die context was het duurst van de hele pilot. Nu legt de
coördinator de opdracht in de runmap `docs/acceptatie/lokaal/<run>/` (gitignored, dezelfde map als het logboek):

- `opdracht.md`: de opdracht, die de agent leest met de tool `bench_opdracht_lezen` van de acceptatie-MCP;
- `opdracht.json`: wat de controle nodig heeft (soort, casus, en de paden van dossier, team en opname).

De agent levert in met `bench_inleveren`. De MCP schrijft elke poging als `inlevering-<n>.json` en roept dit script aan
(`controleer`); het antwoord gaat terug naar de agent, die zijn fouten zelf herstelt. Een geldig formulier wordt
`ingeleverd.json`, en daarna is er niets meer in te leveren. De coördinator leest alleen of het klopt.

    python -m eval.lex_bench_team opdracht --casus LB-10 --analist A --run lb-10-2026-11-20-a --naar-run
    python -m eval.lex_bench_review opdracht --casus LB-10 --team <map>/teamverwachting.json --run ... --naar-run
    python -m eval.lex_bench_inleveren controleer --run lb-10-2026-11-20-a --bestand inlevering-1.json

Met `--naar-run` schrijven de scripts de opdracht in de runmap in plaats van naar stdout (`lex_bench_team.naar_run`);
een runmap die al een opdracht heeft, blijft staan. `controleer` is de aanroep van de MCP.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from eval import lex_bench_review as review
from eval import lex_bench_team as team


def _laad(pad: str | None) -> Path | None:
    return Path(pad) if pad else None


def fouten_in(formulier: Any, controle: dict[str, Any]) -> list[str]:
    """De fouten in een ingeleverd formulier, met dezelfde controle als `lex_bench_team controleer` of `verwerk`."""
    casus = controle["casus"]
    if controle["soort"] == "analist":
        return team.controleer(formulier, team.dossier_uit(casus, _laad(controle["dossier"])), casus)
    if controle["modus"] == "tegenlezen":
        f = json.loads(Path(controle["formulier"]).read_text(encoding="utf-8"))
        return review.controleer(formulier, "tegenlezen", casus, formulier=f)
    set_, opname = review._set_en_opname(casus, _laad(controle["dossier"]), _laad(controle["opname"]))
    kaart = review.lex_tegen_team(set_, json.loads(Path(controle["team"]).read_text(encoding="utf-8")), opname)
    return review.controleer(formulier, "verschillen", casus, kaart=kaart)


def controleer(run: str, bestand: str, map_: Path | None = None) -> dict[str, Any]:
    doel = team.runmap(run, map_)
    if not re.fullmatch(r"inlevering-[0-9]+\.json", bestand):
        raise ValueError("Het bestand heet inlevering-<n>.json.")
    controle = json.loads((doel / "opdracht.json").read_text(encoding="utf-8"))
    try:
        formulier = json.loads((doel / bestand).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"geldig": False, "fouten": [f"geen geldige JSON: {e}"]}
    fouten = fouten_in(formulier, controle)
    return {"geldig": not fouten, "fouten": fouten}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="actie", required=True)
    c = sub.add_parser("controleer", help="toets een inlevering; de uitkomst als JSON op stdout")
    c.add_argument("--run", required=True)
    c.add_argument("--bestand", required=True)
    args = p.parse_args(argv)
    print(json.dumps(controleer(args.run, args.bestand), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
