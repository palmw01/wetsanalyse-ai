# ADR-016: samenvatten na een rapport, de vraag naar boven (bundel 116, 14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, met akkoord van de gebruiker.

- **Code:** graph-qa op `680be14d` (bundel 116, #1497), `CENTRALE_AGENT=meten`. Daarin zit **#1496**:
  - na een rapport vat de centrale agent samen;
  - de vraagvorm;
  - gelezen tegenover gevonden;
  - het plafond van een kind vooraf;
  - het eindevent `regie_taak`.
- **Nulpunt:** de meting van #1495 op `70acbeec`
  ([`../centrale-agent-2026-11-14-bundel115/bundel115.md`](../centrale-agent-2026-11-14-bundel115/bundel115.md)): boom
  S01 784k, D01 469k. Voor P01 is het nulpunt #1492
  ([`../centrale-agent-2026-11-14-bundel114/bundel114.md`](../centrale-agent-2026-11-14-bundel114/bundel114.md)), 2,34M.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen: de graaf was gevuld.
- **Wat gemeten is:** S01, D01 (met het antwoord op de eerste kaart `sa_vraag`) en P01 (met de klik op `sa_start`).
  P01 startte bij 0,70M, binnen het plafond van 2M met de vereiste 0,8M ruimte.
- **Totaal:** 1.495.012 tokens op het account.

## Kort

| Wat | Drempel | Uitkomst |
|---|---|---|
| Na `klaar` en `niet_gelukt` niet opnieuw lezen | 0 graaf- en connectoraanroepen in de ouder | **Gehaald.** S01, D01 en P01 na de klik: 0 tools in de centrale agent |
| D01: vraag naar boven of rapport met bevindingen | `sa_vraag` of bevindingen | **Gehaald: de vraag komt.** Het kind eindigt met status `vraag` en twee vragen. De eerste is de periode van het dossier |
| Niets gelezen noemen wat alleen gevonden is | | **Gehaald.** Elke ECLI en elk Kamerstuk dat een antwoord als gelezen noemt, vroeg een kind op naam op. D01 zegt dat tien gevonden stukken niet gelezen zijn |
| Geen kind ruim boven 300k | | **Gehaald.** 264k–303k |
| `kind_modellen` gevuld | | **Gehaald.** `claude-sonnet-4-6` bij alle drie |
| Eindantwoord volledig | | **S01 en P01 gehaald, D01 niet.** D01 antwoordt terwijl de vraag nog openstaat |
| Brongetrouw | geen onjuiste bron | **S01 en P01 gehaald, D01 niet.** In D01 kloppen minstens twee samenvattingen niet met de uitspraak |
| Kosten per boom | lager dan het nulpunt | **Gehaald.** S01 359k (−54 %), D01 333k (−29 %), P01 800k (−66 %) |

**Wat naar T1/A1 gaat:**

1. **D01 antwoordt al terwijl de vraag openstaat, en de samenvattingen zijn niet uit de bron.** Het kind eindigt met
   status `vraag` (regie `wacht`). In dezelfde beurt schrijft de centrale agent toch een antwoord. Hij begint met "De
   subagent las acht uitspraken …, maar rondde zijn rapport niet af." Daarna vat hij per uitspraak de "kern over de
   melding" samen, zonder zelf iets te lezen en zonder rapport met bevindingen.
   - Bij ECLI:NL:HR:2026:586 schrijft hij: "Centraal stond of tijdig en rechtsgeldig melding van betalingsonmacht was
     gedaan." Volgens de uitspraak gaat de zaak over de aansprakelijkstelling voor een vergrijpboete naast een
     strafrechtelijke veroordeling (una via). Het woord "melding" komt in de uitspraak niet voor.
   - Bij ECLI:NL:PHR:2025:1214 schrijft hij dat de A-G "de verhouding tussen de meldingsplicht en de bewijslast"
     bespreekt. Volgens de uitspraak is het een civiele zaak over faillissementsrecht en onrechtmatige selectieve
     betalingen.

   De vier blokcitaten zijn wel letterlijk (de inhoudsindicaties), en de controle in de code zegt `gegrond`: zij ziet
   samenvattingen zonder citaat niet.
2. **De tweede vraag van het kind wordt niet beantwoord.** Na het antwoord op de periode zegt Lex: "Dank je. De
   subagent heeft nog een vraag." Daarna komt de kaart over het niveau (Hoge Raad, AG, alle instanties). Het meetscript
   heeft maar één antwoord en stopt daar. Het hervatten van het kind is dus niet gemeten. Twee vragen achter elkaar,
   terwijl alleen de periode nodig was, is een extra stap voor de jurist.
3. **De code sloot het D01-kind af.** Zijn laatste tekst is "De subagent rondde niet af met een rapport voor zijn
   laatste ronde; de code sloot hem af met wat hij las." Het rapport staat als gevuld, met status `vraag`.
4. **Het P01-kind voor de Kamerstukken eindigt `niet_gelukt` met bevindingen**, en dat is terecht: "Geen van de zes
   stukken bevat passages die specifiek betrekking hebben op artikel 22." De centrale agent leest daarna niet opnieuw.
5. **Bij P01 ontbreekt het eindevent `regie_taak` van taak 0 (rechtspraak).** Het event van taak 1 is er wel. De
   kinderen in het eindevent `regie` dragen nu wel hun `modellen`, zodat `kind_modellen` gevuld is.

## Per opdracht

| Opdracht | Nulpunt boom | Ouder ruw / gewogen warm | Kind(eren) ruw / gewogen warm | Boom (account) | Kind | Antwoord |
|---|---|---|---|---|---|---|
| S01 rechtspraak bij art. 36 | 784k (#1495) | 82k / 33,1k | 276k / 106,0k | **359k** (−54 %) | `klaar`, 7 aanroepen, 16 tools | *gegrond*, 4,2k tekens, vijf uitspraken |
| D01 periode van het dossier | 469k (#1495) | 69k / 20,3k | 265k / 90,2k | **333k** (−29 %) | `vraag` (2 vragen), 7 aanroepen, 13 tools | *gegrond* volgens de code, 5,3k tekens; zie punt 1 |
| P01 art. 22, rechtspraak + Kamerstukken | 2.344k (#1492) | 199k / 79,9k | 303k / 169,3k en 297k / 92,3k | **800k** (−66 %) | `klaar` (5 aanroepen, 26 tools) en `niet_gelukt` met bevindingen (7, 18) | *gegrond*, 3,7k tekens, per bron apart |

- **S01:** de centrale agent vat het rapport samen ("op basis van de bevindingen van de subagent"). Hij behandelt vijf
  uitspraken. Bij elk staat wat de rechter zegt, ook als de melding niet het centrale punt is (HR:2023:176).
- **P01:** de plankaart kost 79k, met drie zoekaanroepen vóór het plan. Op de kaart staat het plafond ("Ze stoppen bij
  ~2.326.225 tokens samen"), maar geen schatting. Na de klik kost het 721k.

## Brongetrouw

De antwoorden zijn vergeleken met de officiële tekst: de regelingen uit de graaf (BWB-download), de 24 genoemde
uitspraken via de open data van de Rechtspraak en de 6 Kamerstukken via officielebekendmakingen.nl.

- **Citaten:** D01 heeft 4 blokcitaten, alle letterlijk. P01 heeft er één, en de enige melding is een vals alarm (tekst
  tussen twee losse aanhalingstekens). S01 heeft geen blokcitaten: het sjabloon werd geweigerd (`extern.vul`) en het
  antwoord bleef tekst.
- **Samenvattingen, als steekproef naast de inhoudsindicatie:**
  - S01: alle vijf passen (HR:2023:1371, PHR:2025:435, HR:2023:563, HR:2023:176, HR:2019:576);
  - D01: twee passen niet (zie punt 1).
- **Gelezen tegenover gevonden:** in elk antwoord vroeg een kind de genoemde stukken op naam op. De enige uitzondering
  is ECLI:NL:HR:2022:1364 in D01. Die staat binnen een letterlijk geciteerde inhoudsindicatie ("vervolg op …"), niet
  als gelezen stuk.

## Open punten

- Het hervatten na `sa_vraag` (de tweede vraag van D01) is niet gemeten.
- Waarom de centrale agent bij een kind met status `vraag` (regie `wacht`) toch een inhoudelijk antwoord geeft.

## Bestanden

- `b116-runs.jsonl`: S01 (één regel, `centrale_agent_vat.py`).
- `b116-delegatie-runs.jsonl`: D01 en P01 uit `golden_centrale_agent_delegatie.jsonl`.
- `b116-kinderen.jsonl`: de vier kindruns (aanroepen, modellen, ruw, gewogen, sjabloon, tools), zonder tekst.
