"""Leesbare bronnamen, los van bronidentiteit, tekst en annotatiecoördinaten."""
from __future__ import annotations

from collections.abc import Iterable

OPSOMMINGSTEKENS = frozenset({"–", "—", "-", "•", "·", "●"})


def bronlabel(node: dict, begrippen: Iterable[str] = ()) -> str:
    label = (node.get("label") or "").strip()
    nummer = (node.get("nummer") or "").strip()
    if node.get("type") == "Onderdeel" and (not nummer or nummer in OPSOMMINGSTEKENS):
        termen = sorted({b.strip() for b in begrippen if b.strip()})
        fragment = "; ".join(termen) or " ".join((node.get("tekst") or "").split())
        if fragment:
            fragment = fragment if len(fragment) <= 100 else fragment[:99].rstrip() + "…"
            return f"Onderdeel — {fragment}"
    if nummer and label == node.get("type"):
        return f"{label} {nummer}"
    return label
