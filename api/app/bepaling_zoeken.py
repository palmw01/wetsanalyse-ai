"""Een bepaling vinden zoals de jurist haar typt, binnen één regeling, uit de echte bronboom.

Voor *Bepaling toevoegen* (in het gesprek: graph-qa roept het aan voor het kaartje met de treffers): een regeling, dan
een vindplaats typen – "9 lid 2", "art. 9, tweede lid", "21.1", "25.4 onderdeel b", "36 lid 5 sub a" – en live de
bepalingen zien die er echt zijn, met het begin van hun tekst. Geen model en geen fulltext-index: de boom van de
regeling (`bron_resolver.haal_bronrijen`, één query, gecachet per regeling) en een vaste lezing van de invoer.

Waarom zo: een formulier met regeling + artikel + lid past niet op een beleidsregel (de Leidraad heeft divisies
als 9.2 en onderdelen zonder lid), en een vrij tekstveld laat de jurist raden wat er bestaat. Hier kiest hij uit
wat de graaf kent; wat hij dan opneemt is een bron-IRI, die de api daarna nog eens verifieert.
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass

from bronmodel import bouw_snapshot, subtree

from . import annotatie_v2_store as store
from .bron_resolver import haal_bronrijen

MAX_TREFFERS = 10
FRAGMENT = 160
_TTL = 600.0
_CACHE: dict[str, tuple[float, list[dict]]] = {}

_RANGTELWOORD = {
    "eerste": "1", "tweede": "2", "derde": "3", "vierde": "4", "vijfde": "5", "zesde": "6", "zevende": "7",
    "achtste": "8", "negende": "9", "tiende": "10", "elfde": "11", "twaalfde": "12", "dertiende": "13",
    "veertiende": "14", "vijftiende": "15", "zestiende": "16", "zeventiende": "17", "achttiende": "18",
    "negentiende": "19", "twintigste": "20",
}
_BEPALING = {"Artikel", "Divisie"}
_SOORT = {"Artikel": "artikel", "Divisie": "artikel", "Lid": "lid", "Onderdeel": "onderdeel"}


@dataclass(frozen=True)
class Vindplaats:
    """Wat de jurist typte, gelezen: het nummer van het artikel (of de divisie), een lid en een onderdeel – elk
    leeg als het er niet staat. `tekst` is wat overblijft als er geen nummer in staat (zoeken op de kop)."""
    artikel: str = ""
    lid: str = ""
    onderdeel: str = ""
    tekst: str = ""


def _plat(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def _kaal(nummer: str) -> str:
    """"a." → "a", "1°" → "1", "02" → "2": zoals een jurist het typt."""
    n = _plat(nummer).strip().rstrip(".").rstrip("°").strip()
    return n.lstrip("0") or n


def lees(invoer: str) -> Vindplaats:
    """De vindplaats uit vrije invoer. "artikel 9, tweede lid, onderdeel b" → (9, 2, b); "21.1" → (21.1);
    "25.4 onderdeel b" en "36 lid 5 sub a" ook. Begint de invoer niet met een nummer, dan is het tekst."""
    t = _plat(invoer)
    for woord, cijfer in _RANGTELWOORD.items():
        t = re.sub(rf"\b{woord}\s+lid\b", f"lid {cijfer}", t)
    t = re.sub(r"\b(artikel|art)\b\.?", " ", t)
    t = t.replace(",", " ").replace(";", " ")
    m = re.match(r"\s*([0-9]+[a-z]{0,6}(?:[.:][0-9]+[a-z]{0,6})*)\b", t)
    if not m:
        return Vindplaats(tekst=" ".join(t.split()))
    artikel, rest = m.group(1), t[m.end():]
    lid = re.search(r"\blid\s+([0-9]+[a-z]{0,6})\b", rest)
    onderdeel = re.search(r"\b(?:onderdeel|onderdelen|sub|letter)\s+([a-z]{1,3}|[0-9]+)\b", rest)
    if not onderdeel and lid:
        # "9 lid 2 b": een losse letter na het lid is het onderdeel.
        los = re.match(r"\s*([a-z]{1,2})\b", rest[lid.end():])
        onderdeel = los
    return Vindplaats(artikel=artikel, lid=lid.group(1) if lid else "",
                      onderdeel=_kaal(onderdeel.group(1)) if onderdeel else "")


async def boom(bwb_id: str) -> list[dict]:
    """De nodes van één regeling in documentvolgorde, met plek; gecachet per proces (`_TTL`)."""
    nu = time.monotonic()
    if bwb_id in _CACHE and nu - _CACHE[bwb_id][0] < _TTL:
        return _CACHE[bwb_id][1]
    snapshot = bouw_snapshot(await haal_bronrijen(bwb_id), bwb_id=bwb_id)
    nodes = snapshot["nodes"]
    _CACHE[bwb_id] = (nu, nodes)
    return nodes


def _plek(nodes: dict[str, dict], iri: str) -> tuple[str, str, list[str]]:
    """(artikel, lid, onderdelen) van een node, uit de boom: het nummer van het dichtstbijzijnde artikel of de
    divisie erboven, het lid, en de onderdelen van boven naar beneden."""
    artikel = lid = ""
    onderdelen: list[str] = []
    for i in store.keten(nodes, iri):
        n = nodes[i]
        if n["type"] == "Onderdeel" and not artikel and not lid:
            onderdelen.insert(0, _kaal(n["nummer"]))
        elif n["type"] == "Lid" and not artikel and not lid:
            lid = _kaal(n["nummer"])
        elif n["type"] in _BEPALING:
            artikel = _plat(n["nummer"]).strip()
            break
    return artikel, lid, onderdelen


def _naam(n: dict, plek: tuple[str, str, list[str]]) -> str:
    if n.get("vindplaats"):
        return n["vindplaats"]
    artikel, lid, onderdelen = plek
    delen = [f"Artikel {artikel}"] + ([f"lid {lid}"] if lid else []) + \
        ([f"onderdeel {' '.join(onderdelen)}"] if onderdelen else [])
    return ", ".join(delen)


def _treffer(n: dict, ordered: list[dict], plek: tuple[str, str, list[str]]) -> dict:
    tekst = next((x["tekst"] for x in subtree(ordered, n["bron_iri"]) if (x.get("tekst") or "").strip()), "")
    titel = n["label"] if n["type"] == "Divisie" and not n["label"].casefold().startswith("artikel") else ""
    return {"bron_iri": n["bron_iri"], "soort": _SOORT.get(n["type"], "deel"), "vindplaats": _naam(n, plek),
            "titel": titel, "fragment": " ".join(tekst.split())[:FRAGMENT]}


def zoek(ordered: list[dict], invoer: str, limit: int = MAX_TREFFERS) -> list[dict]:
    """De bepalingen die bij de invoer passen, beste eerst:

    1. precies wat er staat (het artikel, het lid, het onderdeel);
    2. wat eronder hangt (de leden of subdivisies van een artikel, de onderdelen van een lid);
    3. artikelen waarvan het nummer met de invoer begint ("21" → 21.1, 21a);
    4. zonder nummer: artikelen en divisies met de woorden in hun kop.

    Een lid bij een beleidsregel zonder leden is de subdivisie ("9 lid 2" → 9.2), zoals `bronmodel._kies_lid`."""
    v = lees(invoer)
    nodes = {n["bron_iri"]: n for n in ordered}
    kandidaten = [n for n in ordered if n["type"] in _SOORT]
    plekken = {n["bron_iri"]: _plek(nodes, n["bron_iri"]) for n in kandidaten}
    if not v.artikel:
        woorden = v.tekst.split()
        if not woorden:
            return []
        raak = [n for n in kandidaten if n["type"] in _BEPALING and all(w in _plat(n["label"]) for w in woorden)]
        return [_treffer(n, ordered, plekken[n["bron_iri"]]) for n in raak[:limit]]

    artikel = _plat(v.artikel)
    # Een beleidsregel kent geen leden: "9 lid 2" is divisie 9.2 als die bestaat.
    if v.lid and any(plekken[i][0] == f"{artikel}.{_plat(v.lid)}" and nodes[i]["type"] == "Divisie" for i in plekken) \
            and not any(plekken[i][0] == artikel and plekken[i][1] for i in plekken):
        artikel, lid = f"{artikel}.{_plat(v.lid)}", ""
    else:
        lid = _kaal(v.lid)

    def rang(n: dict) -> int | None:
        a, l, o = plekken[n["bron_iri"]]
        precies_o = [v.onderdeel] if v.onderdeel else []
        if a == artikel:
            if (l, o) == (lid, precies_o) and (lid or v.onderdeel or n["type"] in _BEPALING):
                return 0
            onder = (not lid or l == lid) and (not v.onderdeel or o[:1] == precies_o)
            if onder and (l, o) != (lid, precies_o) and (bool(l) or bool(o)):
                # Wat eronder hangt: alleen de eerstvolgende laag, anders spoelen diepe onderdelen alles weg.
                diepte = (1 if l and not lid else 0) + len(o) - len(precies_o)
                return 1 if diepte <= 1 else None
            return None
        if not lid and not v.onderdeel and n["type"] in _BEPALING and a.startswith(artikel):
            return 2
        return None

    gerangschikt = sorted(((r, n["volgorde"], n) for n in kandidaten if (r := rang(n)) is not None),
                          key=lambda x: (x[0], x[1]))
    return [_treffer(n, ordered, plekken[n["bron_iri"]]) for _, _, n in gerangschikt[:limit]]


def regelingen(alle: list[dict], invoer: str, eerst: list[str], limit: int = MAX_TREFFERS) -> list[dict]:
    """Regelingen uit `alle` ({bwb_id, citeertitel, soort, afkortingen}) op citeertitel, afkorting of BWB-id;
    die van het werkgebied (`eerst`) vooraan. Lege invoer: alleen die van het werkgebied."""
    t = _plat(invoer).strip()
    plek = {b: i for i, b in enumerate(eerst)}

    def past(r: dict) -> bool:
        if not t:
            return r["bwb_id"] in plek
        namen = [_plat(r.get("citeertitel") or ""), *(_plat(a) for a in r.get("afkortingen") or [])]
        return t in _plat(r["bwb_id"]) or any(all(w in n for w in t.split()) for n in namen)

    raak = [r for r in alle if past(r)]
    raak.sort(key=lambda r: (plek.get(r["bwb_id"], len(plek)), not _plat(r.get("citeertitel") or "").startswith(t),
                             r.get("citeertitel") or r["bwb_id"]))
    return raak[:limit]


def regelingen_query() -> str:
    """Alle regelingen in de graaf met citeertitel, soort en afkortingen (de WTI-verrijking)."""
    return """PREFIX bwb: <urn:bwb-ns:>
SELECT ?r ?citeertitel ?soort (GROUP_CONCAT(DISTINCT ?afk; separator=" | ") AS ?afkortingen) WHERE {
  ?r a bwb:Regeling . FILTER(STRSTARTS(STR(?r), "urn:bwb:"))
  OPTIONAL { ?r bwb:citeertitel ?citeertitel } OPTIONAL { ?r bwb:soort ?soort } OPTIONAL { ?r bwb:afkorting ?afk }
} GROUP BY ?r ?citeertitel ?soort LIMIT 2000"""


_REGELINGEN: tuple[float, list[dict]] | None = None


async def alle_regelingen() -> list[dict]:
    """De regelingen in de graaf, gecachet per proces (`_TTL`)."""
    global _REGELINGEN
    import httpx

    from .graaf_projectie_v2 import _select

    nu = time.monotonic()
    if _REGELINGEN and nu - _REGELINGEN[0] < _TTL:
        return _REGELINGEN[1]
    async with httpx.AsyncClient(timeout=20) as client:
        rijen = await _select(client, regelingen_query())
    alle = [{"bwb_id": (r.get("r") or "").removeprefix("urn:bwb:"), "citeertitel": r.get("citeertitel") or "",
             "soort": r.get("soort") or "",
             "afkortingen": [a.strip() for a in (r.get("afkortingen") or "").split(" | ") if a.strip()]}
            for r in rijen if re.fullmatch(r"urn:bwb:BWB[RV]\d+", r.get("r") or "")]
    _REGELINGEN = (nu, alle)
    return alle
