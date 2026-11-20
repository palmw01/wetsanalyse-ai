"""Schakelbepalingen: een regeling buiten het zoekbereik die een regeling erin van toepassing verklaart (L-1-1).

Art. 72 Mijnbouwwet verklaart de AWR en de Invorderingswet 1990 "met overeenkomstige toepassing" op het winstaandeel. In
Termijnen hing de analysevraag eraan, maar de Mijnbouwwet stond niet in het zoekbereik en Lex stelde haar niet voor:
`bronnen_vinden.q_inkomend` volgt alleen een verwijzing naar een kernbepaling of iets daaronder, en een schakelbepaling
verwijst naar de hele regeling.

Deze stap is deterministisch en noemt geen regeling: hij leest alleen de verwijzingsgraaf en de formule rond het anker.
Een bepaling is een schakelbepaling als ze naar een regeling als geheel (`urn:bwb:BWBR…`) verwijst, en de zin met de
verwijzing van (overeenkomstige) toepassing spreekt zonder ontkenning ("is niet van toepassing" telt niet). Haar regeling
wordt een voorstel "regeling erbij?", met de bepaling als bewijs; de jurist beslist. Schakelbepalingen zijn een vaste
wetgevingstechniek (de AWR voor andere heffingen, de Awb voor bijzondere wetten), dus de stap is generiek.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from .bepaling_namen import rijen
from .graph.queries import NS, PREFIXES
from .ports import GraphPort

logger = logging.getLogger(__name__)

#: Hoeveel schakelregelingen een vraagkaart hoogstens voorstelt: de jurist kiest, en een veelgebruikte wet (de Awb)
#: wordt door honderden regelingen van toepassing verklaard.
MAX_VOORSTELLEN = 3
#: Hoeveel verwijzingen de query hoogstens leest.
MAX_RIJEN = 400

_TOEPASSING = re.compile(r"\b(?:(?:van\s+)?overeenkomstige\s+toepassing|(?:is|zijn|blijft|blijven)\s+(?:\S+\s+){0,8}?"
                         r"van\s+toepassing|met\s+(?:overeenkomstige\s+)?toepassing\s+van)\b", re.IGNORECASE)
_ONTKEND = re.compile(r"\b(?:niet|geen)\s+(?:\w+\s+){0,2}(?:van\s+)?(?:overeenkomstige\s+)?toepassing\b", re.IGNORECASE)
_BWB = re.compile(r"^BWBR\d{7}$")


def q_schakel(bwb_ids: list[str], limit: int = MAX_RIJEN) -> str:
    doelen = " ".join(f"<{NS}{b}>" for b in sorted(set(bwb_ids)) if _BWB.match(b))
    return PREFIXES + f"""SELECT DISTINCT ?doel ?bron ?tekst ?anker ?regeling ?titel WHERE {{
  VALUES ?doel {{ {doelen} }}
  ?v bwb:naar ?doel .
  ?bron bwb:heeftVerwijzing ?v .
  ?bron bwb:tekst ?tekst .
  FILTER(STRSTARTS(STR(?bron), "{NS}BWBR"))
  FILTER(!STRSTARTS(STR(?bron), CONCAT(STR(?doel), ":")))
  FILTER(REGEX(?tekst, "toepassing", "i"))
  OPTIONAL {{ ?v bwb:ankerTekst ?anker }}
  BIND(IRI(REPLACE(STR(?bron), "^({NS}BWBR[0-9]+).*$", "$1")) AS ?regeling)
  OPTIONAL {{ ?regeling bwb:citeertitel ?titel }}
}} ORDER BY ?regeling ?bron LIMIT {limit}"""


def _zin(tekst: str, anker: str) -> str:
    """De zin waarin het anker als heel woord staat ('wet' niet in 'Ambtenarenwet'); leeg als het er niet in staat."""
    m = re.search(rf"(?<!\w){re.escape(anker)}(?!\w)", tekst) if anker else None
    if m is None:
        return ""
    i = m.start()
    begin = max(tekst.rfind(". ", 0, i), tekst.rfind("; ", 0, i)) + 1
    eind = min((j for j in (tekst.find(". ", i), tekst.find("; ", i)) if j >= 0), default=len(tekst))
    return tekst[begin:eind + 1]


def is_schakel(tekst: str, anker: str) -> bool:
    """Spreekt de zin met deze verwijzing van (overeenkomstige) toepassing, zonder ontkenning? Zonder anker in de tekst
    is er geen bewijs, en dus geen schakel."""
    zin = _zin(tekst, anker)
    return bool(zin) and bool(_TOEPASSING.search(zin)) and not _ONTKEND.search(zin)


def schakelregelingen(graph: GraphPort, zoekbereik: list[str], *, max_voorstellen: int = MAX_VOORSTELLEN
                      ) -> list[dict[str, Any]]:
    """De regelingen buiten het zoekbereik met een schakelbepaling naar een regeling erin, sterkste eerst: wie meer
    regelingen uit het zoekbereik van toepassing verklaart, komt eerst. Per regeling de bepalingen en de doelen."""
    binnen = [b for b in zoekbereik if _BWB.match(b)]
    if not binnen:
        return []
    try:
        gevonden = rijen(graph, q_schakel(binnen))
    except Exception:  # noqa: BLE001 – geen graaf: dan geen voorstel, de rest van de vraagkaart werkt
        logger.warning("schakelbepalingen: de graaf antwoordde niet", exc_info=True)
        return []
    per: dict[str, dict[str, Any]] = {}
    for r in gevonden:
        regeling = r.get("regeling", "").removeprefix(NS)
        if not _BWB.match(regeling) or regeling in binnen or not is_schakel(r.get("tekst", ""), r.get("anker", "")):
            continue
        p = per.setdefault(regeling, {"bwb_id": regeling, "titel": r.get("titel") or regeling, "bepalingen": [],
                                      "doelen": []})
        if r["bron"] not in p["bepalingen"]:
            p["bepalingen"].append(r["bron"])
        doel = r.get("doel", "").removeprefix(NS)
        if doel not in p["doelen"]:
            p["doelen"].append(doel)
    return sorted(per.values(), key=lambda p: (-len(p["doelen"]), -len(p["bepalingen"]), p["bwb_id"]))[:max_voorstellen]


def omschrijving(p: dict[str, Any], namen: dict[str, str]) -> str:
    """"verklaart de Invorderingswet 1990 van toepassing (artikel 72)" – uit de graaf, geen model."""
    doelen = [namen.get(d, d) for d in p["doelen"]]
    wat = doelen[0] if len(doelen) == 1 else ", ".join(doelen[:-1]) + " en " + doelen[-1]
    artikelen = sorted({b.split(":artikel:")[1].split(":")[0] for b in p["bepalingen"] if ":artikel:" in b})
    waar = f" (artikel {', '.join(artikelen[:3])})" if artikelen else ""
    return f"verklaart {wat} van toepassing{waar}: regeling erbij?"[:300]
