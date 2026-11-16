# Plan: volwaardige agentprofielen (ADR-016 §A2)

Soort: *plan* (15 nov 2026), gebouwd op akkoord van de gebruiker als PR-stapel `claude/agentprofielen-1…5` (zie
*Stand na het bouwen*), nog niet gemeten. Het hoort bij [ADR-016](adr-016-centrale-agent-en-werkplaats.md) §A2 en
§A5. Het volgt op de eindmeting A6 ([`metingen/centrale-agent-2026-11-15-a6-eind/a6-eind.md`](metingen/centrale-agent-2026-11-15-a6-eind/a6-eind.md)).
Bouwen begint pas na akkoord van de gebruiker en na de laatste fixronde van A6 (PR #1560). Zolang die loopt, raakt dit
plan graph-qa niet aan.

## Stand na het bouwen (15 nov 2026)

Gebouwd zoals hieronder, met vier afwijkingen die tijdens het bouwen bleken:
- **Er was al een tokenplafond per subagent:** `MAX_TOKENS_SUBAGENT = 300_000` (`nodes/antwoord.py`). Het veld
  `budget` vervangt dat per profiel. Geen profiel komt erboven: de budgetten zijn 300k (rechtspraak, wetsgeschiedenis,
  algemeen) en 260k (bepalingen). De eerder voorgestelde 340k en 350k gelden niet. De metingen van run 3 lagen dus
  tegen dat plafond aan, niet eronder.
- **Geen rekening met de supervisor** (besluit van de gebruiker, 15 nov 2026: "We stappen af van supervisor"). Er komt
  geen overgangslijst `SUPERVISOR_SPECIALISTEN`. De supervisor kiest uit de namen die zijn eigen prompt noemt
  (`supervisor._QA_SPECIALISTS`, in de code naast die prompt). Dat verdwijnt met de supervisor.
- **`duiding` blijft bestaan**, met `kiesbaar: false`, want routes in code gebruiken het (advies bij een markering, een
  genoemd stuk lezen). **`definitie` blijft voorlopig ook**, met `kiesbaar: false`: alleen de supervisor gebruikt het,
  en met het profiel zou de methoderol `definitie` zonder aanroeper vallen. Het profiel en de rol vervallen samen met de
  supervisor.
- **De rondegrens per profiel staat in de subagentinstructie**, in het voorvoegsel. Dat voorvoegsel is toch al per
  profiel verschillend, dus de cache lijdt er niet onder.

## Waarom

De gebruiker vroeg of de profielen er goed in zitten, en vergeleek ze met Claude Code. Daar is een subagent een
beschrijving, een instructie, tools, een model, skills en `maxTurns`. Lex heeft acht profielen, en de velden staan in
`bronmodel.agentprofiel`. Maar een deel van die velden doet nog niets.

## Wat er nu is (stand 15 nov 2026, `e95b1163`)

**De profielen:**
- kiesbaar: `algemeen`, `definitie` en `duiding`. Dat zijn de specialisten van de supervisor onder een nieuwe naam;
- niet kiesbaar: `centraal`, `centraal_breed`, `retrieval`, `annotaties_lezen` en `begrippen_lezen`.

**Velden die op papier bestaan maar geen effect hebben:**
1. **`skills`** gebruikt geen enkel profiel. Er is ook geen code die een skill vooraf laadt: alleen
   `CentraleAgent.systeemtekst` zet de beschrijvingen van de skills erin (niveau 1). Een subagent heeft geen
   `laad_skill`, want `Subagent` heeft geen eigen tools.
2. **`max_rondes`** staat overal op `None`. De code leest het veld niet: `nodes/antwoord.max_rondes` neemt voor elke
   subagent `agentvorm.MAX_RONDES_SUBAGENT = 8`.
3. **`budget`** staat overal op `None`. De code leest het veld niet: elke subagent heeft `MAX_TOKENS_SUBAGENT = 300_000`
   (ontdekt bij het bouwen), naast het plafond van de hele opdracht
   (`DELEGATIE_AANDEEL`, een kwart van wat de gebruiker die week nog heeft) en het stukkenplafond van de centrale agent
   (`MAX_STUKKEN_CENTRAAL = 6`).
4. **`modelklasse`** (`model:` in de frontmatter) is sinds #1544 vervangen door de modelkeuze per `agent:<profiel>` in
   het beheer. Het veld staat nog in de validator en in de catalogus (`catalogus.py:137`).

**Twee koppelingen die in de weg zitten:**
5. **`kiesbaar` stuurt twee dingen tegelijk.** `profielen.KIESBAAR` is zowel de lijst van de supervisor
   (`supervisor._QA_SPECIALISTS`) als de keuzelijst van de overdracht `subagent`. Een nieuw kiesbaar profiel zou dus ook
   een specialist van de supervisor worden, en daarmee verandert productie, waar de vlag op `uit` staat.
6. **De centrale agent kiest niet op beschrijving.** Het schema van `subagent` geeft alleen de namen
   (`subagent.invoer_schema`: "Geen beschrijving per profiel"). Welk profiel bij welk werk past, staat met de hand in de
   instructie van `centraal`: "Profiel: duiding voor uitleg bij bepalingen, definitie voor een begrip, algemeen voor de
   rest en voor bronnen naast de wet." Een nieuw profiel vraagt dus een wijziging van die zin, en een profiel uit de
   werkplaats (B5) zou daar nooit in komen.

**En een botsing in de instructie:** `duiding` en `algemeen` zeggen "je rondt als laatste stap af met een sjabloontool"
(`antwoord_duiding`, `antwoord_bepaling`). Als subagent zegt `SUBAGENT_INSTRUCTIE` het tegenovergestelde: "niet met een
antwoordsjabloon". Dat werkt, omdat de subagentregel later staat, maar het profiel is daardoor niet wat het lijkt.

## Wat de metingen laten zien

Alle kinderen van 15 nov 2026 (`centrale-agent-2026-11-15-*/…-kinderen.jsonl`, 34 kinderen, vijf runs). Ingedeeld naar
het werk dat ze deden, afgeleid uit hun tools. Tokens zijn ruw, het volle promptvolume, zoals het budget telt.

- **Rechtspraak lezen** (`zoek_uitspraken`, `get_uitspraak`): 15 kinderen, allemaal met profiel `algemeen` (of nog
  zonder profielnaam in run 2).
  - Mediaan **280k**, van 245k tot 295k.
  - Rondes: mediaan 7, hoogstens 8. Per kind gemiddeld 6 à 7 `get_uitspraak`.
  - Opdrachten: S01, F01, F02, M06, P01, P02, D01.
- **Wetsgeschiedenis lezen** (`zoek_kamerstukken`, `get_kamerstuk`): 5 kinderen, `algemeen`.
  - Mediaan **256k**, van 234k tot 270k.
  - Rondes: mediaan 8, dus altijd de grens.
  - **V03 faalde hier.** Het kind vond drie MvT's (kst-36369-3, kst-36207-3, kst-36309-3), maar las ze niet
    "wegens rondegrens". Zijn 18 aanroepen waren 6 × `zoek_kamerstukken`, 3 × `search_wetgeving`, `inhoudsopgave`,
    `zoek_opbouw`, 5 × `get_artikel` en 2 × `get_lid`, en geen enkele `get_kamerstuk`. Het brede profiel liet hem in de
    wettekst zoeken in plaats van lezen.
- **Bekendmakingen lezen** (`zoek_bekendmakingen`, `get_bekendmaking`): 3 kinderen, `algemeen`. Mediaan **188k**, van
  152k tot 302k. Opdrachten: S05 en M06.
- **Een reeks bepalingen duiden** (`get_bepaling`, `get_artikel`, `get_lid`, `zoek_opbouw`): 11 kinderen, `duiding`.
  - Mediaan **165k**, van 119k tot 210k.
  - Rondes: mediaan 7, hoogstens 8.
  - **S04 haalde de reeks niet.** Het las 22.1–22.8.8 (20 aanroepen in 8 rondes), en zegt eerlijk dat 22.8.9–22.8.12 en
    22.9.x niet gelezen zijn.
- **Een begrip** (`definitie`): **0 van de 34.** Een begripsvraag beantwoordt de centrale agent zelf met
  `antwoord_begrip`. Ook in de agentset verwacht geen opdracht het profiel `definitie`.

Wat eruit volgt:
- **Het werk is taakgericht, het profiel is breed.** 23 van de 34 kinderen deden één soort bronwerk met `algemeen`, dat
  alle tools van de open laag heeft (geen `tools`-lijst), en 18 schema's meestuurt die ze niet gebruiken.
- **De rondegrens bindt waar gelezen moet worden** (V03, S04). Waar het kind klaar was (rechtspraak), lag het al tegen de
  grens: meer rondes geven is daar niet nodig.
- **De kosten per ronde verschillen per bron**: ongeveer 37k bij rechtspraak, 32k bij Kamerstukken en 22k bij
  bepalingen (mediaan van ruw ÷ aanroepen). Een uitspraak is lang. Eén grens voor alle profielen past dus niet.
- **Alle 34 eindigden met `klaar`**, en de profielkeuze was 19/19 goed. De vorm werkt. Wat ontbreekt, is wat een profiel
  per taak meegeeft.

## Besluiten die dit plan voorstelt

1. **Drie taakprofielen voor de subagent**, elk met een smalle toolset, eigen connectors, een eigen instructie en eigen
   grenzen: `rechtspraak_lezen`, `wetsgeschiedenis_lezen` en `bepalingen_duiden`.
2. **`algemeen` blijft het brede profiel**, zoals A2 zegt ("Past geen profiel, dan kiest de centrale agent
   `algemeen`"). Het krijgt expliciete grenzen, gelijk aan wat nu feitelijk geldt.
3. **`definitie` en `duiding` worden niet-kiesbaar als subagent.** Ze blijven specialisten van de supervisor zolang die
   bestaat: productie staat op `uit` en draait de supervisor. Daar blijven ze bitgelijk. Na het besluit van A7 en de
   omzetting van productie vervallen ze (een eigen PR, met de supervisor).
4. **De supervisor krijgt een eigen, vaste lijst** (`definitie`, `duiding`, `algemeen`), los van `kiesbaar`. `kiesbaar`
   betekent daarna alleen wat A2 zegt: de centrale agent mag het profiel kiezen.
5. **De centrale agent kiest op beschrijving.** Het schema van `subagent` krijgt per profiel zijn `description`. De zin
   "Profiel: duiding voor …" in `centraal` en `centraal_breed` wordt: "Kies het profiel op zijn beschrijving; past er
   geen, kies algemeen." Een profiel uit de werkplaats doet dan vanzelf mee.
6. **`max_rondes` en `budget` doen wat ze zeggen.** Ontbreekt het veld, dan gelden de codedefaults, dus gedrag blijft
   gelijk tot een profiel een waarde noemt. Het budget is een vangnet, geen doel: bij het budget krijgt het kind nog één
   ronde, alleen voor het rapport, zoals nu bij de rondegrens.
7. **Geen profiel krijgt in deze stap skills vooraf** (onderbouwing onder *Skills*). Het mechanisme wordt wel gebouwd,
   zodat B5 en een later JRM-profiel het kunnen gebruiken.
8. **`modelklasse` verdwijnt uit het profiel.** Het model staat in het beheer (`agent:<profiel>`, #1544). De regel
   `model:` in een concept uit de werkplaats is alleen een voorstel aan de beheerder (plan Aanpassingen): de werkplaats
   leest hem, het register niet.

## Waarin de profielen van elkaar verschillen

De gebruiker (15 nov 2026): "ik wil dat je nette profielen maakt die echt waarde toevoegen en onderscheidend zijn van
elkaar." De toets per profiel is daarom: wat kan dit profiel dat een ander niet kan, en welke fout uit de meting
voorkomt het? Een profiel dat alleen een smallere toollijst heeft, haalt die toets niet.

Elk kiesbaar profiel is op vier punten anders:
- **een eigen bron**: geen twee taakprofielen delen een connector;
- **eigen vakkennis in de instructie**: hoe die bron is opgebouwd en hoe je erin leest;
- **een eigen vorm van oplevering**: per uitspraak, per stuk of per bepaling;
- **eigen grenzen**: de kosten per ronde verschillen per bron.

Per profiel:
- **`rechtspraak_lezen`: uitspraken.**
  - *Vakkennis*: de rangorde van de instanties (Hoge Raad, hof, rechtbank); het verschil tussen een arrest en een
    conclusie van de A-G, die geen rechtspraak is maar wel gezag heeft; dat de kern in de rechtsoverwegingen staat en
    niet in het procesverloop.
  - *Oplevering*: per uitspraak het ECLI, de instantie, de kern en een passage uit de r.o.
  - *Lost op*: de citaten zonder inhoud uit run 3 (procedurezinnen bij P02, trefwoorden van een conclusie bij P01).
- **`wetsgeschiedenis_lezen`: de totstandkoming.**
  - *Vakkennis*: dossier en stuknummer; welk stuk wat is (MvT, nota naar aanleiding van het verslag, nota van wijziging,
    amendement); de route van wijziging via versie naar dossier en Staatsblad; dat de MvT bij de bepaling hoort die ze
    invoerde, niet bij de huidige tekst.
  - *Oplevering*: per stuk de vindplaats, wat het over de bepaling zegt en een passage.
  - *Lost op*: V03, waar het kind de MvT's vond maar in de wettekst bleef zoeken.
- **`bepalingen_duiden`: een reeks bepalingen in de wet of een beleidsregel.**
  - *Vakkennis*: de opbouw (hoofdstuk, afdeling, artikel, lid, onderdeel); de decimale nummers van een beleidsregel
    (22.8.9 hoort bij artikel 22 van de wet); eerst de reeks vaststellen, dan lezen.
  - *Oplevering*: per bepaling de kern en een passage, en de nummers die hij niet las.
  - *Lost op*: S04, waar de reeks niet af kwam en ook niet vooraf vaststond.
- **`algemeen`: de rest.** Bronnen door elkaar, de standpunten van de kennisgroepen, of werk waarvoor geen taakprofiel
  bestaat. Het onderscheidt zich door breedte: hij is het vangnet, geen taakprofiel, en de centrale agent kiest hem
  alleen als er geen ander past.

Wat hier bewust niet bij staat:
- **Geen profiel per connector zonder vakkennis.** `kennisgroepen` en `wetgeving_live` krijgen geen eigen profiel: er is
  geen opdracht in de metingen die het vraagt, en geen leeswijze die anders is dan wat `algemeen` en
  `bepalingen_duiden` al doen.
- **Geen `definitie` als subagent.** Een begripsvraag is één of twee toolrondes, en dat doet de centrale agent zelf.

## De tools: per profiel de leesweg, en niets daarbuiten

**Wat de tools nu kosten.** Gemeten op `e95b1163` als de lengte van naam, beschrijving en schema (ongeveer vier tekens
per token). De open laag heeft 38 tools, samen ongeveer **16.800 tokens**. `algemeen` heeft geen `tools`-lijst en krijgt
als subagent dus allemaal, ook de JAS-, annotatie- en begrippentools. Die staan in elke ronde in het voorvoegsel.
- Bij 8 rondes is dat ongeveer 135k van de ruwe 260k van een gemiddeld `algemeen`-kind. Dat is een schatting: de
  toolresultaten groeien er nog bovenop.
- De connectortools zijn de grootste schema's:
  - `zoek_uitspraken` ~1.330 tokens;
  - `zoek_kamerstukken` ~1.050;
  - `zoek_bekendmakingen` ~1.010;
  - `zoek_standpunten` ~990.
- De graaftools zijn klein: `get_artikel` ~275, `get_bepaling` ~250, `get_regeling_info` ~140.

**De regel voor een taakprofiel:** het krijgt precies de tools van zijn leesweg, en een tool die op die weg niet nodig
is, komt er niet bij. Een smalle toolset is daarbij geen doel op zich. Hij doet twee dingen:
- de instructie kan de weg voorschrijven, omdat er geen zijpad openligt (V03 zocht in `inhoudsopgave` en `zoek_opbouw`);
- het voorvoegsel blijft klein.

**De drie leeswegen**, afgeleid uit wat de tools kunnen. De connectors zijn gebouwd om per bepaling te zoeken, maar de
kinderen gebruikten dat niet:
- **Rechtspraak.**
  - `zoek_uitspraken(bwb_id, artikel)` geeft de uitspraken die dat artikel noemen (LiDO), te filteren op `instantie` en
    `soort` (uitspraak of conclusie).
  - Daarna lees je ze naast elkaar met `get_uitspraak`. Bij een lange uitspraak eerst `inhoud: true`, en dan met de
    offset naar de rechtsoverwegingen.
  - In run 3 lazen de kinderen één uitspraak per ronde, na elkaar (zie `a2-toolgegevens`). Hier zit de winst.
- **Wetsgeschiedenis.**
  - `geldigheid(bwb_id, artikel)` geeft het Kamerdossier van de wet die de huidige tekst invoerde (`dossiersBepaling`)
    en de Stb.
  - Met dat dossier geeft `zoek_kamerstukken(dossier, soort: "memorie van toelichting")` de stukken.
  - `get_kamerstuk(id, woorden: "<artikel>")` geeft alleen de alinea's over die bepaling, in plaats van een hele MvT.
  - `zoek_bekendmakingen(bwb_id, artikel)` en `get_bekendmaking(id, artikel)` laten zien wat een wijziging aan die ene
    bepaling veranderde.
  - V03 riep `geldigheid` niet aan, zocht zes keer op titel, en las niets.
- **Een reeks bepalingen.**
  - `inhoudsopgave(bwb_id, vanaf)` of `zoek_opbouw` om de reeks vast te stellen.
  - Daarna `get_bepaling`, `get_artikel` en `get_lid` naast elkaar.
  - De `duiding`-kinderen gebruikten precies deze zes tools, en `get_context` en `follow_verwijzingen` geen enkele keer.

**De tools en schemakosten per profiel** (zonder `rapport`, dat de agentvorm voor elk kind meegeeft):
- **`rechtspraak_lezen`, ~2,6k:** `search_wetgeving`, `get_artikel`, `zoek_uitspraken`, `get_uitspraak`.
  - Zonder `get_lid` en `list_regelingen`: een uitspraak hangt aan een artikel (LiDO koppelt geen leden), en
    `list_regelingen` vond in de metingen niets wat `search_wetgeving` niet vond.
- **`wetsgeschiedenis_lezen`, ~4,8k:** `search_wetgeving`, `get_artikel`, `geldigheid`, `zoek_kamerstukken`,
  `get_kamerstuk`, `zoek_bekendmakingen`, `get_bekendmaking`.
  - De bekendmakingen horen erbij, omdat de wijziging de brug is naar het dossier en naar wat er aan de bepaling
    veranderde.
- **`bepalingen_duiden`, ~2,0k:** `zoek_opbouw`, `inhoudsopgave`, `search_wetgeving`, `get_artikel`, `get_lid`,
  `get_bepaling`.
  - Zonder `wetgeving_live`: geen enkel kind gebruikte het, en een regeling buiten de graaf is werk voor `algemeen`.
  - Zonder `get_context` en `follow_verwijzingen`: de samenhang duidt de centrale agent zelf, met het rapport.
- **`algemeen`, ~16,8k:** ongewijzigd, zolang hij ook specialist van de supervisor is.
  - Na de supervisor krijgt hij een expliciete lijst: de lees- en zoektools en alle connectors, zonder de JAS- en
    annotatietools. Die horen bij de vaste routes (`annoteer`, `lees_annotaties`).
  - Dat is dan nog ongeveer 12k. Het staat op de lijst open punten.

**Geen twee taakprofielen delen een connector**, en elk van hun tools staat op hun eigen leesweg. Een gedeelde graaftool
zoals `get_artikel` is het anker naar de bepaling, geen overlap in taak.

**Wat dit voor het verbruik betekent:** de schatting is ongeveer 14k tokens ruw minder per ronde dan `algemeen`, alleen
al aan schema's. De budgetten hieronder zijn daarom **voorlopige plafonds**, gezet op het verbruik van run 3. De meting
stelt ze daarna bij op het hoogst gemeten verbruik van het profiel plus 15 %.

## De profielen

Per profiel de velden zoals ze in `.claude/lex-agents/<naam>.md` komen. De instructie staat hier als kern: de precieze
tekst volgt in de PR en wordt gemeten. Voor de grenzen is de regel:
- `budget` is het hoogst gemeten verbruik plus ongeveer 15 %, plus wat de extra rondes kosten;
- `max_rondes` is 8 (nu), plus 2 waar de rondegrens aantoonbaar de inhoud kostte.

### `rechtspraak_lezen` (nieuw, kiesbaar)

- **description:** "Doorloopt de uitspraken bij een bepaling of onderwerp en geeft per uitspraak de kern met een
  letterlijke passage."
- **methoderol:** `algemeen` (geleend: de basis en het taalniveau van wetsanalyse, byte-gelijk aan wat `algemeen` nu
  krijgt).
- **tools:** `search_wetgeving` en `get_artikel`. De connector geeft daarbij `zoek_uitspraken` en `get_uitspraak`.
- **connectors:** `rechtspraak`.
- **sjablonen:** geen. Een subagent rondt af met `rapport`, en dat geeft de agentvorm.
- **skills:** geen.
- **max_rondes:** 8. De rechtspraakkinderen kwamen in 7 tot 8 rondes tot een rapport, en meer rondes kosten hier het
  meest per ronde.
- **budget:** 300.000, gelijk aan het plafond dat er al was (gemeten tot 295k).
- **Kern van de instructie:**
  - zoek de uitspraken met `zoek_uitspraken` op `bwb_id` en `artikel`; op een onderwerp alleen als de opdracht geen
    bepaling noemt;
  - lees een lange uitspraak via `inhoud: true` en de offset van de rechtsoverwegingen;
  - noemt de opdracht geen aantal of selectie, kies dan de hoogste instanties eerst en zeg welke je liet liggen;
  - lees de uitspraken naast elkaar in één ronde;
  - geef per uitspraak het ECLI, de kern en één letterlijke passage (r.o.);
  - lees de wettekst hoogstens één keer, om de bepaling te verankeren.

### `wetsgeschiedenis_lezen` (nieuw, kiesbaar)

- **description:** "Zoekt en leest de wetsgeschiedenis bij een bepaling (memorie van toelichting, nota's, de
  bekendmaking in Staatsblad of Staatscourant) en vat per stuk samen wat het over de bepaling zegt, met een letterlijke
  passage."
- **methoderol:** `algemeen`.
- **tools:** `search_wetgeving`, `get_artikel`, `geldigheid`. `geldigheid` geeft het Kamerdossier van de wet die de
  huidige tekst invoerde. `inhoudsopgave` en `zoek_opbouw` niet: daarmee liep V03 vast.
- **connectors:** `kamerstukken`, `bekendmakingen`. Kamerstukken en de bekendmaking horen bij dezelfde totstandkoming,
  en S05 en M06 vroegen de bekendmakingen in die lijn.
- **sjablonen:** geen.
- **skills:** geen.
- **max_rondes:** 10. V03 strandde op 8, terwijl de stukken al gevonden waren.
- **budget:** 300.000, gelijk aan het plafond dat er al was. De twee extra rondes moeten uit het kleinere voorvoegsel
  komen.
- **Kern van de instructie:**
  - vind eerst het dossier met `geldigheid` op de bepaling, en pas daarna `zoek_kamerstukken` met `dossier`; op titel
    alleen als `geldigheid` geen dossier geeft;
  - lees met `get_kamerstuk(id, woorden: "<artikel>")` alleen de passages over de bepaling, en de stukken naast elkaar
    in één ronde;
  - zoek niet opnieuw zodra je de stukken hebt;
  - geef per stuk de vindplaats, wat het over de bepaling zegt en één letterlijke passage.

### `bepalingen_duiden` (nieuw, kiesbaar; neemt het werk van `duiding` als subagent over)

- **description:** "Doorloopt een reeks bepalingen (de artikelen van een hoofdstuk, de onderdelen van een beleidsregel
  bij een artikel) en geeft per bepaling de kern met een letterlijke passage."
- **methoderol:** `duiding`. De methodetekst blijft die van de rol `duiding`, byte-gelijk, dus er is geen
  methodemeting nodig (ADR-010).
- **tools:** `zoek_opbouw`, `inhoudsopgave`, `search_wetgeving`, `get_artikel`, `get_lid`, `get_bepaling`.
- **connectors:** geen.
- **sjablonen:** geen.
- **skills:** geen.
- **max_rondes:** 10. S04 had de laatste onderdelen niet gelezen bij 8.
- **budget:** 260.000 (gemeten tot 210k, plus twee rondes van ongeveer 22k).
- **Kern van de instructie:**
  - stel de reeks eerst vast (`inhoudsopgave` of `zoek_opbouw`), en lees dan per ronde zoveel bepalingen naast elkaar
    als je kunt;
  - geef per bepaling de kern en één letterlijke passage;
  - lukt de hele reeks niet binnen je grens, noem dan in `open` precies welke nummers je niet las.

### `algemeen` (blijft, kiesbaar)

- Alle velden blijven zoals ze zijn. De instructie verandert niet, omdat hij ook de specialist van de supervisor is.
- **Nieuw:** `max_rondes: 8` en `budget: 300000`. Dat is precies wat nu geldt (de codedefault 8), plus een vangnet boven
  het hoogst gemeten verbruik (302k). Als specialist van de supervisor leest hij die velden niet, want ze gelden alleen
  voor een opdracht.
- Hij krijgt de opdrachten die geen taakprofiel dragen, zoals de standpunten van de kennisgroepen, een vraag over
  verschillende soorten bronnen tegelijk, of iets wat nog niet bestaat.

### `definitie`, `duiding` (blijven, niet meer kiesbaar)

- **`kiesbaar: false`**, omdat de supervisor ze voortaan uit zijn eigen lijst haalt (besluit 4). Verder bitgelijk.
- **Waarom niet meer als subagent:**
  - `definitie`: 0 keer gekozen in 34 kinderen, en een begripsvraag doet de centrale agent zelf;
  - `duiding`: als subagent doet het altijd hetzelfde (een reeks bepalingen lezen), en daarvoor is
    `bepalingen_duiden` gemaakt. Dat profiel heeft geen antwoordsjablonen die botsen met het rapport.

### De niet-kiesbare profielen

`centraal`, `centraal_breed`, `retrieval`, `annotaties_lezen` en `begrippen_lezen` blijven zoals ze zijn, op één zin
na: de keuze van het profiel in `centraal` en `centraal_breed` (besluit 5). `tests/centrale_agent/test_centrale_agent.py` bewaakt dat
die twee gelijk blijven.

## Skills: wie krijgt wat vooraf

**Voorstel: in deze stap niemand.** Drie redenen:

1. **De methodetekst komt er al via `methoderol`.**
   - `algemeen` krijgt de secties `basis` en `nl-sbb-taalniveau` van wetsanalyse, `duiding` krijgt `basis` en
     `duiding` (`agentrollen.json`);
   - het vooraf laden van `wetsanalyse` (`skills.kern`) geeft de secties van de rol `agent`: `basis`, `definitie`,
     `duiding` en `nl-sbb-taalniveau`;
   - dat is voor een leesprofiel grotendeels dubbel, en het staat in elke ronde in het voorvoegsel.
2. **`wetsuitvoering` heeft geen secties voor een rol** (`"rollen": {}`, ADR-014 §7). Vooraf laden zou nu niets
   opleveren. Een JRM-profiel (een scenario uitwerken) is het voorbeeld van B5. Het komt pas als de JRM-secties na een
   meting aan een rol hangen.
3. **De methodes blijven gescheiden.** De drie nieuwe profielen lenen een rol van wetsanalyse, maar noemen geen
   JAS-tools en geen annotatietools. Zo blijft `test_methodegrenzen.py` groen, en geeft `test_methodes_gescheiden.py`
   geen nieuwe uitzondering. Een profiel dat later `wetsuitvoering` vooraf laadt, mag geen methoderol van wetsanalyse
   lenen. Dat toetst de validator (zie PR 2).

**Wat wel gebouwd wordt (PR 2):** het veld `skills` doet wat A2 zegt. De kern van elke genoemde skill (de secties van de
rol `agent`) komt in de systeemtekst, in het vaste voorvoegsel en ná de instructie van het profiel. Het spoor toont hem
onder *Methode*. De validator meldt:
- een skill zonder kern voor de rol `agent`, omdat die vooraf niets geeft;
- een profiel dat skills van twee methodes noemt;
- een profiel dat een skill van de ene methode noemt en een rol van de andere leent.

Omdat nog geen profiel `skills` noemt, is deze PR bitgelijk.

**`laad_skill` voor een subagent** (A2: de beschrijvingen in het voorvoegsel van `algemeen`) laat dit plan liggen. Geen
opdracht in de agentset heeft een skill nodig, en elke tool in het voorvoegsel kost in elke ronde. Dit komt in de lijst
open punten.

## Grenzen in de code

- **Per profiel:** `max_rondes(settings, state)` neemt `profiel.max_rondes` als het een opdracht is, en anders
  `MAX_RONDES_SUBAGENT`, begrensd door `settings.max_turns`. De zin "je hebt hoogstens 8 rondes" in
  `SUBAGENT_INSTRUCTIE` krijgt het getal van het profiel.
  - Let op: daardoor verandert die instructie per profiel. Het getal komt daarom ná het voorvoegsel, in het eerste
    bericht bij de opdracht, zodat het voorvoegsel per profiel gelijk blijft (ADR-015).
- **Budget:** na elke ronde telt de code het ruwe verbruik van het kind, uit dezelfde bron als `verbruik_van`. Komt de
  volgende ronde naar verwachting boven het budget (huidig verbruik plus de laatste ronde), dan wordt dat de laatste
  ronde, alleen voor het rapport, met `afgesloten` en de reden "budget van het profiel". Het kind ziet in die ronde
  waarom.
- **Het plafond van het platform** (`Grenzen.max_rondes = 12`, `Grenzen.budget = 400_000`): de validator weigert
  daarboven, ook voor een profiel uit de werkplaats. Het plafond van de opdracht (`DELEGATIE_AANDEEL`) blijft
  daarboven gelden.
- **De schatting op de bevestigingskaart** (A5: "een schatting per profiel komt uit de mediaan van eerdere runs") kan
  daarna het budget en de mediaan van het profiel tonen. Dat staat niet in dit plan, maar is een open punt dat hierop
  bouwt.

## Samenhang met Instellingen › Aanpassingen › Agents en de werkplaats

- **Agents** (plan Aanpassingen, PR 2 en 5) leest de catalogus. Het detail krijgt vier regels:
  - *Grenzen*: hoogstens N rondes, ongeveer X tokens;
  - *Skills vooraf*: met een link naar Methodes;
  - *Kiest de centrale agent*: ja of nee;
  - *Specialist van de supervisor*: ja of nee, zolang die bestaat.

  De catalogus geeft daarvoor `max_rondes`, `budget`, `skills` en `kiesbaar` mee, en `modelklasse` valt weg. De
  modelkeuze per rij bestaat al (`agent:<profiel>`): de drie nieuwe profielen krijgen hun sleutel vanzelf en staan op
  *Standaard*.
- **De werkplaats (B5)** gebruikt dezelfde validator (`bronmodel.agentprofiel`, poort 1). Wat dit plan toevoegt, geldt
  daar dus vanzelf:
  - de grens op `max_rondes` en `budget`;
  - de toets op skills en methodes;
  - de keuze op beschrijving (besluit 5), zonder welke een gepromoveerd profiel nooit gekozen zou worden.

  Het concept krijgt in de editor de velden `maxTurns` en `budget` met de platformgrens erbij. Poort 3 (de meting) volgt
  de opzet van de meting hieronder: een paar opdrachten die het profiel moeten kiezen, met zijn budget als plafond.

## PR-volgorde

Alle PR's op eigen branches, gebundeld in één `alles-samen-N`, één keer gemeten. PR 1 en 2 zijn bitgelijk, PR 3 en 4
veranderen gedrag en worden samen gemeten.

1. **Profielvelden afmaken (bitgelijk).** Raakt bronmodel, graph-qa en api (catalogus).
   - `max_rondes` en `budget` bedraden. Zonder waarde gelden de codedefaults.
   - De platformgrenzen in `profielen.grenzen()`.
   - `modelklasse` uit `Agentprofiel`, uit `VELDEN` (`model`) en uit de catalogus.
   - De supervisor krijgt een eigen lijst `SUPERVISOR_SPECIALISTEN`, met een test dat hij gelijk is aan wat
     `KIESBAAR` nu is.
   - Nagaan dat een subagent de antwoordsjablonen van zijn profiel niet aangeboden krijgt, en dat zo nodig in code
     afdwingen.
2. **Skills vooraf (bitgelijk).** Raakt bronmodel en graph-qa.
   - Het veld `skills` laadt de kern in het voorvoegsel, met *Methode* in het spoor.
   - De drie validatorregels uit *Skills*.
   - Geen profiel gebruikt het nog.
3. **Kiezen op beschrijving (gedrag `centraal`).** Raakt graph-qa.
   - Het schema van `subagent` krijgt per profiel zijn `description`.
   - De profielzin in `centraal` en `centraal_breed` wordt vervangen.
   - De catalogus toont dat `kiesbaar` alleen de centrale agent betreft.
4. **De taakprofielen (gedrag subagent).** Raakt graph-qa, `.claude/lex-agents/` en eval.
   - `rechtspraak_lezen`, `wetsgeschiedenis_lezen` en `bepalingen_duiden`.
   - De grenzen op `algemeen`.
   - `kiesbaar: false` op `definitie` en `duiding`.
   - De generator draaien (`genereer_agentprofielen.py`, en daarmee het bronpakket).
   - In de agentset de verwachte `profielen` per opdracht bijwerken (`golden_centrale_agent*.jsonl`): S01/F01/F02 →
     `rechtspraak_lezen`, V03 → `wetsgeschiedenis_lezen`, S05 → `wetsgeschiedenis_lezen`, M06 → de drie, P01/P02 →
     `rechtspraak_lezen` + `wetsgeschiedenis_lezen`, S03/S04/M01/P03 → `bepalingen_duiden`.
5. **Agents toont de profielen (frontend).** Raakt frontend. De vier regels in het detail. Kan na PR 1 los van de rest,
   en past in de stapel van plan Aanpassingen, mits die dan af is.
6. **De meting.** Meetbestanden en een regel in het meetlogboek, `metingen/agentprofielen-<datum>/`.
7. **Later, met de supervisor:** `definitie` en `duiding` weg, en `SUPERVISOR_SPECIALISTEN` weg. Wacht op A7 en op
   productie `aan`.

## Tests

- **`packages/bronmodel/tests`** (validator):
  - `max_rondes` en `budget` boven de platformgrens worden geweigerd;
  - een skill zonder kern voor de rol `agent`, skills van twee methodes, en een skill van de andere methode dan de rol
    geven elk een bevinding;
  - `model:` in de frontmatter van een vast profiel is een onbekend veld.
- **`tests/centrale_agent/test_profielregister.py`**: elk kiesbaar profiel heeft een `description`, en geen kiesbaar profiel heeft een
  antwoordsjabloon. Een subagent rondt alleen met `rapport` af.
- **`tests/test_supervisor*`**: `SUPERVISOR_SPECIALISTEN == ("algemeen", "definitie", "duiding")`, en de supervisor
  kiest bitgelijk (de bestaande scenario's in `test_modelverzoeken.py`).
- **`tests/centrale_agent/test_agentvorm.py`** en de grens in `nodes/antwoord`:
  - een kind met `max_rondes: 3` sluit na drie rondes af met een rapport;
  - een kind met een klein budget sluit af met de reden "budget van het profiel";
  - zonder waarden blijft alles 8 en zonder budget.
- **Voorvoegsel (ADR-015)**: twee opdrachten met hetzelfde profiel hebben hetzelfde voorvoegsel, ook met de rondegrens
  in de opdracht.
- **`tests/methode/test_methodegrenzen.py`** en **`test_methodes_gescheiden.py`**: ongewijzigd groen, zonder nieuwe
  uitzondering.
- **`tests/centrale_agent/test_centrale_agent.py`**: `centraal` en `centraal_breed` blijven gelijk, en het schema van `subagent` draagt
  de beschrijvingen.
- **`tests/methode/test_catalogus.py`**: de nieuwe velden, `modelklasse` weg, en `hangt_af_van` naar de connectors van de nieuwe
  profielen.
- **Altijd `scripts/kruistests.sh`**, en `uv sync --reinstall-package wetsanalyse-bronmodel` na de wijziging aan
  bronmodel. Geen volle suites lokaal: de poort draait ze.

## De meting

Klein en gericht (het lichte regime): **één run**, alleen de opdrachten die een subagent starten, plus vijf gewone
vragen als controle op de centrale agent. Op acceptatie via de acceptatie-MCP en `eval/centrale_agent_meting.mjs`, in
een eigen werkgebied, met de vlag op `meten`.

- **Opdrachten:**
  - S01, F01, F02 (rechtspraak);
  - V03, S05 (wetsgeschiedenis);
  - S03, S04, M01 (bepalingen);
  - M06, P01 (meer profielen tegelijk);
  - E01–E05 (de centrale agent zelf, om te zien of de nieuwe zin in zijn voorvoegsel iets kost).
- **Plafond: 3,5M tokens.** De wachter stopt alles boven 3,45M. Raming uit run 3: ongeveer 3,3M voor de tien
  delegatieopdrachten, plus 0,15M voor E01–E05. Vóór elke opdracht leest de keten het verbruik van het account.
- **Drempels:**
  - **profielkeuze**: in elke opdracht het verwachte taakprofiel; minstens 9 van de 10 opdrachten;
  - **V03**: minstens één MvT gelezen en samengevat met een letterlijke passage, zonder te gokken;
  - **S04**: alle onderdelen 22.1–22.9.x gelezen, of de ongelezen nummers precies genoemd, binnen het budget;
  - **grenzen**: geen kind boven zijn budget plus één ronde, en geen `afgesloten` zonder rapport;
  - **brongetrouw**: geen onjuiste bron en geen verzonnen citaat (zoals A6);
  - **verbruik**: per opdracht hoogstens run 3 plus 10 %. Voor `rechtspraak_lezen` en `wetsgeschiedenis_lezen` is de
    verwachting dat de mediaan per kind duidelijk lager ligt dan die van `algemeen` in run 3 voor hetzelfde werk
    (280k en 256k), door het kleinere voorvoegsel. Blijft dat uit, dan klopt de schatting over de schema's niet, en dat
    komt in het verslag;
  - **leesweg**: de rechtspraakkinderen zoeken op `bwb_id`/`artikel`, het wetsgeschiedeniskind begint bij
    `geldigheid`, en in beide lezen de kinderen meer dan één stuk per ronde;
  - **E01–E05**: mediaan gewogen warm niet boven run 3 (30,6k);
  - **inhoud**: geen opdracht van goed naar fout zonder verklaring.
- Een tweede run alleen bij twijfel over V03 of S04: geen trendclaim op één run. Strandt de meting drie keer op dezelfde
  drempel, dan gaat ze met een voorstel terug naar de gebruiker (A6).
- Tijdens de meting wordt er niet gemerged.

## Open keuzes voor de gebruiker

1. **Drie taakprofielen, of één per connector?** Voorstel: drie, en Kamerstukken en bekendmakingen samen als
   wetsgeschiedenis. Het alternatief is een vierde profiel `bekendmakingen_lezen`. Dat is preciezer, maar de set heeft
   maar drie van zulke kinderen.
2. **`definitie` en `duiding` nu al niet-kiesbaar?** Voorstel: ja. Het alternatief is ze kiesbaar laten naast de nieuwe
   profielen. Dan wordt de keuze moeilijker en is de meting minder scherp.
3. **`modelklasse` helemaal weg?** Voorstel: ja, het beheer kiest het model. Het alternatief is het veld laten staan
   als voorstel aan de beheerder.
4. **Meer rondes voor wetsgeschiedenis en bepalingen** (10 in plaats van 8) betekent meer tokens per kind, tot het
   budget. Voorstel: ja, omdat het budget het vangnet is.

## Lijst open punten (na deze stap)

- `laad_skill` en de skillbeschrijvingen voor een subagent `algemeen` (A2, niveau 1): pas als een opdracht erom vraagt.
- Een JRM-profiel (wetsuitvoering vooraf), na de meting die de JRM-secties aan een rol koppelt (ADR-014 §7; B5).
- De schatting per profiel op de bevestigingskaart, uit de mediaan en het budget (A5).
- `definitie`, `duiding` en `SUPERVISOR_SPECIALISTEN` weg, met de supervisor (na A7).
- `algemeen` daarna met een expliciete toollijst, zonder de JAS-, annotatie- en begrippentools (~16,8k → ~12k).
- De budgetten bijstellen op de meting: het hoogst gemeten verbruik per profiel plus 15 %.
