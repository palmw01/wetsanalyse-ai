"""De lezer van de BWB-toestand-XML: één code voor de importer en voor de connector `wetgeving_live`.

De importer (`tools/bwb-import`) zet een toestand in de graaf; de connector (graph-qa, ADR-013) leest een regeling of
een toestand die niet in de graaf staat. Lezen ze met dezelfde parser, dan is de tekst gelijk, en dus ook de
teksthash, de tekstankers en de jci. Een tweede lezer zou op den duur afwijken, en dan zou dezelfde bepaling twee
teksten hebben.

Vraagt lxml: installeer `wetsanalyse-bronmodel[bwb]`. De api gebruikt dit deel niet en installeert de extra niet.
"""
from __future__ import annotations

from pathlib import Path

#: De officiële XSD's van de BWB (toestand en WTI), met `toestand.xsd` als ingang.
SCHEMAS = Path(__file__).resolve().parent / "schemas"
TOESTAND_XSD = SCHEMAS / "toestand.xsd"
