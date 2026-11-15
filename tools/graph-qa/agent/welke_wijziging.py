"""Welke wijziging bedoel je? Een vraag naar "de wijziging" van één artikel zonder datum of publicatie (agentset V04, A6:
"Vergelijk de tekst van artikel 36 … van vóór en na de wijziging"). Een artikel is vaak meer dan eens gewijzigd. Het
model koos zelf de laatste wijziging die de BWB koppelt en vergeleek daarop, in drie runs. Welke wijziging bedoeld is,
weet alleen de jurist: de code vraagt het vóór het model, met de laatste wijziging uit de graaf (`geldigheid`) als
kandidaat en de ruimte om een andere te noemen.

Geen vraag als de vraag zelf al kiest: een jaartal of datum buiten de naam van de regeling, een publicatie ("Stb.",
"Kamerstuk", "wet van"), of een woord dat één wijziging aanwijst ("laatste", "eerste", "recentste", "nieuwste").
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("graph_qa.welke_wijziging")

_DE_WIJZIGING = re.compile(r"\b(?:v[óo]{1,2}r\s+en\s+na\s+de\s+wijziging|de\s+wijziging\s+van\s+(?:het\s+)?artikel)\b", re.I)
_KIEST_AL = re.compile(
    r"\b(?:laatste|eerste|recentste|nieuwste|vorige|meest\s+recente)\s+wijziging\b|\bstb\b|\bstaatsblad\b|\bkamerstuk"
    r"|\bwet\s+van\s+\d|\bkst-|\bstb-|\b\d{1,2}[-/ ](?:\d{1,2}|januari|februari|maart|april|mei|juni|juli|augustus|"
    r"september|oktober|november|december)\b", re.I)
_JAAR = re.compile(r"\b(?:18|19|20)\d{2}\b")


def vraagt_welke(vraag: str, regelingtitel: str) -> bool:
    """Noemt de vraag "de wijziging" zonder te zeggen welke? Het jaartal in de naam van de regeling telt niet."""
    zonder_naam = re.sub(re.escape(regelingtitel), " ", vraag or "", flags=re.I) if regelingtitel else vraag or ""
    return bool(_DE_WIJZIGING.search(zonder_naam)) and not _KIEST_AL.search(zonder_naam) and not _JAAR.search(zonder_naam)


def laatste_wijziging(graph: Any, bwb_id: str, artikel: str) -> str:
    """De laatste wijziging van het artikel volgens de BWB, als "Stb. 2009, 610 (in werking 4 juli 2010)", of leeg."""
    from .tools import dispatch

    try:
        data = json.loads(dispatch("geldigheid", graph, {"bwb_id": bwb_id, "artikel": artikel}))
    except Exception:  # noqa: BLE001 – zonder kandidaat is de vraag nog steeds de goede vraag
        logger.warning("geldigheid voor de wijzigingsvraag mislukt", exc_info=True, extra={"categorie": "technisch"})
        return ""
    rij = next(iter(data.get("resultaten") or []), {}) if isinstance(data, dict) else {}
    bron = str(rij.get("bron") or rij.get("wijzigingsbron") or "").strip()
    if not bron:
        return ""
    bron = re.sub(r"^Stb\.\s*(\d{4})-(\d+)$", r"Stb. \1, \2", bron)
    inwerking = str(rij.get("bepalingInwerking") or "").strip()
    return f"{bron} (in werking {inwerking})" if inwerking else bron


def melding(vraag: str, graph: Any) -> str:
    """De vraag aan de jurist, of leeg als de vraag zelf al zegt welke wijziging, of niet één artikel van één regeling noemt."""
    from .aanwijzing import lees_aanwijzing
    from .overzicht import regelingen_in_vraag

    if not _DE_WIJZIGING.search(vraag or ""):
        return ""   # de gewone vraag: geen graafquery
    aanwijzing = lees_aanwijzing(vraag or "")
    if len(aanwijzing.artikelen) != 1 or graph is None:
        return ""
    try:
        regelingen = regelingen_in_vraag(graph, vraag)
    except Exception:  # noqa: BLE001 – geen namen: de gewone weg
        return ""
    if len(regelingen) != 1:
        return ""
    bwb_id, titel = regelingen[0]
    if not vraagt_welke(vraag, titel):
        return ""
    artikel = aanwijzing.artikelen[0]
    laatste = laatste_wijziging(graph, bwb_id, artikel)
    opties = [f"- de laatste wijziging: {laatste}" if laatste else "- de laatste wijziging die de BWB kent",
              "- een andere wijziging: noem de datum of de wijzigingswet"]
    return (f"Artikel {artikel} van de {titel} kan meer dan eens gewijzigd zijn. Welke wijziging bedoel je?\n"
            + "\n".join(opties))
