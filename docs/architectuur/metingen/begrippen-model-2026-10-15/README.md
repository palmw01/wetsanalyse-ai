# Begrippenketen + model (spoor D, fase C1) – 15 oktober 2026

Soort: *meting* · Code: `b6fded1` (branch `feat/fase-c1-begrippen-model`) · Model: `claude-sonnet-4-6`
(lokaal `LLM_MODEL`) · Promptversies: vraag `315b1c53355e`, kaart zie `*.json`

## Wat er gemeten is

`python -m eval.begrippen_eval --model --versie <set> --json`, op de drie begrippensets, elk met
drie herhalingen van het model (de keten zelf draait één keer: die is deterministisch). Gemeten:

- paarsgewijze precisie/recall voor *zelfde betekenis* en BCubed, vóór en na het model;
- `samengevoegd verschillend` – paren die volgens de set verschillend zijn maar toch in één groep
  staan (moet 0 zijn);
- **garanties**: per kaart elk fragment-id bestaat, elk fragment staat letterlijk op zijn offsets,
  een letterlijke definitie staat in haar bron, een samengestelde is precies haar fragmenten (moet 0
  fouten zijn);
- de herkomst van de kaarten en de open vragen (geel).

Alle drie de sets zijn **provisional** en inmiddels **ontwikkelsets**: v1 en heldout-v1 waren dat al,
en heldout-v2 (AWR) is hier gebruikt om een ontwerpfout te vinden (zie onder). Dit is een
trendmeting, geen kwaliteitsoordeel; generalisatie vraagt een nieuwe, onbekende set.

## Uitkomst

| set | zelfde P | zelfde R | BCubed F | samengevoegd verschillend | garantiefouten | modelcalls/run |
|---|---:|---:|---:|---:|---:|---:|
| v1 (IW 1990), zonder model | 1,0 | 1,0 | 1,0 | 0 | – | 0 |
| v1, 3 runs | 1,0 | 1,0 | 1,0 | 0 | 0 | 2 |
| heldout-v1 (Awir), zonder model | 1,0 | 0,75 | 0,956 | 0 | – | 0 |
| heldout-v1, 3 runs | 1,0 | 0,75 | 0,956 | 0 | 0 | 0 |
| heldout-v2 (AWR), zonder model | 1,0 | 0,83 | 0,973 | 0 | – | 0 |
| heldout-v2, 3 runs | 1,0 | 0,83 | 0,973 | 0 | 0 | 2 |

Per run in `v1.md`, `heldout-v1.md`, `heldout-v2.md`; alles, met de oordelen en kaarten, in de
`.json`-bestanden.

**Garanties: 100% in alle negen runs.** Geen gefingeerd id, geen niet-letterlijke tekst.

**Het model levert hier geen recall op.** In heldout-v1 zijn de gemiste paren (4 van 16) paren
waarvoor de keten geen vraag stelt; er gaat niets naar het model (de enige open vraag is een paar dat
de wet als relatie noemt, `Z-RELATIE-GAAT-VOOR`, en dat gaat er bewust niet heen). In heldout-v2 is de
enige misser wél een vraag ("Mogendheid", hieronder), en die beoordeelt het model fout. Recall winnen
vraagt dus vooral meer kandidaten van de keten; waar het model wel een vraag krijgt, is één van de
twee gevallen goed.

**Twijfelparen.** v1 "termijnen" (art. 9 lid 5 tegen lid 10, homoniem in de set): drie keer
*verwant, ander begrip* – juist. heldout-v2 "Mogendheid" (AWR art. 2 lid 2 onder c en d, zelfde
begrip in de set): *betekenisverschil*, *betekenisverschil*, *verwant* – fout, in alle runs. Door de
ontwerpkeuze hieronder blijft die vraag wel voor de jurist staan.

**Kaarten.** Letterlijke definities komen zonder model en zijn er voor elke groep waarvan een lid
de term van een begripsbepaling is. Samengesteld: "aanslagbiljet" → "de kennisgeving van de
beschikking of de uitspraak, bedoeld in onderdeel c" (v1, 3/3). Waar de wet alleen een opsomming
geeft ("navorderingsaanslag", "voorlopige aanslag"), geeft het model eerlijk geen definitie.

## Wat de meting aan het ontwerp veranderde

Drie ronden op dezelfde dag; de ruwe gegevens van de eerste twee zijn niet bewaard, de uitkomsten
staan hier.

1. **Eerste versie** (`f72e3ba`, alleen de bronzin rond de formulering in de prompt): v1 voegde de
   homoniem "termijnen" in 3/3 runs samen (zelfde P 0,957). Oorzaak: lid 10 zegt "de in de
   voorgaande leden gestelde termijnen" – zonder de bepaling ziet het model niet dat dat ruimer is.
   Aanpassing: de hele bepaling met de formulering tussen `[[ ]]`, en de algemene instructie eerst
   de precieze referent te bepalen (ruimer of smaller = verwant). Ook viel de kale term als
   fragment weg ("aanslagbiljet … de kennisgeving …").
2. **Scheiding door het model liet de vraag verdwijnen** (`f72e3ba`): bij "Mogendheid" (AWR) was de
   vraag dan weg, terwijl het oordeel fout was. Een foute samenvoeging is zichtbaar (gele groep),
   een foute scheiding niet. Aanpassing (`e8e2a89`): alleen *zelfde betekenis* wordt een link; de
   andere oordelen blijven als advies bij de vraag.
3. **Cirkeldefinities** (`e8e2a89`): in één run van v1 formuleerde het model drie keer "een X is
   een belastingaanslag in de vorm van een X". De toets ving het; nu wordt zo'n definitie niet
   overgenomen (`b6fded1`, `CIRCULAIR_VERWORPEN`).

## Open

- Recall: kandidaten voor de gemiste paren (zie het held-out-verslag van 14 okt) – keten, geen model.
- Een nieuwe, onbekende set voor een generalisatiemeting, en adjudicatie door een jurist.
- Signaal CIRCULAIR bij samengestelde wettekst die de term herhaalt ("beschikking of uitspraak",
  "vereniging"): terecht geel, maar het fragment van "vereniging" begint midden in een zin
  ("van vereniging, is daaronder begrepen …") – knippen op `;` en `:` is daar te grof.
