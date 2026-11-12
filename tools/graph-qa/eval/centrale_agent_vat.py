"""Vat de ruwe runs van de agentset samen (ADR-016 §A6): per opdracht en run één regel met de meetpunten.

    python3 eval/centrale_agent_vat.py <map>/ruw-run1.jsonl [meer ...] [--oordelen oordelen.json] [--uit runs.jsonl]

De ruwe bestanden komen van `eval/centrale_agent_meting.mjs` en bevatten de hele antwoordtekst en alle events; die
horen niet in de repo. Dit script houdt over wat een meting vastlegt: de route, de delegatie, de tools, het sjabloon,
de controle, de tokens en de duur uit het `meting`-event, en wat daarvan tegen de set te toetsen is. Het oordeel over
de inhoud (goed, deels, fout, en of het brongetrouw is) geeft de beoordelaar na lezing tegen de officiële bron; het
staat in `--oordelen` als `{"<id>:<run>": {"oordeel": ..., "brongetrouw": ..., "faalwijze": ..., "opmerking": ...}}`.

Zonder `--uit` print het een regel per opdracht, en met `--tekst N` de eerste N tekens van elk antwoord erbij: zo
leest de beoordelaar de antwoorden.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SET = Path(__file__).resolve().parent / "golden_centrale_agent.jsonl"
#: Een route in code vraagt het model hoogstens één keer: de toelichting van de bepalingsroute.
MAX_RONDES_CODE = 1
#: Naar prijs gewogen (besluit gebruiker 12 nov 2026: de drempel "niet duurder" geldt op deze maat; ADR-016 §A6): een
#: token in invoertokens, naar de prijsverhouding van het model. Schrijven naar de cache kost meer naarmate de TTL
#: langer is; lezen een tiende.
GEWICHT = {"invoer": 1.0, "uitvoer": 5.0, "cache_lees": 0.1, "cache_schrijf_5m": 1.25, "cache_schrijf_1u": 2.0}


def lees_set() -> dict[str, dict[str, Any]]:
    rijen = (json.loads(r) for r in SET.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#"))
    return {r["id"]: r for r in rijen if r["id"] != "_werkgebied"}


def _tokens(meting: dict[str, Any]) -> int:
    return sum(meting.get(k, 0) for k in ("invoer", "uitvoer", "cache_lees", "cache_schrijf"))


def per_soort(metingen: list[dict[str, Any]]) -> dict[str, int]:
    """De tokens per soort uit de modelaanroepen van een of meer `meting`-events. Het schrijven met een TTL van een uur
    staat alleen per aanroep (`cache_schrijf_1u`); zonder aanroepen telt al het schrijven als vijf minuten."""
    aanroepen = [a for m in metingen for a in m.get("aanroepen") or []]
    bron = aanroepen or metingen
    uur = sum(a.get("cache_schrijf_1u", 0) for a in aanroepen)
    return {"invoer": sum(x.get("invoer", 0) for x in bron), "uitvoer": sum(x.get("uitvoer", 0) for x in bron),
            "cache_lees": sum(x.get("cache_lees", 0) for x in bron),
            "cache_schrijf_5m": sum(x.get("cache_schrijf", 0) for x in bron) - uur, "cache_schrijf_1u": uur}


def gewogen(soorten: dict[str, int]) -> int:
    return round(sum(GEWICHT[k] * soorten.get(k, 0) for k in GEWICHT))


def _een_van(ingangen: list[str], gezien: set[str]) -> list[str]:
    """De ingangen (`a|b` = één van beide) waarvan niets is gezien."""
    return [i for i in ingangen if not set(i.split("|")) & gezien]


def vat(rec: dict[str, Any], opdracht: dict[str, Any]) -> dict[str, Any]:
    v = opdracht["verwacht"]
    gemeten = [b for b in rec["beurten"] if b["label"].startswith("gemeten")]
    opzet = [b for b in rec["beurten"] if not b["label"].startswith("gemeten")]
    events = [e for b in gemeten for e in b.get("events", [])]
    metingen = [e for e in events if e["type"] == "meting"]
    tools = [e["tool"] for e in events if e["type"] == "tool_execution" and e.get("phase") == "start"]
    sjabloon: dict[str, Any] = {}
    for m in metingen:
        sjabloon.update(m.get("sjabloon") or {})
    kinderen = [e for e in events if e["type"] == "regie_taak" and e.get("fase") == "start"]
    bevestigingen = [e["bevestiging"] for e in events if e.get("bevestiging")]
    controles = [e for e in events if e["type"] == "grounding"]
    regie = any(e["type"] == "regie" for e in events) or any(b.get("soort") == "regie" for b in bevestigingen)
    rondes = sum(m.get("modelrondes", 0) for m in metingen)
    annoteerde = any(e["type"] in {"element", "run"} for e in events)

    gezien = set(tools) | set(sjabloon.get("gevuld") or {}) | ({"annoteer"} if annoteerde else set())
    laag, hoog = v["subagents"]
    gevuld = set(sjabloon.get("gevuld") or {})
    soorten = per_soort(metingen)
    opzet_soorten = per_soort([e for b in opzet for e in b.get("events", []) if e["type"] == "meting"])
    return {
        "id": rec["id"], "run": rec["run"], "groep": opdracht["groep"], "commit": rec.get("commit", ""),
        "vorm": rec.get("vorm", ""),
        "gesprek": gemeten[0].get("gesprek", "") if gemeten else "",
        "runs": [b.get("run_id", "") for b in gemeten],
        "route": "regie" if regie else "+".join(m.get("route", "") for m in metingen) or "geen",
        "modelrondes": rondes,
        "tokens": sum(_tokens(m) for m in metingen),
        "invoer": sum(m.get("invoer", 0) for m in metingen), "uitvoer": sum(m.get("uitvoer", 0) for m in metingen),
        "cache_lees": sum(m.get("cache_lees", 0) for m in metingen),
        "cache_schrijf": sum(m.get("cache_schrijf", 0) for m in metingen),
        "cache_schrijf_1u": soorten["cache_schrijf_1u"],
        "gewogen": gewogen(soorten), "opzet_gewogen": gewogen(opzet_soorten),
        "duur_ms": sum(m.get("duur_ms", 0) for m in metingen) or sum(b.get("wand_ms", 0) for b in gemeten),
        "opzet_tokens": sum(_tokens(e) for b in opzet for e in b.get("events", []) if e["type"] == "meting"),
        "delta_account": sum(b.get("delta_account") or 0 for b in rec["beurten"]),
        "tools": tools, "sjabloon": sjabloon,
        "kindgesprekken": len(kinderen),
        "bevestiging": [f"{b.get('soort')}:{b.get('opdracht', '')}".rstrip(":") for b in bevestigingen],
        "vraagkaart": [e["vraagkaart"].get("stap") for e in events if e["type"] == "vraagkaart"],
        "niveau": [c.get("niveau", "") for c in controles],
        "niet_letterlijk": sum(len(c.get("niet_letterlijk") or []) for c in controles),
        "unsupported": sum(len(c.get("unsupported") or []) for c in controles),
        "onbevestigd": sum(len(c.get("onbevestigd") or []) for c in controles),
        "fouten": [str(e.get("message") or e.get("melding") or e.get("foutcode") or "")[:200]
                   for e in events if e["type"] == "error"] + ([rec["mislukt"]] if rec.get("mislukt") else []),
        "herhaald": rec.get("herhaald", 0),
        # Tegen de set. De set beschrijft het doel van ADR-016; `route_past` is tot de centrale agent er is een
        # benadering: een route in code vraagt het model hoogstens één keer, de centrale agent minstens één keer.
        "route_past": (rondes <= MAX_RONDES_CODE and not regie or (regie and v["regisseur"])) if v["route"] == "code"
                      else (rondes >= 1 or (regie and v["regisseur"])),
        "delegatie_past": laag <= len(kinderen) <= hoog,
        "tools_ontbreken": _een_van(v["tools_verplicht"], gezien),
        "tools_verboden_gezien": sorted(set(v["tools_verboden"]) & gezien),
        "sjabloon_past": (not gevuld) if v["sjabloon"] is None else bool(set(v["sjabloon"].split("|")) & gevuld),
        "bevestiging_past": bool(bevestigingen) == v["bevestiging"],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("ruw", nargs="+", type=Path)
    p.add_argument("--oordelen", type=Path)
    p.add_argument("--uit", type=Path)
    p.add_argument("--tekst", type=int, default=0)
    p.add_argument("--id", action="append", default=[])
    a = p.parse_args()
    opdrachten = lees_set()
    oordelen = json.loads(a.oordelen.read_text(encoding="utf-8")) if a.oordelen else {}
    regels = []
    for pad in a.ruw:
        for rec in (json.loads(r) for r in pad.read_text(encoding="utf-8").splitlines() if r.strip()):
            if a.id and rec["id"] not in a.id:
                continue
            s = vat(rec, opdrachten[rec["id"]])
            s.update(oordelen.get(f"{s['id']}:{s['run']}", {}))
            regels.append(s)
            if a.uit:
                continue
            print(json.dumps({k: w for k, w in s.items() if k not in {"gesprek", "runs", "commit"}}, ensure_ascii=False))
            for b in rec["beurten"] if a.tekst else []:
                print(f"   [{b['label']}] {b.get('vraag', '')[:100]}")
                print("     " + (b.get("tekst") or "").replace("\n", "\n     ")[:a.tekst])
    if a.uit:
        a.uit.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in regels), encoding="utf-8")
        print(f"{len(regels)} regels naar {a.uit}")


if __name__ == "__main__":
    main()
