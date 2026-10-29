"""Leesbare bronnamen, los van bronidentiteit, tekst en annotatiecoördinaten."""
from __future__ import annotations

from collections.abc import Iterable

OPSOMMINGSTEKENS = frozenset({"–", "—", "-", "•", "·", "●"})


def bronlabel(node: dict, begrippen: Iterable[str] = ()) -> str:
    """De naam van een bronnode zoals de werkplek hem toont. Een ongenummerd onderdeel heet naar zijn begrippen
    (het specifiekste, dus langste, eerst), anders naar het begin van zijn tekst; een kaal label krijgt zijn
    nummer ("Hoofdstuk" + "V", "Lid" + "1", "Divisie" + "1.1.2")."""
    label = (node.get("label") or "").strip()
    nummer = (node.get("nummer") or "").strip()
    if node.get("type") == "Onderdeel" and (not nummer or nummer in OPSOMMINGSTEKENS):
        termen = sorted({b.strip() for b in begrippen if b.strip()}, key=lambda t: (-len(t), t))
        fragment = "; ".join(termen) or " ".join((node.get("tekst") or "").split())
        if fragment:
            fragment = fragment if len(fragment) <= 100 else fragment[:99].rstrip() + "…"
            return f"Onderdeel — {fragment}"
    if nummer and label == node.get("type"):
        return f"{label} {nummer}"
    return label
