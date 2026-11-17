"""Minimale MCP-client naar de graaf (alleen lezen). De MCP-server `graphdb` staat machine-lokaal geregistreerd
(`claude mcp add`, ~/.claude.json); URL en token komen daaruit en worden nooit getoond of opgeslagen."""
import json, os, sys, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools/graph-qa"))
sys.path.insert(0, str(REPO / "packages/bronmodel"))
from agent.graph.results import parse_select  # noqa: E402


def _registratie():
    cfg = json.load(open(os.path.expanduser("~/.claude.json")))
    for p in (cfg.get("projects") or {}).values():
        s = (p.get("mcpServers") or {}).get("graphdb")
        if s and s.get("url"):
            return s["url"], dict(s.get("headers") or {})
    raise SystemExit("geen MCP-server 'graphdb' geregistreerd")


_sessie = None
_id = 0


def _post(body, sessie=None):
    url, headers = _registratie()
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **headers}
    if sessie:
        h["Mcp-Session-Id"] = sessie
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        tekst = r.read().decode()
        sid = r.headers.get("Mcp-Session-Id")
    if tekst.lstrip().startswith("{"):
        return json.loads(tekst), sid
    for regel in tekst.splitlines():
        if regel.startswith("data:"):
            return json.loads(regel[5:].strip()), sid
    return None, sid


def _init():
    global _sessie
    _, _sessie = _post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "meting", "version": "0"}}})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, _sessie)


def select(q):
    global _id
    if _sessie is None:
        _init()
    _id += 1
    res, _ = _post({"jsonrpc": "2.0", "id": _id, "method": "tools/call",
                    "params": {"name": "sparql_query", "arguments": {"query": q, "repositoryId": "inning"}}}, _sessie)
    if "error" in res:
        raise RuntimeError(res["error"])
    inhoud = res["result"]["content"][0]["text"]
    if res["result"].get("isError"):
        raise RuntimeError(inhoud[:300])
    return parse_select(inhoud)
