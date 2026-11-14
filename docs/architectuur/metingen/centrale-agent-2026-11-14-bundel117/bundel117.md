# ADR-016: de vraag sluit de beurt, en verify na een subagent (bundel 117, 14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, alleen D01, met akkoord van de gebruiker.

- **Code:** graph-qa op `be0acda8` (bundel 117, #1500), `CENTRALE_AGENT=meten`. Daarin zit **#1499**:
  - een kind met status `vraag` sluit de beurt met alleen de vraagkaart;
  - `verify` vangt een samenvatting van een stuk dat niet gelezen is;
  - het kind stelt zijn vragen in één keer.

  Ook het meetscript is hersteld. Het sloeg na een stil venster het eerste event over: het eindevent `regie_taak` dat in
  #1495 (S01) en #1498 (P01, taak 0) ontbrak, was een fout van het meetscript, niet van graph-qa.
- **Nulpunt:** D01 in de meting van #1498 op `680be14d`
  ([`../centrale-agent-2026-11-14-bundel116/bundel116.md`](../centrale-agent-2026-11-14-bundel116/bundel116.md)): boom
  333k.
- **Hoe gemeten:** D01 uit de aanvulling, met drie antwoorden klaar voor de kaarten `sa_vraag`, zodat het hervatten
  gemeten kon worden: "Uitspraken uit 2022 tot en met 2024.", "Alle instanties; verder geen beperking." en "Geen
  verdere beperking.". Die drie antwoorden stonden in een lokale kopie van de set en zijn niet in de repo opgenomen.
  Er kwam geen kaart, dus ze zijn niet gebruikt.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen: de graaf was gevuld.
- **Totaal:** 345.465 tokens op het account; plafond 1M.

## Kort

| Wat | Drempel | Uitkomst |
|---|---|---|
| De beurt met de vraag eindigt met alleen de kaart | geen inhoud, geen modelronde | **Niet te toetsen.** Er kwam geen vraag |
| De vragen komen in één keer | | **Niet te toetsen.** Geen vraag |
| Na het antwoord gaat het kind verder en rondt af | rapport | **Niet te toetsen.** Geen vraag, dus niets te hervatten |
| De centrale agent vat het rapport samen zonder opnieuw te lezen | 0 tools in de ouder | **Gehaald.** 0 tools, 2 aanroepen, 46k ruw |
| De samenvattingen kloppen met de gelezen tekst | | **Niet gehaald, ernstig.** Geen van de zeven samenvattingen past bij de uitspraak (§*Brongetrouw*) |
| `verify` vangt het | | **Niet gehaald.** `grounding`: *gegrond*, 7 bronnen, geen `unsupported` |
| Kosten tegen #1498 | 333k | **342k (+3 %).** Ouder 46k ruw / 14,7k gewogen warm, kind 296k / 95,4k |

**Wat naar T1/A1 gaat:**

1. **Het kind vraagt niet, en de code sluit hem af als `klaar`.** Het kind deed 13 tools, onder meer 10×
   `get_uitspraak`, en haalde in 8 aanroepen de laatste ronde zonder eigen rapport. Zijn laatste tekst is: "De
   subagent rondde niet af met een rapport voor zijn laatste ronde; de code sloot hem af met wat hij las." Het rapport
   staat als gevuld, de uitkomst is `klaar` (`opgeleverd: 1`). Een periode heeft hij niet gevraagd en ook niet gekozen.
   In #1498 vroeg hetzelfde kind wel naar de periode. In één run is niet te zeggen of de instructie "in één keer"
   het vragen verdrong, of dat dit spreiding is.
2. **De centrale agent verzint de inhoud van zeven uitspraken.** Het kind las ze wel: alle zeven ECLI's staan in zijn
   aanroepen van `get_uitspraak`. Volgens de officiële tekst zegt geen ervan wat het antwoord zegt (§*Brongetrouw*).
   Het antwoord begint met "De samenvatting is gebaseerd op wat de subagent las". De afsluiting van de code geeft de
   centrale agent kennelijk niet genoeg tekst om samen te vatten, en hij vult het gat met wat over de melding
   waarschijnlijk klinkt.
3. **`verify` ziet het niet.** Het antwoord heeft geen citaten, alleen samenvattingen bij een ECLI. De controle in
   #1499 vangt een samenvatting van een stuk dat *niet gelezen* is. Hier is elk stuk gelezen, maar de samenvatting
   komt niet uit die tekst. Dit is hetzelfde patroon als in #1498, met HR:2026:586 voor de tweede keer.

## Brongetrouw

Elke samenvatting is vergeleken met de officiële tekst via de open data van de Rechtspraak: de inhoudsindicatie, en
of het onderwerp van de samenvatting in de tekst voorkomt.

| Uitspraak | Lex zegt | De uitspraak gaat over |
|---|---|---|
| HR:2026:586 | bij niet tijdig melden alleen ontsnappen met bewijs; "onweerlegbaar vermoed" | aansprakelijkstelling voor een vergrijpboete naast een strafrechtelijke veroordeling (una via); het woord "melding" komt niet voor |
| PHR:2026:845 | of een algemene mededeling als melding geldt | strafzaak: opzettelijk niet betalen (art. 69a AWR), ontvankelijkheid OM, strafuitsluitingsgrond bij uitstel van betaling |
| PHR:2025:435 | of een melding door een curator meetelt; "persoonlijke verplichting" | aansprakelijkheid van een (gewezen) bestuurder die zich voor een ander tijdvak kon disculperen |
| PHR:2025:426 | bewijslast bij ontbrekende melding, "vage stellingen" | Curaçaose zaak, prejudiciële vragen over hoofdelijke aansprakelijkheid, art. 1 EP EVRM, bevoegde rechter |
| PHR:2024:936 | vermoeden van art. 36 lid 4, interne organisatieproblemen | verjaring van de dwanginvordering na uitstel van betaling; "melding" komt niet voor |
| GHSHE:2025:1495 | geen tijdige melding, een mondelinge mededeling volstaat niet | IB/PVV: verkrijgingsprijs aanmerkelijk belang, turboliquidatie; "melding" komt niet voor |
| GHARL:2025:1599 | melding tijdens faillissement, aansprakelijkheid vervalt | uitspraak na verwijzing over het Unierechtelijke verdedigingsbeginsel (andere afloop); "melding" komt niet voor |

Het antwoord heeft geen blokcitaten. Gelezen en gevonden zijn goed gescheiden: alle zeven zijn gelezen, en het
antwoord noemt zestien andere stukken die alleen in de zoekresultaten stonden als *niet* gelezen.

## Open punten

- De vraag naar boven, de kaart zonder inhoud en het hervatten (#1499) zijn niet gemeten, omdat het kind niet vroeg.
  Een tweede run van D01 kan dat alsnog laten zien.
- Wat de afsluiting door de code ("met wat hij las") aan de centrale agent doorgeeft: zonder de inhoud van het rapport
  in de events is niet te zien of de tekst van de uitspraken erin zit.

## Bestanden

- `b117-delegatie-runs.jsonl`: D01 (één regel, `centrale_agent_vat.py`).
- `b117-kinderen.jsonl`: de kindrun (aanroepen, modellen, ruw, gewogen, sjabloon, tools), zonder tekst.
