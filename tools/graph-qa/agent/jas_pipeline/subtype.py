"""JAS-subtype binnen een samengevoegde klasse (ADR-001 §10.1, plan herkomst).

Het platform kent dertien labels waar de officiële tabel zestien begrippen noemt: Variabele en
Variabelewaarde, Parameter en Parameterwaarde, Delegatiebevoegdheid en Delegatie-invulling zijn
samengevoegd. Het subtype maakt dat onderscheid machineleesbaar zonder de labels te breken.

Daarnaast draagt een Tijdsaanduiding één **verbijzondering**. Een formulering kan zowel tijdsaanduiding
als parameter zijn, en JAS kiest dan de meest specifieke klasse (H2:107, JAS-PRIORITY-001). Een duur of
hoeveelheid in de tijdsaanduiding ('zes weken', 'binnen 48 uur') is een vaste waarde uit de wettekst zelf:
het element blijft één Tijdsaanduiding, en het subtype legt vast dat die een parameter verbijzondert. Geen
tweede markering (ADR-001 PR 8, aanvulling 7 nov 2026). Een los getal erin ('48') is een eigen, geneste
Parameter met subtype parameterwaarde (detectorregel `jas.waarde.getal_in_duur`).

Alleen waar het **bewijs** het eenduidig maakt; anders leeg. Nooit geraden: een leeg subtype is een
eerlijke "onbepaald", een verkeerd subtype is een stille fout.

| klasse | subtype | bewijs (detectiecodes) |
|---|---|---|
| Variabele en variabelewaarde | variabelewaarde | een concrete waarde: bedrag, percentage, datum (H2:82) |
| Variabele en variabelewaarde | variabele | een eigenschap-naamwoord ('de hoogte van …') (H2:80) |
| Parameter en parameterwaarde | parameterwaarde | bedrag, percentage, veelvoud, getal in een duur (H2:91) |
| Parameter en parameterwaarde | parameter | een parameterwoord ('tarief', 'drempel') (H2:89) |
| Delegatiebevoegdheid en delegatie-invulling | delegatiebevoegdheid | de delegatieformule (H2:127) |
| Tijdsaanduiding | verbijzondert parameter | een duur of hoeveelheid als kern van de tijdtreffer (H2:107) |

Delegatie-invulling vraagt de graaf (de bovenliggende grondslag) en blijft hier leeg. Een datum of een
relatieve periode ('de overige dagen') zegt niet eenduidig of hij een parameter of een variabele
verbijzondert, en blijft leeg.
"""
from __future__ import annotations

import json
from collections.abc import Iterable

VAR, PAR, DEL = ("Variabele en variabelewaarde", "Parameter en parameterwaarde",
                 "Delegatiebevoegdheid en delegatie-invulling")
TIJD = "Tijdsaanduiding"
VERBIJZONDERT_PARAMETER = "verbijzondert parameter"

#: Tijdcodes waarvan de kern een duur of hoeveelheid is (`{TELWOORD} {PERIODE}`, zie `regels/tijd.yaml`).
#: `TEMPORAL_RELATIVE_PERIOD` hoort er niet bij: zijn telwoord is optioneel ('de overige dagen').
DUURCODES = frozenset({"TEMPORAL_DURATION", "TEMPORAL_PERIOD_OF", "TEMPORAL_RECURRENCE"})

#: klasse → [(subtype, codes die het aanwijzen)]
REGELS: dict[str, tuple[tuple[str, frozenset[str]], ...]] = {
    VAR: (("variabelewaarde", frozenset({"MONEY_AMOUNT", "PERCENTAGE", "COUNT", "TEMPORAL_DATE"})),
          ("variabele", frozenset({"PROPERTY_NOUN"}))),
    PAR: (("parameterwaarde", frozenset({"MONEY_AMOUNT", "PERCENTAGE", "COUNT", "MULTIPLIER",
                                         "DURATION_NUMBER"})),
          ("parameter", frozenset({"PARAMETER_NOUN"}))),
    DEL: (("delegatiebevoegdheid", frozenset({"DELEGATION_FORMULA"})),),
    TIJD: ((VERBIJZONDERT_PARAMETER, DUURCODES),),
}

#: Elk subtype dat een element kan dragen, ook wat de keten zelf niet zet (delegatie-invulling vraagt de
#: graaf). De api (`annotatie_v2_contracts`) en de zoektool staan precies deze waarden toe;
#: `tests/test_contract_drift.py` bewaakt dat, `tests/test_subtype.py` dat REGELS er binnen blijft.
ALLE_SUBTYPEN: tuple[str, ...] = ("variabele", "variabelewaarde", "parameter", "parameterwaarde",
                                  "delegatiebevoegdheid", "delegatie-invulling", VERBIJZONDERT_PARAMETER)

#: Subtypen die geen eigen officieel begrip zijn maar een verbijzondering:
#: subtype → (klasse, verbijzonderde klasse, bron). De vocabulaire maakt er een eigen concept van.
VERBIJZONDERINGEN: dict[str, tuple[str, str, str]] = {VERBIJZONDERT_PARAMETER: (TIJD, PAR, "H2:107")}


def codes_van(evidence: Iterable) -> list[str]:
    """De bewijscodes van een kandidaat. Een geregistreerde tijdkern (`TEMPORAL_KERNEL`) draagt geen eigen
    tijdbewijs, maar noemt de codes van zijn ouder in het detail. Die tellen hier mee: de kern ís de duur
    van die treffer."""
    uit = []
    for e in evidence:
        uit.append(e.code)
        if e.code == "TEMPORAL_KERNEL":
            try:
                uit += json.loads(e.detail or "{}").get("codes", [])
            except (ValueError, AttributeError):
                pass
    return uit


def bepaal(klasse: str, codes: Iterable[str]) -> str:
    """Het subtype, of "" als het bewijs niets of iets tegenstrijdigs zegt."""
    codes = set(codes)
    treffers = {subtype for subtype, aanwijzers in REGELS.get(klasse, ()) if codes & aanwijzers}
    return treffers.pop() if len(treffers) == 1 else ""
