"""XML van buiten lezen: de stukken van overheid.nl, de Rechtspraak en de SRU-zoekdiensten.

Eén ingang in plaats van `ET.fromstring` verspreid over de adapters. `defusedxml` weigert entiteitdeclaraties en externe
verwijzingen (billion laughs, XXE); de DOCTYPE die KOOP meestuurt, met een externe DTD en een lege interne subset, blijft
gewoon leesbaar. Een weigering komt terug als `ET.ParseError`, zodat elke aanroeper haar afhandelt zoals elke andere
onleesbare XML: als een onbruikbaar antwoord, nooit als een crash.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring as _fromstring


def lees_xml(data: bytes | str) -> ET.Element:
    """De wortel van `data`; een entiteit- of externe declaratie is een `ET.ParseError`."""
    try:
        return _fromstring(data)
    except DefusedXmlException as exc:
        raise ET.ParseError(f"XML geweigerd: {type(exc).__name__}") from exc
