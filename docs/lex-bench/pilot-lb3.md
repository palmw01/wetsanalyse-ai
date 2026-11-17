# Voorstel: de pilot LB3

Soort: *voorstel* (vraagt akkoord) · Plan: [`../architectuur/plan-lex-bench.md`](../architectuur/plan-lex-bench.md) §4, §7, §9,
§22 · Stand: 17 nov 2026, voorbereid, **niets gedraaid**

De pilot draait het hele proces één keer op drie nieuwe ontwikkelcasussen, één per niveau: het team blind, bevriezen,
arm L1, de reviewer, en arm L2 op één casus. Hij meet de tokens en toetst of het formulier werkt. Daarna liggen de
plafonds van §7 vast. Dit stuk vraagt het akkoord op het budget en de werkwijze. Zonder dat akkoord draait er geen model
en start er geen `bench-analist` of `bench-reviewer`.

## De drie casussen

De dossiers staan in [`bronselectie/pilot/`](bronselectie/pilot/). Ze zijn geschreven in eigen woorden, zonder de
graaf of Lex te raadplegen, door een Claude-sessie die de bronselectie niet afstemt (besluit 3). Er staat **geen
verwachting** in: geen bepaling, geen artikelnummer, geen `verwacht` of `uitgesloten`. Die komen van het team. Het niveau
is vastgelegd vóór Lex erop draait (§3.2). Een poorttest bewaakt beide (`tests/poort/test_lex_bench_team.py`).

Alle drie gaan over iets anders dan de invordering, waar de zes bestaande sets over gaan (§4.1). De Mijnbouwwet blijft
bewust vrij voor een blinde casus.

- **LB-07, makkelijk: Beslissen op een aanvraag binnen de termijn.** De Awb alleen. Wanneer moet een bestuursorgaan op
  een aanvraag beslissen, wat doet het als het de termijn niet haalt, en wanneer krijgt de aanvrager een dwangsom? Drie
  deelvragen, in de woorden van de wet.
- **LB-08, gemiddeld: Terugbetalen van een te hoog voorschot toeslag.** De Awir, de Awb en de uitvoeringsregeling van de
  Awir. Hoe ontstaat het bedrag, wanneer en in hoeveel delen wordt het terugbetaald, en wat gebeurt er als dat niet op
  tijd gebeurt? De kern ligt in twee regelingen, met een verwijzing ertussen.
- **LB-09, moeilijk: Achteraf alsnog belasting vragen.** De AWR en de Awb. Hoe ver terug kan de Belastingdienst over een
  afgehandeld jaar geld bijvragen, ook bij geld in het buitenland, en komen er rente en een straf bij? Er is een
  woordenkloof: het dossier zegt *geld bijvragen* en *straf*, niet de woorden van de wet. Vier deelvragen.

**Analisten** (besluit 4): bij LB-07 één analist met een tegenlezer, bij LB-09 twee. Voor gemiddeld noemt besluit 4
niets. Bij LB-08 stel ik twee analisten voor, de werkwijze van §4.2. Kies je er één met een tegenlezer, dan scheelt dat
ongeveer 100k.

## De L2-casus: LB-08

Arm L2 draait in de pilot op één casus (besluit 5). Ik kies **LB-08**:

- de bronselectie moet daar over twee regelingen en een verwijzing heen, en dat ziet L2 met de echte graaf en het echte
  gesprek beter dan L1;
- de Awb alleen (LB-07) is groot, en een zoekfout valt daar eerder weg in de ruis;
- LB-09 heeft een vierde deelvraag, dus meer stappen in het gesprek en meer tokens, voor een eerste meting zonder
  plafond uit de praktijk.

## Tokens per arm

Het team en de reviewer draaien in Claude Code. Hun tokens komen uit het abonnement van de gebruiker, niet uit het
budget van Lex. Arm L2 draait in Lex en telt mee in het weekbudget van het account (zie *Account* hieronder).

| arm | wie | aantal | schatting per stuk | plafond per stuk | plafond samen |
|---|---|---|---|---|---|
| T, analist | `bench-analist` | 5 (LB-07: 1, LB-08: 2, LB-09: 2) | 100–200k | 250k | 1,25M |
| T, tegenlezer | `bench-reviewer`, tegenlezen | 1 (LB-07) | 50–100k | 150k | 0,15M |
| reviewer | `bench-reviewer`, verschillen | 3 | 80–150k | 200k | 0,6M |
| coördinator | de sessie die de pilot draait | 1 | 100–150k | 200k | 0,2M |
| L1 | code, offline | 3 | 0 | 0 | 0 |
| L2 | Lex op acceptatie | 1 (LB-08) | 20–50k | 100k | 0,1M |

- **Claude Code samen:** een schatting van 0,9–1,7M, met een plafond van **2,2M**.
- **Lex:** een schatting van 20–50k, met een plafond van **100k**.

**Waar de schatting vandaan komt:**

- *Analist.* De opdracht is ongeveer 17.000 tekens, zo'n 5k tokens: de briefing, twee uitwerkingen uit de skill, het
  dossier en het formulier. Daar komen de systeemprompt en de toolschema's van een subagent bij. `bron_lezen` geeft per
  artikel de tekst en de XML, tot 40.000 tekens elk. Voor een gewoon artikel is dat 1–3k tokens. Per casus verwacht ik
  15–30 aanroepen van `bron_lezen` en 5–15 van `graaf_lezen` (zoeken). §7 schatte hetzelfde: 100–200k.
- *Reviewer.* Die leest alleen de bepalingen waarover een verschil gaat. Op het nulpunt van LB1 had elke casus 38 tot 43
  verschillen tussen L1 en de verwachting. Bij een nieuwe casus zal dat vergelijkbaar zijn, en de reviewer leest de
  meeste bepalingen één keer.
- *L2.* De bronselectie per deelvraag is code zonder model. Het E2E-verslag Rekeningafspraken noemt ongeveer 15k context
  per besluit, en L2 neemt geen besluiten.

**Wat telt:** per subagent het verbruik dat de Agent-tool na afloop meldt, en bij L2 het verschil in
`/api/account/verbruik` vóór en na. Beide gaan in het runrecord (§6). De pilot legt ook vast hoe het getal van de
Agent-tool zich verhoudt tot wat de cache leest. Daarna liggen de plafonds van §7 vast.

**Stopregels:**

- De agents draaien één voor één, nooit naast elkaar.
- Halverwege een subagent zie ik zijn verbruik niet. Het plafond is daarom een grens *tussen* agents: eindigt er één
  boven zijn plafond, of komt het totaal boven 2,2M, dan start er niets nieuws. Ik meld het dan aan de hoofdsessie, en
  de gebruiker beslist.
- Een formulier met fouten gaat één keer terug naar dezelfde analist, met de fouten van `controleer`. Klopt het daarna
  nog niet, dan stopt die casus.
- L2 stopt na de deelvraag waarin het verschil in verbruik boven 100k komt. Dat is de regel `BUDGET_OP` uit het
  meetscript van de centrale agent.

## Hoe de run verloopt

De coördinator is een Claude Code-sessie in een eigen worktree. Dat is deze sessie, of een verse. De coördinator draait
de code en start de agents, maar beoordeelt zelf niets en ziet de keuze van Lex pas na het bevriezen.

1. **Opdracht.** Per analist: `uv run python -m eval.lex_bench_team opdracht --dossier
   docs/lex-bench/bronselectie/pilot/<casus>/set.json --casus LB-0x --analist A --run lb-0x-<datum>-a`. De opdracht
   bevat het dossier zonder niveau, toelichting of verwachting.
2. **Analist.** De coördinator start `bench-analist` met die opdracht als prompt. De analist leest de wettekst
   (`bron_lezen`, bij overheid.nl), zoekt in de graaf (`graaf_lezen`, alleen lezen) en schrijft in zijn eigen logboek. Hij
   ziet Lex niet en leest geen bestanden uit de repo: dat kan het profiel niet.
3. **Controleren.** `controleer` toetst het formulier.
4. **Tegenlezen** (alleen LB-07). `lex_bench_review tegenlezen` maakt de opdracht en `bench-reviewer` leest het formulier
   tegen, zonder Lex.
5. **Samenvoegen en bevriezen.** `lex_bench_team samenvoegen` (bij LB-07 met `--tegenlezing`) schrijft de
   teamverwachting, de formulieren en hun sha256 naar de meetmap `docs/architectuur/metingen/lex-bench-<datum>-pilot/<casus>/`.
   Een map die al bestaat, weigert het.
6. **Opname.** Pas na het bevriezen: `lex_bench_review opnemen --dossier <set.json> --uit <meetmap>/<casus>/graafantwoorden.json`.
   Dat draait de route van L1 live tegen de graaf, op het dossier alleen. Het toont geen keuze van Lex en overschrijft
   geen bestaande opname. Het vraagt de MCP-proxy van acceptatie en het token daarvan, lokaal, en geen model.
7. **L1 en de reviewer.** `lex_bench_review opdracht` maakt de genummerde verschillen tussen L1 en de teamverwachting.
   `bench-reviewer` stelt per verschil een categorie voor, en `verwerk` toetst en telt.
8. **L2 op LB-08.**
   - Verbruik vóór.
   - Via de acceptatie-MCP een werkgebied *Bench LB-08 <run>* met het dossier en de deelvragen.
   - Een gesprek in dat werkgebied, met de vraag *Help mij de bronnen bij dit werkgebied te bepalen*.
   - Per deelvraag de lijst lezen die het paneel voorstelt, in de volgorde van de werkplek, en dan *Klaar* voor de
     volgende. Bench neemt niets op en sluit niets uit.
   - Verbruik na.
   - `lex_bench_review l2` meet die lijst met dezelfde maten als L1.
9. **Vastleggen.** In de meetmap komen het runrecord (`run.json`: commit, image-digests, zoekversie, model van Lex en van
   het team, hashes, verbruik per arm en plafonds), de rapporten per casus en een README. Er komt een regel in het
   meetlogboek, en de hoofdsessie krijgt een melding. In een aparte PR daarna komen de drie casussen in het manifest
   (`bench-bronselectie-v2`), met hun teamverwachting als `concept`.

## Account en wat er op acceptatie ontstaat

- **Account.** De acceptatie-MCP werkt met het gedeelde account van de gebruiker, een beheerder. Er komt geen account of
  token bij. L2 telt dus in het weekbudget van dat account. Wil je L2 liever op een apart analistaccount, dan moet de
  gebruiker dat zelf aanmaken: deze sessie maakt geen accounts aan.
- **Team, reviewer, opname en L1** maken op acceptatie niets aan. Ze lezen de graaf en de officiële bron. Het logboek van
  een agent staat lokaal (`docs/acceptatie/lokaal/<run>/logboek.md`, buiten git).
- **L2 maakt aan:**
  - één werkgebied *Bench LB-08 <run>*, met het dossier en drie deelvragen;
  - één gesprek in dat werkgebied, met zijn berichten en runs;
  - de stand per deelvraag: na *Klaar* staat een deelvraag op *voorlopig afgerond*;
  - regels in het verbruiksjournaal, de audit en de logs.

  Er komen geen bronselecties, annotaties of begrippen bij.
- **Werkgebieden zijn gedeeld.** Elke gebruiker van acceptatie ziet *Bench LB-08 …* staan. De naam zegt waar het voor
  is.
- **Opruimen.**
  - Het werkgebied en het gesprek blijven staan als bewijs bij de meetmap (§4.4).
  - Weghalen gebeurt alleen op een woord van de gebruiker. Dan gaat alleen dat werkgebied weg, en het gesprek, elk op
    hun id: nooit in bulk, en nooit iets anders op het gedeelde account.
  - Het verbruiksjournaal en de audit zijn append-only en blijven altijd staan.

## Wat het akkoord dekt

1. Het budget: 2,2M in Claude Code en 100k in Lex, met de stopregels hierboven.
2. De drie dossiers en hun niveau, of een aanpassing ervan.
3. LB-08 als L2-casus, op het gedeelde account.
4. Twee analisten bij LB-08 (of één met een tegenlezer).
5. Het werkgebied en het gesprek die L2 op acceptatie achterlaat.

## Open na de pilot

- Of *Klaar* zonder besluit de volgende deelvraag opent zoals verwacht. Dat is het eerste wat L2 laat zien. Lukt het
  niet, dan stopt L2 na de eerste deelvraag en meldt de coördinator het.
- Hoe het getal van de Agent-tool zich verhoudt tot de cache. Daarna liggen de plafonds van §7 vast.
- Een jurist die de drie teamverwachtingen vaststelt. Tot dan zijn de cijfers een trendmeting (besluit 2).
