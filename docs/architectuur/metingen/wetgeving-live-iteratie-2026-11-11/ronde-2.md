# Wetgeving buiten de kennisgraaf: iteratie, ronde 2 – 11 november 2026

Soort: *meting* · Code: master `80ca14f4` (bundel 43, met #1228 uit ronde 1) · Straat: acceptatie · Model:
`claude-sonnet-4-6` · Uitvoering: zoals ronde 1 ([`ronde-1.md`](ronde-1.md)): de acceptatie-MCP, elke vraag één run in een
eigen gesprek, met `bronnen: ["wetgeving_live"]`; I02, I06 en I23 met de tweede connector, I29 met de connector uit, I25 in
twee beurten.

De ruwe gegevens staan in [`ronde-2-runs.jsonl`](ronde-2-runs.jsonl). Tokens = invoer + uitvoer + cache lezen + cache
schrijven uit het `meting`-event.

## Score

**22 goed, 7 deels, 0 fout** (ronde 1: 15, 13, 2), samen **1.747.246 tokens** (ronde 1: 3.011.170). I12 telt apart: de
oplossing (#1231, de structuurtekst van het BBBB) zat in bundel 44. Op bundel 41 bleef I12 *deels* (eerlijk: dekking 0 %, met
de link, 40.240 tokens). Na de uitrol van bundel 44 (master `dc3dd7b8`) is I12 **goed**: 52 paragrafen (2 vervallen) in vijf
hoofdstukken, uit de bron, met 130.474 tokens en 79 s. Beide runs staan in de runs.

De lat ligt iets hoger dan in ronde 1. Een lijst zonder link, zoekvraag of totaal telt nu als *deels*. Daardoor zakt I01 van
*goed* naar *deels*, terwijl het antwoord zelf gelijk bleef.

| vraag | soort | oordeel (r1 → r2) | tokens (r1 → r2) | duur |
|---|---|---|---|---|
| I01 | zoeken op onderwerp | goed → **deels** | 65.957 → 89.374 | 26 s |
| I02 | combinatie Rechtspraak | deels → **deels** | 93.967 → 122.792 | 116 s |
| I03 | lezen, onvolledige bron | deels → **deels** | 81.775 → 89.460 | 26 s |
| I04 | artikel lezen | goed → **goed** | 2.870 → 2.897 | 8 s |
| I05 | BW-lid lezen | goed → **goed** | 377 → 353 | 10 s |
| I06 | combinatie Staatsblad | deels → **goed** | 185.367 → 240.750 | 67 s |
| I07 | niet bestaand | deels → **goed** | 44.073 → 0 | 1 s |
| I08 | artikel lezen | deels → **goed** | 899 → 940 | 6 s |
| I09 | onderdeel lezen | deels → **goed** | 2.904 → 330 | 4 s |
| I10 | AMvB lezen | deels → **goed** | 82.434 → 514 | 5 s |
| I11 | ministeriële regeling lezen | deels → **goed** | 84.971 → 793 | 6 s |
| I12 *(apart)* | beleidsregel opbouw | deels → **deels** | 98.591 → 40.240 | 12 s |
| I13 | opbouw | fout → **deels** | 1.035.240 → 416.889 | 184 s |
| I14 | zoeken in de tekst | goed → **goed** | 44.959 → 67.756 | 23 s |
| I15 | eerdere tekst, regeling in de graaf | goed → **goed** | 1.815 → 1.799 | 6 s |
| I16 | eerdere tekst, buiten de graaf | goed → **goed** | 686 → 676 | 4 s |
| I17 | toekomstige datum | deels → **goed** | 907 → 925 | 5 s |
| I18 | vervallen artikel | goed → **goed** | 333 → 302 | 2 s |
| I19 | nog niet in werking | goed → **goed** | 519 → 520 | 3 s |
| I20 | vervallen regeling | fout → **deels** | 509.129 → 187.022 | 58 s |
| I21 | de graaf gaat voor | goed → **goed** | 1.724 → 1.742 | 5 s |
| I22 | dubbelzinnige afkorting | goed → **goed** | 0 → 0 | 1 s |
| I23 | combinatie Kamerstukken | goed → **goed** | 0 → 0 | 1 s |
| I24 | BW-uitleg | goed → **goed** | 41.029 → 62.336 | 23 s |
| I25 | vervolgvraag | deels → **goed** | 85.579 → 6.823 | 16 s |
| I26 | opnemen buiten de graaf | goed → **goed** | 0 → 0 | 0 s |
| I27 | toevoegen buiten de graaf | goed → **goed** | 0 → 0 | 0 s |
| I28 | graaf en overheid.nl samen | deels → **deels** | 325.909 → 353.524 | 205 s |
| I29 | connector uit | goed → **goed** | 0 → 0 | 1 s |
| I30 | telling en volledigheid | deels → **deels** | 219.156 → 98.729 | 30 s |

## Wat ronde 1 oploste

- **Lezen gaat langs de workflow:** I04, I05, I08–I11, I15–I19 en I25. Elk is één modelronde van hoogstens 3k tokens.
  Leden en onderdelen staan er met hun letter; vervallen en nog niet in werking staan er als leemte.
- **Een AMvB en een ministeriële regeling** (I10, I11): voorheen ~83k tokens via het model, nu 0,5–0,8k via de workflow.
- **De vervolgvraag** (I25): "En wat staat er in artikel 32?" wordt herschreven en loopt langs de workflow. Dat kost 3,9k
  tokens, in ronde 1 was het 83k.
- **Opbouw en telling** (I13, I30): de opbouw komt nu in één aanroep, zonder 19 pagina's te bladeren. Voor I13 is dat 417k
  tokens, in ronde 1 was het 1,0M.
- **Niet bestaand, opnemen, connector uit** (I07, I26, I27, I29): een vaste melding zonder model.

## Nieuwe bevindingen en oplossingen (deze PR)

1. **Een artikelnummer met dubbele punt viel weg** (I03). "Artikel 1:1 van de Algemene douanewet" werd artikel 1: de
   herkenning haalde het boek van het BW eraf, ook bij een andere regeling. De workflow faalde daardoor en het model nam het
   over: 4 rondes en 89k tokens.
   **Oplossing:** `buiten_graaf.artikel_in_regeling`. Alleen een boek van het BW verliest het voorvoegsel; de Awb en de
   Algemene douanewet houden "1:1".
2. **De lijst onder het antwoord had geen zoekvraag, totaal of link** (I01, I14, I20, I30). De zoekvraag van de
   wetgevingstools was een zin. Het blok `stukken` verwacht de filters als dict, en zonder dict vervallen ook het totaal en de
   samenvoeging van pagina's. Bij I30 stonden zo 25 artikelen onder "174", zonder "25 van 174".
   **Oplossing:** `wetgeving_tools.zoekvraag_van` gebruikt dezelfde vorm als de andere connectors. Waar geen filter voor
   is (de regeling, het BWB-id), komt een kanttekening. Elke rij krijgt een link. De peildatum filtert nu op het veld "op de
   peildatum" en niet op "geldig vanaf", zodat de zin "peildatum 15 januari 2015" zegt in plaats van "vanaf".
3. **Twee apart gelezen leden waren één stuk** (I28). Lid 1 en lid 2 van artikel 2:9 BW hadden hetzelfde id en allebei
   nr 1. Het antwoord kon lid 2 dus niet aanwijzen, terwijl de vergelijking erop rust. Dat leverde vijf sjabloonpogingen op,
   354k tokens en 205 s.
   **Oplossing:** een gelezen lid (en een onderdeel daarin) is een eigen stuk, zoals in de graaf, met een eigen id
   (`…:artikel:9:lid:2`), label en link. `duiding.live_artikelen` kent per artikel al zijn stukken.
4. **Een eerdere tekst heette in het antwoord "tekst geldig vanaf"** (I15, I16). Dat het een eerdere tekst is, stond alleen
   in de metadata en dus niet in wat de jurist kopieert.
   **Oplossing:** `wetgeving_tools.tekst_periode` maakt van het label bijvoorbeeld "eerdere tekst, geldig van 2015-01-01
   tot en met 2015-01-31".
5. **Het overzicht van een regeling werd vier keer geweigerd** (I13). De duiding eist een gelezen passage voor elk genoemd
   artikel, ook voor het eerste en laatste artikel van een hoofdstuk uit de opbouw van de bron.
   **Oplossing:** `duiding.live_opbouw` laat een artikel dat de opbouw van zo'n regeling noemt meetellen als onderbouwd.
   Wat een artikel inhoudelijk zegt, vraagt nog steeds een gelezen passage.
6. **Een zin over de vorm van het antwoord kwam bij de jurist** (I13). Het antwoord begon met "Ik geef de uitleg daarom in
   tekst, met verwijzing naar de gelezen stukken."
   **Oplossing:** de bewaking op interne taal (B15, voor elke route) vangt nu ook zulke zinnen ("ik geef de … in tekst", "de
   code herkent ze").

## Gemeld, niet hier opgelost (gedeelde code)

- **Graafregelingen uit `search_wetgeving` in de bronnenlijst** (I03, I20). Daar staan de Awb, de AWR, de Awir en de
  Uitv.reg. Awir, terwijl alleen naar hun naam gezocht is. Dit hoort bij provenance (Rechtspraak).
- **"artikel 6:162" en "artikel 2:9" blijven onbevestigd** (I24, I28). `grounding._bekende_artikelen` leest uit de jci
  `boek=6&…&artikel=162` alleen "162", niet "6:162". Het niveau wordt daardoor *onbepaald* bij een goed gelezen artikel.
  Dit hoort bij grounding (Rechtspraak).

## Open (model, niet in code gevangen)

- **I20:** het model raadde een BWB-id uit eigen kennis (BWBR0002471, de Wet op de loonbelasting 1964) en toonde artikel 1
  van die verkeerde wet. Dat deed het hoewel `zoek_regelingen` al zei dat de regeling niet bestaat en dat het geen
  BWB-id's moet raden. Een bewaking in code zou een BWB-id weigeren dat niet in de vraag staat en in geen eerdere uitkomst
  van de beurt. Dat raakt `tool_execution` (gedeeld) en is voorgesteld voor ronde 3.
- **I06:** het juiste Staatsblad, maar in 9 rondes en 241k tokens. Het model zocht de invoering terwijl `publicatie` de
  laatste wijziging gaf.
- **I02:** de uitspraken kloppen, maar het blok met artikel 31 toont alleen de eerste pagina (18 van de 42 passages), die
  het model zelf aanwees.
