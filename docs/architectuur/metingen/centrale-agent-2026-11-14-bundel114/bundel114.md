# ADR-016: delegeren in code, het rapport en het lichte model (bundel 114, 14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`.

- **Code:** graph-qa op `2f796347` (bundel 114, #1489, en #1490), `CENTRALE_AGENT=meten`. Daarin zitten:
  - **#1484:** een kleiner voorvoegsel, en een subagent die vraagt naar een ontbrekende afbakening;
  - **#1485:** delegeren in code waar de vorm vastligt (M03, S01, D01; V01 blijft bij de centrale agent);
  - **#1487:** het rapport valt niet meer om, en een subagent heeft een rondegrens van 8;
  - **#1488 en #1490:** de subagent op de lichte modelklasse (`LLM_MODEL_LICHT=claude-haiku-4-5` op acceptatie).
- **Nulpunt:** de hermeting van #1486 op `b6a70016`
  ([`../centrale-agent-2026-11-14-a3a5-her/her.md`](../centrale-agent-2026-11-14-a3a5-her/her.md)). Voor wat daar
  niet in zat (M03, D02, E06–E08) is het nulpunt de meting van #1482
  ([`../centrale-agent-2026-11-14-a3a5/a3a5.md`](../centrale-agent-2026-11-14-a3a5/a3a5.md)).
- **Vooraf:** de deploy herstartte GraphDB. Een overzichtsvraag zonder model ("Welke artikelen … gaan over de
  aanmaning?") gaf binnen 3 s zes artikelen: de graaf was gevuld.
- **Wat gemeten is:** S01, M03, V01, D01, S03, S05, D02, E03, E06–E09 en P01 (met de klik op `sa_start`). P03 is
  niet gemeten: zie *Plafond*.
- **Plafond: overschreden.** Het plafond was 4M op het account. Vóór P01 stond het op 2,72M; P01 kostte in één beurt
  2,34M, en het account eindigde op **5,06M**. Een peiler op het verbruik (elke 15 s, grens 3,85M) greep niet in: het
  verbruik van een run wordt pas aan zijn eind geboekt, en de boom van P01 eindigde in één keer. Daarna is gestopt en
  gemeld. Les: een delegatie met klik start alleen bij ruim 2,5M ruimte.

## Kort

| Wat | Drempel | Uitkomst |
|---|---|---|
| #1485 M03 in code | regiebevestiging, 0 tokens | **Gehaald.** Bevestiging `regie:bronnen`, 0 tokens (was 584k) |
| #1485 V01 blijft centraal | vraagt welke regeling, geen `get_uitspraak` | **Gehaald.** 70k |
| #1485 S01, D01 in code naar een subagent | één kind, de centrale agent vat het rapport samen | **Half.** Het kind start in code, maar levert geen rapport; de centrale agent doet het werk over |
| #1487 rapport `klaar`, hoogstens 8 aanroepen | S03 en D01 | **Niet gehaald.** Elk kind (4 van 4) haalt de grens van 8 zonder rapport: `niet_gelukt`. S03 delegeert niet meer |
| #1484 vraag naar een ontbrekende afbakening | D01, D02 vragen | **Niet gehaald.** Geen kaart `sa_vraag`; D01 kiest zelf, D02 behandelt alle acht gronden |
| #1484 kleiner voorvoegsel | eerste aanroep kleiner | **Gehaald, klein.** 17,2k → 16,1k zonder connector (−6 %), 22,1k → 21,1–21,8k met |
| A5 P01 met klik | twee rapporten en een bundel | **Niet gehaald.** Twee kinderen `niet_gelukt`, de centrale agent leest alles opnieuw en eindigt met één zin. 2,34M |
| Het lichte model | kind op `claude-haiku-4-5` | **Niet gehaald.** Elke kindaanroep draait op `claude-sonnet-4-6` (terugval) |
| Brongetrouw | geen onjuiste bron of verzonnen citaat | **Gehaald.** 124 citaten, 123 letterlijk; het ene restant is een vals alarm |
| Kosten | niet duurder dan #1486 | **Niet gehaald voor een delegatie.** Zie §*Kosten per boom* |

**Wat naar T1/A1 gaat:**

1. **`kind_modellen` toont de keuze, niet het model dat draaide.** Bij S01 zegt `regie_taak` `claude-haiku-4-5`, maar
   alle 8 aanroepen in de meting van het kind zijn `claude-sonnet-4-6`. Dat past bij de terugval in `Subagent.ronde`
   (een 400 of 404 op het lichte model, waarna `_LICHT_KAPOT` de rest van het proces op het gewone model zet). Vanaf D01
   kiest `regie_taak` zelf al Sonnet. **De mislukte Haiku-aanroep ontbreekt in `aanroepen`.** De logregel
   `subagent_model_terugval` is niet nagelezen (geen toegang tot de logs vanuit deze meting). Het lichte model is dus
   niet gemeten.
2. **Het kind loopt tegen de rondegrens aan zonder rapport, en de centrale agent doet het werk over.** Bij S01 haalt het
   kind (16 tools, 8 aanroepen) de grens met "sjabloon gemist" en eindigt `niet_gelukt`. Daarna leest de centrale agent
   zelf 19 uitspraken in 10 aanroepen. De hele boom kost **857k** op het account. D01 (724k) en P01 (2,34M) tonen
   hetzelfde. De laatste tekst van het kind is telkens een aankondiging ("Laat me nog … ophalen"): het kind wil
   doorlezen als de grens hem stopt.
3. **P01 eindigt zonder antwoord.** Na 21 rondes en 30 tools (12× `get_kamerstuk`, 11× `get_uitspraak`, 7×
   `zoek_kamerstukken`) en twee weigeringen van het duidingssjabloon (`extern.blokken`) krijgt de jurist één zin: "Ik
   haal de relevante stukken op uit de trace …". De laatste aanroep leest uit de cache alleen het voorvoegsel (21.971 tokens);
   het gesprek ervoor lijkt hij niet te hebben.
4. **De vraag naar boven komt niet.** D01 kiest zelf en D02 vraagt niet naar de situatie van de cliënt. Bij D01 gaat
   de vraag in code meteen naar een kind, dat ook niet vraagt.
5. **Het verbruik wordt pas aan het eind van een run geboekt.** Een plafond tijdens een boom bewaken lukt daardoor niet
   van buitenaf. Het plafond in de kaart `sa_start` is de enige rem.

## Per opdracht

### #1485: delegeren in code

| Opdracht | #1486 / #1482 | Nu | Gewogen warm (ouder) | Ruw (account) | Oordeel |
|---|---|---|---|---|---|
| M03 bronnen voor alle deelvragen | zelf, 584k (#1482) | regiebevestiging `regie:bronnen`, 3 deelgesprekken | 0 | 0 | gehaald |
| V01 art. 30 zonder regeling | – | vraagt: AWR, Iw 1990 of Awir? | 15,8k | 70k | gehaald; geen `get_uitspraak` |
| S01 rechtspraak bij art. 36 | zelf, 659k | kind *algemeen* `niet_gelukt`, dan zelf 19× `get_uitspraak` | 164,8k | 857k | *gegrond*; dubbel werk |
| D01 periode van het dossier | kind, 1.354k | kind *algemeen* `niet_gelukt`, dan zelf 21× `get_uitspraak` | 127,5k | 724k | *gegrond*; geen vraag |

- **M03:** na de bevestiging zoekt de regie de bronnen zonder model en zet ze als voorstel in het paneel (8 per
  deelvraag) van het meetwerkgebied. Het script bevestigt alleen de bronnenronde, nooit het annoteren.
- **V01:** de centrale agent noemt drie kandidaten met een artikel 30 en vraagt welke bedoeld is.

### #1487: het rapport en de rondegrens

| Kind | Aanroepen | Tools | Ruw | Gewogen warm | Sjabloon | Uitkomst |
|---|---|---|---|---|---|---|
| S01 (*algemeen*) | 8 | 16 | 317,6k | 93,1k | gemist | `niet_gelukt` |
| D01 (*algemeen*) | 8 | 14 | 304,0k | 85,0k | gemist | `niet_gelukt` |
| P01 rechtspraak (*duiding*) | 8 | 27 | 452,1k | 134,3k | gemist | `niet_gelukt` |
| P01 Kamerstukken (*duiding*) | 8 | 14 | 270,7k | 74,9k | gemist | `niet_gelukt` |

- **De grens werkt:** geen kind komt boven de 8 aanroepen (in #1486 liep het kind van D01 door tot 801k).
- **Het rapport niet:** geen kind vult het. Er komt geen weigering met `passage_niet_te_tonen` of `extern.blokken` uit
  het kind: het rapport wordt niet eens geprobeerd.
- **S03 delegeert niet meer** (in #1486 wel). Hij antwoordt zelf voor 153k ruw en 62,8k gewogen warm, tegen een boom van
  279k. Het duidingssjabloon wordt twee keer geweigerd (`passage_niet_te_tonen`) en blijft leeg; het antwoord is
  *onbepaald*.

### #1484: de vraag naar boven en het voorvoegsel

| Opdracht | Nulpunt | Nu | Gewogen warm | Ruw | Oordeel |
|---|---|---|---|---|---|
| D01 | kind kiest "de meest recente" | kind start in code, geen vraag | 127,5k | 724k | niet gehaald |
| D02 Leidraad bij art. 10 | zelf, 108k (#1482) | zelf, alle acht gronden, geen vraag | 75,2k | 142k | niet gehaald; sjabloon gemist (2× `passage_niet_te_tonen`) |
| S05 Staatsblad bij art. 36 | zelf, 272k | zelf, 4× `get_bekendmaking`, `antwoord_duiding` | 37,8k | 179k | *gegrond*; −34 % ruw |

Het voorvoegsel (de eerste aanroep, cache lezen plus schrijven plus invoer):

| | #1486 | Nu |
|---|---|---|
| zonder connector (S03, E03, E09) | 17.149–17.181 | 16.097–16.143 |
| met connector (S01, S05) | 22.116–22.135 | 21.079–21.845 |

### A5: P01 met de klik

- **Plankaart (117k ruw):** twee subagents met profiel *duiding*, "Lees de elf uitspraken van de Hoge Raad bij artikel
  22 …" en "Lees de kernstukken uit de parlementaire geschiedenis van artikel 22 …".
- **Na de klik (2.227k op het account):** beide kinderen `niet_gelukt` (723k samen), daarna de centrale agent in 21
  aanroepen voor 1.505k ruw. Het antwoord is één zin zonder bron (`cited: 0`).

### Kosten van de rest (zelf antwoorden)

| Opdracht | Nulpunt gewogen warm | Nu | Verschil |
|---|---|---|---|
| E03 | 77,7k (#1486) | 83,9k | +8 % |
| E06 (afgewezen) | 2,8k (#1482) | 2,7k | −3 % |
| E07 | 11,8k (#1482) | 12,1k | +3 % |
| E08 | 45,9k (#1482) | 43,7k | −5 % |
| E09 | 64,8k (#1486) | 30,3k | −53 % |

E03, E06, E07 en E08 liggen binnen de spreiding van één run. E09 leest minder (8 tools, 5 rondes); het antwoord is
*gegrond*. Geen E-opdracht delegeert.

## Kosten per boom

| Opdracht | #1486 boom (ruw) | Nu ouder ruw / warm | Nu kind(eren) ruw / warm | Nu boom (account) |
|---|---|---|---|---|
| S01 | 659k (zelf) | 540k / 164,8k | 318k / 93,1k | **857k** (+30 %) |
| D01 | 1.354k | 420k / 127,5k | 304k / 85,0k | **724k** (−47 %) |
| S03 | 279k | 153k / 62,8k | – | **153k** (−45 %, geen delegatie) |
| P01 | 82k (alleen plan) | 1.621k / 393,6k | 723k / 209,3k | **2.344k** |

De rondegrens maakt het kind goedkoper (D01: 801k → 304k), maar zonder rapport doet de centrale agent het werk
opnieuw. Een delegatie kost dan meer dan zelf doen.

## Brongetrouw

Elk citaat in de antwoorden is vergeleken met de officiële tekst: de vier regelingen uit de graaf
(BWB-download), de uitspraken via de open data van de Rechtspraak (de 19 genoemde ECLI's) en het Staatsblad (2 stukken).

- 124 citaten in S01, S05, E03, E07, E08, E09, D01 en D02: **123 letterlijk**.
- Het restant (S01) is een vals alarm: tekst tussen twee losse aanhalingstekens ("lichtpuntjes" … "aannemelijk
  maken"), geen citaat.
- D01 noemt `ECLI:NL:GHDA:2013:BZ2869` binnen een letterlijk geciteerde passage uit een uitspraak. De Rechtspraak kent
  die ECLI niet (404): het is de verwijzing van de rechter zelf, niet van Lex.
- P01 citeert niets.

## Open punten

- Het lichte model meten zodra de deployment er is (de hoofdsessie meet het nu niet).
- P03 (A5 zonder connector, met klik) is niet gemeten.
- Waarom het kind het rapport niet probeert voor de rondegrens; en waarom de laatste aanroep van P01 zonder het gesprek
  draait.

## Bestanden

- `b114-runs.jsonl`: de tien opdrachten uit de set van 30 (één regel per opdracht, `centrale_agent_vat.py`).
- `b114-delegatie-runs.jsonl`: D01, D02 en P01 uit de aanvulling `golden_centrale_agent_delegatie.jsonl`.
- `b114-kinderen.jsonl`: de vier kindruns (aanroepen, modellen, ruw, gewogen, sjabloon, tools), zonder tekst.
