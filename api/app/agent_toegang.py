"""Wat het agent-token mag: de routes die graph-qa aanroept, en verder niets.

De mens beslist (kaders): Lex stelt voor, de jurist besluit. Dat stond alleen in de code van de agent, terwijl de api
elk client-token alles liet doen. Nu weigert de api het agent-token buiten deze lijst, dus ook op elke
beslissingsroute (een annotatie beoordelen, een begrip accorderen, een kandidaat opnemen). Een besluit dat de jurist
in het gesprek neemt, loopt via een route die alleen de stand van een stap zet en zijn userid draagt.

De lijst is gelijk aan de aanroepen van graph-qa (`agent/wetsanalyse_api.py` en de leesclients); `tests/poort/test_agent_toegang.py`
bewaakt dat in beide richtingen. Een nieuwe aanroep van graph-qa hoort dus hier, en een beslissingsroute hoort er
nooit in (`BESLISSINGEN` in die test).
"""
from __future__ import annotations

import re

#: De client-id van graph-qa in `WETSANALYSE_API_TOKENS` (`deploy/azure/README.md`).
AGENT_CLIENT = "graph-qa"

TOEGESTAAN: frozenset[tuple[str, str]] = frozenset({
    ("GET", "/v1/annotatie/dekking"),
    ("GET", "/v1/connectors"),
    ("GET", "/v1/annotatie/elementen/{}"),
    ("GET", "/v1/annotatie/weergave"),
    ("GET", "/v1/begrippen"),
    ("GET", "/v1/begrippen/{}"),
    ("GET", "/v1/verbruik/controle"),
    ("GET", "/v1/werkgebieden/{}"),
    ("GET", "/v1/werkgebieden/{}/annotatie-werkvoorraad"),
    ("GET", "/v1/werkgebieden/{}/begrippen-runs/{}"),
    ("GET", "/v1/werkgebieden/{}/begrippen/{}"),
    ("GET", "/v1/werkgebieden/{}/begrippen/{}/kaart-runs/{}"),
    ("GET", "/v1/werkgebieden/{}/begrippen/{}/voorstellen"),
    ("GET", "/v1/werkgebieden/{}/bepalingen"),
    ("GET", "/v1/werkgebieden/{}/bronnen-runs/{}"),
    ("GET", "/v1/werkgebieden/{}/bronselectie"),
    ("GET", "/v1/werkgebieden/{}/deelvragen/dekking"),
    ("GET", "/v1/werkgebieden/{}/groepen"),
    ("GET", "/v1/werkgebieden/{}/kandidaten"),
    ("GET", "/v1/werkgebieden/{}/relaties"),
    ("GET", "/v1/werkgebieden/{}/thema-voorstel"),
    ("GET", "/v1/werkgebieden/{}/verdieping"),
    ("PATCH", "/v1/werkgebieden/{}"),
    ("POST", "/v1/annotatie/lagen/batch"),
    ("POST", "/v1/annotatie/zoeken"),
    ("POST", "/v1/begrippen/verifieer"),
    ("POST", "/v1/gesprekken/{}/berichten"),
    ("POST", "/v1/verbruik"),
    ("POST", "/v1/werkgebieden"),
    ("POST", "/v1/werkgebieden/{}/begrippen-runs"),
    ("POST", "/v1/werkgebieden/{}/begrippen-runs/{}/loopt"),
    ("POST", "/v1/werkgebieden/{}/begrippen-runs/{}/mislukt"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/kaart-runs"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/kaart-runs/{}/loopt"),
    ("POST", "/v1/werkgebieden/{}/begrippen/{}/kaart-runs/{}/mislukt"),
    ("POST", "/v1/werkgebieden/{}/bronnen-runs"),
    ("POST", "/v1/werkgebieden/{}/bronnen-runs/{}/loopt"),
    ("POST", "/v1/werkgebieden/{}/bronnen-runs/{}/mislukt"),
    ("POST", "/v1/werkgebieden/{}/bronselectie/{}/status"),
    ("POST", "/v1/werkgebieden/{}/bronselectie/{}/voorstellen"),
    ("POST", "/v1/werkgebieden/{}/deelvragen/voorstellen"),
    ("PUT", "/v1/werkgebieden/{}/begrippen-runs/{}/batches/{}"),
    ("PUT", "/v1/werkgebieden/{}/begrippen-runs/{}/uitkomst"),
    ("PUT", "/v1/werkgebieden/{}/begrippen-runs/{}/verdieping"),
    ("PUT", "/v1/werkgebieden/{}/begrippen/{}/kaart-runs/{}/uitkomst"),
    ("PUT", "/v1/werkgebieden/{}/bronnen-runs/{}/uitkomst"),
})


#: `main.py` hangt elke router onder dit voorvoegsel. Een route kent alleen zijn eigen pad, zonder dat voorvoegsel.
VOORVOEGSEL = "/v1"


def _vorm(pad: str) -> str:
    pad = pad if pad.startswith(VOORVOEGSEL + "/") else VOORVOEGSEL + pad
    return re.sub(r"\{[^{}]+\}", "{}", pad).rstrip("/") or "/"


def mag(client_id: str, methode: str, route_pad: str) -> bool:
    """Mag deze client deze route aanroepen? Alleen het agent-token is begrensd."""
    return client_id != AGENT_CLIENT or (methode.upper(), _vorm(route_pad)) in TOEGESTAAN
