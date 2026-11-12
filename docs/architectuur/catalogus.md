# De catalogus: wat Lex kan

Dit is het werkdocument bij [ADR-014](adr-014-catalogus.md). Het hoort bij de soort **specificatie** en beweegt mee met de code.

## Wat er nu is (inventaris van 12 nov 2026)

| Onderdeel | Register | Vorm | Generator / drift |
|---|---|---|---|
| Methode en rollen | `.claude/skills/wetsanalyse/` + `agentrollen.json` → `agent/methodepakket.py` | md + JSON, gegenereerd | `genereer_methodepakket.py --check`, `test_methodepakket`, `test_methoderollen` |
| JAS-klassen | `references/jas-klassen-referentie.md` → `agent/jas_klassen.py` | md, gegenereerd | `genereer_jas_klassen.py --check`, `test_methode_drift` |
| Relatiecatalogus | `relaties.json` → api, graph-qa, frontend | JSON, gegenereerd | `genereer_jas_relaties.py --check`, `tests/poort/test_relatiecatalogus.py` |
| Specialisten | `agent/specialists.py` `SPECIALISTS` | dataclass | `test_specialists` |
| Agents en taken | `agent/agents/register.py` `AGENTS` + `models.ACTIE_TAAK` | modules met `Taak`/`MODEL_TAKEN` | `test_agents`, `test_agent_contracten` |
| Sjablonen | `agent/sjablonen/` `SJABLONEN` + `bronmodel/antwoord.py` | dataclass + Literal | `test_sjablonen` |
| Regie | `agent/regie/` | dataclasses + tabellen | `test_regie_*`, `test_regisseur` |
| Routes | de volgorde in `nodes/supervisie.py` | code, nog geen tabel | `tests/poort/test_routecontract.py` |
| Connectors | `bronmodel/connectors.py` `CONNECTORS` | beschrijving als enige bron | `test_connectorbeschrijving` |
| Detectieprofielen | `jas_pipeline/profielen/*.yaml` | YAML, één per klasse | `test_detectieprofielen` |
| Detectorregels | `jas_pipeline/detectoren/regels/*.yaml` + Python-detectoren | YAML + code | `test_detectoren` |
| Verklaringen | `jas_pipeline/verklaringen.yaml`, `begrippen_pipeline/verklaringen.yaml` | YAML → api | `genereer_jas_vocabulaire.py --check`, `test_verklaringen` |
| Begrippenregels | `begrippen_pipeline/regels/`, `betekenisregels/`, `b1_woorden.yaml`, `geen_begrip.yaml` | YAML; de beslistabel is code | patroontests |
| Zoekvragen en bronselectie | `zoekvragen.py`, `bronnen_vinden.py`, `deelvraag_zoeken.py` | code; de skillreference is proza | `ZOEKVERSIE`-hash, bronselectie-eval |
| Agent-allowlist | `api/app/agent_toegang.py` `TOEGESTAAN` | code | `tests/poort/test_agent_toegang.py` |

## Een onderdeel toevoegen, per soort

Elk nieuw onderdeel krijgt een beschrijving. Zonder beschrijving wordt `tools/graph-qa/tests/test_catalogus.py` rood.

**Methode** (een nieuwe skill, zoals wetsuitvoering)
1. Leg de bron vast in `docs/wetsanalyse/<bron>/` met een `BRON.md`. Die bevat herkomst, commit of datum, de licentie
   met notice, en de wijzigingen. Zet de bron ook in `docs/wetsanalyse/bronnen/manifest.json`. Materiaal dat niet
   letterlijk mag, komt niet in de repo; zie `docs/README.md`.
2. Maak `.claude/skills/<naam>/` met:
   - `SKILL.md`: `name`, `description` en `metadata.lex` (`soort: methode`, `herkomst`, `licentie`, `letterlijk`);
   - `agentrollen.json`;
   - `references/bronnen.md` met eigen broncodes.
3. Begin met methodetekst voor **bestaande** rollen: `agentrollen.json` noemt zijn secties en per rol welke hij
   toevoegt. Sectie-ids en broncodes zijn uniek over de skills; een nieuwe rol of eigen classificaties volgen ADR-014 §5.
   Met `lex_letterlijk: "ja"` hoort er een `BRON.md` met de licentie in de skillmap.
4. Draai `uv run python scripts/genereer_jas_klassen.py`. Die draait de methodepakketgenerator mee; hij vindt elke map
   onder `.claude/skills/` met `lex_soort: "methode"`. Er is geen code nodig: `tests/test_skill_zonder_code.py` bewijst
   het met een nep-skill.

**Rol of specialist**
- Een `Rol`-member in `agent/llm_stap.py` en secties in `agentrollen.json`.
- Een entry in `SPECIALISTS` met `doel`.
- Routeringsrijen in `eval/golden_routering.jsonl` en een meting (ADR-010).

**Agent of taak**
- De module in `agent/agents/` met `DOEL`, `Taak`, `MODEL_TAKEN`, `Invoer` en `voer_uit`.
- `ACTIE_TAAK` en de routeringsrijen.
- De api-aanroepen in `TOEGESTAAN`.

**Workflow**
- Een vaste functie of node, met haar stappen als constante in de module zelf (`FASEN`, `METHODEN`,
  `KAARTSTAPPEN`) en een regel in `agent/catalogus.uit_workflows` (laag, doel). Meldt de keten haar fasen, dan
  toetst `test_catalogus.py` dat elke gemelde fase in de constante staat.
- Een rij in de routeringstabel.
- Testrijen.

**Route** (een vaste weg zonder model, vóór of na de supervisor)
- Een herkenner, een tak in `nodes/supervisie._kies` en een rij in `agent/routes.py` (`ROUTES`: herkenner, doel, moment).
  `test_catalogus.py` houdt tabel en code gelijk en eist dat de route precies één workflow of agent kiest.
- De rijen in `eval/golden_routering.jsonl` en de negatieven in `eval/golden_gesprek.jsonl` (ADR-005, ADR-010).

**Tool** (een graaftool, leestool of connectortool)
- De declaratie in `agent/tools/` met een beschrijving die zegt wat er terugkomt, het resultaatcontract
  (`tests/test_resultaatcontract.py`) en een plek in een specialist (`tests/test_toolverdeling.py`). De catalogus leest
  `_BY_NAME`; geen eigen lijst.

**Controle** (een hook: deterministisch, op een vast moment)
- Een `CONTROLE`-beschrijving naast de code (naam, label, doel, moment, tests) en de module in
  `agent/catalogus._controlemodules`. Een controle gebruikt hoogstens een skill.

**Connector**
- Zie ADR-013: de beschrijving, de tools en de straatvlag. De catalogus leest de beschrijving.

**Sjabloon**
- Zie ADR-008: de module, de registerregel en `Specialist.sjablonen`. Een nieuw blok krijgt ook een Literal en een component.

**Regelset uit een skill** (S6, achter de proefvlag `SKILL_REGELS`)
- `regels/jas/<familie>.yaml` of `regels/begrippen/<familie>.yaml` in de skillmap. Elke regel heeft het voorvoegsel
  `jas.<skill>.` of `begrip.<skill>.`, de vier testsoorten en een bewijscode die al in de verklaringen staat. De generator
  bundelt ze in het pakket. De ketens nemen ze alleen mee met de vlag aan, alleen op acceptatie. Zie
  `agent/skill_regels.py` en `tests/test_skill_zonder_code.py`.

**Regelset** (een detector-, begrippen- of zoekregel)
- Een YAML-item met `bron`, `versie` en `tests` (positief, negatief, rand, overlap). Het bestand begint met een
  commentaaralinea: dat is het doel in de catalogus. Een nieuw bestand komt vanzelf mee; een nieuwe map hoort in
  `REGELMAPPEN` (`agent/catalogus.py`).
- De code van het item in `verklaringen.yaml`.
- Bij een detectorregel ook `candidate_rules` in het profiel van zijn klasse.

## Afspraken met de andere sporen

- **Slash-commando's.** Een commando verwijst naar een `Onderdeel.id` of naar een `ingang` daarvan, en houdt geen eigen
  lijst van wat Lex kan bij.
- **Contextbeheer.** De catalogus geeft per rol de sectie-sha's. Daarmee kan het stabiele deel van de prompt (de cache-prefix)
  worden bepaald zonder een tweede telling.

## Stand

| Fase | Wat | PR |
|---|---|---|
| C0 | ADR-014 en dit document | #1275 |
| C1 | `Onderdeel` + adapters voor connector, sjabloon, specialist en methode/rol + drift-test | #1279 |
| C2 | agents en taken, regie, regelsets, workflows met stappen | #1281 |
| C5 | `GET /v1/catalogus` + BFF | #1285 |
| C6 | de werkplek: *Werkwijze van Lex* | #1286 |
| S1 | ADR-014 §7 *Samenwerking* | #1290 |
| S2 | concepten, de soorten `tool` en `controle`, aanroepregels als test | #1291 |
| S3 | de routeringstabel (ADR-010) | #1292 |
| S4 | context per agent (`test_context_per_agent`) | #1294 |
| S5 | meerdere skills, binding per rol, nep-skill | #1296 |
| S6 | regelsets uit een skill, achter de proefvlag `SKILL_REGELS` | #1301 (bundel 61) |
| S7 | werkplek per concept | #1299 |
| S8 | commando's wijzen naar één onderdeel | #1298 |
| C7 | een wijziging voorstellen → concept-PR (acceptatie, `CATALOGUS_VOORSTELLEN` + `WA_GITHUB_PR_TOKEN`) | #1310 |
| v3 | de skill wetsanalyse 3.0 volgens de eisen voor Claude-skills, methodetekst byte-gelijk | #1307 |
| C8 | de skill `wetsuitvoering` (JRM 2), eerst zonder rolkoppeling | #1309 |
| C9 | regels voorstellen, met hun eigen tests als poort | – |
