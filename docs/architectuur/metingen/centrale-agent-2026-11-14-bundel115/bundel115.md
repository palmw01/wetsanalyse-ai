# ADR-016: de delegatie sluit af in code (bundel 115, 14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, met akkoord van de gebruiker.

- **Code:** graph-qa op `70acbeec` (bundel 115, #1494), `CENTRALE_AGENT=meten`. Daarin zit **#1493**: de delegatie
  sluit af in code. Bij de rondegrens of het tokenplafond van een subagent (300k ruw) is de volgende ronde de laatste
  en moet het kind een rapport geven. Na een kind dat niet afrondde, krijgt de centrale agent bij een lees-tool
  `na_subagent` terug.
- **Nulpunt:** de meting van #1492 op `2f796347`
  ([`../centrale-agent-2026-11-14-bundel114/bundel114.md`](../centrale-agent-2026-11-14-bundel114/bundel114.md)): boom
  S01 857k, D01 724k, P01 2,34M.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen: de graaf was gevuld (3k tokens).
- **Wat gemeten is:** S01 en D01. **P01 is niet gestart.** Het plafond was 1,5M, en volgens de eigen regel uit #1492
  start P01 met de klik alleen bij minstens ~0,8M ruimte. Na D01 stond het account op 1,26M; er was 0,24M ruimte.
- **Totaal:** 1.255.541 tokens op het account (graafcontrole, S01 en D01).

## Kort

| Wat | Drempel | Uitkomst |
|---|---|---|
| Het kind rondt af met een rapport | `klaar` of `niet_gelukt` met bevindingen | **Half.** S01: rapport `klaar`. D01: het rapport wordt geweigerd (`rapport_vragen`) en het kind eindigt `niet_gelukt` zonder bevindingen |
| Binnen 8 rondes en 300k | per kind | **Niet gehaald.** Beide kinderen 9 aanroepen, 408k en 369k ruw: de grens geeft nog één ronde na het plafond |
| Na `niet_gelukt` niet zelf opnieuw lezen | geen graaf- of connectoraanroep | **Gehaald (D01).** 0 tools in de centrale agent. Er kwam geen `na_subagent`: hij probeerde geen lees-tool |
| Het eindantwoord is volledig | niet één zin | **S01 gehaald, D01 niet.** S01: 26,9k tekens, *gegrond*. D01: de jurist krijgt te horen dat het rapport niet beschikbaar is, plus een lijst |
| Geen sjabloonweigering die het antwoord leeg laat | `passage_niet_te_tonen`, `extern.blokken` | **Gehaald.** Geen van beide. D01 heeft één weigering op `extern.lijsten`, en het sjabloon is daarna toch gevuld |
| Kosten per boom | lager dan #1492 | **Gehaald.** S01 784k (−9 %), D01 469k (−35 %) |
| Brongetrouw | geen onjuiste bron of verzonnen citaat | **S01 gehaald, D01 deels.** S01: 48 van 48 citaten letterlijk. D01: geen citaten, maar de lijst "die de subagent las" bevat 7 uitspraken die het kind niet opvroeg |

**Wat naar T1/A1 gaat:**

1. **Na een rapport `klaar` leest de centrale agent toch alles zelf opnieuw (S01).** Het kind leverde een rapport
   (`opgeleverd: 1`), en daarna deed de centrale agent 17 toolaanroepen (13× `get_uitspraak`, 3× `zoek_uitspraken`,
   `list_regelingen`) in 9 aanroepen voor 376k ruw. `na_subagent` geldt alleen na een kind dat niet afrondde. Het
   antwoord citeert uit wat de centrale agent zelf las. De boom kost daardoor nog 784k, waarvan 408k in het kind.
2. **Het D01-kind wil een vraag stellen, en de toets weigert het rapport.** Het rapport wordt één keer geweigerd op
   `rapport._toets_vragen` (`rapport_vragen`), daarna is het sjabloon gemist en eindigt het kind `niet_gelukt`. Welke
   regel van de toets brak, staat niet in de events: de invoer van het sjabloon wordt niet bewaard. Waarschijnlijk is
   het een vraag bij een status die geen `vraag` is, of een vraag zonder vraagteken. Zo komt de vraag naar boven
   (#1484) er nog steeds niet door, terwijl het kind hem wel wilde stellen.
3. **Het tokenplafond van 300k is een trigger, geen grens.** Bij 300k volgt nog één ronde. De kinderen eindigen op 408k
   (S01) en 369k (D01), elk met 9 aanroepen.
4. **Het D01-antwoord is eerlijk, maar geen antwoord.** De centrale agent leest niet opnieuw (goed), en zegt: "De
   subagent bereikte zijn rondegrens voordat hij kon afronden. Zijn rapport is daardoor niet beschikbaar." Hij biedt
   drie vervolgstappen en een lijst van 16 uitspraken. In de tekst heet die lijst "de uitspraken die de subagent las".
   Volgens de toolaanroepen van het kind vroeg dat er 9 op naam op; 7 in de lijst vond hij alleen in de zoekresultaten.
   Het blok heet wel "Gevonden Rechtspraak".
5. **Bij S01 ontbreekt `regie_taak` met `fase: eind`.** De regie eindigt (`klaar`, `opgeleverd: 1`), maar het
   eindevent van de taak komt niet in de stroom van de ouder. `kind_modellen` is daardoor leeg; het kind draaide op
   `claude-sonnet-4-6` (de aanroepen in zijn meting, en `gekozen_model` in het startevent).

## Per opdracht

| Opdracht | #1492 boom | Ouder ruw / gewogen warm | Kind ruw / gewogen warm | Boom (account) | Kind | Antwoord |
|---|---|---|---|---|---|---|
| S01 rechtspraak bij art. 36 | 857k | 376k / 111,9k | 408k / 160,1k | **784k** (−9 %) | `klaar`, rapport gevuld, 9 aanroepen, 16 tools | *gegrond*, 26,9k tekens, `antwoord_extern` |
| D01 periode van het dossier | 724k | 99k / 32,5k | 369k / 125,9k | **469k** (−35 %) | `niet_gelukt`, rapport geweigerd (`rapport_vragen`), 9 aanroepen, 13 tools | *onbepaald*, 4,2k tekens, geen citaat |

- **S01:** het antwoord bespreekt vier arresten van de Hoge Raad in detail (en noemt er meer) en noemt zijn eigen beperking ("Van de 75 Hoge
  Raad-uitspraken bij artikel 36 zijn er hier slechts vier in detail gelezen") onder *Twijfel en aannames*.
- **D01:** geen kaart `sa_vraag`, geen vraag naar de periode. De centrale agent doet in vier aanroepen geen enkele
  toolaanroep.

## Brongetrouw

De citaten zijn vergeleken met de officiële tekst: de regelingen uit de graaf (BWB-download) en de 25 genoemde
uitspraken via de open data van de Rechtspraak.

- **S01:** 48 citaten, **48 letterlijk**.
- **D01:** geen citaten. Alle 16 uitspraken in de lijst bestaan. 9 daarvan vroeg het kind op naam op met
  `get_uitspraak`; 7 komen alleen uit de zoekresultaten. Het kind deed 11 keer `get_uitspraak`, en bij 2 aanroepen
  staat geen ECLI in het startevent, dus het aantal gelezen stukken kan 9 tot 11 zijn.

## Open punten

- P01 en het plan met twee kinderen zijn niet gemeten (geen ruimte binnen 1,5M).
- Waarom de toets het rapport van D01 weigert: zonder de invoer van het sjabloon is dat niet na te gaan.

## Bestanden

- `b115-runs.jsonl`: S01 (één regel, `centrale_agent_vat.py`).
- `b115-delegatie-runs.jsonl`: D01 uit `golden_centrale_agent_delegatie.jsonl`.
- `b115-kinderen.jsonl`: de twee kindruns (aanroepen, modellen, ruw, gewogen, sjabloon, tools), zonder tekst.
