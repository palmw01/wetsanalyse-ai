#!/usr/bin/env python3
"""De afleidingsregels van het team als eerste bestand in het werkgebied Termijnen (ADR-018, bouwplan R4).

    WETSANALYSE_ACC_URL=… WETSANALYSE_ACC_TOKEN=… python api/scripts/importeer_regels_termijnen.py            # droog
    WETSANALYSE_ACC_URL=… WETSANALYSE_ACC_TOKEN=… python api/scripts/importeer_regels_termijnen.py --uitvoeren

Zet R1–R8 uit `docs/architectuur/afleidingsregels-termijnen-team.md` als regels in Termijnen, met herkomst `import`, en
daarbij de open punten (§4: de interpretatiekeuzes met de keuze van de jurist, het te signaleren uitvoeringsbeleid, de
onderzoekspunten en de gaten) en de parameterwaarden. R8 volgt de methode (plan §10 punt 7): een beslisregel met uitvoer
*bevoegdheid tot verrekening vóór het verstrijken van de betalingstermijn*, op de Rechtsbetrekking van art. 24 lid 2.

- **Via de webapp, zoals een gebruiker.** Het script logt in met een accounttoken (`wa_pat_…`, zoals de acceptatie-MCP)
  en gebruikt de BFF-routes. Wie het token heeft, staat in de revisies en de audit. Geen token in de repo: alles komt
  uit de omgeving.
- **Brongetrouw.** De id's staan hier zoals het verslag ze noemt (begrippen met hun eerste acht tekens, markeringen met
  hun eerste twaalf). Het script lost ze op tegen het werkgebied en stopt bij een id dat niet of niet eenduidig bestaat:
  het verzint niets.
- **Idempotent.** Een regel en een open punt dragen hun sleutel vooraan in de toelichting ("Import termijnen-team R1.");
  een parameterwaarde is zichzelf (begrip, waarde, eenheid); het regelbegrip van R8 is zijn naam. Wat er al is, slaat
  het over; een tweede run maakt niets.
- **De regels blijven concept.** Het team accordeerde ze in zijn logboek, maar een regel in Lex gaat door de poort: elk
  geval heeft een beoordeeld voorbeeld nodig (activiteit 4, niet gedaan), en het te signaleren uitvoeringsbeleid staat
  open. De dragers zijn open: die beoordeelt de jurist in Lex.
- **De keuzes zijn genomen**, zoals de jurist van het team ze nam (§4), met de motivering uit het verslag. De methode
  van de interpretatie staat er niet bij: het verslag noemt haar niet.
- **Het regelbegrip van R8** bestaat nog niet. Het script maakt het als concept, op de Rechtsbetrekking met de rol
  context (die duidt al de uitvoer aan). Zo wacht R8 in de poort tot de gegevensspecialist het beoordeelt (ADR-018,
  besluit 9).

Het script verwijdert niets.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

WERKGEBIED_NAAM = "Termijnen"
BRON = "docs/architectuur/afleidingsregels-termijnen-team.md"
SLEUTEL = "Import termijnen-team {}."
HERKOMST = ("Overgenomen uit het logboek van het team van 19 november 2026 ({bron}, {waar}).")


# --- de inhoud, zoals het verslag haar geeft -----------------------------------------------------------------------
# Een begrip is "b:<8 tekens>", een markering "e:<12 tekens>". `oplossen` maakt er de volle id's van.

def b(kort: str) -> dict:
    return {"soort": "begrip", "begrip_id": f"b:{kort}"}


def t(tekst: str) -> dict:
    return {"soort": "tekst", "tekst": tekst}


def vw(tekst: str, *elementen: str, niet: bool = False) -> dict:
    return {"tekst": tekst, "element_ids": [f"e:{e}" for e in elementen], "niet": niet}


def alle(*delen: dict) -> dict:
    return {"verband": "alle", "delen": list(delen)}


def een_van(*delen: dict) -> dict:
    return {"verband": "een_van", "delen": list(delen)}


def d(element: str, rol: str, geval: str = "") -> dict:
    return {"element_id": f"e:{element}", "rol": rol, "geval": geval}


def inv(kort: str, rol: str = "invoer") -> dict:
    return {"begrip_id": f"b:{kort}", "rol": rol}


AKKOORD_TEAM = ("In het logboek {status} door de jurist en de gegevensspecialist. In Lex gaat de regel door de poort: "
                "elk geval vraagt een beoordeeld voorbeeld (activiteit 4, nog niet gedaan).")

REGELS: list[dict] = [
    {
        "sleutel": "R1",
        "toelichting": "Onderste regel. Er is geen operatorbegrip voor het tellen van de maanden (open punt). De "
                       "voorwaarden van lid 5 volgen lezing C van art. 72 Mijnbouwwet (open punt K1).",
        "status_team": "geaccordeerd",
        "inhoud": {
            "soort": "rekenregel", "regelbegrip_id": "b:f87474ca", "uitvoer_begrip_id": "b:de1bae54", "lidwoord": "het",
            "invoer": [inv("0337495b"), inv("11c714db"), inv("c25b97af")],
            "gevallen": [
                {"label": "lid 5", "voorwaarden": alle(
                    vw("de aanslag is een voorlopige aanslag in de inkomstenbelasting of de vennootschapsbelasting, "
                       "een voorlopige conserverende aanslag, of via art. 72 Mijnbouwwet een voorlopige aanslag "
                       "winstaandeel (lezing C)"),
                    vw("de dagtekening van het aanslagbiljet ligt in het jaar"),
                    vw("het bedrag van de belastingaanslag is niet negatief")),
                 "uitkomst": [t("het aantal maanden van het"), b("0337495b"), t("dat overblijft na de maand van de"),
                              b("11c714db")]},
                {"label": "lid 6", "voorwaarden": alle(
                    vw("het is een aanslag als bedoeld in lid 5 die een uit te betalen bedrag behelst", "02c651028863"),
                    vw("de dagtekening van het aanslagbiljet ligt in het jaar")),
                 "uitkomst": [t("het aantal maanden van het"), b("0337495b"),
                              t("dat overblijft, met inbegrip van de maand van de"), b("11c714db")]},
                {"label": "lid 7", "voorwaarden": alle(
                    vw("de dagtekening van het aanslagbiljet ligt vóór het jaar (elke voorlopige aanslag)")),
                 "uitkomst": [t("het aantal maanden van het"), b("0337495b")]},
            ],
        },
        "dragers": [d("1cb47880a331", "grondslag", "lid 5"), d("e65b6e0f8d78", "grondslag", "lid 6"),
                    d("747ecbc0a10e", "grondslag", "lid 7"), d("02c651028863", "voorwaarde", "lid 6")],
    },
    {
        "sleutel": "R2",
        "toelichting": "Volgt op R1 en sluit R4 uit: alleen bij geen termijnen, of niet meer dan één termijn. Er is "
                       "geen operatorbegrip voor tijdsduur na tijdstip (open punt). Een aanslag van lid 6 met één "
                       "termijn valt níét terug op lid 1 (keuze K6).",
        "status_team": "geaccordeerd",
        "inhoud": {
            "soort": "rekenregel", "regelbegrip_id": "b:6bce8f07", "uitvoer_begrip_id": "b:08ffc11c",
            "invoer": [inv("11c714db"), inv("de1bae54"), inv("855cd256", "parameter")],
            "gevallen": [
                {"voorwaarden": een_van(
                    vw("de aanslag is niet in termijnen invorderbaar"),
                    vw("de termijnregeling leidt niet tot meer dan één termijn", "1d46b64dc6aa")),
                 "uitkomst": [t("het tijdstip dat de"), b("855cd256"), t("na de"), b("11c714db"), t("ligt")]},
            ],
        },
        "dragers": [d("8263fa226caa", "grondslag"), d("1d46b64dc6aa", "grondslag")],
    },
    {
        "sleutel": "R3",
        "toelichting": "Beleidsregel (Leidraad Invordering 2008, 9.5). Levert de eerste vervaldag voor geval lid 5 van "
                       "R4. De betalingstermijn is één maand (parameterwaarde).",
        "status_team": "geaccordeerd als beleidsregel",
        "inhoud": {
            "soort": "rekenregel", "brontype": "beleid", "regelbegrip_id": "b:a9afb082",
            "uitvoer_begrip_id": "b:08ffc11c",
            "invoer": [inv("11c714db"), inv("e48826ff", "parameter")],
            "gevallen": [
                {"voorwaarden": alle(
                    vw("de dagtekening van het aanslagbiljet valt niet op de laatste dag van de kalendermaand",
                       "398711121c90")),
                 "uitkomst": [t("het tijdstip dat de"), b("e48826ff"), t("na de"), b("11c714db"), t("ligt")]},
            ],
        },
        "dragers": [d("398711121c90", "grondslag")],
    },
    {
        "sleutel": "R4",
        "toelichting": "De vervaldag is hier een kenmerk van de termijn. Een termijn heeft in de wet geen volgnummer; de "
                       "regel gebruikt er ook geen. Geval lid 5 volgt R3. \"Eind van de maand\" is de laatste dag van "
                       "de kalendermaand (keuze K7).",
        "status_team": "geaccordeerd",
        "inhoud": {
            "soort": "rekenregel", "regelbegrip_id": "b:225d18a3", "uitvoer_begrip_id": "b:08ffc11c",
            "invoer": [inv("11c714db"), inv("0337495b"), inv("de1bae54")],
            "gevallen": [
                {"label": "lid 5", "voorwaarden": alle(vw("het aantal termijnen is bepaald volgens art. 9 lid 5")),
                 "uitkomst": [t("de eerste vervaldag een maand na de"), b("11c714db"),
                              t("(Leidraad 9.5), en daarna telkens een maand later, totdat er evenveel vervaldagen "
                                "zijn als het"), b("de1bae54")]},
                {"label": "lid 6", "voorwaarden": alle(vw("het aantal termijnen is bepaald volgens art. 9 lid 6")),
                 "uitkomst": [t("de eerste vervaldag op de"), b("f0a7053f"), t("van de maand van de"), b("11c714db"),
                              t(", en daarna telkens een maand later, totdat er evenveel vervaldagen zijn als het"),
                              b("de1bae54")]},
                {"label": "lid 7", "voorwaarden": alle(vw("het aantal termijnen is bepaald volgens art. 9 lid 7")),
                 "uitkomst": [t("de eerste vervaldag op de"), b("f0a7053f"), t("van de eerste maand van het"),
                              b("0337495b"),
                              t(", en daarna telkens een maand later, totdat er evenveel vervaldagen zijn als het"),
                              b("de1bae54")]},
            ],
        },
        "dragers": [d("e9f2f0428ec5", "grondslag", "lid 5"), d("c8429eaa55cb", "grondslag", "lid 6"),
                    d("8cfe37e92e8d", "grondslag", "lid 7")],
    },
    {
        "sleutel": "R5",
        "toelichting": "Het termijnbedrag is zonder teken: met teken wordt het termijnbedrag van een teruggaaf negatief, "
                       "en voldoet het in R6 altijd aan \"ten hoogste € 49\". De wet noemt het bedrag per termijn zelf "
                       "niet; de uitvoer rust op het termijnbedrag in Leidraad 9.3. Er is geen operatorbegrip voor "
                       "gedeeld door (open punt).",
        "status_team": "geaccordeerd (na herindiening)",
        "inhoud": {
            "soort": "rekenregel", "regelbegrip_id": "b:27426263", "uitvoer_begrip_id": "b:cbc694db",
            "lidwoord": "het",
            "invoer": [inv("c25b97af"), inv("de1bae54")],
            "gevallen": [
                {"label": "lid 5", "voorwaarden": alle(
                    vw("het bedrag van de belastingaanslag is een positief bedrag (art. 13 lid 1 AWR)",
                       "dc43143ba8c4")),
                 "uitkomst": [t("het"), b("c25b97af"), t("zonder teken, gedeeld door het"), b("de1bae54")]},
                {"label": "lid 6", "voorwaarden": alle(
                    vw("het bedrag van de belastingaanslag is een uit te betalen bedrag", "6eec78b767f3")),
                 "uitkomst": [t("het"), b("c25b97af"), t("zonder teken, gedeeld door het"), b("de1bae54")]},
                {"label": "lid 7", "voorwaarden": alle(vw("het aantal termijnen is bepaald volgens art. 9 lid 7")),
                 "uitkomst": [t("het"), b("c25b97af"), t("zonder teken, gedeeld door het"), b("de1bae54")]},
            ],
        },
        "dragers": [d("52525d2b22c8", "grondslag", "lid 5"), d("264c4001bc2d", "grondslag", "lid 6"),
                    d("d963056fc488", "grondslag", "lid 7"), d("70ca61bc3d45", "uitvoer"),
                    d("dc43143ba8c4", "invoer", "lid 5"), d("6eec78b767f3", "invoer", "lid 6")],
    },
    {
        "sleutel": "R6",
        "toelichting": "Beleidsregel (Leidraad Invordering 2008, 9.3). De wijze van uitbetaling kent twee waarden; volgens "
                       "Leidraad 9.3 is die lijst volledig. De drempel is € 49 per maand (parameterwaarde).",
        "status_team": "geaccordeerd als beleidsregel (na herindiening)",
        "inhoud": {
            "soort": "beslisregel", "brontype": "beleid", "regelbegrip_id": "b:d23d063b",
            "uitvoer_begrip_id": "b:ef13d661",
            "invoer": [inv("cbc694db"), inv("82165e28", "parameter")],
            "gevallen": [
                {"label": "in één keer", "voorrang": 1, "voorwaarden": alle(
                    vw("het gaat om een voorlopige teruggaaf"),
                    vw("het termijnbedrag is ten hoogste de drempel voor uitbetaling in één keer", "d7d4d9913a3d"),
                    vw("er ligt derdenbeslag", "9735579d6282", niet=True)),
                 "uitkomst": [t("in één keer")]},
                {"label": "anders", "uitkomst": [t("in maandelijkse termijnen")]},
            ],
        },
        "dragers": [d("0fb9888eeb85", "grondslag"), d("d7d4d9913a3d", "voorwaarde", "in één keer"),
                    d("9735579d6282", "voorwaarde", "in één keer"), d("3f1c4b922310", "uitvoer", "in één keer"),
                    d("f6df5e32bb29", "uitvoer", "anders")],
    },
    {
        "sleutel": "R7",
        "toelichting": "Rij 2 gaat voor (de uitzondering_op van volzin 7 op volzin 6). Geval rij 2 volgt de keuze K4 (ook "
                       "een positieve aanslag van lid 7), geval rij 1 de keuze K5.",
        "status_team": "geaccordeerd",
        "inhoud": {
            "soort": "rekenregel", "regelbegrip_id": "b:ef9a1c46", "uitvoer_begrip_id": "b:6334736f",
            "lidwoord": "het",
            "invoer": [inv("08ffc11c"), inv("11c714db")],
            "gevallen": [
                {"label": "rij 2", "voorrang": 1, "voorwaarden": alle(
                    vw("het betreft een termijn van een voorlopige aanslag als bedoeld in art. 9 lid 6 of 7, ook een "
                       "positieve aanslag van lid 7")),
                 "uitkomst": [t("de"), b("08ffc11c"), t("van die termijn")]},
                {"label": "rij 1",
                 "uitkomst": [t("de"), b("11c714db"), t("van de aanslag waaruit het te betalen bedrag blijkt")]},
            ],
        },
        "dragers": [d("43f4f3f1798d", "grondslag", "rij 1"), d("c5d1c19d1503", "grondslag", "rij 2"),
                    d("e41c96f34c84", "invoer", "rij 1")],
    },
    {
        "sleutel": "R8",
        "toelichting": "Het team wees R8 af als afleidingsregel omdat art. 24 lid 2 een bevoegdheid geeft. Volgens de "
                       "methode is het een beslisregel (M-3b-0, plan §10 punt 7), op de Rechtsbetrekking. Het "
                       "regelbegrip is bij de import als concept gemaakt en wacht op de gegevensspecialist.",
        "status_team": "afgewezen als afleidingsregel",
        "regelbegrip": "bepalen van de bevoegdheid tot verrekening vóór het verstrijken van de betalingstermijn",
        "inhoud": {
            "soort": "beslisregel", "regelbegrip_id": "regelbegrip:R8", "uitvoer_begrip_id": "b:fb9f3866",
            "gevallen": [
                {"voorwaarden": alle(
                    vw("de termijn, bedoeld in artikel 9, is nog niet verstreken", "f2f5a4beb58e"),
                    een_van(
                        vw("het betreft een belastingaanslag als bedoeld in artikel 9, vijfde of zevende lid",
                           "4c520bdbace7", niet=True),
                        vw("de belastingaanslagen hebben betrekking op dezelfde belasting en hetzelfde tijdvak",
                           "f9e23c7cf2d6"))),
                 "uitkomst": [t("aanwezig")]},
            ],
        },
        "dragers": [d("0f01cda739e9", "grondslag"), d("f2f5a4beb58e", "voorwaarde"), d("4c520bdbace7", "voorwaarde"),
                    d("f9e23c7cf2d6", "voorwaarde")],
    },
]


def regel(sleutel: str) -> dict:
    return {"soort": "regel", "id": f"regel:{sleutel}"}


def geval(sleutel: str, label: str) -> dict:
    return {"soort": "geval", "id": f"regel:{sleutel}", "geval": label}


def lezing(label: str, omschrijving: str) -> dict:
    return {"label": label, "omschrijving": omschrijving}


def toets(bronsoort: str, omschrijving: str) -> dict:
    return {"bronsoort": bronsoort, "omschrijving": omschrijving}


#: De open punten van §4. Een keuze draagt `keuze`: de lezing die de jurist van het team koos en waarom.
OPEN_PUNTEN: list[dict] = [
    {"sleutel": "K1", "soort": "interpretatiekeuze",
     "vraag": "Hoe werkt \"met overeenkomstige toepassing van … de Invorderingswet 1990\" in art. 72 Mijnbouwwet door "
              "op de termijnen van een voorlopige aanslag winstaandeel?",
     "hangt_aan": [geval("R1", "lid 5"), regel("R8")],
     "lezingen": [lezing("A", "Het winstaandeel geldt als vennootschapsbelasting."),
                  lezing("B", "Lid 5 en 6 van art. 9 gelden niet voor het winstaandeel."),
                  lezing("C", "Het winstaandeel is de belasting waarop de aanslag rust; \"dezelfde belasting\" in art. "
                              "24 lid 2 is winstaandeel met winstaandeel.")],
     "te_toetsen": [toets("wetsgeschiedenis", "de memorie van toelichting bij art. 72 Mijnbouwwet"),
                    toets("jurisprudentie", "rechtspraak over art. 72 Mijnbouwwet")],
     "keuze": ("C", "Lezing A en B zijn verworpen. Niet getoetst aan de memorie van toelichting of aan rechtspraak.")},
    {"sleutel": "K2", "soort": "interpretatiekeuze",
     "vraag": "Valt een aanslag van art. 9 lid 6 onder \"het vijfde lid\" in art. 24 lid 2?",
     "hangt_aan": [regel("R8")],
     "lezingen": [lezing("A", "Ja: een aanslag van lid 6 is een aanslag als bedoeld in lid 5."),
                  lezing("B", "Nee: art. 24 lid 2 noemt alleen het vijfde en zevende lid.")],
     "keuze": ("A", "Een aanslag van lid 6 valt onder art. 24 lid 2.")},
    {"sleutel": "K3", "soort": "interpretatiekeuze",
     "vraag": "Welk tijdvak is \"hetzelfde tijdvak\"?",
     "hangt_aan": [regel("R8"), regel("R1")],
     "lezingen": [lezing("A", "Het jaar waarover de aanslag is vastgesteld; jaar is een soort van tijdvak."),
                  lezing("B", "Een ander tijdvak dan het jaar van de aanslag.")],
     "keuze": ("A", "Het tijdvak is het jaar waarover de aanslag is vastgesteld; jaar is een soort van tijdvak.")},
    {"sleutel": "K4", "soort": "interpretatiekeuze",
     "vraag": "Geldt rij 2 van R7 (de vervaldag van de termijn) ook voor een positieve aanslag van art. 9 lid 7?",
     "hangt_aan": [geval("R7", "rij 2")],
     "lezingen": [lezing("A", "Ja, ook voor een positieve aanslag van lid 7."),
                  lezing("B", "Nee, alleen voor een aanslag van lid 6.")],
     "keuze": ("A", "R7 rij 2 geldt ook voor een positieve aanslag van lid 7.")},
    {"sleutel": "K5", "soort": "interpretatiekeuze",
     "vraag": "Welke aanslag wijst \"te betalen bedrag\" in art. 24 lid 1 aan?",
     "hangt_aan": [geval("R7", "rij 1")],
     "lezingen": [lezing("A", "De aanslag met het te innen bedrag."),
                  lezing("B", "De aanslag met het uit te betalen bedrag.")],
     "keuze": ("A", "\"Te betalen bedrag\" in art. 24 lid 1 wijst de aanslag met het te innen bedrag aan.")},
    {"sleutel": "K6", "soort": "interpretatiekeuze",
     "vraag": "Valt een aanslag van art. 9 lid 6 met één termijn terug op lid 1?",
     "hangt_aan": [regel("R2"), geval("R1", "lid 6")],
     "lezingen": [lezing("A", "Nee: de vervaldag volgt uit lid 6."),
                  lezing("B", "Ja: zoals bij lid 5 volzin 3 geldt dan lid 1.")],
     "keuze": ("A", "Lid 6 met één termijn valt niet terug op lid 1.")},
    {"sleutel": "K7", "soort": "interpretatiekeuze",
     "vraag": "Wat is \"eind van de maand\", ook bij \"telkens een maand later\"?",
     "hangt_aan": [geval("R4", "lid 6"), geval("R4", "lid 7")],
     "lezingen": [lezing("A", "De laatste dag van de kalendermaand; telkens een maand later valt weer op de laatste "
                              "dag van de volgende maand."),
                  lezing("B", "Telkens een maand later valt op dezelfde dagtekening van de volgende maand.")],
     "te_toetsen": [toets("beleid", "bevestiging in de Leidraad Invordering 2008")],
     "keuze": ("A", "\"Eind van de maand\" is de laatste kalenderdag, ook bij \"telkens een maand later\". Beleid moet "
                    "dat bevestigen.")},
    {"sleutel": "U1", "soort": "ontbrekend_uitvoeringsbeleid",
     "vraag": "Leidraad 9.1 legt de enige of laatste termijn op 31 december; in het praktijkvoorbeeld schuift de laatste "
              "termijn dan van 15 naar 31 december.",
     "hangt_aan": [regel("R4")],
     "toelichting": "Leidraad 9.1 staat als context in het werkgebied en is niet geannoteerd, dus draagt ze geen regel.",
     "te_toetsen": [toets("beleid", "Leidraad Invordering 2008, 9.1")]},
    {"sleutel": "U2", "soort": "ontbrekend_uitvoeringsbeleid",
     "vraag": "Wat is het tijdstip van verrekening bij uitbetaling in één keer?",
     "hangt_aan": [regel("R6"), regel("R7")],
     "te_toetsen": [toets("beleid", "Leidraad Invordering 2008")]},
    {"sleutel": "U3", "soort": "ontbrekend_uitvoeringsbeleid",
     "vraag": "Hoe wordt het termijnbedrag afgerond, en waar landt het restant?",
     "hangt_aan": [regel("R5")],
     "te_toetsen": [toets("beleid", "Leidraad Invordering 2008")]},
    {"sleutel": "U4", "soort": "ontbrekend_uitvoeringsbeleid",
     "vraag": "Welke vervaldagen gelden bij een dagtekening op de 29e tot en met de 31e, en welke laatste dag bij "
              "\"telkens een maand later\"?",
     "hangt_aan": [regel("R3"), regel("R4")],
     "toelichting": "De laatste dag van de maand staat alleen in de rekenvoorbeelden van de Leidraad; voor een "
                    "dagtekening op de 29e tot en met de 31e geeft de bron geen uitkomst.",
     "te_toetsen": [toets("beleid", "Leidraad Invordering 2008, 9.5")]},
    {"sleutel": "U5", "soort": "ontbrekend_uitvoeringsbeleid",
     "vraag": "In welk tijdvak geldt de drempel van € 49 per maand?",
     "hangt_aan": [regel("R6")],
     "te_toetsen": [toets("beleid", "Leidraad Invordering 2008, 9.3")]},
    {"sleutel": "U6", "soort": "ontbrekend_uitvoeringsbeleid",
     "vraag": "Wat zegt Leidraad 24.3 over de verrekening?",
     "hangt_aan": [regel("R7")],
     "toelichting": "Leidraad 24.3 is niet gelezen.",
     "te_toetsen": [toets("beleid", "Leidraad Invordering 2008, 24.3")]},
    {"sleutel": "O1", "soort": "onderzoekspunt",
     "vraag": "Is het citaat van Leidraad 9.5 en 9.3 gelijk aan de officiële tekst?",
     "hangt_aan": [regel("R3"), regel("R6")],
     "toelichting": "De bronlezer leest geen Leidraad-onderdelen; R3 en R6 zijn alleen tegen de graaf getoetst.",
     "te_toetsen": [toets("beleid", "de officiële tekst van Leidraad Invordering 2008, 9.3 en 9.5")]},
    {"sleutel": "O2", "soort": "onderzoekspunt",
     "vraag": "Geldt de wettelijke betalingstermijn van zes weken ook in de toestanden tussen 1 januari 2025 en "
              "1 oktober 2026?",
     "hangt_aan": [regel("R2")],
     "toelichting": "De zes weken zijn vastgesteld in de toestanden van 1 januari 2025 en 1 oktober 2026 van art. 9 "
                    "lid 1 Invorderingswet 1990; de toestanden daartussen zijn niet gelezen.",
     "te_toetsen": [toets("wettekst", "de toestanden van art. 9 lid 1 Invorderingswet 1990 tussen 1 januari 2025 en "
                                      "1 oktober 2026")]},
    {"sleutel": "G1", "soort": "gat_in_de_annotatie",
     "vraag": "Er is geen gemarkeerde formulering voor de operatoren tellen van maanden, tijdsduur na tijdstip en "
              "gedeeld door.",
     "hangt_aan": [regel("R1"), regel("R2"), regel("R3"), regel("R4"), regel("R5")],
     "toelichting": "Zonder formulering wordt een operator geen begrip; de regeltekst noemt de bewerking (gat A2 uit "
                    "het plan)."},
    {"sleutel": "G2", "soort": "gat_in_de_annotatie",
     "vraag": "Geval lid 7 van R5 heeft geen invoer voor het bedrag: de tekst heeft er geen formulering voor.",
     "hangt_aan": [geval("R5", "lid 7")]},
    {"sleutel": "G3", "soort": "gat_in_de_annotatie",
     "vraag": "De voorwaarde van geval rij 2 van R7 (lid 6 en lid 7) is niet als eigen markering gelegd.",
     "hangt_aan": [geval("R7", "rij 2")]},
    {"sleutel": "G4", "soort": "gat_in_de_annotatie",
     "vraag": "Een uitzondering_op naar Awb 4:93 lid 3 kan niet: dat lid staat als context in de selectie en heeft "
              "geen elementen.",
     "hangt_aan": [regel("R7")]},
]

#: De parameterwaarden uit het verslag. Het tijdvak staat er niet bij, omdat het verslag het niet vaststelde.
PARAMETERWAARDEN: list[dict] = [
    {"parameter_begrip_id": "b:855cd256", "waarde": "6", "eenheid": "weken", "element_id": "e:8263fa226caa",
     "getoetst": "Vastgesteld in de toestanden van 1 januari 2025 en 1 oktober 2026 van art. 9 lid 1 Invorderingswet "
                 "1990; de toestanden daartussen zijn niet gelezen."},
    {"parameter_begrip_id": "b:e48826ff", "waarde": "1", "eenheid": "maand", "element_id": "e:398711121c90",
     "getoetst": "Leidraad Invordering 2008, 9.5; alleen tegen de graaf getoetst."},
    {"parameter_begrip_id": "b:82165e28", "waarde": "49", "eenheid": "euro per maand", "element_id": "e:d7d4d9913a3d",
     "getoetst": "Leidraad Invordering 2008, 9.3; het tijdvak waarin de waarde geldt, is niet vastgesteld."},
]


# --- oplossen ------------------------------------------------------------------------------------------------------

class ImportFout(Exception):
    pass


def _uniek(kort: str, ids: list[str], wat: str) -> str:
    treffers = [i for i in ids if i.startswith(kort)]
    if len(treffers) != 1:
        raise ImportFout(f"{wat} {kort!r}: {'niet gevonden' if not treffers else f'{len(treffers)} treffers'}.")
    return treffers[0]


def oplosser(begrip_ids: list[str], element_ids: list[str], extra: dict[str, str]) -> Callable[[Any], Any]:
    """Vervangt elke "b:<kort>" en "e:<kort>" door de volle id, en "regelbegrip:…"/"regel:…" uit `extra`."""
    def los(waarde: Any) -> Any:
        if isinstance(waarde, dict):
            return {k: los(v) for k, v in waarde.items()}
        if isinstance(waarde, list):
            return [los(v) for v in waarde]
        if isinstance(waarde, str):
            if waarde.startswith("b:"):
                return _uniek(waarde[2:], begrip_ids, "Begrip")
            if waarde.startswith("e:"):
                return _uniek(waarde[2:], element_ids, "Markering")
            if waarde.startswith(("regelbegrip:", "regel:")):
                if waarde not in extra:
                    raise ImportFout(f"{waarde} is nog niet aangemaakt.")
                return extra[waarde]
        return waarde
    return los


def regel_aanmaak(r: dict) -> dict:
    """Het verzoek voor `POST …/regels`, met de korte id's nog erin."""
    waar = f"§2, {r['sleutel']}"
    toelichting = " ".join([SLEUTEL.format(r["sleutel"]), HERKOMST.format(bron=BRON, waar=waar),
                            AKKOORD_TEAM.format(status=r["status_team"]) if r["status_team"].startswith("geaccordeerd")
                            else f"In het logboek {r['status_team']}.", r["toelichting"]])
    return {"inhoud": {**r["inhoud"], "toelichting": toelichting}, "dragers": r["dragers"], "herkomst": "import"}


def open_punt_aanmaak(p: dict) -> dict:
    toelichting = " ".join(x for x in [SLEUTEL.format(p["sleutel"]), HERKOMST.format(bron=BRON, waar="§4"),
                                       p.get("toelichting", "")] if x)
    inhoud = {"soort": p["soort"], "vraag": p["vraag"], "hangt_aan": p["hangt_aan"],
              "lezingen": p.get("lezingen", []), "te_toetsen": p.get("te_toetsen", []), "toelichting": toelichting}
    return {"inhoud": inhoud, "herkomst": "import"}


def besluit_van(p: dict) -> dict | None:
    if "keuze" not in p:
        return None
    gekozen, waarom = p["keuze"]
    return {"gekozen": gekozen,
            "motivering": f"Keuze van de jurist van het team, overgenomen uit het logboek van 19 november 2026 ({BRON}, "
                          f"§4): {waarom}"}


def regelbegrip_aanmaak(r: dict) -> dict:
    return {"inhoud": {"naam": r["regelbegrip"],
                       "context": f"Het regelbegrip van {r['sleutel']}, gemaakt bij de import van de afleidingsregels "
                                  f"van het team ({BRON}). Het rust op de Rechtsbetrekking van art. 24 lid 2 "
                                  "Invorderingswet 1990, die al de uitvoer aanduidt."},
            "element_ids": [r["dragers"][0]["element_id"]], "rol": "context"}


def heeft_sleutel(tekst: str, sleutel: str) -> bool:
    return (tekst or "").startswith(SLEUTEL.format(sleutel))


# --- uitvoeren -----------------------------------------------------------------------------------------------------

class Bff(Protocol):
    def __call__(self, methode: str, pad: str, body: Any = None) -> tuple[int, Any]: ...


@dataclass
class Verslag:
    gemaakt: dict[str, list[str]] = field(default_factory=lambda: {"regelbegrip": [], "regel": [], "open_punt": [],
                                                                     "keuze": [], "parameterwaarde": []})
    bestond: dict[str, list[str]] = field(default_factory=lambda: {"regelbegrip": [], "regel": [], "open_punt": [],
                                                                     "keuze": [], "parameterwaarde": []})

    def regels(self) -> list[str]:
        return [f"{soort}: {len(self.gemaakt[soort])} nieuw, {len(self.bestond[soort])} bestond al"
                for soort in self.gemaakt]


def _ok(status: int, data: Any, wat: str) -> Any:
    if status >= 300:
        melding = data.get("detail", data) if isinstance(data, dict) else data
        raise ImportFout(f"{wat}: {status} {json.dumps(melding, ensure_ascii=False)[:600]}")
    return data


def werkgebied_id(bff: Bff, naam: str) -> str:
    data = _ok(*bff("GET", "/api/werkgebieden?q=" + urllib.parse.quote(naam)), "Werkgebieden lezen")
    treffers = [w for w in data["werkgebieden"] if w["naam"] == naam]
    if len(treffers) != 1:
        raise ImportFout(f"Werkgebied {naam!r}: {len(treffers)} treffers.")
    return treffers[0]["id"]


def importeer(bff: Bff, wid: str, uitvoeren: bool, log: Callable[[str], None] = print) -> Verslag:
    """Leest het werkgebied, lost alle id's op (vóór er iets geschreven wordt) en maakt wat er nog niet is."""
    v = Verslag()
    wg = f"/api/werkgebieden/{wid}"
    begrippen = _ok(*bff("GET", f"{wg}/begrippen"), "Begrippen lezen")["begrippen"]
    elementen = _ok(*bff("GET", f"{wg}/elementen"), "Elementen lezen")["elementen"]
    regels = _ok(*bff("GET", f"{wg}/regels"), "Regels lezen")["regels"]
    punten = _ok(*bff("GET", f"{wg}/open-punten"), "Open punten lezen")["open_punten"]
    waarden = _ok(*bff("GET", f"{wg}/parameterwaarden"), "Parameterwaarden lezen")["parameterwaarden"]
    begrip_ids = [x["id"] for x in begrippen]
    element_ids = [x["id"] for x in elementen]

    # Eerst alles oplossen wat al kan: een fout id stopt de import voor er iets geschreven is.
    proef = oplosser(begrip_ids, element_ids, {f"regelbegrip:{r['sleutel']}": "-" for r in REGELS if "regelbegrip" in r}
                     | {f"regel:{r['sleutel']}": "-" for r in REGELS})
    for r in REGELS:
        proef(regel_aanmaak(r))
        if "regelbegrip" in r:
            proef(regelbegrip_aanmaak(r))
    for p in OPEN_PUNTEN:
        proef(open_punt_aanmaak(p))
    for w in PARAMETERWAARDEN:
        proef(w)
    log(f"Alle id's opgelost: {len(REGELS)} regels, {len(OPEN_PUNTEN)} open punten, "
        f"{len(PARAMETERWAARDEN)} parameterwaarden.")

    extra: dict[str, str] = {}
    for r in REGELS:
        if "regelbegrip" not in r:
            continue
        al = [x for x in begrippen if x["inhoud"]["naam"] == r["regelbegrip"] and x["status"] != "vervangen"]
        if al:
            extra[f"regelbegrip:{r['sleutel']}"] = al[0]["id"]
            v.bestond["regelbegrip"].append(r["regelbegrip"])
            continue
        v.gemaakt["regelbegrip"].append(r["regelbegrip"])
        if uitvoeren:
            los = oplosser(begrip_ids, element_ids, extra)
            nieuw = _ok(*bff("POST", f"{wg}/begrippen", los(regelbegrip_aanmaak(r))), f"Regelbegrip {r['sleutel']}")
            extra[f"regelbegrip:{r['sleutel']}"] = nieuw["id"]
            begrip_ids.append(nieuw["id"])
        else:
            extra[f"regelbegrip:{r['sleutel']}"] = "(nieuw)"

    for r in REGELS:
        al = [x for x in regels if heeft_sleutel(x["inhoud"].get("toelichting", ""), r["sleutel"])]
        if al:
            extra[f"regel:{r['sleutel']}"] = al[0]["id"]
            v.bestond["regel"].append(r["sleutel"])
            continue
        v.gemaakt["regel"].append(r["sleutel"])
        if uitvoeren:
            nieuw = _ok(*bff("POST", f"{wg}/regels", oplosser(begrip_ids, element_ids, extra)(regel_aanmaak(r))),
                        f"Regel {r['sleutel']}")
            extra[f"regel:{r['sleutel']}"] = nieuw["id"]
        else:
            extra[f"regel:{r['sleutel']}"] = "(nieuw)"
        log(f"Regel {r['sleutel']}: {'gemaakt' if uitvoeren else 'te maken'}.")

    for p in OPEN_PUNTEN:
        al = [x for x in punten if heeft_sleutel(x["inhoud"].get("toelichting", ""), p["sleutel"])]
        punt = al[0] if al else None
        if punt:
            v.bestond["open_punt"].append(p["sleutel"])
        else:
            v.gemaakt["open_punt"].append(p["sleutel"])
            if uitvoeren:
                punt = _ok(*bff("POST", f"{wg}/open-punten",
                                oplosser(begrip_ids, element_ids, extra)(open_punt_aanmaak(p))),
                           f"Open punt {p['sleutel']}")
        besluit = besluit_van(p)
        if besluit is None:
            continue
        if punt and punt["status"] != "open":
            v.bestond["keuze"].append(p["sleutel"])
            continue
        v.gemaakt["keuze"].append(p["sleutel"])
        if uitvoeren and punt:
            _ok(*bff("POST", f"{wg}/open-punten/{punt['id']}/besluit", {**besluit, "verwachte_revisie": punt["revisie"]}),
                f"Keuze {p['sleutel']}")
        log(f"Open punt {p['sleutel']}: {'bestond al' if al else 'gemaakt' if uitvoeren else 'te maken'}"
            f"{', keuze ' + besluit['gekozen'] if besluit else ''}.")

    los = oplosser(begrip_ids, element_ids, extra)
    for w in PARAMETERWAARDEN:
        invoer = los(w)
        al = [x for x in waarden if x["parameter_begrip_id"] == invoer["parameter_begrip_id"]
              and x["waarde"] == invoer["waarde"] and x.get("eenheid", "") == invoer["eenheid"]]
        naam = f"{w['waarde']} {w['eenheid']}"
        if al:
            v.bestond["parameterwaarde"].append(naam)
            continue
        v.gemaakt["parameterwaarde"].append(naam)
        if uitvoeren:
            _ok(*bff("POST", f"{wg}/parameterwaarden", invoer), f"Parameterwaarde {naam}")
    return v


# --- de verbinding: de BFF met een accounttoken, zoals de acceptatie-MCP -----------------------------------------------

class _GeenDoorverwijzing(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003 - de vorm van urllib
        return None


def bff_client(basis: str, token: str, timeout: float = 120) -> Bff:
    basis = basis.rstrip("/")
    if not basis.startswith("https://"):
        raise ImportFout("De basis-URL begint met https://.")
    koekjes = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(koekjes), _GeenDoorverwijzing)

    def verzoek(methode: str, pad: str, body: Any = None, formulier: dict | None = None) -> tuple[int, Any]:
        data, kop = None, {}
        if body is not None:
            data, kop = json.dumps(body).encode(), {"Content-Type": "application/json"}
        if formulier is not None:
            data, kop = urllib.parse.urlencode(formulier).encode(), {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            antwoord = opener.open(urllib.request.Request(basis + pad, data=data, headers=kop, method=methode),
                                   timeout=timeout)
        except urllib.error.HTTPError as e:
            antwoord = e
        tekst = antwoord.read().decode()
        try:
            return antwoord.status, (json.loads(tekst) if tekst else None)
        except ValueError:
            return antwoord.status, tekst

    def login() -> None:
        koekjes.clear()
        _, csrf = verzoek("GET", "/api/auth/csrf")
        verzoek("POST", "/api/auth/callback/api-token",
                formulier={"csrfToken": csrf["csrfToken"], "token": token, "callbackUrl": basis})
        if not any("session-token" in k.name for k in koekjes):
            raise ImportFout("Inloggen met het accounttoken is geweigerd.")

    def bff(methode: str, pad: str, body: Any = None) -> tuple[int, Any]:
        if not any("session-token" in k.name for k in koekjes):
            login()
        status, data = verzoek(methode, pad, body)
        if status == 401:                 # de sessie duurt een uur
            login()
            status, data = verzoek(methode, pad, body)
        return status, data

    return bff


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--uitvoeren", action="store_true", help="schrijf echt; zonder deze vlag alleen lezen en tellen")
    ap.add_argument("--werkgebied", default="", help=f"het id van het werkgebied (standaard: het werkgebied "
                                                     f"{WERKGEBIED_NAAM!r})")
    args = ap.parse_args(argv)
    basis, token = os.environ.get("WETSANALYSE_ACC_URL", ""), os.environ.get("WETSANALYSE_ACC_TOKEN", "").strip()
    if not basis or not token:
        print("Zet WETSANALYSE_ACC_URL en WETSANALYSE_ACC_TOKEN.", file=sys.stderr)
        return 2
    try:
        bff = bff_client(basis, token)
        wid = args.werkgebied or werkgebied_id(bff, WERKGEBIED_NAAM)
        verslag = importeer(bff, wid, args.uitvoeren)
    except ImportFout as e:
        print(f"Gestopt: {e}", file=sys.stderr)
        return 1
    print(("Uitgevoerd" if args.uitvoeren else "Droog (niets geschreven)") + f" in werkgebied {wid}:")
    for regel_ in verslag.regels():
        print("  " + regel_)
    return 0


if __name__ == "__main__":
    sys.exit(main())
