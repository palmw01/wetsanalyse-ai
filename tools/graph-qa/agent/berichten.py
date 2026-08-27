"""Het berichtenvenster naar de LLM: parsen, snoeien en schoonmaken.

Deze helpers bewaken één harde eis van de Anthropic-API: een `tool_result` mag nooit zonder zijn
`tool_use` in het venster staan. Ze zitten in een eigen module zodat zowel de orchestrator als de
node-modules ze kunnen gebruiken.
"""
from __future__ import annotations

from typing import Any

def _parse_final(final: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Splits een Anthropic-response in (tool_uses, text_parts)."""
    tool_uses: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for block in final.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_uses.append({"id": block.id, "name": block.name, "input": block.input})
    return tool_uses, text_parts


def _msg_lengte(m: dict[str, Any]) -> int:
    c = m.get("content")
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        return sum(len(str(b)) for b in c)
    return 0


def _is_tool_result_user(m: dict[str, Any]) -> bool:
    """Een user-message dat (alleen) tool_result-blokken draagt – orphan als z'n tool_use is weggevallen."""
    c = m.get("content")
    return (
        m.get("role") == "user"
        and isinstance(c, list)
        and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c)
    )


def _is_plain_user(m: dict[str, Any]) -> bool:
    """Een 'platte' user-beurt (de vraag/correctie) – géén tool_result-drager. Zo'n bericht is een
    geldig venster-begin: alles erna is een compleet assistant→tool_result-verloop."""
    return m.get("role") == "user" and not _is_tool_result_user(m)


def _trim_messages(messages: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """Beperk de historie die naar de LLM gaat tot een char-budget, met behoud van de
    tool_use/tool_result-integriteit (Anthropic weigert een orphan tool_result).

    Neem het achterste venster binnen budget en breid het begin zo nodig terug uit tot een platte
    user-beurt, zodat elk tool_result zijn tool_use behoudt (Anthropic weigert een orphan). Omdat
    messages[0] altijd een platte user-vraag is, termineert dat en is het resultaat nooit leeg;
    correctheid gaat daarbij boven het strikte char-budget. `max_chars<=0` → ongewijzigd.
    """
    if max_chars <= 0 or not messages:
        return messages
    total = 0
    start = 0
    for i in range(len(messages) - 1, -1, -1):
        total += _msg_lengte(messages[i])
        start = i
        if total >= max_chars:
            break
    # Loop terug over losgeknipte assistant/tool_result-berichten tot een geldig venster-begin
    # (een platte user-beurt), zodat er geen orphan tool_result vooraan blijft staan.
    while start > 0 and not _is_plain_user(messages[start]):
        start -= 1
    return messages[start:]


# Bovengrens op wat er in de CHECKPOINTER blijft staan. `max_history_chars` begrenst alleen wat er
# per beurt naar het model gaat; de opgeslagen historie groeide onbeperkt door, inclusief elk
# tool-resultaat van 8000 tekens. Bij een lang gesprek betekent dat een steeds tragere en dikkere
# checkpoint-write bij élke stap van de graaf.
#
# Ruim boven het prompt-budget gekozen (een veelvoud), zodat het snoeien nooit het venster raakt dat
# de LLM tóch al krijgt: dit is een opslagrem, geen tweede contextrem.
# Vaste grens, want een LangGraph-reducer is een pure functie zonder toegang tot `Settings`. Ruim
# vier keer het default prompt-budget (`max_history_chars`, 40k). Zet iemand dat budget hoger dan de
# helft hiervan, dan waarschuwt `Settings.controleer_historie_grens()` bij boot – dan zou de
# opslagrem binnen het promptvenster gaan knippen, en dat is precies wat hij niet moet doen.
MAX_HISTORIE_CHARS = 160_000


def _snoei_historie(messages: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """Houd de bewaarde historie onder een bovengrens, en knip alleen op een veilige grens.

    "Veilig" is een plátte user-beurt (`_is_plain_user`): begint de historie met een los
    tool_result, dan mist dat blok zijn tool_use en weigert Anthropic de hele request. Vinden we geen
    veilige grens binnen het budget, dan snoeien we níét – een te grote historie is hinderlijk, een
    kapotte is fataal.
    """
    if max_chars <= 0 or not messages:
        return messages
    totaal = sum(_msg_lengte(m) for m in messages)
    if totaal <= max_chars:
        return messages
    # Zoek van achter naar voren de eerste platte user-beurt die het geheel binnen budget brengt.
    opgeteld = 0
    for i in range(len(messages) - 1, -1, -1):
        opgeteld += _msg_lengte(messages[i])
        if opgeteld >= max_chars:
            for j in range(i, len(messages)):
                if _is_plain_user(messages[j]):
                    return messages[j:]
            return messages
    return messages


def _voeg_toe_en_snoei(
    bestaand: list[dict[str, Any]], nieuw: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """State-reducer voor `messages`: append (zoals `operator.add`) plus een opslagrem."""
    return _snoei_historie(list(bestaand) + list(nieuw), MAX_HISTORIE_CHARS)


def _schoon_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip lege tekstblokken (Anthropic weigert {"type":"text","text":""} – Claude stuurt die soms
    mee náást een tool_use; via het gespreksgeheugen komen ze terug). Berichten waarvan de content
    daardoor leeg wordt, slaan we over; tool_use/tool_result en string-content blijven ongemoeid."""
    schoon: list[dict[str, Any]] = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            nieuw = [
                b
                for b in c
                if not (isinstance(b, dict) and b.get("type") == "text" and not str(b.get("text", "")).strip())
            ]
            if nieuw:
                schoon.append({**m, "content": nieuw})
        else:
            schoon.append(m)
    return schoon
