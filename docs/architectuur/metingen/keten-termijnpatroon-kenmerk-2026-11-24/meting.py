"""Meting keten-termijnpatroon, kenmerk zonder koppelwerkwoord (24 nov 2026): kandidaten én relatievoorstellen
zonder model.

Per bepaling: detectie en fusie met de echte parser, dan een vaste keuze in plaats van het model (elke kandidaat met
zijn eerste mogelijke klasse; een tijdkern valt weg zoals `ontdubbel_tijd` doet; een afgewezen kandidaat valt weg), en
daarop `relaties.stel_voor`. Dat meet het mechanisme, niet de keuze van het model. Draai vanuit tools/graph-qa:

    uv run python ../../docs/architectuur/metingen/keten-termijnpatroon-kenmerk-2026-11-24/meting.py uit.json
"""
from __future__ import annotations

import json
import sys

from agent.jas_pipeline import relaties
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import CandidateStatus
from agent.jas_pipeline.subtype import bepaal, codes_van
from agent.jas_pipeline.taal import maak_provider

VAR = "Variabele en variabelewaarde"
BRON = "urn:meting"

SET = [
    ("IW 9.1", "patroon", "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."),
    ("IW 9.2", "patroon", "In afwijking van het eerste lid is een navorderingsaanslag, alsmede een conserverende "
     "navorderingsaanslag invorderbaar één maand na de dagtekening van het aanslagbiljet en een naheffingsaanslag "
     "invorderbaar veertien dagen na de dagtekening van het aanslagbiljet."),
    ("IW 52.1", "patroon", "Het bedrag, vermeld in een beschikking als bedoeld in artikel 49, eerste lid, is "
     "invorderbaar zes weken na de dagtekening van de beschikking. De artikelen 9, tiende lid, 11, 12, 13, 14 en 19 "
     "zijn van overeenkomstige toepassing."),
    ("IW 63b.5", "patroon", "Een door de ontvanger opgelegde bestuurlijke boete is invorderbaar zes weken na de "
     "dagtekening van de beschikking waarbij deze is opgelegd, met overeenkomstige toepassing van de regels die gelden "
     "voor de invordering van de belastingaanslag in verband waarmee deze is opgelegd."),
    ("Awir 33.4", "patroon", "Aansprakelijkstelling geschiedt bij beschikking van de Dienst Toeslagen. Het bedrag "
     "waarvoor de aansprakelijkheid bestaat, is invorderbaar zes weken na de dagtekening van de beschikking. De "
     "artikelen 28, derde lid, 30, 31 en 32 zijn van overeenkomstige toepassing."),
    ("IW 9.5", "controle", "In afwijking van het eerste lid is een voorlopige aanslag in de inkomstenbelasting of in de "
     "vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting, waarvan het "
     "aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld, invorderbaar in zoveel "
     "gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van "
     "het jaar overblijven."),
    ("IW 9.7", "controle", "In afwijking van het eerste lid is een voorlopige aanslag waarvan het aanslagbiljet een "
     "dagtekening heeft die ligt voor het jaar waarover deze is vastgesteld, invorderbaar in zoveel gelijke termijnen "
     "als er maanden van het jaar zijn."),
    ("rekenregel", "controle", "Het bedrag van de vermindering is gelijk aan het verschil tussen het inkomen en het "
     "drempelinkomen, vermenigvuldigd met het percentage."),
    ("synthetisch: geen moment", "controle", "Een belastingaanslag is invorderbaar."),
    ("synthetisch: ontkend", "controle",
     "Een belastingaanslag die een bedrag behelst is niet invorderbaar zolang het adres ontbreekt."),
    ("AWR 13.2", "controle", "Een voorlopige aanslag tot een negatief bedrag die voor of in de loop van het tijdvak "
     "wordt vastgesteld, wordt aangeduid als voorlopige teruggaaf."),
]


def _voorstellen(fusie) -> list[dict]:
    uit = []
    for k in fusie.kandidaten:
        if k.status is CandidateStatus.REJECTED or any(e.code == "TEMPORAL_KERNEL" for e in k.evidence):
            continue
        klasse = k.possible_classes[0]
        uit.append({"id": k.id, "klasse": klasse, "jas_subtype": bepaal(klasse, codes_van(k.evidence)),
                    "ankers": [{"bron_iri": BRON, "start": k.span.start, "eind": k.span.eind, "tekst": k.span.tekst}],
                    "trace": {"kandidaat": {"id": k.id}}})
    return uit


def meet() -> dict:
    p = maak_provider("spacy:nl_core_news_md")
    uit = []
    for cid, soort, tekst in SET:
        a = p.analyseer(tekst)
        if a.gedegradeerd:
            raise SystemExit("volledige parser vereist")
        f = fuseer(detecteer_alles(BronTekst.van_tekst(BRON, tekst, analyse=a)))
        vs = _voorstellen(f)
        rel = relaties.stel_voor(vs, f, {BRON: a})
        tekst_van = {v["id"]: v["ankers"][0]["tekst"] for v in vs}
        klasse_van = {v["id"]: v["klasse"] for v in vs}
        rijen = [{"type": r["type"], "van": tekst_van[r["spoor"]["van_element"]],
                  "naar": tekst_van.get(r["spoor"]["naar_element"], r["spoor"]["naar_element"]),
                  "volgorde": r["volgorde"], "regel": r["spoor"]["regel"]} for r in rel]
        toestand = [k.span.tekst for k in f.kandidaten if any(e.code == "STATE_PROPERTY" for e in k.evidence)]
        uitvoer = {(r["spoor"]["van_element"], r["spoor"]["naar_element"]) for r in rel if r["type"] == "uitvoer"}
        operand_uitvoer = []
        for r in rel:
            if r["type"] != "operand":
                continue
            op = r["spoor"]["naar_element"]
            regels = [x["spoor"]["naar_element"] for x in rel if x["type"] == "operator_in"
                      and x["spoor"]["van_element"] == op]
            if any((g, r["spoor"]["van_element"]) in uitvoer for g in regels):
                operand_uitvoer.append(tekst_van[r["spoor"]["van_element"]])
        uit.append({"id": cid, "soort": soort, "toestand": toestand,
                    "uitvoer_naar_variabele": sorted(tekst_van[n] for _, n in uitvoer if klasse_van.get(n) == VAR),
                    "uitvoer_ook_operand": operand_uitvoer, "relaties": len(rel), "rijen": rijen})
    return {"set": uit}


if __name__ == "__main__":
    r = meet()
    for c in r["set"]:
        print(f'{c["id"]:26} {c["soort"]:9} toestand={c["toestand"]} uitvoer→V={c["uitvoer_naar_variabele"]} '
              f'uitvoer-ook-operand={c["uitvoer_ook_operand"]} relaties={c["relaties"]}')
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
