"""Eval van de begrippenketen (ADR-004): referentieset, scorers en een nulmeting.

De referentieset staat in `docs/wetsanalyse/referentieset-begrippen/v<N>/`:

- `bronnen.json`: letterlijke wettekst per bronnode, met `bron_hash` (sha256) en de aanhef van de
  houder (die bepaalt het bereik van een definitie);
- `cases.json`: de formuleringen (ankers in die bronnen) en de paren met hun relatie;
- `manifest.json`: versie, status en een hash over bronnen + cases. Die hash is de identiteit van
  de versie; een bevroren versie verandert niet (zelfde regel als `eval/referentieset.py`).

Relaties in de set: `zelfde_betekenis`, `kwalificatie`, `inclusie`, `uitsluiting`, `hierarchie`
(gericht: van → naar, zoals de hypothese in `begrippen_pipeline.model`), en `verschillend`: een
paar dat er hetzelfde uitziet maar niet hetzelfde begrip is. Dat laatste is de belangrijkste
negatieve test: zo'n paar mag nooit in één groep belanden.

Maten:

- paarsgewijze precisie/recall per relatietype (een symmetrisch paar telt ongeacht volgorde);
- BCubed precisie/recall/F voor de groepen (Amigó e.a. 2009), over alle formuleringen, met
  ongegroepeerde formuleringen als singletons;
- `samengevoegd_verschillend`: hoeveel `verschillend`-paren toch in één groep staan (hoort 0);
- het aandeel groen en geel;
- determinisme: twee runs, identieke uitvoer.

De status van de set is `provisional` totdat een jurist haar adjudiceert; het rapport noemt die
status altijd. Tegen een provisional set heten de cijfers een trendmeting, geen kwaliteitsoordeel.

    python -m eval.begrippen_eval --check
    python -m eval.begrippen_eval --bijwerken          # herbereken de hash (niet-bevroren versie)
    python -m eval.begrippen_eval --variant lemma      # nulmeting zonder taalanalyse
    python -m eval.begrippen_eval --variant keten      # de begrippenketen
    python -m eval.begrippen_eval --variant keten_zonder_parse   # idem, zonder spaCy
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agent.begrippen_pipeline.model import Bron, Formulering, Hypothese, Manifest
from eval.metrieken import GEVALIDEERD, STATUSSEN

ACTUELE_VERSIE = "v1"
WORTEL = Path(__file__).resolve().parents[3] / "docs" / "wetsanalyse" / "referentieset-begrippen"

RELATIES = tuple(h.value for h in Hypothese) + ("verschillend",)
GERICHT = {h.value for h in Hypothese if not h.symmetrisch}
MANIFEST_VELDEN = ("referentie_versie", "referentie_status", "bevroren_op", "sha256", "toelichting")


class ReferentieFout(ValueError):
    pass


# ---------------------------------------------------------------------------------------------
# Laden en valideren
# ---------------------------------------------------------------------------------------------


def versiemap(versie: str = ACTUELE_VERSIE) -> Path:
    return WORTEL / versie


def _lees(versie: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    m = versiemap(versie)
    return (json.loads((m / "bronnen.json").read_text()), json.loads((m / "cases.json").read_text()),
            json.loads((m / "manifest.json").read_text()))


def sethash(bronnen: dict[str, Any], cases: dict[str, Any]) -> str:
    inhoud = json.dumps({"bronnen": bronnen["bronnen"], "cases": cases}, sort_keys=True,
                        ensure_ascii=False)
    return hashlib.sha256(inhoud.encode()).hexdigest()


def valideer(bronnen: dict[str, Any], cases: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Weigert elke vorm van stille afwijking: tekst, anker, id, relatie, status en hash."""
    if set(manifest) != set(MANIFEST_VELDEN):
        raise ReferentieFout(f"manifest-velden {sorted(manifest)} ≠ {sorted(MANIFEST_VELDEN)}")
    if manifest["referentie_status"] not in STATUSSEN:
        raise ReferentieFout(f"onbekende status {manifest['referentie_status']!r}")
    if manifest["referentie_status"] in GEVALIDEERD and not manifest["bevroren_op"]:
        raise ReferentieFout("een gevalideerde status kan alleen in een bevroren versie staan")
    per_iri: dict[str, dict[str, Any]] = {}
    for b in bronnen["bronnen"]:
        if hashlib.sha256(b["tekst"].encode()).hexdigest() != b["bron_hash"]:
            raise ReferentieFout(f"{b['bron_iri']}: bron_hash past niet bij de tekst")
        if b["bron_iri"] in per_iri:
            raise ReferentieFout(f"{b['bron_iri']}: dubbele bron")
        per_iri[b["bron_iri"]] = b
    ids: set[str] = set()
    for f in cases["formuleringen"]:
        b = per_iri.get(f["bron_iri"])
        if b is None:
            raise ReferentieFout(f"{f['element_id']}: onbekende bron {f['bron_iri']}")
        if b["tekst"][f["start"]:f["eind"]] != f["tekst"]:
            raise ReferentieFout(f"{f['element_id']}: staat niet letterlijk op zijn anker")
        if f["element_id"] in ids:
            raise ReferentieFout(f"{f['element_id']}: dubbel")
        ids.add(f["element_id"])
    gezien: set[tuple[str, str, str]] = set()
    for p in cases["paren"]:
        if p["relatie"] not in RELATIES:
            raise ReferentieFout(f"{p['id']}: onbekende relatie {p['relatie']!r}")
        if p["van"] not in ids or p["naar"] not in ids or p["van"] == p["naar"]:
            raise ReferentieFout(f"{p['id']}: leden {p['van']}/{p['naar']} ongeldig")
        if not p.get("motivatie", "").strip():
            raise ReferentieFout(f"{p['id']}: een paar zonder motivatie is een gok")
        sleutel = _sleutel(p["relatie"], p["van"], p["naar"])
        if sleutel in gezien:
            raise ReferentieFout(f"{p['id']}: dubbel paar")
        gezien.add(sleutel)
    zelfde = {_sleutel("zelfde_betekenis", *s[1:]) for s in gezien if s[0] == "zelfde_betekenis"}
    for s in gezien:
        if s[0] == "verschillend" and _sleutel("zelfde_betekenis", *s[1:]) in zelfde:
            raise ReferentieFout(f"{s[1:]}: tegelijk zelfde betekenis en verschillend")
    if sethash(bronnen, cases) != manifest["sha256"]:
        raise ReferentieFout("manifest-hash wijkt af: draai --bijwerken (alleen een niet-bevroren versie)")


def laad(versie: str = ACTUELE_VERSIE) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    bronnen, cases, manifest = _lees(versie)
    valideer(bronnen, cases, manifest)
    return bronnen, cases, manifest


def manifest_uit(bronnen: dict[str, Any], cases: dict[str, Any]) -> Manifest:
    """De invoer voor de keten: dezelfde bronnen en formuleringen als de referentie."""
    return Manifest(
        bronnen=tuple(Bron(bron_iri=b["bron_iri"], tekst=b["tekst"], bron_hash=b["bron_hash"],
                           label=b.get("label", ""), aanhef=b.get("aanhef", ""),
                           regeling=b.get("regeling", "")) for b in bronnen["bronnen"]),
        formuleringen=tuple(Formulering(element_id=f["element_id"], bron_iri=f["bron_iri"],
                                        start=f["start"], eind=f["eind"], tekst=f["tekst"],
                                        jas_klasse=f["jas_klasse"])
                            for f in cases["formuleringen"]))


# ---------------------------------------------------------------------------------------------
# Wat een variant oplevert en hoe we scoren
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Voorspelling:
    """De vergelijkbare kern van een uitkomst: groepen, relaties en aandacht."""

    groepen: tuple[tuple[str, ...], ...]                    # elk gesorteerd
    relaties: tuple[tuple[str, str, str], ...]              # (hypothese, van, naar)
    aandacht: dict[str, int] = field(default_factory=dict)  # {"groen": n, "geel": m}

    def json(self) -> str:
        return json.dumps({"groepen": sorted(self.groepen), "relaties": sorted(self.relaties),
                           "aandacht": self.aandacht}, sort_keys=True)


def _sleutel(relatie: str, van: str, naar: str) -> tuple[str, str, str]:
    if relatie in GERICHT:
        return (relatie, van, naar)
    a, b = sorted((van, naar))
    return (relatie, a, b)


def gouden_groepen(cases: dict[str, Any]) -> list[set[str]]:
    """De transitieve sluiting van de zelfde-betekenis-paren; overige formuleringen als singleton."""
    ouder = {f["element_id"]: f["element_id"] for f in cases["formuleringen"]}

    def wortel(x: str) -> str:
        while ouder[x] != x:
            ouder[x] = ouder[ouder[x]]
            x = ouder[x]
        return x

    for p in cases["paren"]:
        if p["relatie"] == "zelfde_betekenis":
            ouder[wortel(p["van"])] = wortel(p["naar"])
    groepen: dict[str, set[str]] = defaultdict(set)
    for x in ouder:
        groepen[wortel(x)].add(x)
    return list(groepen.values())


def bcubed(voorspeld: list[set[str]], goud: list[set[str]], items: list[str]) -> dict[str, float]:
    """BCubed precisie/recall/F (Amigó e.a. 2009); elk item zit in precies één cluster."""
    def index(clusters: list[set[str]]) -> dict[str, set[str]]:
        idx = {x: c for c in clusters for x in c}
        return {x: idx.get(x, {x}) for x in items}

    v, g = index(voorspeld), index(goud)
    p = sum(len(v[x] & g[x]) / len(v[x]) for x in items) / len(items)
    r = sum(len(v[x] & g[x]) / len(g[x]) for x in items) / len(items)
    return {"precisie": round(p, 4), "recall": round(r, 4),
            "f": round(2 * p * r / (p + r), 4) if p + r else 0.0}


def _pr(voorspeld: set, goud: set) -> dict[str, Any]:
    tp = len(voorspeld & goud)
    return {"tp": tp, "voorspeld": len(voorspeld), "goud": len(goud),
            "precisie": round(tp / len(voorspeld), 4) if voorspeld else None,
            "recall": round(tp / len(goud), 4) if goud else None}


def scoor(v: Voorspelling, cases: dict[str, Any]) -> dict[str, Any]:
    items = [f["element_id"] for f in cases["formuleringen"]]
    goud_paren: dict[str, set] = defaultdict(set)
    for p in cases["paren"]:
        goud_paren[p["relatie"]].add(_sleutel(p["relatie"], p["van"], p["naar"]))
    # Een groep impliceert zelfde-betekenis-paren tussen al haar leden.
    voorspeld: dict[str, set] = defaultdict(set)
    for g in v.groepen:
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                voorspeld["zelfde_betekenis"].add(_sleutel("zelfde_betekenis", a, b))
    for h, a, b in v.relaties:
        voorspeld[h].add(_sleutel(h, a, b))
    # Een zelfde-betekenis-paar dat de gouden groepen impliceren is ook goud (transitiviteit).
    goud_groepen = gouden_groepen(cases)
    for g in goud_groepen:
        leden = sorted(g)
        for i, a in enumerate(leden):
            for b in leden[i + 1:]:
                goud_paren["zelfde_betekenis"].add(_sleutel("zelfde_betekenis", a, b))
    per_relatie = {h.value: _pr(voorspeld[h.value], goud_paren[h.value]) for h in Hypothese}
    verschillend = {(a, b) for _, a, b in goud_paren["verschillend"]}
    samengevoegd = sorted(f"{a}~{b}" for a, b in verschillend
                          if _sleutel("zelfde_betekenis", a, b) in voorspeld["zelfde_betekenis"])
    return {"per_relatie": per_relatie,
            "bcubed": bcubed([set(g) for g in v.groepen], goud_groepen, items),
            "samengevoegd_verschillend": samengevoegd,
            "aandacht": v.aandacht}


# ---------------------------------------------------------------------------------------------
# Varianten
# ---------------------------------------------------------------------------------------------

_LIDWOORD = re.compile(r"^(de|het|een)\s+", re.IGNORECASE)


def variant_lemma(manifest: Manifest) -> Voorspelling:
    """Nulmeting: groepeer op de formulering zonder lidwoord, kleine letters. Geen relaties.

    Dit is bewust naïef: het is wat 'zelfde woord = zelfde begrip' oplevert, en daarmee de lat
    die de keten moet halen zonder de homoniemen en kwalificaties mee te nemen.
    """
    per: dict[str, list[str]] = defaultdict(list)
    for f in manifest.formuleringen:
        per[_LIDWOORD.sub("", f.tekst).lower()].append(f.element_id)
    groepen = tuple(sorted(tuple(sorted(ids)) for ids in per.values() if len(ids) > 1))
    return Voorspelling(groepen=groepen, relaties=(), aandacht={"groen": len(groepen), "geel": 0})


def variant_keten(manifest: Manifest, provider: Any = None) -> Voorspelling:
    from agent.begrippen_pipeline import keten

    uit = keten.analyseer(manifest, provider)
    groepen = tuple(sorted(g.leden for g in uit.groepen))
    relaties = tuple(sorted((r.hypothese.value, r.van, r.naar) for r in uit.relaties))
    aandacht: dict[str, int] = defaultdict(int)
    for x in (*uit.groepen, *uit.relaties):
        aandacht[x.aandacht.value] += 1
    if uit.vragen:
        aandacht["geel"] += len(uit.vragen)                # een vraag is altijd geel
    return Voorspelling(groepen=groepen, relaties=relaties, aandacht=dict(aandacht))


def variant_keten_zonder_parse(manifest: Manifest) -> Voorspelling:
    """De keten met de null-provider: wat er overblijft zonder spaCy."""
    from agent.jas_pipeline.taal.provider import NullProvider
    return variant_keten(manifest, NullProvider())


VARIANTEN: dict[str, Callable[[Manifest], Voorspelling]] = {
    "lemma": variant_lemma, "keten": variant_keten, "keten_zonder_parse": variant_keten_zonder_parse}


def meet(variant: str, versie: str = ACTUELE_VERSIE) -> dict[str, Any]:
    bronnen, cases, manifest = laad(versie)
    m = manifest_uit(bronnen, cases)
    eerste, tweede = VARIANTEN[variant](m), VARIANTEN[variant](m)
    return {"variant": variant, "referentie_versie": manifest["referentie_versie"],
            "referentie_status": manifest["referentie_status"], "referentie_sha256": manifest["sha256"],
            "manifest_id": m.id, "formuleringen": len(m.formuleringen), "paren": len(cases["paren"]),
            "deterministisch": eerste.json() == tweede.json(),
            **scoor(eerste, cases)}


def rapport(r: dict[str, Any]) -> str:
    regels = [
        f"# Begrippenketen – variant `{r['variant']}`",
        "",
        f"Referentie {r['referentie_versie']} (status **{r['referentie_status']}**, "
        f"sha256 `{r['referentie_sha256'][:12]}`): {r['formuleringen']} formuleringen, "
        f"{r['paren']} paren. Manifest `{r['manifest_id']}`.",
        "",
        "Tegen een provisional set is dit een trendmeting, geen kwaliteitsoordeel.",
        "",
        "| relatie | voorspeld | goud | tp | precisie | recall |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for h, s in r["per_relatie"].items():
        regels.append(f"| {h} | {s['voorspeld']} | {s['goud']} | {s['tp']} | "
                      f"{'–' if s['precisie'] is None else s['precisie']} | "
                      f"{'–' if s['recall'] is None else s['recall']} |")
    b = r["bcubed"]
    regels += ["", f"BCubed groepen: precisie {b['precisie']}, recall {b['recall']}, F {b['f']}.",
               f"Verschillend maar samengevoegd: {len(r['samengevoegd_verschillend'])}"
               + (f" ({', '.join(r['samengevoegd_verschillend'])})" if r["samengevoegd_verschillend"] else "")
               + ".",
               f"Aandacht: {r['aandacht']}. Deterministisch: {'ja' if r['deterministisch'] else 'NEE'}."]
    return "\n".join(regels) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--versie", default=ACTUELE_VERSIE)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--bijwerken", action="store_true")
    ap.add_argument("--variant", choices=sorted(VARIANTEN))
    ap.add_argument("--json", action="store_true", help="rapport als JSON")
    args = ap.parse_args()
    if args.bijwerken:
        bronnen, cases, manifest = _lees(args.versie)
        if manifest["bevroren_op"]:
            raise SystemExit("een bevroren versie verandert niet; maak een nieuwe versie")
        manifest["sha256"] = sethash(bronnen, cases)
        (versiemap(args.versie) / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print(f"hash bijgewerkt: {manifest['sha256']}")
    if args.check or args.bijwerken:
        laad(args.versie)
        print(f"referentieset-begrippen {args.versie}: geldig")
    if args.variant:
        r = meet(args.variant, args.versie)
        print(json.dumps(r, ensure_ascii=False, indent=2) if args.json else rapport(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
