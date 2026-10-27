"""TOOI in de api (spoor I6): de thema's uit `tooitop` als vaste lijst.

Het thema van een werkgebied is een URI uit de TOOI-thesaurus tooitop (thema-indeling officiële
publicaties). De lijst staat als snapshot in `tooi_themas.json` (CC0), met bron en datum; een thema dat
er niet in staat, weigert het contract. Een organisatie-URI (het eerstverantwoordelijke ministerie)
schrijft de importer in de graaf (`tools/bwb-import/app/tooi.py`).
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

SNAPSHOT = Path(__file__).with_name("tooi_themas.json")


@cache
def themas() -> dict[str, dict]:
    """URI → {label, breder}."""
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["themas"]


def thema_label(uri: str | None) -> str:
    return (themas().get(uri or "") or {}).get("label", "")


#: Van het rechtsgebied uit de WTI (een woord in het label) naar een thema van tooitop: een kleine,
#: vaste afbeeldingstabel. De eerste regel die past, telt; volgorde is van specifiek naar breed.
RECHTSGEBIED_THEMA: tuple[tuple[str, str], ...] = (
    ("belasting", "belasting"), ("invordering", "belasting"), ("toeslag", "sociale zekerheid"),
    ("sociaal zekerheid", "sociale zekerheid"), ("sociale zekerheid", "sociale zekerheid"),
    ("uitkering", "sociale zekerheid"), ("subsidie", "begroting"), ("arbeid", "arbeidsverhoudingen"),
    ("strafrecht", "strafrecht"), ("privaatrecht", "privaatrecht"), ("burgerlijk", "privaatrecht"),
    ("bestuursrecht", "bestuursrecht"), ("staats", "staatsrecht"), ("overheid", "inrichting van de overheid"),
    ("milieu", "natuur en milieu"), ("onderwijs", "onderwijs en wetenschap"), ("gezondheid", "zorg en gezondheid"),
    ("zorg", "zorg en gezondheid"), ("verkeer", "verkeer"), ("vreemdeling", "migratie"), ("migratie", "migratie"),
    ("ruimtelijk", "ruimtelijke ordening"), ("wonen", "wonen"), ("economi", "economie"),
)


def _uri_van_label(label: str) -> str | None:
    return next((u for u, t in themas().items() if t["label"] == label), None)


def thema_voorstel(rechtsgebieden: list[str]) -> list[str]:
    """De thema's die bij deze rechtsgebieden passen, het vaakst eerst (zonder model, spoor I6)."""
    telling: dict[str, int] = {}
    for gebied in rechtsgebieden:
        laag = gebied.casefold()
        label = next((t for woord, t in RECHTSGEBIED_THEMA if woord in laag), None)
        if label and (uri := _uri_van_label(label)):
            telling[uri] = telling.get(uri, 0) + 1
    return sorted(telling, key=lambda u: (-telling[u], themas()[u]["label"]))
