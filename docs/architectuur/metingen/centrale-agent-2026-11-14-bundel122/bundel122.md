# ADR-016: controlemeting van D01 na de aansluiting in de breedte (bundel 122, 14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, alleen D01, met akkoord van de gebruiker.

- **Code:** graph-qa op `31116955` (bundel 122, #1527), `CENTRALE_AGENT=meten`. Daarin onder meer:
  - de controle per stuk (`stukcontrole.py`);
  - geweigerde aanroepen als `tool_execution` met `status: geweigerd`;
  - `agentvorm`, `subagent`, `ouder_run_id` en het model in de meting van de beurt;
  - de opdracht en de antwoorden als bericht in het deelgesprek (`doorgegeven`);
  - `delegatie_stand` en `beantwoord_kaart`;
  - `laad_skill` en `lees_skill`;
  - de B1-fix voor een wachtend rapport.
- **Nulpunt:** D01 in de meting van #1510 op `c45cfd19`
  ([`../centrale-agent-2026-11-14-bundel120/bundel120.md`](../centrale-agent-2026-11-14-bundel120/bundel120.md)): 573k.
- **Hoe gemeten:** dezelfde vraag en dezelfde drie antwoorden als bij bundel 118–120, in een lokale kopie van de set
  die niet in de repo staat. Het kind stelde drie vragen, dus alle drie de antwoorden zijn gebruikt.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen: de graaf was gevuld.
- **Totaal:** 652.572 tokens op het account; plafond 1M.

## Kort

| Punt | Uitkomst |
|---|---|
| 1. Kosten | **653k**, tegen 573k bij #1510 (+14 %). Kind deel 1 254k, kind deel 2 304k, centrale agent 94k. **De controle per stuk kostte 0:** zij draaide niet, omdat de goedkopere toetsen al iets vonden (zo is het gebouwd). Er staat geen aanroep met de rol `stukcontrole` in de meting |
| 2. Ving de controle per stuk iets? | **Niet gedraaid.** De toetsen op woorden en passages vonden wel iets, en dat leidde tot een correctieronde in de centrale agent (punt 1 hieronder). Die ronde kostte ongeveer 64k: de tweede en de derde aanroep |
| 3. Het deelgesprek | **Gehaald.** Het eerste bericht is van Lex (`rol: assistant`, `doorgegeven: opdracht`) en begint met "OPDRACHT VAN DE CENTRALE AGENT". De antwoorden staan in een eigen bericht van Lex (`doorgegeven: antwoorden`, "ANTWOORD OP JE VRAGEN (van de gebruiker)"). Er staat geen bericht van de jurist in het deelgesprek |
| 4. `delegaties` | **Gehaald.** Het bericht met de vraagkaart en het eindantwoord dragen `delegaties: ["fccdff1101244c7a"]`; de berichten met kaart 2 en 3 hebben een lege lijst. `/v1/delegaties?gesprek_id=` (via de BFF) geeft één delegatie, `status: klaar`, met het plan, de opdracht en het hervatte kind. Diens `gelezen` noemt alle 16 stukken uit beide delen, en `periode` is `[2022, 2024]` |
| 5. De meting van de beurt | **Gehaald.** Bij de ouder: `agentvorm: centraal`, geen `subagent` en geen `ouder_run_id`, model `claude-sonnet-4-6`. Bij het kind: `agentvorm: centraal`, `subagent: true`, model `claude-sonnet-4-6`. `ouder_run_id` wijst naar de beurt die het deel startte: deel 1 naar beurt 0, deel 2 naar beurt 3. De spans zijn niet gecontroleerd |
| 6. Geweigerde aanroepen | **Gehaald.** De centrale agent deed in ronde 2 vier keer `get_uitspraak`. Elke aanroep staat als `tool_execution` start en eind met `status: geweigerd` en `foutcode: na_subagent`, met `duur_ms: 0`. In het denkproces staat geen "leest …". De enige statusregel ("zoekt in de wetgeving en Rechtspraak") is de vaste regel bij de eerste ronde |
| 7. Brongetrouw | **Wat er staat klopt, maar er staat weinig.** Het eindantwoord vat alleen HR:2023:1371 samen; dat stuk las deel 1, en elke bewering klopt met de tekst. Vier andere stukken laat het bewust weg, ook al vatte het rapport ze goed samen. De periode is gevolgd: niets van buiten 2022–2024. De citaten zijn 10 van 10 letterlijk, maar het zijn kopregels |
| 8. Vragen en kaarten | **Gehaald.** Drie vragen in één keer: periode, instanties en aspect. Kaart 2 en 3 kwamen zonder modelronde (0 tokens, < 1 s). Lex beantwoordde geen vraag zelf. Er was geen werkgebied, dus het pad van `delegatie_stand` is niet geraakt; het event komt niet voor |

**Wat naar T1/A1 gaat:**

1. **Goede samenvattingen vallen weg doordat het rapport te weinig passages draagt.** Het rapport van deel 2 vat
   HR:2023:181, :563, :176 en PHR:2024:936 juist samen. Bij HR:2023:181 klopt nu ook de bewijslast: de ontvanger
   bewijst kennelijk onbehoorlijk bestuur waar tijdig was gemeld. Toch krijgen alle vier in de centrale agent
   `duiding … zonder passage van dat stuk in het rapport`, om twee redenen:
   - de citaten in het rapport komen alleen uit HR:2023:1371 (vooral kopregels);
   - de grens van vier stukken als citaat liet HR:2023:181 en PHR:2024:936 weg ("2 stukken boven de grens van 4 niet als
     citaat getoond").

   De centrale agent probeerde de stukken opnieuw te lezen (vier keer geweigerd, terecht). Daarna schreef hij ze onder
   *Niet samengevat*. De toets meldt daarna nog steeds dezelfde vier `onbevestigd`, nu op de zin die zegt dat ze
   weggelaten zijn. Dat is een valse treffer: die zin vat niets samen.
2. **"Gedragen door de passages in het rapport" klopt niet voor HR:2023:1371.** De samenvatting klopt met de
   uitspraak (r.o. 3.3–3.8), maar de passages in het antwoord zijn de kop van het arrest ("HOGE RAAD DER
   NEDERLANDEN", "BELASTINGKAMER", "tegen"). In het kind stond deze duiding wel als `die de passages van dat stuk niet
   dragen`; in de centrale agent niet.
3. **De toets op een woord uit de vraag treft een opsomming.** In de twee delen van het kind staat bij HR:2023:563, :176, :1107, :181 en
   PHR:2024:936 `met 'betalingsonmacht' uit de vraag, dat niet in dat stuk staat`. Het woord staat in de zin onder
   *Gedaan*: "de meest relevante stukken over de melding van betalingsonmacht gelezen: HR:2023:1371 …, HR:2023:563 …".
   Dat is half terecht. De zin noemt stukken die volgens het rapport zelf niet over de melding gaan, maar hij vat ze
   niet samen. Het kind kreeg er geen extra ronde door: het rapport ging in één keer.
4. **De afbakening komt nu bij de jurist.** Deel 1 zocht alleen bij de Hoge Raad. De beurt met de vraagkaart zegt: "De
   subagent beperkte het zoeken zelf, zonder dat je daarom vroeg: instantie: Hoge Raad. Wil je dat breder, zeg het
   dan." Na het antwoord "alle instanties" zocht deel 2 bij alle instanties.

## Brongetrouw

Vergeleken met de volledige tekst via de open data van de Rechtspraak.

| Uitspraak | Lex zegt | Volgens de tekst | Oordeel |
|---|---|---|---|
| HR:2023:1371 (eindantwoord) | melding binnen twee weken (art. 7 lid 1 UB), doel het invorderingsbeleid; bewijslast bij de ontvanger na een correcte melding (lid 3); vermoeden en tegenbewijs bij niet melden (lid 4); de gewezen bestuurder altijd tot tegenbewijs (leden 5 en 6); geen matiging; "vergaande onzorgvuldigheid"; prejudiciële vragen; de feiten | r.o. 2.1–2.2, 3.3–3.8 en 4 | **klopt** |
| HR:2023:181 (alleen in het rapport) | twee tijdvakken tijdig en rechtsgeldig gemeld; de Hoge Raad casseert op gelieerde schuldeisers en persoonlijk belang; de ontvanger bewijst waar wel was gemeld | r.o. 2.1, 4.1.2–4.1.3 | **klopt**, nu ook de bewijslast; bereikte de jurist niet |
| HR:2023:563, :176, PHR:2024:936 (alleen in het rapport) | als bij bundel 118–120 | | **klopt**; bereikte de jurist niet |

## Per beurt

| Beurt | Wat | Account | Centrale agent | Kind |
|---|---|---|---|---|
| 0 | opdracht → kaart 1 (periode) | 254.441 | 0 modelrondes | deel 1: 6 aanroepen, 15 tools (12× `get_uitspraak`), 254k ruw / 94,5k gewogen warm, `vraag` (3 vragen), afbakening `instantie: Hoge Raad`, begint op 22k |
| 1 | antwoord 1 → kaart 2 (instanties) | 0 | 0 | — |
| 2 | antwoord 2 → kaart 3 (aspect) | 0 | 0 | — |
| 3 | antwoord 3 → hervatten, eindantwoord | 398.131 | 3 modelrondes: 29k, 31k (correctie, 4× geweigerd), 32k; 94k ruw / 38,9k gewogen warm | deel 2: 4 aanroepen, 9 tools (7× `get_uitspraak`), 304k ruw / 132,6k gewogen warm, `klaar` met rapport, begint op 63k |

Deel 2 las nu wel zelf: zeven nieuwe stukken, waaronder HR:2023:181 en PHR:2024:936. Daardoor kost het meer dan bij
bundel 120 (304k tegen 226k), en dat is het grootste deel van de +14 %.

## Open punten

- De controle per stuk is niet gemeten: zij draait alleen als de goedkopere toetsen niets vinden, en die vonden hier
  steeds iets.
- `delegatie_stand`, `beantwoord_kaart` en `laad_skill`/`lees_skill` kwamen in deze run niet voor.
- De spans per subagent zijn niet gecontroleerd.

## Bestanden

- `b122-delegatie-runs.jsonl`: D01 (één regel, `centrale_agent_vat.py`), met de status en de stukken van beide
  rapporten en de geweigerde aanroepen.
- `b122-kinderen.jsonl`: de twee delen van de kindrun (ouder-run, agentvorm, aanroepen, modellen, ruw, gewogen,
  beginnende context, sjabloon, tools), zonder tekst.
