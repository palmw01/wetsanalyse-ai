# De centrale agent, ronde 4: de fixes R4-1 tot en met R4-5, beide vormen – 13 november 2026

- **Soort:** *meting* (ADR-016 §A6, de ronde voor A2; de derde van hoogstens vier).
- **Code:** master `43ff91a0` (bundel 94), op acceptatie voor graph-qa, api en frontend (de laatste publish-run van elk
  op die commit), `CENTRALE_AGENT=meten`. Nieuw tegen ronde 3: geldigheid geeft één rij per bepaling (R4-1),
  grondslagen voor een regeling geven ook haar artikelen (R4-2), bij een artikel zonder regeling kiest Lex niet zelf een
  regeling (R4-3), een regeling die nergens vandaan komt is een bewering (R4-4), de focus draagt wat het vorige antwoord
  noemde, in volgorde (R4-5), en de leesroute zoekt meteen bij de bepaling uit de vraag.
- **Straat:** acceptatie. **Model:** `claude-sonnet-4-6`, in elke rol.
- **Drempel:** niet duurder (naar prijs gewogen, warm; koud apart), niet slechter, brongetrouw 100 %. Volgens het besluit
  van de gebruiker wordt de 25 %-regel getoetst zonder de afwijzing (E06, K06), en staan de mediaan in drie cijfers en
  E10 apart.
- **Gegevens:** [`ronde-4-runs.jsonl`](ronde-4-runs.jsonl) (de agentset en de aanvulling, beide vormen) en
  [`ronde-4-sets.jsonl`](ronde-4-sets.jsonl) (de gesprekken en de kwaliteitsset). De vorige ronde:
  [`ronde-3.md`](../centrale-agent-2026-11-13-r3/ronde-3.md).

## Uitkomst

**De ronde is goed op kosten, en op de inhoud op twee punten na.** Voor het eerst is de centrale agent op dezelfde
versie gemeten naast de supervisor. Op de korte beurt ligt hij gelijk (behalve de afwijzing), op elke lange beurt is
hij goedkoper. De grondslagenvraag loopt niet meer uit de hand. Wat niet goed is: V01 gokt nog de regeling als de
opdracht losstaat, en bij K12 en K13 is de centrale agent slechter dan de supervisor.

| Drempel | Nulmeting → ronde 3 → nu (centraal); supervisor nu | Gehaald |
|---|---|---|
| Mediaan per opdracht, gewogen warm, alle tien (E01–E10) | 8,6k → 11,5k → **6,5k**; supervisor 4,2k | ja tegen de nulmeting; boven de supervisor door E06 |
| Idem zonder E10 (negen) | 9,6k → 10,7k → **9,9k**; supervisor 9,3k | +3 % tegen de nulmeting, +6 % tegen de supervisor |
| Idem, de vijf eigen opdrachten van de centrale agent (E03, E06–E09) | 32,3k → 27,5k → **25,1k**; supervisor 43,1k | ja |
| Geen opdracht meer dan 25 % duurder (zonder de afwijzing) | tegen de supervisor op deze versie: geen; tegen de nulmeting: E03 +43 % | ja tegen de supervisor; E03 zie hieronder |
| De afwijzing (E06, uitzondering, alleen vermeld) | 0,5k → 2,3k → 2,3k; supervisor 0,5k | – |
| Som per run, gewogen warm (E01–E10) | 233,9k / 192,0k / 280,3k → 168,9k / 191,3k / 189,3k → **164,3k / 176,8k / 185,1k**; supervisor 250,2k / 212,5k / 272,3k | ja |
| Som per run, ruw (E01–E10) | 742,1k / 529,4k / 890,6k → 476,2k / 531,6k / 552,2k → **482,1k / 548,5k / 561,8k**; supervisor 755,4k / 634,9k / 904,4k | ja |
| Koud (het uurvoorvoegsel apart) | centraal: alleen B01 run 1 (`centraal_breed`, 29,4k geschreven); supervisor: E run 1 (27,2k) en B run 1 (29,9k) | – |
| E10, apart | 7,3k → 12,4k → **3,4k**; supervisor 3,4k | ja |
| Mediaan duur (E01–E10) | 14,3 s → 11,4 s → **8,0 s**; supervisor 7,7–25,8 s | ja |
| Inhoud enkelvoudig | 30/30 → 30/30 → **30/30**; supervisor 30/30 | ja |
| B01–B04 | 9 goed, 2 deels, 1 fout → **12/12**; supervisor 12/12 | ja |
| Vervolg en V01 (één run) | ronde 3: F 2 goed, 1 deels, 2 fout → **F 4/5, V01 1/2**; supervisor F 3/5, V01 0/2 | ja, op één run |
| Gesprekken | ronde 3: 3/4 → **4/4 inhoudelijk** (scorer 5/6 runs); supervisor 4/4 inhoudelijk (scorer 4/6) | ja |
| Kwaliteitsset (22 vragen) | ronde 3 centraal 19/22 → **18/22**; supervisor 19/22. Gewogen warm 551k → 538k (supervisor 562k), mediaan 11,0k → 9,8k (supervisor 13,1k) | **nee**, K12 en K13 |
| Brongetrouw 100 % | 661 citaten in 63 antwoorden, geen verzonnen citaat; één run *ongegrond* (supervisor), ten onrechte | ja |

## Hoe er gemeten is

Zoals ronde 3, met twee verschillen: **beide vormen op dezelfde versie, om en om** (het veld `agentvorm`), en het
**meetwerkgebied** bij V01 en de vervolgopdrachten. E01–E10 en B01–B04 drie runs per vorm; V01, F01–F05, de
kwaliteitsset en drie van de vier gesprekken één run per vorm; `v-artikel-zonder-wet` drie runs per vorm. Citaten tegen
de officiële tekst (de vijf regelingen en elk genoemd stuk), de inhoud door de meetsessie gelezen tegen `goed` en `bron`.

**Afwijkingen van §A6:** de vervolgopdrachten en de sets rusten op één run; de inhoud is door de meetsessie beoordeeld.
De kwaliteitsset brak bij K17 af op het budget (429); K17–K22 zijn na een reset op dezelfde versie gedraaid, ruim twee
uur later. Hun eerste beurten waren daardoor koud.

## Enkelvoudig: E01–E10, drie runs per vorm

Gewogen warm, mediaan over drie runs (de runs staan in `ronde-4-runs.jsonl`).

| Opdracht | Wie | Nulmeting | Ronde 3 | Supervisor nu | Centraal nu | Centraal tegen supervisor | Centraal tegen nulmeting |
|---|---|---|---|---|---|---|---|
| E01 | route in code | 1,6k | 1,6k | 1,6k | 1,7k | +5 % | +3 % |
| E02 | route in code | 0 | 0 | 0 | 0 | – | – |
| E03 | centraal | 52,2k | 57,9k | 77,8k | 74,7k | −4 % | **+43 %** |
| E04 | route in code | 0 | 0 | 0 | 0 | – | – |
| E05 | route in code | 18,5k | 18,8k | 26,6k | 16,9k | −36 % | −8 % |
| E06 | centraal (afwijzing) | 0,5k | 2,3k | 0,5k | 2,3k | +345 % | +341 % |
| E07 | centraal | 9,6k | 10,7k | 9,3k | 9,9k | +6 % | +3 % |
| E08 | centraal | 111,5k | 48,0k | 75,4k | 43,3k | −43 % | −61 % |
| E09 | centraal | 32,3k | 27,5k | 43,1k | 25,1k | −42 % | −22 % |
| E10 | route in code | 7,3k | 12,4k | 3,4k | 3,4k | +1 % | −53 % |

- **E03 is in beide vormen duurder geworden** (supervisor 77,8k, centraal 74,7k, tegen 52,2k in de nulmeting en 57,9k
  in ronde 3). De centrale agent doet dezelfde drie tool-rondes als in ronde 3, maar weigert het sjabloon
  (`genoemd_onbekend`: de uitleg noemt de Faillissementswet en de Wet Vpb 1969, die niet zijn opgehaald) en zoekt daarna
  in run 2 en 3 die wetten op met `search_wetgeving` en `list_regelingen`: 8–10 modelrondes tegen 6. Dat past bij
  R4-4 (een regeling die nergens vandaan komt is een bewering). Tegen de supervisor op deze versie is het −4 %; tegen
  de nulmeting +43 %. De drempel van §A6 is tegen de nulmeting; de oorzaak zit in een fix die beide vormen raakt.
- **E10** zoekt meteen bij artikel 36 (de fix in de leesroute): één ronde, 3,4k in beide vormen. Het antwoord is
  hetzelfde als in ronde 3 ("geen annotaties gevonden"), zonder de eerste brede zoekslag die 18 annotaties van een
  andere bepaling vond.
- **Inhoud:** 30/30 per vorm. E03 centraal run 1 noemt de verwijzing naar artikel 9 als "Art. 9 leden 6 en 7 IW"; die
  staat erin.

## De brede toolset: B01–B04, drie runs per vorm

| Opdracht | Overdracht | Rondes, centraal | Gewogen warm, ronde 3 | Supervisor nu | Centraal nu | Oordeel centraal / supervisor |
|---|---|---|---|---|---|---|
| B01 geldigheid (R4-1) | ja | 4 / 4 / 5 | 40,5k / 31,2k / 53,2k | 23,5k / 21,2k / 24,9k | 11,4k / 11,4k / 16,7k | 3 goed / 3 goed |
| B02 grondslagen (R4-2) | ja | 4 / 7 / 7 | 121,2k / 52,2k / 97,2k | 30,7k / 26,2k / 26,6k | 13,6k / 25,8k / 28,0k | 3 goed / 3 goed |
| B03 verwijzingen | ja | 4 / 6 / 4 | 25,8k / 25,5k / 21,7k | 17,4k / 28,0k / 14,1k | 16,6k / 25,8k / 16,8k | 3 goed / 3 goed |
| B04 opbouw | nee | 4 / 5 / 5 | 11,5k / 20,3k / 11,7k | 47,7k / 45,9k / 49,3k | 11,8k / 15,2k / 15,1k | 3 goed / 3 goed |

- **De grondslagenvraag loopt niet meer uit de hand:** 69k–132k ruw in 4–7 rondes (ronde 3: 219k–534k, één keer de
  beurtlimiet). Het antwoord geeft de Uitvoeringsregeling Invorderingswet 1990 met haar artikelen (5, 26, 31, 35, 43,
  53), de Leidraad, de regelingen buiten de graaf als BWB-id, en de grens van de graaf.
- **Geldigheid** in één ronde minder; het antwoord noemt 1 januari 2023 (Stb. 2022-536) en de grens dat de graaf één
  toestand kent.
- **De overdracht valt waar ze moet:** B01–B03 in elke run, B04 en E01–E10 nooit. Geen tool buiten het profiel.
- **B04 bij de supervisor** kost een factor 3 meer dan centraal: hij citeert de eerste leden van elk hoofdstuk en
  weigert het sjabloon twee keer (`passage_niet_te_tonen`).

## Vervolg en V01: één run per vorm

| Opdracht | Supervisor | Centraal | Gewogen warm, supervisor / centraal | Opzet gewogen warm, supervisor / centraal |
|---|---|---|---|---|
| V01 (artikel 30 zonder regeling) | fout: gokt de Invorderingswet 1990 | fout: idem | 120,6k / 95,1k | – |
| F01 (eerste uitspraak, bewijslast) | goed | **goed** (ronde 3: fout) | 26,7k / 32,3k | 120,5k / 116,8k |
| F02 (antwoord op de keuzevraag van V01) | fout: opzet gokt, het vervolg start het samenstellen van een werkgebied | **goed** | 5,1k / 105,9k | 131,3k / 24,4k |
| F03 (stand van de deelgesprekken) | fout | fout | 4,8k / 3,4k | 47,3k / 69,6k |
| F04 (lease, bodemrecht) | goed | goed | 141,0k / 102,5k | 88,6k / 44,2k |
| F05 (de Leidraad bij artikel 24) | goed | goed | 65,1k / 55,0k | 1,8k / 1,6k |

- **V01 gokt nog, in beide vormen, als de opdracht losstaat.** Beide zoeken eerst artikel 30 in de Invorderingswet 1990
  én de AWR (centraal) en lezen dan zes tot tien uitspraken bij de Invorderingswet, met `get_uitspraak`, dat de set
  verbiedt. R4-3 grijpt hier niet in: de vraag noemt geen regeling, maar wel "de rente", en de zoekresultaten wijzen
  één regeling aan.
- **In de opzet van F02 vroeg de centrale agent het wél:** "Bedoel je artikel 30 van de AWR, artikel 30 van de
  Invorderingswet 1990, of allebei?", en het vervolg "De Invorderingswet 1990." gaf de samenvatting per uitspraak. Dezelfde
  vraag, op één run twee keer gesteld, gaf dus één keer de keuzevraag. De supervisor gokte twee keer.
- **F01 is goed in beide vormen:** het vervolg gaat over de eerste uitspraak uit het eigen overzicht
  (centraal: Rechtbank Noord-Holland, ECLI:NL:RBNHO:2026:2673; supervisor: HR 6 oktober 2023), met een letterlijke passage.
  In ronde 3 koos de centrale agent de eerste uitspraak die hij in de opzet las (R4-5).
- **F03 ongewijzigd** in beide vormen: geen bundel en geen deelgesprekken in zijn context. Werk voor A4.

## De gesprekken

| Gesprek | Vorm | Runs | Scorer | Inhoudelijk | Gewogen warm |
|---|---|---|---|---|---|
| v-artikel-zonder-wet | centraal | 3 | 2/3 | 3/3 | 10,3k / 10,5k / 6,9k |
| v-artikel-zonder-wet | supervisor | 3 | 1/3 | 3/3 | 19,1k / 41,2k / 19,2k |
| a-artikel9-doorvragen | centraal / supervisor | 1 | ja / ja | ja / ja | 29,6k / 34,1k |
| a-definitie-vervolg | centraal / supervisor | 1 | ja / ja | ja / ja | 32,3k / 67,6k |
| f-bronnen-dan-wetsvraag | centraal / supervisor | 1 | ja / ja | ja / ja | 16,0k / 15,4k |

- **`v-artikel-zonder-wet` op de supervisorweg gokt niet meer** (ronde 3: de wettekst van artikel 3:1, tweede lid, Awb
  op "En het tweede lid?"). In alle zes runs vraagt Lex bij beurt 3 welk artikel bedoeld is. De scorer keurt drie runs
  af omdat beurt 3 niet via de doorvraagroute in code ging maar via het model (`centraal`, `algemeen`), en één keer
  (supervisor run 1) omdat de vraag "Kun je het volledige artikelnummer geven?" niet de verwachte woorden bevat. Dat is
  de route, niet de inhoud.
- **De centrale agent is in elk gesprek goedkoper of gelijk**, het meest bij `a-definitie-vervolg` (32,3k tegen 67,6k).

## De kwaliteitsset

De 22 vragen één run per vorm, om en om (K17–K22 na de reset, zie *Afwijkingen*).

| | Supervisor | Centraal | Centraal, ronde 3 | Ronde 2: supervisor / centraal |
|---|---|---|---|---|
| Geslaagd | 19/22 | 18/22 | 19/22 | 18/22 / 19/22 |
| Ruw | 2,46M | 1,91M | 2,07M | 2,43M / 2,75M |
| Gewogen warm | 562k | 538k | 551k | 599k / 608k |
| Gewogen koud | 623k | 594k | 551k | 630k / 608k |
| Mediaan per vraag, gewogen warm | 13,1k | 9,8k | 11,0k | 14,9k / 12,8k |
| `meer_tools` | – | K13, K15, K17 | K13, K15, K17 | – |

- **K17–K22** zijn in beide vormen goed (K19–K21 via routes in code, zonder model).

- **K03 en K09** falen in beide vormen op dezelfde verwachting ("14 dagen"); het antwoord zegt "veertien dagen" en is
  juist. Dat is de set, niet Lex.
- **K11** faalt alleen bij de supervisor (een verwacht woord ontbreekt in een overzicht van 8k tekens).
- **K12 ("wat is bekend over het milieu in de milieuwet?"):** de centrale agent noemt geen verzonnen regeling meer
  (ronde 3: "de Belastingwet"), maar wijst de vraag af als niet over Nederlandse wet- en regelgeving, zonder te zoeken.
  De supervisor zoekt en zegt dat de graaf geen milieuregelgeving bevat, met de zeven regelingen erbij. Dat is het
  goede antwoord; de centrale agent is hier slechter.
- **K13 (verwijzingen naar artikel 36):** het antwoord van de centrale agent is goed (dezelfde bepalingen als de
  supervisor, uit `verwijst_naar_deze`), maar de bronnenlijst noemt alleen de Leidraad. De bepalingen van de
  Invorderingswet 1990 die hij noemt, staan er niet in (`source_recall` 0). Bij de supervisor staan beide regelingen in
  de lijst. Nieuw in deze ronde (ronde 3: goed).
- **K15** (grondslag van de Leidraad) kost centraal nog 82,5k in 16 rondes (ronde 3: 87,4k); de supervisor 52,0k.
- **K11** kost centraal 124,3k tegen 67,8k bij de supervisor.

## Tools per ronde en het sjabloon (E en B)

- **Centraal:** 78 rondes met tools, 28 met meer dan één, 123 aanroepen (1,6 per ronde). **Supervisor:** 115, 55, 205
  (1,8 per ronde). De centrale agent doet minder rondes: E01–E10 27 / 29 / 30 tegen 40 / 36 / 42.
- **Sjabloonweigeringen:** centraal 8 (`genoemd_onbekend` 5, bij E03; `passage_niet_te_tonen` 3); supervisor 16
  (`passage_niet_te_tonen` 11, `genoemd_onbekend` 4, `genoemd_gelezen+onbekend` 1).

## Brongetrouwheid, per run

661 citaten in 63 antwoorden (de agentset, de aanvulling, V/F en de gesprekken, beide vormen), getoetst tegen de
volledige tekst van de vijf regelingen in de graaf en elk genoemd stuk (uitspraken, Staatsblad). Zeven niet gevonden,
alle geen wettekst: één keer tekst tussen twee aanhalingen (E07), zes keer de tekst van een deelvraag
(`f-bronnen-dan-wetsvraag`). Geen verzonnen citaat, in geen enkele run.

De controle van Lex gaf één run *ongegrond*: B04 supervisor run 2, op het citaat "’s Rijks schatkist heeft een voorrecht
op alle goederen van de belastingschuldige." Dat staat letterlijk in artikel 21, eerste lid; het antwoord gebruikt een
rechte apostrof waar de wet een gekrulde heeft. Een vals alarm van de controle, dus. Verder *gegrond* 32 / 32 en
*onbepaald* 11 / 13 (supervisor / centraal), steeds na een antwoord in tekst.

## Verbruik

Uit de `meting`-events (ruw).

| Onderdeel | Supervisor | Centraal |
|---|---|---|
| E01–E10, drie runs | 2.294.710 | 1.592.362 |
| B01–B04, drie runs | 1.431.379 | 1.012.620 |
| V01 en F01–F05, één run (met opzet) | 2.635.487 | 2.106.626 |
| De gesprekken | 724.664 | 395.020 |
| De kwaliteitsset | 2.462.277 | 1.914.262 |
| **Samen** | **9.548.517** | **7.020.890** |

Samen **16.569.407** tokens, over drie budgetvensters (6,3M vóór de reset van 12:45 UTC, 10,0M tot de 429 bij K17,
0,2M voor K17–K22 na de reset van 15:29 UTC). De schatting vooraf was ~12M; de kwaliteitsset in twee vormen en de
vervolgopdrachten met hun opzet kostten meer dan geraamd.

## Waar het nu op vastzit

- **V01**: bij een artikel zonder regeling gokt Lex nog als de zoekresultaten één regeling suggereren, in beide vormen.
- **K12**: de centrale agent wijst een vraag over een regeling buiten de graaf af in plaats van te zeggen dat die er
  niet in staat.
- **K13**: de bronnenlijst van de centrale agent mist de regeling waaruit het antwoord komt.
- **E03**: een weigering van het sjabloon leidt sinds R4-4 tot extra zoekrondes naar de genoemde regelingen, in beide
  vormen.
- **De controle** keurt een citaat af op een rechte tegen een gekrulde apostrof.
- **De afwijzing** kost centraal 2,3k tegen 0,5k (uitzondering, alleen vermeld).
