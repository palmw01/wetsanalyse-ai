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
  ("Let op: …") telt mee in de beurt, net als in `berichten.beurt_start` met een vraag.

Een hash is twaalf hextekens van een sha256: genoeg om twee verzoeken te vergelijken, te weinig om iets terug te lezen.
Geen veldnaam bevat "token": de redactie in `observability` kijkt daarnaar.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .berichten import CORRECTIE, _is_plain_user, _msg_lengte


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


def opbouw(*, system: Any = None, tools: list[dict[str, Any]] | None = None,
           messages: list[dict[str, Any]] | None = None, **_: Any) -> dict[str, Any]:
    """De opbouw van één verzoek. Neemt de kwargs van `llm.create`/`llm.stream` aan en negeert de rest.

    Een meting mag een aanroep nooit breken: lukt het tellen niet (een vorm die hier niet voorzien is), dan is de
    opbouw leeg."""
    try:
        return _opbouw(system, tools or [], messages or [])
    except (TypeError, ValueError, AttributeError):
        return {}


def _opbouw(system: Any, tools: list[dict[str, Any]], messages: list[dict[str, Any]]) -> dict[str, Any]:
    tools_json = json.dumps(tools, ensure_ascii=False)
    stabiel, variabel = _delen(system)
    begin = _beurt_begin(messages)
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
