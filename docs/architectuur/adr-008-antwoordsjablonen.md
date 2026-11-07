# ADR-008: Antwoordsjablonen, het antwoord als toolaanroep

**Status:** aangenomen, 6 nov 2026. Geldt voor de sjablonen `begrip` (ook de begrippen-leesroute: zonder term een lijst uit `search_begrippen`, zonder uitspraak over de wet), `bepaling`, `duiding` en `annotaties`. De overzichtsroute krijgt er bewust geen.

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
- **Een bepaling is compleet of ze wordt niet getoond.** `get_artikel` levert de onderdelen onder een lid niet mee, dus markeert die leden; het sjabloon weigert tot `get_lid` ze heeft opgehaald.
- **Een passage hoort bij de aangewezen bepaling.** `duiding` toetst elk fragment tegen de tekst van die bepaling, en een bepaling die de uitleg noemt zonder passage gaat terug naar het model; de uitleg zelf gaat als tekst door `verify`.
- **Niets gevonden is een `leemte`:** "in de graaf bij deze term", nooit "bestaat niet".
- **Vrije tekst blijft geldig.** `tool_choice` blijft `auto`, dus het model kán tekst schrijven; `sjabloon gemist` in de log telt hoe vaak.

## Waarom niet anders

- **Geen A2UI of ander UI-protocol:** de interface staat vast, dus een eigen set componenten is eenvoudiger.
- **Het model stelt geen blokken samen:** strict tools hebben per verzoek grenzen op optionele en union-parameters, en feiten horen niet door het model te gaan. Per sjabloon één kleine, platte tool.
- **Geen Citations-api:** die werkt niet samen met JSON-uitvoer. Hier doet de code hetzelfde: het model wijst aan, iets anders levert de letterlijke tekst.
- **Geen aparte tweede modelaanroep om tekst om te zetten:** de afronding zit in dezelfde lus, dus er komt geen ronde bij.

## Gevolgen

Sjabloontools staan los van `TOOLS`: ze staan niet op de MCP-server. Decompositie (op Azure uit) blijft vrije tekst. Een nieuw sjabloon: een module in `agent/sjablonen/`, een regel in `SJABLONEN`, de naam in `Specialist.sjablonen`, en voor een nieuw blok een component in `BLOKKEN`.

De overzichtsroute krijgt geen sjabloon: daar typt geen model feiten over, en de controle, bronnen, graaf en kopieerknop lezen `Bericht.overzicht`, dus een `Antwoord` zou die gegevens alleen dubbel dragen.

## Aanvulling (7 nov 2026): detail bij een antwoord

**Het antwoord wijst aan, het paneel vertelt de rest.** Een sjabloon toont wat het oordeel draagt: de tekst, de vindplaats en, als dat van toepassing is, dat de tekst nog niet geldt. Wat de graaf verder over een bepaling weet, staat in het paneel naast het gesprek. Dat zijn:

- de plek in de opbouw;
- de geldigheid;
- de verwijzingen in beide richtingen;
- grondslag en bevoegdheid;
- waar de bepaling genoemd wordt;
- welke begrippen ze definieert.

- **Geen nieuwe artefactsoort.** Een bepaling is geen uitkomst van een beurt: er valt niets te beoordelen. Het paneel is de bestaande context `bron`. Een chip onder het antwoord opent die context per doel, net als een klik op een vindplaats. Bij het sjabloon `annotaties` zijn het de bronnodes van de markeringen (`Markering.bron_iri`). Die zijn geen `doelen`, want een annotatie is geen bron.
- **De feiten komen van de api, niet uit de trace.** `GET /v1/annotatie/bepaling` (`api/app/bepaling_detail.py`) leest de graaf zonder model. Wat ontbreekt blijft leeg, en een haperende graaf geeft `beschikbaar: false`. De vindplaats draagt de jci die Lex las, met de toestand. Draagt de graaf nu een latere toestand, dan zegt het paneel dat.
- **Kort in het antwoord, lang in het paneel.** In het antwoord staan de vindplaats met jci en toestand, "nog niet in werking", en leden van één artikel onder één kop. In het paneel staat de rest. Het blok `verwijzingen` blijft voor later: verwijzingen horen bij naslag, niet bij het oordeel.
- **Eén graaflezing, geen gedeelde blokken.** Het paneel en het werkgebiedrapport (ADR-009) lezen dezelfde gegevens per bepaling. Daarom staan `Structuurdeel`, `Verwijzing` en `Telling` in één contract, `api/app/bepaling_graaf_contract.py`. Een generiek blokkenmodel voor gesprek, paneel en rapport is bewust niet gekozen: om dezelfde redenen als in ADR-009, en omdat het gedeelde stuk klein is. De eigenaar van die graaflezing is ADR-009. Het werkgebiedrapport hernoemt zijn lezer tot `api/app/bepaling_graaf.py` en voegt `in_dossier` toe aan `Verwijzing` en `RegelingInfo` aan het contract. Het paneel gebruikt dezelfde lezer, met de tellingen achter `met_inkomend`.
