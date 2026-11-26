# Contenttoets C5b – de gouden set na de herstelronde

Soort: *meting* · 26 november 2026 · plan [`../../plan-contenttoets.md`](../../plan-contenttoets.md), stap C5 ·
vorige meting [`../contenttoets-c5-2026-11-26/`](../contenttoets-c5-2026-11-26/README.md)

## Opzet

- **Code:** master `4e2e8b60`. Twee wijzigingen sinds C5:
  - bundel #1891: de contenttoets steunt alleen op de kennisgraaf (#1890);
  - bundel #1893: de vier bevindingen van C5 (#1892).
- **Werkwijze:** dezelfde als bij C5.
  - Per eval van de gouden set één run, in een eigen gesprek.
  - Elke run is `/contenttoets <de tekst>` met `plugins: ["contenttoets"]`.
  - De brontekst gaat niet mee: Lex zoekt de bron zelf in de graaf.
- **Model:** `claude-sonnet-4-6`, profiel `contenttoets` (versie `a7b7d4f7b712`), route `contenttoets`, 12 tools
  (alleen graaftools).
- **Beoordeling:** handmatig, door de hoofdsessie, per grader van de eval. De eval van de standaardregeling heeft sinds
  #1892 de derde zin van 25.3a.2, en de grader staat daar nu *onvolledig* toe.
- **Herhaling:** één run per eval (licht regime). De spreiding is dus niet gemeten.

## Uitkomst

| eval | C5 | C5b | vals "mogelijk onjuist" | duur | toolaanroepen | uitvoer · cache lezen · cache schrijven |
|---|---|---|---|---|---|---|
| kort-uitstel-grens-en-telmoment | 5/6 | 5/6 | 0 | 65 s | 4 | 2.765 · 32.204 · 19.842 |
| reguliere-regeling-niet-in-de-bron | 5/5 | 4/5 | 0 | 111 s | 20 | 4.756 · – · – |
| standaardregeling-zonder-fouten | 3/4 | 4/4 | 0 | 56 s | 7 | 2.488 · 30.177 · 18.349 |
| toeslagschuld-bedrag-en-looptijd | 2/5 | 4/5 | 0 | 50 s | 3 | 2.013 · 32.419 · 18.591 |
| **samen** | **15/20** | **17/20** | **0** | | | |

De grounding was in alle vier de runs `gegrond`, zonder niet-letterlijke citaten. Geen bevinding viel weg in de
citaatcontrole.

### Wat de herstelronde opleverde

- **€ 25 blijft staan.** Het oordeel *mogelijk onjuist* bij de toeslagschuld komt nu door de citaatcontrole. Bij C5
  viel het daar weg.
- **De nummering van *Voor de redacteur* klopt** met het rapport, en er staat geen regel meer bij een bevinding die
  er niet is.
- **De onderdelen worden meegelezen.** De derde uitzondering van 25.3a.1 (bezwaar of beroep) is gevonden, als
  *onvolledig* (V3), met de afweging voor de lezer. De beëindiging bij 79.7 staat onder *Ontbreekt*.
- **J4 wordt gezien.** Bij "dan krijgt u … kort uitstel" staat nu een kanttekening in de twijfel: de bron zegt "kan",
  en 25.5.3 gaat over particulieren. Het oordeel blijft *juist* (zo is de fix ontworpen). De grader vraagt alleen dat
  het rapport het opmerkt, en dat gebeurt nu.
- **Alleen de graaf.** Elke vindplaats is een `urn:bwb:`-IRI, en het profiel had alleen graaftools.

### Per eval: wat nog mist

**Kort uitstel** (5/6)

- **Gemist:** het dwangbevel kreeg *onvolledig* in plaats van *juist met onderdeel e*.
  - Lex nam in één bevinding twee dingen samen: het dwangbevel en de ontbrekende voorwaarde c.
  - Hij citeerde voor het dwangbevel de ondernemersbepaling 25.6.2d onder b.
  - Onderdeel c is daardoor wel gehaald (die grader telt mee), maar het dwangbevel zelf niet.
- **Nieuw: de lijst *Na te lopen* bevat ruis.**
  - Er staat "Vervallen." in (onderdeel b).
  - Onderdeel e (het dwangbevel) staat erin, terwijl de tekst dat zelf noemt.
- ***Voor de redacteur* staat niet op volgorde:** [3], [2], [4].

**Reguliere regeling** (4/5)

- 24 maanden is *mogelijk onjuist*. De bijzondere omstandigheden staan onder *Ontbreekt*, met het citaat.
- 8 weken staat *niet in de bron*. Daar staat geen herschreven zin bij, wel een vraag aan de redacteur.
- Het formulier staat onder *Niet getoetst*.
- **Gemist:** de kwijtschelding bij te weinig betalingscapaciteit staat niet onder *Ontbreekt*. Ze staat alleen in de
  melding *Na te lopen* van de code. De lezer ziet haar dus wel, maar het rapport zelf noemt haar niet.
- **Kosten:** Lex las 15 bepalingen (heel 25.5 en 25.5a) en deed 4 zoekslagen naar de 8 weken. Met 111 s is dit de
  traagste run.

**Standaardregeling** (4/4)

- Er is geen oordeel *mogelijk onjuist*.
- De looptijd, de termijnen en "alle openstaande aanslagen" zijn *juist*, met een vindplaats.
- De derde uitzondering en de verrekening zijn *onvolledig* (V3). Beide citaten zijn letterlijk.

**Toeslagschuld** (4/5)

- € 25 en 36 maanden zijn *mogelijk onjuist*, met de juiste citaten.
- De beëindiging en de bundeling staan onder *Ontbreekt*.
- Elk voorstel staat in de u-vorm.
- **Gemist (zoals bij C5):** het samenvoegen kreeg *onvolledig* (V1: eerst een afzonderlijke regeling) in plaats van
  *juist*. Dat is te verdedigen, maar strenger dan de eval. De grens van € 480 noemt Lex in de toelichting juist.

## Bevindingen voor het vervolg (generiek)

1. **De melding *Na te lopen* filtert te weinig.** Een vervallen onderdeel hoort er niet in. Een passage die de tekst
   al dekt (hier het dwangbevel) of die al in een bevinding staat, ook niet.
2. **Wat de code als leemte vindt, komt niet in het rapport.** In de reguliere regeling zag de controle de
   kwijtschelding, maar *Ontbreekt* noemde haar niet. Twee mogelijkheden:
   - de melding gaat terug naar het model;
   - de code neemt het punt zelf op onder *Ontbreekt*.
3. **Eén bevinding per bewering.** Een bewering die klopt (het dwangbevel) en een voorwaarde die ontbreekt (c) zijn
   twee punten. Samen in één *onvolledig* verbergen ze het juiste oordeel en de juiste vindplaats.
4. ***Voor de redacteur* op nummervolgorde** sorteren.
5. **De bronstand in de events** toont nog de connectors uit het menu van het gesprek, terwijl de contenttoets ze niet
   gebruikt. Het antwoord raakt dit niet, maar wie meekijkt wordt erdoor op het verkeerde been gezet.
6. **De eval van de toeslagschuld** (samenvoegen *juist*) en de werkwijze van Lex (*onvolledig*, omdat eerst een
   afzonderlijke regeling komt) lopen uiteen. Kies één van de twee: de eval laat *onvolledig* toe, of het oordeel
   wordt *juist*.

## Gegevens

- **Gesprekken op acceptatie (account analist):** `5fb5ae414b334c89`, `ca15fdb69b53456c`, `cb97dc90cf9841cc`,
  `7d965ee7c21145be`.
- **Runs:** `8da60685839f4a1585df743afc900903` (kort uitstel), `fdb78342a0ba47df9745186502473572` (reguliere),
  `2f3e467ff14c47878a5cea2c0dc478db` (standaard), `32bb16d2fc76498c9f5fc876af990cdc` (toeslagschuld).
- Van de reguliere regeling zijn alleen de duur en de uitvoer genoteerd.
