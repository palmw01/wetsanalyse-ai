# Staatsblad en Staatscourant, iteratie – ronde 6 (12 november 2026)

Soort: *meting* · Code: master `66e73f75` (bundels 52 en 53: #1260 de fixes van ronde 5, #1259 Kamerstukken, #1261 per
vraag alleen de passende connectortools, #1262 een lijst in tekst wordt in code een sjabloon) · Straat: acceptatie ·
Model: `claude-sonnet-4-6` · Uitvoering: zoals [ronde 5](ronde-5.md), dezelfde 30 vragen, elk één keer, vier
tegelijk. Ruwe gegevens staan in [`runs.jsonl`](runs.jsonl) (`ronde: 6`). Tokens = invoer + uitvoer + cache lezen +
cache schrijven, uit het `meting`-event. Dit is de laatste ronde; geen nieuwe fixes, alleen bevindingen.

**Bronstand.** Bij het begin van elke beurt stonden alle vier de connectors aan, net als in ronde 5 (het eerste
`bronstand`-event, reden "aan"). Sinds #1261 volgt er een tweede `bronstand`-event dat per vraag versmalt (reden
"vraag"); zie bevinding 1.

Twee starts strandden in het script op een geweigerde login van het accounttoken (B02, B03). Ze zijn meteen in een
nieuw gesprek opnieuw gedraaid, en die tellen.

## Uitkomst

**28 goed, 1 deels, 1 fout** (ronde 5: 28, 2, 0). **Samen 1.042.354 tokens** (ronde 5: 1.422.232, −27%; ronde 4:
1.153.439). **44 modelrondes**, 12 vragen zonder model.

| # | oordeel (r5 → r6) | tokens (r5 → r6) | rondes |
|---|---|---|---|
| B03 | **deels → goed** | 135.225 → 102.142 | 4 |
| B04 | goed → goed | 234.582 → 160.515 | 6 |
| B18 | goed → **fout** | 184.237 → 21.560 | 1 |
| B21 | goed → goed | 45.040 → 36.798 | 1 |
| B24 | goed → goed | 117.377 → 151.256 | 6 |
| B26 | deels → deels | 129.623 → 104.922 | 4 |

Wie in één ronde een stuk leest (B06, B08, B09, B12, B25, B27, B30), kost weer 20–23k tokens, net als in ronde 4. De
~8k extra van ronde 5 is weg.

**Garanties:**
- geen run ongegrond;
- 0 niet-letterlijk;
- geen naam van een particulier (B15, B30);
- geen `id_niet_uit_gesprek`: geen vraag gaf het model reden om een id uit eigen kennis te gebruiken.

### Correctierondes en `meting.sjabloon`

Opgeteld over de 30 vragen:
- `gevuld`: 15;
- `geweigerd`: 1 (`extern.blokken`, bij B16);
- `gemist`: 3 (B15, B30, en B18 zonder resultaat);
- `tekst_ernaast`: 3.588 tekens, bij 12 antwoorden.

Er was dus **één correctieronde** (ronde 5: vier). De twee geweigerde `duiding.vul` van B04 en de `extern.lijsten` van
B18 zijn weg.

## Wat de fixes deden

- **#1260, de zoekvraag zonder lege plek** (B03): "Gezocht bij artikel  van BWBR0004770" staat er niet meer. B03 telt nu
  ook goed ("vier wetten/besluiten", met de vier erbij): deels → goed. Dat is spreiding van het model, geen fix.
- **#1260, "horen bij" zonder regeling** (B18): de lijstroute leest "Kamerdossier 36602" weer (lokaal getoetst op
  `66e73f75`: `zoek_kamerstukken {dossier: 36602}`). Op acceptatie kreeg de route Kamerstukken alleen niet meer aangeboden;
  zie bevinding 1.
- **#1262 en #1251**: B04 haalt het sjabloon zonder weigering, 235k → 161k.

## Bevindingen (benoemd, niet opgelost)

1. **B18 zegt dat een connector uit staat terwijl hij aan staat** (gedeeld, uit #1261). "Welke publicaties horen bij
   Kamerdossier 36602?" Het woord "publicaties" wijst Staatsblad en Staatscourant aan. Het tweede `bronstand`-event zet
   Kamerstukken, Rechtspraak en Wetgeving buiten de kennisgraaf daarom uit, met reden "vraag". Daarna gebeurde dit:
   - de lijstroute zag alleen Staatsblad en Staatscourant, en die kan het dossier niet lezen;
   - het model riep `zoek_kamerstukken` toch aan en kreeg `connector_uit`;
   - Lex zei tegen de jurist: "Kamerstukken staan in dit gesprek uit … noem ze dan expliciet". Dat is niet waar: de
     jurist zette niets uit.

   Een versmalling per vraag hoort de jurist niet als "uit" te horen. De connector die het filter van de vraag draagt
   (hier het dossier), hoort erbij te blijven. Dat is aan de eigenaar van #1261.
2. **Tellingen in de eigen toelichting** (B26: "op vier punten, alle in artikel 25 en één in 28, één in 36 en één nieuw
   artikel 45"). De onderdelen A–D eronder kloppen. Zoals in ronde 5 toetst de beweringentoets geen aantallen.
3. **B24 en B23 lezen meer dan nodig.** B24 vraagt nog `geldigheid` na het lezen van de bekendmaking (117k → 151k). B23
   leest de memorie van toelichting erbij, wat de terugwerkende kracht juist goed maakt (126k). Dit is spreiding van het
   model, geen defect.

## Wat deze ronde niet zegt

Eén run per vraag. De tekst is gelezen bij B03–B05, B09, B12, B15, B16, B18 en B21–B26. Bij de andere vragen zijn
alleen de route, de tokens, de bronnen en de grounding nagelopen.
