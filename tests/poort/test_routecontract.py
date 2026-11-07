"""Elke aanroep tussen de lagen landt op een route die er is, met die methode.

De browsertests mocken `/api/**`, dus een ontbrekende BFF-export of een verkeerd upstream-pad kan daar niet
falen. Zo werkte een knop lange tijd niet zonder dat iets rood werd. Dit contract toetst statisch: browser →
BFF → api, en graph-qa en de admin-MCP → api.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from routeboek import (
    DOORGEEF, FRONTEND, Aanroep, Route, admin_mcp_aanroepen, agent_aanroepen, agent_routes, api_routes,
    bff_aanroepen, bff_routes, client_aanroepen, gewicht, past,
)

# Bekende breuken, elk met de stap die ze oplost. Een vermelding die niet meer nodig is, laat de test falen.
BEKEND: dict[tuple[str, str, str], str] = {
    # E6-S2 vraagt de actieve runs al op; graph-qa levert `GET /v1/runs?actief=true` in E6-S1. Haal dit weg
    # zodra die route op master staat.
    ("GEEN_API", "GET", "/v1/runs"): "E6-S1",
}


def _zoek(routes: list[Route], aanroep: Aanroep) -> tuple[list[Route], bool]:
    """De best passende routes op het pad, en of de methode daarbij hoort."""
    passend = [r for r in routes if past(r.pad, aanroep.pad)]
    if not passend:
        return [], False
    if aanroep.methode == "REQ":
        return passend, True
    met_methode = [r for r in passend if r.methode == aanroep.methode]
    return met_methode or passend, bool(met_methode)


def _breuken() -> set[tuple[str, str, str]]:
    uit = set()
    api = api_routes() + agent_routes()
    bff = bff_routes()
    for a in client_aanroepen():
        routes, methode_klopt = _zoek(bff, a)
        if not routes:
            uit.add(("GEEN_BFF", a.methode, a.pad))
            continue
        if not methode_klopt:
            uit.add(("METHODE", a.methode, a.pad))
        # Een catch-all geeft alles door: het pad moet upstream dan ook bestaan.
        beste = max(routes, key=lambda r: gewicht(r.pad))
        for bff_pad, upstream in DOORGEEF:
            if "{*}" in beste.pad and (a.pad == bff_pad or a.pad.startswith(bff_pad + "/")):
                doel = Aanroep(a.methode, upstream + a.pad[len(bff_pad):], a.plek)
                if not _zoek(api, doel)[1]:
                    uit.add(("GEEN_UPSTREAM", a.methode, a.pad))
    for a in bff_aanroepen() + agent_aanroepen() + admin_mcp_aanroepen():
        if not _zoek(api, a)[1]:
            uit.add(("GEEN_API", a.methode, a.pad))
    return uit


def test_elke_aanroep_landt_op_een_route():
    nieuw = _breuken() - set(BEKEND)
    assert not nieuw, f"aanroepen zonder route: {sorted(nieuw)}"


def test_bekende_breuken_bestaan_nog():
    opgelost = set(BEKEND) - _breuken()
    assert not opgelost, f"haal deze uit BEKEND, ze zijn opgelost: {sorted(opgelost)}"


@pytest.mark.parametrize("gevonden,minimaal", [
    (api_routes, 150), (agent_routes, 5), (bff_routes, 60), (bff_aanroepen, 40),
    (client_aanroepen, 120), (agent_aanroepen, 40), (admin_mcp_aanroepen, 10),
])
def test_de_parser_vindt_genoeg(gevonden, minimaal):
    """Verandert de codevorm, dan valt de parser stil en zou het contract zomaar groen zijn."""
    assert len(gevonden()) >= minimaal


def test_de_catch_alls_laten_de_client_door(tmp_path):
    """`isWerkgebiedRoute` en `isGeneriekRoute` zijn de allowlists; ze draaien uit de echte bron."""
    bron = (FRONTEND / "lib" / "werkgebied.ts").read_text(encoding="utf-8")

    def functie(naam: str) -> str:
        begin = bron.index(f"export function {naam}")
        return bron[begin:bron.index("\n}\n", begin) + 3]

    (tmp_path / "allow.ts").write_text(functie("isWerkgebiedRoute") + functie("isGeneriekRoute"), encoding="utf-8")
    paden = sorted({a.pad for a in client_aanroepen()})
    werkgebied = [p.removeprefix("/api/werkgebieden/").replace("{}", "x").split("/")
                  for p in paden if p.startswith("/api/werkgebieden/")]
    generiek = [p.removeprefix("/api/begrippen/").replace("{}", "x").split("/")
                for p in paden if p.startswith("/api/begrippen/")]
    assert werkgebied and generiek
    # `groepen/{id}/{actie}`: de actie is een variabele in de client, de allowlist kent de waarden.
    werkgebied = [[*p[:3], "afwijzen"] if p[1:2] == ["groepen"] and len(p) == 4 else p for p in werkgebied]
    (tmp_path / "paden.json").write_text(json.dumps({"werkgebied": werkgebied, "generiek": generiek}), encoding="utf-8")
    script = """
      import { readFileSync } from "node:fs";
      const { isWerkgebiedRoute, isGeneriekRoute } = await import(process.argv[1] + "/allow.ts");
      const p = JSON.parse(readFileSync(process.argv[1] + "/paden.json", "utf8"));
      console.log(JSON.stringify([...p.werkgebied.filter((x) => !isWerkgebiedRoute(x)),
                                  ...p.generiek.filter((x) => !isGeneriekRoute(x))]));
    """
    uit = subprocess.run(["node", "--input-type=module", "-e", script, str(tmp_path)],
                         capture_output=True, text=True, check=True)
    assert json.loads(uit.stdout) == []


def test_het_contract_vangt_een_verwijderde_export():
    aanroep = Aanroep("PUT", "/api/werkgebieden/{}/deelvragen/{}/koppelingen", "x")
    catch_all = [r for r in bff_routes() if r.pad == "/api/werkgebieden/{*}"]
    assert catch_all and not _zoek(catch_all, aanroep)[1]
