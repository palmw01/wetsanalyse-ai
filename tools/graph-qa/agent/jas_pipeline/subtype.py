"""JAS-subtype binnen een samengevoegde klasse (ADR-001 §10.1, plan herkomst).

Het platform kent dertien labels waar de officiële tabel zestien begrippen noemt: Variabele en
Variabelewaarde, Parameter en Parameterwaarde, Delegatiebevoegdheid en Delegatie-invulling zijn
samengevoegd. Het subtype maakt dat onderscheid machineleesbaar zonder de labels te breken.

Alleen waar het **bewijs** het eenduidig maakt; anders leeg. Nooit geraden: een leeg subtype is een
eerlijke "onbepaald", een verkeerd subtype is een stille fout.

| klasse | subtype | bewijs (detectiecodes) |
|---|---|---|
| Variabele en variabelewaarde | variabelewaarde | een concrete waarde: bedrag, percentage, datum (H2:82) |
| Variabele en variabelewaarde | variabele | een eigenschap-naamwoord ('de hoogte van …') (H2:80) |
| Parameter en parameterwaarde | parameterwaarde | bedrag, percentage, veelvoud (H2:91) |
| Parameter en parameterwaarde | parameter | een parameterwoord ('tarief', 'drempel') (H2:89) |
| Delegatiebevoegdheid en delegatie-invulling | delegatiebevoegdheid | de delegatieformule (H2:127) |

Delegatie-invulling vraagt de graaf (de bovenliggende grondslag) en blijft hier leeg.
"""
from __future__ import annotations

from collections.abc import Iterable

VAR, PAR, DEL = ("Variabele en variabelewaarde", "Parameter en parameterwaarde",
                 "Delegatiebevoegdheid en delegatie-invulling")

#: klasse → [(subtype, codes die het aanwijzen)]
REGELS: dict[str, tuple[tuple[str, frozenset[str]], ...]] = {
    VAR: (("variabelewaarde", frozenset({"MONEY_AMOUNT", "PERCENTAGE", "TEMPORAL_DATE"})),
          ("variabele", frozenset({"PROPERTY_NOUN"}))),
    PAR: (("parameterwaarde", frozenset({"MONEY_AMOUNT", "PERCENTAGE", "MULTIPLIER"})),
          ("parameter", frozenset({"PARAMETER_NOUN"}))),
    DEL: (("delegatiebevoegdheid", frozenset({"DELEGATION_FORMULA"})),),
}


def bepaal(klasse: str, codes: Iterable[str]) -> str:
    """Het subtype, of "" als het bewijs niets of iets tegenstrijdigs zegt."""
    codes = set(codes)
    treffers = {subtype for subtype, aanwijzers in REGELS.get(klasse, ()) if codes & aanwijzers}
    return treffers.pop() if len(treffers) == 1 else ""
