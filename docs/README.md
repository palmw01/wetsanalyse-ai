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
het bestand en niet op één map — dat is twee keer misgegaan met een te specifiek pad. Alle PDF's
onder `docs/` zijn daarom standaard genegeerd. Controleer na een wijziging aan die regels altijd
met `git check-ignore -v <pad>`.

Heb je dat materiaal rechtmatig, dan werkt het gewoon lokaal. De kennis eruit mag in de skill
landen; de tekst niet.

## Per doel één ingang

| Vraag | Document | Soort |
|---|---|---|
| Wat moeten we nog doen? | [`PLAN.md`](PLAN.md) | plan |
| Hoe werkt de annotatieketen nu? | [`architectuur/annotatieketen.md`](architectuur/annotatieketen.md) | specificatie |
| Hoe werken het annotatiedomein en de graaf? | [`architectuur/annotatie-bronnodes.md`](architectuur/annotatie-bronnodes.md) + [`wetsanalyse-workbench/jas-annotatie-ontologie.md`](wetsanalyse-workbench/jas-annotatie-ontologie.md) | specificatie |
| Wat is de projectmethode en hoe landt die in de agents? | [`wetsanalyse/methode-onderzoek.md`](wetsanalyse/methode-onderzoek.md) + de skill | specificatie |
| Wat is er gemeten? | [`architectuur/metingen/README.md`](architectuur/metingen/README.md) | meting |
| Hoe valideren we juridisch? | [`architectuur/onderzoek-empirische-validatie.md`](architectuur/onderzoek-empirische-validatie.md) + [`wetsanalyse/referentieset/`](wetsanalyse/referentieset/README.md) | onderzoek |
| Waarom is het zo ontworpen? | [ADR-001](architectuur/adr-001-hybride-jas-pijplijn.md), [ADR-002](architectuur/adr-002-taalprovider.md) | besluit |
| Hoe praat Lex? | [`schrijfrichtlijn-lex.md`](schrijfrichtlijn-lex.md) | specificatie |

Toelichting bij enkele documenten:

- **`PLAN.md`** is het enige plan. Wat af is gaat eruit; ontwerpbesluiten horen in een ADR of
  specificatie.
- **`architectuur/annotatieketen.md`** beschrijft de stappen, de configuratie, het beslisbeleid,
  de detectoren en de bekende beperkingen van `hybrid_v1`. Het vervangt de losse
  `hybrid-v1-*`-documenten van 27–29 september; die staan in de git-geschiedenis.
- **`wetsanalyse-workbench/jas-annotatie-ontologie.md`** beschrijft de RDF-projectie van de
  annotatielagen (`api/app/graaf_projectie_v2.py`): één laag per bronnode, in
  `urn:jas:graph:v2:<laag-id>`. De api is de waarheid over lifecycle, beslissingen en dekking; de
  graaf is een projectie. `jas-ontologie.ttl` en `api/app/jas_ontologie.py` horen bij het oudere
  v1-pad (laag per artikel) en blijven als historie staan.
- **ADR-001** is uitgevoerd t/m PR 18 (25 sep 2026). De opdracht erachter
  (`opdracht-jas-annotatiepijplijn.md`) staat alleen nog in de git-geschiedenis.
- **`onderzoek-empirische-validatie.md`** bevat de fouttaxonomie v2, de metrics, het
  adjudicatieprotocol en de stopcriteria (§18). V1–V6 zijn uitgevoerd, V7 is open.
- **`architectuur/metingen/`** is bewijs: meetbestanden worden niet achteraf gewijzigd. Het
  onderzoek naar invordering staat in `wetsanalyse/onderzoek-invordering-2026-09-29/`, omdat
  code en meethashes dat pad gebruiken.
- **`wetsanalyse/referentieset/*.md`** zijn gegenereerd uit `v1/cases.json`
  (`render_jas_referentieset.py --check`). Bewerk de JSON, niet de Markdown.

## Runbook

- **`observability.md`** — logschema, tracing, Grafana, de controle-meting. Operations, geen
  methode; het staat hier omdat er nog geen betere plek voor is.
