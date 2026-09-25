"""Blind annoteren vergelijken en adjudiceren (adjudicatieprotocol v1, validatieplan V2).

Twee juristen annoteren elk blind via het formulier (`scripts/blind_formulier.py`); dat levert per
annotator per casus een JSON op. Deze module doet §11 stap 3 t/m 5:

- **vergelijken** op positie → een verschillenlijst (gelijk, klasse, span, alleen_a, alleen_b),
  het aandeel gelijk op positie en Cohen's κ op de klasse bij gelijke positie;
- **adjudiceren**: de besluiten van de adjudicator toepassen en er gold-elementen volgens §10.4 van
  maken, met per element het verschil en het besluit.

Het systeem is nooit annotator: niets hier leest systeemoutput, en de uitkomst is alleen afgeleid
uit wat A, B en de adjudicator vastlegden.

    python -m eval.adjudicatie vergelijk a.json b.json [--md verschillen.md] [--json verschillen.json]
    python -m eval.adjudicatie besluit a.json b.json besluiten.json --adjudicator C --datum 2026-10-01
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent.jas_klassen import GELDIGE_JAS_KLASSEN
from eval.referentieset import (
    BESLUITEN, SOURCE_STATUS, ReferentieFout, _keuze, _span, _velden, casussen,
)

PROTOCOLVERSIE = "1"
ANNOTATIE_VERPLICHT = ("protocolversie", "annotator", "casus_id", "tekst_sha256", "source_status",
                       "elementen", "negatief")
ANNOTATIE_OPTIONEEL = ("opmerking",)
ELEMENT_VERPLICHT = ("start", "eind", "tekst", "klasse", "motivatie", "herkenningsvraag", "h2_ref")
ELEMENT_OPTIONEEL = ("subtype", "context", "relaties")
# "geen" levert geen gold-element op; daarom staat het niet in referentieset.BESLUITEN.
BESLUITEN_ADJUDICATOR = tuple(b for b in BESLUITEN if b != "gelijk") + ("geen",)


# --- annotatorbestand ---------------------------------------------------------------------------

def valideer_annotatie(ann: dict[str, Any], casus: dict[str, Any]) -> None:
    """Eén annotatorbestand tegen zijn casus: dezelfde tekst, letterlijke spans, bestaande klassen."""
    waar = f"{ann.get('annotator', '?')}/{ann.get('casus_id', '?')}"
    _velden(waar, ann, ANNOTATIE_VERPLICHT, ANNOTATIE_OPTIONEEL)
    if ann["casus_id"] != casus["id"] or ann["tekst_sha256"] != casus["tekst_sha256"]:
        raise ReferentieFout(f"{waar}: hoort niet bij casus {casus['id']} of bij een andere tekstversie")
    if ann["protocolversie"] != PROTOCOLVERSIE:
        raise ReferentieFout(f"{waar}: protocolversie {ann['protocolversie']!r}, verwacht {PROTOCOLVERSIE}")
    if not ann["annotator"]:
        raise ReferentieFout(f"{waar}: annotator ontbreekt")
    _keuze(f"{waar}.source_status", ann["source_status"], SOURCE_STATUS)
    for i, e in enumerate(ann["elementen"]):
        ew = f"{waar}/elementen[{i}]"
        _velden(ew, e, ELEMENT_VERPLICHT, ELEMENT_OPTIONEEL)
        _span(ew, casus["tekst"], e)
        _keuze(f"{ew}.klasse", e["klasse"], tuple(GELDIGE_JAS_KLASSEN))
    for i, n in enumerate(ann["negatief"]):
        _span(f"{waar}/negatief[{i}]", casus["tekst"], n)


# --- vergelijken (§11 stap 3) -------------------------------------------------------------------

@dataclass(frozen=True)
class Verschil:
    id: str
    soort: str                      # gelijk | klasse | span | alleen_a | alleen_b
    a: int | None                   # index in A.elementen
    b: int | None                   # index in B.elementen
    start: int
    eind: int
    tekst: str
    klasse_a: str | None
    klasse_b: str | None


def _overlap(x: dict[str, Any], y: dict[str, Any]) -> bool:
    return x["start"] < y["eind"] and y["start"] < x["eind"]


def vergelijk(a: dict[str, Any], b: dict[str, Any], tekst: str) -> list[Verschil]:
    """Koppel A en B op positie, in drie rondes van streng naar los.

    1. zelfde span én klasse → `gelijk`;
    2. zelfde span, andere klasse → `klasse`;
    3. overlappende span, zelfde klasse → `span`.

    Wat daarna overblijft is `alleen_a`/`alleen_b`. Twee elementen die zowel in span als in klasse
    verschillen, zijn twee losse lezingen en worden dus niet gekoppeld: de adjudicator beslist ze
    elk apart.
    """
    ea, eb = a["elementen"], b["elementen"]
    vrij_a, vrij_b = set(range(len(ea))), set(range(len(eb)))
    paren: list[tuple[str, int, int]] = []

    def ronde(soort: str, past) -> None:
        for i in sorted(vrij_a, key=lambda i: (ea[i]["start"], ea[i]["eind"], ea[i]["klasse"])):
            kandidaten = [j for j in sorted(vrij_b, key=lambda j: (eb[j]["start"], eb[j]["eind"], eb[j]["klasse"]))
                          if past(ea[i], eb[j])]
            if kandidaten:
                vrij_a.discard(i)
                vrij_b.discard(kandidaten[0])
                paren.append((soort, i, kandidaten[0]))

    zelfde_span = lambda x, y: (x["start"], x["eind"]) == (y["start"], y["eind"])  # noqa: E731
    ronde("gelijk", lambda x, y: zelfde_span(x, y) and x["klasse"] == y["klasse"])
    ronde("klasse", zelfde_span)
    ronde("span", lambda x, y: _overlap(x, y) and x["klasse"] == y["klasse"])

    rijen: list[tuple[str, int | None, int | None]] = [*paren, *(("alleen_a", i, None) for i in vrij_a),
                                                       *(("alleen_b", None, j) for j in vrij_b)]

    def positie(r: tuple[str, int | None, int | None]) -> tuple[int, int]:
        e = ea[r[1]] if r[1] is not None else eb[r[2]]
        return e["start"], e["eind"]

    uit = []
    for n, (soort, i, j) in enumerate(sorted(rijen, key=lambda r: (*positie(r), r[0])), 1):
        # Bij een spanverschil toont de rij de vereniging, zodat de adjudicator beide lezingen ziet.
        s = min(ea[i]["start"] if i is not None else 10**9, eb[j]["start"] if j is not None else 10**9)
        t = max(ea[i]["eind"] if i is not None else -1, eb[j]["eind"] if j is not None else -1)
        uit.append(Verschil(f"V{n:02d}", soort, i, j, s, t, tekst[s:t],
                            ea[i]["klasse"] if i is not None else None, eb[j]["klasse"] if j is not None else None))
    return uit


def overeenstemming(verschillen: list[Verschil]) -> dict[str, Any]:
    """§11 stap 5: aandeel gelijk op positie, en Cohen's κ op de klasse bij gelijke positie.

    Positie-overeenstemming = gekoppelde paren met dezelfde span / alle rijen (Jaccard op posities).
    κ wordt alleen berekend over paren met dezelfde span (`gelijk` + `klasse`); met minder dan twee
    paren of zonder variatie in de verwachte overeenstemming is hij niet gedefinieerd (`None`).
    """
    n = len(verschillen)
    zelfde_plek = [v for v in verschillen if v.soort in ("gelijk", "klasse")]
    uit: dict[str, Any] = {"rijen": n, "per_soort": dict(Counter(v.soort for v in verschillen)),
                           "positie_overeenstemming": len(zelfde_plek) / n if n else None,
                           "kappa_klasse": None, "kappa_paren": len(zelfde_plek)}
    if len(zelfde_plek) >= 2:
        po = sum(v.soort == "gelijk" for v in zelfde_plek) / len(zelfde_plek)
        ka, kb = Counter(v.klasse_a for v in zelfde_plek), Counter(v.klasse_b for v in zelfde_plek)
        pe = sum(ka[k] * kb[k] for k in ka) / len(zelfde_plek) ** 2
        uit["kappa_klasse"] = None if pe == 1 else (po - pe) / (1 - pe)
    return uit


# --- adjudiceren (§11 stap 4) -------------------------------------------------------------------

def _gold(e: dict[str, Any], status: str, verschil: str, besluit: str) -> dict[str, Any]:
    return {"gid": "", "start": e["start"], "eind": e["eind"], "tekst": e["tekst"], "klasse": e["klasse"],
            "subtype": e.get("subtype"), "context": e.get("context"), "motivatie": e["motivatie"],
            "herkenningsvraag": e["herkenningsvraag"], "h2_ref": e["h2_ref"], "annotation_status": status,
            "relaties": [], "adjudicatie": {"verschil": verschil, "besluit": besluit}}


def adjudiceer(casus: dict[str, Any], a: dict[str, Any], b: dict[str, Any], besluiten: dict[str, Any],
               adjudicator: str, datum: str) -> dict[str, Any]:
    """De casusvelden die de adjudicatie oplevert: `gold`, `negatief`, `source_status`, `adjudicatie`.

    `besluiten` heeft per niet-gelijk verschil-id een `besluit` (kies_a, kies_b, beide, geen,
    debatable), en optioneel `source_status` als A en B daarover verschilden. Een ontbrekend besluit
    is een fout: stilzwijgend "gelijk" aannemen is precies wat adjudicatie moet voorkomen.

    Relaties gaan niet mee; die zijn optioneel en vragen gids die pas hier ontstaan.
    """
    valideer_annotatie(a, casus)
    valideer_annotatie(b, casus)
    if a["annotator"] == b["annotator"]:
        raise ReferentieFout("annotator A en B zijn dezelfde persoon")
    if adjudicator in (a["annotator"], b["annotator"]) and not besluiten.get("gezamenlijk"):
        raise ReferentieFout("adjudicator is ook annotator; leg dat vast met besluiten.gezamenlijk = true (§11)")
    gold: list[dict[str, Any]] = []
    for v in vergelijk(a, b, casus["tekst"]):
        ea = a["elementen"][v.a] if v.a is not None else None
        eb = b["elementen"][v.b] if v.b is not None else None
        if v.soort == "gelijk":
            gold.append(_gold(ea, "correct", "gelijk", "gelijk"))
            continue
        besluit = (besluiten.get("verschillen", {}).get(v.id) or {}).get("besluit")
        if besluit not in BESLUITEN_ADJUDICATOR:
            raise ReferentieFout(f"{v.id} ({v.soort}, {v.tekst!r}): besluit {besluit!r} niet in {BESLUITEN_ADJUDICATOR}")
        if besluit == "kies_a" and ea is None:
            raise ReferentieFout(f"{v.id}: kies_a, maar A heeft hier geen element")
        if besluit == "kies_b" and eb is None:
            raise ReferentieFout(f"{v.id}: kies_b, maar B heeft hier geen element")
        status = "debatable" if besluit == "debatable" else "correct"
        gekozen = {"kies_a": [ea], "kies_b": [eb], "beide": [ea, eb], "debatable": [ea, eb], "geen": []}[besluit]
        gold.extend(_gold(e, status, v.soort, besluit) for e in gekozen if e is not None)
    gold.sort(key=lambda g: (g["start"], g["eind"], g["klasse"]))
    for n, g in enumerate(gold, 1):
        g["gid"] = f"G{n:02d}"

    if a["source_status"] == b["source_status"]:
        source_status = a["source_status"]
    else:
        source_status = besluiten.get("source_status")
        _keuze("besluiten.source_status (A en B verschillen)", source_status, SOURCE_STATUS)

    negatief: dict[tuple[int, int], dict[str, Any]] = {}
    for n in [*a["negatief"], *b["negatief"]]:
        negatief.setdefault((n["start"], n["eind"]), {k: n[k] for k in ("start", "eind", "tekst", "waarom_geen_element")})
    return {"gold": gold, "negatief": sorted(negatief.values(), key=lambda n: (n["start"], n["eind"])),
            "source_status": source_status,
            "adjudicatie": {"annotator_a": a["annotator"], "annotator_b": b["annotator"], "adjudicator": adjudicator,
                            "datum": datum, "protocolversie": PROTOCOLVERSIE}}


# --- rapport ------------------------------------------------------------------------------------

def als_markdown(casus: dict[str, Any], a: dict[str, Any], b: dict[str, Any], verschillen: list[Verschil]) -> str:
    o = overeenstemming(verschillen)
    kappa = "n.v.t." if o["kappa_klasse"] is None else f"{o['kappa_klasse']:.2f}"
    pos = "n.v.t." if o["positie_overeenstemming"] is None else \
        f"{sum(v.soort in ('gelijk', 'klasse') for v in verschillen)}/{o['rijen']}"
    regels = [f"# Verschillen {casus['id']} — {casus['vindplaats']}", "",
              f"A: **{a['annotator']}** · B: **{b['annotator']}** · protocol v{PROTOCOLVERSIE}", "",
              f"Bron: A {a['source_status']}, B {b['source_status']}"
              + ("" if a["source_status"] == b["source_status"] else " — **besluit nodig**"), "",
              f"Gelijk op positie: {pos} · κ klasse bij gelijke positie: {kappa} (n={o['kappa_paren']})", "",
              "| id | soort | fragment | A | B | besluit |", "|---|---|---|---|---|---|"]
    for v in verschillen:
        besluit = "—" if v.soort == "gelijk" else " "
        regels.append(f"| {v.id} | {v.soort} | {v.tekst.replace('|', '/')} | {v.klasse_a or ''} | "
                      f"{v.klasse_b or ''} | {besluit} |")
    return "\n".join(regels) + "\n"


def besluitsjabloon(a: dict[str, Any], b: dict[str, Any], verschillen: list[Verschil]) -> dict[str, Any]:
    """Het in te vullen besluitenbestand: alleen de verschillen die een besluit vragen."""
    uit: dict[str, Any] = {"verschillen": {v.id: {"besluit": None, "motivatie": ""}
                                           for v in verschillen if v.soort != "gelijk"}}
    if a["source_status"] != b["source_status"]:
        uit["source_status"] = None
    return uit


def _laad(pad: str) -> dict[str, Any]:
    return json.loads(Path(pad).read_text(encoding="utf-8"))


def _casus(ann: dict[str, Any]) -> dict[str, Any]:
    alle = {c["id"]: c for c in casussen()}
    if ann.get("casus_id") not in alle:
        raise ReferentieFout(f"onbekende casus {ann.get('casus_id')!r}")
    return alle[ann["casus_id"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="actie", required=True)
    v = sub.add_parser("vergelijk")
    v.add_argument("a")
    v.add_argument("b")
    v.add_argument("--md")
    v.add_argument("--json")
    s = sub.add_parser("besluit")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("besluiten")
    s.add_argument("--adjudicator", required=True)
    s.add_argument("--datum", required=True)
    args = ap.parse_args(argv)

    a, b = _laad(args.a), _laad(args.b)
    casus = _casus(a)
    if args.actie == "vergelijk":
        valideer_annotatie(a, casus)
        valideer_annotatie(b, casus)
        verschillen = vergelijk(a, b, casus["tekst"])
        md = als_markdown(casus, a, b, verschillen)
        if args.md:
            Path(args.md).write_text(md, encoding="utf-8")
        if args.json:
            Path(args.json).write_text(json.dumps(
                {"casus": casus["id"], "overeenstemming": overeenstemming(verschillen),
                 "verschillen": [asdict(x) for x in verschillen], "besluiten": besluitsjabloon(a, b, verschillen)},
                ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sys.stdout.write(md)
        return 0
    uit = adjudiceer(casus, a, b, _laad(args.besluiten), args.adjudicator, args.datum)
    sys.stdout.write(json.dumps(uit, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
