"""Meting keten-termijnpatroon (24 nov 2026): wat reikt de keten zonder model aan bij "[iets] is [toestand] [termijn]
na [moment]", en wat op de controles zonder dat patroon?

Detectie, fusie en het deterministische besluit, met de echte parser; geen model, geen graaf. Draai vanuit
tools/graph-qa:

    uv run python ../../docs/architectuur/metingen/keten-termijnpatroon-2026-11-24/meting.py uit.json
"""
from __future__ import annotations

import json
import sys

from agent.jas_pipeline.besluit import deterministisch
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.taal import maak_provider

AR, VAR, PAR = "Afleidingsregel", "Variabele en variabelewaarde", "Parameter en parameterwaarde"

# (id, soort, tekst, toestanden): de toestand(en) die volgens de skill (voorbeelden.md E03) een Variabele zijn.
SET = [
    ("IW 9.1", "patroon", "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.",
     ["invorderbaar"]),
    ("IW 9.2", "patroon", "In afwijking van het eerste lid is een navorderingsaanslag, alsmede een conserverende "
     "navorderingsaanslag invorderbaar één maand na de dagtekening van het aanslagbiljet en een naheffingsaanslag "
     "invorderbaar veertien dagen na de dagtekening van het aanslagbiljet.", ["invorderbaar", "invorderbaar"]),
    ("IW 52.1", "patroon", "Het bedrag, vermeld in een beschikking als bedoeld in artikel 49, eerste lid, is "
     "invorderbaar zes weken na de dagtekening van de beschikking. De artikelen 9, tiende lid, 11, 12, 13, 14 en 19 "
     "zijn van overeenkomstige toepassing.", ["invorderbaar"]),
    ("IW 63b.5", "patroon", "Een door de ontvanger opgelegde bestuurlijke boete is invorderbaar zes weken na de "
     "dagtekening van de beschikking waarbij deze is opgelegd, met overeenkomstige toepassing van de regels die gelden "
     "voor de invordering van de belastingaanslag in verband waarmee deze is opgelegd.", ["invorderbaar"]),
    # Controles: invorderbaar zonder moment, ontkend, als bijvoeglijk naamwoord, een telling, en zinnen zonder toestand.
    ("IW 9.5", "controle", "In afwijking van het eerste lid is een voorlopige aanslag in de inkomstenbelasting of in de "
     "vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting, waarvan het "
     "aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld, invorderbaar in zoveel "
     "gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van "
     "het jaar overblijven.", []),
    ("IW 9.7", "controle", "In afwijking van het eerste lid is een voorlopige aanslag waarvan het aanslagbiljet een "
     "dagtekening heeft die ligt voor het jaar waarover deze is vastgesteld, invorderbaar in zoveel gelijke termijnen "
     "als er maanden van het jaar zijn.", []),
    ("synthetisch: geen moment", "controle", "Een belastingaanslag is invorderbaar.", []),
    ("synthetisch: ontkend", "controle",
     "Een belastingaanslag die een bedrag behelst is niet invorderbaar zolang het adres ontbreekt.", []),
    ("synthetisch: bijvoeglijk", "controle",
     "Het invorderbare bedrag wordt binnen zes weken na de dagtekening betaald.", []),
    ("AWR 13.2", "controle", "Een voorlopige aanslag tot een negatief bedrag die voor of in de loop van het tijdvak "
     "wordt vastgesteld, wordt aangeduid als voorlopige teruggaaf.", []),
    ("Awb 4:13.1", "controle", "Een beschikking dient te worden gegeven binnen de bij wettelijk voorschrift bepaalde "
     "termijn of, bij het ontbreken van zulk een termijn, binnen een redelijke termijn na ontvangst van de aanvraag.",
     []),
]


def meet() -> dict:
    p = maak_provider("spacy:nl_core_news_md")
    uit = []
    for cid, soort, tekst, toestanden in SET:
        a = p.analyseer(tekst)
        if a.gedegradeerd:
            raise SystemExit("volledige parser vereist")
        f = fuseer(detecteer_alles(BronTekst.van_tekst("urn:meting", tekst, analyse=a)))
        rijen = []
        for k in f.kandidaten:
            b = deterministisch(k)
            rijen.append({"label": k.label, "tekst": k.span.tekst, "klassen": list(k.possible_classes),
                          "codes": sorted({e.code for e in k.evidence}),
                          "besluit": f"{b.status.value}:{b.klasse}" if b else "model"})
        var_toestand = [r for r in rijen if r["tekst"] in toestanden and VAR in r["klassen"]]
        uit.append({"id": cid, "soort": soort, "kandidaten": len(rijen),
                    "afleidingsregel": sum(AR in r["klassen"] for r in rijen),
                    "variabele_op_toestand": len(var_toestand), "verwacht_variabele": len(toestanden),
                    "parameter": sum(PAR in r["klassen"] for r in rijen), "rijen": rijen})
    return {"set": uit}


if __name__ == "__main__":
    r = meet()
    for c in r["set"]:
        print(f'{c["id"]:28} {c["soort"]:9} kand={c["kandidaten"]:2} AR={c["afleidingsregel"]} '
              f'V-op-toestand={c["variabele_op_toestand"]}/{c["verwacht_variabele"]} P={c["parameter"]}')
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
