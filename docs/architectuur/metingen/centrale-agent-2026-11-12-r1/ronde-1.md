# De centrale agent, ronde 1: T1 en A1 zijn bitgelijk – 12 november 2026

- **Soort:** *meting* (ADR-016 §A6, de ronde voor T1 en A1).
- **Code:** master `bb544957` (bundel 79: T1, de validatoren in `bronmodel`, en A1, het profielregister), tegen
  `808c908e` (bundel 78), de versie van de nulmeting.
- **Straat:** acceptatie. **Model:** `claude-sonnet-4-6`.
- **Drempel:** bitgelijk – de kwaliteitsset en de routeringsset laten geen verschil zien tegen de versie van vóór A1.
- **Gegevens:** [`ronde-1-runs.jsonl`](ronde-1-runs.jsonl), één regel per opdracht, en
  [`ronde-1-prijsgewogen.jsonl`](ronde-1-prijsgewogen.jsonl), de tokens per soort voor deze ronde en de nulmeting.

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

## Naar prijs gewogen: de vergelijkingsbasis voor A2

Besluit van de gebruiker (12 nov 2026): de drempel *niet duurder* geldt op naar prijs gewogen tokens; de ruwe tokens
staan ernaast. Hieronder beide maten voor de tien enkelvoudige opdrachten, voor de nulmeting op `808c908e` (drie runs)
en voor deze ronde op `bb544957` (één run). De cijfers per opdracht en run, met de vijf soorten tokens apart, staan in
[`ronde-1-prijsgewogen.jsonl`](ronde-1-prijsgewogen.jsonl).

**De weging**, in invoertokens, naar de prijsverhouding van het model: invoer × 1, uitvoer × 5, cache lezen × 0,1, cache
schrijven met een TTL van vijf minuten × 1,25 en van een uur × 2. De factoren komen in ADR-016 §A6 te staan; wijken ze
daar af, dan zijn de gewogen cijfers opnieuw te rekenen uit het bestand, de ruwe niet.

| Opdracht | Ruw, nulmeting r1 / r2 / r3 | Gewogen, nulmeting r1 / r2 / r3 | Mediaan gewogen | Ruw, nu | Gewogen, nu |
|---|---|---|---|---|---|
| E01 | 934 / 935 / 916 | 1,6k / 1,6k / 1,5k | 1,6k | 939 | 1,6k |
| E02 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| E03 | 148,0k / 114,8k / 195,3k | 44,7k / 52,2k / 72,4k | 52,2k | 229,6k | 93,1k |
| E04 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| E05 | 77,8k / 48,7k / 49,0k | 26,5k / 17,0k / 18,5k | 18,5k | 48,7k | 51,1k* |
| E06 | 2,3k / 2,3k / 2,3k | 545 / 515 / 520 | 520 | 2,3k | 545 |
| E07 | 45,6k / 34,1k / 45,5k | 9,7k / 7,6k / 9,6k | 9,6k | 34,1k | 25,3k* |
| E08 | 312,0k / 192,8k / 380,0k | 111,5k / 75,6k / 113,5k | 111,5k | 136,3k | 45,7k |
| E09 | 124,0k / 92,6k / 185,9k | 32,3k / 27,9k / 57,2k | 32,3k | 180,7k | 57,8k |
| E10 | 31,6k / 43,2k / 31,6k | 24,1k* / 9,7k / 7,1k | 9,7k | 31,6k | 24,0k* |
| **som** | 742,1k / 529,4k / 890,6k | 250,7k / 192,0k / 280,3k | | 664,2k | 299,3k |
| **mediaan** | 38,6k / 38,6k / 38,5k | 16,9k / 8,7k / 8,3k | | 32,9k | 24,7k |

Een \* betekent: in die beurt is het voorvoegsel van een uur geschreven (de cache was koud).

- **De basis voor A2:** over de 30 opdracht-runs van de nulmeting is de mediaan **38,6k ruw** en **9,6k gewogen**.
  Per run is de som 250,7k / 192,0k / 280,3k gewogen tegen 742,1k / 529,4k / 890,6k ruw.
- **Gewogen is ongeveer een derde van ruw.** Ruw is grotendeels cache lezen, en dat telt voor een tiende. Wat gewogen zwaar
  telt, is de uitvoer en het schrijven van de cache.
- **Een koude cache bepaalt de gewogen kosten van een korte beurt.** E05, E07 (nu) en E10 (nulmeting r1, en nu) schreven
  het voorvoegsel van een uur: 8,8k tot 17,9k tokens tegen factor 2. E07 kost ruw evenveel als in de nulmeting (34k) en
  gewogen 25k tegen 8k–10k. Welke beurt het voorvoegsel schrijft, hangt af van wat er het uur ervoor op de straat
  liep, niet van de versie.
- **Voor A2 volgt daaruit:** vergelijk gewogen kosten over drie runs en met het schrijven van het uurvoorvoegsel apart
  vermeld (`cache_schrijf_1u`). De centrale agent krijgt een eigen voorvoegsel, dus in zijn eerste beurt is de cache
  altijd koud; een vergelijking van één run tegen de nulmeting meet dan vooral dat.
- **Deze ronde tegen de nulmeting:** gewogen 299,3k tegen 250,7k / 192,0k / 280,3k. Het verschil zit in E03
  (meer rondes) en in de drie beurten met een koude cache; de handtekeningen zijn gelijk.

## Verbruik

664.182 tokens uit de `meting`-events, gelijk aan het verschil in de accountstand (3.196.601 → 3.860.783). Daarvan
E03 230k, E09 181k en E08 136k.
