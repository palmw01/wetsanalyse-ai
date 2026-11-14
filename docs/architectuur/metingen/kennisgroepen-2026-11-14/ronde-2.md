# Kennisgroepstandpunten, ronde 2 – 14 november 2026

- **Soort:** *meting*, de tweede en laatste ronde (plan-connector-kennisgroepen §4, licht regime: één run, alleen
  centraal, hoogstens twee rondes).
- **Code:** master `40a777fe` (bundel 108, met de fixes uit [#1466](https://github.com/palmw01/wetsanalyse-ai/pull/1466));
  api, graph-qa en bwb-import uitgerold, het budget gereset om 01:47 UTC. De fixes vragen geen nieuwe index: ze lezen
  predicaten die er al stonden (`kgo:middel`, `kgo:belastingsoort`, `kgo:kennisgroep`, `kgo:vervangtId`).
- **Uitvoering:** als ronde 1 ([`ronde-1.md`](ronde-1.md)): de 20 vragen, elk in een nieuw gesprek, met dezelfde
  `extra`. Aantekeningen per vraag in [`ronde-2-aantekeningen.md`](ronde-2-aantekeningen.md).

## Uitkomst

**Garanties 20/20; kwaliteit 16 goed, 3 matig, 1 fout** (ronde 1: 12/2/6). Het doel (≥ 17 goed, 0 fout) is net niet
gehaald. Vijf van de zes fouten uit ronde 1 zijn goed (vraag 3, 4, 8 deels, 10, 14), vraag 2 van matig naar goed. De
ene fout is nieuw in zijn vorm: de fix voor de tekststand gaf het model een stand per artikel, en het model trok die door
naar het lid.

| Garantie | Uitkomst |
|---|---|
| geen standpunt onder een `doel` of als wettekst | 20/20 |
| elk standpuntblok heeft de statusregel en een datum | 20/20 |
| een ingetrokken of vervallen standpunt nooit als geldend | 20/20 |
| elk citaat letterlijk in de gelezen tekst | 20/20 (grounding nergens `niet_letterlijk`) |
| een uitgezette connector wordt niet gebruikt | 20/20 |

| # | ronde 1 → 2 | wat er nu gebeurde |
|---|---|---|
| 1 | goed → goed | gelezen in code; de bronnenlijst noemt alleen het standpunt (was 8 bronnen, nu 1) |
| 2 | matig → **goed** | lijstroute zonder model; het blok noemt het verborgen ingetrokken standpunt, "1 in de tekst herkend" en "ten minste" |
| 3 | fout → **goed** | 30 geldend en 1 ingetrokken bij art. 3.111 Wet IB 2001, "23 van Onroerende zaken" uit `per_kennisgroep`. Klein: de zoekvraag noemt "BWBR0011353" in plaats van de naam, en een eerste aanroep met een geraden id kostte een ronde |
| 4 | fout → **goed** | art. 10 Wet BPM 1992 live van overheid.nl, daarna het standpunt als eigen blok met statusregel; 7 rondes, 225k tokens |
| 5 | goed → goed | alleen de tools van Kennisgroepstandpunten (6.106 tekens toolschema, was 25.969) |
| 6 | goed → goed | dezelfde vijf kenmerken; de toelichting herhaalt de lijst wel in lopende tekst |
| 7 | goed → goed | dezelfde vier kenmerken |
| 8 | fout → *matig* | 2 rondes en 40k tokens (was 12 rondes en 503k), totaal 93 uit de index; maar de verdeling telde twee indelingen van de site samen, en het model maakte er reeksen van ("12–13") |
| 9 | goed → goed | als ronde 1 |
| 10 | fout → **goed** | zonder model: "Het is ingetrokken door Kennisgroepstandpunt KG:013:2026:4" |
| 11 | matig → *matig* | de status juist, geen vertrouwensbeginsel meer, nog steeds geen vindplaats (B8, open) |
| 12 | goed → goed | als ronde 1 |
| 13 | fout → **fout** | "artikel 25, zeventiende lid, is gewijzigd": de tekststand geldt voor het artikel; lid 17 luidde op 5 april 2022 woordelijk als nu (`bron_lezen`, toestand 2022-01-01 tegen 2026-10-01) |
| 14 | fout → **goed** | KG:013:2026:4 en KG:013:2023:3 via `noemt`, daarna de uitspraak gelezen |
| 15 | goed → *matig* | de juiste stukken en pagina's (31 930, nr. 3 en 9), maar nr. 9 heet "nota van wijziging"; in ronde 1 zocht het model Kamerstukken op en zei terecht "nota naar aanleiding van het verslag" |
| 16 | goed → goed | als ronde 1 |
| 17 | goed → goed | melding zonder model |
| 18 | goed → goed | als ronde 1 |
| 19 | goed → goed | route `bepaling_lezen`, 1.579 + 154 tokens (ronde 1: 1.579 + 177) |
| 20 | goed → goed | geen casusadvies |

Bij vraag 9, 12, 16 en 18 zijn route, tools, sjabloon en grounding gelijk aan ronde 1; hun tekst is niet opnieuw woord voor
woord nagelezen.

## Fixes na deze ronde (zonder derde ronde)

| # | bevinding | vraag | fix |
|---|---|---|---|
| B13 | `per_belastingsoort` telde de indelingen *middel* ("Inkomstenbelasting") en *belastingsoort* ("Inkomstenbelasting (IB)") samen | 8 | twee verdelingen, `per_belastingsoort` en `per_middel`; de tool zegt ze niet samen te tellen |
| B15 | de tekststand per artikel zei niet dat hij per artikel is | 13 | `tekststanden` draagt `niveau: artikel` en de zin "of het genoemde lid anders luidt, zegt dit niet"; de toolbeschrijving zegt het lid op beide data te lezen voor een uitspraak over het lid |

Deze fixes zijn niet meer op acceptatie gemeten; ze hebben tests.

## Open

- **B8** (vraag 11): de status van een kennisgroepstandpunt zonder vindplaats. De statusregel komt uit de code, maar de
  bron heeft geen tekst in de index die de status zelf uitlegt.
- **B10**: `?search=` vindt een kenmerk met voorloopnullen in de titel niet (alleen de terugvalweg zonder index).
- **B11** (vraag 3): een regeling buiten de graaf staat in de zoekvraag als BWB-id, niet met haar naam.
- **B12** (vraag 6): de toelichting herhaalt de gevonden lijst in lopende tekst, tegen het sjabloon in.
- **B14** (vraag 15): het soort van een Kamerstuk dat een standpunt alleen citeert, leidt het model af uit de tekst in
  plaats van het op te zoeken.

## Kosten

Samen **1.000.743** tokens (invoer 1.655, uitvoer 10.911, cache lezen 777.274, cache schrijven 210.903): 21 % minder dan
ronde 1 (1.259.074), vooral door vraag 8 (503k → 41k). Vraag 4 werd duurder (0 → 227k): in ronde 1 eindigde die zonder
model bij een onbekende wetsnaam, nu leest hij wet en beleid. Drie vragen gingen zonder model: 2 (de lijstroute), 10
en 17.

## Wat deze ronde niet zegt

- Eén run per vraag; de spreiding is niet gemeten.
- De werkplek is niet in de browser bekeken.
- De fixes B13 en B15 zijn niet op acceptatie gemeten.

Voor deze ronde zijn 20 gesprekken aangemaakt. Er is niets gewijzigd of gewist.
