"""De controle per stuk op de gerichte set (plan centrale agent na A6, PR B): per geval één aanroep van de lezer, met
het model van de straat. Alleen met akkoord van de gebruiker: het kost ongeveer twaalf aanroepen van 3–5k tokens.

    python -m eval.stukcontrole_set                 # het model uit de omgeving (AZURE_FOUNDRY_*)
    python -m eval.stukcontrole_set --json uit.json

Per geval: het oordeel van de lezer op de zin, en of de melding "tegenspreekt" volgde. De drempel uit het plan: geen
vals `spreekt_tegen` op een juiste samenvatting ('steunt'), en minstens drie van de vier omgedraaide beweringen
('tegen') gevonden. Een verwijzing en "zegt meer" zijn nooit een tegenspraak."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SET = Path(__file__).resolve().parent.parent / "tests" / "data" / "stukcontrole_set.json"


def gevallen() -> list[dict[str, Any]]:
    return json.loads(SET.read_text(encoding="utf-8"))["gevallen"]


def tekst_van(geval: dict[str, Any]) -> str:
    """Het antwoord zoals de lezer het krijgt: de zin onder een kop met het stuk (zoals `Extern.kern`)."""
    return f"**{geval['id']}**\n{geval['zin']}"


def beoordeel(llm: Any, settings: Any, geval: dict[str, Any]) -> dict[str, Any]:
    from agent.stukcontrole import controleer

    oordelen: dict[str, set[str]] = {}
    tegen = controleer(llm, settings, tekst_van(geval), {geval["id"]: geval["passage"]}, [], oordelen=oordelen)
    return {"id": geval["id"], "soort": geval["soort"], "oordelen": sorted(oordelen.get(geval["id"], set())),
            "tegenspreekt": bool(tegen)}


def samenvatting(uitslag: list[dict[str, Any]]) -> dict[str, Any]:
    tegen = [u for u in uitslag if u["soort"] == "tegen"]
    rest = [u for u in uitslag if u["soort"] != "tegen"]
    return {"gevonden": sum(u["tegenspreekt"] for u in tegen), "van": len(tegen),
            "vals": sum(u["tegenspreekt"] for u in rest),
            "steunt_herkend": sum(u["oordelen"] == ["steunt"] for u in uitslag if u["soort"] == "steunt"),
            "drempel": sum(u["tegenspreekt"] for u in tegen) >= 3 and not any(u["tegenspreekt"] for u in rest)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    from agent.adapters.anthropic_llm import AnthropicLLM
    from agent.config import Settings

    settings = Settings.from_env()
    llm = AnthropicLLM(settings)
    uitslag = [beoordeel(llm, settings, g) for g in gevallen()]
    rapport = {"gevallen": uitslag, "samenvatting": samenvatting(uitslag)}
    for u in uitslag:
        print(f"{u['soort']:<10} {u['id']:<24} {','.join(u['oordelen']) or '-':<30} "
              f"{'tegenspreekt' if u['tegenspreekt'] else ''}")
    print(json.dumps(rapport["samenvatting"], ensure_ascii=False))
    if args.json:
        args.json.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
