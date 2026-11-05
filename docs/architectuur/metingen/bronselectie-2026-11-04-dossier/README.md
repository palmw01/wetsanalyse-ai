# Meting bronselectie – het dossier zoekt mee (4 nov 2026)

Soort: *meting* · Hoort bij: PLAN spoor F *Vervolg*, het zoeken en rangschikken van `bepaling_opties` · 0 modelcalls

## Vraag

In `bepaling_opties` telt het dossier alleen mee voor de volgorde, als één lijst op het aantal geraakte
dossiertermen (analysevraag, praktijkvoorbeeld, context). De aanleiding en het doel worden niet gelezen. Op
3 nov 2026 bleek dat de held-out set *bestuurdersaansprakelijkheid* verliest op woorden: de analist schrijft
"melden", de wet "mededeling". Helpt het als het dossier echt meezoekt?

## Opzet

Er zijn vier nieuwe vlaggen op `Zoekprofiel` (`tools/graph-qa/agent/deelvraag_zoeken.py`), elk standaard uit:

| vlag | ingreep |
|---|---|
| `dossier_velden` | de dossiertermen komen ook uit de aanleiding en het doel |
| `dossier_lijsten` | elke dossierterm is een eigen indexlijst per regeling, in de pool en in de fusie (in plaats van de lijst op aantal); een optie moet nog steeds een deelvraagterm raken (spoor K) |
| `dossier_omgeving` | het artikel of de eerste divisie van een beleidsregel krijgt een rang op de dossiertermen die het raakt, gewogen naar zeldzaamheid in de pool (idf); die rang is een extra RRF-lijst |
| `gelijkenis` | `bwb_similarity` op de deelvraag met het praktijkvoorbeeld, als extra lijst binnen de regelingen; een treffer telt als raak aan de deelvraag |

- **Kiezen** gebeurde op drie ontwikkelsets: bezwaar, invorderbaarheid per deelvraag en
  bestuurdersaansprakelijkheid. De opnames zijn live aangevuld (`--aanvullen`), via de acc-proxy en
  `SIMILARITY_INDEX=bwb_similarity`. Daarnaast is de maat `gedeeld` nieuw: het aandeel opties dat bij meer dan
  één deelvraag staat. Die bewaakt spoor K.
- **Blind** is gemeten op een nieuwe held-out set `kwijtschelding-concept` (#803):
  - de stof is Iw 26, de Uitvoeringsregeling Iw 1990 en Leidraad 26;
  - het is de eerste set met aanleiding en doel;
  - er zijn 4 deelvragen in de woorden van een analist, met 24 verwachte bepalingen, waarvan 21 nodig;
  - de set is gecommit vóór de code en één keer live opgenomen (`--opnemen`) tegen acceptatie.

## Uitkomst

Recall nodig, met tussen haakjes de pool:

| route | bezwaar | invorderbaarheid | bestuurdersaansprakelijkheid | **kwijtschelding (blind)** |
|---|---|---|---|---|
| standaard | 0,53 (0,84) | 0,36 (0,94) | 0,22 (0,91) | **0,10 (0,33)** |
| met `dossier_velden` | 0,53 | 0,36 | 0,22 | 0,10 |
| met `dossier_lijsten` | 0,53 (0,84) | 0,36 (1,00) | 0,22 (0,95) | 0,05 (0,54) |
| met `dossier_omgeving` | 0,40 | 0,36 | 0,28 | 0,10 |
| met `gelijkenis` | 0,53 | 0,36 | 0,22 | 0,10 |
| met alle vier | 0,40 | 0,36 | 0,22 | 0,05 (0,54) |

`gedeeld` (standaard → `dossier_lijsten`): 0,48 → 0,65, 0,43 → 0,65, 0,40 → 0,55 en blind 0,30 → 0,48.

**Besluit: alle vier blijven uit.** Op de ontwikkelsets wint geen van de vier zonder elders te verliezen, en op de
blinde set evenmin.

## Wat het zegt

- **`dossier_velden`** verandert niets. De ontwikkelsets hebben geen aanleiding en geen doel. Op de blinde set,
  die ze wel heeft, leveren ze geen woorden op die het verschil maken.
- **`dossier_lijsten`** vindt meer: de pool gaat blind van 0,33 naar 0,54. Toch zakt de recall nodig.
  - Elke dossierterm is een eigen lijst, en een bepaling die veel dossiertermen raakt, stapelt bijdragen. Zo
    verdringt ze de bepaling die de deelvraag beantwoordt.
  - De kaartjes gaan op elkaar lijken (`gedeeld` stijgt overal). Dat is precies de regressie die spoor K
    voorkwam.
  - Het meezoeken werkt dus wel, maar als gelijke lijst in de fusie hoort het dossier niet.
- **`dossier_omgeving`** wisselt per set: bestuurdersaansprakelijkheid +0,06, bezwaar −0,13, blind gelijk.
  - Zonder idf won een grote divisie (Leidraad 25, 30 teksten) door haar gewone woorden: "ontvanger",
    "betalen", "pas".
  - Met idf onderscheidt de omgeving beter, maar het werkgebied is breder dan één artikel. Bij bezwaar gaan de
    deelvragen over verschillende artikelen.
- **`gelijkenis`** helpt niet. Van de 40 treffers van `bwb_similarity` op een deelvraag vallen er hooguit enkele
  binnen de regelingen, en die gaan over iets anders. "Melden … niet kan betalen" gaf bijvoorbeeld Leidraad 58.2
  en 35.12.4. Bij deze index is de woordenkloof met gelijkenis niet te overbruggen.
- **Het verlies op de blinde set zit nu al in het zoeken** (pool 0,33), niet pas in de rangschikking zoals op
  3 nov. De deelvragen en de analysevraag zeggen nergens "kwijtschelding": "de belastingschuld laten vervallen",
  "niet genoeg inkomen", "spaargeld". Alleen de **naam** van het werkgebied ("Kwijtschelding voor
  particulieren") draagt het woord van de wet, en het zoeken leest de naam niet.
- **Bijvangst, niet doorgevoerd:**
  - "haar" en "iemand" worden zoektermen (`zoektermen._GEEN_TERM` mist ze).
  - Ze toevoegen veranderde op de ontwikkelsets niets aan de recall, en bij bestuurdersaansprakelijkheid stonden
    er twee uitgesloten bepalingen meer in de top.
  - Omdat de meting het niet rechtvaardigt, is het teruggedraaid.

## Volgende stap

Het dossier hoort niet als extra lijst in de fusie, maar als de **woorden van de wet** waarmee de deelvraag
zoekt. Twee kandidaten, elk als eigen vlag en op een nieuwe set:

1. **De naam en de begrippen van het werkgebied**: de naam ("Kwijtschelding …") en de NL-SBB-begrippen of
   `bwb:definieertBegrip` uit de gekozen regelingen leveren termen van de wet. Die zoeken mee met elke
   deelvraag en tellen als deelvraagterm.
2. **De koppen van de gekozen regelingen**: een deelvraagwoord dat een kop raakt ("vermogen", "betalingscapaciteit"),
   brengt de termen van die kop als zoekterm mee.

Het RRF-ontwerp zelf is een open punt: het aantal lijsten waarin een bepaling voorkomt, weegt zwaarder dan wat
ze raakt. 36.5.1 raakt "melden" en stond op plek 16, achter bepalingen die alleen "belastingen" en "betalen"
raken. Op 3 nov won "zonder fusie" daar ook al.

Alle vier sets zijn nu ontwikkelsets.

## Reproduceren

```bash
cd tools/graph-qa
uv run python -m eval.bronselectie_eval --intake --set kwijtschelding-concept                 # offline op de opname
uv run python -m eval.bronselectie_eval --intake --set bestuurdersaansprakelijkheid-concept
uv run python -m eval.bronselectie_eval --intake --set invorderbaarheid-deelvragen-concept
uv run python -m eval.bronselectie_eval --intake --set bezwaar-ontvankelijkheid-concept
```

`tests/test_bronselectie_eval.py` pint de getallen, en `tests/test_bronnen_vinden.py` toetst elke vlag.
