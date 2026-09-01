# docs/ — wegwijzer

Deze map mengt vier soorten materiaal. Ze vragen elk een andere omgang, en dat verschil is aan de
mapnamen niet af te lezen — vandaar deze index.

| soort | wat het betekent |
|---|---|
| **bron van derden** | niet van ons, niet aanpassen; wijzigingen vastleggen in `BRON.md` |
| **specificatie** | beschrijft ons systeem; moet met de code meebewegen |
| **plan** | mag verouderen, mits de status gedateerd en eerlijk is |
| **runbook** | operationeel; klopt of klopt niet, geen tussenvorm |

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

## Specificaties van ons systeem

- **`wetsanalyse-workbench/jas-annotatie-ontologie.md`** — de RDF-projectie van het annotatiedomein
  naar de graaf. **Nog niet gebouwd** (Fase 4). Het *werkende* domein staat niet hier maar in
  `api/app/annotatie_contracts.py` — dat bestand is de waarheid over lifecycle, beslissingen en
  Critic-rondes.
- **`schrijfrichtlijn-lex.md`** — toon en opmaak van de assistent Lex. Zijn identiteit staat in
  `tools/graph-qa/agent/prompts.py`.

## Plannen

- **`wetsanalyse-workbench/PLAN.md`** — de workbench en de annotatie-agent. Fase 1 en het grootste
  deel van Fase 2 zijn gebouwd; het bestand is plan én changelog, dus lees de latere kaders als de
  actuele stand.
- **`kennisbank/PLAN.md`** — een tweede corpus (beleidsstukken, handleidingen) naast de wetsgraaf.
  Nog niets van gebouwd. Lees dit vóór je aan retrieval of grounding werkt: het stelt eisen aan
  allebei.

## Runbook

- **`observability.md`** — logschema, tracing, Grafana, de controle-meting. Operations, geen
  methode; het staat hier omdat er nog geen betere plek voor is.
