# Contenttoets C5 – de gouden set op acceptatie

Soort: *meting* · 26 november 2026 · plan [`../../plan-contenttoets.md`](../../plan-contenttoets.md), stap C5

## Opzet

- **Code:** master `38073111` (bundels #1876, #1880 en #1886). De proefvlag `CONTENTTOETS` is aan (azure-infra deploy op
  acceptatie, 26 nov 2026), en de beheerder biedt de plugin aan.
- **Werkwijze:** per eval van de gouden set (`.claude/skills/contenttoets/evals/`, vier stuks) één run in een eigen
  gesprek. Elke run is `/contenttoets <de tekst>` met `plugins: ["contenttoets"]`, zoals de werkplek hem stuurt. De
  brontekst uit de eval gaat **niet** mee: Lex zoekt de bron zelf in de graaf. Dat is de echte werkwijze, maar wel
  strenger dan de eval, die de bron meegeeft.
- **Model:** `claude-sonnet-4-6`, profiel `contenttoets` (versie `f98c0dca856f`), route `contenttoets`.
- **Beoordeling:** handmatig, door de hoofdsessie, per grader van de eval. Een citaat dat ik controleerde, heb ik
  in de graaf van acceptatie opgezocht (`graaf_lezen`).
- **Herhaling:** één run per eval (licht regime); de spreiding is dus niet gemeten.

## Uitkomst

| eval | graders gehaald | vals "mogelijk onjuist" | duur | uitvoer · cache lezen · cache schrijven |
|---|---|---|---|---|
| kort-uitstel-grens-en-telmoment | 5 van 6 | 0 | 120 s | 5.131 · 337.388 · 47.142 |
| reguliere-regeling-niet-in-de-bron | 5 van 5 | 0 | 102 s | 3.877 · 223.479 · 44.184 |
| standaardregeling-zonder-fouten | 3 van 4 | 0 | 77 s | 3.126 · 81.915 · 26.835 |
| toeslagschuld-bedrag-en-looptijd | 2 van 5 | 0 | 50 s | 1.814 · 39.520 · 25.077 |
| **samen** | **15 van 20** | **0** | | |

**Geen enkel vals "mogelijk onjuist".** Elk oordeel "mogelijk onjuist" was terecht en had het juiste citaat. Volgens
het plan is dat het stopcriterium, en daar is niet aan voldaan. De grounding was in alle vier de runs `gegrond`,
zonder niet-letterlijke citaten.

### Per eval

**Kort uitstel** (5/6)

- Gehaald:
  - € 25.000 is mogelijk onjuist, met als citaat "minder dan € 20.000";
  - het telmoment is mogelijk onjuist ("na de laatste vervaldag van de (oudste) aanslag");
  - het dwangbevel is juist, met onderdeel e;
  - onderdeel c staat onder *Ontbreekt*;
  - de citaten zijn letterlijk.
- **Gemist:** "dan krijgt u … kort uitstel" kreeg *juist*. De bron zegt "kan … worden getroffen" (J4 Modaliteit). Lex
  steunde op de ondernemersbepaling (25.6.2d, "kunnen … krijgen") en zag het verschil met de bepaling voor
  particulieren niet.
- Extra en terecht: Lex wijst erop dat de tekst particulieren en ondernemers niet onderscheidt.

**Reguliere regeling** (5/5)

- 24 maanden is mogelijk onjuist (J4), met het citaat over de bijzondere omstandigheden.
- 8 weken staat niet in de bron. Daar staat geen herschreven zin bij, wel een vraag aan de redacteur.
- Het formulier staat onder *Niet getoetst*. Lex beoordeelde het ook als bewering (*niet in de bron*); de grader
  accepteert dat.
- De kwijtschelding bij te weinig betalingscapaciteit staat onder *Ontbreekt*.
- **Aandachtspunt:** Lex noemt artikel 6f Uitvoeringsregeling Invorderingswet 1990 en zegt dat het "nog niet in
  werking" is. Dat heb ik niet gecontroleerd.

**Standaardregeling** (3/4)

- Er is geen enkel oordeel *mogelijk onjuist*.
- De looptijd, de termijnen en de uitzonderingen 1° en 2° zijn juist, met een vindplaats.
- Eenvoudiger woorden ("minstens", "wij") zijn niet als fout aangemerkt.
- De verrekening kreeg *onvolledig* (V3) in plaats van *juist*. **Lex heeft hier gelijk en de eval niet:** 25.3a.2
  bevat in de graaf ook "Tenzij anders overeengekomen, verrekent de ontvanger een voorlopige teruggaaf
  inkomstenbelasting over het lopende jaar niet …". De gouden set gaf alleen de eerste twee zinnen van de bron. De
  eval moet worden bijgewerkt; dit is geen fout van Lex.
- **Gemist:** de derde uitzondering (bezwaar of beroep). Die staat in de graaf als `25.3a.1/Tekst/Onderdeel._3`, maar
  Lex las hem niet. Hij noemt hem alleen als twijfel ("er kan een derde onderdeel zijn"). Wel veilig: de bewering
  kreeg niet het oordeel *juist* met een te stellige toelichting.

**Toeslagschuld** (2/5)

- Gehaald:
  - 36 maanden is mogelijk onjuist, met "binnen 24 maandelijkse termijnen";
  - er staat een voorstel in de u-vorm bij elke bevinding die niet juist is.
- **Weggevallen:** het oordeel *mogelijk onjuist* over € 25 per maand. De citaatcontrole liet de bevinding vallen
  ("1 bevinding is niet getoond: het citaat of de bronpassage was niet letterlijk te vinden"). De bron staat in de graaf
  wel letterlijk: "€ 20 per maand voor iedere terugvordering afzonderlijk", met gewone spaties. Wat er precies niet
  klopte, staat niet in de events. **Inconsistent:** *Voor de redacteur* noemt nog "Verander '€ 25 per maand' in
  '€ 20 per maand'". Dat is een regel bij een bevinding die er niet meer staat.
- Het samenvoegen kreeg *onvolledig* (V1: eerst een afzonderlijke regeling) in plaats van *juist*. Dat is te
  verdedigen, maar strenger dan de eval.
- **Gemist:** dat de regeling wordt beëindigd als de aflossing niet wordt nagekomen. *Ontbreekt* is leeg, terwijl de
  zin in dezelfde bepaling (79.7) staat die Lex las.

## Bevindingen voor het vervolg (generiek)

1. **Weggevallen bevinding en de lijst voor de redacteur lopen uiteen.** Als de citaatcontrole een bevinding laat
   vallen, moet de regel in `voor_redacteur` die ernaar verwijst ook vallen. Of de bevinding blijft staan, als het
   bronstuk letterlijk is en alleen het citaat uit de content een kleine afwijking heeft. De reden van het wegvallen
   hoort in de events (welk citaat, welke tekst). De nummering in `voor_redacteur` liep ook uit de pas: "[4]" verwees
   naar bevinding 5 (standaardregeling).
2. **Ontbreekt binnen de gelezen bepaling.** In twee van de vier runs miste Lex een materiële voorwaarde of uitzondering
   in een bepaling die hij wel opvroeg (79.7 beëindiging, 25.3a.1 onderdeel 3°). Een controlestap per gelezen bepaling
   ("welke voorwaarden, uitzonderingen en gevolgen staan hier, en noemt de tekst ze?") kan dat deterministisch
   ondersteunen. De onderdelen van de bepaling moeten dan wel meegelezen worden.
3. **Modaliteit (J4).** "Dan krijgt u" tegenover "kan worden getroffen" is gemist, omdat een verwante bepaling met
   "kunnen … krijgen" als steun gold. Een bewering die steunt op een bepaling voor een andere doelgroep dan de tekst, is
   een signaal.
4. **De gouden set.** Bij `standaardregeling-zonder-fouten` hoort de derde zin van 25.3a.2 erbij. Dan is
   *onvolledig* over de verrekening een te verwachten uitkomst.

## Gegevens

- **Gesprekken op acceptatie (account analist):** `2194105bf5d84352`, `0cfa3b8cf651434e`, `8c845fe1d52942e9`,
  `a16503abaea448d4`.
- **Runs:** `194a01dd2f9a42e1a34277fdfb002ba5`, `45f56a1b57ca41eaaffc05c60005853c`, `508887d233314047b19510b576ce3b02`,
  `1104571876fd4359b66eb1daffce545b`.
- De volledige antwoorden staan in die gesprekken (blok `contenttoets`). In deze map staan alleen de beoordeling en de
  cijfers.
