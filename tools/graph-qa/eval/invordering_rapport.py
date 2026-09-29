"""Controleer en vergelijk de bevroren proef, zonder model- of graafaanvragen."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import median

from eval.invordering_proef import MEETMAP, ONDERZOEK, TOKENS, VARIANTEN, controleer_cases, schrijf, sha


def lees(p):
    return json.loads(p.read_text())


def cel(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def sleutel(v):
    return tuple((a["bron_iri"], a["start"], a["eind"]) for a in v["ankers"]) + (v["klasse"],)


def laad_runs():
    runs = []
    for p in sorted((MEETMAP / "modelruns").glob("[123]-*.json")):
        r = lees(p)
        herstel = p.parent / "snapshot-herstel" / p.name
        if herstel.exists():
            nieuw = lees(herstel)
            if nieuw["herstel"]["origineel_sha256"] != hashlib.sha256(p.read_bytes()).hexdigest():
                raise ValueError("oorspronkelijke poging veranderd na herstel")
            if nieuw["calls"][:len(r["calls"])] != r["calls"] or nieuw["fusie"] != r["fusie"]:
                raise ValueError("snapshotreplay veranderde oorspronkelijke reacties of detectie")
            r, p = nieuw, herstel
        runs.append({**r, "_bestand": str(p.relative_to(MEETMAP / "modelruns"))})
    return runs


def valideer_runs(pakket, runs, manifest, *, volledig=True):
    controleer_cases(pakket)
    cases = {c["id"]: c for c in pakket["casussen"]}
    verwacht = {(c, v, n) for c in cases for v in VARIANTEN for n in range(1, 4)}
    werkelijk = {(r["casus"], r["variant"], r["ronde"]) for r in runs}
    if (not werkelijk <= verwacht or len(werkelijk) != len(runs)
            or volledig and (werkelijk != verwacht or len(runs) != 72)):
        raise ValueError(f"verwacht precies 72 unieke pogingen; gevonden {len(runs)}")
    fusies = {}
    for r in runs:
        if r["casussen_sha256"] != pakket["casussen_sha256"]:
            raise ValueError("run heeft andere bronnen")
        versie = "baseline" if r["variant"] == VARIANTEN[0] else "variant"
        if r["code_sha256"] != manifest["code"][versie] or r["model"] != "claude-sonnet-4-6":
            raise ValueError("code/model gewisseld")
        if r["tokens"] != {k: sum(c.get("tokens", {}).get(k, 0) for c in r["calls"]) for k in TOKENS}:
            raise ValueError("tokentelling wijkt af")
        if r["status"] != "ok":
            continue  # blijft een mislukte primaire poging, nooit een stille vervanging
        if r["meting"]["gedegradeerd"]:
            raise ValueError("onverwachte terugvalparse")
        nodes = {n["bron_iri"]: n for n in cases[r["casus"]]["snapshot"]["segmenten"]}
        def controleer_span(a):
            n = nodes[a["bron_iri"]]
            if not (0 <= a["start"] < a["eind"] <= len(n["tekst"])) or n["tekst"][a["start"]:a["eind"]] != a["tekst"] or a["bron_hash"] != n["bron_hash"]:
                raise ValueError("fragment is niet brongetrouw")
        for k in r["fusie"]["kandidaten"]:
            controleer_span(k["span"])
            for o in k["span_options"]:
                controleer_span(o["span"])
        for v in r["voorstellen"]:
            for a in v["ankers"]:
                controleer_span(a)
        versies = {(d["detector"], d["versie"]) for d in r["meting"]["detectorresultaten"]}
        if versie == "variant":
            versies.add(("fusie", r["meting"]["fusie_versie"]))
            context = r["meting"]["broncontext"]
            verwacht_context = cases[r["casus"]]["context"] if r["variant"] == "C_context" else []
            if [(x["bron_iri"], x["bron_hash"]) for x in context["passages"]] != [(x["bron_iri"], x["bron_hash"]) for x in verwacht_context]:
                raise ValueError("aangeboden context wijkt af")
        if any((b["detector"], b["versie"]) not in versies for b in r["fusie"]["bijdragen"]):
            raise ValueError("bijdrage heeft onjuiste detectorversie")
        # B en C verschillen alleen in modelcontext, nooit in detectie.
        key = (r["casus"], versie)
        h = sha(r["fusie"])
        if key in fusies and fusies[key] != h:
            raise ValueError("detectie niet reproduceerbaar")
        fusies[key] = h


def samenvatting(rs):
    ok = [r for r in rs if r["status"] == "ok"]
    calls = [c for r in rs for c in r["calls"]]
    retries = sum(sum(n - 1 for n in Counter(c["verzoek_sha256"] for c in r["calls"]
                    if c["verzoek"]["tools"][0]["name"] == "classificeer").values()) for r in rs)
    return {
        "pogingen": len(rs), "geslaagd": len(ok), "mislukt": len(rs) - len(ok),
        "calls": len(calls), "calls_mislukt": sum(c["status"] != "ok" for c in calls),
        "classifier_calls": sum(c["verzoek"]["tools"][0]["name"] == "classificeer" for c in calls),
        "review_calls": sum(c["verzoek"]["tools"][0]["name"] == "beoordeel" for c in calls),
        "classifier_herpogingen": retries,
        "tokens": {k: sum(r["tokens"][k] for r in rs) for k in TOKENS},
        "kosten_schatting_usd": round(sum(r["kosten"]["schatting_usd"] for r in rs), 6),
        "mediaan_seconden": round(median(r["seconden"] for r in rs), 3),
        "voorstellen": sum(len(r["voorstellen"]) for r in ok),
        "menselijk": sum(v["trace"]["beslissing"]["status"] == "HUMAN_REVIEW" for r in ok for v in r["voorstellen"]),
        "beslisstatus": dict(Counter(b["status"] for r in ok for b in r["beslissingen"])),
        "twijfels": dict(Counter(t["reden"] for r in ok for t in r["meting"]["twijfels"])),
        "resolutieregels": dict(Counter(t["regel"] for r in ok for t in r["meting"]["resolutie"])),
        "technische_classifier_twijfels": dict(Counter(t["categorie"] for r in ok
                for t in r["meting"]["twijfels"] if t["reden"] == "CLASSIFIER_ABSTAIN")),
        "ongeldige_reviewoordelen": sum(t["regel"] == "R-ONGELDIG" for r in ok for t in r["meting"]["resolutie"]),
        "validatiefouten": dict(Counter(t["code"] for r in ok for t in r["meting"]["validatie"] if t["ernst"] == "fout")),
        "snapshot_herstelde_pogingen": sum("herstel" in r for r in rs),
        "ontdubbelde_tijdgrenzen": sum(len(r["meting"].get("alternatieve_tijdgrenzen", {})) for r in ok),
        "stopredenen": dict(Counter(c.get("antwoord", {}).get("stop_reason", "fout") for c in calls)),
    }


def stabiliteit(rs):
    sets = [{sleutel(v) for v in r.get("voorstellen", [])} for r in rs if r["status"] == "ok"]
    if not sets:
        return {"geslaagde_runs": 0}
    union, inter = set.union(*sets), set.intersection(*sets)
    statussen = [{(sleutel(v), v["trace"]["beslissing"]["status"]) for v in r["voorstellen"]}
                 for r in rs if r["status"] == "ok"]
    return {"geslaagde_runs": len(sets), "unie": len(union), "doorsnede": len(inter),
            "alle_runs_gelijk": all(s == sets[0] for s in sets),
            "status_stabiel": all(s == statussen[0] for s in statussen),
            "menselijk_per_run": [sum(v["trace"]["beslissing"]["status"] == "HUMAN_REVIEW"
                for v in r["voorstellen"]) for r in rs if r["status"] == "ok"],
            "doorsnede_door_unie": len(inter) / len(union) if union else 1.0,
            "aantallen": [len(s) for s in sets]}


def modelrapport(pakket, runs, manifest):
    valideer_runs(pakket, runs, manifest)
    totaal = {v: samenvatting([r for r in runs if r["variant"] == v]) for v in VARIANTEN}
    per = {c["id"]: {v: stabiliteit([r for r in runs if r["casus"] == c["id"] and r["variant"] == v])
                      for v in VARIANTEN} for c in pakket["casussen"]}
    md = ["# Modelvergelijking: 72 primaire pogingen", "",
          "A = baseline b8117e2; B = a0699a5 met lege aanvullende context; C = dezelfde code met vooraf bevroren graafcontext. Drie pogingen per variant en casus. Volgorde per ronde A/B/C, B/C/A, C/A/B. Geen uitrol of opslag van annotaties.", "",
          "Een voorstel voor menselijke beoordeling telt als voorstel, niet als juridisch geaccepteerd element. Stabiliteit vergelijkt bron-IRI + exacte offsets + klasse; zij bewijst geen juistheid. Mislukte pogingen worden afzonderlijk geteld en niet vervangen.", "",
          "| Variant | Pogingen / geslaagd | Calls (review) | Voorstellen (menselijk) | Mediaan s/run | Kostenraming USD |",
          "|---|---:|---:|---:|---:|---:|"]
    for v, s in totaal.items():
        md.append(f'| {v} | {s["pogingen"]} / {s["geslaagd"]} | {s["calls"]} ({s["review_calls"]}) | {s["voorstellen"]} ({s["menselijk"]}) | {s["mediaan_seconden"]} | {s["kosten_schatting_usd"]:.4f} |')
    md += ["", "Kosten zijn een raming uit de gerapporteerde input-, output- en cachetokens en de in elk runbestand opgenomen lijstprijs; geen Azure-factuur. SDK-retries staan op nul; de bestaande classifier mag één identieke herpoging doen bij ontbrekende tooluitvoer. Deze herpogingen worden apart geteld. Eventuele mislukte pipelinepogingen blijven in de noemer. De adapter kan bij een geweigerd cachepunt eenmaal zonder caching herhalen; de vastgelegde calls meten adapteraanroepen, geen netwerkverkeer.", "",
           "De eerste zes pogingen draaiden sequentieel. Daarna zijn maximaal drie onafhankelijke casussen tegelijk uitgevoerd, met een barrière tussen de rondes en dezelfde variantrotatie per casus. Zie `modelruns/planner.json`. Latentie is daardoor mede afhankelijk van parallelisme en is geen zuivere snelheidsbenchmark.", "",
           "Tijdens ronde 1 bleek de lokale onderzoekssnapshot van de controles niet afgesloten: de hoogste geselecteerde ouder verwees naar de niet meegeleverde regelingwortel. Dit gaf `V_ANKER`, onafhankelijk van de modelkeuze. De lokale boom is expliciet afgebakend, met behoud van de echte externe graafouder, teksten, offsets, directe oudercontext en alle primaire reacties. De betrokken pogingen zijn zonder herhaalde classificatie gereplayed; hun oorspronkelijke bestanden blijven bewaard. `modelruns/correctie-snapshot.json` en `snapshot-herstel/` registreren deze correctie. De vergelijking gebruikt de herstelde uitvoer en telt iedere primaire poging eenmaal. Dit was een fout in de proefopbouw, geen juridische afwijzing en geen gewijzigde productvalidator.", "",
           "## Herhaalbaarheid", "", "Aantallen zijn de drie runs in rondevolgorde. ‘Vast/unie’ is het aantal voorstellen dat in alle geslaagde runs terugkomt, gedeeld door alle verschillende voorstellen.", "",
           "| Casus | A: aantallen; vast/unie | B: aantallen; vast/unie | C: aantallen; vast/unie |", "|---|---|---|---|"]
    for cid, ps in per.items():
        cols = [f'{p.get("aantallen", [])}; {p.get("doorsnede", 0)}/{p.get("unie", 0)}' for p in ps.values()]
        md.append("| " + " | ".join([cid, *cols]) + " |")
    md += ["", "De volledige toegevoegde, verdwenen, anders geklasseerde en wisselende voorstellen staan in [het beoordelingsdossier](model-dossier.md). [De machineleesbare vergelijking](model-vergelijking.json) bevat ook tokens, besluitstatus, twijfels en resolutieregels.", ""]
    return {"status": "diagnostisch_geen_gold", "manifest": manifest, "varianten": totaal, "casussen": per}, "\n".join(md)


def dossier(pakket, runs):
    md = ["# Beoordelingsdossier van alle modeluitvoer", "",
          "Elke rij is één bronspan + klasse, ook als die slechts eenmaal voorkomt. Per variant staat het aantal geaccepteerde voorstellen (a) en menselijke twijfelgevallen (m), op drie pogingen. B−A en C−B zijn waarnemingen op de unie van drie runs; geen causale of juridische score. Een andere grens/klasse staat als aparte rij. De broncodepoint-offsets zijn halfopen [start,eind).", ""]
    for c in pakket["casussen"]:
        rs = sorted([r for r in runs if r["casus"] == c["id"]], key=lambda r: (r["ronde"], r["variant"]))
        md += [f'## {c["id"]}', "", "Bron(nen):"]
        for n in c["snapshot"]["segmenten"]:
            md += ["", f'`{n["bron_iri"]}` · SHA256 `{n["bron_hash"]}`', "", "> " + n["tekst"].replace("\n", "\n> ")]
        md += ["", "Runbestanden met volledige prompts, reacties, bijdragen en besluiten:", "",
               ", ".join(f'[{r["variant"]} ronde {r["ronde"]}](modelruns/{r["_bestand"]})' for r in rs), "",
               "| Offset | Fragment | Klasse | A (a/m) | B (a/m) | C (a/m) | Verschil in aanwezigheid |",
               "|---|---|---|---:|---:|---:|---|"]
        waarden, telling = {}, Counter()
        for r in rs:
            for v in r.get("voorstellen", []):
                k = sleutel(v)
                waarden[k] = v
                telling[k, r["variant"], v["trace"]["beslissing"]["status"]] += 1
        for k in sorted(waarden):
            v = waarden[k]
            aant = [(telling[k, var, "ACCEPTED"], telling[k, var, "HUMAN_REVIEW"]) for var in VARIANTEN]
            wijzigingen = []
            for i, naam in [(1, "B−A"), (2, "C−B")]:
                x, y = sum(aant[i-1]), sum(aant[i])
                if not x and y: wijzigingen.append(naam + " toegevoegd")
                elif x and not y: wijzigingen.append(naam + " verdwenen")
                elif aant[i-1] != aant[i]: wijzigingen.append(naam + " wisselend/status")
            offset = ", ".join(f'[{a["start"]},{a["eind"]})' for a in v["ankers"])
            md.append("| " + " | ".join([offset, cel(v["tekst"]), v["klasse"],
                *[f"{a}/{m}" for a, m in aant], "; ".join(wijzigingen) or "behouden"]) + " |")
        md += ["", "Gerichte herbeoordelingen en technische uitval:", ""]
        regels = []
        for r in rs:
            if r["status"] != "ok":
                regels.append(f'- {r["variant"]} ronde {r["ronde"]}: poging mislukt ({r.get("fout")}).')
            for t in r.get("meting", {}).get("resolutie", []):
                toelichting = t.get("motivering") or t.get("ongeldig_omdat") or "Geen motivering in het oorspronkelijke besluitregister."
                regels.append(f'- {r["variant"]} ronde {r["ronde"]}, {t["label"]}: {t["regel"]}. {toelichting}')
        md += regels or ["Geen gerichte herbeoordeling in deze pogingen."]
        md.append("")
    return "\n".join(md)


def detectierapport():
    voor, na = lees(ONDERZOEK / "meting.json"), lees(MEETMAP / "04-bevroren-keten.json")
    md = ["# Deterministische detectieverschillen", "", "De oorspronkelijke onderzoeksmeting blijft ongewijzigd. Labels zijn geen vergelijkingssleutel: hieronder worden bron + offsets vergeleken. Verschillen in bewijs en routing tellen afzonderlijk. Geen live modelaanvragen in deze vergelijking.", ""]
    for cid, nieuw in na["casussen"].items():
        oud = voor["casussen"][cid]
        md += [f"## {cid}", "", f'Tellingen (raw/fusie/model): {oud["tellingen"]["raw"]}/{oud["tellingen"]["fusie"]}/{oud["tellingen"]["model"]} → {nieuw["tellingen"]["raw"]}/{nieuw["tellingen"]["fusie"]}/{nieuw["tellingen"]["model"]}.', ""]
        md += kandidaatverschillen(oud["kandidaten"], nieuw["kandidaten"])
    dev = lees(MEETMAP / "ontwikkelcontrole-na.json")["vergelijking"]
    md += ["## Bestaande ontwikkelcontrole", "", "Deze zestien historische fixtures zijn uitsluitend regressiecontrole, niet de bron voor de modelproef. Freeze en referentieset v1 zijn ongewijzigd. Alle volledige parses blijven gelijk. De systeemprompt is veranderd en daardoor wijzigt bij iedere casus de classifierinvoer, ook zonder kandidaatwijziging.", "", "262 kandidaten blijven 262; kernankers met klasse 73/81 → 72/81; inclusief opties 75/81 → 74/81; regelbesluiten 19 en modelkandidaten 243 blijven gelijk. WZT01/E11 verliest de eerdere samengestelde hoofdspan: de gedeelde segmentgrens stopt nu vóór de zelfstandige fictiebepaling na de puntkomma. Dit is een bewuste functionele grenswijziging, geen ongemerkt gerepareerde referentie. Het oude brede anker blijft in referentieset v1 staan.", ""]
    for cid, d in dev["per_casus"].items():
        md += [f"### {cid}", ""]
        if d["kandidaten"]:
            md += kandidaatverschillen([x["voor"] for x in d["kandidaten"] if x["voor"]],
                                       [x["na"] for x in d["kandidaten"] if x["na"]])
        else:
            md += ["Kandidaten, klassen, bewijs, opties en routing gelijk; alleen de systeemprompt wijzigt.", ""]
    return "\n".join(md)


def kandidaatverschillen(voor, na):
    def key(k): return k["bron"], k["start"], k["eind"]
    def zonderlabel(k): return {n: v for n, v in k.items() if n != "label"} if k else None
    a, b = {key(k): k for k in voor}, {key(k): k for k in na}
    md = ["| Offset | Fragment | Voor: klassen / route | Na: klassen / route | Verklaring |", "|---|---|---|---|---|"]
    for k in sorted(a.keys() | b.keys()):
        x, y = a.get(k), b.get(k)
        if zonderlabel(x) == zonderlabel(y): continue
        bewijs = {e["code"] for c in (x, y) if c for e in c["bewijs"]}
        if "TEMPORAL_KERNEL" in bewijs: reden = "Expliciete temporele kernhypothese met oorspronkelijke bijdrage; specificiteit opnieuw toegepast."
        elif "CALCULATION_QUANTITY" in bewijs: reden = "Aantalregel: berekende uitkomst en resterende invoer."
        elif "CALCULATION_APPLICABILITY" in bewijs: reden = "Afzonderlijke terugverwijzende toepassingskeuze."
        elif "CALCULATION_ASSIGNMENT" in bewijs: reden = "Passieve toewijzing met benoemde grootheid, omgekeerde woordvolgorde."
        elif "CALCULATION_CALENDAR_POSITION" in bewijs: reden = "Afleiding van vervaldag uit gelijke kalenderpositie."
        elif "TEMPORAL_DESCRIPTION" in bewijs: reden = "Volledige relatieve datumomschrijving."
        elif "TEMPORAL_DATE" in bewijs: reden = "Geldige dag/maand zonder verplicht jaartal."
        elif "TEMPORAL_MONTH" in bewijs: reden = "Maandbepaling inclusief eerder/later."
        elif "TEMPORAL_RECURRENCE" in bewijs: reden = "Herhaalde relatieve termijn."
        elif "CONDITIONAL_ELLIPSIS" in bewijs: reden = "Elliptische voorwaarde met governor."
        elif "NOMINALIZED_ACTION" in bewijs: reden = "Nominalisatie stopt vóór zelfstandige/distributieve vervolgregel."
        elif any(e.startswith("CALCULATION_") for e in bewijs): reden = "Afleiding gebruikt beschermde segmentgrenzen, inclusief grens bij puntkomma."
        elif bewijs & {"TEMPORAL_PERIOD_NOUN", "TEMPORAL_RELATIVE_PERIOD"}: reden = "Maand-/kalenderperiodeherkenning uitgebreid."
        else: reden = "Bewijs/klasseruimte gewijzigd; zie volledige voor/na-rijen in het meetbestand."
        def oms(c): return cel(", ".join(c["possible_classes"]) + " / " + c["route"]) if c else "—"
        md.append(f'| [{k[1]},{k[2]}) | {cel((y or x)["tekst"])} | {oms(x)} | {oms(y)} | {reden} |')
    return md + [""]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detectie", action="store_true")
    parser.add_argument("--monitor", action="store_true", help="controleer aanwezige pogingen zonder bestanden te schrijven")
    args = parser.parse_args()
    if args.detectie:
        with (MEETMAP / "detectieverschillen.md").open("x") as f:
            f.write(detectierapport())
        return
    bestanden = sorted((MEETMAP / "modelruns").glob("[123]-*.json"))
    runs = laad_runs()
    pakket, manifest = lees(MEETMAP / "proef-bronnen.json"), lees(MEETMAP / "modelruns/manifest.json")
    if args.monitor:
        valideer_runs(pakket, runs, manifest, volledig=False)
        print(json.dumps({"pogingen": len(runs), "rondes": dict(Counter(r["ronde"] for r in runs)),
            "varianten": {v: samenvatting([r for r in runs if r["variant"] == v]) for v in VARIANTEN}}, indent=2))
        return
    data, md = modelrapport(pakket, runs, manifest)
    data["planner"] = lees(MEETMAP / "modelruns/planner.json")
    data["snapshot_correctie"] = lees(MEETMAP / "modelruns/correctie-snapshot.json")
    data["herstelbestanden_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (MEETMAP / "modelruns/snapshot-herstel").glob("*.json")}
    data["runbestanden_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in bestanden}
    schrijf(MEETMAP / "model-vergelijking.json", data)
    for naam, tekst in [("model-vergelijking.md", md), ("model-dossier.md", dossier(pakket, runs))]:
        with (MEETMAP / naam).open("x") as f:
            f.write(tekst)


if __name__ == "__main__":
    main()
