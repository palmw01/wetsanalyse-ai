# ADR-016: meting na het plan centrale agent na A6 (bundel 142 en 143, 16 nov 2026)

Soort: *meting*, licht regime: één run, alleen de opdrachten die PR A, PR C en de agentprofielen raken, plafond 2,5M. De
gebruiker gaf akkoord met "2,5M" ([plan](../../plan-centrale-agent-na-a6.md), *Meten*; plan agentprofielen, *Meting*).

## Opzet

- **Code:** graph-qa op `7f9d4f47` (bundel 143, #1608; daarvoor bundel 142, #1606). Daarin zitten PR D, A, C, B en E
  uit het plan, en de agentprofielen 1–5 (#1565). Het model is `claude-sonnet-4-6`.
- **Werkgebied:** een nieuw meetwerkgebied uit de eerste regel van de set. Dat van A6 bestaat niet meer.
- **Gedraaid:** één opdracht tegelijk, in deze volgorde: S01, S04, V03, F02 en P01.
  - P01 staat in `golden_centrale_agent_delegatie.jsonl` en draaide daarom met `--set`.
- **Niet gedraaid:**
  - M06 en F01, omdat ze niet meer binnen het plafond pasten. Mijn schatting voor alle zeven was 3,3M.
  - F01 bouwt bovendien op het overzicht van S01, en dat kwam er niet (zie *De vraag naar boven*).
- **Bewaking:**
  - Een wachter peilde elke 20 s het verbruik van het account en zou alles boven 2,45M stoppen. Hij hoefde niet in te
    grijpen.
  - Een opdracht startte alleen als het verbruik tot dan, plus haar schatting, onder 2,45M bleef.
- **Vervolg:** S01 en F02 eindigden met een vraag naar boven. Die vraag heb ik in hetzelfde gesprek beantwoord met
  *Nee, rond af met wat er is*, om het eindantwoord te kunnen meten (zie *Na het antwoord*). Dat staat apart in
  `vervolg-runs.jsonl`.
- **Totaal:** ongeveer 1,89M tokens (verschil in het verbruik van het account; de teller telt cache-lezen ×1). Er kwam
  geen `BUDGET_OP`.

## Uitkomst

| Opdracht | Profiel van het kind | Kind: uitkomst, rondes, ruw | Account | Eindantwoord | Vorige meting |
|---|---|---|---|---|---|
| S01 | `rechtspraak_lezen` | `klaar` → vraag, 8, 310k | 310k | **geen:** vraag naar boven | fout (slot, 332k) |
| S04 | `bepalingen_duiden` | `klaar`, 7, 138k | 162k | **goed** | deels (run 3, 229k) |
| V03 | `wetsgeschiedenis_lezen` | `niet_gelukt` → vraag, 10, 233k | 233k | **geen:** vraag naar boven | goed (na A6, 319k) |
| F02 | `rechtspraak_lezen` | `klaar` → vraag, 8, 280k | 280k | **geen:** vraag naar boven | goed (slot, 425k) |
| P01 | `wetsgeschiedenis_lezen` + `rechtspraak_lezen` | beide `klaar` → vraag; 10 en 7, 250k en 270k | 520k | **geen:** vraag naar boven | deels (run 3, 561k) |
| S01, vervolg | idem, hervat | rapport | ~195k | **fout:** de beurt past niet in het venster | – |
| F02, vervolg | idem, hervat | rapport | 185k | **fout:** de beurt past niet in het venster | – |

- **S04 (goed).**
  - Per onderdeel 22.1–22.9 van de Leidraad een kern, en de ongelezen subonderdelen precies genoemd: 22.8.10 tot en met
    22.8.12.
  - Twee feiten uit het antwoord heb ik tegen de tekst in de graaf getoetst: de acht dagen bij de overbetekening (22.3)
    en de tien dagen bij een onduidelijk bezwaarschrift (22.8.8). Beide kloppen.
  - Het antwoord kwam als tekst en niet in een sjabloon (telling `gemist`).
- **S01, V03, F02 en P01:** zie de volgende twee delen.

## De vraag naar boven (PR C) houdt het antwoord tegen

Alle vijf de kinderen van S01, V03, F02 en P01 stopten op hun grens:
- vier op de rondegrens (8 voor rechtspraak, 10 voor wetsgeschiedenis);
- het rechtspraakkind van P01 op het tokenplafond, na 7 rondes en 270k.

In de laatste ronde schreef elk kind zijn rapport, dus `laatste_gehad` stond overal aan. Elk had ook iets onder 'Open',
of gevonden stukken die het niet las. `begrensd_vraag` maakte daar in alle vijf de gevallen een vraag van, ook bij vier
kinderen met de status `klaar`. Daardoor:

- **schreef de centrale agent geen eindantwoord**: de beurt eindigt met de vraagkaart (`VRAAG_VAN_SUBAGENT`). F02 was in
  de slotmeting nog goed;
- **zegt de vraag vaak niet wat er open is:** bij S01, F02 en P01 (rechtspraak) staat er alleen "Ik kwam aan de grens
  van wat ik in één keer mag lezen voor ik klaar was. Zal ik verder lezen?". De tekst over 'Open' was langer dan 300
  tekens, en dan valt de toelichting weg. Bij V03 en P01 (wetsgeschiedenis) noemt de vraag de ongelezen Kamerstukken
  wel;
- **is de regel te ruim:** 'Open' bevat ook twijfel en aannames ("de uitkomst van die procedure is niet opgehaald"), en
  de laatste ronde is bijna altijd de ronde van het rapport.

## Na het antwoord: de bundel past niet in het venster

Bij S01 en F02 heb ik de vraag beantwoord met *Nee, rond af met wat er is*:
- Het kind werd hervat en gaf zijn rapport.
- Daarna faalde de eerste modelaanroep van de centrale agent, bij allebei, met een `BadRequestError`.
- De melding was "Deze beurt paste niet binnen de grenzen van het model – meestal is het gesprek te lang geworden".
- De meting telt 0 invoertokens en 0 modelrondes. De uitkomst is `mislukt`.

`agent._provider_fout` geeft die melding alleen als de provider een te lange vraag meldt ("too long", "exceed", …).
Een te groot schema heet anders. De vraag aan het model was dus groter dan het venster. Na het hervatten draagt de
beurt de historie van het gesprek, het eerste en het tweede rapport, de toolresultaten van het kind (in de
`source_trace`) en de steun. De logregel `model_aanroep` met de opbouw van die vraag heb ik niet kunnen lezen: Grafana en
App Insights zijn vanuit deze sessie niet bereikbaar. De run-id's staan hieronder, zodat het achteraf kan.

- S01, vervolg: ouder `12b5f5b0d64b44cd99b65045a091566b`, kind `77dd0b0fec3647f2a998539d3d317af6`;
- F02, vervolg: zie `vervolg-runs.jsonl` en `kinderen.jsonl` (beurt `gemeten:vervolg1:sa_vraag`).

Dit pad bestond al vóór PR C (`ongelezen_vraag`, A6 eind), maar werd zelden genomen. Met PR C loopt elke delegatie erlangs.

## Drempels

Uit het plan agentprofielen (*Meting*) en het plan centrale agent na A6 (PR A en C), voor zover gedraaid:

| Drempel | Uitkomst |
|---|---|
| **Profielkeuze**: in elke opdracht het verwachte taakprofiel | **gehaald**, 5 van 5 (6 kinderen) |
| **V03**: minstens één MvT gelezen en samengevat met een letterlijke passage | **niet gehaald**: het kind las kst-35305-3 en kst-36418-3, maar er kwam geen eindantwoord |
| **S04**: alle onderdelen gelezen of de ongelezen nummers precies genoemd, binnen het budget | **gehaald**: 22.8.10–22.8.12 genoemd, kind 138k van 260k |
| **Grenzen**: geen kind boven zijn budget plus één ronde, en geen `afgesloten` zonder rapport | **gehaald**: hoogste 310k bij een budget van 300k; elk kind gaf een rapport |
| **Brongetrouw**: geen onjuiste bron en geen verzonnen citaat | **gehaald voor wat er staat**: één eindantwoord (S04), steekproef 2 van 2 juist. Te weinig om meer te zeggen |
| **Verbruik**: per opdracht hoogstens de vorige meting plus 10 % | **gehaald voor de eerste beurt** (S01 310k tegen 332k, S04 162k tegen 229k, V03 233k tegen 319k, F02 280k tegen 425k, P01 520k tegen 561k); met het vervolg erbij niet |
| **Leesweg**: rechtspraak via het artikel, wetsgeschiedenis vanaf `geldigheid`, meer dan één stuk per ronde | **gehaald**: `zoek_uitspraken` vroeg, `geldigheid` als eerste stap na het zoeken, 1,8–4,6 aanroepen per ronde |
| **Inhoud**: geen opdracht van goed naar fout zonder verklaring | **niet gehaald**: F02 en V03 waren goed en geven nu geen antwoord; de verklaring staat hierboven |
| **PR A**: S01 en P01 per stuk een kern, `tekst_ernaast` 0 of klein, minstens de helft van de citaten draagt de kern | **niet gemeten**: geen eindantwoord met `antwoord_extern` |
| **PR C**: een kind op zijn grens met iets open, vraagt het | **gehaald, maar te ruim**: 5 van 5, ook bij `klaar`; de vraag houdt het antwoord tegen, en na het antwoord past de bundel niet (2 van 2) |

## Voorstel (geen nieuwe ronde, besluit gebruiker 15 nov 2026)

1. **De vraag van C houdt het antwoord niet tegen** (generiek, in `subagent.begrensd_vraag` en `finalize_node`):
   - Bij een kind met een rapport `klaar` schrijft de centrale agent het antwoord uit dat rapport.
   - De vraag "Zal ik verder lezen?" komt er daarna bij, als kaart onder het antwoord, met wat er niet gelezen is. Dat
     is nu een eindstation.
   - Alleen zonder bruikbaar rapport (`niet_gelukt`, `afgesloten`, of niets gelezen van de gevraagde bron, zoals
     `ongelezen_vraag`) blijft de vraag een poort.
   - 'Open' telt niet meer als reden; alleen gevonden maar ongelezen stukken en stukken die deels gelezen zijn.
   - De vraag noemt die altijd, ook ingekort.
2. **Een hervatte bundel past in het venster** (generiek, in de beurt na `subagent.hervat`):
   - Eerst de opbouw van de twee mislukte vragen lezen in de logregel `model_aanroep` (de run-id's hierboven).
   - Daarna begrenzen wat de hervatte bundel meedraagt: alleen het laatste rapport, en de toolresultaten van het kind
     niet twee keer.
   - Het moet een test krijgen die een hervatting door de hele graaf laat lopen met een rapport van de omvang van S01
     (40k tekens), met de vraag onder het venster.
3. **Daarna één lichte meting**, met akkoord: S01, F02 en P01 (de geraakte vorm), met een plafond van ongeveer 1,2M. Dan
   is ook PR A te meten.

## Bestanden

- `runs.jsonl`: de vijf opdrachten (`centrale_agent_vat.py`), zonder tekst. `tokens` en `gewogen` komen uit het
  `meting`-event van de laatste beurt. Die is 0 als de beurt met een vraagkaart eindigde; `delta_account` is het
  verbruik.
- `vervolg-runs.jsonl`: S01 en F02 met de beurt waarin de vraag beantwoord is (`gemeten:vervolg1:sa_vraag`).
- `kinderen.jsonl`: de kindruns zonder tekst: profiel, uitkomst, rondes, ruw verbruik, sjabloontelling, tools en de
  vraag naar boven.

De ruwe runs staan niet in de repo.
