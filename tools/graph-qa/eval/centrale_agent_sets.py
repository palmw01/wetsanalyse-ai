"""Scoor de kwaliteitsset en de gesprekken die via acceptatie zijn gesteld (ADR-016 §A6, de ronde voor A2).

    uv run python -m eval.centrale_agent_sets <map>/ruw-kwaliteit-*-run1.jsonl <map>/ruw-duiding-*-run1.jsonl <map>/ruw-partijen-*-run1.jsonl <map>/ruw-klassen-*-run1.jsonl <map>/ruw-gesprek-*-run1.jsonl [--uit runs.jsonl]

De sets draaien anders in-process (`eval/run_eval.py`). `eval/centrale_agent_meting.mjs vragen …` stelt dezelfde vragen
via de werkplek op de straat, in twee vormen (supervisor en centrale agent). Dit script maakt uit de events van elke
beurt een opname (`eval/opname.py`) en geeft die aan de scorers van de sets zelf: `scoring.score_opname` voor de
kwaliteitsset en `gesprek.beurt_uit_opname` voor een gesprek. Er komt dus geen tweede maat bij.

Twee verschillen met een run in-process:
- de route komt uit het `meting`-event, niet uit de statusregels (de client van de acceptatie-MCP geeft die niet door).
  Een agent met een taak (`deelvragen:dekking`) telt ook als zijn agent (`deelvragen`);
- bij de centrale agent is de route `centraal`: een verwachting die een specialist bij naam noemt (`definitie`,
  `duiding`, `algemeen`) is daar niet te toetsen en telt niet als fout. Ze staat apart in `niet_getoetst`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.centrale_agent_vat import gewogen, per_ronde, per_soort
from eval.gesprek import beurt_uit_opname
from eval.opname import neem_op, nieuwe_opname
from eval.scoring import score_opname

EVAL = Path(__file__).resolve().parent
#: Routes die alleen bij de supervisor bestaan: de specialist die hij kiest.
SPECIALISTROUTES = {"definitie", "duiding", "algemeen"}


def _lees(pad: Path) -> list[dict[str, Any]]:
    return [json.loads(r) for r in pad.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]


def kwaliteitsset() -> dict[str, dict[str, Any]]:
    return {f"K{i + 1:02d}": c for i, c in enumerate(_lees(EVAL / "golden.jsonl"))}


def partijenset() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in _lees(EVAL / "golden_duiding_partijen.jsonl")}


def klassenset() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in _lees(EVAL / "golden_klasse_twijfel.jsonl")}


def duidingset() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in _lees(EVAL / "golden_duiding.jsonl")}


def gesprekken() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in _lees(EVAL / "golden_gesprek.jsonl")}


def opname_van(beurt: dict[str, Any], vraagtype: str = "") -> dict[str, Any]:
    """De opname die de scorers lezen, uit de events van één beurt."""
    opname = nieuwe_opname(beurt.get("vraag", ""), vraagtype)
    for ev in beurt.get("events") or []:
        neem_op(opname, ev)
    opname["tekst"] = beurt.get("tekst") or ""
    route = (opname.get("meting") or {}).get("route") or ""
    opname["routes"] = [r for r in dict.fromkeys([route, route.split(":")[0]]) if r]
    return opname


def kosten(beurten: list[dict[str, Any]]) -> dict[str, Any]:
    metingen = [e for b in beurten for e in b.get("events") or [] if e.get("type") == "meting"]
    soorten = per_soort(metingen)
    return {"modelrondes": sum(m.get("modelrondes", 0) for m in metingen),
            "duur_ms": sum(m.get("duur_ms", 0) for m in metingen),
            "tokens": sum(soorten.values()), "gewogen": gewogen(soorten), "gewogen_warm": gewogen(soorten, warm=True),
            "cache_schrijf_1u": soorten["cache_schrijf_1u"],
            "route": [(m.get("route") or "") for m in metingen], **toolgebruik(beurten, metingen)}


def toolgebruik(beurten: list[dict[str, Any]], metingen: list[dict[str, Any]]) -> dict[str, Any]:
    """Welke tools de beurt vroeg, per modelronde, en of de overdracht naar de brede toolset viel (A2-2b)."""
    events = [e for b in beurten for e in b.get("events") or []]
    # Een aanroep die de code weigerde (`status: geweigerd`), draaide niet; hij telt bij `tool_buiten_profiel`.
    tools = [e.get("tool", "") for e in events if e.get("type") == "tool_execution" and e.get("phase") == "start"
             and e.get("status") != "geweigerd"]
    profielen = sorted({a.get("profiel_id") for m in metingen for a in (m.get("contextopbouw") or {}).get("agenten") or []
                        if a.get("profiel_id")})
    return {"tools": tools, "tools_per_ronde": per_ronde(events), "profielen": profielen,
            "meer_tools": "meer_tools" in tools or "centraal_breed" in profielen,
            "tool_buiten_profiel": sum(1 for e in events if e.get("type") == "tool_execution" and e.get("phase") == "end"
                                       and e.get("foutcode") == "tool_buiten_profiel"),
            "sjabloon": {k: v for m in metingen for k, v in (m.get("sjabloon") or {}).items()}}


def scoor_kwaliteit(rec: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    beurt = rec["beurten"][0] if rec.get("beurten") else {}
    r = score_opname(case, opname_van(beurt, case.get("vraagtype", "")))
    return {"vraag": case["question"], "vraagtype": r.vraagtype, "geslaagd": r.passed and not rec.get("mislukt"),
            "faithfulness": r.faithfulness, "source_recall": r.source_recall, "contains_ok": r.contains_ok,
            "refusal_ok": r.refusal_ok, "zonder_verboden_ok": r.zonder_verboden_ok, "overzicht_ok": r.overzicht_ok,
            "volgorde_ok": r.volgorde_ok, "sjabloon_ok": r.sjabloon_ok, "fout": r.error,
            **kosten(rec.get("beurten") or [])}


def scoor_gesprek(rec: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    centraal = rec.get("vorm") == "centraal"
    beurten = []
    for spec, beurt in zip(case["beurten"], rec.get("beurten") or []):
        verwacht = dict(spec.get("verwacht") or {})
        niet_getoetst = []
        if centraal and verwacht.get("route") in SPECIALISTROUTES:
            niet_getoetst.append(f"route {verwacht.pop('route')}")
        b = beurt_uit_opname({**spec, "verwacht": verwacht}, opname_van(beurt, spec.get("vraagtype") or case.get("vraagtype", "")))
        beurten.append({"vraag": spec["vraag"], "routes": b.routes, "tools": b.tools, "niveau": b.niveau,
                        "fouten": b.fouten, "niet_getoetst": niet_getoetst, **kosten([beurt])})
    compleet = len(beurten) == len(case["beurten"])
    return {"scenario": case.get("scenario", ""), "geslaagd": compleet and not any(b["fouten"] for b in beurten),
            "beurten": beurten, **kosten(rec.get("beurten") or [])}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("ruw", nargs="+", type=Path)
    p.add_argument("--uit", type=Path)
    a = p.parse_args()
    sets = {"kwaliteit": (kwaliteitsset(), scoor_kwaliteit), "duiding": (duidingset(), scoor_kwaliteit),
            "partijen": (partijenset(), scoor_kwaliteit),
            "klassen": (klassenset(), scoor_kwaliteit),
            "gesprek": (gesprekken(), scoor_gesprek)}
    regels = []
    for pad in a.ruw:
        for rec in _lees(pad):
            cases, scoor = sets[rec["set"]]
            regels.append({"id": rec["id"], "set": rec["set"], "vorm": rec.get("vorm", ""), "run": rec["run"],
                           "commit": rec.get("commit", ""), "herhaald": rec.get("herhaald", 0),
                           "gesprek": next((b.get("gesprek", "") for b in rec.get("beurten") or []), ""),
                           **scoor(rec, cases[rec["id"]])})
    if a.uit:
        a.uit.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in regels), encoding="utf-8")
        print(f"{len(regels)} regels naar {a.uit}")
        return
    for r in regels:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
