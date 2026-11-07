"""Het agent-token mag precies de routes die graph-qa aanroept, en geen enkele beslissingsroute.

De lijst staat in `api/app/agent_toegang.py`. Deze test houdt hem gelijk aan de aanroepen van graph-qa, in beide
richtingen: een nieuwe aanroep die er niet in staat, geeft anders pas op acceptatie een 403, en een route die graph-qa
niet meer aanroept, hoort er niet meer in.
"""
from __future__ import annotations

import ast

from routeboek import WORTEL, agent_aanroepen, api_routes, normaal, past

#: Waar de jurist beslist. Het agent-token komt hier nooit, ook niet als graph-qa er later een aanroep bij krijgt.
BESLISSINGEN = {
    ("POST", "/v1/annotatie/elementen/{}/beslissing"),
    ("POST", "/v1/annotatie/lagen/{}/beslissingen"),
    ("POST", "/v1/annotatie/lagen/{}/status"),
    ("POST", "/v1/begrippen/{}/accorderen"),
    ("POST", "/v1/begrippen/{}/heropenen"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/accorderen"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/heropenen"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/generiek-maken"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/combineren-generiek"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/koppelingen/beoordelen"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/koppelingen/bevestigen"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/koppelingen/{}/bevestigen"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/voorstellen/{}/overnemen"),
    ("POST", "/v1/werkgebieden/{}/bronselectie/{}/kandidaten/{}"),
    ("POST", "/v1/werkgebieden/{}/groepen/akkoord"),
    ("POST", "/v1/werkgebieden/{}/relaties/{}/bevestigen"),
}


def _toegestaan() -> set[tuple[str, str]]:
    boom = ast.parse((WORTEL / "api" / "app" / "agent_toegang.py").read_text(encoding="utf-8"))
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.AnnAssign) and getattr(knoop.target, "id", "") == "TOEGESTAAN":
            return {tuple(e.value for e in t.elts) for t in knoop.value.args[0].elts}
    raise AssertionError("TOEGESTAAN niet gevonden")


def _api_route(methode: str, pad: str) -> str:
    """Het routesjabloon van de api waar deze aanroep landt; dat vergelijkt de api bij het verzoek."""
    kandidaten = [normaal(r.pad) for r in api_routes() if r.methode == methode and past(r.pad, pad)]
    assert kandidaten, f"{methode} {pad}: geen api-route"
    return pad if pad in kandidaten else min(kandidaten, key=lambda k: k.count("{"))


def test_de_lijst_is_wat_graph_qa_aanroept():
    verwacht = {(a.methode, _api_route(a.methode, a.pad)) for a in agent_aanroepen()}
    toegestaan = _toegestaan()
    assert toegestaan - verwacht == set(), "in de lijst, maar graph-qa roept het niet aan"
    assert verwacht - toegestaan == set(), "graph-qa roept dit aan: zet het in api/app/agent_toegang.py"


def test_geen_beslissingsroute_voor_de_agent():
    assert _toegestaan() & BESLISSINGEN == set()


def test_de_beslissingsroutes_bestaan():
    """Een hernoemde route valt anders stil uit deze bewaking."""
    api = {(r.methode, normaal(r.pad)) for r in api_routes()}
    assert BESLISSINGEN - api == set()
