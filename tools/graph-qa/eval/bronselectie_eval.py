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
Voor `bepaling_opties` ook `recall_pool`: het aandeel verwachte bepalingen dat de index vindt vóór de
rangschikking (`deelvraag_zoeken.kandidatenpool`). Ligt `recall` daar ver onder, dan laat de
rangschikking ze vallen; ligt `recall_pool` zelf laag, dan mist het zoeken ze.

**`--zoekvragen`** meet op een set met een `gebeurtenis` (schema 3) de eerste stap van de zoekvragen a–d
(`agent/zoekvragen.py`): op welke plek `gebeurtenis_opties` de gebeurtenis van de set voorstelt, met en zonder de
naam van het werkgebied, en hoeveel van de verwachte bepalingen met `zoekvraag: a` de `grondslag` vindt.

`--opnemen` vraagt `GRAPHDB_MCP_URL` en `GRAPHDB_TOKEN` (en voor gelijkenis `SIMILARITY_INDEX`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from agent import deelvraag_zoeken, zoektermen
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


class AanvullendeGraaf(OpnameGraaf):
    """Speelt de opname af en haalt alleen wat ontbreekt bij de echte graaf, en onthoudt dat erbij. Zo blijft
    een opname die bij een eerdere meting hoort (bewijs) staan, en komen de queries van nieuwe code erbij."""

    def __init__(self, opname: dict[str, dict[str, str]], echt: Any) -> None:
        super().__init__(opname)
        self.echt = echt

    def sparql(self, query: str) -> str:
        sleutel = _sleutel(query)
        if sleutel not in self.opname["sparql"]:
            self.opname["sparql"][sleutel] = self.echt.sparql(query)
        return self.opname["sparql"][sleutel]

    def semantic_search(self, query: str, limit: int = 10) -> str:
        sleutel = _sleutel(f"{limit}|{query}")
        if sleutel not in self.opname["semantisch"]:
            self.opname["semantisch"][sleutel] = self.echt.semantic_search(query, limit)
        return self.opname["semantisch"][sleutel]

    def close(self) -> None:
        self.echt.close()


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

    onderwerp = zoektermen.onderwerp_van_deelvraag(vraag)
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


def _dossier(s: dict[str, Any]) -> dict[str, Any]:
    return {k: s.get(k, "") for k in ("naam", "analysevraag", "praktijkvoorbeeld", "context", "aanleiding", "doel")}


def _met_profiel(profiel: deelvraag_zoeken.Zoekprofiel):
    def route(graph: Any, s: dict[str, Any], vraag: str) -> list[dict[str, Any]]:
        from agent.zoektermen import uitsluitstammen

        return deelvraag_zoeken.bepaling_opties(graph, regelingen=s["regelingen"], deelvraag=vraag, dossier=_dossier(s),
                                              buiten=uitsluitstammen(s.get("buiten", "")), profiel=profiel)
    route.profiel = profiel
    return route


_bepaling_opties = _met_profiel(deelvraag_zoeken.STANDAARD_PROFIEL)
#: De ingrepen waarmee het dossier meezoekt (meetlogboek `bronselectie-2026-11-04-dossier`).
DOSSIERVLAGGEN = ("dossier_velden", "dossier_lijsten", "dossier_omgeving", "gelijkenis")

#: De routes van de meting: de standaard, de rangschikking van F3f (21 okt 2026) als ijkpunt, de standaard met
#: telkens één ingreep uit of – het lemma, standaard uit – erbij (ablatie), en de deelvraagmethode van vóór F3f.
ROUTES = {"bepaling_opties": _bepaling_opties, "F3f (21 okt)": _met_profiel(deelvraag_zoeken.F3F),
          **{f"zonder {v}": _met_profiel(replace(deelvraag_zoeken.STANDAARD_PROFIEL, **{v: False}))
             for v in ("per_term", "samenstelling", "divisies", "kop_overal", "fusie", "per_regeling")},
          "met lemma": _met_profiel(replace(deelvraag_zoeken.STANDAARD_PROFIEL, lemma=True)),
          "met lengte": _met_profiel(replace(deelvraag_zoeken.STANDAARD_PROFIEL, lengte=True)),
          **{f"met {v}": _met_profiel(replace(deelvraag_zoeken.STANDAARD_PROFIEL, **{v: True}))
             for v in DOSSIERVLAGGEN},
          "met dossier (alles)": _met_profiel(replace(deelvraag_zoeken.STANDAARD_PROFIEL,
                                                      **{v: True for v in DOSSIERVLAGGEN})),
          "vorige deelvraagmethode": _vorige_deelvraagmethode}


def _pool(graph: Any, s: dict[str, Any], vraag: str, profiel=deelvraag_zoeken.STANDAARD_PROFIEL) -> list[str]:
    """Wat de index bij de deelvraag vindt, vóór de rangschikking (`deelvraag_zoeken.kandidatenpool`): zo
    scheidt de meting wat het zoeken mist van wat de rangschikking laat vallen."""
    pool = deelvraag_zoeken.kandidatenpool(graph, regelingen=s["regelingen"], deelvraag=vraag, dossier=_dossier(s),
                                         profiel=profiel)
    return list(pool["gevonden"]) if pool else []


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


def scoor_pool(s: dict[str, Any], i: int, pool: list[str]) -> dict[str, Any]:
    verwacht = [v for v in s["verwacht"] if v["deelvraag"] == i]
    in_pool = [v for v in verwacht if any(_raakt(c, v["bron_iri"]) for c in pool)]
    return {"pool": len(pool), "in_pool": len(in_pool),
            "niet_in_pool": [v["bron_iri"] for v in verwacht if v not in in_pool]}


def _deel(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


def meet_intake(graaf: Any, s: dict[str, Any]) -> dict[str, Any]:
    from agent import overzicht, regelingnamen

    rapport = {}
    for naam, route in ROUTES.items():
        regelingnamen._CACHE.clear()
        overzicht._REGELINGEN_CACHE.clear()
        per = [scoor_deelvraag(s, i, route(graaf, s, vraag)) for i, vraag in enumerate(s["deelvragen"])]
        if hasattr(route, "profiel"):
            for i, (p, vraag) in enumerate(zip(per, s["deelvragen"])):
                p.update(scoor_pool(s, i, _pool(graaf, s, vraag, route.profiel)))
        # Hoeveel opties bij meer dan één deelvraag staan: als het dossier elk kaartje vult, stijgt dit (spoor K).
        tel: dict[str, int] = {}
        for p in per:
            for c in set(p["opties"]):
                tel[c] = tel.get(c, 0) + 1
        alle_opties = [c for p in per for c in p["opties"]]
        som = {k: sum(p[k] for p in per) for k in ("verwacht", "nodig", "aantal", "gevonden", "gevonden_nodig", "exact", "raak")}
        rapport[naam] = {"recall": _deel(som["gevonden"], som["verwacht"]),
                         "recall_nodig": _deel(som["gevonden_nodig"], som["nodig"]),
                         "recall_exact": _deel(som["exact"], som["verwacht"]),
                         "precisie": _deel(som["raak"], som["aantal"]), "aantal": som["aantal"],
                         "uitgesloten": sum(len(p["uitgesloten"]) for p in per),
                         "uitgesloten_gemarkeerd": sum(len(p["uitgesloten_gemarkeerd"]) for p in per),
                         "gedeeld": _deel(sum(1 for c in alle_opties if tel[c] > 1), len(alle_opties)),
                         "per_deelvraag": per}
        if hasattr(route, "profiel"):
            rapport[naam]["recall_pool"] = _deel(sum(p["in_pool"] for p in per), som["verwacht"])
            rapport[naam]["pool"] = sum(p["pool"] for p in per)
    return rapport


def tabel_intake(s: dict[str, Any], rapport: dict[str, Any]) -> str:
    def f(x):
        return "–" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)
    regels = [f"Set: {s['naam']} – status {s['status']} (trendmeting, geen kwaliteitsoordeel tot vaststelling)",
              f"Analysevraag: {s['analysevraag']}",
              f"Deelvragen: {len(s['deelvragen'])}, verwacht: {len(s['verwacht'])}, uitgesloten: {len(s['uitgesloten'])}",
              "", "| route | aantal | recall | recall nodig | exact | precisie | uitgesloten | uitgesloten gemarkeerd "
                  "| gedeeld | pool | recall pool |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for naam, r in rapport.items():
        regels.append(f"| {naam} | {r['aantal']} | {f(r['recall'])} | {f(r['recall_nodig'])} | {f(r['recall_exact'])} | "
                      f"{f(r['precisie'])} | {r['uitgesloten']} | {r['uitgesloten_gemarkeerd']} | {f(r['gedeeld'])} | "
                      f"{r.get('pool', '–')} | {f(r.get('recall_pool'))} |")
    for naam, r in rapport.items():
        if naam not in ("bepaling_opties", "F3f (21 okt)", "vorige deelvraagmethode"):
            continue
        regels += ["", f"**{naam}** per deelvraag:"]
        for i, p in enumerate(r["per_deelvraag"]):
            regels.append(f"- {i + 1}. {p['gevonden']}/{p['verwacht']} gevonden (exact {p['exact']}), {p['raak']}/{p['aantal']} raak"
                          f"{', gemarkeerd ' + str(p['gemarkeerd']) if p['gemarkeerd'] else ''}; gemist: "
                          f"{', '.join(g.split(':', 2)[2] for g in p['gemist']) or 'niets'}"
                          + (f"; in de pool {p['in_pool']}/{p['verwacht']} (van {p['pool']}), niet in de pool: "
                             f"{', '.join(g.split(':', 2)[2] for g in p['niet_in_pool']) or 'niets'}" if "pool" in p else ""))
    return "\n".join(regels)


# --- zoekvragen a–d: de gebeurtenis en de grondslag ---------------------------------------------------

def meet_zoekvragen(graaf: Any, s: dict[str, Any]) -> dict[str, Any]:
    """De plek van de gebeurtenis van de set in de voorstellen (1 = bovenaan, None = niet in de lijst), met en
    zonder de naam, en de recall van de grondslag op de verwachte bepalingen met `zoekvraag: a`."""
    from agent import zoekvragen
    from agent.zoektermen import _stamdeel, zoektermen as termen

    doel = termen(s["gebeurtenis"])
    sleutel = _stamdeel(doel[0]) if doel else ""

    def plek(dossier: dict[str, Any]) -> tuple[int | None, list[str]]:
        opties = [o["gebeurtenis"] for o in zoekvragen.gebeurtenis_opties(graaf, regelingen=s["regelingen"],
                                                                          dossier=dossier)]
        gevonden = [i + 1 for i, o in enumerate(opties) if zoekvragen._sleutel(o) == sleutel]
        return (gevonden[0] if gevonden else None), opties

    dossier = {k: s.get(k, "") for k in zoekvragen.DOSSIERVELDEN}
    met, opties_met = plek(dossier)
    zonder, opties_zonder = plek({**dossier, "naam": ""})
    buiten = zoektermen.uitsluitstammen(zoektermen.buiten_uit_afbakening("Buiten de afbakening: " + s.get("buiten", "")))
    gevonden = [k["bron_iri"] for k in zoekvragen.grondslag(graaf, gebeurtenis=s["gebeurtenis"],
                                                             regelingen=s["regelingen"], buiten=buiten)]
    verwacht = list(dict.fromkeys(v["bron_iri"] for v in s["verwacht"] if v.get("zoekvraag") == "a"))
    raak = [v for v in verwacht if any(_raakt(c, v) for c in gevonden)]
    # De pool van de zoekvragen a–d (PR 4): wat erin zit, per zoekvraag van de set.
    p = zoekvragen.pool(graaf, gebeurtenis=s["gebeurtenis"], regelingen=s["regelingen"], buiten=buiten)
    pool = p["kandidaten"]
    unieke = list({v["bron_iri"]: v for v in s["verwacht"]}.values())

    def treffer(v: dict[str, Any]) -> dict[str, Any] | None:
        return next((k for k in pool if _raakt(k["bron_iri"], v["bron_iri"])), None)

    per_zoekvraag = {}
    for z in "abcd":
        groep = [v for v in unieke if v.get("zoekvraag") == z]
        per_zoekvraag[z] = {"verwacht": len(groep), "gevonden": sum(treffer(v) is not None for v in groep)}
    nodig = [v for v in unieke if v["rol"] in ("kern", "afhankelijkheid")]
    gevonden_v = [(v, t) for v in unieke if (t := treffer(v)) is not None]
    pool_meting = {
        "pool": len(pool), "pool_volledig": p["volledig"], "per_zoekvraag": per_zoekvraag,
        "pool_recall": _deel(len(gevonden_v), len(unieke)),
        "pool_recall_nodig": _deel(sum(treffer(v) is not None for v in nodig), len(nodig)),
        "zoekvraag_juist": _deel(sum(t["zoekvraag"] == v.get("zoekvraag") for v, t in gevonden_v), len(gevonden_v)),
        "pool_uitgesloten": [k["bron_iri"] for k in pool if any(_raakt(k["bron_iri"], u["bron_iri"]) for u in s["uitgesloten"])],
        "pool_gemist": [v["bron_iri"] for v in unieke if treffer(v) is None],
    }
    return {**pool_meting, "gebeurtenis": s["gebeurtenis"], "plek_met_naam": met, "plek_zonder_naam": zonder,
            "opties_met_naam": opties_met, "opties_zonder_naam": opties_zonder,
            "grondslag": gevonden, "grondslag_verwacht": verwacht, "grondslag_recall": _deel(len(raak), len(verwacht)),
            "grondslag_precisie": _deel(sum(any(_raakt(c, v["bron_iri"]) for v in s["verwacht"]) for c in gevonden),
                                       len(gevonden))}


def tabel_zoekvragen(s: dict[str, Any], r: dict[str, Any]) -> str:
    def f(x):
        return "–" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)
    return "\n".join([
        f"Set: {s['naam']} – gebeurtenis *{r['gebeurtenis']}*", "",
        f"- plek in de voorstellen met de naam: {f(r['plek_met_naam'])} ({', '.join(r['opties_met_naam'])})",
        f"- zonder de naam: {f(r['plek_zonder_naam'])} ({', '.join(r['opties_zonder_naam'])})",
        f"- grondslag (zoekvraag a): recall {f(r['grondslag_recall'])}, precisie {f(r['grondslag_precisie'])}, "
        f"{len(r['grondslag'])} gevonden: {', '.join(g.split(':', 2)[2] for g in r['grondslag'])}",
        f"- pool a–d: {r['pool']} kandidaten{'' if r['pool_volledig'] else ' (onvolledig)'}, recall {f(r['pool_recall'])}, "
        f"recall nodig {f(r['pool_recall_nodig'])}, zoekvraag juist {f(r['zoekvraag_juist'])}, "
        f"uitgesloten {len(r['pool_uitgesloten'])}",
        "  per zoekvraag: " + ", ".join(f"{z} {x['gevonden']}/{x['verwacht']}" for z, x in r["per_zoekvraag"].items()),
        f"  gemist: {', '.join(g.split(':', 2)[2][-40:] for g in r['pool_gemist']) or 'niets'}"])


def _echte_graaf():
    from agent.adapters.graphdb_graph import make_graph
    from agent.config import Settings
    return make_graph(Settings.from_env())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--set", default=None)
    p.add_argument("--intake", action="store_true", help="per deelvraag meten (F3f), op een set met deelvragen")
    p.add_argument("--zoekvragen", action="store_true",
                   help="de gebeurtenis en de grondslag (zoekvragen a–d), op een set met een gebeurtenis")
    p.add_argument("--opnemen", action="store_true", help="live tegen de graaf en de opname vernieuwen")
    p.add_argument("--aanvullen", action="store_true",
                   help="de opname afspelen en alleen wat ontbreekt live ophalen en toevoegen (de rest blijft bewijs)")
    p.add_argument("--json", type=Path, help="het rapport ook als JSON wegschrijven")
    a = p.parse_args(argv)
    a.set = a.set or (INTAKE_SET if a.intake else STANDAARD_SET)
    s = laad_set(a.set)
    if a.intake and not s.get("deelvragen"):
        p.error(f"set {a.set} heeft geen deelvragen")
    if a.zoekvragen and not s.get("gebeurtenis"):
        p.error(f"set {a.set} heeft geen gebeurtenis")
    meting, opmaak = (meet_zoekvragen, tabel_zoekvragen) if a.zoekvragen else \
        (meet_intake, tabel_intake) if a.intake else (meet, tabel)
    pad = SETS / a.set / "graafantwoorden.json"
    if a.aanvullen:
        graaf = AanvullendeGraaf(json.loads(pad.read_text()) if pad.exists() else {"sparql": {}, "semantisch": {}},
                                 _echte_graaf())
        try:
            rapport = meting(graaf, s)
        finally:
            graaf.close()
        pad.write_text(json.dumps(graaf.opname, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    elif a.opnemen:
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
