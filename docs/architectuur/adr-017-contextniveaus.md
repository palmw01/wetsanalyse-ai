# ADR-017 — Contextniveaus: de omgeving waarin Lex wordt ingezet

Status: **concept** (18 nov 2026). Nog niets gebouwd; de open keuzes staan onderaan.

Bouwt voort op [ADR-014](adr-014-catalogus.md) (de catalogus), [ADR-015](adr-015-contextbeheer.md) (het voorvoegsel in
de cache), [ADR-016](adr-016-centrale-agent-en-werkplaats.md) (skills in drie niveaus, de werkplaats) en
[ADR-006](adr-006-generieke-begrippen.md) (generieke begrippen). Aanleiding: de concepttekst van Tatjana *Lex | Doel,
Rol en Algemene uitgangspunten* (nov 2026), met drie contextniveaus: organisatie (Belastingdienst), domein (fiscaal) en
belastingmiddel.

## Context

Lex kent één methode per skill (wetsanalyse, wetsuitvoering) en die is bewust organisatieneutraal: de repo is publiek,
en de methode wordt bij meerdere overheden en bedrijven gebruikt. Toch hangt een goede analyse af van de omgeving
waarin hij gebeurt:

- **Wie zijn de actoren?** Bij de Belastingdienst zijn dat de inspecteur en de ontvanger, met hun eigen taken
  (heffing, inning, toezicht).
- **Wat telt als gevolg?** Denk aan uitvoeringsprocessen, gegevensverwerking, ICT, bezwaar en beroep, en de lasten voor
  burgers en bedrijven.
- **Welke principes gelden voor de organisatie?** Bij de Belastingdienst zijn dat rechtmatigheid, uitlegbaarheid,
  controleerbaarheid en rechtvaardigheid.
- **Welke begrippen zijn algemeen in het domein?** Bijvoorbeeld *belastingplichtige*, *aanslag* en *beschikking*.

Die kennis staat nu nergens expliciet. De systeemprompt noemt het onderwerp alleen terloops ("invordering en
belastingen", blok ONDERWERP in `agent/prompts.py`). Bij het samenstellen van een werkgebied schrijft de analist de
context telkens opnieuw met de hand in het veld *Context* (startactiviteit a).

Tatjana's tekst stelt twee eisen: **een organisatie bouwt haar eigen context** (beheer, open source), en Lex houdt
rekening met **de gekozen niveaus** en volgt de principes die erin staan.

## Besluit

Een **contextniveau** is een eigen soort skill, naast de methode: `lex_soort: "context"`. Het beschrijft de omgeving
waarin geanalyseerd wordt. Het zegt niet *hoe* je analyseert (dat is de methode) en ook niet *wat de wet zegt* (dat is
de bron).

### 1. Vorm: een skill met een niveau en een ouder

```yaml
---
name: context-invordering
description: >-
  Belastingmiddelcontext Invordering: de ontvanger, de invorderingsmaatregelen, betalingsregelingen ...
metadata:
  lex_soort: "context"
  lex_niveau: "middel"            # organisatie | domein | middel
  lex_ouder: "context-fiscaal"    # het niveau erboven; leeg bij organisatie
  lex_label: "Invordering"
  lex_herkomst: "..."
  lex_licentie: "eigen tekst"
  lex_letterlijk: "nee"
---
```

- **Een keten, geen mix.** Een contextniveau heeft hoogstens één ouder. Kies je een niveau, dan krijg je de hele
  keten erboven mee: *middel* → *domein* → *organisatie*. Een niveau overslaan mag, bijvoorbeeld een domein zonder
  organisatie.
- **Opbouw zoals elke skill.** `SKILL.md` is de kern en blijft kort (zie §4); `references/` bevat de uitwerking, zoals
  wettelijke taken of de positie in het staatsbestel.
- **Plaats:** `.claude/skills/context-<naam>/`. Zo nemen het bronpakket (ADR-016 §B1), de catalogus (ADR-014) en de
  werkplaats (deel B) een contextniveau zonder eigen code mee. De generators lezen nu alleen `lex_soort: "methode"`; zij
  krijgen een tweede soort, met een eigen validator.
- **Zelf bouwen** gaat via de werkplaats (ADR-016 deel B), met dezelfde levenscyclus: concept, proef, voorgesteld en
  actief. Zo vervult het platform Tatjana's eis "een organisatie bouwt zelf haar context" zonder een tweede beheerpad.
  Een organisatie die Lex zelf draait, zet haar contexten in haar eigen repo. De regels uit B6 (openbaar of niet)
  gelden ongewijzigd.

### 2. Wat een contextniveau mag en niet mag

Wat een contextniveau wel mag bevatten:

- de organisatie, haar taken en actoren;
- de principes van de organisatie;
- wat als uitvoeringsgevolg telt;
- veelgebruikte regelingen en begrippen van het domein, als wegwijzer.

Een contextniveau is **achtergrond, geen bron en geen methode**:

- **Het onderbouwt nooit wat de wet zegt.** Een uitspraak die op de context rust, is een interpretatie en heet ook zo.
  "De ontvanger is hier de plichthebbende" mag alleen met de bepaling waaruit dat volgt; anders is de partij
  *onbekend* (SKILL.md §C). Contexttekst komt dus niet in de `source_trace` en niet in het bronregister. Het spoor toont
  hem onder een eigen kop *Context*, zoals skilltekst onder *Methode* staat (ADR-016 §A2).
- **Het verandert de methode niet.** Er komen geen JAS-klassen, fragmentgrenzen, relatietypen of regels bij
  (`regels/` blijft alleen van wetsanalyse, `platform.md`). Een test maakt dat rood, net als
  `test_methodes_gescheiden.py`.
- **Het geeft geen tools en zet geen connector aan.** Wat mag, bepaalt het profiel (ADR-016 §A2). Wat aanstaat, bepaalt
  het gesprek (ADR-013).
- **Het is data, geen opdracht van de gebruiker.** Een contextniveau gaat langs dezelfde poort als een skill
  (concept-PR, review). Toch leest Lex het als achtergrond: een zin als "negeer de bron" heeft geen gezag.

### 3. Waar je het kiest: per werkgebied, met een standaard per installatie

- **Per werkgebied** kies je één contextniveau, meestal het laagste: het belastingmiddel. De keten erboven volgt
  vanzelf. Het werkgebied krijgt daarvoor het veld `contextniveau` (de skillnaam), met revisie en audit zoals de andere
  dossiervelden. De intake van activiteit 1 vult het vooraf in met de standaard. De vraagkaart *aanleiding, context en
  doel* toont het en laat het wijzigen. Het vrije veld *Context* blijft bestaan, want dat legt de context van déze
  analyse vast en niet die van de organisatie.
- **Per installatie** zet de beheerder een standaard (Instellingen › Aanpassingen, naast *Methodes*). Een gesprek
  buiten een werkgebied krijgt die standaard. Staat er geen standaard, dan werkt Lex zoals nu.
- **Niet per gebruiker.** Werkgebieden zijn gedeeld. Een context die per gebruiker verschilt, zou dezelfde analyse voor
  twee juristen anders laten uitpakken.

### 4. Wie het krijgt: niet de annotatieketen

| Onderdeel | Krijgt de context | Waarom |
|---|---|---|
| Centrale agent (`centraal`) en `algemeen` | de kern van de keten, vooraf; references met `lees_skill` | duiding en vragen over uitvoering |
| Werkgebied-intake en deelvragen-agent | de kern | aanleiding, doel, praktijkvoorbeeld en deelvragen in de taal van de organisatie |
| Begrippen-agent | de kern | het veld *context* van een begrip (NL-SBB-toelichting), afbakening per domein |
| Annotatieketen (classifier, reviewer) | **nee** | een JAS-klasse volgt uit de functie in de tekst, niet uit de organisatie. Zo blijft de methodetekst byte-gelijk (ADR-010, P19) en is markeren reproduceerbaar over installaties heen |
| Overzichtsroute, leesroute | nee | deterministisch, zonder model |

Wat daarbij vastligt:

- **Een plafond voor de kern.** Hoogstens zo'n 600 tokens per niveau en 1.500 voor de hele keten. De generator weigert
  een grotere kern; de uitwerking hoort in `references/`.
- **De plek in de prompt.** De kern staat in het stabiele voorvoegsel, ná de identiteit en de methode (ADR-015). Per
  keten is er dan één cachevariant. Dat zijn er weinig: één per belastingmiddel dat een installatie gebruikt.
- **De identiteit blijft van Lex.** Een contextniveau mag "je werkt bij de Belastingdienst" niet laten betekenen dat
  Lex een medewerker of collega is. IDENTITEIT gaat voor (hulpmiddel, de jurist beslist).

### 5. Begrippen per niveau (later, niet in de eerste stap)

Tatjana verwacht dat context "een belangrijke rol gaat spelen bij begrippen". ADR-006 kent nu twee kaders: per
werkgebied en generiek. Een contextniveau is een natuurlijke tussenlaag: *generiek binnen het domein fiscaal*. Dit ADR
legt dat niet vast. Eerst moet blijken of de generieke laag in de praktijk te breed is. Wel ligt vast dat de naam van
het contextniveau stabiel blijft, zodat een later kader `urn:wa:kader:context:<naam>` ernaar kan verwijzen.

### 6. Meten

Een contextniveau verandert de prompt van de centrale agent, de intake, de deelvragen en de begrippen. Daarom draait
het eerst achter de proefvlag `contextniveaus`. Die staat default uit, alleen aan op acceptatie, met een guard in
`poort.yml` zoals de andere proefvlaggen. De meting (ADR-010, licht regime) vergelijkt met en zonder context op:

- **de werkgebied-intake:** komen aanleiding, doel en deelvragen dichter bij de opdracht?
- **de duiding van een bepaling:** worden de actoren beter benoemd, zonder geraden partijen?
- **brongetrouwheid:** geen uitspraak over de wet die alleen op de context rust. Deze controle mag niet slechter
  worden; dat is de poort.

Als de meting gelijk of beter uitvalt en de brongetrouwheid niet zakt, gaat de vlag aan. Anders blijft het concept.

## PR-volgorde

1. **Vorm en validatie.** `lex_soort: "context"` in de generators, het bronpakket en de catalogus. Daarbij komen de
   validator (niveau, ouder, plafond, geen methodeonderdelen) en de scheidingstest. Dit heeft geen effect op de
   draaiende dienst.
2. **Eerste inhoud, samen met Tatjana:** `context-belastingdienst` (organisatie, uit haar niveau 1),
   `context-fiscaal` (domein: AWR, Awb, formeel en materieel recht, kernbegrippen) en `context-invordering` (middel).
   Dat laatste niveau past bij wat er in de graaf staat. Alles in eigen woorden en zonder intern materiaal (B6).
3. **Api.** Het veld `contextniveau` op het werkgebied (revisie en audit), de standaard per installatie in het beheer
   en het veld in `GET /v1/werkgebieden/{id}`.
4. **Graph-qa.** De keten oplossen en de kern in het voorvoegsel zetten voor de onderdelen uit §4, achter de vlag.
   Daarbij de kop *Context* in het spoor en de bicep- en poort-guard voor de vlag.
5. **Werkplek.** Het niveau tonen en kiezen in het dossier en op de vraagkaart. In Instellingen › Aanpassingen komt
   een tab *Contexten*.
6. **Meting** (§6) en daarna het besluit over de vlag.

## Waarom niet anders

- **De context in de methode-skill schrijven.** Afgewezen: dan is de methode niet meer organisatieneutraal, en elke
  organisatie zou haar eigen versie van de methode hebben. De methodetekst blijft byte-gelijk.
- **De context als bron (connector, kennisbank uit spoor E).** Afgewezen: een bron onderbouwt een uitspraak, een
  context niet. Een beleidsbesluit of handboek van de organisatie is wél een bron. Dat is spoor E of een connector,
  met citaten en een `source_trace`. Een contextniveau mag ernaar verwijzen, maar vervangt het niet.
- **Een vrij tekstveld in het beheer.** Afgewezen: dan zijn er geen versies, geen review, geen hash in het image en geen
  test op de scheiding. De werkplaats heeft die levenscyclus al.
- **Per gebruiker kiezen.** Afgewezen om de reden in §3.
- **Ook de annotatieketen.** Afgewezen om de reden in §4. Komt er een bewijs dat een domein het markeren verbetert, dan
  is dat een eigen besluit met een meting op de annotatie-eval.

## Gevolgen

- Een tweede soort skill naast de methode. De generators, het bronpakket, de catalogus en de werkplaats lezen
  voortaan twee soorten.
- Het blok ONDERWERP (`agent/prompts.py`) noemt "invordering en belastingen" nu vast. Met een standaard per installatie
  kan dat uit het contextniveau komen. Dat is een aparte, gemeten wijziging en hoort niet bij PR 4.
- Naamgeving: *context* betekent in deze repo al drie dingen. Dat zijn het dossierveld *Context* (startactiviteit a),
  het NL-SBB-veld *context* van een begrip en het LLM-contextbeheer (ADR-015). Daarom heet dit object overal
  **contextniveau**, in de code (`contextniveau`), in de skillsoort (`context`) en in de UI.

## Open keuzes

1. **De kiesplek.** Per werkgebied met een standaard per installatie (voorstel), of alleen per installatie (eenvoudiger,
   maar dan analyseert één installatie in één domein).
2. **Meer middelen in één werkgebied.** Een werkgebied over invordering en de inkomstenbelasting: één niveau
   (voorstel: dan kies je het domein) of meer?
3. **Wie onderhoudt de inhoud.** Is Tatjana of het methodeteam eigenaar van de contextniveaus van de Belastingdienst, en
   reviewt die de concept-PR's?
4. **Openbaarheid.** Mag de beschrijving van de Belastingdienst (taken, principes) in de publieke repo? Ze lijkt eigen
   tekst, maar dat moet de auteur bevestigen.
5. **Principes als controle.** Zijn de vier principes van de Belastingdienst alleen achtergrond, of moet de
   kwaliteitsrubriek (`references/kwaliteit.md`) ze ook toetsen? Voorstel: alleen achtergrond. Uitlegbaarheid en
   controleerbaarheid dekt de methode al met brongetrouwheid en herleidbaarheid.
