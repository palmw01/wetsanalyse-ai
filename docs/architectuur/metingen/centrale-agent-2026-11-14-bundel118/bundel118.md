# ADR-016: de vraag, het hervatten en een afgesloten kind (bundel 118, 14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, alleen D01, met akkoord van de gebruiker.

- **Code:** graph-qa op `d7bcc889` (bundel 118, #1503), `CENTRALE_AGENT=meten`. Daarin zit **#1502**:
  - een kind dat de code afsluit, krijgt de status `afgesloten`, en de beurt eindigt dan met tekst uit code;
  - na een rapport moet een duiding van een stuk rusten op een passage van dat stuk (`verify`);
  - de inhoud van het rapport staat in de meetsamenvatting.
- **Nulpunt:** D01 in de meting van #1501 op `be0acda8`
  ([`../centrale-agent-2026-11-14-bundel117/bundel117.md`](../centrale-agent-2026-11-14-bundel117/bundel117.md)): 342k.
- **Hoe gemeten:** D01 uit de aanvulling, met drie antwoorden klaar voor de kaarten `sa_vraag`: "Uitspraken uit 2022
  tot en met 2024.", "Alle instanties; verder geen beperking." en "Geen verdere beperking.". Die antwoorden stonden in
  een lokale kopie van de set en zijn niet in de repo opgenomen. Alle drie zijn gebruikt.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen: de graaf was gevuld.
- **Totaal:** 625.587 tokens op het account; plafond 1M.

## Kort

| Wat | Uitkomst |
|---|---|
| Status van het kind | **Eerst `vraag`, na het hervatten `klaar`.** Het hervatte kind is door de code afgesloten, maar krijgt toch `klaar` (`afgesloten: 0`) |
| De beurt met de vraag eindigt met alleen de kaart | **Gehaald.** "Voordat ik verder kan, heb ik een vraag voor je." Er is geen modelronde van de centrale agent |
| De vragen komen in één keer | **Gehaald.** Het rapport heeft drie vragen. Kaart 2 en 3 komen zonder modelronde (0 tokens, < 1 s) |
| Het kind gaat na het antwoord verder | **Gehaald.** `hervat: true`, hetzelfde kindgesprek. Het leest alleen uitspraken uit 2022–2023 |
| Het kind rondt af met een rapport | **Niet gehaald.** De code sloot hem af ("met wat hij las"). Het rapport is leeg: geen `gedaan`, geen `bevindingen`, geen `stukken` |
| Bij `afgesloten`: tekst uit code, zonder samenvattingen | **Niet gehaald.** De status werd `klaar`, dus #1502 greep niet in. De centrale agent schreef in 4 modelrondes een tekst per uitspraak |
| Elke duiding steunt op een passage en klopt met de uitspraak | **Deels.** HR:2023:1371 klopt en steunt op 48 letterlijke citaten. Voor de overige zes geeft het antwoord geen inhoud, maar het bevat wel twee onjuiste aanwijzingen (§*Brongetrouw*) |
| `verify` vangt een duiding zonder passage | **Half.** De enige inhoudelijke duiding zonder passage (HR:2023:181) staat als `onbevestigd`. Twee misleidende verwijzingen en de zin "verdere inhoud over de melding" ziet hij niet |
| Kosten tegen #1501 | **626k (+83 %).** Eerste kind 254k, hervat kind 249k, centrale agent 122k |

**Wat naar T1/A1 gaat:**

1. **Een hervat kind dat de code afsluit, krijgt `klaar` in plaats van `afgesloten`.** Het hervatte kind deed 6 aanroepen
   (249k ruw). Zijn laatste tekst is "De subagent rondde niet af met een rapport voor zijn laatste ronde; de code sloot
   hem af met wat hij las." In het eindevent staat `uitkomst: klaar` met een leeg rapport, en de regie meldt
   `afgesloten: 0, opgeleverd: 1`. Waarschijnlijk telt het plafond van 300k over beide delen van het kind samen
   (254k + 249k), want het hervatte deel bleef zelf onder 300k en onder 8 rondes. De nieuwe status van #1502 werkt dus
   niet op het pad van het hervatten. Daardoor schrijft de centrale agent zelf per uitspraak een tekst over een leeg
   rapport.
2. **Na het hervatten leest het kind opnieuw wat het al gelezen had.** Het eerste deel las HR:2023:1371, :563 en :176.
   Het hervatte deel begint met een context van 30k: de toolresultaten van het eerste deel zitten er niet in. Het haalt
   die drie uitspraken opnieuw op. Dat verklaart een groot deel van de +83 %.
3. **De goede bevindingen uit het eerste rapport bereiken de jurist niet.** Het eerste rapport (status `vraag`) vat vijf
   uitspraken juist samen; zie §*Brongetrouw*. Twee daarvan vallen in de gekozen periode: HR:2023:563 en HR:2023:176. In
   het eindantwoord staat bij die twee alleen "verdere inhoud over de melding staat in het niet-gelezen deel".
4. **Het eindantwoord is vooral een citaatdump.** Het heeft 48 blokcitaten, alle letterlijk. Bijna alle komen uit
   HR:2023:1371, ook kopregels als "HOGE RAAD DER NEDERLANDEN", "tegen" en "ARREST". Bij drie andere uitspraken staat
   een lege kop "Uit de rechtspraak". Eén sjabloonweigering: `extern.blokken`.
5. **De kaart stelt een overbodige derde vraag.** Na de periode en de instanties vraagt het kind naar het aspect van de
   meldingsplicht. De opdracht vroeg al wat de rechter "over de melding" zegt.

## Brongetrouw

De samenvattingen zijn vergeleken met de officiële tekst via de open data van de Rechtspraak: de inhoudsindicatie, en
of het onderwerp van de samenvatting in de tekst voorkomt. De 48 blokcitaten zijn alle letterlijk gevonden.

**Het eindantwoord.** Alle zeven uitspraken zijn van 2022 of 2023, en alle zeven las het hervatte kind op naam.

| Uitspraak | Lex zegt | De uitspraak gaat over | Oordeel |
|---|---|---|---|
| HR:2023:1371 | meldingsplicht, vermoeden bij niet melden, weerlegging alleen bij niet te wijten, art. 36 lid 4 dwingend, geen matiging | dat, r.o. 3.3, 3.5, 5.2.2, 5.4 en 3.8 | **klopt**, met passages |
| HR:2023:181 | bestuurdersaansprakelijkheid en bewijslast bij kennelijk onbehoorlijk bestuur | inhoudsindicatie: "bewijs van kennelijk onbehoorlijk bestuur" | klopt, maar zonder passage; `verify`: `onbevestigd` |
| HR:2023:176 | "Zie toelichting bij … HR:2023:181" | het Unierechtelijke verdedigingsbeginsel en het criterium van de andere afloop; "meld" komt niet voor | **misleidend**, niet gevangen |
| HR:2023:183 | "Zie toelichting bij … HR:2023:181" | hetzelfde als HR:2023:176; "meld" komt niet voor | **misleidend**, niet gevangen |
| PHR:2022:803 | geen inhoud; "verdere inhoud over de melding" in het niet-gelezen deel | civiel: bestuurdersaansprakelijkheid op grond van art. 2:248 BW | geen inhoud |
| HR:2023:563 | geen inhoud, als hierboven | aansprakelijkstelling na een schikking met de curator (art. 36.1 Leidraad) | geen inhoud |
| GHARL:2023:5865 | geen inhoud, als hierboven | bestuurdersaansprakelijkheid; "meld" komt 14 keer voor | geen inhoud |

De zin dat "verdere details over de melding" in het niet-gelezen deel staan, is voor HR:2023:181, :176 en :183 niet
waar: in die uitspraken komt het woord "melding" niet voor.

**Het eerste rapport**, dat niet bij de jurist kwam: alle vijf samenvattingen kloppen met de inhoudsindicatie.

- HR:2026:586 gaat over het una-via-beginsel bij een vergrijpboete naast een strafrechtelijke veroordeling, en het
  rapport zegt "raakt de meldingsplicht niet". Dat is juist; in #1498 en #1501 werd deze uitspraak een meldingszaak.
- HR:2023:176 gaat over het Unierechtelijke verdedigingsbeginsel.
- HR:2023:563 gaat over een schikking met de curator en de Leidraad.
- HR:2020:1502 gaat over art. 33 IW 1990 en een gewezen bestuurder van een vof.
- HR:2020:1107 gaat over art. 49 lid 6 IW 1990 en art. 8:42 Awb.

## Per beurt

| Beurt | Wat | Account | Centrale agent | Kind |
|---|---|---|---|---|
| 0 | opdracht → kaart 1 | 254.490 | 0 modelrondes | 7 aanroepen, 13 tools, 254k ruw / 88,7k gewogen warm, `vraag` (3 vragen) |
| 1 | antwoord 1 → kaart 2 | 0 | 0 | — |
| 2 | antwoord 2 → kaart 3 | 0 | 0 | — |
| 3 | antwoord 3 → hervatten, eindantwoord | 371.097 | 4 modelrondes, 0 tools, 122k ruw / 54,5k gewogen warm | 6 aanroepen, 11 tools, 249k ruw / 110,7k gewogen warm, door de code afgesloten, `klaar` |

## Open punten

- In beurt 0 staat bij de centrale agent geen enkele modelronde, en de stijging van het account is precies het kind.
  Of de delegatie hier door code werd gestart of dat een ronde van de centrale agent niet geboekt is, is uit de events
  niet te zien.
- Of het plafond van 300k over het eerste en het hervatte deel samen telt: dat volgt uit de getallen, niet uit een event.

## Bestanden

- `b118-delegatie-runs.jsonl`: D01 (één regel, `centrale_agent_vat.py`), met de status en de stukken van beide rapporten.
- `b118-kinderen.jsonl`: de twee delen van de kindrun (aanroepen, modellen, ruw, gewogen, sjabloon, tools), zonder
  tekst.
