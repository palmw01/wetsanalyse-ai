"""Meting van bronnen vinden met Lex (spoor D, fase A): welke ontdekmethode helpt?

De referentieset staat in `docs/wetsanalyse/referentieset-bronselectie/<set>/set.json`: een
analysevraag, de kernselectie, de **verwachte** bepalingen met rol en motivering, wat buiten de graaf
valt (een open punt, niet in de noemer) en de **uitgesloten** bepalingen met reden.

Maten, per configuratie van methoden:

- `recall_nodig`: aandeel van de verwachte bepalingen met rol kern of afhankelijkheid dat gevonden is;
- `recall`: idem over alle verwachte bepalingen (ook aanverwant);
- `recall_exact`: als `recall`, maar alleen een kandidaat die gelijk is aan de verwachte bepaling of
  erbinnen valt – niet een die haar omvat (heel artikel 2 "omvat" alle definities, maar wijst geen
  ervan aan);
- `recall@10` / `recall@20` over de lijst in de volgorde van de werkplek (sterkste rol eerst);
- `overbodig`: aandeel kandidaten dat een **uitgesloten** bepaling raakt (hoort 0 te zijn);
- `onbeoordeeld`: kandidaten die de set niet noemt – geen fout, wel werk voor de jurist;
- `rol_juist`: van de gevonden verwachte bepalingen, het aandeel met de verwachte rol;
- `aantal`: hoeveel kandidaten de jurist te zien krijgt.

Een kandidaat raakt een bepaling uit de set als hij er gelijk aan is, erbinnen valt of haar omvat
(`bronnen_vinden.in_selectie`): artikel 8 opnemen omvat artikel 8 lid 1.

Configuraties: elke methode apart, de standaard (`STANDAARD`), de standaard min telkens één methode
(ablatie) en de standaard plus gelijkenis. **Een methode die de standaard niet aantoonbaar beter maakt,
hoort niet standaard aan** – dat oordeel staat in het meetlogboek, niet in dit script.

De status van de set is `concept` tot een jurist hem vaststelt; de cijfers heten dan een trendmeting.

Offline (standaard, en zo in CI) draait alles tegen een **opname** van de graafantwoorden
(`graafantwoorden.json` naast de set), zodat geen graaf nodig is. Een query die niet in de opname
staat, laat die methode falen (`volledig: false`) en het rapport noemt het.

    python -m eval.bronselectie_eval                      # offline, tegen de opname
    python -m eval.bronselectie_eval --opnemen            # live tegen de graaf, en de opname vernieuwen
    python -m eval.bronselectie_eval --json uit.json      # het rapport ook als JSON
    python -m eval.bronselectie_eval --intake             # per deelvraag (F3f), op een set met deelvragen

**`--intake`** (F3f) meet de bepalingen per deelvraag: `bepaling_opties` – de functie van de intake én
van de deelvragen-agent – tegen de verwachte bepalingen van elke deelvraag (`verwacht[].deelvraag`),
naast de vorige deelvraagmethode (het overzicht per deelvraag, op artikelniveau) als ijkpunt. Maten per
deelvraag en samen: `recall`, `recall_nodig`, `recall_exact` (het lid zelf, of erbinnen), `precisie`
(het aandeel opties dat een verwachte bepaling van díé deelvraag raakt), `uitgesloten` (opties die een
uitgesloten bepaling raken, niet gemarkeerd) en `uitgesloten_gemarkeerd` (wel gemarkeerd, onderaan).

`--opnemen` vraagt `GRAPHDB_MCP_URL` en `GRAPHDB_TOKEN` (en voor gelijkenis `SIMILARITY_INDEX`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from agent import bronnen_vinden
from agent.bronnen_vinden import METHODEN, STANDAARD, in_selectie, vind

SETS = Path(__file__).resolve().parents[3] / "docs" / "wetsanalyse" / "referentieset-bronselectie"
STANDAARD_SET = "invorderbaarheid-concept"


def _sleutel(tekst: str) -> str:
    return hashlib.sha256(tekst.encode()).hexdigest()[:24]


class OpnameGraaf:
    """Speelt opgenomen graafantwoorden af; een onbekende query is een fout (geen stil leeg)."""

    def __init__(self, opname: dict[str, dict[str, str]]) -> None:
        self.opname = opname
        self.ontbrekend = 0

    def initialize(self) -> dict[str, Any]:
        return {}

    def sparql(self, query: str) -> str:
        try:
            return self.opname["sparql"][_sleutel(query)]
        except KeyError:
            self.ontbrekend += 1
            raise LookupError("query niet in de opname") from None

    def semantic_search(self, query: str, limit: int = 10) -> str:
        try:
            return self.opname["semantisch"][_sleutel(f"{limit}|{query}")]
        except KeyError:
            self.ontbrekend += 1
            raise LookupError("semantische zoekvraag niet in de opname") from None

    def close(self) -> None:
        pass


class OpnemendeGraaf:
    """Stuurt door naar de echte graaf en onthoudt elk antwoord."""

    def __init__(self, echt: Any) -> None:
        self.echt = echt
        self.opname: dict[str, dict[str, str]] = {"sparql": {}, "semantisch": {}}

    def initialize(self) -> dict[str, Any]:
        return self.echt.initialize()

    def sparql(self, query: str) -> str:
        uit = self.echt.sparql(query)
        self.opname["sparql"][_sleutel(query)] = uit
        return uit

    def semantic_search(self, query: str, limit: int = 10) -> str:
        uit = self.echt.semantic_search(query, limit)
        self.opname["semantisch"][_sleutel(f"{limit}|{query}")] = uit
        return uit

    def close(self) -> None:
        self.echt.close()


def laad_set(naam: str = STANDAARD_SET) -> dict[str, Any]:
    return json.loads((SETS / naam / "set.json").read_text())


def invoer_van(s: dict[str, Any]) -> dict[str, Any]:
    """Zoals de api hem vastlegt (`bronnen_run_store.invoer_van`)."""
    return {"naam": s["naam"], "analysevraag": s["analysevraag"], "context": [],
            "kern": [{"bron_iri": k["bron_iri"], "label": k.get("label", ""), "bwb_id": k["bron_iri"].split(":")[2],
                      "bereik": "onderliggend"} for k in s["kern"]]}


def configuraties() -> dict[str, tuple[str, ...]]:
    """Elke methode apart, de standaard (met kern), de standaard min telkens één methode, en de
    standaard plus elk van de methoden die er niet in zitten."""
    uit: dict[str, tuple[str, ...]] = {f"alleen {m}": (m,) for m in METHODEN}
    uit["standaard"] = STANDAARD
    for m in STANDAARD:
        uit[f"standaard zonder {m}"] = tuple(x for x in STANDAARD if x != m)
    for m in METHODEN:
        if m not in STANDAARD:
            uit[f"standaard + {m}"] = (*STANDAARD, m)
    uit["alles"] = METHODEN
    return uit


def _raakt(kandidaat: str, iri: str) -> bool:
    return in_selectie(kandidaat, [iri])


def scoor(s: dict[str, Any], uitkomst: dict[str, Any]) -> dict[str, Any]:
    ks = uitkomst["kandidaten"]
    iris = [k["bron_iri"] for k in ks]
    verwacht = s["verwacht"]
    nodig = [v for v in verwacht if v["rol"] in ("kern", "afhankelijkheid")]

    def gevonden_in(lijst: list[str], v: dict[str, Any]) -> bool:
        return any(_raakt(c, v["bron_iri"]) for c in lijst)

    def recall(groep: list[dict[str, Any]], lijst: list[str]) -> float | None:
        return round(sum(gevonden_in(lijst, v) for v in groep) / len(groep), 3) if groep else None

    def precies(v: dict[str, Any]) -> bool:
        return any(c == v["bron_iri"] or c.startswith(v["bron_iri"] + ":") for c in iris)

    overbodig = [c for c in iris if any(_raakt(c, u["bron_iri"]) for u in s["uitgesloten"])]
    bekend = [v["bron_iri"] for v in verwacht] + [u["bron_iri"] for u in s["uitgesloten"]]
    onbeoordeeld = [c for c in iris if not any(_raakt(c, b) for b in bekend)]
    rollen = []
    for v in verwacht:
        k = next((k for k in ks if _raakt(k["bron_iri"], v["bron_iri"])), None)
        if k is not None:
            rollen.append(k["rol"] == v["rol"])
    return {
        "aantal": len(ks),
        "recall_nodig": recall(nodig, iris),
        "recall": recall(verwacht, iris),
        "recall_exact": round(sum(precies(v) for v in verwacht) / len(verwacht), 3) if verwacht else None,
        "recall@10": recall(verwacht, iris[:10]),
        "recall@20": recall(verwacht, iris[:20]),
        "overbodig": round(len(overbodig) / len(ks), 3) if ks else 0.0,
        "overbodig_iris": overbodig,
        "onbeoordeeld": len(onbeoordeeld),
        "rol_juist": round(sum(rollen) / len(rollen), 3) if rollen else None,
        "gemist": [v["bron_iri"] for v in verwacht if not gevonden_in(iris, v)],
        "onvolledig": sorted(m for m, x in uitkomst["meting"].items() if not x["volledig"]),
    }


def meet(graaf: Any, s: dict[str, Any], configs: dict[str, tuple[str, ...]] | None = None) -> dict[str, Any]:
    invoer = invoer_van(s)
    rapport = {}
    from agent import overzicht, regelingnamen
    for naam, methoden in (configs or configuraties()).items():
        # Elke configuratie op zichzelf: geen namen of regelingen uit de cache van een vorige, anders
        # vraagt een configuratie offline iets anders dan bij de opname.
        regelingnamen._CACHE.clear()
        overzicht._REGELINGEN_CACHE.clear()
        rapport[naam] = scoor(s, vind(graaf, invoer, methoden))
    return rapport


def tabel(s: dict[str, Any], rapport: dict[str, Any]) -> str:
    regels = [f"Set: {s['naam']} – status {s['status']} (trendmeting, geen kwaliteitsoordeel tot vaststelling)",
              f"Analysevraag: {s['analysevraag']}",
              f"Verwacht: {len(s['verwacht'])} (nodig: {sum(v['rol'] != 'aanverwant' for v in s['verwacht'])}),"
              f" uitgesloten: {len(s['uitgesloten'])}, buiten de graaf: {len(s['buiten_graaf'])}", "",
              "| configuratie | aantal | recall nodig | recall | exact | r@10 | r@20 | overbodig | onbeoordeeld | rol juist | onvolledig |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for naam, r in rapport.items():
        def f(x):
            return "–" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)
        regels.append(f"| {naam} | {r['aantal']} | {f(r['recall_nodig'])} | {f(r['recall'])} | {f(r['recall_exact'])} | {f(r['recall@10'])} | "
                      f"{f(r['recall@20'])} | {f(r['overbodig'])} | {r['onbeoordeeld']} | {f(r['rol_juist'])} | "
                      f"{', '.join(r['onvolledig']) or '–'} |")
    std = rapport.get("standaard")
    if std:
        regels += ["", f"Gemist door de standaard: {', '.join(std['gemist']) or 'niets'}",
                   f"Overbodig in de standaard: {', '.join(std['overbodig_iris']) or 'niets'}"]
    return "\n".join(regels)


# --- per deelvraag (F3f) ---------------------------------------------------------------------------

INTAKE_SET = "bezwaar-ontvankelijkheid-concept"


def _vorige_deelvraagmethode(graph: Any, s: dict[str, Any], vraag: str) -> list[dict[str, Any]]:
    """De deelvraagmethode van vóór F3f (`bronnen_vinden._deelvraag` tot 21 okt 2026), als ijkpunt: het
    overzicht per deelvraag, op artikelniveau, hoogstens 15 – letterlijk overgenomen."""
    from agent.overzicht import bouw_overzicht

    onderwerp = bronnen_vinden.onderwerp_van_deelvraag(vraag)
    if not onderwerp:
        return []
    try:
        ov = bouw_overzicht(graph, vraag, onderwerp=onderwerp)
    except ValueError:
        return []
    uit = []
    for r in ov.get("regelingen", []):
        for b in [b for deel in r.get("delen", []) for b in deel.get("bepalingen", [])] + r.get("ook_genoemd", []):
            if len(uit) < 15 and b["iri"] not in [u["bron_iri"] for u in uit]:
                uit.append({"bron_iri": b["iri"], "buiten": False})
    return uit


def _bepaling_opties(graph: Any, s: dict[str, Any], vraag: str) -> list[dict[str, Any]]:
    from agent.werkgebied_context import uitsluitstammen

    return bronnen_vinden.bepaling_opties(
        graph, regelingen=s["regelingen"], deelvraag=vraag,
        dossier={k: s.get(k, "") for k in ("naam", "analysevraag", "praktijkvoorbeeld", "context")},
        buiten=uitsluitstammen(s.get("buiten", "")))


ROUTES = {"bepaling_opties": _bepaling_opties, "vorige deelvraagmethode": _vorige_deelvraagmethode}


def scoor_deelvraag(s: dict[str, Any], i: int, opties: list[dict[str, Any]]) -> dict[str, Any]:
    verwacht = [v for v in s["verwacht"] if v["deelvraag"] == i]
    nodig = [v for v in verwacht if v["rol"] in ("kern", "afhankelijkheid")]
    gewoon = [o["bron_iri"] for o in opties if not o.get("buiten")]
    gemarkeerd = [o["bron_iri"] for o in opties if o.get("buiten")]
    alles = gewoon + gemarkeerd

    def gevonden(v: dict[str, Any]) -> bool:
        return any(_raakt(c, v["bron_iri"]) for c in alles)

    def precies(v: dict[str, Any]) -> bool:
        return any(c == v["bron_iri"] or c.startswith(v["bron_iri"] + ":") for c in alles)

    def raakt_uitgesloten(c: str) -> bool:
        return any(_raakt(c, u["bron_iri"]) for u in s["uitgesloten"])

    return {"verwacht": len(verwacht), "nodig": len(nodig), "aantal": len(gewoon), "gemarkeerd": len(gemarkeerd),
            "gevonden": sum(map(gevonden, verwacht)), "gevonden_nodig": sum(map(gevonden, nodig)),
            "exact": sum(map(precies, verwacht)),
            "raak": sum(1 for c in gewoon if any(_raakt(c, v["bron_iri"]) for v in verwacht)),
            "uitgesloten": [c for c in gewoon if raakt_uitgesloten(c)],
            "uitgesloten_gemarkeerd": [c for c in gemarkeerd if raakt_uitgesloten(c)],
            "gemist": [v["bron_iri"] for v in verwacht if not gevonden(v)],
            "opties": alles}


def _deel(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


def meet_intake(graaf: Any, s: dict[str, Any]) -> dict[str, Any]:
    from agent import overzicht, regelingnamen

    rapport = {}
    for naam, route in ROUTES.items():
        regelingnamen._CACHE.clear()
        overzicht._REGELINGEN_CACHE.clear()
        per = [scoor_deelvraag(s, i, route(graaf, s, vraag)) for i, vraag in enumerate(s["deelvragen"])]
        som = {k: sum(p[k] for p in per) for k in ("verwacht", "nodig", "aantal", "gevonden", "gevonden_nodig", "exact", "raak")}
        rapport[naam] = {"recall": _deel(som["gevonden"], som["verwacht"]),
                         "recall_nodig": _deel(som["gevonden_nodig"], som["nodig"]),
                         "recall_exact": _deel(som["exact"], som["verwacht"]),
                         "precisie": _deel(som["raak"], som["aantal"]), "aantal": som["aantal"],
                         "uitgesloten": sum(len(p["uitgesloten"]) for p in per),
                         "uitgesloten_gemarkeerd": sum(len(p["uitgesloten_gemarkeerd"]) for p in per),
                         "per_deelvraag": per}
    return rapport


def tabel_intake(s: dict[str, Any], rapport: dict[str, Any]) -> str:
    def f(x):
        return "–" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)
    regels = [f"Set: {s['naam']} – status {s['status']} (trendmeting, geen kwaliteitsoordeel tot vaststelling)",
              f"Analysevraag: {s['analysevraag']}",
              f"Deelvragen: {len(s['deelvragen'])}, verwacht: {len(s['verwacht'])}, uitgesloten: {len(s['uitgesloten'])}",
              "", "| route | aantal | recall | recall nodig | exact | precisie | uitgesloten | uitgesloten gemarkeerd |",
              "|---|---|---|---|---|---|---|---|"]
    for naam, r in rapport.items():
        regels.append(f"| {naam} | {r['aantal']} | {f(r['recall'])} | {f(r['recall_nodig'])} | {f(r['recall_exact'])} | "
                      f"{f(r['precisie'])} | {r['uitgesloten']} | {r['uitgesloten_gemarkeerd']} |")
    for naam, r in rapport.items():
        regels += ["", f"**{naam}** per deelvraag:"]
        for i, p in enumerate(r["per_deelvraag"]):
            regels.append(f"- {i + 1}. {p['gevonden']}/{p['verwacht']} gevonden (exact {p['exact']}), {p['raak']}/{p['aantal']} raak"
                          f"{', gemarkeerd ' + str(p['gemarkeerd']) if p['gemarkeerd'] else ''}; gemist: "
                          f"{', '.join(g.split(':', 2)[2] for g in p['gemist']) or 'niets'}")
    return "\n".join(regels)


def _echte_graaf():
    from agent.adapters.graphdb_graph import make_graph
    from agent.config import Settings
    return make_graph(Settings.from_env())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--set", default=None)
    p.add_argument("--intake", action="store_true", help="per deelvraag meten (F3f), op een set met deelvragen")
    p.add_argument("--opnemen", action="store_true", help="live tegen de graaf en de opname vernieuwen")
    p.add_argument("--json", type=Path, help="het rapport ook als JSON wegschrijven")
    a = p.parse_args(argv)
    a.set = a.set or (INTAKE_SET if a.intake else STANDAARD_SET)
    s = laad_set(a.set)
    if a.intake and not s.get("deelvragen"):
        p.error(f"set {a.set} heeft geen deelvragen")
    meting, opmaak = (meet_intake, tabel_intake) if a.intake else (meet, tabel)
    pad = SETS / a.set / "graafantwoorden.json"
    if a.opnemen:
        graaf = OpnemendeGraaf(_echte_graaf())
        try:
            rapport = meting(graaf, s)
        finally:
            graaf.close()
        pad.write_text(json.dumps(graaf.opname, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    else:
        graaf = OpnameGraaf(json.loads(pad.read_text()))
        rapport = meting(graaf, s)
        if graaf.ontbrekend:
            print(f"Let op: {graaf.ontbrekend} query's stonden niet in de opname; draai --opnemen.", file=sys.stderr)
    print(opmaak(s, rapport))
    if a.json:
        a.json.write_text(json.dumps({"set": a.set, "status": s["status"], "rapport": rapport}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
