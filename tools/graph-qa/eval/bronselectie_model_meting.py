"""De meting van de proef `Zoekprofiel.model_kiest` (na de pilot LB3 van Lex Bench): per set de zoekvragenroute van nu
naast de route waarin een model per deelvraag kiest, live tegen de graaf en het model van de straat.

Kost modeltokens: alleen met akkoord, via `azure-infra` → `eval` met `eval_set: bronselectie_model`. Het image draagt
`docs/` niet, dus de sets komen van GitHub, van precies de commit van het image (`LEX_REVISIE`): wat gemeten wordt,
hoort bij de code die meet. Lokaal kan `--lokaal` (de sets uit de checkout), maar dan nog met een echt model en een
echte graaf.

Met `--rondes` kiest het model meer keren per set (de spreiding tussen runs), met `--varianten` meten varianten die de
pool verbreden elk één ronde, en per nodige bepaling zegt de meting waar ze afviel (`afval`). Met `--werkgebied` meet ze
naast de keuze per deelvraag ook de keuze voor het hele werkgebied (`deelvraag_keuze.PER_WERKGEBIED`), even veel rondes.
Per route telt ze ook de verkeerde deelvraag: een nodige bepaling die bij haar eigen deelvraag ontbreekt en bij een
andere staat (`bronselectie_eval.verkeerde_deelvraag`). De variant `wetstermen` meet de proef tegen de woordenkloof
(`Zoekprofiel.wetstermen`), met de afval per variant; met `--kandidaten 80+wetstermen` meet ze de kandidatenlijst zonder
de keuze door het model. De meting stopt vóór een
set als het verbruik van het model boven `MAX_TOKENS` komt. Ze schrijft geen opname weg en
wijzigt geen set: het rapport staat in de log."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from eval.bronselectie_eval import ROUTES, kandidaten_route, meet_intake, model_kiest_route
from eval.wortel import WORTEL as WORTEL_REPO

REPO = "palmw01/wetsanalyse-ai"
WORTEL = WORTEL_REPO
REFERENTIE = "docs/wetsanalyse/referentieset-bronselectie"
PILOT = "docs/lex-bench/bronselectie/pilot"
PILOTMETING = "docs/architectuur/metingen/lex-bench-2026-11-17-pilot"
#: De sets met deelvragen; `invorderbaarheid-concept` heeft er geen.
SETS = ("bestuurdersaansprakelijkheid-concept", "bezwaar-ontvankelijkheid-concept",
        "invorderbaarheid-deelvragen-concept", "kwijtschelding-concept", "rekeningafspraken-deelvragen-concept",
        "termijnen-deelvragen-concept", "verrekening-concept")
CASUSSEN = {"LB-07": "lb-07-beslistermijn", "LB-08": "lb-08-terugvordering-toeslag",
            "LB-09": "lb-09-achteraf-belasting"}
STANDAARD = "zoekvragen standaard (stap 8)"
MODEL = "model kiest (proef)"
WERKGEBIED = "model kiest per werkgebied"
#: Het plafond op het verbruik van het model over de hele meting (invoer, cache en uitvoer samen).
MAX_TOKENS = 1_500_000


def lezer(lokaal: bool):
    """Een functie pad → JSON: uit de checkout, of van GitHub op de commit van het image."""
    if lokaal:
        return lambda pad: json.loads((WORTEL / pad).read_text(encoding="utf-8"))
    revisie = os.environ.get("LEX_REVISIE", "").strip()
    if not revisie:
        raise SystemExit("LEX_REVISIE ontbreekt: zonder commit weet de meting niet welke sets bij deze code horen.")
    import httpx

    client = httpx.Client(timeout=30, follow_redirects=True)

    def lees(pad: str) -> Any:
        r = client.get(f"https://raw.githubusercontent.com/{REPO}/{revisie}/{pad}")
        r.raise_for_status()
        return r.json()
    return lees


def sets(lees) -> list[tuple[str, dict[str, Any]]]:
    """De sets van de meting: de referentiesets met deelvragen, en de drie pilotcasussen met de bevroren
    teamverwachting als verwachting (zoals `lex_bench_review._set_met_team`)."""
    from eval.lex_bench_review import _set_met_team

    uit = [(naam, lees(f"{REFERENTIE}/{naam}/set.json")) for naam in SETS]
    for casus, map_ in CASUSSEN.items():
        dossier = lees(f"{PILOT}/{map_}/set.json")
        tv = lees(f"{PILOTMETING}/{casus}/teamverwachting.json")
        uit.append((casus, _set_met_team({**dossier, "status": "concept"}, tv)))
    return uit


def _maat(r: dict[str, Any], sleutel: str) -> str:
    w = r.get(sleutel)
    return "–" if w is None else f"{w:.2f}"


#: De varianten die de pool verbreden (analyse bronselectie, 17 nov 2026): elk één ronde naast het model.
#: `wetstermen` (proef tegen de woordenkloof): één kleine modelstap per deelvraag vertaalt naar de taal van de wet; kost
#: ook in `--kandidaten` een model (~1k tokens per deelvraag).
VARIANTEN = {"definitie_brug": {"definitie_brug": True}, "verwijzingen": {"verwijzingen": True},
             "wetstermen": {"wetstermen": True}, "zonder_wetstermen": {"wetstermen": False},
             "rrf": {"menging": "rrf"}, "belang": {"belang": True},
             "zonder_belang": {"belang": False}}


def variant(naam: str) -> tuple[dict[str, Any], int | None]:
    """De vlaggen en de grens van een variant: een naam uit `VARIANTEN`, of `kandidaten_<n>` voor een andere grens dan
    `deelvraag_keuze.MAX_KANDIDATEN` (het model kiest dan uit n kandidaten)."""
    import re

    m = re.fullmatch(r"kandidaten_(\d+)", naam)
    if m:
        return {}, int(m.group(1))
    return VARIANTEN[naam], None


def met_model(variant: str) -> bool:
    """Of een kandidatenlijst (`--kandidaten`) een model nodig heeft: als het zoekprofiel met deze variant de wetstermen
    vraagt. Sinds #1707 staan ze standaard aan, dus ook de lijst zonder variant."""
    from dataclasses import replace

    from agent import deelvraag_zoeken

    return replace(deelvraag_zoeken.STANDAARD_PROFIEL, **VARIANTEN.get(variant, {})).wetstermen
#: Waar een nodige bepaling afviel, van vroeg naar laat.
FASEN = ("niet gevonden", "gevonden, niet bij de 40", "bij de 40, niet gekozen", "gekozen")


def afval(graaf: Any, s: dict[str, Any], spoor: list[dict[str, Any]]) -> dict[str, Any]:
    """Per nodige bepaling (kern of afhankelijkheid) van de set: waar ze afviel. *Gevonden* is wat de index bij de
    deelvraag vindt (`_pool`, de woordenroute vóór de rangschikking) samen met de pool rond de gebeurtenis; *bij de 40*
    is wat het model te zien kreeg; *gekozen* wat het koos. Uit het spoor van de eerste modelronde, of van een variant:
    met de vlag `wetstermen` zoekt *gevonden* ook op de termen die de variant bij die deelvraag gebruikte."""
    from agent import deelvraag_zoeken, zoekvragen, zoektermen
    from eval.bronselectie_eval import _pool, _raakt

    per_vraag = {e["vraag"]: e for e in spoor if e["set"] == s["naam"]}
    gebeurtenis: list[str] = []
    if s.get("gebeurtenis"):
        buiten = zoektermen.uitsluitstammen(zoektermen.buiten_uit_afbakening("Buiten de afbakening: " + s.get("buiten", "")))
        gebeurtenis = [k["bron_iri"] for k in zoekvragen.pool(graaf, gebeurtenis=s["gebeurtenis"], regelingen=s["regelingen"],
                                                               buiten=buiten)["kandidaten"]]
    tel = {f: 0 for f in FASEN}
    voorbeelden: dict[str, list[str]] = {f: [] for f in FASEN}
    for i, vraag in enumerate(s["deelvragen"]):
        e = per_vraag.get(vraag)
        if e is None:
            continue
        wet = e.get("wetstermen") or []
        gevonden = set(_pool(graaf, s, vraag, deelvraag_zoeken.STANDAARD_PROFIEL, **({"wetstermen": wet} if wet else {}))) \
            | set(gebeurtenis)
        for v in s["verwacht"]:
            if v["deelvraag"] != i or v["rol"] not in ("kern", "afhankelijkheid"):
                continue
            iri = v["bron_iri"]
            raakt = lambda lijst: any(_raakt(c, iri) for c in lijst)  # noqa: E731
            fase = (FASEN[3] if raakt(e["gekozen"]) else FASEN[2] if raakt(e["kandidaten"])
                    else FASEN[1] if raakt(gevonden) else FASEN[0])
            tel[fase] += 1
            if len(voorbeelden[fase]) < 4:
                voorbeelden[fase].append(f"DV{i + 1} {iri.split(':', 1)[-1]}")
    return {"telling": tel, "voorbeelden": voorbeelden}


#: De diepte waarop de rangdiagnose elke lijst opvraagt, en de vakken waarin ze een plaats telt.
DIEPTE = 400
VAKKEN = ((81, 120), (121, 200), (201, DIEPTE))


def _vak(plaats: int | None) -> str:
    if plaats is None:
        return "niet in de lijst"
    for van, tot in VAKKEN:
        if van <= plaats <= tot:
            return f"{van}–{tot}"
    return "≤80"


def rangen(graaf: Any, s: dict[str, Any], llm: Any, model: str, meting: dict[str, Any] | None,
           cache: dict[tuple, Any]) -> dict[str, Any]:
    """Waar een nodige bepaling (kern of afhankelijkheid) staat die niet bij de 80 kandidaten kwam: haar plaats in de
    woordenroute en in de pool rond de gebeurtenis, elk tot `DIEPTE` opgevraagd, met de standaard van het zoekprofiel
    (dus met wetstermen als er een model is). Zo ziet de meting of een andere menging of een langere lijst haar binnen
    kan halen, of dat ze in geen van beide lijsten staat. Een telling per vak, bv. `woorden 81–120 · pool niet in de
    lijst`. 0 tokens buiten de wetstermen, die de gedeelde cache al heeft."""
    from dataclasses import replace

    from agent import deelvraag_keuze, deelvraag_zoeken, zoekvragen, zoektermen
    from eval.bronselectie_eval import _dossier, _raakt, wetstermen_voor

    profiel = replace(deelvraag_zoeken.STANDAARD_PROFIEL, model_kiest=True, verwijzingen=False)
    dossier = _dossier(s)
    buiten = zoektermen.uitsluitstammen(zoektermen.buiten_uit_afbakening("Buiten de afbakening: " + s.get("buiten", "")))
    pool = None
    if s.get("gebeurtenis"):
        sleutel = (id(graaf), s["naam"])
        if sleutel not in cache:
            cache[sleutel] = zoekvragen.pool(graaf, gebeurtenis=s["gebeurtenis"], regelingen=s["regelingen"], buiten=buiten)
        pool = cache[sleutel]["kandidaten"]
    tel: dict[str, int] = {}
    voorbeelden: list[str] = []
    for i, vraag in enumerate(s["deelvragen"]):
        wet = wetstermen_voor(graaf, s, vraag, profiel, llm, model, meting, cache)
        woorden = [o["bron_iri"] for o in deelvraag_zoeken.bepaling_opties(
            graaf, regelingen=s["regelingen"], deelvraag=vraag, dossier=dossier, buiten=buiten, limit=DIEPTE,
            profiel=profiel, met_tekst=False, wetstermen=wet) if not o.get("buiten")]
        uit_pool = [o["bron_iri"] for o in zoekvragen.opties_bij_deelvraag(
            pool, vraag, gebeurtenis=s["gebeurtenis"], limit=DIEPTE, dossier=dossier, profiel=profiel,
            wetstermen=wet)] if pool is not None else []
        kand = [k["bron_iri"] for k in deelvraag_keuze.kandidaten(
            [{"bron_iri": x} for x in uit_pool], [{"bron_iri": x} for x in woorden])]
        for v in s["verwacht"]:
            if v["deelvraag"] != i or v["rol"] not in ("kern", "afhankelijkheid"):
                continue
            iri = v["bron_iri"]
            if any(_raakt(c, iri) for c in kand):
                continue

            def plaats(lijst: list[str]) -> int | None:
                return next((n for n, c in enumerate(lijst, 1) if _raakt(c, iri)), None)

            pw, pp = plaats(woorden), plaats(uit_pool)
            vak = f"woorden {_vak(pw)} · pool {_vak(pp)}"
            tel[vak] = tel.get(vak, 0) + 1
            if len(voorbeelden) < 4:
                voorbeelden.append(f"DV{i + 1} {iri.split(':', 1)[-1]} (woorden {pw}, pool {pp})")
    return {"telling": dict(sorted(tel.items())), "voorbeelden": voorbeelden}


def meet_kandidaten(a: argparse.Namespace) -> int:
    """De recall van de kandidatenlijst per grens (en eventueel een variant, `80+definitie_brug`), zonder keuze door het
    model: 0 tokens. Het model kiest bijna alles wat nodig is en bij de kandidaten staat, dus dit is zijn plafond. Een
    variant die een model nodig heeft (`80+wetstermen`, `met_model`) krijgt het model van de straat voor alleen die
    stap."""
    from agent.adapters.graphdb_graph import make_graph
    from agent.config import Settings

    settings = Settings.from_env()
    graaf = make_graph(settings)
    keuzes = [x for x in a.kandidaten.split(",") if x]
    llm = None
    if any(met_model(c.partition("+")[2]) for c in keuzes):
        from agent.adapters.anthropic_llm import AnthropicLLM

        llm = AnthropicLLM(settings)
    modelmeting: dict[str, Any] = {}
    routes: dict[str, Any] = {}
    # Eén cache voor alle routes: de wetstermen per deelvraag vraagt de meting zo één keer, niet per route.
    gedeeld: dict[tuple, Any] = {}
    for c in keuzes:
        grens, _, variant = c.partition("+")
        routes[c] = kandidaten_route(int(grens), VARIANTEN.get(variant) if variant else None,
                                     llm=llm if met_model(variant) else None,
                                     model=settings.llm_model, meting=modelmeting, cache=gedeeld)
    print(f"Kandidatenlijst (zonder model): {', '.join(routes)}; commit {os.environ.get('LEX_REVISIE', '') or 'lokaal'}",
          flush=True)
    som = {c: [0, 0] for c in routes}
    rapport: dict[str, Any] = {}
    rangtotaal: dict[str, int] = {}
    try:
        for naam, s in sets(lezer(a.lokaal)):
            r = meet_intake(graaf, s, routes)
            for c, v in r.items():
                som[c][0] += sum(d["gevonden_nodig"] for d in v["per_deelvraag"])
                som[c][1] += sum(d["nodig"] for d in v["per_deelvraag"])
            rapport[naam] = {c: v["recall_nodig"] for c, v in r.items()}
            print(f"{naam:40} " + " | ".join(f"{c} {_maat(v, 'recall_nodig')}" for c, v in r.items()), flush=True)
            if a.rangen:
                d = rangen(graaf, s, llm, settings.llm_model, modelmeting, gedeeld)
                for k, n in d["telling"].items():
                    rangtotaal[k] = rangtotaal.get(k, 0) + n
                print(f"{'':40} rangen: {json.dumps(d['telling'], ensure_ascii=False)} | bv. {'; '.join(d['voorbeelden'])}",
                      flush=True)
    finally:
        graaf.close()
    print("TOTAAL nodig bij de kandidaten: " + " | ".join(f"{c} {g}/{n}" for c, (g, n) in som.items()), flush=True)
    if a.rangen:
        print("RANGEN TOTAAL (nodig, niet bij de 80): " + json.dumps(rangtotaal, ensure_ascii=False), flush=True)
    if llm is not None:
        print(f"MODEL (wetstermen): {modelmeting.get('llm_calls', 0)} aanroepen, verbruik "
              f"{json.dumps(llm.meter.als_dict())}", flush=True)
    if a.json:
        a.json.write_text(json.dumps({"som": som, "sets": rapport}, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--lokaal", action="store_true", help="de sets uit de checkout in plaats van van GitHub")
    p.add_argument("--json", type=Path, help="het rapport ook als JSON wegschrijven")
    p.add_argument("--rondes", type=int, default=1, help="hoe vaak het model per set kiest (de spreiding tussen runs)")
    p.add_argument("--werkgebied", action="store_true",
                   help="ook de keuze voor het hele werkgebied (deelvraag_keuze.PER_WERKGEBIED), even veel rondes")
    p.add_argument("--varianten", default="", help="komma-gescheiden varianten uit VARIANTEN, elk één ronde")
    p.add_argument("--kandidaten", default="",
                   help="zonder model: de recall van de kandidatenlijst per grens, bv. 40,80,120 of 80+definitie_brug")
    p.add_argument("--rangen", action="store_true",
                   help="bij --kandidaten: de plaats van elke nodige bepaling die niet bij de 80 kwam, per lijst")
    a = p.parse_args(argv)
    if a.kandidaten:
        return meet_kandidaten(a)

    from agent.adapters.anthropic_llm import AnthropicLLM
    from agent.adapters.graphdb_graph import make_graph
    from agent.config import Settings

    settings = Settings.from_env()
    llm = AnthropicLLM(settings)
    graaf = make_graph(settings)
    modelmeting: dict[str, Any] = {}
    spoor: list[dict[str, Any]] = []
    spoor_wg: list[dict[str, Any]] = []
    routes: dict[str, Any] = {STANDAARD: ROUTES[STANDAARD]}
    # Eén cache voor alle modelroutes: dezelfde wetstermen per deelvraag, dus een gepaarde vergelijking.
    gedeeld: dict[tuple, Any] = {}
    for r in range(1, a.rondes + 1):
        routes[f"{MODEL} {r}"] = model_kiest_route(llm, settings.llm_model, modelmeting, spoor=spoor if r == 1 else None,
                                                   cache=gedeeld)
    if a.werkgebied:
        for r in range(1, a.rondes + 1):
            routes[f"{WERKGEBIED} {r}"] = model_kiest_route(llm, settings.llm_model, modelmeting, werkgebied=True,
                                                            cache=gedeeld,
                                                            spoor=spoor_wg if r == 1 else None)
    sporen: dict[str, list[dict[str, Any]]] = {}
    for v in [x for x in a.varianten.split(",") if x]:
        sporen[v] = []
        vlaggen, limit = variant(v)
        routes[f"variant {v}"] = model_kiest_route(llm, settings.llm_model, modelmeting, vlaggen=vlaggen,
                                                   spoor=sporen[v], limit=limit, cache=gedeeld)
    print(f"Bronselectie: {', '.join(routes)}; model {settings.llm_model}, "
          f"commit {os.environ.get('LEX_REVISIE', '') or 'lokaal'}", flush=True)
    rapport: dict[str, Any] = {}
    totaal_afval = {f: 0 for f in FASEN}
    afval_variant = {v: {f: 0 for f in FASEN} for v in sporen}
    totaal_afval_wg = {f: 0 for f in FASEN}
    totaal_verkeerd: dict[str, int] = {}
    try:
        for naam, s in sets(lezer(a.lokaal)):
            if llm.meter.totaal > MAX_TOKENS:
                print(f"STOP: het verbruik ({llm.meter.totaal}) is boven {MAX_TOKENS}; {naam} en verder niet gemeten.",
                      flush=True)
                break
            r = meet_intake(graaf, s, routes)
            modellen = [r[k]["recall_nodig"] or 0.0 for k in r if k.startswith(MODEL)]
            prec = [r[k]["precisie"] or 0.0 for k in r if k.startswith(MODEL)]
            val = afval(graaf, s, spoor)
            for f, n in val["telling"].items():
                totaal_afval[f] += n
            val_wg = afval(graaf, s, spoor_wg) if a.werkgebied else None
            for f, n in (val_wg or {}).get("telling", {}).items():
                totaal_afval_wg[f] += n
            for k, v in r.items():
                totaal_verkeerd[k] = totaal_verkeerd.get(k, 0) + v["verkeerde_deelvraag"]
            rapport[naam] = {"routes": {k: {m: v[m] for m in ("recall_nodig", "recall", "precisie", "aantal",
                                                               "verkeerde_deelvraag", "verkeerd")}
                                        | {"per_deelvraag": [{"opties": d["opties"]} for d in v["per_deelvraag"]]}
                                        for k, v in r.items()},
                             "afval": val, **({"afval_werkgebied": val_wg} if val_wg else {})}
            for v, sp in sporen.items():
                val_v = afval(graaf, s, sp)
                rapport[naam][f"afval {v}"] = val_v
                for f, n in val_v["telling"].items():
                    afval_variant[v][f] += n
                print(f"{'':40} afval {v}: " + ", ".join(f"{f} {n}" for f, n in val_v["telling"].items()), flush=True)
            varianten = " | ".join(f"{k.removeprefix('variant ')} {_maat(v, 'recall_nodig')}"
                                   for k, v in r.items() if k.startswith("variant "))
            print(f"{naam:40} nodig {_maat(r[STANDAARD], 'recall_nodig')} → model gem. {sum(modellen) / len(modellen):.2f}"
                  f" ({min(modellen):.2f}–{max(modellen):.2f})"
                  f" | precisie {_maat(r[STANDAARD], 'precisie')} → {sum(prec) / len(prec):.2f}"
                  + (f" | {varianten}" if varianten else "")
                  + f" | verbruik tot nu {llm.meter.totaal}", flush=True)
            if a.werkgebied:
                wg = [r[k]["recall_nodig"] or 0.0 for k in r if k.startswith(WERKGEBIED)]
                wg_prec = [r[k]["precisie"] or 0.0 for k in r if k.startswith(WERKGEBIED)]
                print(f"{'':40} per werkgebied: nodig gem. {sum(wg) / len(wg):.2f} ({min(wg):.2f}–{max(wg):.2f})"
                      f" | precisie {sum(wg_prec) / len(wg_prec):.2f}", flush=True)
            print(f"{'':40} verkeerde deelvraag: " + " | ".join(f"{k} {v['verkeerde_deelvraag']}" for k, v in r.items()),
                  flush=True)
            print(f"{'':40} afval: " + ", ".join(f"{f} {n}" for f, n in val["telling"].items())
                  + " | niet gevonden bv. " + "; ".join(val["voorbeelden"][FASEN[0]]), flush=True)
            if val_wg:
                print(f"{'':40} afval per werkgebied: " + ", ".join(f"{f} {n}" for f, n in val_wg["telling"].items()),
                      flush=True)
    finally:
        graaf.close()
    print("AFVAL TOTAAL: " + ", ".join(f"{f} {n}" for f, n in totaal_afval.items()), flush=True)
    for v, tel in afval_variant.items():
        print(f"AFVAL TOTAAL {v}: " + ", ".join(f"{f} {n}" for f, n in tel.items()), flush=True)
    if a.werkgebied:
        print("AFVAL TOTAAL PER WERKGEBIED: " + ", ".join(f"{f} {n}" for f, n in totaal_afval_wg.items()), flush=True)
    print("VERKEERDE DEELVRAAG TOTAAL: " + " | ".join(f"{k} {n}" for k, n in totaal_verkeerd.items()), flush=True)
    print(f"MODEL: {modelmeting.get('llm_calls', 0)} aanroepen, verbruik {json.dumps(llm.meter.als_dict())}", flush=True)
    if a.json:
        a.json.write_text(json.dumps({"verbruik": llm.meter.als_dict(), "afval": totaal_afval,
                                      "afval_werkgebied": totaal_afval_wg, "verkeerde_deelvraag": totaal_verkeerd,
                                      "afval_varianten": afval_variant,
                                      "sets": rapport},
                                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
