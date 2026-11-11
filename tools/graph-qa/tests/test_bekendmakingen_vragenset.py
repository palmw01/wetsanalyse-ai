"""De vragenset van Staatsblad en Staatscourant (`tests/data/bekendmakingen_vragenset.json`) tegen opgenomen antwoorden.

Per vraag toetst dit:

- **de route**: een lijstvraag leest de code zelf (`bron_lijst.lees`) en een genoemd stuk ook (`genoemde_stukken`),
  met precies de argumenten uit de set; een vraag voor het model niet;
- **de tool**: dezelfde argumenten gaan door `dispatch`, tegen de antwoorden van KOOP zoals ze op 10 nov 2026 waren
  (`tests/fixtures/koop/vragenset/`, een opname per verzoek), en het resultaat voldoet aan `verwacht`.

Een verzoek dat niet is opgenomen, faalt: dan bouwt de tool een andere zoekvraag dan toen, en dat hoort zichtbaar te
zijn. Opnieuw opnemen (gratis, alleen KOOP, geen model):

    BEKENDMAKINGEN_OPNEMEN=1 uv run --extra dev pytest tests/test_bekendmakingen_vragenset.py

De graaf komt uit twee vaste antwoorden (`GRAAF`), zoals de acceptatiegraaf ze op 10 nov 2026 gaf.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import httpx
import pytest

from agent import tools
from agent.adapters.sru_bekendmakingen import SruBekendmakingen
from agent.bron_lijst import lees as lijstvraag
from agent.config import Settings
from agent.tools.bekendmaking_tools import REGELGEVENDE_SOORTEN
from bronmodel.connectors import genoemde_stukken

from fakes import FakeGraph

HIER = Path(__file__).parent
SET = json.loads((HIER / "data" / "bekendmakingen_vragenset.json").read_text(encoding="utf-8"))["vragen"]
OPNAME = HIER / "fixtures" / "koop" / "vragenset"
OPNEMEN = os.environ.get("BEKENDMAKINGEN_OPNEMEN") == "1"
AAN = Settings(connector_bekendmakingen=True)
IW = "BWBR0004770"


def _tsv(kop: list[str], rijen: list[list[str]]) -> str:
    def cel(v: str) -> str:
        return v if v.startswith('"') else json.dumps(v, ensure_ascii=False)
    return json.dumps("\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n" for r in rijen))


_DATUM = '"2010-07-04"^^<http://www.w3.org/2001/XMLSchema#date>'
_DATUM_2026 = '"2026-01-01"^^<http://www.w3.org/2001/XMLSchema#date>'
#: Wat de acceptatiegraaf op 10 nov 2026 antwoordde: de koppelingen van Iw art. 36 en de regelingen bij drie publicaties.
GRAAF = {
    "art36": _tsv(["waarde", "rol", "inwerking", "aantal"],
                  [["Stb.2009-610", "wijziging", _DATUM, "1"], ["Stb.2010-176", "inwerkingtreding", _DATUM, "1"]]),
    "regelingen": _tsv(["waarde", "rol", "bwb", "titel", "aantal"], [
        ["Stb.2009-610", "inwerkingtreding", "BWBR0002320", '"Algemene wet inzake rijksbelastingen"@nl', "1"],
        ["Stb.2009-610", "wijziging", "BWBR0002320", '"Algemene wet inzake rijksbelastingen"@nl', "1"],
        ["Stb.2009-610", "wijziging", IW, '"Invorderingswet 1990"@nl', "1"],
        ["Stb.2010-176", "inwerkingtreding", IW, '"Invorderingswet 1990"@nl', "1"]]),
    # AWR art. 67f, zoals de acceptatiegraaf op 11 nov 2026 antwoordde.
    "awr67f": _tsv(["waarde", "rol", "inwerking", "aantal"],
                   [["Stb.2025-431", "wijziging", _DATUM_2026, "1"], ["Stb.2025-431", "inwerkingtreding", _DATUM_2026, "1"]]),
}


def _graaf(soort: str | None) -> FakeGraph:
    def antwoord(q: str) -> str:
        if "VALUES ?waarde" in q:
            return GRAAF["regelingen"] if soort == "regelingen" else ""
        return GRAAF[soort] if soort in ("art36", "awr67f") else ""
    return FakeGraph(results=antwoord)


def _sleutel(r: httpx.Request) -> str:
    """Eén verzoek als sleutel: het pad en de parameters, gesorteerd."""
    u = urlparse(str(r.url))
    return f"{u.path}?{'&'.join(f'{k}={v}' for k, v in sorted(parse_qsl(u.query)))}"


class Opname:
    """Speelt de opgenomen antwoorden af, of neemt ze op tegen de echte dienst (`BEKENDMAKINGEN_OPNEMEN=1`)."""

    def __init__(self) -> None:
        self.index_pad = OPNAME / "index.json"
        self.index: dict[str, str] = json.loads(self.index_pad.read_text()) if self.index_pad.exists() else {}
        self.echt = httpx.Client(timeout=60) if OPNEMEN else None

    def __call__(self, r: httpx.Request) -> httpx.Response:
        sleutel = _sleutel(r)
        if self.echt is not None:
            antwoord = self.echt.get(str(r.url))
            naam = hashlib.sha1(sleutel.encode()).hexdigest()[:16] + ".xml"
            OPNAME.mkdir(parents=True, exist_ok=True)
            (OPNAME / naam).write_bytes(antwoord.content)
            self.index[sleutel] = naam
            self.index_pad.write_text(json.dumps(self.index, indent=1, sort_keys=True, ensure_ascii=False))
            return httpx.Response(antwoord.status_code, content=antwoord.content)
        if sleutel not in self.index:
            pytest.fail(f"niet opgenomen: {sleutel}\nde tool vraagt iets anders dan bij de opname; neem op met "
                        "BEKENDMAKINGEN_OPNEMEN=1")
        return httpx.Response(200, content=(OPNAME / self.index[sleutel]).read_bytes())


def _bron() -> SruBekendmakingen:
    return SruBekendmakingen(client=httpx.Client(transport=httpx.MockTransport(Opname())))


@pytest.mark.parametrize("v", SET, ids=[v["id"] for v in SET])
def test_de_route_leest_wat_de_set_zegt(v: dict):
    if v["route"] == "lijstvraag":
        uit = lijstvraag(v["vraag"], frozenset({"bekendmakingen"}), lambda t: [])
        assert uit is not None and uit.connector == "bekendmakingen" and uit.tool == v["tool"], v["vraag"]
        assert uit.args == v["args"], f"{v['id']}: de code las {uit.args}"
    elif v["route"] == "genoemd stuk":
        assert [i for _, i in genoemde_stukken(v["vraag"])] == [v["args"]["id"]], v["vraag"]


@pytest.mark.parametrize("v", SET, ids=[v["id"] for v in SET])
def test_de_tool_levert_wat_de_set_verwacht(v: dict):
    d = json.loads(tools.dispatch(v["tool"], _graaf(v.get("graaf")), v["args"], AAN, bekendmakingen=_bron()))
    e = v["verwacht"]
    if "reden" in e:
        assert d["status"] == "error" and d["reden"] == e["reden"], d
        return
    assert d["status"] == "ok", d
    rijen = d["resultaten"]
    if "aantal" in e:
        assert d["aantal"] == e["aantal"], [r.get("id") for r in rijen]
    if e.get("nieuwste_eerst"):
        datums = [r["datum"] for r in rijen if r.get("datum")]
        assert datums == sorted(datums, reverse=True), datums
    if "eerste" in e:
        assert rijen[0]["id"] == e["eerste"], [r["id"] for r in rijen]
    if "ids" in e:
        assert [r["id"] for r in rijen] == e["ids"]
    if "inwerking" in e:
        assert {r["inwerking"] for r in rijen} == {e["inwerking"]}
    for ident, rol in e.get("wetsverwijzing", {}).items():
        assert next(r for r in rijen if r["id"] == ident)["wetsverwijzing"].startswith(rol)
    for sleutel, waarde in e.get("alle", {}).items():
        assert rijen and all(waarde.lower() in str(r.get(sleutel, "")).lower() for r in rijen), (
            sleutel, [r.get(sleutel) for r in rijen])
    if e.get("stcrt_regelgevend"):
        assert all(r["soort"] in REGELGEVENDE_SOORTEN or r.get("publicatie") == "Staatsblad" for r in rijen), (
            [(r.get("publicatie"), r.get("soort")) for r in rijen])
    if "datum_vanaf" in e:
        assert all(r["datum"] >= e["datum_vanaf"] for r in rijen)
    if "datum_tot" in e:
        assert all(r["datum"] <= e["datum_tot"] for r in rijen)
    if "totaal_min" in e:
        assert d["totaal"] >= e["totaal_min"], d["totaal"]
    for sleutel, waarde in e.get("stuk", {}).items():
        assert d["stuk"].get(sleutel) == waarde or (isinstance(waarde, str) and waarde.lower() in str(
            d["stuk"].get(sleutel, "")).lower()), (sleutel, d["stuk"].get(sleutel))
    if "tekst_bevat" in e:
        assert any(e["tekst_bevat"] in r["tekst"] for r in rijen)
    if "wetsverwijzing_bevat" in e:
        assert e["wetsverwijzing_bevat"] in d["stuk"].get("wetsverwijzing", ""), d["stuk"]
    if "onderdelen" in e:
        assert {r["kop"].split(" › ")[1] for r in rijen if " › " in r.get("kop", "")} == set(e["onderdelen"])


def test_de_set_dekt_het_geheel():
    """Elke soort vraag uit de opdracht staat erin, en elke vraag noemt een tool, argumenten en een goed antwoord."""
    soorten = {v["soort"] for v in SET}
    for nodig in ("recentheid", "per regeling", "inwerkingtreding", "beleid in de Staatscourant", "één publicatie lezen",
                  "alleen een PDF", "koppeling met Kamerstukken", "telling en filter", "rectificatie", "tweede versie",
                  "niet bestaand nummer", "zonder treffers"):
        assert nodig in soorten, nodig
    for v in SET:
        assert v["tool"] in tools.CONNECTOR_TOOLS and v["args"] and v["goed"] and v["verwacht"], v["id"]
