"""Offline onderzoek van vier graafteksten; geen model-, graaf- of opslagaanroepen.

Run: python -m eval.onderzoek_invordering --output /tmp/invordering-meting.json
De bevroren graafsnapshots zijn de enige tekstbron. XML/web worden niet ingelezen.
Conceptfuncties zijn onderzoekshypothesen, nooit gold of een recallnoemer.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from bronmodel import CorpusMap, valideer_ankers

from agent.config import Settings
from agent.jas_klassen import GELDIGE_JAS_KLASSEN
from agent.jas_pipeline.besluit import deterministisch, uit_modelkeuze
from agent.jas_pipeline.classificatie import TOOL, systeemprompt, toolschema, userprompt
from agent.jas_pipeline.dekking import structureel
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from agent.jas_pipeline.keten import analyseer
from agent.jas_pipeline.onzekerheid import signaleer
from agent.jas_pipeline.taal import SpacyProvider
from eval.detector_audit import rij, samen_voordat_specificiteit

ROOT = Path(__file__).resolve().parents[3]
DOSSIER = ROOT / "docs/wetsanalyse/onderzoek-invordering-2026-09-29"
CASUSSEN = ("IW-9-1", "IW-9-5", "LI-9.1", "LI-9.5")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def controleer_bronnen(pakket):
    if tuple(c["id"] for c in pakket["casussen"]) != CASUSSEN:
        raise ValueError("onderzoek vereist precies de vier afgesproken ontwikkelcasussen")
    ids, iris = set(), set()
    for c in [*pakket["casussen"], *pakket["contextpassages"]]:
        if c["herkomst"] != "graaf":
            raise ValueError("analysetekst moet uit de graaf komen")
        if sha(c["tekst"].encode()) != c["bron_hash"]:
            raise ValueError(f"bronhash wijkt af: {c['id']}")
        if c["id"] in ids or c["bron_iri"] in iris:
            raise ValueError("dubbele bronidentiteit")
        ids.add(c["id"])
        iris.add(c["bron_iri"])
    budget = pakket["contextbudget"]
    if budget["gebruikt"] != len(pakket["contextpassages"]) or budget["gebruikt"] > budget["maximum"]:
        raise ValueError("contextbudget klopt niet")


def controleer_concepten(pakket, concepten):
    bronnen = {c["id"]: c for c in pakket["casussen"]}
    if set(concepten) != set(bronnen):
        raise ValueError("conceptdossier ontbreekt")
    for cid, dossier in concepten.items():
        if dossier["status"] != "concept_niet_geadjudiceerd":
            raise ValueError("onderzoek mag geen gold suggereren")
        if set(dossier["klassenbeoordeling"]) != set(GELDIGE_JAS_KLASSEN):
            raise ValueError("beoordeel alle dertien klassen")
        c = bronnen[cid]
        ids = set()
        for e in dossier["elementen"]:
            if e["id"] in ids:
                raise ValueError("dubbel concept-id")
            ids.add(e["id"])
            if not 0 <= e["start"] < e["eind"] <= len(c["tekst"]):
                raise ValueError("conceptgrens buiten de eigen node")
            if c["tekst"][e["start"]:e["eind"]] != e["tekst"]:
                raise ValueError("concepttekst is geen exact bronfragment")
            if any(k not in GELDIGE_JAS_KLASSEN for k in e["mogelijke_klassen"]):
                raise ValueError("onbekende conceptklasse")


def snapshot(c):
    node = {k: c[k] for k in ("bron_iri", "parent_iri", "tekst", "bron_hash", "type", "nummer", "volgorde")}
    parent = {"bron_iri": c["parent_iri"], "tekst": c["ouder_context"], "parent_iri": "",
              "volgorde": 0, "type": "Artikel"}
    return {"schema_versie": 2, "snapshot_id": sha(json.dumps(node, sort_keys=True).encode()),
            "doel": node, "nodes": [parent, node], "segmenten": [node]}


class KeuzeFake:
    """Een expliciete besliskaart door de echte classifier/review/validatie laten lopen.

    Dit bewijst transport van aangeleverde keuzes, geen juridische modelkwaliteit.
    Geen standaardacceptatie: onbekende labels wijzen we af. Review volgt alleen
    bewust weggelaten classifierlabels en kiest de opgegeven klasse.
    """

    def __init__(self, keuzes, via_review=()):
        self.keuzes = keuzes
        self.via_review = set(via_review)
        self.calls = []

    def create(self, **request):
        self.calls.append(request)
        tool = request["tools"][0]
        schema = tool["input_schema"]["properties"]
        if tool["name"] == TOOL:
            labels = schema["beslissingen"]["items"]["properties"]["kandidaat"]["enum"]
            payload = {"beslissingen": [
                {"kandidaat": label, "beslissing": self.keuzes.get(label, GEEN_ANNOTATIE), "optie": ""}
                for label in labels if label not in self.via_review]}
        else:
            labels = schema["oordelen"]["items"]["properties"]["geval"]["enum"]
            payload = {"oordelen": [{"geval": label, "actie": "CHANGE" if self.keuzes.get(label, GEEN_ANNOTATIE) != GEEN_ANNOTATIE else "KEEP",
                                       "klasse": self.keuzes.get(label, "") if self.keuzes.get(label) != GEEN_ANNOTATIE else "",
                                       "motivering": "Vastgelegde keuze in de offline transportproef."}
                                    for label in labels]}
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name=tool["name"], input=payload)])


def speel(c, keuzes, via_review=()):
    snap = snapshot(c)
    kaart = CorpusMap(snap["segmenten"])
    fake = KeuzeFake(keuzes, via_review)
    uit = analyseer(snapshot=snap, corpus_segmenten=kaart.als_dicts(), corpus=kaart.corpus,
                   llm=fake, model="offline-besliskaart-geen-model",
                   settings=Settings(taal_provider="spacy:nl_core_news_md", deterministisch_accepteren=True,
                                     gerichte_review=True, classifier_spankeuze=False,
                                     classifier_granulariteit="universeel"))
    for v in uit.voorstellen:
        valideer_ankers(snap, v["ankers"])
    return uit, fake


def conceptbereik(elementen, kandidaten):
    """Exacte hypothese-bereikbaarheid; overlap alleen nooit als gevonden tellen."""
    uit = []
    for e in elementen:
        core = [k for k in kandidaten if (k.span.start, k.span.eind) == (e["start"], e["eind"])]
        options = [k for k in kandidaten if any((o.span.start, o.span.eind) == (e["start"], e["eind"])
                                               for o in k.span_options)]
        uit.append({"concept": e["id"], "status": e["status"], "kern": [k.label for k in core],
                    "optie": [k.label for k in options],
                    "klassen_op_kern": sorted({cl for k in core for cl in k.possible_classes} & set(e["mogelijke_klassen"])),
                    "klassen_op_optie": sorted({cl for k in options for cl in k.possible_classes} & set(e["mogelijke_klassen"]))})
    return uit


def dossiers_markdown(pakket, concepten, meting):
    def cel(s):
        return str(s).replace("|", "\\|").replace("\n", " ")

    regels = ["# Vier conceptdossiers", "",
              "Status: concept, niet geadjudiceerd. Geen minimale aantallen of volledige gold-set. "
              "Alle fragmenten komen uit de graaf, in [bronnen.json](bronnen.json). "
              "De 60 onderzoeksitems omvatten voorstellen, alternatieven, relaties en expliciete uitsluitingen; "
              "ze zijn geen 60 verwachte annotaties.", "",
              "`voorstel` = onderbouwde werkhypothese; `open` = afzonderlijke juridische beoordeling; "
              "`samenhang` = relatie/context zonder verplicht extra label; `uitsluiten` = gemotiveerd negatief geval. "
              "Meerdere klassen zijn alternatieven tenzij de motivering verschillende functies onderscheidt. "
              "Kern/optie gaat alleen over exacte grenzen; afwezige kerngrenzen bewijzen niet dat iedere overlappende "
              "systeemmarkering onjuist is.", ""]
    for c in pakket["casussen"]:
        d = concepten[c["id"]]
        bereik = {r["concept"]: r for r in meting["casussen"][c["id"]]["conceptbereik"]}
        regels += [f"## {c['id']}", "", f"Bron: `{c['bron_iri']}`; {c['juridische_status']}; graaftoestand {c['toestand']}.",
                   "", "> " + c["tekst"], "", d["interpretatie"], "", "### Elementen en functies", "",
                   "| ID | Bereik [start,eind) en fragment | Mogelijke klasse | Beoordeling | Functie | Exacte kandidaat/optie |",
                   "|---|---|---|---|---|---|"]
        for e in d["elementen"]:
            b = bereik[e["id"]]
            kandidaten = ", ".join(b["kern"]) or "geen kern"
            if b["optie"]:
                kandidaten += "; optie: " + ", ".join(b["optie"])
            kandidaten += "; passende kernklasse: " + (", ".join(b["klassen_op_kern"]) or "geen")
            regels.append("| " + " | ".join(map(cel, [e["id"], f"[{e['start']},{e['eind']}) {e['tekst']}",
                                                      ", ".join(e["mogelijke_klassen"]) or "bronrelatie", e["status"],
                                                      e["functie"], kandidaten])) + " |")
        regels += ["", "### Alle dertien klassen beoordeeld", "", "| Klasse | Beoordeling |", "|---|---|"]
        regels += [f"| {cel(k)} | {cel(v)} |" for k, v in d["klassenbeoordeling"].items()]
        regels += ["", "### Open beoordelingsvragen", "", *["- " + v for v in d["reviewvragen"]], ""]
    regels += ["## Geraadpleegde contextpassages", "",
               "Deze vijftien passages zijn uit dezelfde graafophaling geselecteerd; "
               "de technische ophaalquery haalt de bronboom op, maar de inhoudelijke selectie blijft hieronder expliciet. "
               "Alle teksten en hashes staan in bronnen.json. Niet-gebruikte bronboomnodes zijn geen onderdeel "
               "van de analysetekst of de meting.", "", "| ID | Reden |", "|---|---|"]
    regels += [f"| {c['id']} | {cel(c['reden'])} |" for c in pakket["contextpassages"]]
    regels += ["", "Open bronvragen:", "", *["- " + s for s in pakket["contextbudget"]["open"]], ""]
    return "\n".join(regels)


def meet(pakket, concepten, historisch):
    controleer_bronnen(pakket)
    controleer_concepten(pakket, concepten)
    provider = SpacyProvider("nl_core_news_md")
    samen = "\n\n".join(f"[{c['id']} | {c['juridische_status']} | {c['toestand']}]\n{c['tekst']}"
                          for c in [*pakket["casussen"], *pakket["contextpassages"]])
    result = {}
    for c in pakket["casussen"]:
        a = provider.analyseer(c["tekst"])
        if a.gedegradeerd:
            raise RuntimeError(f"volledige parse vereist: {c['id']}: {a.fout}")
        bron = BronTekst.van_tekst(c["bron_iri"], c["tekst"], analyse=a, context=c["ouder_context"])
        rs = detecteer_alles(bron)
        f = fuseer(rs)
        opnieuw = fuseer(detecteer_alles(bron))
        if f != opnieuw:
            raise AssertionError("niet-reproduceerbare detectie")
        zonder = fuseer(detecteer_alles(BronTekst.van_tekst(c["bron_iri"], c["tekst"], analyse=a)))
        model = [k for k in f.kandidaten if deterministisch(k) is None]
        schema = toolschema(model) if model else None
        unie = set(schema["input_schema"]["properties"]["beslissingen"]["items"]["properties"]["beslissing"]["enum"]) if schema else set()
        lek = [{"label": k.label, "tekst": k.span.tekst, "extra_in_batchschema": sorted(unie-set(k.toegestane_beslissingen()))}
               for k in model if unie-set(k.toegestane_beslissingen())]
        # Gebruik voor deze diagnostiek expliciet de route van het huidige systeem.
        alles_af = [deterministisch(k) or uit_modelkeuze(k, GEEN_ANNOTATIE, "") for k in f.kandidaten]
        vragen = {"alleen_eigen_tekst": userprompt(model, c["tekst"]),
                  "onderzoeksvariant_met_bronpakket": userprompt(model, samen)}
        old = historisch.get(c["id"])
        history = {"beschikbaar": bool(old)}
        if old:
            keuzes = old["beslissingen"] or [
                {**e["trace"]["beslissing"], "start": e["trace"]["kandidaat"]["span"]["start"],
                 "eind": e["trace"]["kandidaat"]["span"]["eind"],
                 "mogelijke_klassen": e["trace"]["kandidaat"]["mogelijke_klassen"]}
                for e in old["elementen"]]
            now = {(k.span.start, k.span.eind): k for k in f.kandidaten}
            history.update({"tijd": old["run"]["tijd"], "per_status": old["run"]["instellingen"]["meting"]["per_status"],
                            "volledige_beslisregistratie": bool(old["beslissingen"]),
                            "grens_of_klasse_gewijzigd": [
                                {"label_oud": b["label"], "start": b["start"], "eind": b["eind"],
                                 "klassen_oud": b["mogelijke_klassen"],
                                 "klassen_nu": list(now[(b["start"], b["eind"])].possible_classes) if (b["start"], b["eind"]) in now else None}
                                for b in keuzes if (b["start"], b["eind"]) not in now or
                                set(b["mogelijke_klassen"]) != set(now[(b["start"], b["eind"])].possible_classes)]})
            if old["beslissingen"] and not history["grens_of_klasse_gewijzigd"]:
                uitvoer, fake = speel(c, {b["label"]: b["klasse"] or GEEN_ANNOTATIE for b in keuzes})
                history["replay"] = {"soort": "vastgelegde_keuzes_geen_nieuwe_modelmeting", "per_status": uitvoer.meting["per_status"],
                                     "twijfels": uitvoer.meting["twijfels"], "review_calls": uitvoer.meting.get("review_calls", 0),
                                     "voorstellen": [{"tekst": v["tekst"], "klasse": v["klasse"], "ankers": v["ankers"]} for v in uitvoer.voorstellen]}
        result[c["id"]] = {
            "bron_hash": c["bron_hash"], "parse": asdict(a),
            "raw": [{**rij(k), "detector": r.detector, "versie": r.versie} for r in rs for k in r.kandidaten],
            "voor_specificiteit": [rij(k) for k in samen_voordat_specificiteit(rs).values()],
            "kandidaten": [{**rij(k), "label": k.label} for k in f.kandidaten],
            "detectiebijdragen": [b.model_dump(mode="json") for b in f.bijdragen],
            "detectoren": [{"naam": r.detector, "versie": r.versie, "kandidaten": len(r.kandidaten), "overgeslagen": r.overgeslagen} for r in rs],
            "tellingen": {"raw": sum(len(r.kandidaten) for r in rs), "fusie": len(f.kandidaten),
                          "model": len(model), "routes": dict(Counter(rij(k)["route"] for k in f.kandidaten))},
            "reproduceerbaar": True, "oudercontext_verandert_detectie": f.kandidaten != zonder.kandidaten,
            "dekking": structureel(f, [bron], {bron.bron_iri: {r.detector for r in rs}}),
            "alle_modelkeuzes_afgewezen": {"per_status": dict(Counter(b.status.value for b in alles_af)),
                                          "twijfels": [t.model_dump() for t in signaleer(f.per_id(), alles_af, [], set())]},
            "batchschema_extra_keuzes": lek, "classifier": {"system": systeemprompt(model), "tool": schema, **vragen},
            "conceptbereik": conceptbereik(concepten[c["id"]]["elementen"], f.kandidaten), "historisch": history}
    controles = []
    # Kunstmatige grammaticaproeven, uitdrukkelijk geen aanvullende juridische bronnen.
    for cid, tekst in [
        ("datum_zonder_jaar", "De termijn eindigt op 31 december."),
        ("datum_met_jaar", "De termijn eindigt op 31 december 2026."),
        ("toewijzing_volgorde_1", "De vervaldag wordt gesteld op 31 december."),
        ("toewijzing_volgorde_2", "De vervaldag wordt op 31 december gesteld."),
        ("gewone_handeling", "Het boek wordt op tafel gelegd."),
        ("vergelijking", "De dag heeft hetzelfde nummer als dat van de dagtekening."),
        ("voorwaarde", "Als de aanvraag tijdig is ingediend, wordt zij behandeld."),
        ("verwijzing", "Volgens artikel 9.1 bedraagt de vergoeding € 1.000."),
    ]:
        a = provider.analyseer(tekst)
        f = fuseer(detecteer_alles(BronTekst.van_tekst("synthetisch:"+cid, tekst, analyse=a)))
        controles.append({"id": cid, "status": "synthetisch_geen_rechtsbron", "tekst": tekst,
                          "kandidaten": [rij(k) for k in f.kandidaten]})
    files = [*sorted((ROOT / "tools/graph-qa/agent/jas_pipeline").rglob("*.py")),
             *sorted((ROOT / "tools/graph-qa/agent/jas_pipeline").rglob("*.yaml")),
             ROOT / "tools/graph-qa/uv.lock", Path(__file__),
             *(DOSSIER / n for n in ("bronnen.json", "concepten.json", "historische-sporen.json"))]
    return {"schema_versie": 1, "status": "diagnostisch_geen_gold", "modelaanroepen": 0,
            "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "python": platform.python_version(), "spacy": importlib.metadata.version("spacy"), "taalmodel": provider.model,
            "config": {"classifier_spankeuze": False, "classifier_granulariteit": "universeel", "deterministisch_accepteren": True},
            "hashes": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in files},
            "casussen": result, "synthetische_controles": controles}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dossiers", type=Path, help="optionele Markdown-weergave van concepten en gemeten bereik")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("meetbestand bestaat al; kies een nieuw vergelijkingspunt")
    if args.dossiers and args.dossiers.exists():
        parser.error("dossierbestand bestaat al; kies een nieuwe bestandsnaam")
    pakket, concepten, historie = (json.loads((DOSSIER / n).read_text()) for n in ("bronnen.json", "concepten.json", "historische-sporen.json"))
    result = meet(pakket, concepten, historie)
    with args.output.open("x") as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if args.dossiers:
        with args.dossiers.open("x") as f:
            f.write(dossiers_markdown(pakket, concepten, result))


if __name__ == "__main__":
    main()
