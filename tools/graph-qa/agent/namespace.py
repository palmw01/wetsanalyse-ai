"""
De IRI-ruimte van de kennisgraaf – één bron van waarheid binnen graph-qa.

Waarom deze module bestaat. De basis-IRI wordt door de **importer** bepaald
(`tools/bwb-import/app/rdf_vocab.py`), maar hij werd hier op drie plekken los
overgetypt: als SPARQL-prefix, als filterwaarde en als regex in de
provenance-herkenning. Drie kopieën van dezelfde string die niets van elkaar
weten, is drie kansen om stil uit elkaar te lopen – en het gevolg is niet een
foutmelding maar een leeg antwoord: de filters matchen dan simpelweg niets.

De waarde is een eigenschap van de **data in de graaf**, niet van een sessie of
een omgeving: de graaf staat in `urn:bwb:` (migratie aug 2026), en graph-qa leest
hem niet meer uit `GRAPHDB_BASE_IRI` – die stond nergens anders dan de default.

De drift-guard `tests/test_namespace_drift.py` bewaakt dat deze waarden gelijk
blijven aan die van de importer en de frontend.
"""
from __future__ import annotations

import re

#: Documentruimte: de IRI's van regelingen, artikelen en leden.
BASIS = "urn:bwb:"

#: Vocabulaireruimte: de predicaten en klassen. Bewust géén vindplaatsen – zie provenance.
ONTOLOGIE = "urn:bwb-ns:"

#: Scheidingsteken tussen segmenten in een URN-ruimte. Spiegelt ``Vocab._sep`` in
#: tools/bwb-import/app/rdf_vocab.py.
SEP = ":"


def vindplaats_patroon(basis: str = BASIS) -> str:
    """Regex-patroon dat een vindplaats-IRI in vrije tekst herkent. Een backtick of sterretje hoort er niet bij:
    dat is Markdown rond de IRI (`` `urn:bwb:…` ``, **…**). Een accolade ook niet: `urn:bwb:{BWB-id}` is een patroon
    dat uitlegt hoe een IRI is opgebouwd (`graph_schema`), geen vindplaats. Zonder die uitsluiting stond
    `urn:bwb:{BWB-id` in de bronnenlijst (ronde 2 van de meting van ADR-016, K04 en K10)."""
    return re.escape(basis) + r"[^\s\"'<>)\]{}\\`*]+"
