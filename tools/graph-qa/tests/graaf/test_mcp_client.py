"""semantic_search: MCPClient bouwt de juiste similarity_search-argumenten."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.mcp_client import MCPClient, MCPError


def test_semantic_search_gebruikt_similarity_search():
    c = MCPClient(url="http://x/mcp", token="t", repository_id="inning", similarity_index="bwb_similarity")
    captured: dict = {}

    def _fake_call_tool(name, arguments):
        captured["name"] = name
        captured["arguments"] = arguments
        return [{"type": "text", "text": "resultaat"}]

    c.call_tool = _fake_call_tool  # type: ignore[assignment]
    out = c.semantic_search("belasting niet op tijd betaald", limit=5)

    assert out == "resultaat"
    assert captured["name"] == "similarity_search"
    args = captured["arguments"]
    assert args["similarityIndex"] == "bwb_similarity"
    assert args["connectorType"] == "similarity"
    assert args["repositoryId"] == "inning"
    assert args["query"] == "belasting niet op tijd betaald"


def test_rpc_non_2xx_zonder_result_raist(monkeypatch):
    # F5: een 5xx met een JSON-body zonder `result`/`error` mag niet stil een leeg resultaat geven.
    c = MCPClient(url="http://x/mcp", token="t", repository_id="inning")
    resp = SimpleNamespace(
        status_code=500,
        headers={"content-type": "application/json"},
        json=lambda: {"jsonrpc": "2.0", "id": 1},  # geen result, geen error
        text="internal error",
    )
    monkeypatch.setattr(c._client, "post", lambda *a, **k: resp)
    with pytest.raises(MCPError) as exc:
        c._rpc("tools/call", {"name": "x", "arguments": {}})
    assert "500" in str(exc.value)


def test_rpc_2xx_result_ok(monkeypatch):
    # Regressie: een gewone 200 met result blijft werken (statuscheck raakt het happy-path niet).
    c = MCPClient(url="http://x/mcp", token="t", repository_id="inning")
    resp = SimpleNamespace(
        status_code=200,
        headers={"content-type": "application/json"},
        json=lambda: {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}},
        text="",
    )
    monkeypatch.setattr(c._client, "post", lambda *a, **k: resp)
    assert c.call_tool("x", {}) == [{"type": "text", "text": "ok"}]


# ---------------------------------------------------- de handshake hoort bij de verbinding
class _NepServer:
    """Bootst de GraphDB MCP-server na: zonder geldige sessie geen tools/call.

    Zo doet de echte server het (GraphDB MCP Server 2.0.0): een `tools/call` zonder sessie geeft
    HTTP 400, en een sessie die hij niet kent HTTP 404 — in beide gevallen met een XML-body, dus
    de client struikelt al op het ontbreken van JSON.
    """

    def __init__(self, sessie: str = "s-1") -> None:
        self.sessie = sessie
        self.geldig: set[str] = set()
        self.aanroepen: list[str] = []

    def post(self, url, json=None, headers=None, **_kw):
        methode = json["method"]
        self.aanroepen.append(methode)
        meegestuurd = (headers or {}).get("Mcp-Session-Id")

        if methode == "initialize":
            self.geldig.add(self.sessie)
            return SimpleNamespace(
                status_code=200, headers={"content-type": "application/json",
                                          "Mcp-Session-Id": self.sessie},
                json=lambda: {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "nep"}}},
                text="",
            )
        if meegestuurd is None:
            return SimpleNamespace(status_code=400, headers={"content-type": "application/xml"},
                                   json=lambda: (_ for _ in ()).throw(ValueError("geen json")),
                                   text="<McpError><cause/><stackTrace>…")
        if meegestuurd not in self.geldig:
            return SimpleNamespace(status_code=404, headers={"content-type": "application/xml"},
                                   json=lambda: (_ for _ in ()).throw(ValueError("geen json")),
                                   text="<McpError><cause/><stackTrace>…")
        return SimpleNamespace(
            status_code=200, headers={"content-type": "application/json"},
            json=lambda: {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"text": "ok"}]}},
            text="",
        )


def _client_met(server: _NepServer) -> MCPClient:
    c = MCPClient(url="http://x/mcp", token="t", repository_id="inning")
    c._client = SimpleNamespace(post=server.post, close=lambda: None)  # type: ignore[assignment]
    return c


def test_tools_call_doet_zelf_de_handshake():
    """De smoke riep `initialize()` niet aan en kreeg daardoor op élke query HTTP 400.

    Twee van de drie `make_graph`-aanroepers deden de handshake, de derde niet — en dat kostte vier
    eval-runs. Een voorwaarde die elke aanroeper moet onthouden, hoort in de verbinding zelf.
    """
    server = _NepServer()
    uit = _client_met(server).sparql("SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")

    assert uit == "ok"
    assert server.aanroepen == ["initialize", "tools/call"]


def test_handshake_gebeurt_maar_een_keer():
    """De sessie wordt hergebruikt; anders kost elke tool-aanroep een extra rondgang."""
    server = _NepServer()
    c = _client_met(server)
    c.sparql("SELECT ?s WHERE { ?s ?p ?o }")
    c.sparql("SELECT ?s WHERE { ?s ?p ?o }")

    assert server.aanroepen.count("initialize") == 1


def test_verlopen_sessie_wordt_een_keer_hersteld():
    """GraphDB is niet-persistent en komt na een herstart zonder sessies op.

    De client stuurde het oude sessie-id dan eeuwig mee en herstelde nooit.
    """
    server = _NepServer()
    c = _client_met(server)
    c.sparql("SELECT ?s WHERE { ?s ?p ?o }")
    server.geldig.clear()          # GraphDB is herstart: de sessie bestaat niet meer
    server.aanroepen.clear()

    assert c.sparql("SELECT ?s WHERE { ?s ?p ?o }") == "ok"
    assert server.aanroepen == ["tools/call", "initialize", "tools/call"]


def test_sessie_die_ongeldig_blijft_wordt_een_zichtbare_fout():
    """Hoogstens één herstelpoging: een tweede 404 komt ergens anders vandaan en mag niet in een
    lus verdwijnen."""
    class _AltijdWeg(_NepServer):
        def post(self, url, json=None, headers=None, **_kw):
            resp = super().post(url, json=json, headers=headers, **_kw)
            self.geldig.clear()    # elke sessie is meteen weer ongeldig
            return resp

    with pytest.raises(MCPError, match="blijft ongeldig"):
        _client_met(_AltijdWeg()).sparql("SELECT ?s WHERE { ?s ?p ?o }")
