# De skill in het platform (voor wie hem wijzigt)

Deze skill is ook een **build-input** van Lex, de agent in `tools/graph-qa/`. Lees dit voordat je iets aan de skill
verandert: een paar onderdelen gaan letterlijk als prompt of als data naar de draaiende dienst.

## Inhoud

- Wat het platform uit de skill haalt
- Een wijziging doorvoeren
- Wat je niet zomaar verandert
- Een tweede methode-skill
- Kwaliteit meten

## Wat het platform uit de skill haalt

| Onderdeel | Gebruikt als | Generator en bewaking |
|---|---|---|
| Frontmatter `metadata` (`methode_versie`, `lex_*`) en `description` | De beschrijving van de methode in de catalogus (ADR-014) | `scripts/genereer_methodepakket.py` |
| Secties tussen `<!-- methode:<id>:begin -->` en `…:end -->` | Methodetekst in de systeemprompt, per rol uit `agentrollen.json` | idem → `agent/methodepakket.py`; `test_methodepakket`, `test_methoderollen`, `test_context_per_agent` |
| `references/jas-klassen-referentie.md` | Het blok JAS_KLASSEN voor classifier en reviewer | `scripts/genereer_jas_klassen.py` → `agent/jas_klassen.py`; `test_methode_drift` |
| De tabel met de dertien klassen in `SKILL.md` | Een derde drager van dezelfde namen | `test_methode_drift` eist elke klasse vet in die tabel |
| `relaties.json` | De relatiecatalogus voor api, graph-qa en werkplek | `scripts/genereer_jas_relaties.py`; `tests/poort/test_relatiecatalogus.py` |
| `references/bronnen.md` | Het register van broncodes (M/P) | De generator weigert een sectie met een onbekende code |
| `regels/` (alleen in een andere methode-skill) | Detector- en begrippenregels, achter de proefvlag `SKILL_REGELS` | `agent/skill_regels.py`; `test_skill_zonder_code` |

De rest van de skill (de werkstromen, de protocollen, de voorbeelden) is voor wie de skill in Claude gebruikt. Het
platform laadt die tekst niet.

## Een wijziging doorvoeren

```bash
cd tools/graph-qa && uv run python scripts/genereer_jas_klassen.py
```

Dat draait ook de methodepakket- en relatiegenerator. CI draait hetzelfde met `--check`. Draai daarna minstens:

```bash
uv run --extra dev pytest -q tests/test_methodepakket.py tests/test_methode_drift.py tests/test_methoderollen.py tests/test_context_per_agent.py tests/test_catalogus.py
```

## Wat je niet zomaar verandert

- **De tekst van een methodesectie.** Die gaat letterlijk naar het model. Een wijziging verandert het gedrag van Lex
  en de vingerafdruk van de rol (`methode.vingerafdruk`). Doe het als bewuste stap, met een meting (ADR-010: drie
  runs, kwaliteitsset en meting per beurt) en een P-regel in het [beslisregister](bronnen.md).
- **`methode_versie`.** Die staat in de kop van elke systeemprompt ("WETSANALYSE 2.1 — rol …"). Verhoog hem alleen
  bij een betekeniswijziging van de methode, niet bij een herschikking van de skill (`skill_versie` is daarvoor).
- **De koppen en velden van de klassenreferentie.** De generator leest ze; een andere vorm laat hem luid falen.
- **Bestandsnamen.** Code, tests en documentatie verwijzen naar `agentrollen.md`, `bronnen.md`,
  `deelvragen-en-bronnen.md`, `jas-klassen-referentie.md`, `zoekvragen-bronselectie.md`, `verwijzingen-volgen.md`,
  `begrippen.md`, `nl-sbb-en-b1.md` en `relaties.md`.
- **Materiaal van derden.** De repo is publiek. Het boek (Boom) en de BRM-readers alleen in eigen woorden;
  W3C-materiaal van BZK mag letterlijk, met de notice (zie `docs/wetsanalyse/wetsanalyse-rijk/BRON.md`).

## Een tweede methode-skill

Een andere methode (zoals wetsuitvoering, JRM) is een eigen map onder `.claude/skills/` met `lex_soort: "methode"`.
Zo'n skill vult **bestaande** rollen aan met eigen secties en een eigen bronregister, en kan regelsets meebrengen
achter de proefvlag. Er is geen code nodig; zie ADR-014 §7 en `docs/architectuur/catalogus.md`.

## Kwaliteit meten

- **Inhoudelijke acceptatie** volgt de [kwaliteitsrubriek](kwaliteit.md).
- **Metingen van het platform** staan in `docs/architectuur/metingen/` en worden nooit achteraf gewijzigd.
- **De testgevallen van deze skill** staan in `evals/`, in de vorm die `claude plugin eval` leest.
