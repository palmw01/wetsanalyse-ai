# ADR-011 — Relaties tussen markeringen (deelactiviteit 2c)

Status: **aangenomen; opslag, projectie en de eerste keten-voorstellen (4C) gebouwd** · Datum: 2026-11-08 · Hoort bij: [ADR-001](adr-001-hybride-jas-pijplijn.md),
[annotatie-bronnodes](annotatie-bronnodes.md), [PLAN open keuze 7](../PLAN.md#open-keuzes), skill
[`references/relaties.md`](../../.claude/skills/wetsanalyse/references/relaties.md)

## Context

Het platform markeert en classificeert formuleringen in JAS-klassen, maar legt niet vast hoe die markeringen
samenhangen. De methode vraagt dat wel. Deelactiviteit 2c is een diagram van gemarkeerde formuleringen rond een
centrale klasse: rechtsbetrekking, rechtsfeit, afleidingsregel of voorwaarde. Analisten maken dat diagram nu buiten
het platform, als losse afbeelding in een wiki of presentatie. Zo'n plaatje is niet herleidbaar naar het anker,
niet doorzoekbaar, en veroudert stil als de tekst of de markering verandert.

Een vergelijking met een bestaande, door juristen gemaakte analyse liet zien dat het grootste deel van zo'n diagram in
vaste rollen valt: operator, invoer, uitvoer, onderdeel, waarde, recht- of plichthebbende, voorwerp en voorwaarde. De
rest is regelinhoud (een waarde of tak op de lijn) of regelstructuur (een relatie tussen twee afleidingsregels). En
partijen die de tekst zelf niet noemt, staan wel in het diagram.

Drie dingen staan vast:

- **De methode benoemt de verbanden, maar geeft ze geen namen.** JAS tekent lijnen zonder type (H2). Het boek, H2,
  WetsTaal en JRM 2 beschrijven per klasse waarmee hij samenhangt. De rollen zijn methode; codes en leesvormen zijn
  een projectkeuze (`verbeterplan-jas-pipeline-2026-10-08.md`, stap D).
- **W3C Web Annotation kent geen relatie tussen annotaties.** De werkgroep raadde aan eigen triples in een eigen
  namespace te zetten. Annotatietools als INCEpTION en FoLiA leggen een relatie vast als eigen object tussen twee spans.
  LegalRuleML en FLINT zetten de rol op de relatie, niet op de partij.
- **De relaties rond een afleidingsregel zijn de grondstof voor activiteit 3b.** Uitvoer, invoer, operatoren met hun
  operanden, voorwaarden en parameters zijn precies de opbouw van een afleidingsregel. Zonder volgorde is "A verminderd
  met B" niet te onderscheiden van "B verminderd met A".

## Besluit

**Relaties tussen markeringen horen bij activiteit 2** (open keuze 7, voor dit deel beantwoord). Ze worden vastgelegd
en beoordeeld zoals markeringen, en de graaf maakt er het 2c-diagram van. Geen losse afbeeldingen.

### De catalogus

- **Eén catalogus, in de skill** (`.claude/skills/wetsanalyse/relaties.json`, uitleg in `references/relaties.md`).
  Per type: code, leesvorm en inverse, toegestane klassen aan beide kanten (bij `waarde` met subtype), de drager,
  `methodisch` (komt het verband uit de methode), de bron, en waar nodig `volgorde` en `tekstueel`. De catalogus
  wordt gegenereerd naar `api/app/jas_relaties.py` en `frontend/lib/jasRelaties.ts`, met een drifttest, net als de
  klassen. Een type bestaat alleen als het in de catalogus staat; de api kent geen vrije relatienamen.
- **De methodische typen**: rechthebbende, plichthebbende, verricht, voorwerp, voorwaarde, creëert, wijzigt,
  beëindigt, invoer, uitvoer, kenmerk, waarde, operator_in, operand, tijd, plaats, delegatie_over, bevoegde en
  definieert.
- **Drie projecttypen**:
  - `onderdeel` (een rechtsobject bevat een ander; JRM noemt het verband, JAS niet);
  - `uitzondering_op` ("in afwijking van", "met uitzondering van");
  - `toepassing` ("vindt toepassing", "is van toepassing").

  De laatste twee zijn `tekstueel`: ze bestaan alleen waar de tekst ze uitdrukt.
- **`uitvoer`** gaat van een afleidingsregel naar een variabele, een rechtssubject, een rechtsobject of een
  tijdsaanduiding. Een regel kan een moment opleveren (een vervaldag) of een specialisatie van een subject of object
  (H2:71).
- **`invoer`** komt van een variabele, parameter, voorwaarde, tijdsaanduiding, rechtssubject, rechtsobject of
  rechtsbetrekking, en gaat naar een afleidingsregel of een **voorwaarde** (aanvulling 8 nov 2026, besluit gebruiker:
  een voorwaarde bestaat uit operanden, H2:62; een jurist legt wat vergeleken wordt vaak direct aan de voorwaarde,
  zonder aparte operator).
- **`invoer` en `operand` dragen een optionele `volgorde`** (een geheel getal, uniek per regel of operator). Zonder
  volgorde is de relatie onvolledig voor een niet-commutatieve bewerking. Dat is een signaal, geen fout.
- **Buiten activiteit 2** blijven:
  - relaties tussen afleidingsregels (vertakking, volgorde, herhaling);
  - een waarde of tak als label op een lijn;
  - specialisatie van een begrip (dat is de begripsrelatie *soort van*);
  - rechtsgevolg en juridisch relevant feit als eigen element;
  - feittypen, datatypen en RegelSpraak.

  Ze komen terug in activiteit 3b en 6.

### Opslag (api, stijl C)

- **Tabel `annotatie_v2_relaties`**, een rij per relatie: `van` en `naar` (`{soort: element|impliciet, id}`), `type`,
  `volgorde`, herkomst (`agent` of `mens`, met het spoor: regel of model, regel-id, UD-pad, run), dezelfde
  `lifecycle` als een element (één definitie van beoordeeld, `annotatie_v2_contracts`), `aandacht`, `toelichting`,
  `bewijs` en `stand_van`/`stand_naar`.
- **De relatie hoort bij de laag van de drager.** De catalogus wijst per type de kant aan die de centrale klasse
  draagt. Een mutatie raakt die laag, dus een relatie gaat door het schrijfslot, krijgt een revisie, kan 412 geven,
  komt in de audit en gaat mee met de projectie, allemaal via `_raak`.
- **Een eindpunt mag in een andere laag liggen** (lid 5 → lid 1, Awb → IW). Wie een relatie legt, wijst het eindpunt
  aan met een element-id. Een agent in de batch wijst het aan met de ankers van de kandidaat; de api zet die na het
  opslaan om naar het uiteindelijke element-id. Een eindpunt dat niet op te lossen is, wordt gemeld, nooit geraden.
- **Doorwerking**: `stand_van`/`stand_naar` zijn de hash van klasse, ankers en bronhash van elk eindpunt bij het
  vastleggen, zoals bij begripsrelaties. Wijkt een kant af (klassewissel, grenskeuze, verouderd, verworpen,
  vervangen), dan staat de relatie op *veranderd* en vraagt ze opnieuw een oordeel.
- **Een gewist element neemt zijn relaties mee**, met een auditregel. `verwijder_weergave` doet dat ook. Een verworpen
  of verouderd element laat ze staan, als historie, met *veranderd*.
- **Wat de api toetst**: het type bestaat, het klassenpaar past (met subtype), geen relatie naar zichzelf, de eindpunten
  bestaan en zijn actueel, de drager klopt, en een `volgorde` alleen bij een type dat hem kent. Juridische juistheid
  toetst hij niet.
- **Een id volgt uit de inhoud**: `R` + hash(van, naar, type, volgorde). Een herhaalde run is daarmee idempotent, en een
  afgewezen voorstel komt niet terug.

### Impliciete partij

- **Tabel `annotatie_v2_impliciet`**: een partij die de tekst niet noemt. Alleen klasse Rechtssubject (besluit
  gebruiker, 7 nov 2026), met een label in de woorden van de analist, een verplichte toelichting (waaruit volgt ze), een
  optionele vindplaats (de bepaling die de partij wél noemt of definieert) en een optioneel `zelfde_als` (een markering
  elders).
- **Alleen de jurist maakt haar.** Lex stelt geen impliciete partij voor. Open keuze 8 (telt zo'n partij voor een
  rechtsbetrekking?) blijft open; dit besluit beantwoordt alleen hoe je haar vastlegt.
- **Geen markering.** Ze heeft geen ankers, geen tekst en geen dekking. Ze telt niet in de inventaris, de statistiek of
  de afronding, en `valideer` blijft gelijk. Een eigen soort houdt de invarianten van markeringen intact: een anker
  verzinnen zou ze breken.
- **Hergebruik boven kopie.** Binnen een werkgebied is één impliciete partij genoeg, ook als ze in elk diagram
  terugkomt. In activiteit 3 kan ze een begrip worden.

### Projectie (RDF)

- **Een n-aire knoop `jas:Relatie`** in de graph van de dragerlaag, met `jas:van`, `jas:naar`, `jas:relatietype`,
  `jas:volgorde`, lifecycle, herkomst en `prov:wasGeneratedBy` bij een agentvoorstel. Een impliciete partij is een
  `jas:ImplicietElement` met `jas:label` en `jas:vindplaats`.
- **Een directe triple alleen bij een beoordeelde relatie**, voor eenvoudige SPARQL, zoals bij begripsrelaties
  (`<van> rel:<code> <naar>`, `urn:jas-ns:rel:`). *Veranderd* staat niet in de graaf: dat hangt af van een eindpunt
  in een andere laag, en de projectie per laag blijft zuiver. De api meldt het (aanvulling bij 3D, 8 nov 2026).
- **De typen zijn SKOS-concepten** in de vocabulaire (`urn:jas-ns:relatie:<code>`), met leesvorm, inverse, bron en
  `jas:vanKlasse`/`jas:naarKlasse`. Geen `rdfs:domain`, `range` of `owl:sameAs`: rdfsplus zou anders afleiden wat de
  jurist niet vastlegde.
- **De invarianten blijven gelden**: geen subject onder `urn:bwb:`, geen `urn:bwb-ns:`-predicaat en geen schema-axioma's
  in een `urn:jas:graph:*`. De SHACL-shape en de graafcontrole krijgen de relaties erbij. Schemaversie 3 wordt 4.
- **Relaties zijn afgeleide duiding**, net als annotaties: ze tellen nooit als bron of grounding.

### Kardinaliteit en volledigheid zijn diagnostisch

Een afleidingsregel heeft precies één `uitvoer` en minstens één `invoer` (catalogus, `kardinaliteit`). De SHACL-shape
`JasModel` en de graafcontrole melden het, in het schrijfpad weigert niets. Zo kan de jurist een diagram stap voor stap
opbouwen, en blijft een onvolledige afleidingsregel zichtbaar (beperking D08 in `annotatieketen.md`).

### Meten

De vergelijker met een externe analyse (`eval/extern_dossier.py`) krijgt de recall per relatietype op (van, type, naar),
met een vertaaltabel van de notatie van het team naar de catalogus. Daarnaast komt de maat **regelskelet-compleet**:
per afleidingsregel uit de referentie, heeft het platform de regel, zijn uitvoer, zijn invoer en zijn voorwaarden
gemarkeerd en verbonden? Dat meet of activiteit 3b later kan bouwen. Alleen de diagrammen van activiteit 2 tellen als
referentie; afleidingsregels die een team in 3b opstelde zijn geen meetlat.

### Voorstellen komen later, en eerst zonder model

De eerste stappen leggen opslag, projectie en review neer, zodat de jurist relaties met de hand kan vastleggen. Daarna
stelt de keten relaties voor (ADR-001: kennis in regels en tests), achter een proefvlag en in deze volgorde:

1. de spans van de functiedetector: uitvoer en invoer;
2. waarde;
3. operator met operanden, met de volgorde uit de woordvolgorde;
4. de aanhechting van een voorwaarde;
5. kenmerk;
6. tijd;
7. rollen, via een lexicon van predicaten.

Een strikte modelstap voor ambigue aanhechting en rollen volgt pas na een meting. Een voorstel is altijd een voorstel:
een goedgekeurde markering keurt haar relaties niet goed. Omgekeerd keurt een goedgekeurde relatie haar eindpunten niet
goed: zolang een eindpunt een voorstel is, heet de relatie in het rapport "vastgelegd", niet "akkoord" (8 nov 2026).

**Gebouwd (4C, 8 nov 2026): de stappen 1 tot en met 4**, in `tools/graph-qa/agent/jas_pipeline/relaties.py`, achter de
proefvlag `RELATIE_VOORSTELLEN` (standaard uit; uit is de uitkomst van de keten bitgelijk). Elke regel heeft een code
(`REL_UITVOER_FUNCTIE`, `REL_INVOER_FUNCTIE`, `REL_WAARDE_NESTING`, `REL_OPERATOR_IN_NESTING`,
`REL_OPERAND_WOORDVOLGORDE`, `REL_VOORWAARDE_AANHECHTING`) met een verklaring en vier testsoorten. Bij twijfel komt er
geen voorstel, en elk voorstel gaat door de catalogus, die graph-qa als gegenereerde kopie draagt. Een eindpunt is de
lijst ankers van een voorstel; de api zet die in de batch om naar het element-id en meldt wat niet lukt. Een ronde
`opnieuw` vervangt oude voorstellen zonder oordeel, zoals bij elementen. Kenmerk, tijd en rollen (stappen 5 tot en met
7) volgen nog; een meting op een referentie ook.

## Gevolgen

- De werkplek krijgt een blok *Relaties* per element in het annotatiepaneel. De graaf krijgt een lijnsoort
  `jas_relatie`, een knoopsoort `impliciet`, en een diagrammodus per centrale klasse. Daarmee komt het 2c-diagram uit
  de graaf in plaats van uit een plaatje. Exports dragen de relaties: JSON v4, TriG, en een relatielijst plus regelskelet
  in Markdown en PDF.
- Afronden van een laag hangt voorlopig niet van relaties af; de werkplek telt wel de open relaties. Of afronden
  beoordeelde relaties moet vragen, is een latere keuze.
- Lex leest relaties via de leesroute ("wat is de invoer van de regel in lid 5?"), op wat vastgelegd is.
- Een relatie geeft een tweede reden om een laag opnieuw te projecteren, en de graaf groeit. Daarom tonen de
  graafweergave en de focus relaties alleen op verzoek.

## Overwogen en afgewezen

- **De rol als label of subtype op het element.** Een subject is in de ene betrekking plichthebbende en in de andere
  rechthebbende. Een rol op het element dwingt tot kopieën.
- **Een impliciete partij als markering zonder anker.** Ankers, dekking, eigenaar, zoeken en SHACL gaan uit van een
  tekstanker. Een uitzondering daarop zou door elke lezer van de elemententabel moeten lopen.
- **Een gebogen `oa:Annotation` met een relatie als body.** Web Annotation kent geen richting tussen targets. Een eigen
  knoop is wat de werkgroep zelf aanraadde.
- **Vrije relatienamen, zoals de werkwoordsvormen van een team.** Dan is niets te toetsen of te vergelijken. De
  werkwoordsvorm wordt de leesvorm.
- **Regelstructuur nu al meenemen** (relaties tussen afleidingsregels, waarden op lijnen). Dat is activiteit 3b. Het
  hoort bij het regelartefact, met eigen begrippen en validatie, niet bij markeringen.
- **Kardinaliteit afdwingen bij het schrijven.** Dan kan een jurist een diagram niet in stappen opbouwen.

## Fasering

| stap | wat | waar |
|---|---|---|
| 3A | dit besluit, de catalogus en de uitleg in de skill, een vormtest op de catalogus | docs, skill, `tests/poort` |
| 3B | de catalogus als code, met `--check` en drifttests | graph-qa-script, api, frontend |
| 3C | opslag en routes (`/v1/annotatie/relaties`, impliciete partij), BFF | api, frontend-BFF |
| 3D | projectie, vocabulaire, SHACL, graafcontrole, schema 4 | api |
| 3E | vergelijker: recall per type en regelskelet-compleet | graph-qa `eval/` |
| 4A–4D | review in het paneel, graaf en diagrammodus, deterministische voorstellen, Lex leest | frontend, api, graph-qa |
