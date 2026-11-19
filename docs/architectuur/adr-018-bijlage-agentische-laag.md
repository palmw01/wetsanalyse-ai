# ADR-018, bijlage A: de agentische laag voor afleidingsregels

- **Status**: voorstel, ter goedkeuring. De eerste versie is van 19 nov 2026. Deze versie is herschreven na de review van
  de hoofdsessie (19 nov 2026), op verzoek van de gebruiker.
- **Hoort bij**: [ADR-018](adr-018-afleidingsregels.md) en het bouwplan in
  [plan-afleidingsregels-in-lex.md](plan-afleidingsregels-in-lex.md) §13, stappen R5 en R6.
- **Wat er al is**:
  - R1, de regel als object in de api (#1768);
  - R2, de regelkaart, de keten en het overzicht (#1770).

  Daarmee stelt de jurist regels op en beoordeelt hij ze. Lex doet in 3b nog niets (L-3b-3).
- **Wat hier staat**: hoe Lex meedoet. De eisen van de gebruiker zijn:
  - robuust, generiek en toekomstbestendig;
  - passend bij de centrale agent met subagents en zo min mogelijk vaste routes (ADR-016);
  - passend bij de inrichting van *Aanpassingen* (Methodes, Agents, Connectors en Modellen) en bij de werkplek;
  - steeds getoetst aan de methode (`references/afleidingsregels.md`).
- **Hold**: tot het akkoord wordt er niets van R3 en verder gebouwd, en niets van R5 of R6.

## 1. Uitgangspunten

- **De AI stelt voor, de jurist beslist.**
  - Lex maakt een regel, een voorbeeld, een open punt of de onderbouwing van een lezing hoogstens als voorstel.
  - Accorderen, afwijzen, een drager beoordelen, een lezing kiezen en verwijderen doet de jurist.
  - De api weigert het agent-token op elke beslissingsroute (`agent_toegang`, ADR-016 §A5).
- **Lex kiest geen interpretatie.** Laat de tekst ruimte, dan legt Lex de lezingen voor, met hun grondslag en wat nog
  getoetst moet worden. De keuze, de methode ervan en de reden komen van de jurist (M-3b-2, L-X-1).
- **Code eerst, model waar het moet** (ADR-005, ADR-010).
  - Inventariseren, toetsen en een conceptregel opbouwen gebeurt in code.
  - Een model doet een smalle, strikte stap met de fragmenten waarop het voorstel rust, en pas na een meting (R6).
  - Zoeken in bronnen naast de wet is werk voor subagents met hun eigen profiel (R6b).
- **Niet strenger dan de methode** (M-3b-0). De agent wijst niets af wat de methode toelaat. Een gat is een signaal,
  geen afwijzing.
- **Generiek.**
  - Geen toets, tool of tekst voor Termijnen of een ander werkgebied. Termijnen is de meetset, niet het ontwerp.
  - Elk patroon één keer: één stand per werkgebied, één besluitroute, één vorm voor een voorstel.
- **De skill is de bron.** Wat de agent toetst en vraagt, staat in `afleidingsregels.md` en wordt daaruit gegenereerd,
  zoals de relatiecatalogus en de begripverwachting.

## 2. De regels-agent

### 2.1 Een taakagent, geen profiel

- **Plek**: `tools/graph-qa/agent/agents/regels.py`, in de vorm van de begrippen-agent (ADR-005):
  - een `Taak`-enum met `MODEL_TAKEN` en `DOEL`, en een `voer_uit` per taak;
  - in `agents/register.py`: `AGENTS["regels"]` en `NAAM["regels"] = "regels-agent"`;
  - in `overdracht.TAAKAGENTS`, zodat de centrale agent een taak geeft met de bestaande tool `taakagent`.
- **Geen profiel in `.claude/lex-agents/`.** Een profiel hoort bij een agent met een model en een toollus: de centrale
  agent, een subagent of de stap van een leesroute. Een taakagent draait in code. Op master heeft geen taakagent een
  profiel (deelvragen, begrippen, annotatie). De catalogus haalt de soort `agent` uit `DOEL`, en daarmee staat de
  regels-agent onder *Aanpassingen › Agents*.
- **Lezen komt met R7, als profiel.** `regels_lezen` (`kiesbaar: false`, methoderol `algemeen`) is de stap van de route
  `lees_regels`, net als `begrippen_lezen` bij `lees_begrippen`. `centraal.md` krijgt onder VASTE ROUTES de regel
  "welke afleidingsregels er al zijn → lees_regels".

### 2.2 De taken

Per taak staat erbij of het code of een model is.

- **`inventariseren`** (code): van de analysevraag en de deelvragen terug naar de uitvoer die nodig is. De taak kijkt
  verder dan de markeringen van de klasse Afleidingsregel (§4.1). Volgens de methode rust een regel ook op:
  - een Rechtsbetrekking met haar voorwaarden, voor een beslisregel over een recht, plicht of bevoegdheid;
  - een Tijdsaanduiding die een tijdstip afleidt;
  - elk geclassificeerd begrip waarvoor een afleiding aan de orde is.

  Het resultaat is de lijst van uitvoeren die een regel nodig hebben, met de keten. Die opent als artefact `regels`.
- **`volledigheidstoets`** (code): de gaten uit de skill (§4.2), per regel of skelet, elk met de plek waar het zit.
- **`opstellen`** (code): één conceptregel uit het skelet en de begrippen.
  - Uit het skelet komen de soort (uit de klasse van de drager), de invoer op volgorde, de gevallen uit de voorwaarden en
    de grondslag.
  - De relaties worden ook over bepalingen heen gevolgd, binnen het werkgebied (§4.4).
  - Het taalpatroon komt van de api (`regeltekst.py`).
  - Is de soort onzeker, dan stelt de taak de waarschijnlijkste voor en zegt ze waarom. Een geval zonder label krijgt een
    volgnummer.
- **`uitsluiting_toetsen`** (code): leiden twee of meer regels dezelfde uitvoer af, dan toetst de taak of hun gevallen
  elkaar uitsluiten (M-3b-1). Dat gebeurt op de voorwaardenboom: dezelfde markering, of dezelfde voorwaarde met `niet`.
  Kan de code het niet vaststellen, dan wordt het een open punt, geen oordeel.
- **`voorbeelden`** (code): per geval de invoer die het geval raakt:
  - normaal;
  - elke voorwaarde niet vervuld;
  - de grens van elke vergelijking;
  - nul, negatief en onbekend.

  De uitkomst rekent de taak alleen uit bij een rekenregel met bekende waarden. Het oordeel staat altijd op `open`.
- **`keuzes_signaleren`** (model, R6): een passage die meer dan één lezing toelaat. De taak legt een open punt met de
  lezingen, de fragmenten waarop elke lezing rust en wat nog getoetst moet worden. Ze kiest niet.
- **`lezingen_onderbouwen`** (subagents, R6b): zie §2.4.

### 2.3 Hoe de regels-agent zich verhoudt tot de rest (ADR-016)

- **De centrale agent** beantwoordt een gewone vraag zelf. Een vraag over regels die er al liggen, is lezen: tot R7 uit
  de context van het werkgebied (§5.5), daarna via `lees_regels`.
- **Een taak start in code of met `taakagent`.**
  - Een suggestie, commando of fase-knop met een `actie` kiest de taak in code, zonder modelstap (`ACTIE_TAAK`).
  - Een getypte opdracht ("stel de regels op") geeft de centrale agent met de tool `taakagent` aan de regels-agent.
  - Er is geen eigen route naast de route van de taakagents.
- **Opstellen is nooit werk van een subagent.** Opstellen is een keten in code; ADR-016 §A5 zegt dat een agent het
  werk van een keten nooit zelf nadoet.
- **Subagents doen het zoekwerk waar de methode om vraagt**: de lezingen van een open punt onderbouwen uit bronnen naast
  de wet (§2.4).
- **3b is een fase van "werk dit werkgebied uit"** (§5.1). De regisseur verdeelt bronnen en annoteren per deelvraag
  (ADR-012). Regels horen bij het werkgebied en de keten loopt over de deelvragen heen, dus 3b is één fase voor het hele
  werkgebied, niet een regie per regel.
- **De begrippen-agent maakt het begrip.** De regels-agent maakt nooit zelf een begrip. Ontbreekt een begrip, dan vraagt
  hij de begrippen-agent om een voorstel op de passage. Dat geldt voor een regelbegrip ("bepalen <uitvoer>") en voor een
  tussenresultaat; het tussenresultaat rust op de Afleidingsregel, met de koppelrol `afgeleid` (#1760). Tot het begrip
  er is, staat de regel niet in de poort (ADR-018 besluit 2).

### 2.4 Subagents: de lezingen van een open punt onderbouwen (R6b)

- **Waarom**: de methode vraagt bij een open punt de lezingen met hun grondslag, en wat nog getoetst moet worden
  (bijvoorbeeld de memorie van toelichting of de jurisprudentie). Dat is zoekwerk dat:
  - naast elkaar kan lopen;
  - over verschillende bronnen gaat;
  - een rapport oplevert, en vragen.

  Daar zijn subagents voor.
- **Hoe, met wat er al is**:
  - Het plan volgt uit het open punt, in code: elk item van `te_toetsen` met zijn bronsoort wijst een kiesbaar profiel
    aan. Wetsgeschiedenis gaat naar `wetsgeschiedenis_lezen` (Kamerstukken, Bekendmakingen), jurisprudentie naar
    `rechtspraak_lezen` (Rechtspraak). Kennisgroepen gaat naar `algemeen` met die connector.
  - Het is een delegatie met een plan uit code, zoals de regie (ADR-016 §A5). Het loopt dus niet via een vrij
    samengestelde opdracht van het model.
  - Vóór de start staat er een bevestigingskaart met het plan, de profielen, de schatting en het plafond (§7.3).
  - Elke subagent werkt met zijn eigen profiel, tools en connectors. Zijn rapport is een toolresultaat en gaat door het
    bronregister en `verify`.
- **Wat het oplevert**:
  - Per lezing de onderbouwing met fragmenten. Die komt op het open punt te staan als voorstel van Lex.
  - Een vraag van een subagent komt als keuzekaart (ADR-016 §A4) bij de jurist.
  - `te_toetsen` krijgt per item de stand "nagelopen", met de bron, of "niets gevonden".
- **Lex kiest nog steeds niet.** Het rapport onderbouwt elke lezing apart, en de jurist kiest.

## 3. De tools

Een tool is hier een functie van de regels-agent in code. Per tool staan:
- het contract;
- of hij leest of schrijft;
- wat een voorstel is en wat vastleggen;
- de plek in `agent_toegang`;
- de grenzen;
- of hij hergebruikt is of nieuw.

In de open laag (de toollijst van een profiel) komt alleen het lezen, en pas met R7.

### 3.1 Lezen

- **`skelet_lezen`** (hergebruikt, #1769)
  - Contract: in gaat een `bron_iri` of een werkgebied. Uit komt per regeldrager zijn skelet (`regelskelet.opbouw`) en
    wat het mist (`regelskelet.gaten`).
  - Api: `GET /v1/annotatie/weergave?vorm=skelet`. Die staat al in `TOEGESTAAN`.
  - Grens: het skelet zegt iets over de vorm, niet over de inhoud. De agent rekent het skelet nooit zelf opnieuw uit.
- **`regels_lezen`** (nieuw)
  - Contract: de regels van het werkgebied met regeltekst, poort en signalen, en de keten (`hierarchie`).
  - Api: `GET …/regels`, `…/regels/hierarchie` en `…/regels/{}`. Die komen nieuw in `TOEGESTAAN`.
- **`begrippen_lezen`** (hergebruikt): de bestaande leesroutes van de begrippen. Daar komt niets bij.
- **`open_punten_lezen`** (nieuw, met het object van lessenbundel 4)
  - Contract: de open punten van het werkgebied (`hangt_aan` met regel en geval), met status, lezingen, gekozen lezing en
    `te_toetsen`.
  - Api: de leesroute van het open-puntobject. Die komt nieuw in `TOEGESTAAN`.
  - Grens: een gekozen lezing is een gegeven voor de volgende regel, geen voorstel.

### 3.2 Voorstellen

- **`regel_voorstellen`** (nieuw)
  - Contract: in gaan `RegelAanmaak` met `herkomst: "lex"` en de dragers. Uit komt de regel met status `concept`.
  - Wat het is: een voorstel. Op de regelkaart staat het als `Voorstel` (geel, met de tekst "Voorstel van Lex").
    Alleen de jurist accordeert hem.
  - Api: `POST …/regels`, nieuw in `TOEGESTAAN`, begrensd:
    - alleen met `herkomst: "lex"`;
    - alleen op dragers in het werkgebied;
    - de grondslag blijft verplicht (422);
    - hoogstens één nieuwe regel per uitvoer per beurt.
  - Een eigen concept aanvullen (`PATCH`, `POST …/dragers`) mag alleen zolang niemand anders het wijzigde. De api toetst
    dat op de laatste actor; anders volgt 403.
  - Grens: nooit `accorderen`, `heropenen`, `afwijzen`, `DELETE` of het beoordelen van een drager. Die staan in
    `BESLISSINGEN` (`tests/poort/test_agent_toegang.py`).
- **`veld_voorstellen`** (nieuw, na R5)
  - Wat het is: een voorstel per veld op een regel van de jurist, in de vorm van de kaartvoorstellen van een begrip
    (overnemen, aanpassen of afwijzen).
  - Dit is ook de weg voor voorbeelden bij een regel die niet van Lex is.
- **`open_punt_leggen`** (nieuw)
  - Contract: het object van lessenbundel 4. Het heeft:
    - een soort (§4.3);
    - `hangt_aan`: regel, geval, markering, begrip of deelvraag;
    - de passage;
    - de lezingen met hun fragmenten;
    - `te_toetsen` met de bronsoort;
    - de status `open`.
  - Wat het is: een voorstel. De jurist kiest met methode en reden (§5.3).
  - Api: `POST` op het open-puntobject, nieuw in `TOEGESTAAN`. Het besluit (`…/besluit`) staat er nooit in.
- **`onderbouwing_leggen`** (nieuw, R6b): het rapport van de subagents per lezing op het open punt, met fragmenten. Het is
  een voorstel; de lezing zelf verandert niet.

### 3.3 Toetsen

- **`volledigheidstoets`** (in de api, als uitbreiding van `regelskelet.gaten`; geen tweede berekening)
  - Contract: in gaat een regel of skelet. Uit komen gaten met een code uit de skill (§4.2) en de plek.
  - Lezen. De werkplek toont dezelfde gaten als signaal op de regelkaart, dus agent en jurist zien één toets.
  - Api: in `GET weergave?vorm=skelet` en als `signalen` op de regel.
- **`uitsluiting_toetsen`** (in de api, als uitbreiding van `regel_store.keten`)
  - Contract: het signaal `zelfde_uitvoer` krijgt een uitkomst. Die is "sluiten uit", "sluiten niet uit" (met het paar
    gevallen) of "niet vast te stellen".

### 3.4 Wat hergebruikt is en wat nieuw

- **Hergebruikt**:
  - het skelet (`regelskelet.py`, #1769);
  - de regeltekst en de keten (R1);
  - de regelkaart en de artefacten `regel` en `regels` (R2);
  - de begrippenroutes;
  - het open-puntobject met zijn besluitroute (lessenbundel 4);
  - `taakagent`, `subagent`, de delegatie en de keuzekaart (ADR-016);
  - de kiesbare profielen en connectors;
  - `llm_stap.Rol` en de modelkeuze per stap (#1542, #1550);
  - de catalogus (ADR-014).
- **Nieuw**:
  - de taakagent `regels`;
  - de tools `regels_lezen`, `regel_voorstellen`, `veld_voorstellen`, `open_punt_leggen`, `open_punten_lezen` en
    `onderbouwing_leggen`;
  - de twee toetsen;
  - de generieke `werkvoortgang` (§5.4);
  - de rollen van §6.1;
  - de regels in `TOEGESTAAN`.

## 4. De methode (3b), getoetst aan de skill

### 4.1 Waarop een regel rust

- De inventaris volgt `afleidingsregels.md` ("Waarop een regel rust"), niet alleen de Afleidingsregel-markeringen.
- Zonder de Rechtsbetrekking met haar voorwaarden mist Lex precies de beslisregels "bepalen recht op …".
- De meting telt de drie soorten dragers als aparte categorie (§7):
  - de Afleidingsregel;
  - de Rechtsbetrekking met voorwaarden;
  - de Tijdsaanduiding en het geclassificeerde begrip.

### 4.2 De gaten komen uit de skill

- `afleidingsregels.md` krijgt een lijst gaten, elk met een code. Een generator maakt er een bestand van voor api en
  graph-qa, zoals `relaties.json` en `begripverwachting.json`. Een drifttest in de poort bewaakt dat code en skill gelijk
  zijn.
- De lijst bevat die van de regelspecialist (L-3b-3):
  - uitvoer zonder begrip;
  - invoer zonder volgorde;
  - een rechtsobject als invoer;
  - een voorwaarde aan de verkeerde drager;
  - geen `uitzondering_op` bij "In afwijking van";
  - twee regels met dezelfde uitvoer zonder voorwaarden die elkaar uitsluiten;
  - een parameter zonder tijdvak.
- Daarbij komen de gaten die de methode noemt en de regelspecialist niet:
  - een regel zonder regelbegrip "bepalen <uitvoer>";
  - een regel die rust op een bron met rol *context*, met het signaal "wordt dit een bron om te analyseren?";
  - een formulering met twee uitvoeren die maar één regel draagt;
  - een operatorformulering zonder operatorbegrip, of twee operatorbegrippen met dezelfde betekenis (hergebruik);
  - een parameterbegrip met een waarde in de definitie, of een parameterwaarde zonder tijdvak;
  - een invoer die de tekst niet noemt en die ook elders niet te vinden is: een impliciete invoer, met het signaal
    "ontbrekend uitvoeringsbeleid".
- Zo blijft de methode de bron, en is een volgend werkgebied meteen gedekt. De checklist van de regelspecialist (#1758)
  blijft het referentiepunt van de meting.

### 4.3 Vier soorten open punt, met wat nog getoetst moet worden

- De skill kent vier soorten:
  - interpretatiekeuze;
  - ontbrekend uitvoeringsbeleid;
  - onderzoekspunt;
  - gat in de annotatie.
- Daarbij hoort `te_toetsen`: wat nog getoetst moet worden, met een bronsoort (bijvoorbeeld de memorie van toelichting of
  de jurisprudentie). Dat veld voedt de onderbouwing van §2.4.
- Lessenbundel 4 bouwt het object met precies deze vorm. De bijlage legt geen tweede vorm vast.

### 4.4 Over bepalingen heen

- Een eindpunt van een relatie mag in een andere bepaling liggen (de skill). `opstellen` volgt de relaties daarom over
  bepalingen heen, binnen het werkgebied.
- Een eindpunt buiten de geannoteerde bronnen wordt een signaal ("deze invoer staat in een bepaling die niet is
  geannoteerd"), geen invoer.

### 4.5 Wat de lessen meegeven

- **#1758, de regelspecialist** (`.claude/agents/agent-regelspecialist.md`): zijn checklist gaat in de skill (§4.2) en
  wordt daaruit een toets in code. De specialist blijft het referentiepunt.
- **#1762, de regels R1–R8 van Termijnen**: de ontwikkelset, al vast in R1 (`test_regels_termijnen.py`). Het is geen
  held-out set.
- **#1764, de lessen**:
  - L-3b-1 is opgelost met R1, L-3b-2 met #1769, en L-3b-3 met deze bijlage;
  - M-3b-0 is een uitgangspunt (§1);
  - M-3b-1 is `uitsluiting_toetsen`;
  - M-3b-2 en L-X-1 zijn het open punt van lessenbundel 4, met `open_punt_leggen`.

## 5. De route, het besluit en de stand

### 5.1 3b als fase van "werk dit werkgebied uit"

- "Werk dit werkgebied uit" is al een plan in fasen met de jurist ertussen (`regie_plan` met `uitwerken`, ADR-016 §A4 en
  §A5). Elke fase eindigt waar de jurist beslist.
- 3b is de fase na de begrippen. De poort naar die fase is ADR-018 besluit 2: de begrippen waarop de regels rusten zijn
  beoordeeld, en de keuzes die een regel nodig heeft zijn genomen.
- Onder de bundel van de begrippenfase staat de knop voor de volgende fase (`volgende_fase`). Die kiest de actie
  `regels_inventariseren` in code, met nul tokens.
- Wie het werkgebied in het gesprek uitwerkt zonder knop, krijgt dezelfde taak via de centrale agent en `taakagent`.
- `delegatie_stand` en de bundel tonen de stand van de regels uit de `werkvoortgang` (§5.4).

### 5.2 Regel voor regel

- Binnen de fase werkt de agent regel voor regel, zoals de bronselectie per deelvraag (spoor J). De code kiest de
  volgende regel uit de stand bij de api. Zij volgt de keten van onder naar boven, zodat een regel pas aan de beurt is als
  zijn invoer er is.
- Per regel verschijnt een compact kaartje in het gesprek (`PaneelChip`, soort `regel`). Het verwijst naar het paneel,
  waar de jurist leest en beslist met dezelfde regelkaart als op de pagina.
- Een tussenvraag, herladen of een ander gesprek breekt niets, want de stand staat niet in het gesprek.

### 5.3 Eén besluitroute, twee plekken om haar te bedienen

- **Het besluit hoort bij het artefact.** Een open punt staat op de regelkaart, bij zijn regel en geval. Daar kiest de
  jurist een lezing, met methode en reden. Dat is het artefactmodel: op een artefact lees, bewerk en besluit je.
- **In het gesprek staat de keuzekaart van ADR-016 §A4** (met `beantwoord_kaart`). Haar klik schrijft naar dezelfde
  route van de jurist. Er komt geen nieuwe modus van de vraagkaart.
- **Er is één route**: de besluitroute van het open-puntobject (lessenbundel 4). Die draagt het userid en gebruikt nooit
  het agent-token.
- Een volgende regel leest de gekozen lezing als gegeven (`open_punten_lezen`, en de context van §5.5).

### 5.4 Eén stand: `werkvoortgang`

- **Generiek**: één `werkvoortgang` per werkgebied, met:
  - een soort (`regels`, en later `bronselectie`);
  - een onderwerp (de uitvoer, of de deelvraag);
  - een stand;
  - wie de stand zette, en wanneer.
- De standen zijn voor elke soort gelijk:
  - niet gestart;
  - in behandeling;
  - voorlopig af;
  - beoordeeld;
  - opnieuw bekijken.
- *Beoordeeld* wordt afgeleid uit het besluit van de jurist. Bij een regel is dat accorderen.
- **Regels is de eerste gebruiker.** De bronselectie (`bronselectie_voortgang`) verhuist later, in een eigen PR, met een
  test die elke soort langs dezelfde standen laat lopen. Die migratie komt in PLAN.md.
- De agent zet *in behandeling* en *voorlopig af* via een stap-route in `TOEGESTAAN`.
- In de werkplek staat de stand als `StatusLabel` per uitvoer in de keten (het artefact `regels`).

### 5.5 De regels in de context van het werkgebied

- `werkgebied_context.py` geeft nu naam, dossier, deelvragen en bronnen mee. Daar komt een compact blok bij: per uitvoer
  de soort, de status en de genomen keuzes, met een plafond in tekens.
- Zo beantwoordt de centrale agent een vervolgvraag ("waarom heeft deze regel twee gevallen?") zonder extra ronde.
- Volgens ADR-015 staat dat blok in de context van de beurt, na de historie, en buiten het vaste voorvoegsel.

### 5.6 Catalogus, commando's en routering

- **De catalogus** (ADR-014) krijgt:
  - de agent `regels`, uit `DOEL`;
  - een workflow `regels` met zijn stappen (`_wf`), de routes en de tools.

  *Aanpassingen › Agents* en *Methodes* tonen dan wat 3b doet, met de methoderol.
- **Commando's**: per vaste handeling een `/`-commando met dezelfde actie als de suggestie (`SUGGESTIES`, frontend
  §Commando's). Bijvoorbeeld:
  - bij het werkgebied: "Welke afleidingsregels zijn er nodig?" en "Toets de keten";
  - bij een regel: "Vul deze regel aan", "Stel voorbeelden voor" en "Toets deze regel".
- **Routering** (ADR-010): de nieuwe acties en de getypte opdrachten komen in de routeringsset (`golden_routering.jsonl`
  en `golden_routering_centraal.jsonl`). Een klik blijft dan nul tokens kosten, en een regressie wordt rood.

## 6. De modelstappen in *Aanpassingen*

### 6.1 Elke modelstap is een `llm_stap.Rol`

- Elke modelstap van 3b wordt een `Rol` met naam, methoderol en `lus`:
  - `Rol.REGEL_KEUZES = ("regel_keuzes", "regels", False)`;
  - later `REGEL_SOORT` en `REGEL_VOORBEELD`.
- Ze staan dan vanzelf onder *Aanpassingen › Agents*, bij "Stappen zonder agentprofiel". De beheerder kiest daar het
  model (`stap:<rol>`), de contextweergave telt ze als losse stap, en het verbruik is per stap te zien.
- De test op de lijst van stappen ziet elke nieuwe rol. Een modelstap zonder rol faalt.
- De subagents van §2.4 gebruiken hun eigen profiel, met het model dat bij dat profiel gekozen is. Er komt geen eigen
  rol voor.

### 6.2 Een methoderol `regels`

- `references/agentrollen.md` krijgt een sectie `regels` tussen de methodemarkers, en `agentrollen.json` koppelt de rol
  eraan. De tekst is kort en verwijst naar `afleidingsregels.md`. Hij noemt:
  - de taalpatronen;
  - één regel per uitvoer;
  - de grondslag;
  - geen interpretatie kiezen;
  - niet strenger dan de methode.
- De tekst tussen de methodemarkers stuurt het gedrag, dus een wijziging vraagt een meting (ADR-010, P19). In R5 gebruikt
  alleen de code de rol; met R6 krijgt de modelstap hem mee, en dan wordt hij gemeten.
- De gegenereerde bestanden volgen vanzelf, via `genereer_jas_klassen.py`, met `--check` in CI:
  - het methodepakket;
  - het bronpakket;
  - de gaten (§4.2).
- De scheiding met wetsuitvoering blijft (`test_methodes_gescheiden.py`).

## 7. Meten en robuustheid

Licht meten: één run, een gerichte set en de geraakte vorm. Drie runs alleen bij twijfel.

### 7.1 Wat, en in welke volgorde

- **R5, zonder model**:
  - `inventariseren`: recall per soort drager (§4.1) op Termijnen;
  - `opstellen`: de velden tegen R1–R8 van Termijnen (soort, uitvoer, invoer op volgorde, aantal gevallen, grondslag),
    met recall en precisie per veld;
  - `volledigheidstoets`: de gaten op het skelet van Termijnen van vóór het herstel, tegen de gaten van de
    regelspecialist in het logboek van de proef;
  - `uitsluiting_toetsen`: R2, R3 en R4 (dezelfde uitvoer), en een kring.
- **R6, de eerste modelstap**: `keuzes_signaleren`, met de negen interpretatiekeuzes en zes punten beleid van Termijnen
  als set. Daarna de soort bij twijfel. Het label van een geval komt het laatst.
- **R6b, de subagents**: zijn de lezingen terecht en elk met een fragment onderbouwd? Is `te_toetsen` nagelopen? Wat kost
  het, als delta van het verbruik?
- **Blind**: WA TRM H1, en een werkgebied met een reken- en een beslisregel dat niemand eerder zag.

### 7.2 Vastgelegd, zodat het niet ad hoc ontstaat

- Een regressie wordt rood in de routeringsset en in de golden set van de centrale agent (ADR-016 §A6).
- **Lex Bench**: 3b komt in `plan-lex-bench.md` als volgende arm, met een blind team tegen Lex. Bouwen hoeft nu niet;
  vastleggen wel.
- De drempels gelden per soort regel (reken, beslis, specialisatie), niet per werkgebied.

### 7.3 Kosten en plafond

- Een regel opstellen zonder model kost nul tokens.
- Een modelstap kost hoogstens enkele duizenden tokens per regel.
- Subagents zijn duur, ongeveer vijftien keer een chat. Daarom:
  - hoogstens `N` subagents per open punt (voorstel: één per bronsoort in `te_toetsen`, hoogstens drie);
  - een bevestigingskaart vóór de start, met het plafond van de opdracht (ADR-016 §A5);
  - een aparte meting van wat het kost.

### 7.4 Goed genoeg (voorstel)

- De opbouw: recall ≥ 0,9 per veld op de ontwikkelset, en ≥ 0,8 blind.
- De inventaris: recall ≥ 0,9 per soort drager.
- De volledigheidstoets: recall 1,0 op de gaten van de regelspecialist, met precisie ≥ 0,8.
- Het signaleren van keuzes: recall ≥ 0,8, met elk signaal op een fragment, en nul gekozen lezingen.
- De onderbouwing: elke lezing met minstens één fragment uit een bron in het bronregister, en nul gekozen lezingen.
- Haalt een stap het niet, dan blijft hij uit. De regel van de jurist werkt zonder.

## 8. De werkplek

- **Een voorstel van Lex** op de regelkaart is het bestaande `Voorstel` (geel, met tekst). Een voorstel per veld op een
  regel van de jurist hergebruikt `KaartVoorstelKaart`. Overnemen, aanpassen en afwijzen hebben zo één vorm in heel Lex.
- **De onderbouwing per lezing** staat bij het open punt, opklapbaar, met de fragmenten, in de vorm van
  `DefinitieOnderbouwing`.
- **De stand per regel** staat in de keten als `StatusLabel`, met de toon uit het register.
- **Het denkproces** toont een taak van de regels-agent zoals die van de begrippen-agent: een spoorregel per bron
  (`spoorbronnen`), zonder tellingen die niets zeggen.
- **Mobiel**: de keten, de regelkaart met het open punt en de beslistabel krijgen een browsertest op 390 px.

## 9. Volgorde

- Eerst lessenbundel 4: het open-puntobject met zijn besluitroute.
- R3 (de open punten op de regelkaart) komt daarna.
- R4 (Termijnen importeren) vraagt een akkoord op het moment van uitvoeren, via de hoofdsessie.
- R5 (de regels-agent zonder model, `werkvoortgang`, de toetsen uit de skill) komt na lessenbundel 3 (een betrouwbaar
  skelet) en R4.
- R6 (`keuzes_signaleren`, daarna de soort) komt na de meting van R5.
- R6b (de onderbouwing door subagents) komt na de meting van R6.
- R7: de leesroute `lees_regels`, het rapport en de projectie.
- Wat zonder de agent al waarde heeft, kan eerder: de gaten uit de skill en de uitsluitingstoets in de api, als signaal
  op de regelkaart.

## 10. Keuzes voor de gebruiker

Elke keuze heeft een voorstel. Na het akkoord gaan ze als besluiten in ADR-018.

1. **Hoe landt een regel van Lex?**
   - Voorstel: als conceptregel met `herkomst: "lex"`, als `Voorstel` op de kaart. Er is één object en één kaart, de poort
     en de revisies werken meteen, en accorderen blijft bij de jurist.
2. **Mag Lex een regel wijzigen?**
   - Voorstel: alleen een eigen concept dat nog niemand anders wijzigde. Bij elke andere regel stelt Lex per veld voor
     (`KaartVoorstelKaart`); dat komt na R5.
3. **Profiel of taakagent?**
   - Voorstel: geen profiel voor de regels-agent. Het is een taakagent in het register en in `TAAKAGENTS`, via
     `taakagent`. Een leesprofiel `regels_lezen` (niet kiesbaar) komt met R7, met `lees_regels` onder VASTE ROUTES.
4. **Regie per regel of één fase?**
   - Voorstel: 3b is één fase van "werk dit werkgebied uit", regel voor regel, zonder subagents voor het opstellen.
5. **Een eigen methoderol `regels`?**
   - Voorstel: ja, met een korte tekst die naar `afleidingsregels.md` verwijst. Elke modelstap is een `llm_stap.Rol` met
     die methoderol, zichtbaar en te kiezen onder *Aanpassingen › Agents*. Er wordt gemeten zodra een model hem krijgt.
6. **Waar staat de volledigheidstoets?**
   - Voorstel: in de api, als uitbreiding van `regelskelet.gaten`, met de gaten uit de skill (gegenereerd, met een
     drifttest).
7. **Welke modelstap eerst?**
   - Voorstel: het signaleren van interpretatiekeuzes. Daar zat in Termijnen het meeste handwerk, en de stap kiest niets.
8. **Hoe ver gaan voorbeelden van Lex?**
   - Voorstel: de invoer per geval altijd, de uitkomst alleen bij een rekenregel met bekende waarden, en het oordeel
     altijd `open`.
9. **Een ontbrekend begrip?**
   - Voorstel: de regels-agent vraagt de begrippen-agent om een voorstel op de passage. Dat geldt voor een regelbegrip
     "bepalen <uitvoer>" en voor een tussenresultaat (met `afgeleid`). De regel wacht in de poort tot het begrip er is.
10. **Wat is goed genoeg?**
    - Voorstel: de drempels van §7.4. Eerst de ontwikkelset, dan blind. Haalt een stap het niet, dan blijft hij uit.
11. **Subagents om de lezingen bij een open punt te onderbouwen?**
    - Voorstel: ja, als R6b, na de meting van R6. Het plan komt uit `te_toetsen` (code). Er is een bevestigingskaart en
      een plafond van hoogstens drie per open punt. Het rapport staat per lezing bij het open punt, en Lex kiest niets.
12. **Een generieke `werkvoortgang`, of eerst een eigen tabel?**
    - Voorstel: meteen generiek, met regels als eerste gebruiker. De bronselectie verhuist later in een eigen PR, en die
      migratie komt in PLAN.md.
13. **Waar besluit de jurist?**
    - Voorstel: op het artefact (het open punt op de regelkaart). In het gesprek staat de keuzekaart van ADR-016 §A4.
      Beide schrijven naar de ene besluitroute van het open-puntobject. Er komt geen nieuwe modus van de vraagkaart.
