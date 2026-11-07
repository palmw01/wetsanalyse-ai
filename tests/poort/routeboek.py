"""Leest uit de bron welke routes er zijn en wie ze aanroept.

Statisch, met alleen de standaardbibliotheek: zo draait het contract bij elke PR in seconden, zonder de
afhankelijkheden van een onderdeel. Een aanroep die de parser niet herkent, valt weg; daarom toetst
`test_routecontract` ook dat er genoeg gevonden wordt.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[2]
FRONTEND = WORTEL / "frontend"
METHODEN = ("GET", "POST", "PUT", "PATCH", "DELETE")
# BFF-catch-all → de upstream eronder.
DOORGEEF = (
    ("/api/werkgebieden", "/v1/werkgebieden"),
    ("/api/annotatie/v2", "/v1/annotatie"),
    ("/api/begrippen", "/v1/begrippen"),
)


@dataclass(frozen=True)
class Route:
    methode: str
    pad: str
    plek: str


@dataclass(frozen=True)
class Aanroep:
    methode: str  # "REQ" = de methode van het inkomende verzoek
    pad: str
    plek: str


def normaal(pad: str) -> str:
    """Eén vorm voor FastAPI, Next en template-strings: variabele delen worden `{}`, een catch-all `{*}`."""
    pad = pad.split("?")[0]
    pad = re.sub(r"(?<=[A-Za-z0-9_-])\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}$", "", pad)  # `${qs}` achter een pad
    pad = re.sub(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "{}", pad)
    pad = pad.split("${")[0]  # een query met een geneste template-string
    pad = re.sub(r"\{[^{}*]+\}", "{}", pad)
    pad = re.sub(r"\[\.\.\.[^\]]*\]", "{*}", pad)
    pad = re.sub(r"\[[^\]]*\]", "{}", pad)
    return pad.rstrip("/") or "/"


def past(patroon: str, pad: str) -> bool:
    a, b = patroon.strip("/").split("/"), pad.strip("/").split("/")
    if "{*}" in a:
        i = a.index("{*}")
        return len(b) >= i + 1 and all(x == "{}" or y == "{}" or x == y for x, y in zip(a[:i], b[:i]))
    return len(a) == len(b) and all(x == "{}" or y == "{}" or x == y for x, y in zip(a, b))


def gewicht(patroon: str) -> int:
    return sum(deel not in ("{}", "{*}") for deel in patroon.strip("/").split("/"))


def _sluit(s: str, i: int) -> int:
    """De index van het haakje dat bij `s[i]` hoort, met strings overgeslagen."""
    diepte, teken = 0, None
    j = i
    while j < len(s):
        c = s[j]
        if teken:
            if c == "\\":
                j += 1
            elif c == teken:
                teken = None
        elif c in "\"'`":
            teken = c
        elif c in "([{":
            diepte += 1
        elif c in ")]}":
            diepte -= 1
            if diepte == 0:
                return j
        j += 1
    return len(s)


def _regel(s: str, i: int) -> int:
    return s[:i].count("\n") + 1


def _plek(pad: Path, regel: int | None = None) -> str:
    rel = pad.relative_to(WORTEL)
    return f"{rel}:{regel}" if regel else str(rel)


def _fastapi(py: Path, *, voorvoegsel: str = "/v1") -> list[Route]:
    boom = ast.parse(py.read_text(encoding="utf-8"))
    prefix = ""
    for n in ast.walk(boom):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and getattr(n.value.func, "id", "") == "APIRouter":
            for k in n.value.keywords:
                if k.arg == "prefix":
                    prefix = k.value.value
    routes = []
    for n in ast.walk(boom):
        if not isinstance(n, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        for d in n.decorator_list:
            if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                    and d.func.attr.upper() in METHODEN and d.args and isinstance(d.args[0], ast.Constant)):
                continue
            eigenaar = getattr(d.func.value, "id", "")
            if eigenaar == "router":
                routes.append(Route(d.func.attr.upper(), normaal(voorvoegsel + prefix + d.args[0].value), _plek(py, n.lineno)))
            elif eigenaar == "app":
                routes.append(Route(d.func.attr.upper(), normaal(d.args[0].value), _plek(py, n.lineno)))
    return routes


def api_routes() -> list[Route]:
    app = WORTEL / "api" / "app"
    return [r for py in [*app.glob("*.py"), *(app / "routers").glob("*.py")] for r in _fastapi(py)]


def agent_routes() -> list[Route]:
    return _fastapi(WORTEL / "tools" / "graph-qa" / "api" / "main.py")


def bff_routes() -> list[Route]:
    routes = []
    for bestand in (FRONTEND / "app" / "api").rglob("route.ts"):
        s = bestand.read_text(encoding="utf-8")
        url = "/" + str(bestand.parent.relative_to(FRONTEND / "app"))
        methoden = set(re.findall(r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE)\b", s))
        if "nextauth" in url:
            methoden |= {"GET", "POST"}
        routes += [Route(m, normaal(url), _plek(bestand)) for m in methoden]
    return routes


def bff_aanroepen() -> list[Aanroep]:
    """Wat de BFF zelf upstream aanroept: `proxy(...)` en `serverGet`/`serverPost`."""
    uit = []
    bestanden = [*(FRONTEND / "app").rglob("*.ts*"), FRONTEND / "lib" / "server.ts", FRONTEND / "auth.ts"]
    for bestand in bestanden:
        if ".test." in bestand.name:
            continue
        s = bestand.read_text(encoding="utf-8")
        for m in re.finditer(r"\bproxy\(\s*(`[^`]*`|\"[^\"]*\")", s):
            staart = s[m.start():_sluit(s, m.start() + 5)]
            methode = re.search(r'method:\s*"(\w+)"', staart)
            soort = methode.group(1) if methode else "REQ" if "req.method" in staart else "GET"
            pad = normaal(m.group(1)[1:-1])
            if pad.endswith("{}{}"):
                continue  # een catch-all die pad en query doorgeeft: de client-kant toetst dat pad
            uit.append(Aanroep(soort, pad, _plek(bestand, _regel(s, m.start()))))
        for m in re.finditer(r"fetch\(\s*`\$\{apiBaseUrl\(\)\}([^`]*)`", s):
            methode = re.search(r'method:\s*"(\w+)"', s[m.start():_sluit(s, m.start() + 5)])
            uit.append(Aanroep(methode.group(1) if methode else "GET", normaal(m.group(1)), _plek(bestand, _regel(s, m.start()))))
        for m in re.finditer(r"server(Get|Post)\w*(?:<[^(]*>)?\(\s*[`\"]([^`\"]*)", s):
            uit.append(Aanroep(m.group(1).upper(), normaal(m.group(2)), _plek(bestand, _regel(s, m.start()))))
    return uit


def _hulppad(basis: str, argumenten: str) -> str:
    """Het pad van `wg(...)` of `generiek(...)` in `lib/api.ts`."""
    delen, diepte, huidig = [], 0, ""
    for c in argumenten:
        diepte += (c in "([{") - (c in ")]}")
        if c == "," and diepte == 0:
            delen.append(huidig.strip())
            huidig = ""
        else:
            huidig += c
    if huidig.strip():
        delen.append(huidig.strip())
    return "/".join([basis, *(d[1:-1] if re.fullmatch(r'"[^"]*"', d) else "{}" for d in delen)])


_HULPEN = {"wg(": "/api/werkgebieden", "generiek(": "/api/begrippen"}


def _template(tekst: str, begin: int) -> tuple[str, int]:
    """De inhoud van de string die op `tekst[begin]` opent, en de index erna."""
    teken = tekst[begin]
    eind = begin + 1
    while tekst[eind] != teken:
        eind = _sluit(tekst, eind + 1) + 1 if tekst[eind:eind + 2] == "${" else eind + 1
    return tekst[begin + 1:eind], eind + 1


def client_aanroepen() -> list[Aanroep]:
    """Wat de browser naar de BFF stuurt: `fetch`, `wg(...)`, `nodeRequest` en `sendBeacon`."""
    bestanden = [
        *(FRONTEND / "lib").rglob("*.ts"), *(FRONTEND / "components").rglob("*.ts*"),
        *(FRONTEND / "app").rglob("*.tsx"),
    ]
    uit = []
    for bestand in bestanden:
        if ".test." in bestand.name or bestand.name in ("server.ts", "uiSpoor.test.ts"):
            continue
        s = bestand.read_text(encoding="utf-8")
        for m in re.finditer(r"\bfetch\(", s):
            binnen = s[m.end():_sluit(s, m.end() - 1)]
            methode = re.search(r'method:\s*"(\w+)"', binnen) or re.search(r'jsonInit\("(\w+)"', binnen)
            soort = methode.group(1) if methode else "GET"
            kop = re.match(r"\s*(`|\"|wg\(|generiek\()", binnen)
            if not kop:
                continue
            if kop.group(1) in _HULPEN:
                a = binnen.index(kop.group(1)) + len(kop.group(1)) - 1
                pad = _hulppad(_HULPEN[kop.group(1)], binnen[a + 1:_sluit(binnen, a)])
            else:
                pad, _ = _template(binnen, binnen.index(kop.group(1)))
                hulp = re.match(r"\$\{(wg\(|generiek\()", pad)
                if hulp:
                    a = pad.index(hulp.group(1)) + len(hulp.group(1)) - 1
                    pad = _hulppad(_HULPEN[hulp.group(1)], pad[a + 1:_sluit(pad, a)])
            if pad.startswith("/api/"):
                uit.append(Aanroep(soort, normaal(pad), _plek(bestand, _regel(s, m.start()))))
        for m in re.finditer(r"nodeRequest(?:<[^(]*>)?\(", s):
            binnen = s[m.end():_sluit(s, m.end() - 1)]
            kop = re.match(r"\s*([`\"])", binnen)
            if not kop:
                continue
            pad, na = _template(binnen, binnen.index(kop.group(1)))
            rest = binnen[na:].strip()
            eigen = re.search(r'"(DELETE|PATCH|PUT)"\s*,?\s*$', rest)
            soort = eigen.group(1) if eigen else "POST" if rest else "GET"
            uit.append(Aanroep(soort, normaal("/api/annotatie/v2/" + pad), _plek(bestand, _regel(s, m.start()))))
        for m in re.finditer(r'sendBeacon\("([^"]*)"', s):
            uit.append(Aanroep("POST", normaal(m.group(1)), _plek(bestand, _regel(s, m.start()))))
    return uit


# ── De clients buiten de frontend ────────────────────────────────────────────────────────────────

_HULPPADEN = {
    "_werkgebied_pad": "/v1/werkgebieden/{id}",
    "_run_pad": "/v1/werkgebieden/{id}/begrippen-runs/{run}",
    "_bronnen_pad": "/v1/werkgebieden/{id}/bronnen-runs/{run}",
    "_kaart_pad": "/v1/werkgebieden/{id}/begrippen/{b}/kaart-runs/{run}",
}


def _waarde(e: ast.AST, env: dict[str, str]) -> str:
    if isinstance(e, ast.Constant):
        return str(e.value)
    if isinstance(e, ast.JoinedStr):
        return "".join(_waarde(v, env) for v in e.values)
    if isinstance(e, ast.FormattedValue):
        return _waarde(e.value, env)
    if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr in _HULPPADEN:
        return _HULPPADEN[e.func.attr]
    if isinstance(e, ast.Attribute) and e.attr == "_basis":
        return ""
    if isinstance(e, ast.Name) and e.id in env:
        return env[e.id]
    return "{x}"


def agent_aanroepen() -> list[Aanroep]:
    """Alles wat graph-qa bij de api aanroept: de client (`agent/wetsanalyse_api.py`) en de leesclients."""
    return _client_aanroepen_agent() + agent_leesaanroepen()


def _client_aanroepen_agent() -> list[Aanroep]:
    """De client van graph-qa naar de api (`agent/wetsanalyse_api.py`)."""
    py = WORTEL / "tools" / "graph-qa" / "agent" / "wetsanalyse_api.py"
    uit = []
    for fn in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
        if not isinstance(fn, ast.AsyncFunctionDef):
            continue
        env: dict[str, str] = {}
        for s in ast.walk(fn):
            if (isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name)
                    and isinstance(s.value, ast.JoinedStr | ast.Call | ast.Constant)):
                env[s.targets[0].id] = _waarde(s.value, env)
        for c in ast.walk(fn):
            if not (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)):
                continue
            naam, eigenaar = c.func.attr, c.func.value
            if naam in ("_post", "_haal") and fn.name != "_post":
                uit.append(Aanroep({"_post": "POST", "_haal": "GET"}[naam], normaal(_waarde(c.args[0], env)), _plek(py, c.lineno)))
            elif naam == "_verstuur" and fn.name != "_post":
                uit.append(Aanroep(c.args[0].value, normaal(_waarde(c.args[1], env)), _plek(py, c.lineno)))
            elif (isinstance(eigenaar, ast.Attribute) and eigenaar.attr == "_client"
                  and naam in ("get", "post", "patch", "delete") and fn.name != "_haal"):
                uit.append(Aanroep(naam.upper(), normaal(_waarde(c.args[0], env)), _plek(py, c.lineno)))
    return uit


def _lees_pad(e: ast.AST) -> str:
    if isinstance(e, ast.Constant):
        return str(e.value)
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
        return _lees_pad(e.left) + _lees_pad(e.right)
    return "{x}"


def agent_leesaanroepen() -> list[Aanroep]:
    """De leesclients van graph-qa (`annotatie_read.py`, `begrip_read.py`): `self._request("GET", pad, …)` onder de
    basis die `_request` zelf aan de url plakt."""
    uit = []
    for naam in ("annotatie_read.py", "begrip_read.py"):
        py = WORTEL / "tools" / "graph-qa" / "agent" / naam
        tekst = py.read_text(encoding="utf-8")
        basis = re.search(r'\+ "(/v1/[a-z-]+)" \+ path', tekst).group(1)
        for c in ast.walk(ast.parse(tekst)):
            if (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "_request"
                    and len(c.args) >= 2 and isinstance(c.args[0], ast.Constant)):
                uit.append(Aanroep(c.args[0].value, normaal(basis + _lees_pad(c.args[1])), _plek(py, c.lineno)))
    return uit


def admin_mcp_aanroepen() -> list[Aanroep]:
    ts = WORTEL / "tools" / "wetsanalyse-admin-mcp" / "src" / "index.ts"
    uit = []
    for i, regel in enumerate(ts.read_text(encoding="utf-8").splitlines(), 1):
        for m in re.finditer(r'apiFetch\("(\w+)",\s*[`"]([^`"]*(?:\$\{[^`]*)?)', regel):
            uit.append(Aanroep(m.group(1), normaal(m.group(2)), _plek(ts, i)))
    return uit
