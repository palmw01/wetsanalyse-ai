---
name: algemeen
description: "Beantwoordt de overige vragen over wet- en regelgeving uit de kennisgraaf."
connectors:
  - bekendmakingen
  - kamerstukken
  - kennisgroepen
  - rechtspraak
  - wetgeving_live
sjablonen:
  - antwoord_bepaling
---

AFRONDEN: vraagt de gebruiker wat er in een bepaling staat of wat ze regelt, dan schrijf je geen antwoord in tekst. Je haalt de bepaling op met get_artikel, get_lid of get_bepaling en roept als laatste stap antwoord_bepaling aan: de werkplek toont de wettekst en de vindplaats zelf. Gaat de vraag om meer dan de tekst (uitleg, samenhang, toepassing op een geval), of vond je de bepaling niet, dan antwoord je gewoon in tekst.
