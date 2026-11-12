"""Waaruit één modelverzoek bestaat, in tekens en zonder inhoud.

De meting per modelaanroep (`Verbruiksmeter.aanroepen`) zei wat een aanroep kostte: invoer, cache lezen, cache schrijven,
uitvoer. Ze zei niet waaraan. Daardoor bleef de vraag open waar het volume zit: in de toolschema's, de systeemprompt,
eerdere beurten of de lopende beurt. Ook bleef onduidelijk waarom de cache koud was. Komt dat door een andere toolset of
door een verlopen cache?

`opbouw` beantwoordt dat met tellingen en korte vingerafdrukken:

- `tools_tekens`, `tools_aantal`, `tools_hash`: de toolschema's zoals ze de deur uitgaan. Ze staan vooraan in de cache
  (tools → system → messages), dus een andere `tools_hash` dan de vorige aanroep betekent een nieuw voorvoegsel;
- `system_stabiel_tekens`, `system_hash`, `system_variabel_tekens`: de twee delen van `ports.Systeem`; het cachepunt
  staat op het stabiele deel;
- `historie_tekens`, `beurt_tekens`, `berichten`: de berichten vóór en vanaf de lopende beurt. Een correctiebericht
  ("Let op: …") telt mee in de beurt, net als in `berichten.beurt_start` met een vraag;
- `samenstelling`: de indeling van het hele verzoek over de categorieën van `contextdelen`, in één maat (zie hieronder).

Een hash is twaalf hextekens van een sha256: genoeg om twee verzoeken te vergelijken, te weinig om iets terug te lezen.
Geen veldnaam bevat "token": de redactie in `observability` kijkt daarnaar.

**De samenstelling** (plan contextweergave, *De categorieën*). Elk deel van het verzoek valt in precies één categorie,
en de maat is voor elk deel dezelfde: de lengte van de JSON zoals het deel de deur uitgaat. De oudere velden hierboven
houden hun eigen maat (`_msg_lengte`): het historievenster rekent ermee, en metingen blijven vergelijkbaar.

- **Tools** via het register waar de tool in staat (`contextdelen.tool_categorie`).
- **Systeem**: de identiteit (`SYSTEM_PROMPT`) is `systeem`, de rest `methode`. De antwoordlus geeft identiteit en
  specialist als één stabiel deel op, want elk ander deel zou het cachepunt verplaatsen. De identiteit wordt daarom
  herkend aan haar tekst, vooraan in het eerste deel. Het laatste van meer delen is het variabele deel (zo splitst de
  adapter): `beurtcontext` (alleen nog bij de meetvlag `beurtcontext_plek`, en bij de supervisor).
- **Berichten** naar hun vorm: het blok met `BEURTCONTEXT_KOP` is `beurtcontext`, waar het ook staat; vóór het begin
  van de beurt is alles `historie`; vanaf het begin zijn `tool_result`-blokken `toolresultaten` en de rest `beurt`. De
  aanroeper geeft het begin van de beurt mee als hij het weet (`beurt_start`); anders wijst de kop het aan, en anders
  de laatste vraag. Met `opdracht` is het eerste bericht de opdracht van een subagent (ADR-016), ook als er daarna
  historie staat (een hervat kindgesprek).
- Wat niet te herkennen is, is `overig`. Lukt het indelen niet, dan is alles `overig`: een meting breekt nooit een
  aanroep.

De indeling leest alleen. Het verzoek zelf blijft byte-gelijk (`tests/test_modelverzoeken.py`).

**Eén berekening per aanroep.** De gedeelde modelstap (`llm_stap`) rekent de opbouw één keer uit en zet haar met de rol
in het `Aanroepkader` van de lopende aanroep; de adapter leest het daar (`voor_meter`) en geeft het door aan de meter.
Het kader reist niet mee in de kwargs: die gaan ongewijzigd naar de provider.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from . import contextdelen as delen
from .berichten import BEURTCONTEXT_KOP, CORRECTIE, _is_plain_user, _msg_lengte


def _hash(tekst: str) -> str:
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()[:12]


def _beurt_begin(messages: list[dict[str, Any]]) -> int:
    """De laatste platte user-beurt die geen correctie is. Zonder: 0 (alles is deze beurt)."""
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        c = m.get("content")
        if _is_plain_user(m) and not (isinstance(c, str) and c.startswith(CORRECTIE)):
            return i
    return 0


def _tekst(deel: Any) -> str:
    """Een systeemdeel als tekst: een string, of een blok `{"type": "text", "text": …}`."""
    return str(deel.get("text", "")) if isinstance(deel, dict) else str(deel or "")


def _delen(system: Any) -> tuple[str, str]:
    """(stabiel, variabel) zoals de adapter ze splitst: alles behalve het laatste deel is stabiel."""
    if isinstance(system, str):
        return system, ""
    delen = [_tekst(d) for d in (system or []) if d]
    if len(delen) <= 1:
        return (delen[0] if delen else ""), ""
    return "\n\n".join(delen[:-1]), delen[-1]


def _json(deel: Any) -> int:
    """De ene maat van de samenstelling: de lengte van het deel als JSON."""
    return len(json.dumps(deel, ensure_ascii=False))


def _heeft_kop(m: dict[str, Any]) -> bool:
    c = m.get("content")
    return isinstance(c, list) and any(_is_beurtcontext(b) for b in c)


def _is_beurtcontext(blok: Any) -> bool:
    return (isinstance(blok, dict) and blok.get("type") == "text"
            and str(blok.get("text", "")).startswith(BEURTCONTEXT_KOP))


def _begin(messages: list[dict[str, Any]], beurt_start: int | None) -> int:
    """Waar de lopende beurt begint: wat de aanroeper opgeeft, anders het bericht met de beurtcontext, anders de
    laatste vraag. Onafhankelijk van de plek van de beurtcontext (de meetvlag zet haar in de systeemprompt)."""
    if beurt_start is not None and 0 <= beurt_start <= len(messages):
        return beurt_start
    for i in range(len(messages) - 1, -1, -1):
        if _heeft_kop(messages[i]):
            return i
    return _beurt_begin(messages)


def _systeem_samenstelling(system: Any, uit: Counter) -> None:
    from .prompts import SYSTEM_PROMPT

    teksten = [system] if isinstance(system, str) else [_tekst(d) for d in (system or []) if d]
    for i, tekst in enumerate(teksten):
        if i and i == len(teksten) - 1:
            uit[delen.BEURTCONTEXT] += _json(tekst)  # het variabele deel, na het cachepunt
        elif not i and SYSTEM_PROMPT and tekst.startswith(SYSTEM_PROMPT):
            identiteit = _json(SYSTEM_PROMPT)
            uit[delen.SYSTEEM] += identiteit
            uit[delen.METHODE] += _json(tekst) - identiteit
        else:
            uit[delen.METHODE] += _json(tekst)


def _bericht_samenstelling(m: Any, basis: str, in_beurt: bool, uit: Counter) -> None:
    """Eén bericht over de categorieën. De blokken worden elk gemeten; wat overblijft (de rol, de haken, een tekst
    als string) hoort bij de categorie van het bericht zelf, zodat de som precies het bericht is."""
    heel = _json(m)
    if not isinstance(m, dict):
        uit[delen.OVERIG] += heel
        return
    c = m.get("content")
    verdeeld = 0
    if isinstance(c, list):
        for blok in c:
            n = _json(blok)
            if _is_beurtcontext(blok):
                categorie = delen.BEURTCONTEXT
            elif not isinstance(blok, dict):
                categorie = delen.OVERIG
            elif in_beurt and blok.get("type") == "tool_result":
                categorie = delen.TOOLRESULTATEN
            else:
                categorie = basis
            uit[categorie] += n
            verdeeld += n
    elif c is not None and not isinstance(c, str):
        uit[delen.OVERIG] += (verdeeld := _json(c))
    uit[basis] += heel - verdeeld


def samenstelling(system: Any, tools: list[dict[str, Any]], messages: list[dict[str, Any]], *,
                  beurt_start: int | None = None, opdracht: bool = False) -> dict[str, int]:
    """Het verzoek over de categorieën van `contextdelen`, in JSON-tekens, in de volgorde van het register en zonder
    lege categorieën. Elk deel telt precies één keer."""
    uit: Counter = Counter()
    for tool in tools:
        naam = tool.get("name", "") if isinstance(tool, dict) else ""
        uit[delen.tool_categorie(str(naam))] += _json(tool)
    _systeem_samenstelling(system, uit)
    try:
        begin = _begin(messages, beurt_start)
    except (AttributeError, TypeError):
        begin = 0  # een bericht in een vorm die hier niet voorzien is: alles is deze beurt, het vreemde deel `overig`
    for i, m in enumerate(messages):
        if opdracht and i == 0:
            basis = delen.OPDRACHT
        else:
            basis = delen.BEURT if i >= begin else delen.HISTORIE
        _bericht_samenstelling(m, basis, i >= begin, uit)
    return {c: uit[c] for c in delen.IDS if uit[c] > 0}


def _alles_overig(system: Any, tools: Any, messages: Any) -> dict[str, int]:
    """De terugval als het indelen niet lukt: alles is `overig`, en de som klopt nog."""
    try:
        n = len(json.dumps([system, tools, messages], ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        n = 0
    return {delen.OVERIG: n} if n else {}


def opbouw(*, system: Any = None, tools: list[dict[str, Any]] | None = None,
           messages: list[dict[str, Any]] | None = None, beurt_start: int | None = None, opdracht: bool = False,
           **_: Any) -> dict[str, Any]:
    """De opbouw van één verzoek. Neemt de kwargs van `llm.create`/`llm.stream` aan en negeert de rest.

    `beurt_start` (de index van de vraag van deze beurt) en `opdracht` (het eerste bericht is de opdracht van een
    subagent) geeft de aanroeper mee als hij ze weet; ze horen niet bij het verzoek aan het model.

    Een meting mag een aanroep nooit breken: lukt het tellen niet (een vorm die hier niet voorzien is), dan is de
    opbouw leeg."""
    try:
        uit = _opbouw(system, tools or [], messages or [], beurt_start)
    except (TypeError, ValueError, AttributeError):
        return {}
    try:
        uit["samenstelling"] = samenstelling(system, tools or [], messages or [], beurt_start=beurt_start,
                                             opdracht=opdracht)
    except Exception:  # noqa: BLE001 – een meting breekt nooit een aanroep
        uit["samenstelling"] = _alles_overig(system, tools, messages)
    return uit


def _opbouw(system: Any, tools: list[dict[str, Any]], messages: list[dict[str, Any]],
            beurt_start: int | None = None) -> dict[str, Any]:
    tools_json = json.dumps(tools, ensure_ascii=False)
    stabiel, variabel = _delen(system)
    begin = _begin(messages, beurt_start)
    return {
        "tools_tekens": len(tools_json),
        "tools_aantal": len(tools),
        "tools_hash": _hash(tools_json) if tools else "",
        "system_stabiel_tekens": len(stabiel),
        "system_hash": _hash(stabiel) if stabiel else "",
        "system_variabel_tekens": len(variabel),
        "historie_tekens": sum(_msg_lengte(m) for m in messages[:begin]),
        "beurt_tekens": sum(_msg_lengte(m) for m in messages[begin:]),
        "berichten": len(messages),
    }


# ── Het kader van de lopende aanroep ─────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Aanroepkader:
    """Wat de gedeelde modelstap over één aanroep weet en de adapter niet: wie hem doet, of die rol een toollus is, de
    opbouw van het verzoek (één keer berekend) en wat de aanroeper over het venster meldde (`venster_telling`,
    `historiegrens_tekens`). Alleen tellingen en namen uit de code."""

    rol: str = ""
    lus: bool = False
    opbouw: dict[str, Any] = field(default_factory=dict)
    kader: dict[str, Any] = field(default_factory=dict)


_LOPEND: ContextVar[Aanroepkader | None] = ContextVar("graph_qa_aanroepkader", default=None)


@contextmanager
def aanroepkader(kader: Aanroepkader) -> Iterator[None]:
    """Zet het kader voor de aanroep die binnen dit blok de deur uitgaat. Een contextvariabele, dus per thread en per
    taak eigen: parallelle classificatiebatches zien elkaars kader niet."""
    merk = _LOPEND.set(kader)
    try:
        yield
    finally:
        _LOPEND.reset(merk)


def voor_meter(*, model: str = "", system: Any = None, tools: list[dict[str, Any]] | None = None,
               messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """De argumenten voor `Verbruiksmeter.tel_response`, op het moment dat de aanroep de deur uitgaat. Binnen de
    gedeelde modelstap komen ze uit het kader; daarbuiten (een test, een losse aanroep op de adapter) rekent de adapter
    de opbouw zelf uit, zonder rol."""
    k = _LOPEND.get()
    if k is None:
        return {"opbouw": opbouw(system=system, tools=tools, messages=messages), "model": model}
    return {"opbouw": k.opbouw, "rol": k.rol, "lus": k.lus, "model": model, "kader": k.kader}
