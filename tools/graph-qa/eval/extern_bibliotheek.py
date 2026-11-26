"""Een begrippen- en afleidingsregelbibliotheek als referentie: inlezen en vergelijken met een werkgebied.

Een team dat buiten het platform analyseert, legt activiteit 3 vaak vast in een wiki: één pagina per begrip en één per
afleidingsregel, elk met een veldtabel (naam, definitie of regeltekst, klasse, waarde, bron, …), en een werkbestand dat
per klasse de gemarkeerde formuleringen aan een begripsnaam koppelt. Deze module leest zo'n Confluence-export (HTML) in
een neutraal schema en vergelijkt het met de begrippen en regels van een werkgebied. Het is de tegenhanger van
`eval/extern_dossier.py`, dat activiteit 2 vergelijkt, en gebruikt dezelfde HTML-boom en dezelfde regels voor de plek
van een bepaling. Plan: `docs/architectuur/plan-lessen-termijnen-bibliotheek.md`, V1.

**Het materiaal zelf hoort niet in de repo.** Een export is van derden; hij en alles wat eruit komt (de referentie,
het rapport) staan in `docs/acceptatie/lokaal/` (gitignored) of buiten de repo. De code kent geen pad en geen
afkorting van een regeling: alles komt als argument binnen. In de repo komt hoogstens een manifest zonder inhoud
(`manifest`: aantallen en hashes, geen namen).

**De export is onvertrouwde invoer.** De lezer gebruikt alleen de standaardbibliotheek, voert niets uit en volgt geen
link. Draai hem met `python -I`.

Wat de vergelijking zegt, en wat niet:

- **Begrippen** worden gekoppeld via de formuleringen waarop ze rusten, niet via hun naam: het werkbestand noemt per
  formulering de vindplaats en de begripsnaam, het werkgebied per element de bronnode en de tekst, en de koppelingen van
  het werkgebied zeggen welk begrip op welk element rust. Uitkomst per referentiebegrip: `gedekt`, `anders_gesneden`
  (de formuleringen liggen bij meer begrippen, of één begrip draagt ook die van een ander referentiebegrip),
  `zonder_begrip` (het element is er, het begrip niet), `niet_gemarkeerd` (geen element op die plek), en voor een
  begrip zonder formulering in het werkbestand (vaak een tussenresultaat) `alleen_op_naam`/`ontbreekt`, op naam.
- **Regels** worden gekoppeld via hun uitvoer: het referentiebegrip dat de regel afleidt (de naam na "bepaal"), en de
  begrippen in het werkgebied die daarbij horen. Daarnaast hoeveel van de invoerbegrippen overeenkomen.
- De referentie is **één analyse, geen gouden standaard**, en vaak met een andere analysevraag. De uitkomst is dekking
  en verschil; een jurist beoordeelt de verschillen (`docs/wetsanalyse/referentieset/adjudicatieprotocol.md`).

Gebruik:

    uv run python -I eval/extern_bibliotheek.py lees --begrippen <map> --regels <map> [--werkbestand <html>] \\
        [--traject <naam>] --uit <referentie.json>
    uv run python -I eval/extern_bibliotheek.py vergelijk --referentie <referentie.json> --werkgebied <werkgebied.json> \\
        --begrippen <begrip_lezen.json> [--regels <map met regels>] --afkortingen <afkortingen.json> [--uit <rapport>]
    uv run python -I eval/extern_bibliotheek.py manifest --naam <naam> <map …> --uit <manifest.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.padcontrole import veilig_pad  # noqa: E402
from eval.extern_dossier import (  # noqa: E402
    Knoop,
    _cellen,
    _iri_past,
    _iris,
    _rijen,
    _schoon,
    boom,
    bron_uit,
    klasse_van,
)
from eval.scoring import _norm, _token_iou  # noqa: E402

SCHEMA = "extern-bibliotheek-v1"

# --- Velden ---------------------------------------------------------------------------------------------------

# De rijkoppen van een veldtabel, naar een vaste sleutel. Onbekende koppen komen onder `overig`, niet stil weg.
VELDEN: dict[str, str] = {
    "begripsnaam": "naam",
    "begrip": "naam",
    "begripsdefinitie": "definitie",
    "definitie": "definitie",
    "afleidingsregel": "regeltekst",
    "eigenaar": "eigenaar",
    "formulering uit primaire juridische bron": "bron",
    "formulering uit de primaire juridische bron": "bron",
    "klasse": "klasse",
    "waarde": "waarde",
    "interpretatie": "interpretatie",
    "gerelateerde begrippen": "gerelateerd",
    "opmerkingen": "opmerkingen",
    "status": "status",
    "status begrip": "status",
}

_PAGINA_ID = (re.compile(r"\.(\d{5,})\.html"), re.compile(r"/pages/(\d{5,})(?:/|$)"))
_DOORHALING = {"s", "del", "strike"}
_BEPAAL = re.compile(r"^\s*bepa{1,2}l(?:en)?\s+(?:of\s+)?(?:van\s+(?:de|het)\s+)?", re.I)


def pagina_id(href: str) -> str:
    """Het id van een wikipagina uit een link: de export noemt een pagina `<naam>.<id>.html`, een link naar de wiki
    `…/pages/<id>/<naam>`. Geen id → ""."""
    href = unquote(href or "")
    for patroon in _PAGINA_ID:
        if m := patroon.search(href):
            return m.group(1)
    return ""


def _tekst(k: Knoop | str, br: str = "\n") -> str:
    """De tekst van een knoop zonder doorgehaalde delen: een doorhaling is in zo'n wiki een vervallen keuze."""
    if isinstance(k, str):
        return k
    if k.tag in _DOORHALING:
        return ""
    if k.tag == "br":
        return br
    blok = k.tag in ("p", "li", "div")
    tekst = "".join(_tekst(c, br) for c in k.kinderen)
    return f"{tekst}{br}" if blok else tekst


def _regels_van(k: Knoop) -> list[str]:
    return [r for r in (_schoon(x) for x in _tekst(k).split("\n")) if r]


def _links(k: Knoop) -> list[tuple[str, str]]:
    """(tekst, href) van elke link die niet doorgehaald is."""
    uit: list[tuple[str, str]] = []

    def loop(n: Knoop) -> None:
        for c in n.kinderen:
            if isinstance(c, Knoop) and c.tag not in _DOORHALING:
                if c.tag == "a":
                    uit.append((_schoon(_tekst(c, " ")), c.attrs.get("href", "")))
                else:
                    loop(c)

    loop(k)
    return uit


def _hoofdinhoud(wortel: Knoop) -> Knoop:
    for d in wortel.alle("div"):
        if d.attrs.get("id") == "main-content":
            return d
    return wortel


def _veldtabel(tabel: Knoop) -> dict[str, Knoop]:
    """Een tabel met twee kolommen, kop links: {sleutel: waardecel}. De eerste rij kan in `thead` staan."""
    velden: dict[str, Knoop] = {}
    for rij in _rijen(tabel):
        cellen = _cellen(rij)
        if len(cellen) != 2:
            continue
        kop = _schoon(_tekst(cellen[0], " ")).lower().rstrip(":")
        velden.setdefault(VELDEN.get(kop, f"overig:{kop}"), cellen[1])
    return velden


def _is_voorbeeldtabel(tabel: Knoop) -> bool:
    rijen = _rijen(tabel)
    return bool(rijen) and _schoon(_tekst(_cellen(rijen[0])[0], " ")).lower().startswith("voorbeeld") \
        if rijen and _cellen(rijen[0]) else False


def _oordeel(waarde: str) -> str:
    w = waarde.lower()
    if w.startswith("ja"):
        return "ja"
    if w.startswith("nee"):
        return "nee"
    if w.startswith(("nvt", "n.v.t")):
        return "nvt"
    return "leeg" if not w else "anders"


def lees_voorbeelden(tabel: Knoop) -> dict[str, Any]:
    """Een voorbeeldtabel: kolommen zijn gevallen, rijen eerst de invoer, dan "is invoer juist?", de uitvoer en "is de
    voorspelling juridisch juist?". Alleen de vorm en de oordelen; de waarden blijven in het schema voor wie ze lokaal
    wil narekenen."""
    rijen = _rijen(tabel)
    kop = [_schoon(_tekst(c, " ")) for c in _cellen(rijen[0])]
    n = max(0, len(kop) - 1)
    deel = ""
    invoer: list[dict[str, Any]] = []
    uitvoer: list[dict[str, Any]] = []
    oordeel_invoer: list[str] = []
    oordeel_uitvoer: list[str] = []
    for rij in rijen[1:]:
        cellen = [_schoon(_tekst(c, " ")) for c in _cellen(rij)]
        if not cellen:
            continue
        label, waarden = cellen[0], cellen[1:]
        laag = label.lower()
        if laag.startswith("invoer"):
            deel = "invoer"
        elif laag.startswith("uitvoer"):
            deel = "uitvoer"
        elif "invoer" in laag and "juist" in laag:
            oordeel_invoer = [_oordeel(w) for w in waarden]
        elif "juist" in laag:
            oordeel_uitvoer = [_oordeel(w) for w in waarden]
        elif deel:
            (invoer if deel == "invoer" else uitvoer).append({"begrip": label, "waarden": waarden})
    return {"gevallen": n, "invoer": invoer, "uitvoer": uitvoer,
            "oordeel_invoer": dict(Counter(oordeel_invoer)), "oordeel_uitvoer": dict(Counter(oordeel_uitvoer))}


def _bronnen(cel: Knoop) -> list[dict[str, str]]:
    """De bepalingen in het bronveld: elke link naar wetten.overheid.nl, met het lid uit de tekst als het er staat."""
    uit = []
    regels = _regels_van(cel)
    for tekst, href in _links(cel):
        if "BWBR" not in href:
            continue
        b = bron_uit(href, tekst)
        if not b["lid"]:
            # "lid 5. De eerste termijn …" of "Lid 1 Een belastingaanslag …" op een volgende regel.
            for r in regels:
                if m := re.match(r"\s*lid\s+(\d+\w?)\b", r, re.I):
                    b = {**b, "lid": m.group(1)}
                    break
        uit.append(b)
    return uit


def lees_pagina(html: str, bestand: str = "") -> dict[str, Any] | None:
    """Eén begrip- of regelpagina. Een pagina zonder veldtabel met een naam (een index, een zoekpagina) → None."""
    wortel = boom(html)
    inhoud = _hoofdinhoud(wortel)
    tabellen = inhoud.alle("table")
    velden: dict[str, Knoop] = {}
    voorbeelden = None
    for t in tabellen:
        if _is_voorbeeldtabel(t):
            voorbeelden = voorbeelden or lees_voorbeelden(t)
        elif not velden:
            v = _veldtabel(t)
            if "naam" in v:
                velden = v
    if not velden:
        return None
    naam = _schoon(_tekst(velden["naam"], " "))
    klasse = _schoon(_tekst(velden["klasse"], " ")) if "klasse" in velden else ""
    soort = "regel" if "regeltekst" in velden or klasse.lower() == "afleidingsregel" else "begrip"
    trajecten = []
    for p in inhoud.kind("p"):
        if _schoon(_tekst(p, " ")).lower().startswith("gebruikt in"):
            trajecten = [t for t, _ in _links(p) if t]
    tekstveld = "regeltekst" if soort == "regel" else "definitie"
    verwijzingen = []
    if tekstveld in velden:
        verwijzingen = _uniek([{"naam": t, "id": pagina_id(h)} for t, h in _links(velden[tekstveld])
                               if pagina_id(h)])
    gerelateerd = [{"naam": t, "id": pagina_id(h)} for t, h in _links(velden["gerelateerd"])] \
        if "gerelateerd" in velden else []
    pagina = {
        "id": pagina_id(bestand),
        "soort": soort,
        "naam": naam,
        "trajecten": trajecten,
        "tekst": "\n".join(_regels_van(velden[tekstveld])) if tekstveld in velden else "",
        "klasse": klasse,
        "waarde": _schoon(_tekst(velden["waarde"], " ")) if "waarde" in velden else "",
        "bron": _bronnen(velden["bron"]) if "bron" in velden else [],
        "verwijzingen": verwijzingen,
        "gerelateerd": gerelateerd,
        "interpretatie": bool("interpretatie" in velden and _regels_van(velden["interpretatie"])),
        "opmerkingen": bool("opmerkingen" in velden and _regels_van(velden["opmerkingen"])),
        "status": _schoon(_tekst(velden["status"], " ")) if "status" in velden else "",
        "voorbeelden": voorbeelden,
    }
    if soort == "regel":
        pagina["uitvoer"] = _BEPAAL.sub("", naam).strip()
    return pagina


# --- Het werkbestand ------------------------------------------------------------------------------------------

_VINDPLAATS = re.compile(
    r"^\s*(?P<afk>[^,]+?),\s*art(?:ikel)?\.?\s*(?P<art>[\w:]+(?:\.[\w:]+)*?)\.?"
    r"(?:\s+lid\s+(?P<lid>\d+\w?))?(?:\s+alinea\s+(?P<alinea>\d+))?\s*\.?\s*$", re.I)


def vindplaats_uit(tekst: str) -> dict[str, str] | None:
    """"IW, Art. 9 lid 5" → {afkorting, artikel, lid, alinea}. Een regel die niet zo begint → None."""
    m = _VINDPLAATS.match(tekst or "")
    if not m:
        return None
    return {"afkorting": m.group("afk").strip(), "artikel": m.group("art").rstrip("."), "lid": m.group("lid") or "",
            "alinea": m.group("alinea") or ""}


def _uniek(namen: list[dict[str, str]]) -> list[dict[str, str]]:
    """Dezelfde naam met hetzelfde id één keer, in volgorde."""
    gezien: set[tuple[str, str]] = set()
    uit = []
    for n in namen:
        sleutel = (_norm(n["naam"]), n["id"])
        if sleutel not in gezien:
            gezien.add(sleutel)
            uit.append(n)
    return uit


def _koppel(n: int, waarden: list[Any]) -> list[list[Any]]:
    """Wat bij fragment i hoort: één waarde voor alle, of per index als de aantallen gelijk zijn; anders alles (en de
    koppeling is dan dubbelzinnig)."""
    if len(waarden) == 1:
        return [waarden] * n
    if len(waarden) == n:
        return [[w] for w in waarden]
    return [waarden] * n


def lees_werkbestand(html: str) -> list[dict[str, Any]]:
    """De tabellen "Klasse | Gemarkeerde tekst | Wet | Begripsnaam | …": per formulering de klasse, de tekst, de
    vindplaats en het begrip. Doorgehaalde rijen en regels vallen weg."""
    uit: list[dict[str, Any]] = []
    for tabel in _hoofdinhoud(boom(html)).alle("table"):
        rijen = _rijen(tabel)
        if not rijen:
            continue
        kop = [_schoon(_tekst(c, " ")).lower() for c in _cellen(rijen[0])]
        if len(kop) < 4 or kop[0] != "klasse" or "begrip" not in kop[3]:
            continue
        for rij in rijen[1:]:
            cellen = _cellen(rij)
            if len(cellen) < 4:
                continue
            klasregels = _regels_van(cellen[0])
            if not klasregels:
                continue  # geheel doorgehaald
            klassen = sorted({k for deel in re.split(r"[/,]", klasregels[0]) if (k := klasse_van(deel.strip()))})
            fragmenten = _regels_van(cellen[1])
            plekken = [p for r in _regels_van(cellen[2]) if (p := vindplaats_uit(r))]
            namen = _uniek([{"naam": t, "id": pagina_id(h)} for t, h in _links(cellen[3]) if t])
            if not namen:
                namen = [{"naam": r, "id": ""} for r in _regels_van(cellen[3])]
            if not fragmenten:
                continue
            per_plek = _koppel(len(fragmenten), plekken) if plekken else [[]] * len(fragmenten)
            per_naam = _koppel(len(fragmenten), namen) if namen else [[]] * len(fragmenten)
            for frag, pl, nm in zip(fragmenten, per_plek, per_naam, strict=True):
                tekst = re.sub(r"\s*\(\d+\s*x\)\s*$", "", frag)
                uit.append({"klasse": klassen, "tekst": tekst, "vindplaatsen": pl, "begrippen": nm,
                            "dubbelzinnig": len(pl) > 1 or len(nm) > 1})
    return uit


def lees_bibliotheek(begrippen: list[Path], regels: list[Path], werkbestand: list[Path] | None = None,
                     traject: str = "") -> dict[str, Any]:
    """De referentie: begrippen en regels (alleen die van het traject, als er een is gegeven) en de formuleringen."""
    def lees(paden: list[Path], soort: str) -> list[dict[str, Any]]:
        uit = []
        for p in paden:
            pg = lees_pagina(p.read_text(encoding="utf-8", errors="replace"), p.name)
            if pg and pg["soort"] == soort and (not traject or any(traject.lower() in t.lower()
                                                                   for t in pg["trajecten"])):
                uit.append(pg)
        return uit

    formuleringen = [f for p in werkbestand or [] for f in lees_werkbestand(p.read_text(encoding="utf-8",
                                                                                       errors="replace"))]
    return {"schema": SCHEMA, "traject": traject, "begrippen": lees(begrippen, "begrip"),
            "regels": lees(regels, "regel"), "formuleringen": formuleringen}


# --- Vergelijken ----------------------------------------------------------------------------------------------

def _sleutel(naam: str) -> str:
    return re.sub(r"[^\w ]", "", _norm(naam)).strip()


def _past_tekst(fragment: str, element: str) -> bool:
    """Dezelfde formulering: gelijk, of grotendeels dezelfde woorden. Een element dat het fragment alleen bevat (de hele
    normzin om "de dagtekening" heen) is een andere formulering, en het begrip daarop een ander begrip."""
    nf, ne = _norm(fragment), _norm(element)
    if not nf or not ne:
        return False
    if nf == ne or _token_iou(fragment, element) >= 0.5:
        return True
    korter, langer = sorted((nf, ne), key=len)
    return korter in langer and len(korter) >= 0.6 * len(langer)


def _bron_van(plek: dict[str, str], afkortingen: dict[str, str]) -> dict[str, str] | None:
    bwb = afkortingen.get(plek["afkorting"]) or afkortingen.get(plek["afkorting"].rstrip("."))
    return {"bwb_id": bwb, "artikel": plek["artikel"], "lid": plek["lid"]} if bwb else None


def _platform(werkgebied: Any, begrippen: Any) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]],
                                                          dict[str, set[str]]]:
    """De elementen, de begrippen (id → begrip) en per element de begrippen die erop rusten."""
    data = werkgebied.get("data", werkgebied) if isinstance(werkgebied, dict) else werkgebied
    el = data.get("elementen", data) if isinstance(data, dict) else data
    elementen = el.get("elementen", []) if isinstance(el, dict) else el
    b = begrippen.get("data", begrippen)
    lijst = b.get("begrippen", [])
    lijst = lijst.get("begrippen", []) if isinstance(lijst, dict) else lijst
    per_id = {x["id"]: x for x in lijst if x.get("status") != "vervangen"}
    op_element: dict[str, set[str]] = {}
    for k in (b.get("samenhang") or {}).get("koppelingen", []):
        # Alleen de passages die het begrip dragen; een passage als context draagt het niet.
        if k.get("beoordeling") != "afgewezen" and k.get("rol") != "context" and k.get("begrip_id") in per_id:
            op_element.setdefault(k["element_id"], set()).add(k["begrip_id"])
    return [e for e in elementen if e.get("lifecycle") != "rejected"], per_id, op_element


def _naam_van(b: dict[str, Any]) -> str:
    return (b.get("inhoud") or {}).get("naam") or b.get("naam", "")


def _regelbegrippen(per_id: dict[str, dict[str, Any]], regels: list[Any] | None) -> set[str]:
    """De begrippen die een regel benoemen ("bepalen …"): uit de regels, en anders aan hun naam. Ze dragen een regel,
    niet de betekenis van een formulering, en tellen bij de begrippen niet mee."""
    ids = {(r.get("data", r).get("inhoud") or {}).get("regelbegrip_id", "") for r in regels or []}
    return {b for b in per_id if b in ids or _BEPAAL.match(_naam_van(per_id[b]))}


def vergelijk_begrippen(referentie: dict[str, Any], werkgebied: Any, begrippen: Any,
                        afkortingen: dict[str, str], regels: list[Any] | None = None) -> dict[str, Any]:
    elementen, per_id, op_element = _platform(werkgebied, begrippen)
    regelbegrippen = _regelbegrippen(per_id, regels)
    per_id = {b: x for b, x in per_id.items() if b not in regelbegrippen}
    op_element = {e: bs - regelbegrippen for e, bs in op_element.items()}
    namen_lex: dict[str, set[str]] = {}
    for bid, b in per_id.items():
        namen_lex.setdefault(_sleutel(_naam_van(b)), set()).add(bid)

    # Per referentiebegrip: de formuleringen, de elementen op die plek, en de begrippen daarop.
    per_ref: dict[str, dict[str, Any]] = {}
    for f in referentie.get("formuleringen", []):
        for nm in f["begrippen"]:
            r = per_ref.setdefault(_sleutel(nm["naam"]), {"formuleringen": 0, "elementen": set(), "lex": set(),
                                                          "stemmen": Counter()})
            r["formuleringen"] += 1
            for plek in f["vindplaatsen"]:
                bron = _bron_van(plek, afkortingen)
                if not bron:
                    continue
                for e in elementen:
                    if any(_iri_past(i, bron) for i in _iris(e) if i) and _past_tekst(f["tekst"], e.get("tekst", "")):
                        r["elementen"].add(e["id"])
                        r["lex"] |= op_element.get(e["id"], set())
                        r["stemmen"].update(op_element.get(e["id"], set()))
    gedeeld = Counter(bid for r in per_ref.values() for bid in r["lex"])

    uitkomsten: list[dict[str, Any]] = []
    for b in referentie.get("begrippen", []):
        s = _sleutel(b["naam"])
        r = per_ref.get(s)
        op_naam = sorted(namen_lex.get(s, set()))
        if r and r["formuleringen"]:
            if not r["elementen"]:
                uitkomst = "niet_gemarkeerd"
            elif not r["lex"]:
                uitkomst = "zonder_begrip"
            elif len(r["lex"]) == 1 and gedeeld[next(iter(r["lex"]))] == 1:
                uitkomst = "gedekt"
            else:
                uitkomst = "anders_gesneden"
            lex = sorted(r["lex"])
            beste = [b for b, _ in r["stemmen"].most_common(1)]
        else:
            uitkomst = "alleen_op_naam" if op_naam else "ontbreekt"
            lex = op_naam
            beste = op_naam[:1]
        uitkomsten.append({"beste": beste, "referentie": b["id"], "naam": b["naam"], "klasse": b["klasse"], "waarde": b["waarde"],
                           "uitkomst": uitkomst, "lex": lex, "lex_namen": [_naam_van(per_id[x]) for x in lex]})
    gekoppeld = {x for u in uitkomsten for x in u["lex"]}
    return {
        "telling": dict(Counter(u["uitkomst"] for u in uitkomsten)),
        "per_klasse": {k: dict(Counter(u["uitkomst"] for u in uitkomsten if (u["klasse"] or "(leeg)").lower() == k))
                       for k in sorted({(u["klasse"] or "(leeg)").lower() for u in uitkomsten})},
        "ja_nee": dict(Counter(u["uitkomst"] for u in uitkomsten if u["waarde"].lower() == "boolean")),
        "alleen_in_lex": sorted(_naam_van(per_id[x]) for x in per_id if x not in gekoppeld),
        "regelbegrippen": len(regelbegrippen),
        "begrippen": uitkomsten,
    }


def _lex_regels(regels: list[Any]) -> list[dict[str, Any]]:
    uit = []
    for r in regels:
        r = r.get("data", r)
        if r.get("status") == "vervangen":
            continue
        inhoud = r.get("inhoud") or {}
        uit.append({"id": r["id"], "naam": r.get("naam", ""), "uitvoer": r.get("uitvoer", ""),
                    "uitvoer_begrip_id": inhoud.get("uitvoer_begrip_id", ""),
                    "invoer": [i["begrip_id"] for i in inhoud.get("invoer", [])]})
    return uit


def vergelijk_regels(referentie: dict[str, Any], begrippen_rapport: dict[str, Any],
                     regels: list[Any]) -> dict[str, Any]:
    """Per referentieregel: is er een regel in het werkgebied met dezelfde uitvoer (via het gekoppelde begrip), en
    hoeveel van de invoerbegrippen komen overeen."""
    lex = _lex_regels(regels)
    per_naam = {_sleutel(u["naam"]): u for u in begrippen_rapport["begrippen"]}
    per_id = {b["id"]: b for b in referentie.get("begrippen", [])}
    uitkomsten = []
    gebruikt: set[str] = set()
    for r in referentie.get("regels", []):
        uit_ref = per_naam.get(_sleutel(r["uitvoer"]))
        lex_uit = set(uit_ref["beste"]) if uit_ref else set()
        # Eerst op de naam van de uitvoer: alle woorden van de uitvoer in het werkgebied staan in die van de
        # referentie ("termijnbedrag" in "termijnbedrag van de aanslag"). Anders via het begrip dat de meeste
        # formuleringen van de referentie-uitvoer draagt: dan is de regel er, maar anders gesneden.
        ref_woorden = set(_sleutel(r["uitvoer"]).split())
        treffers = [x for x in lex if (w := set(_sleutel(x["uitvoer"]).split())) and w <= ref_woorden]
        via = "naam"
        if not treffers:
            treffers = [x for x in lex if x["uitvoer_begrip_id"] in lex_uit]
            via = "begrip"
        invoer_ref = [v for v in r["verwijzingen"] if _sleutel(v["naam"]) != _sleutel(r["uitvoer"])]
        invoer_lex = {i for x in treffers for i in x["invoer"]}
        overeen = 0
        for v in invoer_ref:
            ref_b = per_id.get(v["id"]) or {"naam": v["naam"]}
            u = per_naam.get(_sleutel(ref_b["naam"]))
            if u and set(u["beste"]) & invoer_lex:
                overeen += 1
        gebruikt |= {x["id"] for x in treffers}
        uitkomst = ("gevonden" if via == "naam" else "anders_gesneden") if treffers else "ontbreekt"
        uitkomsten.append({"referentie": r["id"], "naam": r["naam"], "uitkomst": uitkomst,
                           "lex": [x["naam"] for x in treffers], "invoer_referentie": len(invoer_ref),
                           "invoer_overeen": overeen, "gevallen_referentie": _gevallen(r["tekst"])})
    return {"telling": dict(Counter(u["uitkomst"] for u in uitkomsten)),
            "alleen_in_lex": sorted(x["naam"] for x in lex if x["id"] not in gebruikt),
            "regels": uitkomsten}


_KOP = re.compile(r"\b(?:wordt|worden)\s+(?:berekend|gesteld|bepaald)\b|\bis\s+(?:een|een\s+\w+)\s.*?\bindien\b", re.I)


def _gevallen(tekst: str) -> int:
    """Hoeveel gevallen een regeltekst heeft: elke kop "wordt berekend als / wordt gesteld op / … indien"."""
    return max(1, sum(1 for r in tekst.split("\n") if _KOP.search(r)))


def vorm(referentie: dict[str, Any]) -> dict[str, Any]:
    """De vorm van de referentie, zonder inhoud: hoe groot zijn regels, hoeveel begrippen zijn ja/nee of afgeleid."""
    regels = referentie.get("regels", [])
    begrippen = referentie.get("begrippen", [])
    return {
        "begrippen": len(begrippen),
        "regels": len(regels),
        "formuleringen": len(referentie.get("formuleringen", [])),
        "klassen": dict(Counter((b["klasse"] or "(leeg)").lower() for b in begrippen)),
        "met_waarde": sum(1 for b in begrippen if b["waarde"]),
        "ja_nee": sum(1 for b in begrippen if b["waarde"].lower() == "boolean"),
        "met_bron": sum(1 for b in begrippen if b["bron"]),
        "met_interpretatie": sum(1 for b in begrippen if b["interpretatie"]),
        "regels_per_gevallen": dict(Counter(_gevallen(r["tekst"]) for r in regels)),
        "regels_met_voorbeelden": sum(1 for r in regels if r["voorbeelden"]),
        "voorbeeldgevallen": sum((r["voorbeelden"] or {}).get("gevallen", 0) for r in regels),
        "invoer_per_regel": dict(Counter(len({v["id"] for v in r["verwijzingen"]}) for r in regels)),
    }


def vergelijk(referentie: dict[str, Any], werkgebied: Any, begrippen: Any, regels: list[Any] | None,
              afkortingen: dict[str, str]) -> dict[str, Any]:
    b = vergelijk_begrippen(referentie, werkgebied, begrippen, afkortingen, regels)
    rapport = {"schema": f"{SCHEMA}-rapport", "vorm": vorm(referentie), "begrippen": b}
    if regels is not None:
        rapport["regels"] = vergelijk_regels(referentie, b, regels)
    return rapport


def manifest(naam: str, mappen: list[Path]) -> dict[str, Any]:
    """Een manifest zonder inhoud: per map het aantal HTML-pagina's en de gesorteerde hashes, en één hash over alles.
    Geen bestandsnamen: die dragen de namen van begrippen en regels."""
    delen = []
    for m in mappen:
        hashes = sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(m.glob("*.html")))
        delen.append({"paginas": len(hashes), "sha256": hashlib.sha256("\n".join(hashes).encode()).hexdigest()})
    alles = hashlib.sha256("".join(d["sha256"] for d in delen).encode()).hexdigest()
    return {"naam": naam, "schema": SCHEMA, "delen": delen, "sha256": alles}


def _print(r: dict[str, Any]) -> None:
    v = r["vorm"]
    print(f"Referentie: {v['begrippen']} begrippen, {v['regels']} regels, {v['formuleringen']} formuleringen")
    print(f"  ja/nee {v['ja_nee']}, met waarde {v['met_waarde']}, regels per aantal gevallen {v['regels_per_gevallen']}")
    print(f"Begrippen: {r['begrippen']['telling']}  (ja/nee: {r['begrippen']['ja_nee']})")
    print(f"  alleen in het werkgebied: {len(r['begrippen']['alleen_in_lex'])}")
    if "regels" in r:
        g = r["regels"]
        print(f"Regels: {g['telling']}; alleen in het werkgebied: {len(g['alleen_in_lex'])}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Een begrippen- en regelbibliotheek inlezen en vergelijken met Lex")
    sub = ap.add_subparsers(dest="actie", required=True)
    lees = sub.add_parser("lees")
    lees.add_argument("--begrippen", type=Path, required=True, help="map met de begrippagina's")
    lees.add_argument("--regels", type=Path, required=True, help="map met de regelpagina's")
    lees.add_argument("--werkbestand", type=Path, nargs="*", help="de pagina('s) met het werkbestand van activiteit 3")
    lees.add_argument("--traject", default="", help="alleen begrippen en regels van dit traject")
    lees.add_argument("--uit", type=Path, required=True)
    verg = sub.add_parser("vergelijk")
    verg.add_argument("--referentie", type=Path, required=True)
    verg.add_argument("--werkgebied", type=Path, required=True, help="werkgebied_lezen met volledig: true")
    verg.add_argument("--begrippen", type=Path, required=True, help="begrip_lezen zonder begrip_id")
    verg.add_argument("--regels", type=Path, help="map met de regels (GET …/regels/{id}), één JSON per regel")
    verg.add_argument("--afkortingen", type=Path, required=True, help="JSON {afkorting in het werkbestand: BWB-id}")
    verg.add_argument("--uit", type=Path)
    man = sub.add_parser("manifest")
    man.add_argument("--naam", required=True)
    man.add_argument("mappen", type=Path, nargs="+")
    man.add_argument("--uit", type=Path, required=True)
    args = ap.parse_args(argv)

    def laad(p: Path) -> Any:
        return json.loads(veilig_pad(p).read_text(encoding="utf-8"))

    if args.actie == "lees":
        ref = lees_bibliotheek(sorted(args.begrippen.glob("*.html")), sorted(args.regels.glob("*.html")),
                               args.werkbestand, args.traject)
        veilig_pad(args.uit).write_text(json.dumps(ref, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(ref['begrippen'])} begrippen, {len(ref['regels'])} regels, "
              f"{len(ref['formuleringen'])} formuleringen")
        return
    if args.actie == "manifest":
<<<<<<< HEAD
        args.uit.write_text(json.dumps(manifest(args.naam, args.mappen), indent=2) + "\n", encoding="utf-8")
        return
=======
        veilig_pad(args.uit).write_text(json.dumps(manifest(args.naam, args.mappen), indent=2) + "\n", encoding="utf-8")
        return 0
>>>>>>> origin/claude/charming-roentgen-32c691
    regels = [laad(p) for p in sorted(args.regels.glob("*.json"))] if args.regels else None
    rapport = vergelijk(laad(args.referentie), laad(args.werkgebied), laad(args.begrippen), regels,
                        laad(args.afkortingen))
    if args.uit:
        veilig_pad(args.uit).write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    _print(rapport)


if __name__ == "__main__":
    sys.exit(main())
