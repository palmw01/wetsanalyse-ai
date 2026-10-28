# Plan: contextbewust betekenisonderzoek in de begrippenketen (activiteit 3)

> **Hervatten na /clear.** Dit is spoor **M** (betekenisonderzoek). De opdracht is de lange
> gebruikersopdracht "verbeter de begripsvorming in Lex" van 27-10-2026. Het plan en de opdrachttoets
> hieronder zijn het resultaat van het onderzoek, dus herhaal het onderzoek niet. Lees deze sectie en
> de voortgangslijst, kijk met `git branch -a | grep spoor-m` en `gh pr list` wat er al staat, en ga
> door bij het eerste open vinkje. Werk de vinkjes bij in de repo-kopie
> (`docs/architectuur/plan-betekenisonderzoek.md`), niet hier.
>
> **Besluiten van de gebruiker (28 okt 2026)**:
> 1. Live modelmeting mag (een paar euro, 3×, vóór en na).
> 2. Oplevering als PR-stapel op branches, gepusht en **niet** gemerged.
>
> De kwesties zonder besluit (TOOI `dct:publisher`, invorderingsrente of belastingrente) leg ik vast
> als beperking. Ik verander ze niet.

## Voortgang

- [x] **M0** Plan vastleggen (gedaan 28 okt 2026; de nulmeting staat onder *Nulmeting*):
  - deze tekst naar `docs/architectuur/plan-betekenisonderzoek.md`;
  - een regel "spoor M" in `docs/PLAN.md`;
  - het memory-bestand `spoor-m-betekenisonderzoek.md` met een regel in `MEMORY.md`;
  - nulmeting: `eval.begrippen_eval --variant keten`, de suites groen op master, de casus-fixtures uit de graaf.
- [x] **M1** (branch `spoor-m1-onderzoeksstand`; afwijkingen onder *Afwijkingen van het plan*):
  - het model `Onderzoek`/`Contextbron`;
  - de samenvoeging van `fragmenten`;
  - api `begrip_onderzoek.py`, met opslag en identiteit (§1, §2);
  - de verwijzingsquery in bronmodel;
  - tests.
- [x] **M2** (`spoor-m2-betekenisanalyse`):
  - `betekenis.py`;
  - signalen (contextdefinitie, `BEREKENING_IN_BEPALING`);
  - prompt, schema en toetsen van kaart en scherper (§3–§5);
  - `eval/betekenisonderzoek_eval.py`.
- [x] **M3** (`spoor-m3-voorbeelden-runs`):
  - de voorbeelden (§6);
  - `werkvoorraad_id`, batch-id en de twee bugfixes (§7).
- [x] **M4** (`spoor-m4-bewijs-export`; het eindrapport staat onderaan):
  - `definitie_onderbouwing`, projectie en export (§8);
  - frontend (§9) en documentatie plus skill (§10);
  - de live meting en het meetlogboek;
  - het eindrapport (opdrachttoets, oorzaken, bestanden, metingen, beperkingen, wat de jurist nog moet beoordelen).

### Nulmeting (28 okt 2026, master `03739283`)

- `begrippen_eval --variant keten`: v1 BCubed F 1,000 (13 groen, 2 geel); heldout-v1 F 0,956 (recall
  0,916; 8 groen, 1 geel); heldout-v2 F 0,973 (recall 0,947; 9 groen, 1 geel). Alle drie deterministisch.
- Suites op master groen (graph-qa, api).
- Casus A en B: `tools/graph-qa/eval/betekenisonderzoek_casus.json`, letterlijk uit de graaf op
  acceptatie (art. 30fb en 30fc AWR, alle leden en onderdelen), `bron_hash` = `bronmodel.tekst_hash`.

### Afwijkingen van het plan

- **M1, verwijzingen**: geen querybouwer in `packages/bronmodel`. De api heeft er al een
  (`samenhang._uitgaand`, dezelfde `bwb:heeftVerwijzing`-vorm als de graafweergave), en graph-qa
  verzamelt zelf geen context: de api bouwt het onderzoek. Eén vocabulaire, op één plek.
- **M1, identiteit**: `onderzoek_id` neemt ook de vergelijkingsbegrippen op (id, status, hash van naam en
  definitie). Ze komen in de prompt, dus een gewijzigde definitie elders moet een ander dossier geven.
- **M1, kaartruns**: `invoer_id` neemt `onderzoek_id` op; de promptversie niet. Die kent alleen
  graph-qa, en zijn batch-id's dragen haar al (`verdieping.batch_id`); in M3 gaat ze in de
  `werkvoorraad_id` van het meedenken.
- **M1, versies**: `fragmenten.VERSIE` blijft 1 tot M2 het onderzoek echt aan de prompts geeft; zonder
  onderzoek is de fragmentkeuze bitgelijk (getest).

- **M2, dossier zonder onderzoek**: de kaart en *scherper* bouwen het dossier altijd, ook zonder
  onderzoek (een run van vóór spoor M). Dan zegt het "alleen de bepalingen met de passages onderzocht"
  en krijgt een geformuleerde definitie `CONTEXT_NIET_ONDERZOCHT`. De **keten** (groepen, vragen) is
  zonder onderzoek bitgelijk: `begrippen_eval --variant keten` geeft op v1, heldout-v1 en heldout-v2
  exact het rapport van de nulmeting (`metingen/betekenisonderzoek-2026-10-28/m2-keten-*.json`).
- **M2, kwalificatie**: "geldt als X:" staat niet in `definities._definitie` (dat zou de keten raken),
  maar in het dossier (`betekenis._KWALIFICATIE`). De keten kent de kwalificatie al als relatiepatroon.
- **M2, `ROL_IN_BEPALING`**: alleen *voorwaarde* (bij/indien/ingeval … vóór de passage) en *grondslag
  van een berekening*. Een rechtsgevolg aan de passage zelf herkennen vraagt de zinsbouw; de toets
  `RECHTSGEVOLG_IN_DEFINITIE` kijkt naar de definitie, en daar zit het probleem.
- **M2, frontend**: de nieuwe codes van `toetsen.TEKST` staan al in `frontend/lib/begripVoorstellen.ts`,
  want de drift-test eist het per PR; de weergave (§9) volgt in M4.
- **M2, `BEREKENING_IN_BEPALING`**: de patronen staan in `begrippen_pipeline/betekenisregels/berekening.yaml`
  (niet in `regels/`: dat register eist groepen `van`/`naar`), met dezelfde vier testsoorten.

- **M3, `werkvoorraad_id`**: de hash van de twijfelvragen en groepen zonder definitie (de inhoud van
  de batches), het `onderzoek_id`, het model en de promptversies – niet van de batch-id's zelf: die
  vragen de hergroepering, en die draait pas na de bevestiging. Een knop van vóór spoor M draagt geen
  id; Lex vraagt dan opnieuw om bevestiging (liever één klik meer dan een onbedoelde run).
- **M3, ontdubbelen**: een naam is een kort woord met een hoofdletter (vooraan in de zin hoogstens
  acht letters en geen functiewoord, of midden in de zin). Een heuristiek: "Bedrijf X …" vooraan wordt
  ook `<naam>`. De kenmerken knipt code uit de definitie (komma's en verbindingswoorden).
- **M3, de klare brondefinitie**: `kaart_kern` telt een klare run die de api teruggeeft als voorstel
  (de api geeft hem alleen terug met open voorstellen). `test_uitwerken_volgt_de_methode` legde het
  oude gedrag vast; die test zegt nu het omgekeerde, met een eigen test voor "geen brondefinitie →
  scherper".

- **M4, onderbouwing**: alleen een definitie uit een kaartvoorstel krijgt `definitie_onderbouwing`. Een
  definitie die via het akkoord op een groep (fase D) binnenkwam, heeft er nog geen: de revisie noemt
  dan geen voorstel. De kaart van de verdieping draagt haar fragmenten wel, dus dat is een vervolgstap.
  *Nazorg (28 okt 2026)*: gedaan; `_neem_over` bevriest de onderbouwing in het revisiedetail. Daarbij
  ook: `ontbrekend` telt nu mee in `onderzoek_id` (versie 2), want het stuurt `CONTEXT_NIET_ONDERZOCHT`
  en de prompt; een run van tijdens een storing bleef anders na het herstel staan.
- **M4, `door.onderzoek`**: de samenvatting van het dossier staat bij elk voorstel (in `door`), niet
  alleen bij de run, zodat de werkplek haar zonder extra verzoek kan tonen.
- **M4, meedenkaanbod**: `begrippen_beurt.meedenk_aanbod` maakte zijn bevestiging zonder
  `werkvoorraad_id` (M3 vergat die ingang); hersteld, anders vroeg de knop na het voorstellen altijd
  opnieuw om bevestiging.

Werkwijze per PR:

- de suites van de geraakte componenten groen;
- `git push` met `SKIP_HOOK=1` alleen na een groene suite (memory `spoor-d-werkgebieden-begrippen`);
- `gh pr create --base <vorige>`, en nooit `--delete-branch` (memory `gestapelde-prs-mergen`);
- commit- en PR-attributie volgens de systeemmelding.

## Context

Lex stelt begrippen voor vanuit geannoteerde formuleringen, maar ziet daarbij alleen de bronnodes
waarop een annotatie-element een anker heeft. Daardoor:

- **Casus A**: "herziening" in art. 30fb lid 4 AWR kreeg als definitie het toepassingsgeval van dat
  ene lid ("…met een negatief bedrag tot … positief bedrag"). Leden 1–6 hebben dezelfde opening
  ("Bij herziening van een voorlopige aanslag … met X tot Y") en variëren alleen in de
  bedragovergang. Het algemene begrip bleef buiten beeld.
- **Casus B**: bij "belasting" kwam het rechtsgevolg in de definitie terecht ("…als grondslag voor de
  berekening van belastingrente"), en de beperking tot IB/Vpb komt uit de toepassingsvoorwaarde van
  30fc lid 1. In 30fc lid 7 staat een eigen kwalificatie van "het te betalen bedrag aan belasting"
  ("Voor de toepassing van dit artikel geldt als …"). Dat is een ander begrip, en de keten herkent
  het niet: `definities._definitie` kent geen "geldt als … :".

De methode vraagt hier uitdrukkelijk om. In het boek, stap 3a, staat:

- andere onderdelen en regelingen raadplegen;
- *bijdrage-inkomen* als homoniem binnen één lid, door een berekening;
- de begripsomschrijving geeft de wezenlijke kenmerken plus het doel, maar geen afleidingen;
- een afleidingsregel krijgt een eigen begrip ("bepalen …");
- bij stap 4: concrete voorbeelden met variatie in bedragen, om de afleiding te valideren.

Het doel is dat contextonderzoek deterministisch in de bestaande keten komt, vóór de definitie, met
bewijs en herkomst door de hele keten heen. Er komt geen nieuwe agent en geen vrije onderzoekslus.

## Opdrachttoets (beknopt; komt volledig in het rapport)

| Aanname | Oordeel | Onderbouwing |
|---|---|---|
| 1. Het manifest komt uit bruikbare elementen en hun bronnodes | **Bevestigd** | `api/app/begrip_manifest.py:45-86`: precies één anker per element, niet verouderd, letterlijk |
| 2. Contextbronnen zonder annotaties komen niet mee | **Bevestigd** | Een `Bron` ontstaat alleen met een formulering erop (`:68-76`) |
| 3. `voor_groep` beperkt tot de bronnen van de leden en de begripsbepalingen in het manifest | **Bevestigd** | `fragmenten.py:46-57`, en de bijna-kopie `kaartacties.fragmenten_voor:152` |
| 4. Andere leden en verwante bepalingen worden niet onderzocht | **Bevestigd** | Alleen de tekst van de ouder gaat mee, als `aanhef` |
| 5. "Scherper" gebruikt het manifest; de brondefinitie loopt via een eigen graafroute | **Bevestigd** | `begrip_kaart.zoek_brondefinities:76` |
| 6. Betekenisonderscheiding, bereiken en getypeerde relaties bestaan al | **Bevestigd** | `definities.Bereik`, `besluit.TABEL`, `groeperen` |
| 7. Dezelfde term in dezelfde bronnode geeft sterke steun | **Bevestigd, en methodisch te sterk** | `ZELFDE_BEPALING` → `Z-STERK-SCHOON` → link (geel). Het boek geeft een tegenvoorbeeld: bijdrage-inkomen in art. 43 lid 3 Zvw |
| 8. Fragmenttoetsen controleren alleen tekst | **Bevestigd** | `toetsen.garanties` |
| 9. Voorbeelden worden alleen op tekstgelijkheid ontdubbeld | **Bevestigd** | `kaartacties.py:402-412`. Het model krijgt geen fragmenten; er is geen kenmerk en geen toetsvraag |
| 10. Voorstellen gebruikt geen model; verdieping heeft een eigen route met bevestiging | **Bevestigd** | |
| 11. Agenttaken slaan de verify-node over | **Bevestigd, bewuste keuze** | `nodes/agent_taak.py:13`. De borging moet dus in de begrippenworkflow zelf |
| 12. Onderbouwing zonder annotatiekoppeling verdient aandacht | **Bevestigd: verlies na overnemen** | `definitie_bron_iri` en `fragmenten` verdwijnen uit `begrippen.inhoud`. Ze staan alleen nog in `begrip_voorstellen.waarde` en worden niet geprojecteerd |
| Bevestiging gebonden aan de inhoud | **Onjuist: alleen het aantal telt** | `begrippen_verdieping.py:119`, api `:141-146` |
| Extra bevinding | **Fout** | `kaartacties.promptversie` kent `"uitleg"` niet, en uitleg deelt de hash van "graaf" |
| Extra bevinding | **Fout** | `uitwerken` start `scherper` met het model wanneer een brondefinitie-run al open voorstellen heeft (`agents/begrippen.py:388`, `kaart_beurt.py:458/488`) |
| Tegenvoorbeelden in de RDF | **Correct, maar onbewaakt** | Alleen `wel` wordt `skos:example`. `niet`/`onzeker` vallen weg uit de RDF en er is geen test |
| `dct:publisher` = eerstverantwoordelijke organisatie | **Gedeeltelijk juist** | Een uitgever is niet hetzelfde als de eerstverantwoordelijke organisatie. Ik leg het vast als beperking en zet de mapping niet stil om |
| Invorderingsrente of belastingrente | **Te verifiëren** | 30fb/30fc gaan over *belastingrente* (AWR); invorderingsrente staat in art. 28 IW 1990. Ik controleer de naam van het werkgebied in de casus en corrigeer niets stilzwijgend |

## Gekozen architectuur: één gedeelde *onderzoeksstand* naast het manifest

Het manifest en zijn id blijven ongewijzigd. Daarnaast komt een onveranderlijke **onderzoeksinvoer**
met een eigen id (`O…`). De api bouwt die, de zuivere keten leest hem, en alle routes gebruiken
hem: voorstellen, meedenken en de kaartacties.

### 1. Model (graph-qa, zuiver): `begrippen_pipeline/model.py`

- `Contextbron(Bron)` krijgt de velden:
  - `rol` ∈ `analyseren | context | onderzoek | vergelijking`;
  - `reden` ∈ `zelfde_artikel | definitie_in_regeling | verwijzing | contextselectie`;
  - `voor`: de element-id's of bron-IRI's die hem aanleverden.
- `Onderzoek` krijgt:
  - `manifest_id`, `bronnen: tuple[Contextbron]`, `begrippen` (vergelijkingsmateriaal: id, naam, definitie, status, werkgebied, `eigen` ja/nee);
  - `ontbrekend: tuple[{wat, reden: budget|niet_in_graaf|onbereikbaar|buiten_selectie}]`;
  - `versie` en `id` = `"O"+hash(manifest_id, sorted(iri@hash), versie)`.
- Een validator eist dat geen contextbron samenvalt met een manifestbron.
- `fragmenten.alle(manifest, onderzoek=None)` wordt de geldige fragmentruimte. Fragment-id's blijven
  `fragment_id(bron_iri, start, eind)`, dus bestaande id's blijven gelijk.

### 2. Contextverzameling (api, deterministisch): nieuw `api/app/begrip_onderzoek.py`

De api heeft per regeling de volledige bronboom al in handen (`werkgebied_inventaris.inventaris_met_bronbomen`),
met teksten en hashes. Daaruit, in vaste prioriteit, telkens gesorteerd op documentvolgorde:

1. **Zelfde artikel**: de leden en onderdelen van het artikel van elk anker (uit de bronboom).
2. **Definities in de geselecteerde regelingen**: nodes die "verstaan onder", "geldt als … :" of
   "wordt aangemerkt als" dragen, en waarvan de definiens of de ouder een formuleringstekst bevat
   (genormaliseerd, op woordgrens).
3. **Expliciete verwijzingen**, diepte 1, vanaf de ankernodes. Er komt een kleine querybouwer in
   `packages/bronmodel`, zodat api en graph-qa hetzelfde vocabulaire delen. Een doel buiten de graaf
   wordt `ontbrekend: niet_in_graaf`.
4. **Contextselecties zonder annotaties** (rol *context*): hun nodes uit de bronboom.
5. **Begrippen** uit dit werkgebied (alle) en uit andere werkgebieden met een exact gelijke naam of
   alternatieve term (hoogstens 5). Dit is vergelijkingsmateriaal, nooit een bron.

Standaardwaarden (constanten met docstring):

- hoogstens `MAX_ZELFDE_ARTIKEL=12`, `MAX_DEFINITIES=6`, `MAX_VERWIJZINGEN=6`, `MAX_CONTEXTSELECTIE=6`;
- samen hoogstens `MAX_BRONNEN=24` en `MAX_TEKENS=40_000`;
- stopregel: zodra het budget op is, krijgt de rest `ontbrekend: budget`, in prioriteitsvolgorde;
- een onbereikbare graaf geeft `ontbrekend: onbereikbaar` en is geen fout.

De api slaat het onderzoek op bij de run (`begrippen_runs.onderzoek` JSON; voor kaartruns in `invoer`).
Kolommen komen erbij via `reconcile_schema`; er is geen migratie nodig.

Identiteit verandert als volgt:

- de idempotentiesleutel van een run wordt `(werkgebied, manifest_id, onderzoek_id)`;
- `laatste()` meldt `verouderd` ook bij een ander `onderzoek_id`;
- `invoer_id` van een kaartrun neemt `onderzoek_id` en de promptversie op.

### 3. Betekenisanalyse (graph-qa, zuiver): nieuw `begrippen_pipeline/betekenis.py`

Per groep (en per begrip bij kaartacties) levert dit een compact **dossier** van bevindingen. Elke
bevinding heeft een `soort`: `bronfeit`, `signaal` of `interpretatie` (de laatste alleen van een
model). Daarbij horen bewijs (fragment-id's en bron-IRI) en een regel met versie.

| Code | Soort | Wat |
|---|---|---|
| `VOORKOMENS` | bronfeit | waar de term (woordgrens, genormaliseerd) nog meer staat in manifest en onderzoek |
| `PARALLELLE_BEPALINGEN` | signaal | ≥2 leden met dezelfde opening tot en met de term en verschillende vervolgen: een mogelijk toepassingsgeval van een algemener begrip (casus A) |
| `DEFINITIE_IN_CONTEXT` | bronfeit | een definitie of kwalificatie van de term in een contextbron, met bereik; per lid binnen of buiten het bereik |
| `KWALIFICATIE_SAMENGESTELD` | bronfeit | "geldt als het te betalen bedrag aan belasting" staat los van de kale term (casus B) |
| `BEREKENING_OP_TERM` | signaal | in de bronnode wordt de term zelf bewerkt ("op nihil gesteld", "verminderd met", "tot geen hoger bedrag"): mogelijk een berekeningsresultaat of een homoniem door berekening |
| `ROL_IN_BEPALING` | signaal | de formulering staat in een voorwaardezin (*bij/indien/ingeval …*) of in een rechtsgevolg (*wordt … in rekening gebracht/vergoed*) |
| `AFLEIDINGSREGEL` | signaal | een lid met klasse Afleidingsregel: een eigen begrip "bepalen …" (boek 3b) |
| `GEEN_DEFINITIE_GEVONDEN` | bronfeit | binnen de onderzochte context, met wat er niet onderzocht is |

Er komen **open vragen** bij met een vaste formulering. Een voorbeeld: "Duidt 'herziening' in lid 4
hetzelfde aan als in de leden 1–3, 5–6, of een specifiek geval?" Een modeloordeel wordt nooit een
`Bewijs` in de beslistabel.

### 4. Signalen en groeperen (zuiver; ADR-004 blijft staan)

- `definities.wettelijke_termen(..., onderzoek)`: definities in contextbronnen tellen mee, zonder
  anker. Gebruiken twee formuleringen dezelfde term binnen het bereik van dezelfde contextdefinitie,
  dan geeft dat **`WETTELIJKE_TERM`, steun sterk**: de wet legt het verband, dus het is legitiem.
  Buiten het bereik geeft het `BUITEN_BEREIK`.
- **Nieuw tegen-signaal tegen `ZELFDE_BEPALING`**: `BEREKENING_IN_BEPALING`, onbeslist en zwak.
  Bevat de bronnode een berekeningspatroon op die term, dan wordt de link een possible link (een
  vraag). De regex komt in `regels/relaties.yaml`-formaat met vier testsoorten en een verklaring in
  `verklaringen.yaml`.
- Zonder onderzoek blijft de uitkomst bitgelijk aan nu. Dat bewaken de bestaande tests en
  `begrippen_eval`.
- De versies gaan omhoog: `signalen.VERSIE`, `definities.VERSIE` en `fragmenten.VERSIE`.

### 5. Definities (kaart en "scherper"): één gedeelde functie

- `fragmenten.voor_groep` en `kaartacties.fragmenten_voor` worden samengevoegd tot
  `fragmenten.onderzoeksfragmenten(manifest, onderzoek, leden, termen)`.
- De prioriteit is:
  1. definities in de context;
  2. de eigen bronnen;
  3. leden van hetzelfde artikel;
  4. verwijzingen;
  5. contextselecties.
- Er blijven hoogstens 40 fragmenten, in een stabiele volgorde.
- De prompt (`kaart.groepblok`, `kaartacties.kantblok`) krijgt het dossier mee: de bevindingen en de
  vragen.
- Het schema krijgt er strikte velden bij:
  - `soort` ∈ `begrip|berekeningsresultaat|afleidingsregel|toepassingsgeval`;
  - `bereik` ∈ `algemeen|specifiek`;
  - `voorkeursterm` (string);
  - `ontbreekt` (string, bij `geen`).
  Dit zijn interpretaties. Ze worden bewaard op het voorstel en sturen geen beslisregel aan.
- Nieuwe deterministische toetsen in `toetsen.signalen` (geel; de tekst staat in `TEKST`, en
  `frontend/lib` krijgt dezelfde codes vanwege de drift-test):
  - `ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE`: de definitie bevat woorden die alleen in één variant van
    `PARALLELLE_BEPALINGEN` voorkomen, terwijl de naam de kale term is. Een voorgestelde
    voorkeursterm gaat dan mee in de motivatie;
  - `RECHTSGEVOLG_IN_DEFINITIE`: patroon "grondslag voor", "in rekening gebracht", "dient als … voor de berekening";
  - `AFLEIDING_IN_DEFINITIE`: uitbreiding van `REKENREGEL`;
  - `ONDERBOUWING_EEN_VOORKOMEN`: de fragmenten komen uit één bron, terwijl er ≥2 voorkomens zijn;
  - `FRAGMENT_ONDERSTEUNT_NIET`: een gekozen fragment deelt geen inhoudswoord met de definitie;
  - `TEGENBEWIJS_IN_ONDERZOEK`: er is een andere definitie of een `BUITEN_BEREIK` voor de term;
  - `CONTEXT_NIET_ONDERZOCHT`: er is geen onderzoek of `ontbrekend` is niet leeg.
- **Afzien**: `herkomst=geen` met `ontbreekt` wordt een melding "onvoldoende bewijs: …" en geen
  definitie.
- De garanties gaan over de fragmentruimte manifest + onderzoek. Een letterlijke definitie uit een
  contextbron is toegestaan.

### 6. Voorbeelden

- De prompt krijgt eerst de onderscheidende kenmerken uit het dossier en de fragmenten.
- Het schema krijgt er per voorbeeld bij:
  - `soort` ∈ `positief|tegenvoorbeeld|grensgeval|afwijkend`;
  - `toetst` ∈ `begrip|scenario|voorwaarde|rechtsgevolg`;
  - `kenmerk` (een enum uit de kenmerken).
- Er is geen vast minimum meer.
- **Ontdubbelen** gebeurt deterministisch op `(oordeel, kenmerk, tekst met <getal>/<naam>/<jaar>)`.
  Een getal dat in een fragment voorkomt (een grenswaarde, zoals "6 maanden" of "19 weken") blijft
  letterlijk in de sleutel, en het teken (negatief, nihil, positief) blijft ook staan.
- Nieuwe codes:
  - `SEMANTISCH_DUBBEL`: het dubbele voorbeeld valt weg en de melding noemt het aantal;
  - `TOETST_ANDERE_VRAAG`: `toetst ≠ begrip` terwijl de definitie een begrip is.
- `GEEN_TEGENVOORBEELD` blijft bestaan.
- Het contract (`VoorstelInvoer`) krijgt de optionele velden `soort_voorbeeld`, `toetst` en
  `kenmerk`, achterwaarts compatibel. Bij het overnemen blijft `oordeel` het veld van het begrip.

### 7. Runs, bevestiging en cache

- De bevestiging bij het meedenken krijgt `werkvoorraad_id`: de hash van de gesorteerde
  batch-id's plus `onderzoek_id`, model en promptversie. Wijkt die af, dan komt er een nieuwe
  bevestiging. `aantal` blijft, voor de werkplek.
- `verdieping.batch_id` neemt `onderzoek_id` op.
- Fixes:
  - `kaartacties.promptversie("uitleg")`;
  - `uitwerken` start "scherper" niet wanneer er al open definitievoorstellen liggen.
- Hergebruik van onderzoek: dezelfde manifest- en onderzoeksstand levert hetzelfde dossier op. Het
  is zuiver, dus er is geen cache-tabel nodig.

### 8. Bewijs na het overnemen, projectie en export (api)

- `GET /v1/begrippen/{id}` krijgt een afgeleid veld `definitie_onderbouwing`, uit het voorstel achter
  de huidige definitierevisie (`begrip_revisies.detail.voorstel_id`):
  - de fragmenten (bron_iri, offsets, tekst);
  - `definitie_bron_iri`/`vindplaats`;
  - `onderzoek_id`;
  - per fragment de rol `ondersteunend`.

  Dit wordt alleen gelezen; er is geen nieuwe opslag en `inhoud` blijft slank.
- Projectie (`begrip_projectie.py`):
  - de bronnen van de fragmenten van de geaccepteerde definitie worden `dct:source`-documenten met
    `wa:rol "definitieonderbouwing"`;
  - een onderzochte maar niet gekozen bron wordt geen `dct:source`;
  - `niet` → `wa:tegenvoorbeeld`, `onzeker` → `wa:grensgeval`, en `skos:example` blijft alleen `wel`.

  De shapes blijven groen.
- De samenvatting in het gesprek (`begrippen_beurt`, `kaart_beurt`) noemt uit het opgeslagen onderzoek:
  - het aantal onderzochte bronnen;
  - wat ontbreekt;
  - het aantal open betekenisvragen.

  De tekst komt uit code, zonder vrij modelantwoord.

### 9. Frontend (klein)

`KaartVoorstel.tsx` toont, als ze er zijn:

- de nieuwe aandachtspunten;
- "onderzochte context: n bronnen, ontbreekt: …";
- per voorbeeld de soort en wat het toetst.

Er komt geen nieuwe werkplek. De drift-test op de codes wordt bijgewerkt.

### 10. Documentatie

- ADR-004 krijgt een aanvulling (de sectie *Onderzoeksstand*).
- `tools/graph-qa/CLAUDE.md` (begrippenketen) en `api/CLAUDE.md` worden bijgewerkt.
- In de skill komt in `references/begrippen.md` de nuance over de context: specifiek tegenover
  algemeen, een berekeningsresultaat, een afleiding als eigen begrip, en voorbeelden die toetsen.
  Daarna `genereer_methodepakket.py`.
- Er komt een meetlogboek-entry `metingen/betekenisonderzoek-2026-10-28/`.

## Kritieke bestanden

- graph-qa:
  - `agent/begrippen_pipeline/{model,fragmenten,definities,signalen,betekenis*,kaart,kaartacties,toetsen,verdieping,keten}.py`;
  - `regels/relaties.yaml` en `verklaringen.yaml`;
  - `agent/{begrippen_run,begrippen_verdieping,begrip_kaart,kaart_beurt,begrippen_beurt}.py`;
  - `agent/agents/begrippen.py`.
- api:
  - `begrip_onderzoek.py`* en `begrip_manifest.py`;
  - `begrippen_run_store.py` en `begrip_voorstel_store.py`;
  - `begrippen_verdieping.py`, `begrip_voorstel_contracts.py`, `begrippen_run_contracts.py`;
  - `begrip_store.py`, `begrip_projectie.py`, `db.py`.
- `packages/bronmodel`: de querybouwer voor verwijzingen.
- frontend: `components/werkgebieden/KaartVoorstel.tsx`, `lib/types.ts` en de codelijst.

\* nieuw

## Tests

- **Zuiver** (fixtures, zonder netwerk, database of model):
  - casus A en B als fixture uit de graaf, met teksten en `tekst_hash` (vastgelegd op 28-10-2026);
  - homoniem binnen één lid (bijdrage-inkomen-achtig), synoniem, een definitie met bereik
    "dit artikel" of onbekend, een contextdefinitie buiten de selectie;
  - een contextbron zonder annotaties, een ontbrekende bron en een overschreden budget;
  - dubbele ankers, gelijke tekst op verschillende ankers, een gemanipuleerd fragment-id;
  - een modelinterpretatie die nooit `Bewijs` wordt;
  - de determinisme-test: tweemaal dezelfde invoer geeft bitgelijke dossiers en id's;
  - zonder onderzoek bitgelijk aan nu.
- **Agent**: met `FakeLLM([])` blijft "voorstellen" modelvrij. Verder bevestiging met
  `werkvoorraad_id`, hervatten zonder dubbele batches of kosten, een verouderd onderzoek (een ander
  `O…`), "uitwerken" met open voorstellen, en de promptversie van uitleg.
- **Api**:
  - de onderzoeksbouw met prioriteit en budget;
  - de idempotentie op `onderzoek_id`;
  - de fragmenttoets op contextbronnen;
  - `definitie_onderbouwing` na het overnemen;
  - de projectie: `dct:source` alleen voor ondersteunende bronnen, tegenvoorbeelden niet als
    `skos:example`, SHACL groen;
  - TOOI ongewijzigd;
  - de contract-drift graph-qa ↔ api (`test_contract_drift`, `test_begrippen_manifest_drift`).
- **Frontend**: vitest, de drift van de codes, typecheck en lint.

## Verificatie en kwaliteitsmeting

1. De suites:
   - `cd tools/graph-qa && uv run --extra dev pytest -q`, en `scripts/genereer_* --check`;
   - api pytest, inclusief de Postgres-tests als `ANNOTATIE_TEST_DSN` lokaal kan;
   - in de frontend `npm test`, `npm run typecheck` en `npm run lint`.
2. `python -m eval.begrippen_eval --variant keten` voor en na: geen regressie op de bestaande sets.
   Het nieuwe tegen-signaal is een nieuwe regel, dus de held-out-status meld ik eerlijk.
3. Een nieuw `eval/betekenisonderzoek_eval.py`, offline en deterministisch, vergelijkt oud en nieuw op
   de casus-fixtures:
   - de gevonden en de gebruikte context;
   - de herkende bevindingen en vragen;
   - of de geconstateerde definities van A en B nu gemarkeerd worden;
   - de grootte van de prompt (tekens of tokens);
   - het gedrag bij bronuitval en budget.
4. Live modelmeting (**akkoord gebruiker, 28 okt 2026**): 3× kaart + scherper + voorbeelden op A en
   B, vóór (master) en na, lokaal via de acc-proxy en het modelprofiel (memory
   `lex-vervolggesprekken-traject`, `graphdb-mcp-proxy`); tokens en duur rapporteren.
5. Een jurist moet nog beoordelen: de juistheid van de voorgestelde definities, of de begrippen in
   casus A en B gelijk of specifiek zijn, en de rol van `dct:publisher`.


## Eindrapport (28 okt 2026)

### Opdrachttoets, na de uitvoering

| Aanname of bevinding | Uitkomst |
|---|---|
| 1–5. Het manifest en de fragmentruimte kennen alleen geannoteerde bronnodes | **Opgelost**: naast het manifest staat een onderzoeksstand (`Onderzoek`, `O…`). De fragmentruimte is manifest + onderzoek, in api en graph-qa. |
| 6. Bereiken en getypeerde relaties bestaan al | Hergebruikt: definities in contextbronnen gebruiken `Bereik`, de beslistabel is ongewijzigd. |
| 7. `ZELFDE_BEPALING` is methodisch te sterk | **Begrensd**: `BEREKENING_IN_BEPALING` maakt er een vraag van als de bepaling de term bewerkt. De regel is nieuw en op de bestaande sets niet getriggerd, dus er is nog geen held-out-bewijs. |
| 8. Fragmenttoetsen controleren alleen tekst | **Aangevuld**: acht inhoudelijke toetsen op definities, met het dossier. |
| 9. Voorbeelden worden alleen op tekst ontdubbeld | **Opgelost**: per voorbeeld kenmerk, soort en toets; ontdubbeld op (oordeel, kenmerk, genormaliseerde tekst). |
| 10–11. Voorstellen zonder model; agenttaken zonder verify | Zo gelaten. De borging zit in de keten: dossier, toetsen en garanties. |
| 12. Het bewijs gaat verloren na overnemen | **Opgelost**: `definitie_onderbouwing` en `dct:source` met de rol `definitieonderbouwing`, voor kaartvoorstellen en (nazorg 28 okt 2026) ook voor overnemen en akkoord op een groep, bevroren in het revisiedetail. De begripskaart in de werkplek toont haar nog niet. |
| Bevestiging alleen op aantal | **Opgelost**: `werkvoorraad_id`. |
| `promptversie("uitleg")` | **Opgelost**. |
| *uitwerken* start scherper naast open brondefinities | **Opgelost**. |
| Tegenvoorbeelden in de RDF | **Bewaakt**: *niet* → `wa:tegenvoorbeeld`, *onzeker* → `wa:grensgeval`, `skos:example` alleen *wel*, met een test. |
| `dct:publisher` = eerstverantwoordelijke organisatie | **Niet gewijzigd**: een beperking, zie hieronder. |
| Invorderingsrente of belastingrente | **Niet geverifieerd**: de naam van het werkgebied op acceptatie heb ik niet kunnen inzien (geen api-toegang vanuit deze sessie). De casussen gaan over *belastingrente* (AWR 30fb/30fc). |

### Oorzaken (casus A en B)

- **A**: het model zag alleen lid 4 en definieerde dus het toepassingsgeval. Met de leden 1–6 als
  context en het signaal `PARALLELLE_BEPALINGEN` (de variantwoorden positief/negatief/hoger/lager/
  groter/kleiner) kiest het in 3 van de 3 runs de algemene definitie.
- **B**: lid 7 was onzichtbaar, en een kwalificatie "geldt als … :" werd niet als zodanig herkend. Het
  model zette daarom de samenstelling (en het rechtsgevolg) in de definitie van de kale term. Nu staan
  `KWALIFICATIE_SAMENGESTELD`, `RECHTSGEVOLG_IN_DEFINITIE` en `TEGENBEWIJS_IN_ONDERZOEK` in het dossier
  en de toetsen, en ziet Lex af met een reden.

### Bestanden

- **graph-qa**: `begrippen_pipeline/{model,fragmenten,betekenis*,definities,signalen,keten,kaart,
  kaartacties,toetsen,verdieping}.py`, `betekenisregels/berekening.yaml`*, `verklaringen.yaml`;
  `agent/{begrippen_run,begrippen_verdieping,begrip_kaart,kaart_beurt,begrippen_beurt,models,agent,state}.py`,
  `agents/{begrippen,register}.py`, `nodes/supervisie.py`, `api/main.py`;
  `eval/betekenisonderzoek_eval.py`*, `eval/betekenisonderzoek_casus.json`*;
  tests `test_begrippen_onderzoek.py`* en `test_betekenis.py`*.
- **api**: `begrip_onderzoek.py`*, `begrip_manifest.py`, `begrippen_run_store.py`, `begrip_voorstel_store.py`,
  `begrippen_verdieping.py`, `begrip_store.py`, `begrip_projectie.py`, `db.py`, contracten
  (`begrippen_run_contracts`, `begrip_voorstel_contracts`, `gesprek_contracts`); test `test_begrip_onderzoek.py`*.
- **frontend**: `lib/{begripVoorstellen,kaartVoorstel,types,api}.ts`, `components/werkgebieden/KaartVoorstel.tsx`,
  `components/werkplek/{ThreadRij,WerkplekClient}.tsx`.
- **docs**: ADR-004 (*Aanvulling: de onderzoeksstand*), beide CLAUDE.md's, de skill `references/begrippen.md`
  (+ `methodepakket.py`), `referentieset-begrippen/onderzoek-id.vectoren.json`*, en het meetverslag.

\* nieuw

### Metingen

Zie [`metingen/betekenisonderzoek-2026-10-28/`](metingen/betekenisonderzoek-2026-10-28/README.md):

- de keten is bitgelijk aan de nulmeting;
- offline worden beide foutdefinities gemarkeerd;
- live hebben 6 van de 6 definities vóór een kernsignaal, en 1 van de 5 erna; A is algemeen, B ziet af met een reden;
- het verbruik per aanroep is ongeveer 2× zo groot.

### Beperkingen

- **Een ontwikkelset**: twee casussen, en de toetsen zijn erop ontworpen. Voor generalisatie is een
  held-out-set nodig (bijvoorbeeld bijdrage-inkomen in de Zvw, of een andere parallelle reeks).
- **`ROL_IN_BEPALING`** kent alleen *voorwaarde* en *grondslag van een berekening*.
- **Namen in voorbeelden** worden heuristisch herkend.
- **Verwijzingen**: de api volgt één stap uitgaand. Een doel in een regeling die niet in de graaf
  staat, wordt `niet_in_graaf`.
- **Onderzoek op acceptatie** is niet live gemeten via de api. De live meting bouwde het onderzoek zoals
  de api dat zou doen; `begrip_onderzoek` zelf is met fixtures getest.
- **`dct:publisher`**: een uitgever is niet hetzelfde als de eerstverantwoordelijke organisatie. Dat staat
  er nog zo; het is een besluit voor de gebruiker.

### Wat de jurist nog moet beoordelen

- Of de algemene definitie van *herziening* juist is ("wijziging van een voorlopige aanslag IB/Vpb waarbij
  het bedrag verandert"), en of de varianten van 30fb eigen (specifieke) begrippen moeten worden.
- Of *belasting* in 30fc een eigen begrip is, en of *het te betalen bedrag aan belasting* (lid 7, na
  verrekening) een eigen begrip met een afleidingsregel is.
- De rol van `dct:publisher` in de export.
- Of het werkgebied van de casus over belastingrente gaat of over invorderingsrente (en dus de naam).
