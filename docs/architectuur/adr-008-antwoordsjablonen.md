# ADR-008: Antwoordsjablonen, het antwoord als toolaanroep

**Status:** aangenomen, 6 nov 2026. Geldt nu voor het sjabloon `begrip`; de andere volgen na de meting op acceptatie.

## Context

De antwoordketen eindigde in vrije tekst. Het model typte citaat, vindplaats en status over uit de tool-rijen en bedacht de indeling zelf, de controle werkte op één string, en de graaf viste zijn doelen uit de proza. Eenzelfde vraag kon er elke keer anders uitzien.

## Besluit

**Een sjabloon is een tool waarmee een specialist zijn beurt afrondt.** De code vult de feiten uit wat de graaf teruggaf, het model levert alleen wat een oordeel of formulering vraagt, en de werkplek tekent vaste blokken.

```
agent ⇄ tools → sjabloontool → sjabloon → verify → (correct) → finalize
```

- **Contract:** `bronmodel/antwoord.py`, gedeeld door api en graph-qa. De blokken zijn een gesloten lijst; `frontend/lib/antwoord.ts` is de spiegel, en een test leest de bron.
- **`door`:** elk blok zegt of het uit de bron komt of van Lex.
- **`tekst` blijft.** `antwoord_tekst` maakt vaste Markdown uit de blokken: die voedt de controle, de historie, *Kopieer* en de eval. Een vorm die de blokken niet kent, gebruikt de tekst.
- **Niet te vullen is een fout aan het model** (`Onvulbaar`, `is_error`), nooit een halve vulling.
- **Niets gevonden is een `leemte`:** "in de graaf bij deze term", nooit "bestaat niet".
- **Vrije tekst blijft geldig.** `tool_choice` blijft `auto`, dus het model kán tekst schrijven; `sjabloon gemist` in de log telt hoe vaak.

## Waarom niet anders

- **Geen A2UI of ander UI-protocol:** de interface staat vast, dus een eigen set componenten is eenvoudiger.
- **Het model stelt geen blokken samen:** strict tools hebben per verzoek grenzen op optionele en union-parameters, en feiten horen niet door het model te gaan. Per sjabloon één kleine, platte tool.
- **Geen Citations-api:** die werkt niet samen met JSON-uitvoer. Hier doet de code hetzelfde: het model wijst aan, iets anders levert de letterlijke tekst.
- **Geen aparte tweede modelaanroep om tekst om te zetten:** de afronding zit in dezelfde lus, dus er komt geen ronde bij.

## Gevolgen

Sjabloontools staan los van `TOOLS`: ze staan niet op de MCP-server. Decompositie (op Azure uit) blijft vrije tekst. Een nieuw sjabloon: een module in `agent/sjablonen/`, een regel in `SJABLONEN`, de naam in `Specialist.sjablonen`, en voor een nieuw blok een component in `BLOKKEN`.
