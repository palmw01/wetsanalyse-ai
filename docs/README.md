# docs/ — wegwijzer

Deze map mengt zeven soorten materiaal. Ze vragen elk een andere omgang, en dat verschil is aan de
mapnamen niet af te lezen — vandaar deze index.

| soort | wat het betekent |
|---|---|
| **bron van derden** | niet van ons, niet aanpassen; wijzigingen vastleggen in `BRON.md` |
| **specificatie** | beschrijft ons systeem; moet met de code meebewegen |
| **plan** | mag verouderen, mits de status gedateerd en eerlijk is |
| **runbook** | operationeel; klopt of klopt niet, geen tussenvorm |
| **besluit** (ADR) | legt een keuze en haar afweging vast; blijft staan, een nieuw besluit vervangt het |
| **onderzoek** | onderzoeksontwerp of -protocol; gedateerd, en gevolgd tot het is uitgevoerd |
| **meting** | bewijs; nooit achteraf wijzigen, een correctie krijgt een eigen rij of map |

## De methode

- **`wetsanalyse/wetsanalyse-rijk/`** — *bron van derden.* De officiële Wetsanalyse-documentatie
  van BZK onder de **W3C-licentie** (dus buiten de EUPL van de rest van dit project); herkomst en
  afwijkingen staan in [`BRON.md`](wetsanalyse/wetsanalyse-rijk/BRON.md). `H2-JAS.md` is de
  **gezaghebbende** klassenindeling: per klasse een omschrijving, een herkenningsvraag en de
  uitdrukkingswijze.
- **`wetsanalyse/wa-table.png`** — *bron van derden.* De officiële JAS-tabel: zestien genummerde
  klassen met korte definities en de kleurcodering. De labelkleuren in
  `api/app/jas_klassen.py` en `frontend/lib/jas.ts` zijn hieruit gesampled.
  Deze afbeelding staat er twee keer, byte-identiek: ook als
  `wetsanalyse/wetsanalyse-rijk/media/wa-table.png`. Dat is bewust — de code verwijst naar het
  bovenste pad, en de kopie in `media/` hoort bij het onveranderd overgenomen bronmateriaal.
- **`wetsanalyse/WetsTaal.md`** — *bron van derden* (CC0). De WetsTaal-handreiking, een **werkversie**
  en uitdrukkelijk geen vastgestelde standaard. Een andere methodetaal dan het JAS; behandel hem
  als achtergrond, niet als gezag naast `H2-JAS.md`.

**Waar de methode wordt toegepast:** niet hier, maar in
[`.claude/skills/wetsanalyse/`](../.claude/skills/wetsanalyse/). Die skill is de operationele
annoteerinstructie voor activiteit 2 en de **bron** van de klassetekst in de code —
`tools/graph-qa/agent/jas_klassen.py` wordt eruit gegenereerd (zie
`tools/graph-qa/scripts/genereer_jas_klassen.py`, bewaakt door `tests/test_methode_drift.py`).
Wil je het gedrag van de annotator bijsturen, bewerk dan de skill.

### Lokaal-only bronmateriaal

Het boek (Boom uitgevers) en de readers van het Expertisecentrum BRM ("bestemd voor gebruik binnen
de Belastingdienst") horen niet in deze publieke repo. Ze staan in `.gitignore`, op de **vorm** van
het bestand en niet op één map (`docs/**/*.pdf`, `docs/**/*.pages.md`, `docs/**/wetsanalyse-boek.md`):
een regel op één pad laat een kopie op een andere plek door. Alle PDF's onder `docs/` zijn daarom
standaard genegeerd, ook die in `kennisbank/` en `regelspraak/`. Controleer na een wijziging aan die
regels altijd met `git check-ignore -v <pad>`.

Heb je dat materiaal rechtmatig, dan werkt het gewoon lokaal. De kennis eruit mag in de skill
landen; de tekst niet.

**`wetsanalyse/bronnen/`** — het [manifest](wetsanalyse/bronnen/manifest.json) van de lokaal
bewaarde originelen (bron-ID, herkomst, versie, SHA-256) waarnaar de skill verwijst via
`references/bronnen.md`. Alleen de README, het manifest en een `.gitignore` staan in git; de PDF's en
HTML-bestanden zelf zijn lokaal.

## Per doel één ingang

| Vraag | Document | Soort |
|---|---|---|
| Wat moeten we nog doen? | [`PLAN.md`](PLAN.md) | plan |
| Hoe werkt de annotatieketen nu? | [`architectuur/annotatieketen.md`](architectuur/annotatieketen.md) | specificatie |
| Hoe werken het annotatiedomein en de graaf? | [`architectuur/annotatie-bronnodes.md`](architectuur/annotatie-bronnodes.md) + [`wetsanalyse-workbench/jas-annotatie-ontologie.md`](wetsanalyse-workbench/jas-annotatie-ontologie.md) | specificatie |
| Hoe werkt de bronselectie per deelvraag? | [`architectuur/bronselectie-per-deelvraag.md`](architectuur/bronselectie-per-deelvraag.md) | specificatie |
| Hoe verhouden artefacten zich tot het artefactmodel van Claude? | [`architectuur/artefacten-langs-claude.md`](architectuur/artefacten-langs-claude.md) | onderzoek |
| Wat is de projectmethode en hoe landt die in de agents? | [`wetsanalyse/methode-onderzoek.md`](wetsanalyse/methode-onderzoek.md) + de skill | specificatie |
| Wat is er gemeten? | [`architectuur/metingen/README.md`](architectuur/metingen/README.md) | meting |
| Hoe valideren we juridisch? | [`architectuur/onderzoek-empirische-validatie.md`](architectuur/onderzoek-empirische-validatie.md) + [`wetsanalyse/referentieset/`](wetsanalyse/referentieset/README.md) | onderzoek |
| Waartegen meten we begrippen en bronselectie? | [`wetsanalyse/referentieset-begrippen/`](wetsanalyse/referentieset-begrippen/README.md) en `wetsanalyse/referentieset-bronselectie/` (per set een conceptmap met eigen README) | meting |
| Wat bleek uit het onderzoek naar invordering? | [`wetsanalyse/onderzoek-invordering-2026-09-29/`](wetsanalyse/onderzoek-invordering-2026-09-29/README.md) | onderzoek |
| Wat biedt INT-terminologie voor activiteit 2 en 3? | [Volledig onderzoek als HTML-pagina](wetsanalyse/onderzoek-int-terminologie-2026-10-08/index.html) · [dossier van 8 oktober 2026](wetsanalyse/onderzoek-int-terminologie-2026-10-08/README.md), met alle hulpmiddelen en relevante concepten | onderzoek |
| Hoe vindt een werkgebied zijn bronnen, en welke taalpatronen helpen bij begrippen? | [`architectuur/onderzoek-werkgebied-en-begrippen-2026-10.md`](architectuur/onderzoek-werkgebied-en-begrippen-2026-10.md) | onderzoek |
| Waarom is het zo ontworpen? | [ADR-001](architectuur/adr-001-hybride-jas-pijplijn.md), [ADR-002](architectuur/adr-002-taalprovider.md), [ADR-003](architectuur/adr-003-nl-sbb-begrippencontract.md), [ADR-004](architectuur/adr-004-begrippenketen.md), [ADR-005](architectuur/adr-005-vraag-lex-en-agents.md), [ADR-006](architectuur/adr-006-generieke-begrippen.md), [ADR-007](architectuur/adr-007-llm-pad-en-verwerker.md) (concept), [ADR-008](architectuur/adr-008-antwoordsjablonen.md) | besluit |
| Hoe praat Lex? | [`schrijfrichtlijn-lex.md`](schrijfrichtlijn-lex.md) | specificatie |
| Hoe test een agent-team de hele keten op acceptatie? | [`acceptatie/briefing-team.md`](acceptatie/briefing-team.md) + [`acceptatie/wetsanalyse-e2e.md`](acceptatie/wetsanalyse-e2e.md) | runbook |

Toelichting bij enkele documenten:

- **`PLAN.md`** is het enige plan. Wat af is gaat eruit; ontwerpbesluiten horen in een ADR of
  specificatie. Eén uitwerking staat apart, omdat `PLAN.md` ernaar verwijst:
  [`architectuur/plan-betekenisonderzoek.md`](architectuur/plan-betekenisonderzoek.md) (spoor M).
- **`architectuur/verbeterplan-jas-pipeline-2026-10-08.md`** is *onderzoek*: het ontwerp voor de
  kandidaten na V7 uit spoor A (bewijs per hypothese, frames, relaties), met eigen meet- en
  acceptatiecriteria. Het start na V7.
- **`architectuur/annotatieketen.md`** beschrijft de stappen, de configuratie, het beslisbeleid,
  de detectoren en de bekende beperkingen van `hybrid_v1`, de enige annotatieketen.
- **`wetsanalyse-workbench/jas-annotatie-ontologie.md`** beschrijft de RDF-projectie van de
  annotatielagen (`api/app/graaf_projectie_v2.py`): één laag per bronnode, in
  `urn:jas:graph:v2:<laag-id>`. De api is de waarheid over lifecycle, beslissingen en dekking; de
  graaf is een projectie.
- **ADR-001** is uitgevoerd: de hybride keten is de enige annotatieroute. **ADR-002** legt de
  taalprovider vast (spaCy, `nl_core_news_md`). **ADR-003** maakt NL-SBB het datacontract
  voor begrippen; de projectie naar de graaf staat er. **ADR-004** ontwerpt de begrippenketen die
  betekenisgroepen voorstelt; de voorstellen staan er, de meting per deelkeuze loopt door.
  **ADR-005** legt Vraag Lex en de agents vast, met een aanvulling over de tekstroutes vóór de
  supervisor. **ADR-006** legt de generieke begrippen vast, gebouwd en op acceptatie. **ADR-007** is een
  concept over het LLM-pad en de verwerker, met open punten voor de eigenaar. **ADR-008** maakt van een
  antwoord een toolaanroep op een sjabloon; dat geldt nu voor het sjabloon `begrip`.
- **`architectuur/onderzoek-empirische-validatie.md`** bevat de fouttaxonomie v2, de metrics, het
  adjudicatieprotocol en de stopcriteria (§18). V1–V6 zijn uitgevoerd, V7 is open.
- **`architectuur/metingen/`** is bewijs: meetbestanden worden niet achteraf gewijzigd. Het
  onderzoek naar invordering staat in `wetsanalyse/onderzoek-invordering-2026-09-29/`, omdat
  code en meethashes dat pad gebruiken.
- **De zes familiedossiers in `wetsanalyse/referentieset/`** (`awb.md`, `bw6.md`, `iw.md`,
  `omgevingswet.md`, `rvv.md`, `wzt.md`) zijn gegenereerd uit `v1/cases.json`
  (`tools/graph-qa/scripts/render_jas_referentieset.py`, met `--check` als controle). Bewerk de
  JSON, niet de Markdown.

## Runbook

- **`observability.md`** — logschema, tracing, Grafana, de controle-meting. Operations, geen
  methode; het staat hier omdat er nog geen betere plek voor is.
- **`acceptatie/`** — het scenario en de briefing voor een acceptatietest van begin tot eind met de
  [acceptatie-MCP](../tools/wetsanalyse-acceptatie-mcp/README.md). Lokale runs staan in
  `acceptatie/lokaal/` en gaan niet in git.
