# ADR-016: hermeting na de reparatie van C (#1611, 16 nov 2026)

Soort: *meting*, licht regime: één run, alleen de opdrachten van de geraakte vorm, plafond 1,2M. De gebruiker gaf akkoord
met "Ja, 1,2M". De meting volgt op [de meting na het plan](../centrale-agent-2026-11-16-na-plan/na-plan.md) (#1610).

## Opzet

- **Code:** graph-qa op `7859d2eb` (#1611, de vraag uit code als kaart onder het antwoord). Het model is
  `claude-sonnet-4-6`.
- **Werkgebied:** het meetwerkgebied van de vorige meting.
- **Volgorde:** S01 en P01 (de opdrachten waarop PR A, de kern per stuk, te meten is), daarna F02 als dat nog past.
  Een wachter stond op 1,15M.
- **Gedraaid:**
  - S01;
  - P01, gestart en na ongeveer 262k afgebroken (zie hieronder);
  - twee korte diagnosebeurten met Rechtspraak aan, in een eigen gesprek.
- **Niet gedraaid:** F02.
- **Totaal:** 567k tokens (verschil in het verbruik van het account).

## Uitkomst

| Beurt | Route | Uitkomst | Account |
|---|---|---|---|
| S01 | `subagent_route` → `centraal` | kind `rechtspraak_lezen` `klaar` (8 rondes, 264k). Daarna faalt de eerste modelaanroep van de centrale agent: `BadRequestError`, 0 tokens | 264k |
| P01 | `subagent_plan` → bevestigd | afgebroken na het starten van de twee kinderen: de bundel zou op dezelfde fout uitkomen | ~262k |
| Diagnose 1: "Wat zegt ECLI:NL:HR:2023:1371 over het doel van de meldingsplicht …?" | genoemd stuk → profiel `duiding` | **goed**: `antwoord_extern` met een kern per stuk, het citaat r.o. 3.3, *gegrond* | ~40k |
| Diagnose 2: "Waarom is rechtspraak belangrijk bij de uitleg van artikel 36, vierde lid …? Twee zinnen, zonder uitspraken op te zoeken." | `centraal` | **fout:** de eerste modelaanroep faalt, `BadRequestError`, 0 tokens | ~0 |

## Wat dit zegt

- **De reparatie van C werkt:**
  - Het kind van S01 meldde `klaar` en kreeg geen aanbod en geen vraag. De beurt ging door naar de centrale agent.
  - De afgelopen meting eindigde hier met "Zal ik verder lezen?".
- **De centrale agent met een connector aan faalt op zijn eerste modelaanroep, ook zonder subagent** (diagnose 2).
  - Het gaat dus niet om het hervatten en niet om de bundel.
  - Elke vraag die bij `centraal` uitkomt terwijl een connector meedoet, faalt op acceptatie.
  - De melding is "Deze beurt paste niet binnen de grenzen van het model". Die geeft `agent._provider_fout` bij elke 400
    waarvan de melding "too long", "too large" of "exceed" noemt.
- **De meting na het plan (#1610) zag hetzelfde.** De twee fouten na het hervatten waren deze fout. De centrale agent
  deed in die hele meting maar één modelaanroep, bij S04 zonder connector.
- **In de slotmeting van A6 (`81bee0d1`) werkte `centraal` met een connector nog.** Daarna zijn gemerged: de
  agentprofielen (#1565), A7, B-3, het denkproces, en PR A (het veld `kern` in `antwoord_extern`) tot en met C.
- **Hoofdverdachte: het strict schema van `centraal` met een connector (PR A).**
  - `duiding` heeft hetzelfde `antwoord_extern` met `kern`, maar 3 strict tools, en werkt.
  - `centraal` heeft er 12. Met alleen Rechtspraak aan groeide het van 8.692 naar 8.873 tekens.
  - De grens van de API is een grens op de complexiteit van de grammatica, niet op tekens. `tests/test_strict_grenzen.py`
    benadert haar met tekens, en die toets is groen.
  - Bewezen is dit niet. De melding van de provider staat sinds #1611 in de logregel `model_aanroep_fout`, maar die kon
    ik niet lezen: de Grafana-toegang ontbreekt in deze sessie.

**Run-id's** om `model_aanroep_fout` te lezen:
- diagnose 2: `efc55543ccc54601a4c417af09ca5e05`;
- S01, ouder: `f6cbb69e9654473ebd4f3ecff836f108`.

## Drempels

| Drempel | Uitkomst |
|---|---|
| **PR C**: een vraag uit code houdt geen eindantwoord tegen; `klaar` krijgt niets | **gehaald** bij S01: geen vraag, de beurt ging door naar het antwoord |
| **PR A**: per stuk een kern, en minstens de helft van de citaten draagt de kern | **gehaald in de route `duiding`** (diagnose 1: kern aanwezig, het citaat r.o. 3.3 draagt haar). **Niet te meten in `centraal`**: die faalt |
| **S01 en P01**: een eindantwoord over de uitspraken | **niet gehaald**: de centrale agent faalt (S01), P01 afgebroken |
| **Brongetrouw** | **gehaald voor wat er staat**: diagnose 1 *gegrond* |
| **Verbruik** binnen het plafond | **gehaald**: 567k van 1,2M |

## Vervolg

- **De 400 van `centraal` met een connector** wordt opgelost in de hoofdsessie, met PR #1614. Die PR maakt zes
  overdrachten niet-strict:
  - `wijs_af`;
  - `meer_tools`;
  - `toon_overzicht`;
  - `lees_annotaties`;
  - `lees_begrippen`;
  - `toon_stukken`.
- Daarmee gaat het strict schema van `centraal` met een connector van 12 tools en 9.473 tekens naar 6 tools en 8.091
  tekens.
- Dit past bij de hoofdverdachte hierboven, de grens van de grammatica.
- De meting is in deze ronde afgebroken. Een nieuwe meting van S01, P01 en F02 vraagt opnieuw akkoord van de gebruiker.
  Punt 1 en 2 van het voorstel hieronder zijn daarmee ingehaald.

## Voorstel (geen nieuwe ronde)

1. **Eerst de oorzaak vaststellen.** Lees `model_aanroep_fout` van de twee run-id's hierboven, in App Insights of
   Grafana. De regel geeft de opbouw in tekens per deel, de status en het begin van de melding van de provider.
2. **Is het het strict schema** ("too complex", "too large" bij de grammatica):
   - Een snelle generieke fix: `antwoord_extern` in het profiel `centraal` niet-strict, of `kern` daar weglaten, tot er
     een grens per grammatica is.
   - Daarnaast: `tests/test_strict_grenzen.py` terug naar de laatst bewezen omvang van `centraal` met een connector
     (8.692 tekens met alleen Rechtspraak), in plaats van 9.500 over alle connectors.
3. **Is het de lengte van de vraag:** de opbouw in de logregel zegt welk deel te groot is. Dan geldt een grens op dat
   deel.
4. Daarna opnieuw licht meten: S01, P01 en F02, met akkoord.

## Bestanden

- `runs.jsonl`: S01 (`centrale_agent_vat.py`), zonder tekst. `tokens` is 0 omdat de beurt faalde; `delta_account` is
  het verbruik.
- `kinderen.jsonl`: het kind van S01, zonder tekst.

De ruwe runs staan niet in de repo. P01 en de diagnosebeurten staan er niet in: P01 is afgebroken, en de diagnoses
stonden buiten het meetscript (de run-id's hierboven).
