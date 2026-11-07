"""Een bewaarde run: per case of beurt de events die de scorers lezen, zodat opnieuw scoren gratis is.

Een live run kost geld en geeft elke keer een andere tekst. Zonder opname is een nieuwe of verbeterde scorer
alleen te toetsen met een nieuwe run, en is een verschil tussen twee rapporten niet te scheiden van de
spreiding van het model. `run_eval.py --bewaar uit.jsonl` schrijft per case (QA) of per beurt (`--gesprek`) één
regel; `--herscoor uit.jsonl` scoort dat bestand met de huidige scorers, zonder agent, model of graaf.

Een regel draagt de case (QA) of het gesprek en de beurt (gesprek) zoals ze in de set stonden: de opname is
zo op zichzelf leesbaar, en herscoren gebruikt de verwachtingen van toen.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def nieuwe_opname(vraag: str, vraagtype: str) -> dict[str, Any]:
    return {"vraag": vraag, "vraagtype": vraagtype, "tekst": "", "antwoord": None,
            "grounding": {"grounded": True, "cited": 0, "unsupported": []}, "sources": [],
            "status": [], "tools": [], "overzicht": None, "error": None, "verbruik": None, "weigeringen": []}


def neem_op(opname: dict[str, Any], ev: dict[str, Any]) -> None:
    """Voeg één event uit `answer_stream` toe aan de opname; wat geen scorer leest, valt weg."""
    soort = ev.get("type")
    if soort == "token":
        opname["tekst"] += ev.get("content", "")
    elif soort == "antwoord":
        opname["antwoord"] = ev.get("antwoord")
    elif soort == "grounding":
        opname["grounding"] = {k: v for k, v in ev.items() if k != "type"}
    elif soort == "sources":
        opname["sources"] = ev.get("sources") or []
    elif soort == "status":
        opname["status"].append(ev.get("message", ""))
    elif soort == "tool_execution" and ev.get("phase") == "start":
        opname["tools"].append(ev.get("tool", ""))
    elif soort == "overzicht":
        opname["overzicht"] = ev.get("overzicht")
    elif soort == "meting":
        opname["meting"] = {k: v for k, v in ev.items() if k != "type"}
    elif soort == "error":
        opname["error"] = ev.get("message")


def bewaar(pad: Path, regels: list[dict[str, Any]]) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in regels), encoding="utf-8")


def lees(pad: Path) -> list[dict[str, Any]]:
    return [json.loads(r) for r in pad.read_text(encoding="utf-8").splitlines() if r.strip()]
