# Plan: elke geclassificeerde formulering een begrip (activiteit 3a)

Status: **fase 1 (B1–B3) in uitvoering**, de rest concept · 18–19 nov 2026. De onderbouwing (de bron per klasse, de
verdeling in werkgebied *Termijnen* op acceptatie) staat in een lokaal onderzoeksrapport; de kern staat hieronder en in de
skill (`references/begrippen.md`, *Welke formulering krijgt wat*; register P21). Het hoort naast
plan-afleidingsregels ([PR #1737](https://github.com/palmw01/wetsanalyse-ai/pull/1737)) (activiteit 3b). Dat plan stelt in A2 en D5
hetzelfde voor als dit plan; dit plan levert dat mechanisme, en 3b bouwt erop voort.

Uitgangspunt: **de bron is leidend.** Elke regel hieronder volgt uit een bronvindplaats. Waar het een projectkeuze is,
staat dat erbij.

**Aanleiding.** In *Termijnen* waren 212 elementen geannoteerd, waarvan 56 (26 %) gekoppeld aan een geaccordeerd
begrip; 156 stonden op "te verwerken". Volgens de methode krijgt ruwweg 85–90 % een begrip. Het gat zit niet in NL-SBB
maar in de keten (alleen groepen van minstens twee, operatoren en parameters uitgesloten, zinsvormen niet gegroepeerd),
in een afwijsmaatstaf uit de gegevensblik ("geen eigen gegeven") en in het slanke profiel (P15).

## 1. Wat de bron vraagt

1. Elke geclassificeerde formulering krijgt een begrip. Een begrip wordt hergebruikt bij dezelfde betekenis; bij een
   homoniem komt er een nieuw begrip (M01 h.3 stap 3a; M02 §3.5.1–3.5.2a; M03 hoofdactiviteit 3a).
2. Uitzonderingen per klasse:
   - een voorwaarde krijgt een omschrijving "indien …" (M01 h.6–7);
   - een vaste waarde zoals "nihil" krijgt niets (M01 h.6);
   - een brondefinitie wordt de wettelijke definitie van het begrip, geen eigen begrip (M01 h.4 punt 16, h.6).
3. Operatoren krijgen herbruikbare begrippen ("plus", "min"), afleidingsregels en rechtsfeiten een naam met een
   werkwoord vooraan (M01 h.3 stap 3b, h.6; M02 §3.5.2a).
4. Een begrip draagt zijn klasse, de brondefinitie, "specialisatie van" en, bij een rechtsbetrekking, de rechtkant, de
   plichtkant en het voorwerp als begrippen (M01 h.6 §6.3.4). M04 H3 geeft de JAS-klassen als NL-SBB-topbegrippen.
5. De verzameling is begrensd door het diagram. Alleen formuleringen die met een centrale klasse samenhangen, doen mee
   (M02 §3.4.2c; M03 hoofdactiviteit 2).
6. Een begrip is bouwsteen voor het gegevens-, regel- en procesmodel (M03 hoofdactiviteit 3a). "Geen eigen gegeven" is
   dus geen afwijsreden.

## 2. PR-stapel

Fase 1 (B1–B3) rust alleen op de bron en kan in één bundel naar acceptatie. Fase 2 (B4–B6) verandert wat Lex
voorstelt en wordt per stap gemeten. Fase 3 (B7–B8) vraagt een besluit of een modelstap.

### Fase 1 — de maat en de methode

**B1 · Skill: verwachting per klasse** (alleen skill en docs, maar wel een build-input).

- Een tabel *Welke formulering krijgt wat* in `references/begrippen.md`, per klasse met bronvindplaats.
- Hetzelfde als data: `begripverwachting.json`, naast `relaties.json`, met per klasse `begrip`, `omschrijving` of
  `koppeling-definitie`.
- Een generator naar `api/app/jas_begripverwachting.py` en `frontend/lib/jasBegripverwachting.ts`, met een drift-test
  (zelfde patroon als `genereer_jas_relaties.py`). Het bronpakket wordt bijgewerkt.
- In `references/begrippen.md`: "geen eigen gegeven, organisatie of kalendereenheid is geen reden om af te wijzen", en
  "een losse markering zonder centrale klasse: eerst de vraag of ze erbij hoort". De rolbeschrijvingen van
  `agent-jurist` en `agent-gegevensspecialist` volgen.
- Dit is tekst buiten de methodemarkers en `begrippen.md` gaat niet in een prompt, dus er is geen meting nodig (P19). Dat
  ga ik na voor de merge.
- `bronnen.md`: een nieuwe regel P-dekking. ADR-004 krijgt een aanvulling met de aankondiging van B4–B6.

**B2 · Api: dekking per klasse** (api, met het contract in `frontend/lib/types.ts` en kruistests).

- `dekking()` geeft per element `verwacht` (uit B1) en totalen per klasse.
- *Voorwaarde* (verwacht een omschrijving): ze telt als `verwerkt_via_drager` zodra een ADR-011-relatie `voorwaarde` haar
  aan een drager hangt die zelf gekoppeld is.
- *Brondefinitie*: ze telt als verwerkt als ze met de rol `definitie` aan een begrip hangt. Dat kan nu al; dit maakt het
  expliciet.
- Het nieuwe signaal `zonder_samenhang`: een element zonder enige ADR-011-relatie naar of van een centrale klasse. Dat is
  een vraag, geen stand, en het telt niet mee in de noemer van de begrippen.
- De bestaande standen blijven. Er komt één stand bij, en een noemer "verwacht een begrip".

**B3 · Werkplek: dekking zichtbaar en afwijzen met gevolg** (frontend, api).

- Tab Elementen: de werkvoorraad per klasse, met de verwachting als label ("krijgt een begrip", "krijgt een
  omschrijving").
- Een groep afwijzen vraagt wat er met de passages gebeurt:
  - "ander begrip": koppelen;
  - "geen begrip": buiten behandeling, met de reden van de afwijzing;
  - "later": niets.

  De route `groepen/{id}/afwijzen` krijgt een optioneel veld daarvoor. Het rapport (ADR-009) neemt de dekking per klasse
  over.

### Fase 2 — wat Lex voorstelt (deterministisch, per stap gemeten)

**B4 · Keten: groep van één en koppelen aan een bestaand begrip** (graph-qa `begrippen_pipeline`, api `begrippen_run_store`).

- Een formulering die volgens B1 een begrip verwacht en in geen groep zit, wordt een groep met één lid. Ze is altijd
  geel, met de uitleg "komt één keer voor".
- De naam komt uit de taalanalyse (term, enkelvoud, zonder lidwoord; M02 §3.5.2a, *Begripsnaam*).
- Komt de naam overeen met een begrip in het werkgebied of het generieke kader, dan verschijnt via het bestaande
  `lijkt_op` het voorstel "koppel aan …".
- Bij tegenbewijs (een beperking, of een berekening in de bepaling: `BEREKENING_IN_BEPALING`) blijft het voorstel geel,
  als mogelijk homoniem (M01 h.3 stap 3a, bijdrage-inkomen).
- De parameter gaat uit `geen_begrip.yaml` (M01 h.6). Een parameterwaarde die alleen een getal of bedrag is, wacht op B7.
- De groepeerversie wordt opgehoogd.
- Meting op Termijnen: per klasse het aandeel elementen met een voorstel, en de precisie van "koppel aan …"
  (jurist-oordeel). Daarna één blinde run op een tweede werkgebied.

**B5 · Operatorbegrippen bij een formulering, generiek hergebruikt** (skill, api, keten). *Bijgesteld 19 nov 2026
naar de methode, zie `plan-lessen-e2e-termijnen.md` §0 en M-3a-1. De eerste versie zette de operatoren vooraf als
geaccordeerde begrippen in het generieke kader, zonder passage. Dat doet de methode niet.*

- Een operatorbegrip ontstaat bij een **gemarkeerde operatorformulering**, net als elk ander begrip. Daarna wordt het
  hergebruikt voor elke formulering met dezelfde betekenis. Zo maakt het boek *plus* bij "het gezamenlijke bedrag van"
  en hergebruikt het bij "vermeerderd met" (M01 h.3 stap 3b, h.6).
- In de skill komt een vaste lijst (`operatoren.json`): en, of, niet, plus, min, maal, gedeeld door, groter dan, kleiner
  dan, gelijk aan, ten minste, ten hoogste. Elke operator krijgt een omschrijving in eigen woorden en de
  uitdrukkingswijzen uit M04 H2 *Operator* (W3C-licentie) en M01 h.4 punt 11.
  - De lijst is een **voorstel**: de naam en omschrijving die de keten voorstelt bij een formulering. Het zijn geen
    begrippen vooraf.
- Bij de eerste formulering in een werkgebied maakt de jurist (of Lex als voorstel) het begrip, met die passage. Het
  begrip wordt generiek (ADR-006). Elk volgend werkgebied koppelt zijn eigen passage aan hetzelfde generieke begrip.
  Zo houdt ook een operator zich aan "geen begrip zonder grondslag" (#1760).
- De keten koppelt een gemarkeerde operator via de uitdrukkingstabel aan het generieke begrip als dat er al is, of
  stelt het nieuwe begrip voor met de naam uit de lijst. Bij twijfel geel. Het filter dat operatoren niet op
  woordgelijkheid groepeert, blijft.
- **Datumrekenen** ("zes weken na", "telkens een maand later") is volgens de methode geen operator maar een
  Tijdsaanduiding (M04 H2, de meest specifieke klasse gaat voor). Die krijgt een eigen begrip. Hoe de afleidingsregel
  de bewerking opschrijft, hoort bij het ontwerp van de regel (`plan-afleidingsregels-in-lex.md`), niet bij B5.
- Het taalpatroon van een regel ("moet berekend worden als", "is", "indien aan alle volgende voorwaarden is voldaan") is
  geen begrip (M02 §3.5.2b).

**B6 · Beperkte termen en specialisaties** (keten).

- "De belastingschuldige die een onderneming drijft" wordt een groep van één met de volledige term als naam, en een
  relatievoorstel *soort van* naar het begrip van de kale term (M01 h.6: "specialisatie van"; M02 §3.5.2a, *Begripsnaam*:
  een aspect dat de betekenis verandert, geeft een nieuw begrip).

### Fase 3 — besluit en modelstap

**B7 · Namen voor zinsvormen** (begrippen-agent, een strikte modelstap; vraagt een meting volgens ADR-010).

- Een naamvoorstel voor:
  - een rechtsbetrekking ("verschuldigdheid …", "bevoegdheid … tot …");
  - een rechtsfeit ("indienen …");
  - een delegatiebevoegdheid;
  - een parameterwaarde ("… in tijdvak").
- Een omschrijving "indien …" voor een voorwaarde.
- De afleidingsregel ("bepalen <uitvoer>") neemt de uitvoer uit het skelet (ADR-011) en is dus deterministisch waar het
  skelet er is. Dit is A2 van het plan afleidingsregels; ik bouw het hier één keer.
- Toetsen in code: werkwoord vooraan bij rechtsfeit en afleidingsregel, geen ontkenning, geen lidwoord vooraan
  (M02 §3.5.2a).

**B8 · Klasse en samenhang op het begrip (heroverweging van P15)** (api, projectie, kaart).

- De klasse wordt *afgeleid* uit de dragende markeringen, niet ingevoerd. Ze staat op de kaart, en in de Turtle als
  relatie naar het JAS-topbegrip uit M04 H3.
- Bij een rechtsbetrekking: rechtkant, plichtkant en voorwerp als relatie naar begrippen, afgeleid uit de ADR-011-rollen
  van de gekoppelde markeringen.
- De soort (bedrag, datum, …) wordt een optioneel veld, gedeeld met D5 van het plan afleidingsregels.
- Dit wijzigt het besluit van 13 nov 2026 (P15) en vraagt jouw besluit. De bron (M01 h.6, M04 H3) pleit ervoor.

## 3. Volgorde, bundels en meten

- **Bundel 1**: B1 + B2 + B3. Geen gedragswijziging van Lex. Op acceptatie toon ik de nieuwe dekking van Termijnen als
  nulmeting.
- **Bundel 2**: B4. Meten, één run (licht regime), dan pas verder.
- **Bundel 3**: B5 + B6. Meten.
- B7 en B8 na een besluit. Of ze vóór of na de afleidingsregels komen, stem ik af met plan-afleidingsregels.
- Elke fix is generiek. Termijnen is ontwikkelset; het tweede werkgebied wordt blind gemeten.

## 4. Wat ik bewust niet doe

- Geen begrip voor een voorwaarde (M01 h.6–7).
- Geen automatische uitsluiting op klasse. "Geen begrip" blijft een besluit van de jurist.
- Geen groepering van functiewoorden op woordgelijkheid.
- Aan de annotatieketen verandert niets. Een losse markering wordt gesignaleerd, niet verwijderd.
