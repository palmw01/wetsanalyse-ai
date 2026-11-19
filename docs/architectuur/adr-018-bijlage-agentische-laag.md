# ADR-018, bijlage A: de agentische laag voor afleidingsregels

- **Status**: voorstel, ter goedkeuring (19 nov 2026). Hoort bij [ADR-018](adr-018-afleidingsregels.md) en het bouwplan in
  [plan-afleidingsregels-in-lex.md](plan-afleidingsregels-in-lex.md) §13, stappen R5 en R6.
- **Wat er al is**: R1 (de regel als object in de api) en R2 (de regelkaart, de keten en het overzicht). Daarin stelt de
  jurist regels op en beoordeelt hij ze; Lex doet in 3b nog niets (L-3b-3).
- **Wat hier staat**: hoe Lex meedoet. Het gaat om de regels-agent, zijn tools, de skills, de route en de stand, de
  meting, en de keuzes voor de gebruiker. Tot het akkoord wordt er niets van R3 en verder gebouwd, en niets van R5 of R6.

## 1. Uitgangspunten

- **De AI stelt voor, de jurist beslist.** Lex maakt een regel, een voorbeeld of een open punt hoogstens als voorstel.
  Accorderen, afwijzen, een drager beoordelen, een lezing kiezen en verwijderen doet de jurist. De api weigert het
  agent-token op elke beslissingsroute (`agent_toegang`, ADR-016 §A5).
- **Lex kiest geen interpretatie.** Laat de tekst ruimte, dan legt Lex de lezingen voor als open punt. De keuze, de
  methode ervan en de reden komen van de jurist (M-3b-2, L-X-1).
- **Code eerst, model waar het moet** (ADR-005, ADR-010). Inventariseren, toetsen en een conceptregel opbouwen uit het
  skelet gebeurt in code. Een model doet alleen een smalle, strikte stap, met de fragmenten waarop het voorstel rust, en
  pas na een meting (R6).
- **Niet strenger dan de methode** (M-3b-0). De agent wijst niets af wat de methode toelaat. Een gat is een signaal, geen
  afwijzing.
- **Generiek.** Geen toets, tool of tekst voor Termijnen of een ander werkgebied. Termijnen is de meetset, niet het
  ontwerp.

## 2. De regels-agent

### 2.1 Vorm en plek

- **Een taakagent zoals de begrippen-agent** (ADR-005): `tools/graph-qa/agent/agents/regels.py`, met een `Taak`-enum,
  `MODEL_TAKEN`, `DOEL` en een `voer_uit` per taak. Hij staat in `agents/register.py` (`AGENTS["regels"]`,
  `NAAM["regels"] = "regels-agent"`).
- **Het profiel** staat in `.claude/lex-agents/regels.md`, in de vorm van de andere profielen (ADR-016 §A2):
  - `name: regels`;
  - `description`: "Stelt afleidingsregels voor uit het regelskelet en de begrippen, toetst de keten op volledigheid en
    uitsluiting, en legt open punten voor; elk resultaat is een voorstel.";
  - `kiesbaar: false`: de centrale agent kiest dit profiel niet, want een taak start via een route in code (§5);
  - `methoderol: regels`, een nieuwe rol (§4.2);
  - `tools`: de lijst van §3;
  - `sjablonen`: geen. Wat een beurt oplevert is een artefact (`regel` of `regels`), geen antwoordsjabloon.
- Het profiel gaat via de generators (`genereer_agentprofielen.py`, `genereer_bronpakket.py`) het image in, zoals elk
  profiel.

### 2.2 De taken

Per taak staat erbij of het code of model is.

- **`inventariseren`** (code): van de analysevraag en de deelvragen terug naar de uitvoer die nodig is. De taak zet de
  Afleidingsregel-markeringen en hun skelet ernaast, en geeft de lijst van regels die er moeten komen, met de keten. Het
  resultaat is een lijst in het paneel (`regels`), geen regel.
- **`volledigheidstoets`** (code): per regel of skelet de gaten die de regelspecialist in de proef bij elke regel afliep
  (L-3b-3):
  - uitvoer zonder begrip;
  - invoer zonder volgorde;
  - een rechtsobject als invoer;
  - een voorwaarde aan de verkeerde drager;
  - geen `uitzondering_op` bij "In afwijking van";
  - twee regels met dezelfde uitvoer zonder voorwaarden die elkaar uitsluiten;
  - een parameter zonder tijdvak.

  Elk gat is een signaal met de plek waar het zit.
- **`opstellen`** (code): één conceptregel uit het skelet en de begrippen. De taak bepaalt de soort uit de klasse van de
  uitvoer, de invoer op volgorde, de gevallen uit de voorwaarden en de grondslag uit de dragende markering. Het taalpatroon
  komt van de api (`regeltekst.py`).
  - Is de soort onzeker, dan stelt de taak de waarschijnlijkste voor en zegt ze waarom. Een model komt pas in R6.
  - Een geval zonder label krijgt een volgnummer.
- **`uitsluiting_toetsen`** (code): leiden twee of meer regels dezelfde uitvoer af, dan toetst de taak of hun gevallen
  elkaar uitsluiten (M-3b-1). Dat gebeurt op de voorwaardenboom: dezelfde markering, of dezelfde voorwaarde met `niet`.
  Kan de code het niet vaststellen, dan wordt het een open punt, geen oordeel.
- **`voorbeelden`** (code, in R6 met een model voor het praktijkvoorbeeld): per geval de invoer die het geval raakt:
  - normaal;
  - elke voorwaarde niet vervuld;
  - de grens van elke vergelijking;
  - nul, negatief en onbekend.

  De uitkomst rekent de taak alleen uit bij een rekenregel met bekende waarden. Het oordeel staat altijd op `open`.
- **`keuze_signaleren`** (model, R6): een passage die meer dan één lezing toelaat. De taak legt een open punt met de
  lezingen en de fragmenten waarop elke lezing rust. Ze kiest niet.

### 2.3 Hoe de regels-agent zich verhoudt tot de rest (ADR-016)

- **De centrale agent** beantwoordt een gewone vraag zelf. Een vraag over regels die er al liggen ("welke regels leiden
  het termijnbedrag af?") is lezen. Dat gaat later via een leesroute (`regels_lezen`, R7), zoals `begrippen_lezen` (§3.1).
- **Werk aan regels start nooit vanuit een model.** Een suggestie of commando met een `actie` kiest de taak in code
  (`ACTIE_TAAK`). Een getypte opdracht ("stel de regels op") brengt de centrale agent met een overdracht naar de route
  `regels`, zoals bij de andere taakagents.
- **Geen subagent die regels opstelt.** Opstellen is een keten in code (ADR-016 §A5: "een agent doet het werk van een
  keten nooit zelf na"). De centrale agent mag geen profiel samenstellen dat regels schrijft.
- **De regisseur** (ADR-012) verdeelt per deelvraag. Regels horen bij het werkgebied, en de keten loopt over de
  deelvragen heen. Daarom geen regie per regel: één gesprek, regel voor regel (§5). De regie blijft voor bronnen en
  annoteren.
- **De begrippen-agent**: de regels-agent maakt nooit zelf een begrip. Ontbreekt een regelbegrip of tussenresultaat,
  dan vraagt hij de begrippen-agent om een voorstel op de passage. Bij een tussenresultaat rust dat voorstel op de
  Afleidingsregel, met de koppelrol `afgeleid` (#1760). Tot het begrip er is, staat de regel niet in de poort (ADR-018
  besluit 2).

## 3. De tools

Per tool staan hieronder het contract, of hij leest of schrijft, wat een voorstel is en wat vastleggen, de plek in
`agent_toegang`, de grenzen, en of hij hergebruikt of nieuw is. Een tool is hier een functie van de regels-agent in code.
Alleen de leestools komen in de open laag (de toollijst van een profiel), en pas met R7.

### 3.1 Lezen

- **`skelet_lezen`** (hergebruikt, #1769)
  - Contract: in gaat een `bron_iri` of een werkgebied. Uit komt per Afleidingsregel-markering haar skelet (opbouw) en
    wat het mist (`gaten`, in woorden), uit `regelskelet.py`.
  - Api: `GET /v1/annotatie/weergave?vorm=skelet`. Die staat al in `TOEGESTAAN` (`GET /v1/annotatie/weergave`).
  - Grens: het skelet zegt iets over de vorm, niet over de inhoud.
- **`regels_lezen`** (nieuw)
  - Contract: in gaat een werkgebied, eventueel met een regel-id. Uit komen de regels met hun regeltekst, poort en
    signalen, en de keten (`hierarchie`).
  - Api: `GET /v1/werkgebieden/{}/regels`, `…/regels/hierarchie` en `…/regels/{}`. Die drie komen nieuw in `TOEGESTAAN`.
  - Grens: alleen lezen. Met R7 komt er een leesroute in de open laag bij (`search_regels`, bevestigd door de api,
    zoals `search_begrippen`).
- **`begrippen_lezen`** (hergebruikt)
  - Contract: de begrippen van het werkgebied met status en koppelingen, zoals de begrippen-agent ze leest.
  - Api: de bestaande leesroutes van de begrippen in `TOEGESTAAN`. Daar komt niets bij.
- **`open_punten_lezen`** (nieuw, met R3 en lessenbundel 4)
  - Contract: de open punten van het werkgebied, per regel en per geval, met hun status en de gekozen lezing.
  - Api: de leesroute van het open-puntobject (L-X-1). Die komt nieuw in `TOEGESTAAN`.
  - Grens: een gekozen lezing is een gegeven voor de volgende regel, geen voorstel.

### 3.2 Voorstellen

- **`regel_voorstellen`** (nieuw)
  - Contract: in gaan `RegelAanmaak` met `herkomst: "lex"` en de dragers. Uit komt de nieuwe regel met status `concept`.
  - Wat het is: een voorstel. Het is een conceptregel die in de werkplek als "Voorstel van Lex" staat (geel, met tekst),
    en alleen de jurist accordeert hem.
  - Api: `POST /v1/werkgebieden/{}/regels`, nieuw in `TOEGESTAAN`, begrensd:
    - alleen met `herkomst: "lex"`;
    - alleen op dragers die in het werkgebied bestaan;
    - de grondslag blijft verplicht (422);
    - hoogstens één nieuwe regel per uitvoer per beurt.
  - Een eigen conceptregel aanvullen gaat met `PATCH` en `POST …/dragers`. Dat mag alleen op een regel met `herkomst: "lex"`
    die nog niemand anders wijzigde. De api toetst dat op de laatste actor; anders volgt 403 (keuze 2).
  - Grens: nooit `accorderen`, `heropenen`, `afwijzen`, `DELETE` of `PATCH …/dragers/{}` (beoordelen). Die staan in
    `BESLISSINGEN` van `tests/poort/test_agent_toegang.py`.
- **`voorbeeld_voorstellen`** (nieuw)
  - Contract: voorbeelden bij een geval, met `oordeel: "open"`.
  - Wat het is: een voorstel. Het oordeel "juridisch juist?" geeft de jurist.
  - Api: via de `PATCH` van een eigen conceptregel. Bij een regel van de jurist kan het alleen als voorstel per veld, in
    de vorm van de kaartvoorstellen van een begrip (keuze 2).
- **`open_punt_leggen`** (nieuw, met R3)
  - Contract: soort (interpretatiekeuze, ontbrekend uitvoeringsbeleid of gat), de regel en het geval, de passage, de
    lezingen met hun fragmenten, en de status `open`.
  - Wat het is: een voorstel. De jurist kiest, met methode en reden, via de vraagkaart (§5.3).
  - Api: `POST` op het open-puntobject, nieuw in `TOEGESTAAN`. Kiezen staat nooit in die lijst.

### 3.3 Toetsen

- **`volledigheidstoets`** (nieuw, in de api, naast `regelskelet.gaten`)
  - Contract: in gaat een regel of skelet. Uit komen de gaten van §2.2, elk met de plek.
  - Lezen. De werkplek toont dezelfde gaten als signaal op de regelkaart (U2), dus agent en jurist zien één toets.
  - Api: een leesroute (`GET …/regels/{}/toets` en `GET weergave?vorm=skelet` met de toets erbij), in `TOEGESTAAN`.
- **`uitsluiting_toetsen`** (nieuw, in de api, uitbreiding van `regel_store.keten`)
  - Contract: het signaal `zelfde_uitvoer` krijgt een uitkomst. Die is "sluiten uit", "sluiten niet uit" (met het paar
    gevallen) of "niet vast te stellen".
  - Lezen; staat in `hierarchie`.

### 3.4 Wat hergebruikt is en wat nieuw

- Hergebruikt:
  - het skelet (`regelskelet.py`, #1769);
  - de begrippenroutes;
  - de regeltekst (`regeltekst.py`, R1);
  - de keten (`regel_store.keten`, R1);
  - de vraagkaart en de stand per stap (de bronselectie, spoor J);
  - de overdracht en de route in code (ADR-016);
  - `PaneelChip` en de artefacten `regel` en `regels` (R2).
- Nieuw:
  - de taakagent `regels` met profiel en methoderol;
  - de tools `regels_lezen`, `regel_voorstellen`, `voorbeeld_voorstellen`, `open_punt_leggen` en `open_punten_lezen`;
  - de api-toetsen `volledigheidstoets` en `uitsluiting_toetsen`;
  - `regel_voortgang` (§5.4) en de regels in `TOEGESTAAN`.

## 4. De skills

### 4.1 De methode staat er al

- `references/afleidingsregels.md` (#1766) is de bron. Die beschrijft:
  - wat een afleidingsregel is;
  - waarop een regel rust;
  - één regel per uitvoer;
  - tussenresultaten en wat de tekst open laat;
  - operatoren, tijd en parameters;
  - wat open blijft.

  Er komt geen tweede reference. Wat de agent nodig heeft en ontbreekt, komt daar bij, in eigen woorden.
- Het boek en de BRM-readers blijven lokaal. De skill geeft de methode in eigen woorden (repo publiek).

### 4.2 Een methoderol `regels`

- `references/agentrollen.md` krijgt een sectie `regels` tussen de methodemarkers. `agentrollen.json` koppelt de rol
  `regels` aan die sectie. De tekst is kort en verwijst naar `afleidingsregels.md`:
  - de taalpatronen;
  - één regel per uitvoer;
  - de grondslag;
  - geen interpretatie kiezen;
  - niet strenger dan de methode.
- **De tekst tussen de methodemarkers stuurt het gedrag** en vraagt een meting (ADR-010, P19). In R5 gebruikt alleen de
  code de rol (de tekst gaat mee in de kaart van een open punt). In R6 krijgt de modelstap hem mee, en dan wordt hij
  gemeten (§6).
- De scheiding met wetsuitvoering blijft: de rol staat alleen in de skill wetsanalyse.
  `tests/methode/test_methodes_gescheiden.py` dekt dat al.

### 4.3 Wat gegenereerd wordt

- Het methodepakket (`agent/methodepakket.py`): de tekst van de rol `regels`, via `genereer_methodepakket.py`.
- Het profielregister (`agent/agentprofielen.py`): het profiel `regels`, via `genereer_agentprofielen.py`, bewaakt door
  `tests/centrale_agent/test_profielregister.py`.
- Het bronpakket (`agent/bronpakket.json`): de nieuwe hash van de skill en het profiel.
- `genereer_jas_klassen.py --check` in CI dekt alle drie. De poort draait de graph-qa-suite, want `.claude/skills/**` en
  `.claude/lex-agents/**` zijn build-input.

### 4.4 Wat de lessen meegeven

- **#1758, de regelspecialist van het acceptatieteam** (`.claude/agents/agent-regelspecialist.md`): zijn checklist wordt
  de volledigheidstoets in code, niet in een prompt. De specialist blijft het referentiepunt van de meting.
- **#1762, de regels R1–R8 van Termijnen**: de ontwikkelset. Ze staat al als vaste set in R1
  (`test_regels_termijnen.py`). Het is geen held-out set: nieuwe regels vragen een nieuwe blinde set (§6).
- **#1764, de lessen uit de proef**:
  - L-3b-1 (een plek voor de regel) is opgelost met R1;
  - L-3b-2 (het skelet compact lezen) met #1769;
  - L-3b-3 (Lex stelt niets voor) met deze bijlage;
  - M-3b-0 (niet strenger dan de methode) is een uitgangspunt (§1);
  - M-3b-1 (één beslistabel per uitvoer) is `uitsluiting_toetsen`;
  - M-3b-2 en L-X-1 (open punten) zijn `open_punt_leggen` op het object van lessenbundel 4.

## 5. De route en de stand

### 5.1 De ingang is code

- Nieuwe acties in `ACTIE_TAAK`: `regels_inventariseren`, `regels_toetsen`, `regel_opstellen` en `regel_voorbeelden`, en
  in R6 `regel_keuzes`. Een klik op een suggestie of een commando kiest de taak zonder modelstap.
- Suggesties (`SUGGESTIES` in `lib/vraagLex.ts`):
  - bij het werkgebied: "Welke afleidingsregels zijn er nodig?" en "Toets de keten";
  - bij een regel (Vraag Lex met onderwerp `regel`): "Vul deze regel aan", "Stel voorbeelden voor" en "Toets deze regel".
- Een getypte opdracht komt via de centrale agent met een overdracht in dezelfde route.

### 5.2 Regel voor regel

- Zoals de bronselectie per deelvraag (spoor J). De code kiest de volgende regel uit de stand bij de api (§5.4). Zij
  volgt de keten van onder naar boven, zodat een regel pas aan de beurt is als zijn invoer er is.
- Per regel komt er een compact kaartje in het gesprek (`PaneelChip`, soort `regel`). Dat verwijst naar het paneel, waar
  de jurist leest en beslist met dezelfde regelkaart als op de pagina. *Klaar* gaat verder, *Hoe wil je verder?* sluit
  af.
- Een tussenvraag, herladen of een ander gesprek breekt niets, want de stand staat niet in het gesprek.

### 5.3 Vraagkaarten

- Een open punt met lezingen is een vraagkaart (`Vraagkaart.modus: "regels"`), in de vorm van de dock:
  - per lezing een optie met titel en fragment;
  - "Weet ik (nog) niet": het punt blijft open;
  - "Typ je antwoord…": een eigen lezing.
- Het antwoord is een besluit van de jurist. Het loopt via een route die alleen de stand van de stap zet en zijn userid
  draagt (de vorm van `bronselectie`), nooit via het agent-token. De methode en de reden komen op het open punt.
- Een volgende regel leest de gekozen lezing als gegeven (`open_punten_lezen`, en in `werkgebied_context.py`).

### 5.4 De stand bij de api

- `regel_voortgang` per werkgebied, naar het model van `bronselectie_voortgang`. Per uitvoer staat er:
  - niet gestart;
  - in behandeling;
  - voorlopig af;
  - beoordeeld (afgeleid uit de status van de regel);
  - opnieuw bekijken (een drager of invoerbegrip veranderde, R7).
- De agent zet *in behandeling* en *voorlopig af* via een stap-route in `TOEGESTAAN`. *Beoordeeld* volgt uit accorderen
  door de jurist.

## 6. Meten

Licht meten: één run, een gerichte set en de geraakte vorm. Drie runs alleen bij twijfel.

- **Eerst, in R5, zonder model**:
  - `opstellen`: de velden van de conceptregels tegen R1–R8 van Termijnen (soort, uitvoer, invoer op volgorde, aantal
    gevallen, grondslag), met recall en precisie per veld.
  - `volledigheidstoets`: de gaten op het skelet van Termijnen van vóór het herstel, tegen de gaten die de
    regelspecialist noemde in het logboek van de proef. Recall en precisie.
  - `uitsluiting_toetsen`: R2, R3 en R4 (dezelfde uitvoer) en een kring.
- **Daarna, in R6, de eerste modelstap**: `keuze_signaleren`, met de negen interpretatiekeuzes en zes punten beleid van
  Termijnen als set. Dan de soort bij twijfel, en het label van een geval het laatst.
- **Blind**: WA TRM H1, en een werkgebied met een reken- en een beslisregel dat niemand eerder zag.
- **Goed genoeg** (voorstel):
  - de opbouw recall ≥ 0,9 per veld op de ontwikkelset en ≥ 0,8 blind;
  - de volledigheidstoets recall 1,0 op de gaten van de regelspecialist, met precisie ≥ 0,8;
  - het signaleren van keuzes recall ≥ 0,8, met elk signaal op een fragment, en nul gekozen lezingen;
  - de kosten: een regel opstellen zonder model kost nul tokens. Een modelstap kost hoogstens enkele duizenden tokens
    per regel, gemeten als de delta van het verbruik.

## 7. Volgorde

- R3 (open punten op de regel) komt na lessenbundel 4. Pas dan bestaan `open_punt_leggen` en de vraagkaart.
- R4 (Termijnen importeren) vraagt een akkoord op het moment van uitvoeren. Dat gaat via de hoofdsessie.
- R5 (deze agent, zonder model) komt na lessenbundel 3 (een betrouwbaar skelet) en R4.
- R6 (de modelstappen) komt na de meting van R5.
- Wat zonder de agent al waarde heeft, kan eerder: de volledigheidstoets en de uitsluitingstoets in de api, als signaal
  op de regelkaart.

## 8. Keuzes voor de gebruiker

Elke keuze heeft een voorstel. Na het akkoord gaan ze als besluiten in ADR-018.

1. **Hoe landt een regel van Lex?**
   - Als conceptregel met `herkomst: "lex"`, of als voorstel in een aparte lijst naast de regels (zoals de groepen van
     de begrippenketen)?
   - Voorstel: als conceptregel. Er is dan één object en één kaart, de poort en de revisies werken meteen, en de kaart
     zegt "Voorstel van Lex". Accorderen blijft bij de jurist.
2. **Mag Lex een regel wijzigen?**
   - Voorstel: alleen een eigen concept dat nog niemand anders wijzigde. Bij elke andere regel stelt Lex een veld voor
     (overnemen, aanpassen of afwijzen, zoals bij een begrip). Dat komt na R5.
3. **Mag de centrale agent het profiel kiezen?**
   - Voorstel: nee (`kiesbaar: false`). Werk start via een route in code. Lezen gaat later via `regels_lezen` (R7).
4. **Regie per regel of één gesprek?**
   - Voorstel: één gesprek, regel voor regel, zonder subagents. De keten loopt over deelvragen heen, en de jurist is
     bij elke regel de poort.
5. **Een eigen methoderol `regels`?**
   - Voorstel: ja, met een korte tekst die naar `afleidingsregels.md` verwijst, en met een meting zodra een model hem
     krijgt (R6).
6. **Waar staat de volledigheidstoets?**
   - Voorstel: in de api, naast `regelskelet.gaten`. Agent en werkplek zien dan dezelfde toets, en hij helpt de jurist
     ook zonder de agent.
7. **Welke modelstap eerst?**
   - Voorstel: het signaleren van interpretatiekeuzes. Daar zat in Termijnen het meeste handwerk (negen keuzes, zes
     punten beleid), en de stap kiest niets.
8. **Hoe ver gaan voorbeelden van Lex?**
   - Voorstel: de invoer per geval altijd, de uitkomst alleen bij een rekenregel met bekende waarden, en het oordeel
     altijd `open`.
9. **Een ontbrekend regelbegrip?**
   - Voorstel: de regels-agent vraagt de begrippen-agent om een voorstel op de passage (bij een tussenresultaat met
     `afgeleid`). De regel wacht in de poort tot het begrip er is.
10. **Wat is goed genoeg?**
    - Voorstel: de drempels van §6. Eerst de ontwikkelset, dan blind. Haalt een stap het niet, dan blijft hij uit, en
      de regel van de jurist werkt zonder.
