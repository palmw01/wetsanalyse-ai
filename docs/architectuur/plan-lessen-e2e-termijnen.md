# Plan: lessen uit de end-to-end proef op Termijnen (activiteit 1 tot en met 3b)

Status: **concept**, 19 nov 2026, bijgewerkt na een lezing van de methode (§0). Er is nog niets gebouwd. Bouwen begint pas na akkoord van de gebruiker, en elke stap
krijgt dan eerst een eigen toets of dit de beste verbetering is.

## Waar dit over gaat

Werkgebied *Termijnen* op acceptatie is de eerste proef die de hele keten doorliep: werkgebied, deelvragen,
bronselectie, annoteren met relaties, begrippen en afleidingsregels. Het werk liep in twee rondes:

- **18 nov 2026**: de hoofdsessie werkte als jurist de bronselectie, de annotatie en de begrippen af.
- **19 nov 2026**: de agents jurist, gegevensspecialist en regelspecialist stelden de afleidingsregels op (3b). Het
  resultaat staat in `afleidingsregels-termijnen-team.md` (PR #1762).

Dit plan zet de lessen voor de hele keten op een rij en stelt generieke verbeteringen voor. **Termijnen is een
proefcasus.** Een oplossing die alleen voor deze artikelen, begrippen of dit werkgebied werkt, staat hier niet in. Bij
elke bevinding staat waarom de oplossing ook elders standhoudt.

**Bronnen**

- Het logboek van de 3b-run (lokaal, `docs/acceptatie/lokaal/afleidingsregels-termijnen-2026-11-19/logboek.md`; een
  citaat hieronder heet *logboek* met het tijdstip).
- Het rapport en het logboek van 18 nov (lokaal, `termijnen-2026-11-18/`).
- Het teamrapport uit PR #1762.
- Een begrip op acceptatie, alleen gelezen: `begrip_lezen` op 27426263. Op Termijnen is niets gewijzigd.
- De gedeelde notities over derdenbeslag, belastingschuldige en de E2E Rekeningafspraken.
- De code op `origin/master` (454f974a).

**Wat al opgelost is of al in een plan staat, en hier dus niet opnieuw voorkomt**

- PR #1738: een zoekronde voor een andere deelvraag heropent geen afronding meer, en een onderdeel van een
  `id:`-bepaling is op te nemen. Dat waren twee bevindingen van 18 nov.
- PR #1744–#1763:
  - de grenzen, de toelichting en de annoteeropdracht (#1744);
  - relaties per laag beoordelen, het 2c-diagram en rollen en voorwerp (#1748);
  - het begripsantwoord (#1755–#1757, #1763);
  - geen begrip zonder annotatie (#1760);
  - een subdivisie die alleen gevonden is, geen gelezen bron (#1761).
- **`onderzoek-bronselectie-termijnen-2026-11.md`** (stap 0–8): waarom de zoeker de kern van DV2 en DV3 mist. Die
  stappen staan, en dit plan herhaalt ze niet.
- **`plan-begrip-per-formulering.md`** (B1–B8): elke formulering een begrip, de operatorbegrippen (B5) en de soort
  (B8).
- **`plan-afleidingsregels.md`** §5 (D1–D6, A1–A5, U1–U4, R1–R3, M1–M2). Dit plan verwijst naar die codes. Wat de proef
  toevoegt, is het bewijs, de oorzaak in de code en een scherpere volgorde.

**Leeswijzer**

- Per activiteit staan eerst de fouten van **Lex** zelf (de agent, de api, de werkplek). Daarna volgen de fouten in de
  **methode of de skill**.
- Het **testgereedschap** (de acceptatie-MCP) staat apart in §7: het is geen deel van Lex.
- Prioriteit: **P1** (blokkeert de keten), **P2** (kost de jurist veel werk of geeft een verkeerd resultaat), **P3**
  (hinder).
- Omvang: **S** (een dag, één onderdeel), **M** (enkele dagen, twee onderdelen), **L** (een spoor, meer PR's).

## 0. Wat de methode zegt over begrippen zonder eigen formulering, operatoren en regels

Gelezen op 19 nov 2026, op verzoek van de gebruiker: de methode is leidend. De bronnen zijn het boek (M01), de
Handleiding (M02), de Leidraad (M03) en de Rijksspecificatie (M04), met de codes van `references/bronnen.md`. M01–M03
zijn van derden en staan hier in eigen woorden, zonder citaten.

**1. Een begrip ontstaat bij een formulering, maar niet elk begrip heeft er een eigen.**
- De hoofdregel: elke geclassificeerde formulering krijgt een begrip, dat je hergebruikt voor elke formulering met
  dezelfde betekenis (M01 h.3 stap 3a; M02 §3.5.2a; M03 hoofdactiviteit 3a).
- Een **tussenresultaat** van een berekening krijgt wél een begrip, ook als de wet het niet noemt. De uitvoering moet
  elke rekenstap kunnen uitvoeren, uitleggen en controleren, en dus moet elk tussenresultaat een naam hebben.
  - M01 §2.2.2 laat het zien aan de tabel van art. 5.2 Wet IB 2001: vier nieuwe begrippen voor één tussenstap.
  - In h.6 komt het terug bij art. 43 Zvw: het loon na de eerste rekenstap in lid 2 onder a, en het bijdrage-inkomen na
    de nihilstelling en na de maximumstelling in lid 3. Het oude tussenresultaat blijft daarbij bewaard, zodat de
    berekening uitlegbaar blijft.
  - M02 §1.2 (*impliciete algoritmes*) zegt hetzelfde: een regel die één berekening lijkt, vraagt vaak extra tussenregels
    die de tussenresultaten en hun voorwaarden expliciet afleiden.
- Een **impliciet element** dat een regel nodig heeft, krijgt een begrip, en de interpretatie wordt gesignaleerd.
  - M01 h.7 geeft drie voorbeelden. Een tijdstip dat logisch volgt maar niet in de tekst staat (de eerste verzending
    naast de tweede), gesignaleerd als ontbrekend uitvoeringsbeleid (stap 5). Een rechtssubject dat in het ene lid geen
    formulering heeft en in het andere wel. Voorwaarden en variabelen die alleen nodig zijn om de regels op elkaar aan
    te laten sluiten.
  - Bij dat laatste zegt het boek ook: je gaat daarna terug naar de wettekst om ze alsnog te duiden.
- De **grondslag** blijft altijd de bron. Elk begrip en elke afleidingsregel moet via de gemarkeerde formuleringen
  rechtstreeks op wetgeving of beleidsregels terug te voeren zijn, niet op een memo of code (M03, analyseresultaat 17).
  Een begrip zonder eigen formulering hangt dus aan de formulering van de regel die het afleidt, of aan de interpretatie
  die het nodig maakte.

**2. Een operatorbegrip ontstaat bij een formulering en wordt daarna hergebruikt.**
- Het boek maakt een operatorbegrip voor een formulering die op een bewerking wijst: *plus* bij "het gezamenlijke bedrag
  van". Daarna hergebruikt het dat begrip bij andere formuleringen met dezelfde betekenis: *plus* bij "vermeerderd met",
  *min* bij "verminderd met", "met uitzondering van" en "wordt niet in aanmerking genomen" (M01 h.3 stap 3b met
  art. 3.110 Wet IB 2001; h.6 bij art. 43 lid 2 Zvw en de bepalingen waarnaar het verwijst).
- Het boek maakt nergens een operatorbegrip zonder formulering. Wat in de regeltekst zelf staat ("moet berekend worden
  als", "is", "indien aan alle volgende voorwaarden is voldaan"), is het **taalpatroon** van de regel, geen begrip
  (M02 §3.5.2b; M03 deelactiviteit 3b).
- Een ontkenning laat je uit het begrip en zet je in de regel als operator *niet* (M01 h.3 stap 3a, h.7 art. 2:11 Awb).

**3. Een afleidingsregel leidt een begrip af, en dat kan ook een beslissing over een recht zijn.**
- M04 H2 (*Afleidingsregel*) noemt een regel die bepaalt of een recht bestaat een beslisregel, met ja of nee als uitvoer.
  Ook het bepalen van een specialisatie van een rechtssubject of rechtsobject is een afleidingsregel. M02 §3.5.2b en
  M03 deelactiviteit 3b noemen berekeningen, beslissingen, specialisaties en voorwaarden.
- Het voorbeeld in M02 bij de zorgtoeslag: *bepalen recht op zorgtoeslag* leidt het recht op zorgtoeslag af uit
  voorwaarden.
- M03 hoofdactiviteit 3 zegt het per formulering: het krijgt een begrip, en waar dat aan de orde is een of meer
  afleidingsregels die dat begrip afleiden. Een rechtsbetrekking met voorwaarden kan dus een begrip hebben met een
  beslisregel erbij.
- Per afgeleid begrip is er één regel met een naam "bepalen …" (de tabellen in M02 §3.5.2b).

**4. Een parameterwaarde is een eigen formulering met een eigen begrip.**
- De parameter is de omschrijving van de waarde, de parameterwaarde de concrete waarde in een periode (M04 H2).
- Het boek classificeert de waarde apart, maakt er een begrip voor ("… in tijdvak") en relateert dat aan de parameter.
  De regel gebruikt de parameter, niet de waarde (M01 h.6, art. 43 lid 3 en art. 45 Zvw met de Regeling zorgverzekering).

**Wat dit betekent voor wat er nu ligt**
- **#1760** (open) maakt "geen begrip zonder annotatie" een harde regel, en zegt daarbij dat een tussenresultaat zonder
  formulering geen begrip is.
  - Het eerste deel klopt met de methode, als de annotatie de grondslag is: de formulering waaraan het begrip hangt.
  - Het tweede deel is in strijd met M01 §2.2.2 en h.6, en met M02 §1.2.
  - Zie M-3a-0.
- **B5** in `plan-begrip-per-formulering.md` zet operatoren als geaccordeerde begrippen in het generieke kader, zonder
  passage. Ook dat volgt de methode niet: een operatorbegrip ontstaat bij een formulering (punt 2). Een vaste lijst met
  namen mag wel, als voorstel. Zie M-3a-1.
- **Het team ging in Termijnen op drie plekken strenger te werk dan de methode** (§6, M-3b-0):
  - geen tussenbegrip (*termijnregime*, *maandnummer van de dagtekening*);
  - "een regel rust op een AR-markering" als eis, waardoor R5, R6 en R8 eerst werden afgewezen;
  - "het termijnbedrag rust op geen afleidingsregel", terwijl "gelijke termijnen" de deling draagt; de jurist markeerde
    het later alsnog (M-2-2).

## 1. Top 5

1. **De afleidingsregel heeft geen plek in Lex, en de interpretatiekeuzes en het ontbrekende beleid evenmin**
   (§6, L-3b-1 en L-X-1). Het team schreef alle acht regels, negen interpretatiekeuzes en zes punten ontbrekend beleid
   in een logboek buiten de werkplek. Het skelet van een regel stopte de gegevensspecialist in het vrije veld
   *toelichting* van het regelbegrip. P1, L.
2. **De keten legt het skelet van een afleidingsregel verkeerd** (§3, L-2-2). De invoer is het binnenste rechtsobject
   ("het aanslagbiljet") in plaats van de waarde ("de dagtekening van het aanslagbiljet"). De invoer heeft geen volgorde.
   "niet" krijgt twee operanden. `uitzondering_op` bij "In afwijking van" en `toepassing` bij "vindt toepassing" komen
   er niet. De jurist wees in drie leden 14 relaties af en legde er 30 opnieuw. P1, M.
3. **De keten herkent een afleidingsregel alleen in één vorm** (§3, L-2-1). Vijf afleidingsregels markeerde de
   jurist zelf. Eén oorzaak is aan te wijzen: het patroon "zoveel … als" eist het woord "overblijven" of "resteren".
   P1, M.
4. **Een agent of jurist kan een regelskelet niet compact lezen** (§6, L-3b-2). Eén lid lezen kostte 62.000 tekens.
   Een bron lezen herhaalde het hele dossier. Het rapport kent het skelet al (`werkgebied_rapport.regelskelet_regels`),
   maar de api biedt het niet als leesvorm. P2, S.
5. **Begrippen en regels zijn niet op elkaar afgestemd** (§5, L-3a-1 tot en met L-3a-3). Er waren twee regelbegrippen
   voor één uitvoer. Een parameterwaarde stond in een definitie. Het woord "betalingstermijn" duidde twee begrippen aan.
   Een opvolger en een samenvoeging vroegen extra handwerk. Lex zag geen van deze punten. P2, M.

Daarnaast moeten **twee regels de methode weer volgen** voordat er verder gebouwd wordt (§0, M-3a-0 en M-3a-1):
- #1760 zegt dat een tussenresultaat geen begrip is. De methode zegt het omgekeerde: een tussenresultaat krijgt een
  begrip, dat rust op de afleidingsregel die het afleidt.
- B5 zet operatorbegrippen zonder passage in het generieke kader. De methode maakt een operatorbegrip bij een
  formulering en hergebruikt het daarna.

Beide punten bepalen hoe D1 en B5 eruitzien.

## 2. Activiteit 1 en de bronselectie

### Fouten van Lex

**L-1-1 — Een regeling die de wet van overeenkomstige toepassing verklaart, blijft buiten het zoekbereik**

- **Wat**: de Mijnbouwwet stond niet in het zoekbereik, en Lex stelde haar niet voor. Toch hangt de analysevraag eraan.
  Art. 72 Mbw verklaart de AWR en de IW 1990 van overeenkomstige toepassing op het winstaandeel. Het rapport van 18 nov
  meldt: "De Mijnbouwwet stond niet in de regelingen. Lex stelde haar ook niet voor." De jurist voegde haar zelf toe.
  Het hele 3b-werk rust erop: interpretatiekeuze 1 is lezing C van art. 72 Mbw.
- **Activiteit**: 1, het zoekbereik.
- **Oorzaak**: `bronnen_vinden.q_inkomend` (`tools/graph-qa/agent/bronnen_vinden.py:226`) volgt een verwijzing naar
  een kernbepaling of iets daaronder (`?kern (BEVAT)* ?doel`). Een schakelbepaling verwijst naar de hele regeling ("de
  Invorderingswet 1990"), dus naar een knoop bóven de kern. Die valt erbuiten. Daarbij volgt de zoeker alleen bronnen
  binnen het zoekbereik, en een regeling erbuiten wordt nooit een suggestie.
- **Oplossing**:
  - Bij het zoekbereik (de vraagkaart in activiteit 1 en de bronselectie) komt een deterministische stap. Zoek de
    bepalingen buiten het zoekbereik die naar een regeling ín het zoekbereik verwijzen met de functie *toepassing*
    ("overeenkomstige toepassing", "is van toepassing"), op regelingniveau.
  - Zo'n regeling verschijnt als voorstel "regeling erbij?", met de schakelbepaling als bewijs. De jurist beslist.
  - `verwijzingsfunctie` (r. 128) kent het patroon al.
- **Waarom generiek**: schakelbepalingen zijn een vaste techniek van wetgeving: de AWR voor andere heffingen, de Awb
  voor bijzondere wetten, de Zvw en de Wfsv. De stap gebruikt alleen de verwijzingsgraaf en de functie van de
  verwijzing, en noemt geen regeling.
- **Meten**:
  - Een nieuwe kleine set "regeling buiten het zoekbereik": Termijnen (Mbw) als ontwikkelset en minstens één blind
    werkgebied met een schakelbepaling.
  - Maat: recall van de schakelregeling in de voorstellen, en het aantal valse voorstellen per werkgebied.
- **Prioriteit en omvang**: P2, M (graph-qa en de vraagkaart).

**L-1-2 — Een contextbron die een regel draagt, blijft onzichtbaar**

- **Wat**: Leidraad 9.1 stond als context en was dus niet geannoteerd. Ze legt de enige of laatste termijn op
  31 december en verandert daarmee het praktijkvoorbeeld. Het team kon er geen regel op bouwen: "Leidraad 9.1 …
  is niet geannoteerd, dus kan ze geen regel dragen. Alleen gesignaleerd" (teamrapport §6). Hetzelfde gold voor
  Awb 4:93 lid 3 als doel van een `uitzondering_op` (logboek 19:07:30): "die bron staat als context en heeft geen
  elementen".
- **Activiteit**: 1 (de rol van een bron), met gevolg in 2c en 3b.
- **Oorzaak**:
  - De rol *context* betekent "niet annoteren" (`bronselectie-per-deelvraag.md`).
  - Een relatie kan alleen tussen elementen of met een impliciete partij (`annotatie_v2_relaties._info`, r. 95–101).
  - Een bepaling waarnaar een gemarkeerde `uitzondering_op` of `toepassing` wijst, kan dus geen eindpunt zijn zonder
    eerst een analysebron te worden.
- **Oplossing**:
  - Een relatie mag een **bron als eindpunt** hebben (soort `bron`, met de bron-IRI en de stand). Alleen de typen
    `uitzondering_op` en `toepassing` krijgen die soort: daar wijst de wet naar een hele bepaling.
  - Het skelet toont zo'n eindpunt als "naar een contextbron".
  - De dekking per deelvraag krijgt een signaal: een contextbron waarnaar een geaccordeerde relatie of een
    afleidingsregel verwijst, is kandidaat om te analyseren. De jurist beslist.
- **Waarom generiek**: een afwijking van een algemene wet ("In afwijking van artikel 4:93 Awb") komt in elk
  bijzonder rechtsgebied voor. De rol van een bron verandert niet vanzelf.
- **Meten**: op Termijnen en WA TRM H1 het aandeel `uitzondering_op` uit de tekst ("In afwijking van") met een eindpunt.
  Nu is dat 0 als het doel een contextbron is.
- **Prioriteit en omvang**: P2, M (catalogus, api en werkplek). Hangt aan besluit M-1-1.

### Fouten in de methode of de skill

**M-1-1 — Mag een relatie naar een bepaling wijzen die je niet annoteert?**

- **Stand (20 nov 2026)**: besloten en gebouwd (ADR-011, *Een hele bepaling als eindpunt*).
  - Een eindpunt `bron` mag bij `eindpunt_bron` in `relaties.json`, dus bij `uitzondering_op` en `toepassing`.
  - De keten legt die twee naar het doel van de verwijzing uit de graaf, en legt `tijd` uit de nesting.
  - De dekking noemt een contextbron waarnaar een beoordeelde relatie wijst (L-1-2).

- **Wat**: zie L-1-2. ADR-011 kent alleen element-eindpunten en impliciete partijen.
- **Oplossing**: een besluit in ADR-011. Een relatie `uitzondering_op` of `toepassing` mag een bron als eindpunt hebben.
  In `relaties.json` wordt dat een veld per type (`eindpunt_bron: true`). De skill zegt in `relaties.md` wanneer:
  alleen als de wet zelf naar de hele bepaling verwijst.
- **Waarom generiek**: het is een regel in de catalogus, geen uitzondering per bron.
- **Prioriteit en omvang**: P2, S (docs en skill). Een wijziging in `relaties.json` is een build-input van graph-qa:
  draai de generator en de drifttest.

## 3. Activiteit 2: markeren en relaties (2a–2c)

### Fouten van Lex

**L-2-1 — De keten herkent een afleidingsregel alleen in één vorm**

- **Wat**: de jurist markeerde vijf afleidingsregels zelf (logboek 19:15:55 en 19:21:57):
  - art. 9 lid 1: "invorderbaar zes weken na de dagtekening";
  - lid 7, volzin 1: "zoveel gelijke termijnen als er maanden van het jaar zijn";
  - "gelijke termijnen" in lid 5, 6 en 7;
  - Leidraad 9.3: "In dat geval worden de voorlopige teruggaven in één keer uitbetaald".

  Op 18 nov markeerde hij ook de slotzin van IW 24 lid 1 zelf. De regelspecialist schreef (19:00:14): "Niet als AR
  gemarkeerd maar regeldragend: AR3 lid 7 vz1 …; AR5 lid 1 'zes weken na de dagtekening'".
- **Activiteit**: 2a–2b.
- **Oorzaak**: `detectoren/functies.py` kent vijf vormen.
  - `_AANTAL` (r. 26) eist na "zoveel … als" het woord "overblijven" of "resteren". Lid 5 en 6 voldoen daaraan, lid 7
    ("als er maanden van het jaar zijn") niet.
  - Een datum als "<duur> na <tijdstip>" wordt een Tijdsaanduiding (`TEMPORAL_DESCRIPTION`, r. 146–153), nooit een
    afleiding. Dat het een uitkomst oplevert (de vervaldag), ziet de detector niet.
  - Een verdeling ("in gelijke termijnen") en een gevolg van een vergelijking ("In dat geval worden …") kent de
    detector niet.
- **Oplossing**: de functiedetector krijgt een paar algemene vormen erbij, elk met een eigen code en een eigen
  verklaring in `verklaringen.yaml`:
  - **Aantal**: "zoveel X als (er) Y" met elk werkwoord, mits de bijzin een telbare grootheid draagt. Dat is de
    hoofdvorm van `_AANTAL`; "overblijven" en "resteren" worden bewijs voor de invoer, geen eis.
  - **Datum uit een duur**: een Tijdsaanduiding "<duur> na/vóór <tijdstip>" die een rechtsbetrekking of een vervaldatum
    begrenst, wordt ook een kandidaat-Afleidingsregel. Het tijdstip is de invoer, de duur een parameter en de datum de
    uitvoer. Dat is geel, omdat de methode hier een keuze laat (M-2-1).
  - **Verdeling**: "(in) gelijke <telbare eenheden>" bij een bedrag is een afleiding met het bedrag en het aantal als
    invoer.
  - **Gevolg van een vergelijking**: een hoofdzin die volgt op een voorwaarde met een operator ("niet groter is dan …;
    in dat geval …") en een waarde of wijze vastlegt.
- **Waarom generiek**: dit zijn taalpatronen die de methode zelf noemt voor afleidingsregels (rekenregel, datumregel,
  verdeling, beslisregel; skill `markeringslijst.md`). Geen patroon noemt een term uit de IW.
- **Meten**:
  - Recall en precisie van de klasse Afleidingsregel per bepaling, op de ontwikkelset (Termijnen en WA TRM H1) en op een
    blinde set met een rekenregel en een beslisregel uit een andere regeling.
  - Daarnaast de eval van de keten (ADR-001) op de bestaande sets: andere klassen mogen niet achteruitgaan. Met drie
    runs, omdat het geel per run sterk varieert.
- **Prioriteit en omvang**: P1, M (graph-qa). Detectorversie omhoog en de verklaringen opnieuw genereren.

**L-2-2 — De keten legt het skelet van een afleidingsregel verkeerd**

- **Wat** (logboek 19:00:30, 19:04:14, 19:06:25 en 19:15:55):
  - De invoer van de regels in lid 5, 6 en 7 was "het aanslagbiljet" of "de voorlopige aanslag": een rechtsobject, geen
    waarde ("'het aanslagbiljet' 97731f06784b als invoer is geen waarde, weg").
  - De invoer had geen volgorde ("invoeren zonder volgorde").
  - "meer dan" hing als operand onder "niet", en "niet" kreeg twee plekken ("de richting is onlogisch: 'niet' heeft één
    operand"). Operand 1 van "meer dan" ontbrak.
  - "In afwijking van het eerste lid" kreeg geen `uitzondering_op`, en "vindt het eerste lid toepassing" geen
    `toepassing`. Een afleidingsregel had daardoor alleen een voorwaarde, zonder invoer of uitvoer.
  - "telkens een maand later" had geen relatie.
  - De jurist wees 14 relaties af en legde er ongeveer 30 opnieuw (19:15:55).
- **Activiteit**: 2c.
- **Oorzaak** (`tools/graph-qa/agent/jas_pipeline/relaties.py`):
  - `_functie` (r. 167–181) kiest met `_minimaal` het binnenste voorstel dat de invoerspan overlapt. Bij "de dagtekening
    van het aanslagbiljet" is dat "het aanslagbiljet". De catalogus laat een Rechtsobject als invoer toe (`relaties.json`,
    `invoer.van`), dus `_past` houdt het niet tegen. De invoer krijgt geen `volgorde` (r. 179).
  - `_operator` (r. 239–252) geeft elke operator een linker- en een rechteroperand. De catalogus kent geen ariteit per
    operator.
  - Voor `uitzondering_op`, `toepassing`, `tijd` en een interval is er geen regel. De docstring zegt: "Kenmerk en tijd
    doet deze module niet" (r. 34).
  - `_voorwaarde` (r. 270–285) eist één drager. Dragen een rechtsbetrekking en een afleidingsregel hetzelfde predicaat
    (lid 5), dan komt er geen voorstel. In Termijnen hing de voorwaarde 6450… daardoor alleen aan de rechtsbetrekking
    (19:00:30). Dat dit de oorzaak is, is aannemelijk maar niet nagerekend.
- **Oplossing**: dit is A1 uit `plan-afleidingsregels.md`, nu met de plek in de code.
  - **Invoer**: kies het grootste voorstel binnen de invoerspan dat een waarde draagt (Variabele, Parameter,
    Tijdsaanduiding). Een Rechtsobject binnen die waarde wordt een `kenmerk`-voorstel ("dagtekening is kenmerk van
    aanslagbiljet"), geen invoer. Een Rechtsobject dat alleen staat, blijft invoer, maar geel.
  - **Volgorde**: de invoer krijgt de woordvolgorde als `volgorde`, net als de operanden.
  - **Ariteit**: `relaties.json` krijgt per operatorbegrip een ariteit (niet: 1; en/of: n; vergelijkingen en rekenen: 2).
    Bij "niet" komt alleen de operand die volgt.
  - **Uitzondering en toepassing**: "In afwijking van <verwijzing>" wordt `uitzondering_op` en "vindt <verwijzing>
    toepassing" wordt `toepassing`, met de opgeloste verwijzing als eindpunt (de verwijzingsgraaf van de bepaling, of een
    bron-eindpunt na M-1-1). Dat is tekstueel en dus deterministisch.
  - **Voorwaarde**: dragen een rechtsbetrekking en een afleidingsregel samen het predicaat, dan gaat het voorstel naar
    beide, geel.
- **Waarom generiek**: elke regel leunt op de zinsontleding en de catalogus. "In afwijking van" en "vindt toepassing"
  zijn vaste formules in de wetgevingstechniek (Aanwijzingen voor de regelgeving).
- **Meten**:
  - De maat *regelskelet-compleet* van ADR-011 per afleidingsregel: uitvoer precies één, invoer ten minste één, met
    volgorde, en geen rechtsobject als enige invoer.
  - Daarnaast de precisie van de relatievoorstellen tegen het oordeel van de jurist. Termijnen is daarvoor de
    ontwikkelset: het skelet na het herstel van 19 nov is het oordeel. WA TRM H1 en een blind werkgebied volgen.
  - De voorstellen blijven achter de proefvlag `relatieVoorstellen` tot de meting er is.
- **Prioriteit en omvang**: P1, M (graph-qa en de catalogus in de skill).

**L-2-3 — Een afgewezen relatie houdt haar volgordeplek bezet**

- **Wat**: "een afgewezen relatie houdt haar volgordeplek bezet; een gecorrigeerde invoer of operand op plek 1 geeft 409
  volgorde_bezet" (logboek 19:13:17, trace e9f91bb0…). Drie relaties staan daardoor zonder nummer, met de plek in de
  toelichting.
- **Activiteit**: 2c.
- **Oorzaak**:
  - `annotatie_v2_relaties.py:111–115` (handmatig leggen) toetst de plek tegen álle relaties, ook afgewezen en vervangen.
  - Het batchpad van de keten (r. 248) sluit afgewezen relaties wél uit. De twee paden zijn dus niet consistent.
- **Oplossing**:
  - Eén functie `plek_bezet(conn, type, naar, volgorde)` die alleen actuele relaties telt (niet `rejected`, niet
    `vervangen`, niet verouderd). Beide paden gebruiken haar.
  - Een test die afwijzen en daarna opnieuw leggen op dezelfde plek doorloopt.
- **Waarom generiek**: het gaat om elke relatie met volgorde.
- **Meten**: een api-test; daarna op acceptatie een plek opnieuw leggen in een testwerkgebied (niet in Termijnen).
- **Prioriteit en omvang**: P2, S (api).

**L-2-4 — `verwachte_revisies` heeft twee sleutels**

- **Wat**: "verwachte_revisies verwacht de bron-iri als sleutel, niet het laag-id; met het laag-id kwam er een 412"
  (logboek 19:13:17, trace 139650f3…). In de E2E Rekeningafspraken liep een agent er ook op vast.
- **Activiteit**: 2.
- **Oorzaak**: het contract zegt "per bron-IRI, zoals bij elementen" (`annotatie_v2_contracts.py:233–240`). De
  besluitroutes per laag (`/lagen/{laag}/…`) spreken in laag-id's.
- **Oplossing**:
  - De api neemt beide sleutels aan. Een laag-id wordt via de laag naar haar bron-IRI vertaald, en twee sleutels die
    naar dezelfde laag wijzen zijn een 422.
  - Een 412 noemt welke sleutel hij verwachtte.
- **Waarom generiek**: een contractkwestie, los van inhoud.
- **Meten**: een api-test.
- **Prioriteit en omvang**: P3, S (api).

**L-2-5 — Een datum als waarde komt als Rechtsfeit of Voorwaarde binnen**

- **Wat**: "de dagtekening van het aanslagbiljet" (art. 24 lid 1 slottekst) stond als Rechtsfeit. De jurist zette haar
  om naar Variabele, omdat "de datum een waarde is, geen handeling" (logboek 19:21:57). Op 18 nov wees hij om dezelfde
  reden vier keer "dagtekening als Voorwaarde" af.
- **Activiteit**: 2b.
- **Oorzaak**: niet tot op de regel nagegaan. De kleine classifier krijgt een naamwoordgroep met "dagtekening" en kiest
  tussen Rechtsfeit, Voorwaarde en Variabele. Geen detector zegt dat een tijdstip-naamwoord ("dagtekening", "datum",
  "tijdstip") een waarde is. `functies.py:146` kent die lemma's alleen bij een relatieve bijzin.
- **Oplossing**:
  - Een detector "tijdstip als waarde". Een naamwoordgroep met een tijdstip-hoofd en een *van*-bepaling, zonder eigen
    werkwoord, is bewijs voor Variabele (als invoer of uitvoer van een regel) of Tijdsaanduiding.
  - Is er een concurrerende hypothese Rechtsfeit, dan is dat twijfel, geel.
- **Waarom generiek**: elke datumregel heeft zo'n waarde: dagtekening, vervaldag, tijdstip van ontvangst, datum van
  ingang.
- **Meten**: de verwarringsmatrix van de eval (ADR-001) voor Variabele, Tijdsaanduiding, Rechtsfeit en Voorwaarde, op de
  bestaande sets. Drie runs.
- **Prioriteit en omvang**: P2, S–M (graph-qa).

**L-2-6 — Een brondefinitie buiten "wordt verstaan onder" wordt niet herkend**

- **Wat**: "Niet herkend als Brondefinitie: AWR 13 lid 2 ('wordt aangeduid als') en Leidraad 1.1.2 onderdeel 10"
  (rapport 18 nov). De jurist markeerde beide zelf.
- **Activiteit**: 2b.
- **Oorzaak**: `detectoren/structuur.py` kent twee vormen, de aanhef `_AANHEF` (r. 17) en de zin `_ZIN` (r. 19). Beide
  eisen "verstaan onder". De zoeker kent "wordt aangeduid als" wel als brug (`deelvraag_zoeken.py:162`), de annotatie
  niet. Waarom het Leidraad-onderdeel niet herkend werd, is niet nagegaan: de aanhef kan anders luiden, of het onderdeel
  staat als eigen bronnode zonder context.
- **Oplossing**:
  - De definitiedetector krijgt de formules die de Aanwijzingen voor de regelgeving en de praktijk gebruiken: "wordt
    aangeduid als", "hierna: …", "wordt … genoemd", "in deze … wordt onder … verstaan". Elk met een eigen regelcode.
  - Voor het Leidraad-onderdeel: eerst nagaan welke aanhef daar staat (lezen, niet raden). Dan dezelfde route als bij een
    onderdeel van een wet, met de aanhef uit `BronTekst.context`.
- **Waarom generiek**: het zijn algemene definitieformules. De lijst staat in de skill (`markeren-fragmentgrenzen.md`)
  en niet in de code.
- **Meten**: recall van Brondefinitie op de begrippensets van ADR-004. Daarin staan definities buiten een
  begripsbepalingenartikel.
- **Prioriteit en omvang**: P2, S (graph-qa en de skill).

### Fouten in de methode of de skill

**M-2-1 — Een bepaling kan een rechtsbetrekking én een afleidingsregel dragen; de skill zegt niet wanneer**

- **Wat**: art. 9 lid 1 ("Een belastingaanslag is invorderbaar zes weken na de dagtekening") stond alleen als
  Rechtsbetrekking: "de rekenregel staat in een Rechtsbetrekking" (logboek 19:04:14). Bij art. 24 lid 2 ging het
  omgekeerd. De regelspecialist stelde er een afleidingsregel voor, en de jurist wees die af: "een bevoegdheid … onder
  voorwaarden, geen afleiding van een waarde" (19:13:17). Beide keren was het een oordeel zonder houvast in de skill.
  Volgens de methode was de afwijzing van art. 24 lid 2 niet juist (§0 punt 3, M-3b-0).
- **Oplossing**: in `references/markeringslijst.md` en de nieuwe reference `afleidingsregels.md` (M2 uit het plan),
  in eigen woorden naar M04 H2 en M02 §3.5.2b:
  - In **activiteit 2** markeer je wat de tekst doet. Een recht, plicht of bevoegdheid is een Rechtsbetrekking met haar
    voorwaarden. Een formulering die een waarde berekent of afleidt is een Afleidingsregel. Het gaat dan om een aantal,
    een bedrag, een datum of een keuze, bijvoorbeeld "zes weken na de dagtekening" of "zoveel … als". Draagt één zin
    allebei, dan markeer je ze allebei, met overlap (de banen van #1741).
  - In **activiteit 3b** maak je een afleidingsregel voor elk begrip dat afgeleid moet worden. Dat geldt ook voor een
    beslissing of een recht bestaat (een beslisregel met ja of nee als uitvoer), en voor een specialisatie. Ook als de
    formulering in activiteit 2 een Rechtsbetrekking is en geen Afleidingsregel.
- **Waarom generiek**: het volgt de definitie van de klassen in de bron, niet de casus.
- **Prioriteit en omvang**: P2, S. Valt de tekst tussen de methodemarkers, dan is een meting nodig (ADR-010, P19).

**M-2-2 — Eén formulering, twee uitvoeren: hoe fijn markeer je?**

- **Wat**: "zoveel gelijke termijnen als …" levert het aantal termijnen én het termijnbedrag. De kardinaliteit (precies
  één uitvoer per afleidingsregel, `relaties.json`) dwong een tweede markering op "gelijke termijnen". Eerst werd R5
  daarom afgewezen ("'gelijke' zit in de AR voor het aantal (precies één uitvoer)", 19:13:17), daarna aanvaard met de
  nieuwe markering (19:21:57).
- **Oplossing**: de skill zegt het: *een formulering die twee waarden oplevert, draagt twee afleidingsregels, elk op het
  kleinste stuk tekst dat de eigen afleiding draagt*. Overlap is toegestaan. Zo wordt de kardinaliteit één regel met een
  werkwijze, in plaats van een reden om af te wijzen.
- **Prioriteit en omvang**: P2, S (skill).

**M-2-3 — Een invoer zonder formulering**

- **Wat**: rij lid 7 van R5 heeft geen invoer voor het bedrag. "Lid 7 markeer ik niet: … bevat geen formulering voor
  het bedrag, en een markering zonder formulering kan niet" (19:23:01). Bij lid 5 kwam de invoer uit een andere bepaling
  (AWR 13 lid 1), en dat is aanvaard.
- **Oplossing**, volgens §0 punt 1:
  - Kan de invoer uit een andere bepaling komen, dan heeft dat de voorkeur. `relaties.md` staat dat al toe ("Een
    eindpunt mag in een andere bepaling liggen").
  - Anders volgt de skill het boek. Het element dat de regel nodig heeft, krijgt een begrip (hier het bestaande
    *bedrag van de belastingaanslag*). Het is invoer van de regel als **impliciete invoer**, en de interpretatie wordt
    een open punt van de soort ontbrekend uitvoeringsbeleid (L-X-1). Daarna kijk je opnieuw in de wettekst of er toch
    een formulering is.
  - ADR-011 kent al impliciete partijen (`impliciet_toegestaan`). Of een impliciete invoer daar ook onder valt, is een
    besluit. Het voorstel is ja, met de verplichting een open punt te maken: de methode doet het zo, en de jurist ziet
    dat er een interpretatie ligt.
- **Prioriteit en omvang**: P3, S (skill en ADR-011).

## 4. Deelvragen

De proef leverde hier weinig nieuws op dat al niet in een plan staat. Twee punten:

- **L-DV-1 — De slotzin die DV3 beantwoordt, kwam mee via DV2.** "De zoeker vond die zin niet; hij kwam alleen mee
  doordat IW 24 lid 1 voor DV2 was opgenomen" (logboek 18 nov, 22:20:43). De oorzaken (O1–O7) en de stappen staan in
  `onderzoek-bronselectie-termijnen-2026-11.md`. Daar komt één aanvulling bij. De dekking per deelvraag
  (`werkgebied_deelvragen.dekking`) kijkt per deelvraag naar de eigen bronnen. Een bron die bij een andere deelvraag
  opgenomen is en de vraag ook beantwoordt, telt niet mee en komt ook niet als voorstel. **Voorstel**: een opgenomen
  bepaling die volgens de zoeker bij deze deelvraag kern is, verschijnt als voorstel "ook bij deze deelvraag?". P3, S.
- **L-DV-2 — Het onderzoekspunt van een deelvraag en de interpretatiekeuzes van de regels liggen los.** DV3 was
  "voorlopig afgerond met onderzoekspunt (herberekening of saldering per termijn; toepassing art. 9 lid 5/6 op
  winstaandeel via art. 72 Mbw)" (18 nov). Op 19 nov werd dat interpretatiekeuze 1 in de regels, zonder dat de
  deelvraag het weet. Dit lost L-X-1 op.

## 5. Activiteit 3a: begrippen

### Fouten van Lex

**L-3a-1 — Twee regelbegrippen voor één uitvoer, en Lex ziet het niet**

- **Wat**: "bepalen van het tijdstip van verrekening" (18875a3a) en "idem van een termijn" (8d54e463) hadden dezelfde
  uitvoer. Ze moesten worden samengevoegd. Het oordeel: "Twee 'bepalen'-begrippen … voor dezelfde uitvoer zijn niet
  eenduidig" (19:09:22). Bij R1 dreigde hetzelfde (19:01:53, V3).
- **Activiteit**: 3a, met gevolg in 3b.
- **Oorzaak**:
  - Er is geen signaal dat het begrip van een afleidingsregel naast de uitvoer van die regel legt.
  - `begrip_onderhoud_store.dekking` (r. 410) telt per element. De relaties van ADR-011 kent hij niet.
- **Oplossing**: een aandachtspunt op het begrip (het bestaande `aandachtspunten`), deterministisch:
  - twee begrippen die allebei op een afleidingsregel rusten, waarvan de `uitvoer`-relaties naar passages van hetzelfde
    begrip wijzen, krijgen "één uitvoer, twee regelbegrippen: combineren?";
  - omgekeerd krijgt één regelbegrip waarvan de dragers verschillende uitvoerbegrippen hebben: "meer uitvoeren".
- **Waarom generiek**: het rust op de uitvoerkardinaliteit uit de catalogus en op de koppelingen, niet op een naam.
- **Meten**: op Termijnen vóór het samenvoegen (de revisiehistorie) moet het signaal 18875a3a/8d54e463 vinden. Dan nul
  valse signalen op de andere werkgebieden op acceptatie, alleen gelezen.
- **Prioriteit en omvang**: P2, S–M (api en de begripskaart).

**L-3a-2 — Een parameterwaarde in de definitie, een homoniem in de alternatieve termen**

- **Wat**:
  - De definitie van "wettelijke betalingstermijn" (855cd256) bevatte "zes weken". "Bij een wetswijziging verandert dan
    het begrip in plaats van de waarde" (19:05:57, V4).
  - "betalingstermijn" stond als alternatieve term bij *termijn* (e6aed82a), terwijl het woord ook de termijn van
    art. 9 lid 1 en de algemene betalingstermijn van Leidraad 9.5 aanduidt (18:58:09, 19:07:43).
  - Beide moesten met de hand in een revisie.
- **Activiteit**: 3a.
- **Oorzaak**: de conformiteitstoets (NL-SBB, diagnostisch) kijkt naar de vorm van het begrip. Ze legt de definitie niet
  naast de klasse van de dragers, en de alternatieve termen niet naast het hele kader.
- **Oplossing**: twee aandachtspunten.
  - **Waarde in de definitie**: een begrip met een dragende passage van klasse Parameter, waarvan de definitie de tekst
    van een gekoppelde of geneste parameterwaarde bevat (een getal, een duur of een bedrag uit die waarde). Volgens de
    methode (§0 punt 4) krijgt de waarde een eigen begrip op haar eigen markering ("… in tijdvak"), met een relatie
    `waarde` naar de parameter. De regel gebruikt de parameter. Het aandachtspunt stelt dat voor. In Termijnen is "zes
    weken" in lid 1 de parameterwaarde (379bc7e1…, invoer van R2).
  - **Homoniem**: een alternatieve term die gelijk is aan de naam of een alternatieve term van een ander actief begrip
    in hetzelfde kader of het generieke kader, of die als kop in de naam van een ander begrip staat.
- **Waarom generiek**: beide toetsen gebruiken alleen de klasse, de koppeling en de tekst. Geen term staat vast.
- **Meten**: precisie van de aandachtspunten op alle werkgebieden op acceptatie (alleen lezen). Een jurist beoordeelt
  een steekproef van twintig.
- **Prioriteit en omvang**: P2, S (api).

**L-3a-3 — Opvolgen en samenvoegen vragen extra handwerk en voegen een valse alternatieve term toe**

- **Wat**: "nieuwe-betekenis kopieert de koppelingen als 'open', dus elke opvolger vraagt een aparte beoordeelstap … ;
  combineren maakt geen derde begrip … ; combineren zet de naam van het vervangen begrip als alternatieve term; die heb
  ik weggehaald, omdat een smallere regel geen synoniem is" (logboek 19:23:52).
- **Activiteit**: 3a.
- **Oorzaak**:
  - `begrip_relatie_store.py:237–250` zet bij opvolging elke koppeling op `beoordeling="open"`, ook als het bewijs
    gelijk bleef.
  - `combineer` (r. 334–353) voegt de naam van het vervangen begrip altijd toe aan `alternatieve_termen`.
  - Een samenvoeging van twee begrippen tot een nieuw begrip bestaat niet.
- **Oplossing**:
  - Een koppeling waarvan het bewijs (de element-hash) bij opvolging gelijk is, houdt haar beoordeling. Alleen een
    gewijzigd bewijs wordt open.
  - `combineer` krijgt een keuze: `naam_als_alternatieve_term` (standaard aan, zodat het gedrag gelijk blijft voor wie
    het niet kiest). De werkplek vraagt het bij samenvoegen.
  - Een route "samenvoegen tot nieuw begrip" die in één transactie `nieuwe_betekenis` en `combineer` doet, met één
    revisie per begrip.
- **Waarom generiek**: het gaat om het onderhoud van elk begrip.
- **Meten**: api-tests. Op acceptatie in een testwerkgebied het aantal handelingen voor een samenvoeging: nu vier, daarna
  één.
- **Prioriteit en omvang**: P2, M (api en werkplek).

**L-3a-4 — Het skelet van een regel belandt in de toelichting van het begrip, en raakt verouderd**

- **Wat**: het geaccordeerde begrip *bepalen van het termijnbedrag* (27426263) draagt in zijn toelichting de hele regel
  als vrije tekst, met id's, invoer en uitvoer. Het eindigt met "Concept tot de jurist R5 accordeert." Het begrip is
  geaccordeerd (gelezen met `begrip_lezen`). De gegevensspecialist liet de zin staan "om geen extra revisie na het
  accorderen te maken" (19:24:52). Een voorbeeld zegt "€ -300.000 en 7 termijnen", terwijl de regel zonder teken rekent.
- **Activiteit**: 3a en 3b.
- **Oorzaak**: er is geen regelobject (L-3b-1), dus het skelet heeft geen eigen plek.
- **Oplossing**: L-3b-1. Daarnaast een aandachtspunt bij accorderen: een toelichting die het woord "concept" of
  "tot … accordeert" bevat terwijl het begrip geaccordeerd wordt. Dat is klein en vangt een vorm van verouderde tekst.
- **Prioriteit en omvang**: P3, S (api).

### Fouten in de methode of de skill

**M-3a-0 — Een tussenresultaat krijgt een begrip; #1760 zegt het omgekeerde**

- **Wat**:
  - #1760 (open) voegt aan de skill (`references/begrippen.md`, SKILL.md §D) toe dat een tussenresultaat van een
    afleidingsregel zonder formulering geen begrip is, "tot er een formulering is die het aanduidt".
  - Het team volgde die lijn in Termijnen: "Geen beslisregel *termijnregime*, en geen tussenbegrip *maandnummer van de
    dagtekening* … Een tussenresultaat zonder eigen formulering wordt geen begrip" (teamrapport §6).
  - De methode zegt het tegendeel. Een tussenresultaat krijgt een begrip, zodat de berekening uitvoerbaar en uitlegbaar
    is, en het oude tussenresultaat blijft bewaard (M01 §2.2.2 en h.6 bij art. 43 Zvw; M02 §1.2; §0 punt 1 hierboven).
  - Wat de methode wél eist, is een grondslag in de bron (M03, analyseresultaat 17). Dat deel van #1760 klopt.
- **Oplossing**: #1760 bijstellen vóór de merge.
  - De regel wordt: **geen begrip zonder grondslag in een gemarkeerde formulering.** Het begrip hangt aan een passage
    die het aanduidt (de gewone koppeling), óf aan de afleidingsregel die het afleidt.
  - Voor dat tweede geval komt er een koppelrol `afgeleid`, op de markering van de afleidingsregel. Het begrip is dan
    de uitvoer van die regel.
  - Een impliciet element (§0 punt 1) hangt aan de formulering waarvoor het nodig is, met een open punt van de soort
    interpretatie of ontbrekend uitvoeringsbeleid (L-X-1).
  - De api-guard blijft: `maak` weigert zonder koppeling, en de laatste koppeling gaat er niet af. Ze telt `afgeleid`
    mee.
  - De zin over het tussenresultaat in de skill wordt vervangen door de regel van het boek, in eigen woorden.
- **Waarom generiek**: het is de regel van de methode zelf. Elk werkgebied met een berekening in meer stappen heeft
  tussenresultaten (het boek laat het zien aan de Wet IB 2001, de Zvw en de Awb).
- **Meten**: geen gedragsmeting. Het is een regel in de api en tekst buiten de methodemarkers; dat ga ik na. De toets
  is dat de tussenbegrippen uit de proef op papier (*termijnregime*, *maandnummer van de dagtekening*) met de rol
  `afgeleid` te maken zijn, en een begrip zonder enige koppeling niet.
- **Prioriteit en omvang**: P1, S.
- **Stand**: gebouwd in #1760 (19 nov 2026), op verzoek van de gebruiker. Daarin zitten de koppelrol `afgeleid` (alleen
  op een Afleidingsregel, 422 `geen_afleidingsregel`), de poort, de projectie, de SHACL-vorm, het rapport en de
  frontendtypen, en de tekst in de skill en in `api/CLAUDE.md`. Het impliciete element (open punt) volgt met L-X-1.

**M-3a-1 — Een operatorbegrip ontstaat bij een formulering, niet in een lijst vooraf**

- **Wat**:
  - Het team miste drie operatoren ("tellen van maanden", "tijdsduur na tijdstip", "gedeeld door"). Ze kregen geen
    begrip, want "er is geen gemarkeerde formulering die ze aanduidt" (teamrapport §4).
  - Dat volgt de methode. "zes weken na de dagtekening" en "telkens een maand later" zijn Tijdsaanduidingen: bij twijfel
    gaat de tijdsaanduiding als meest specifieke klasse voor (M04 H2 *Tijdsaanduiding*; SKILL.md, *Samenloop*). De
    uitdrukkingswijzen van een operator (M04 H2 *Operator*) noemen geen datumrekenen.
  - B5 in `plan-begrip-per-formulering.md` wil daarnaast een vaste set operatoren "als geaccordeerde begrippen met
    herkomst 'methode'" in het generieke kader, zonder passage.
- **Wat de methode zegt** (§0 punt 2): je maakt een operatorbegrip bij een formulering die een bewerking uitdrukt, en
  hergebruikt het daarna voor elke formulering met dezelfde betekenis. Het taalpatroon van de regel ("moet berekend
  worden als", "is") is geen begrip.
- **Oplossing**:
  - **B5 bijstellen.**
    - De vaste lijst in de skill (`operatoren.json`) wordt een **lijst met namen en uitdrukkingswijzen**: het voorstel
      dat de keten doet als ze een operatorformulering ziet. Het zijn geen begrippen vooraf.
    - Het operatorbegrip ontstaat bij de eerste gemarkeerde formulering, met die passage. Daarna is het generiek
      (ADR-006): elk volgend werkgebied hergebruikt het met een eigen passage.
    - Zo blijft "geen begrip zonder grondslag" ook voor operatoren gelden, zonder uitzondering.
  - **Datumrekenen zonder operatorformulering.** De methode zegt niet hoe een regel een tijdsduur bij een tijdstip
    optelt als de tekst daar geen operator voor heeft. De tijdsaanduiding krijgt een begrip, en de afleidingsregel die
    het tijdstip afleidt, noemt de bewerking in haar taalpatroon. Of daar een vaste woordenlijst voor nodig is, is een
    projectkeuze. Die hoort bij het ontwerp van de regel (D1, `plan-afleidingsregels-in-lex.md`), niet bij de
    begrippen. Ik maak er geen operatorbegrip van.
  - **De keten**: L-2-1 en L-2-2 stellen bij zulke vormen een Afleidingsregel met een Tijdsaanduiding als invoer of
    uitvoer voor, geen Operator.
- **Waarom generiek**: dit is de werkwijze van het boek.
- **Prioriteit en omvang**: P1 als bijstelling van B5 (het bepaalt D1 en B5), S (docs en skill). De keten valt in
  bundel 3.

**M-3a-2 — Een begrip met twee tellingen, en een begrip dat te smal is**

- **Wat**:
  - "aantal resterende maanden van het jaar" (a91e3bd1) droeg in één definitie de telling "na de maand" (lid 5) en "met
    inbegrip van die maand" (lid 6). "de waarde hangt af van de soort aanslag zonder dat het begrip dat als kenmerk
    draagt" (19:01:53).
  - "vervaldag" (d9d0e191) was gedefinieerd voor een termijn van een voorlopige aanslag. Passages die over elke aanslag
    gaan (art. 9 lid 1, Leidraad 9.5), konden er niet aan. Dat vroeg een opvolger (19:05:57).
- **Oplossing**: twee regels in `references/begrippen.md`, in eigen woorden:
  - *een definitie die per geval een andere waarde geeft ("bij A …, bij B …"), zijn twee begrippen of één begrip met
    een kenmerk*;
  - *formuleer de definitie uit alle passages met deze term in het werkgebied, niet uit de eerste*.

  In Lex helpt B4 (een groep van één, koppelen aan een bestaand begrip): een passage die op een bestaand begrip lijkt
  maar breder is, komt dan als voorstel "koppel aan …?" en maakt het verschil zichtbaar.
- **Prioriteit en omvang**: P3, S (skill).

**M-3a-3 — Een bedrag met teken**

- **Wat**: "bij een negatieve voorlopige aanslag is invoer 1 … negatief. De deling geeft dan een negatief termijnbedrag …
  Elke teruggaaf zou dan in één keer gaan, en dat is fout" (19:09:22). De oplossing was een revisie "zonder teken".
- **Oplossing**: dit is precies de soort (D5 en B8). Een bedrag is *met teken* of *zonder teken*. Het voorstel is de
  soort met die waarde als eerste eigenschap van B8. Het besluit over P15 ligt al bij de gebruiker.
- **Prioriteit en omvang**: P2, hoort bij B8.

## 6. Activiteit 3b: afleidingsregels

### Fouten van Lex

**L-3b-1 — De afleidingsregel heeft geen plek in Lex**

- **Wat**: acht regels, waarvan zeven geaccordeerd, vier beslistabellen en twee parameters met hun waarde per tijdvak.
  Ze staan alleen in het logboek en in een document. Het teamrapport §7: "D1, de regel als eigen object, is de grootste
  ontbrekende stap … Een beslistabel (één uitvoer, rijen die elkaar uitsluiten) moet een vorm van D1 zijn." Een regel
  op een heropende laag is niet te zien (19:13:17, punt b).
- **Activiteit**: 3b.
- **Oorzaak**: D1 is nog niet gebouwd (`plan-afleidingsregels.md`, fase 3).
- **Oplossing**: D1, D2, U3, U4 en R1 uit het plan, met wat de proef eraan toevoegt:
  - **De beslistabel is de basisvorm.** Een regel heeft één uitvoer en één of meer rijen. Elke rij heeft eigen
    voorwaarden, invoer, bewerking en dragende markeringen. Een rekenregel zonder rijen is een tabel met één rij. Alle
    beslistabellen van Termijnen (R1, R4, R5 en R7) passen in die vorm.
  - **Een regelbegrip per uitvoer**: het regelbegrip ("bepalen <uitvoer>") hoort bij de regel, niet bij een rij
    (L-3a-1).
  - **De regel gebruikt de parameter, niet de waarde.** De waarde is een parameterwaarde met een eigen begrip, een
    tijdvak (geldig van/tot), een vindplaats en de getoetste toestand (§0 punt 4, L-3a-2).
  - **De bewerking is een operatorbegrip** op een gemarkeerde formulering (M-3a-1). Het taalpatroon ("moet berekend
    worden als", "indien aan alle volgende voorwaarden is voldaan") hoort bij de regelvorm, en is geen begrip.
  - **Een tussenresultaat is een eigen regel met een eigen uitvoerbegrip** (rol `afgeleid`, M-3a-0). Zo krijgt het
    termijnregime uit de proef op papier weer een plek.
  - **Bewijsstand per dragende markering**, net als bij een begripskoppeling. Een heropende of gewijzigde laag zet de
    regel op "herbeoordelen", zichtbaar op de regel.
  - **De regeltekst wordt afgeleid**, zoals in het plan. De taalpatronen van de methode komen in de skill.
- **Waarom generiek**: elk werkgebied met een rekenregel of beslisregel heeft dit nodig. De vorm komt uit de methode
  (M01 h.3 stap 3b), niet uit Termijnen.
- **Meten**:
  - Het hele 3b-resultaat van Termijnen moet in het object passen, zonder vrije tekst voor skelet of parameters. Dat is
    de ontwikkelset.
  - WA TRM H1 is de tweede set.
  - Daarna een blinde ronde op een ander werkgebied met het team van drie agents. Maat: het aantal regels of velden dat
    buiten het object moest.
- **Prioriteit en omvang**: P1, L (api, BFF, werkplek en rapport). Eerst Fase 0 uit het plan: een ADR voor het
  regelartefact, met M-3a-1 erin.

**L-3b-2 — Een regelskelet compact lezen kan niet**

- **Wat**:
  - "De MCP-tool weergave_lezen gaf op art. 9 lid 5 62.000 tekens terug, en werkgebied_lezen met bron_iri geeft het hele
    dossier opnieuw mee" (19:13:17, punt d).
  - Het teamrapport: de lijst van begrippen zonder id is ruim 300.000 tekens.
  - De gegevensspecialist gebruikte ongeveer 396.000 tokens voor 39 aanroepen.
  - Elke koppeling draagt `bewijs` en `bewijs_bij_koppelen`, ook als die gelijk zijn: in het gelezen begrip 27426263
    staat drie keer hetzelfde bewijs dubbel.
- **Activiteit**: 2c en 3b (voor elke agent en elke MCP-client).
- **Oorzaak**:
  - `GET /v1/annotatie/weergave` kent `volledig` en `lijst` (`annotatie_v2.py:73`; `annotatie_v2_store.lijst_weergave`,
    r. 128). De lijst bevat alle relaties, ook afgewezen, en alle elementen van de laag.
  - Een vorm per afleidingsregel is er niet, terwijl `werkgebied_rapport.regelskelet_regels` (r. 883) het skelet al
    uitrekent voor het rapport.
  - Een koppeling geeft het bewijs bij koppelen altijd mee.
- **Oplossing**:
  - `GET weergave?vorm=skelet` geeft per afleidingsregel (en per rechtsbetrekking) de actuele relaties met hun
    eindpunt in één regel (klasse, tekst, begrip). De berekening komt uit het rapport, zodat er één skelet is.
  - `bewijs_bij_koppelen` alleen als het afwijkt van `bewijs`.
  - De acceptatie-MCP volgt (§7).
- **Waarom generiek**: het gaat om de vorm van een antwoord, voor elk werkgebied.
- **Meten**: tekens per aanroep op Termijnen, vóór en na (doel: één lid onder 8.000 tekens). Daarnaast het verbruik van
  een volgende 3b-ronde op een ander werkgebied.
- **Prioriteit en omvang**: P2, S (api).

**L-3b-3 — Lex stelt in 3b niets voor**

- **Wat**: alles wat het team deed, deed het zelf: de inventaris van de afleidingsregels, het skelet, de gaten, de
  regeltekst en de hiërarchie. Lex had er geen route voor.
- **Activiteit**: 3b.
- **Oorzaak**: A3 en A5 uit het plan bestaan nog niet.
- **Oplossing**: A3 (deterministisch een conceptregel uit een skelet) en A5 (regels lezen in het gesprek), na D1. De
  proef geeft de **volledigheidstoets** die A3 eerst moet doen, letterlijk de lijst die de regelspecialist bij elke regel
  afliep: uitvoer zonder begrip, invoer zonder volgorde, rechtsobject als invoer, voorwaarde aan de verkeerde drager,
  geen `uitzondering_op` bij "In afwijking van", twee regels met dezelfde uitvoer zonder uitsluitende voorwaarden,
  parameter zonder tijdvak. Die toets is ook zonder A3 waardevol, als signaal op de afleidingsregel in de werkplek (U2).
- **Waarom generiek**: elke toets rust op de catalogus en de kardinaliteit.
- **Meten**: de gaten die de toets op het skelet van Termijnen van vóór het herstel vindt, tegen de gaten die de
  regelspecialist noemde (logboek 19:00:30 tot en met 19:08:05). Recall en precisie.
- **Prioriteit en omvang**: de volledigheidstoets P2, M. A3 en A5 P2, L, na D1.

### Fouten in de methode of de skill

**M-3b-0 — In Termijnen is de methode strenger toegepast dan zij is**

- **Wat**: drie werkregels van het team staan niet in de methode, en ze hadden gevolgen.
  - **"Een regel rust op een AR-markering."** R5 en R6 werden daarom eerst afgewezen ("geen dragende AR-markering",
    19:13:17), en pas aanvaard toen de jurist nieuwe markeringen had gelegd. R8 (art. 24 lid 2) bleef afgewezen: "een
    bevoegdheid … onder voorwaarden, geen afleiding van een waarde".
    - Volgens M04 H2 en M02 §3.5.2b is een regel die bepaalt of een recht bestaat juist een beslisregel. De uitvoer
      bestond al: het begrip *bevoegdheid tot verrekening vóór het verstrijken van de betalingstermijn* (fb9f3866),
      zoals de gegevensspecialist zelf voorstelde (19:09:22).
    - Volgens M03 hoofdactiviteit 3 kan elk begrip een afleidingsregel hebben die het afleidt. De grondslag is de
      formulering die het begrip draagt, met haar voorwaarden.
  - **"Een tussenresultaat is geen begrip."** Dat is M-3a-0.
  - **"Een operator zonder formulering wordt geen begrip."** De formuleringen waren er wel (M-3a-1).
- **Oplossing**:
  - De reference `afleidingsregels.md` (M2) legt de grondslag van een regel vast zoals de methode die geeft. Een regel
    rust op de formuleringen die zijn uitvoer en zijn voorwaarden dragen: de Afleidingsregel-markering als die er is,
    en anders de formulering van het afgeleide begrip (ook een Rechtsbetrekking bij een beslisregel).
  - De regelspecialist (`.claude/agents/agent-regelspecialist.md`) en de briefing van het team volgen. Dat is
    testgereedschap, geen deel van Lex, maar het bepaalt wat de volgende proef meet.
  - Het teamrapport van Termijnen krijgt een naschrift: R8 is volgens de methode een beslisregel, en het termijnregime
    een tussenbegrip. Herstel op acceptatie alleen met akkoord, want Termijnen blijft in dit plan ongewijzigd.
- **Waarom generiek**: het gaat om de werkregels van elk team en van Lex zelf (D1 en A3 nemen dezelfde regel over).
- **Prioriteit en omvang**: P1, S (skill, docs en agentprofiel).

**M-3b-1 — Eén beslistabel per uitvoer**

- **Wat**: het team week af van de proef op papier: "Eén beslistabel per uitvoer in plaats van een regel per lid … Drie
  regelbegrippen voor dezelfde uitvoer geven drie identiteiten voor één gegeven" (teamrapport §6).
- **Oplossing**: dit wordt een regel in `references/afleidingsregels.md` (M2). Het plan afleidingsregels §4 wordt erop
  aangepast, zodat de proef op papier de werkwijze niet meer tegenspreekt.
- **Prioriteit en omvang**: P2, S (skill en docs).

**M-3b-2 — Ontbrekend beleid en interpretatiekeuzes hebben geen vaste vorm**

- **Wat**: negen interpretatiekeuzes (logboek 19:13:17) en zes punten ontbrekend beleid (19:13:01). Een paar
  voorbeelden: de afronding van het termijnbedrag, een dagtekening op de 29e tot en met de 31e, het tijdvak van de
  € 49. De methode vraagt ze expliciet te maken. Lex heeft er geen plek voor (L-X-1), en de skill geeft geen vorm.
- **Oplossing**: in de skill een vaste vorm per open punt:
  - de soort: interpretatiekeuze, ontbrekend beleid, onderzoekspunt of gat in de annotatie;
  - waar het aan hangt;
  - de lezingen (A/B/C) met hun grondslag;
  - de keuze en wie die maakte;
  - wat nog getoetst moet worden (bijvoorbeeld "niet getoetst aan de MvT").

  Dat is D4 uit het plan, verbreed.
- **Prioriteit en omvang**: P2, S (skill). De opslag is L-X-1.

## 7. Testgereedschap: de acceptatie-MCP

Dit is geen deel van Lex, maar het begrenst wat een agent kan beoordelen.

- **T-1 — `bron_lezen` leest geen Leidraad-divisie.** "bron_lezen kon 9.5 niet lezen ('Artikel 9.5 staat niet in deze
  toestand'), dus het citaat is alleen getoetst tegen de graaf" (19:05:34). Ook R6 en het tijdvak van de € 49 zijn
  daardoor niet tegen de officiële tekst getoetst.
  - **Oorzaak**: `tools/wetsanalyse-acceptatie-mcp/src/bron.ts:135–137` zoekt alleen `<artikel>`.
  - **Oplossing**: zoeken op de structuurelementen van de BWB-XML (artikel, divisie, en een onderdeel daarbinnen),
    met het label als nummer. De parser van de importer weet welke elementen dat zijn.
  - **Nagaan bij de bouw**: toetst de citaatcontrole van Lex zelf een Leidraad-citaat wel tegen de bron? Dat is hier
    niet nagegaan.
  - P2, S.
- **T-2 — `werkgebied_lezen` met `bron_iri` geeft het hele dossier mee.** `index.ts:228–237` haalt altijd werkgebied,
  dekking, elementen en audit op. Alleen de elementen worden gefilterd.
  - **Oplossing**: met `bron_iri` alleen de elementen van die bepaling, plus het skelet (`vorm=skelet`, L-3b-2).
  - P3, S.

## 8. Over de hele keten

**L-X-1 — Interpretatiekeuzes, ontbrekend beleid en gaten horen bij het werkgebied, niet in een logboek**

- **Wat**: zie M-3b-2 en L-DV-2. Op 18 nov waren het drie onderzoekspunten, op 19 nov negen interpretatiekeuzes en zes
  punten beleid. Alles stond in het logboek en in documenten. In de api heeft alleen de bronselectie een
  onderzoekspunt (`api/app/bronselectie.py`).
- **Oplossing**:
  - Een object *open punt* per werkgebied, met de vorm uit M-3b-2. Het hangt aan een deelvraag, markering, begrip of
    regel.
  - Een open punt heeft een status (open, gekozen, getoetst) en een audit.
  - Het rapport (ADR-009) krijgt een hoofdstuk, R3 uit het plan, verbreed.
  - Het bestaande onderzoekspunt van de bronselectie wordt een open punt van de soort onderzoekspunt.
  - Lex leest ze als context (`werkgebied_context.py`), zodat een volgend gesprek weet welke lezing gekozen is.
- **Waarom generiek**: de methode vraagt in elke analyse dat twijfel en aannames expliciet zijn (CLAUDE.md,
  *brongetrouwheid*).
- **Meten**: alle open punten van Termijnen moeten er zonder vrije tekst in passen.
- **Prioriteit en omvang**: P1, M (api, werkplek en rapport). Kan vóór D1, en D1 hangt eraan.

**L-X-2 — Een laag heropenen om één relatie te herstellen**

- **Wat**: "Een relatie of markering herstellen in een afgeronde laag vraagt heropenen en opnieuw accorderen (lagen 9
  lid 1, 5 en 7). Dat gaat goed" (19:13:17, punt b). Het werkt dus, maar elke reparatie aan een skelet vraagt twee
  extra statuswissels per laag. In deze proef waren dat zes lagen.
- **Oplossing**: niet het slot weghalen. Een relatiebesluit op een afgeronde laag krijgt de vorm "heropen, beslis en
  sluit" in één aanroep, met één revisie en de reden in de audit. Dat volgt het patroon van `akkoord: true` bij
  koppelen (#1748).
- **Prioriteit en omvang**: P3, S (api).

## 9. Voorstel voor de PR-volgorde, gebundeld

Elke bundel wordt samen getest en samen uitgerold (de werkwijze van `alles-samen-N`). Een bundel die het gedrag van Lex
verandert, wordt licht gemeten (één run, gerichte set). Drie runs alleen bij de annotatieketen, omdat het geel per run
sterk varieert.

0. **Gedaan**: M-3a-0 zit in #1760 ("geen begrip zonder grondslag", met de rol `afgeleid` voor een tussenresultaat).
1. **Bundel 1, de methode volgen** (alleen docs, skill en het agentprofiel):
   - M-3a-1 (B5 bijstellen), M-3b-0 (de werkregels van het team), M-1-1 (bron als eindpunt), M-2-1, M-2-2, M-2-3,
     M-3a-2, M-3b-1 en M-3b-2;
   - een ADR voor het regelartefact en de open punten (Fase 0 uit het plan afleidingsregels, met L-X-1 erin);
   - `plan-afleidingsregels.md` §4 en `plan-begrip-per-formulering.md` B5 bijgewerkt.

   Vraagt een besluit van de gebruiker. Tekst tussen de methodemarkers vraagt een meting.
2. **Bundel 2, kleine api-fixes en leesvormen** (geen gedrag van Lex):
   - L-2-3 (volgordeplek), L-2-4 (twee sleutels), L-3a-3 (opvolgen en samenvoegen), L-3a-4 (verouderde toelichting),
     L-X-2;
   - L-3b-2 (`vorm=skelet`, bewijs niet dubbel);
   - T-1 en T-2 in de acceptatie-MCP.

   Kan direct, los van bundel 1.
3. **Bundel 3, de keten voor 2b en 2c** (graph-qa, gemeten):
   - L-2-1 (vormen van een afleidingsregel), L-2-5 (tijdstip als waarde), L-2-6 (brondefinitieformules);
   - L-2-2 (het skelet). L-2-2 kan pas na M-1-1, voor de eindpunten van `uitzondering_op`.

   Meten op Termijnen en WA TRM H1, daarna blind.

   **Stand (19 nov 2026)**: gebouwd, met de toetsing per stap:
   - **L-2-1**:
     - *aantal*: elke telbare bijzin, op de parse;
     - *datum uit een duur*: een rechtsgevolg als toestand met een moment wordt een eigen AR-kandidaat;
     - *verdeling*: `jas.afleiding.verdeling`.
     - *Gevolg van een vergelijking* ("In dat geval …") is afgevallen. Het signaal wijst even vaak op een
       rechtsbetrekking, en de classifier ziet de voorwaarde al.
   - **L-2-5**: `TEMPORAL_VALUE` (V/T).
   - **L-2-6**: "wordt aangeduid als".
     - Bij het Leidraad-onderdeel is de oorzaak nu gelezen: 1.1.2 is een lijst "– term: omschrijving" onder de kop
       "Definities", zonder aanhef. Die kop bereikt de detector niet; `BronTekst.context` draagt alleen de tekst van
       de ouder.
     - Dat vraagt de kop in de snapshot en in de keten, en is een eigen stap.
   - **L-2-2**:
     - de invoer is de grootste waarde, met een `kenmerk` voor het rechtsobject erin;
     - de invoer staat op volgorde;
     - een ontkenning heeft één operand;
     - een voorwaarde gaat naar rechtsbetrekking én afleidingsregel samen.
     - De ariteit staat in de keten (`relaties.EEN_OPERAND`) en niet in `relaties.json`: het is een eigenschap van de
       operatorformulering, niet van een relatietype, en de api en de werkplek lezen haar niet.
     - `uitzondering_op`, `toepassing` en `tijd` wachten op M-1-1 (een bron als eindpunt).
   - **Gemeten**:
     - deterministisch met `eval.kandidaat_eval`, vóór en na, op v1 en concept. De recall is gelijk (0,90 en 0,69),
       er komen één à twee kandidaten bij, en de precisie gaat van 0,277 naar 0,274 en van 0,230 naar 0,229.
     - De sets bevatten deze vormen niet. De vormen zelf toetst `tests/annotatieketen/test_keten_vormen_termijnen.py`.
     - De meting van de keten met het model (drie runs, en de relatievoorstellen achter `relatieVoorstellen`) volgt
       na de uitrol, met een eigen akkoord.
4. **Bundel 4, open punten** (api, werkplek en rapport): L-X-1, L-DV-2, en L-1-2 voor zover het het signaal bij de
   dekking is. Na bundel 1.

   **Stand (19 nov 2026)**: L-X-1 is gebouwd in de api, de context van Lex en het rapport. Na toetsing gelden deze
   keuzes:
   - **De vorm**:
     - de soorten komen uit de skill (*Wat open blijft*), met een drift-test op de tekst;
     - een punt hangt aan een of meer regels, gevallen, markeringen, begrippen of deelvragen;
     - de lezingen dragen hun grondslag;
     - `te_toetsen` heeft een bronsoort;
     - de methode komt uit ADR-018 §6.
   - **Het besluit** loopt via één route van de jurist (`…/besluit`), vanaf elke plek. Het agent-token kan haar niet
     aanroepen. Gesprek-UI en kaart-UI komen niet in deze bundel.
   - **L-DV-2** is opgelost doordat één punt aan een deelvraag én een regel of markering kan hangen.
   - **Uitgesteld**:
     - Het onderzoekspunt van de bronselectie is sinds 20 nov 2026 een open punt (soort onderzoekspunt, aan de
       deelvraag). De poort leest het daar, en de oude plek in de voortgang wordt niet meer gebruikt.
     - Het signaal van L-1-2 hangt aan een relatie naar een contextbron. Die bestaat pas na M-1-1, dus het signaal
       schuift naar bundel 7.
5. **Bundel 5, begrippen naast regels** (api): L-3a-1 en L-3a-2. Daarna de volledigheidstoets van L-3b-3 als signaal op
   de afleidingsregel. Na bundel 3, want de signalen rusten op een betrouwbaar skelet.

   **Stand (20 nov 2026)**: gebouwd volgens ADR-018 besluit 7.6 en bijlage A §4.2.
   - **De volledigheidstoets**: zestien gaten uit de skill (`regelgaten.json`, gegenereerd, met een drifttest).
     - De gaten van de regelspecialist zijn er alle. Daarbij komen de zes van de methode, behalve "twee
       operatorbegrippen met dezelfde betekenis": die vraagt een oordeel over betekenis, geen vorm.
     - De toets zit op drie plekken: skelet, regel en keten.
   - **L-3a-1**: dit zit in de keten van de regels (`zelfde_uitvoer`, `regelbegrip_meer_uitvoeren`), en niet als
     heuristiek op de begrippen. Sinds R1 zijn regels objecten, dus daar is de uitvoer zeker.
   - **L-3a-2**: een homoniem in de alternatieve termen en een waarde in de definitie van een parameter worden
     aandachtspunten op het begrip.
   - **De datumregel uit de meting van bundel 3**: het tijdstip is de invoer (`DATE_ASSIGNMENT` noemt het,
     `relaties.py` legt het). Een uitvoer is er niet, want de datum heeft geen formulering.
6. **Bundel 6, de regel als object** (fase 3 uit het plan afleidingsregels): L-3b-1, met de beslistabel als basisvorm.
   Na bundel 1 en 4.
7. **Bundel 7, activiteit 1** (graph-qa en de vraagkaart): L-1-1 (schakelbepalingen op regelingniveau), en L-1-2
   (contextbron als eindpunt, na M-1-1). Staat los van 2–6 en kan parallel.

   **Stand (20 nov 2026)**: L-1-1 is gebouwd in `agent/schakelbepalingen.py`. De stap is deterministisch.
   - **De regel:** een bepaling buiten het zoekbereik die naar een regeling als geheel verwijst, in een zin over
     "(overeenkomstige) toepassing" zonder ontkenning, maakt haar regeling tot het voorstel "regeling erbij?".
   - **Waar:** in de vraagkaart van het zoekbereik, als optie die niet voorgeselecteerd is. In de bronselectie staat
     een zin met de bepaling erbij.
   - **Op de gegevens van acceptatie** (zoekbereik IW, AWR en de Leidraad): de Mijnbouwwet staat als eerste voorstel
     (art. 72, twee doelen). Daarna komt de Awir, een echte schakel naar de AWR die voor Termijnen niet nodig is.
   - **L-1-2:** wat kan zonder M-1-1, zit in bundel 5 (het gat `rust_op_contextbron`). Het signaal bij de dekking voor
     een contextbron waarnaar een relatie wijst, vraagt een relatie met een bron als eindpunt. Dat blijft open tot het
     besluit over M-1-1.
8. **Daarna**: A3 en A5 (Lex stelt regels voor en leest ze), en B8 met de soort, na een besluit over P15.

**Waarom deze volgorde**

- Bundel 1 beslist wat D1 en B5 worden. Zonder dat besluit bouw je twee keer.
- Bundel 2 haalt nu al het meeste handwerk weg, zonder risico voor het gedrag.
- Bundel 3 maakt het skelet betrouwbaar. Elk signaal en elke regel daarna rust erop.
- De regel als object (bundel 6) komt pas als het skelet en de open punten er staan. Dan past wat de proef opleverde er
  zonder vrije tekst in.

## 10. Wat dit plan bewust niet doet

- Geen uitzondering voor een artikel, begrip of werkgebied. Ook geen herstel van de data van Termijnen: de jurist heeft
  het skelet daar al met de hand hersteld.
- Geen RegelSpraak, geen feitmodel en geen voorbeeldreeksen. Dat is activiteit 4 en later (fase 5 van het plan
  afleidingsregels).
- Geen herhaling van de zoekstappen uit `onderzoek-bronselectie-termijnen-2026-11.md`.
- Geen wijziging op acceptatie. Alles hierboven is gelezen, niet geschreven.

## 11. Wat niet is nagegaan

- Waarom het Leidraad-onderdeel 1.1.2 onder 10 niet als Brondefinitie herkend werd (L-2-6).
- Of de voorwaarde in lid 5 door de regel in `_voorwaarde` aan de verkeerde drager hing, of later met de hand zo gelegd
  is (L-2-2).
- Of de citaatcontrole van Lex een Leidraad-citaat tegen de officiële tekst toetst (T-1).
- De werkgebieddata op acceptatie zijn niet opnieuw in hun geheel gelezen: één lid lezen kost al 62.000 tekens.
  Bevindingen uit de data komen uit het logboek van de run en uit één begrip (27426263).
