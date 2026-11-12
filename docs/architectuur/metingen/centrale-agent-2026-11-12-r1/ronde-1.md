# De centrale agent, ronde 1: T1 en A1 zijn bitgelijk – 12 november 2026

- **Soort:** *meting* (ADR-016 §A6, de ronde voor T1 en A1).
- **Code:** master `bb544957` (bundel 79: T1, de validatoren in `bronmodel`, en A1, het profielregister), tegen
  `808c908e` (bundel 78), de versie van de nulmeting.
- **Straat:** acceptatie. **Model:** `claude-sonnet-4-6`.
- **Drempel:** bitgelijk – de kwaliteitsset en de routeringsset laten geen verschil zien tegen de versie van vóór A1.
- **Gegevens:** [`ronde-1-runs.jsonl`](ronde-1-runs.jsonl), één regel per opdracht.

**Uitkomst: geen verschil gevonden.** Wat Lex naar het model stuurt, is op beide versies hetzelfde, in de repo en op
de straat. De ronde is goed; A2 kan beginnen.

## Hoe er gemeten is

Een antwoord van een model is nooit bitgelijk: dezelfde vraag gaf in de nulmeting drie verschillende teksten en tot
vijf keer zoveel tokens. Bitgelijk is daarom gemeten op wat Lex zelf bepaalt: het verzoek aan het model, de route en de
tekst van de routes zonder model. In twee stappen, afgestemd met de hoofdsessie.

### Stap 1 – de repo, zonder tokens

- **De opnames van de modelverzoeken** (`tests/data/modelverzoeken/`, twaalf bestanden; `test_modelverzoeken.py` legt
  elk verzoek byte voor byte vast) zijn tussen `808c908e` en `bb544957` ongewijzigd. Hetzelfde geldt voor de
  routeringsset (`eval/golden_routering.jsonl`, `tests/test_routering.py`), de kwaliteitsset (`eval/golden.jsonl`),
  `agent/prompts.py` en `agent/methodepakket.py`.
- **De poort van bundel 79** (#1346) was groen: `poort` en beide shards van graph-qa. Daarin draaien de routeringsset,
  de modelverzoeken en de hashtest van A1 (`tests/test_profielregister.py`): per specialist de instructie, de tools, de
  sjablonen en de methoderol tegen de hashes van vóór het register.
- **Die hashes zijn onafhankelijk nagerekend.** De code van `808c908e` en van `bb544957` is elk apart geladen, en per
  specialist zijn de instructie, de gesorteerde tools met hun aantal, de sjablonen, de methoderol en de volledige
  systeemtekst (methodetekst plus instructie) gehasht. De uitvoer van beide versies is byte-gelijk, voor alle zes de
  specialisten, en gelijk aan de waarden in de test.

### Stap 2 – de straat, 664.182 tokens

De tien enkelvoudige opdrachten van de agentset, één keer op `bb544957`, met hetzelfde script en dezelfde bronstand als
de nulmeting. Per modelaanroep is de **handtekening** vergeleken met de drie runs van de nulmeting op `808c908e`: de
rol, het model, `tools_hash`, `system_hash`, het aantal tools en de omvang van het vaste systeemdeel en van de tools
(uit `aanroepen` op het `meting`-event).

| Opdracht | Route | Modelrondes (nulmeting → nu) | Tokens (nulmeting → nu) | Handtekeningen | Niet in de nulmeting | Tekst |
|---|---|---|---|---|---|---|
| E01 | algemeen | 1 / 1 / 1 → 1 | 934 / 935 / 916 → 939 | 1 | 0 | wettekst gelijk |
| E02 | overzicht | 0 / 0 / 0 → 0 | 0 → 0 | 0 | 0 | gelijk |
| E03 | duiding | 8 / 6 / 9 → 10 | 148k / 115k / 195k → 230k | 2 | 0 | verschilt |
| E04 | algemeen | 0 / 0 / 0 → 0 | 0 → 0 | 0 | 0 | gelijk |
| E05 | duiding | 3 / 2 / 2 → 2 | 78k / 49k / 49k → 49k | 1 | 0 | verschilt |
| E06 | afgewezen | 1 / 1 / 1 → 1 | 2k / 2k / 2k → 2k | 1 | 0 | gelijk |
| E07 | definitie | 5 / 4 / 5 → 4 | 46k / 34k / 46k → 34k | 2 | 0 | verschilt |
| E08 | duiding | 12 / 9 / 14 → 7 | 312k / 193k / 380k → 136k | 2 | 0 | verschilt |
| E09 | duiding | 8 / 6 / 10 → 9 | 124k / 93k / 186k → 181k | 2 | 0 | verschilt |
| E10 | annotaties_lezen | 3 / 4 / 3 → 3 | 32k / 43k / 32k → 32k | 1 | 0 | verschilt |

- **Handtekeningen:** 37 modelaanroepen, zes verschillende handtekeningen. Elk komt voor in de nulmeting, en geen
  handtekening van de nulmeting ontbreekt bij dezelfde opdracht.
- **Model:** in elke aanroep `claude-sonnet-4-6`, zoals in de nulmeting.
- **Route en specialist:** per opdracht gelijk aan alle drie de runs van de nulmeting.
- **Routes zonder model:** E02, E04 en E06 geven letterlijk dezelfde tekst. Bij E01 is het blok met de wettekst gelijk;
  de toelichting schrijft het model.
- **Rondes en tokens:** binnen wat de nulmeting liet zien, op twee na. E03 kostte 10 rondes en 230k (nulmeting hoogstens
  9 en 195k), E08 7 rondes en 136k (nulmeting minstens 9 en 193k). Met gelijke handtekeningen is dat spreiding van het
  model; één run tegen drie zegt over rondes en tokens niets meer dan dat.
- **Controle:** geen run *ongegrond*; E04 en E10 *onbepaald*, zoals in de nulmeting.

## Wat niet vergeleken kon worden

- **De antwoorden zelf.** Ze verschillen per run, ook binnen één versie. De inhoud is in deze ronde niet opnieuw
  beoordeeld.
- **De kwaliteitsset op de straat.** Er is geen run van die set op `808c908e`, dus een run op `bb544957` heeft niets om
  tegen te vergelijken. De set is alleen in de repo vergeleken (ongewijzigd) en loopt mee in de poort. Afgesproken: hij
  draait op de straat alleen als stap 2 een verschil toont. Dat was niet zo.
- **Het variabele deel van het verzoek.** De handtekening dekt de tools en de systeemtekst. De berichten (de vraag, de
  context van de beurt, de toolresultaten) hebben geen hash op het `meting`-event; die zijn alleen in stap 1 gedekt,
  door de opnames.
- **De hashes zijn afgekapt** (twaalf tekens). Een botsing is onwaarschijnlijk; de omvang in tekens is daarom
  meevergeleken.
- **Niet elke specialist kwam op de straat aan bod.** De tien opdrachten raken de supervisor, de toelichting van de
  bepalingsroute en de specialisten `duiding`, `definitie` en `annotaties_lezen`. `algemeen` in de antwoordlus,
  `begrippen_lezen` en `retrieval` zijn alleen in stap 1 vergeleken.
- **T1** (de validatoren) raakt de draaiende keten niet: het bewijs is dat het methodepakket byte-gelijk bleef (stap 1).

## Verbruik

664.182 tokens uit de `meting`-events, gelijk aan het verschil in de accountstand (3.196.601 → 3.860.783). Daarvan
E03 230k, E09 181k en E08 136k.
