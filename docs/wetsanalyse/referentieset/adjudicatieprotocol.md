# Adjudicatieprotocol v1

Hoe een casus van de referentieset van `provisional` naar `adjudicated` gaat. Het ontwerp en de
motivering staan in [onderzoek-empirische-validatie §10–§11](../../architectuur/onderzoek-empirische-validatie.md);
dit document is de werkinstructie. De protocolversie (`1`) staat in elk annotatorbestand en in het
adjudicatierecord. Een wijziging aan deze stappen is een nieuwe protocolversie.

## Rollen

- **Annotator A en annotator B:** juristen die de JAS-methode kennen. Ze werken onafhankelijk.
- **Adjudicator C:** een derde jurist. A en B mogen samen adjudiceren, maar dan met een schriftelijk
  besluit en `"gezamenlijk": true` in het besluitenbestand.
- **Namen zijn codes.** Deze repo is publiek, en het adjudicatierecord komt in `cases.json` te
  staan. Gebruik daarom een vaste code per persoon (bijvoorbeeld `jur-01`) als annotator- en
  adjudicatornaam. Wie achter een code zit, wordt buiten de repo bijgehouden.
- **Het systeem is nooit annotator.** Geen systeemoutput, geen conceptmarkeringen uit `cases.json` en
  geen eerdere annotatie van dezelfde bepaling in de werkplek. Systeemoutput mag een vraag oproepen,
  maar nooit een antwoord leveren.

## Stappen per casus

### 1. Bron controleren

Vergelijk de tekst en de SHA-256 in het formulier met de officiële bron (Staatsblad, of de
versiegebonden weergave uit het [bronnenmanifest](../bronnen/manifest.json)). Kies daarna één
status:

- `valid`: de tekst klopt en is geschikt om te annoteren;
- `ambiguous`: de tekst klopt, maar het is twijfelachtig of hij als normtekst geannoteerd hoort te
  worden. Denk aan een beleidsregel met rekenvoorbeelden;
- `unusable`: de tekst wijkt af of is ongeschikt. **Hier stopt de casus.**

### 2. Blind annoteren

Maak het formulier aan (één HTML-bestand, dat offline werkt):

```bash
cd tools/graph-qa
uv run python scripts/blind_formulier.py --uit blind-formulier-v1.html   # optioneel: --casus IW01 AWB04
```

Het formulier toont per casus alleen de vindplaats, de versie, de brontekst en de hash, plus de
dertien klassen met hun herkenningsvragen. Een test bewaakt dat er geen conceptmarkering,
dossiertoelichting of systeemoutput in het bestand terechtkomt.

Vul per element het volgende in:

- de **exacte span**: selecteer het fragment met de muis. Witruimte aan de rand valt weg, en een
  selectie midden in een woord wordt geweigerd;
- de **klasse**, en het **subtype** waar de klasse dat kent;
- de **herkenningsvraag** die het element beantwoordt, letterlijk uit JAS;
- een **H2-verwijzing** (`H2:NN`);
- een **motivatie**, en eventueel de context die voor de klasse nodig was.

Twee spelregels:

- **Meerdere functies op dezelfde span** zijn meerdere elementen.
- Een **negatief element** leg je alleen vast bij een bewuste keuze, met de reden erbij. Bijvoorbeeld:
  "invorderbaar" is het naamwoordelijk deel van het gezegde en geen object.

Het formulier bewaart je werk tussentijds in de browser. **Opslaan als JSON** levert
`<casus>-<annotator>.json` op, en dat bestand lever je in bij de adjudicator. Met **JSON laden** ga
je later verder waar je gebleven was.

### 3. Vergelijken

```bash
uv run python -m eval.adjudicatie vergelijk IW01-a.json IW01-b.json --md IW01-verschillen.md --json IW01-verschillen.json
```

De vergelijking gaat op positie en in drie rondes, van streng naar los:

| soort | betekenis |
|---|---|
| `gelijk` | zelfde span, zelfde klasse |
| `klasse` | zelfde span, andere klasse |
| `span` | overlappende span, zelfde klasse |
| `alleen_a` / `alleen_b` | alleen door één annotator gemarkeerd |

Twee elementen die zowel in span als in klasse verschillen, worden niet aan elkaar gekoppeld. Het
zijn twee lezingen, die elk een eigen besluit krijgen. Het JSON-bestand bevat onder `besluiten` het
sjabloon dat de adjudicator invult.

### 4. Adjudiceren

Per verschil (behalve `gelijk`) kiest de adjudicator één besluit:

| besluit | gevolg voor gold |
|---|---|
| `kies_a` / `kies_b` | het element van A of van B |
| `beide` | allebei, want het zijn verschillende functies |
| `geen` | geen element. Neem het zo nodig op als negatief element |
| `debatable` | allebei, met `annotation_status: debatable` |

Kies `debatable` alleen als beide lezingen methodisch verdedigbaar zijn, en zet de reden in de
motivatie. Verschillen A en B in hun bronstatus, dan beslist de adjudicator ook die
(`"source_status"` in het besluitenbestand).

```bash
uv run python -m eval.adjudicatie besluit IW01-a.json IW01-b.json IW01-besluiten.json \
  --adjudicator jur-03 --datum 2026-10-15 > IW01-gold.json
```

De uitkomst bevat `gold`, `negatief`, `source_status` en het casusbrede `adjudicatie`-record.
Neem die velden over in de casus van de nieuwe versie (`v<N+1>/cases.json`; maak die aan met
`uv run python -m eval.referentieset --versie v1 --nieuw v2`). Vul de `constructies`
in volgens de dekkingsmatrix (§10.3) en zet de casus op **`review_pending`**. Een ontbrekend besluit
is een fout: het script neemt nooit stilzwijgend "gelijk" aan.

### 5. Overeenstemming vastleggen

`vergelijk` rapporteert twee maten, beide vóór adjudicatie:

- **Gelijk op positie:** gekoppelde paren met dezelfde span, gedeeld door alle rijen.
- **Cohen's κ op de klasse**, alleen over paren met dezelfde span. Onder twee paren is κ niet
  gedefinieerd.

Neem beide maten op in het rapport van de versie. Lage overeenstemming is informatie over de
methode, geen reden om een casus te schrappen.

### 6. Bevriezen

```bash
uv run python -m eval.referentieset --versie v2 --dekking                     # wat ontbreekt nog (§10.3)
uv run python -m eval.referentieset --versie v2 --bevries 2026-10-20 --protocol 1
```

`--bevries` zet elke `review_pending`-casus op `adjudicated` en berekent de hash. Het valideert het
volledige record voordat er iets wordt geschreven. Vanaf dat moment is de versie onveranderlijk.

## Onveranderlijkheid

- Wijzigen gaat alleen via een nieuwe versie, met `voorganger` en een changelog per gid in het
  manifest (casus, gid, reden, oud, nieuw, datum, adjudicator).
- `provisional` is niet hetzelfde als `adjudicated`. En `adjudicated` betekent niet dat er nooit meer
  iets verandert: een fout in gold wordt een nieuwe versie, nooit een stille correctie. De test op
  manifest-drift maakt een stille correctie zichtbaar.
- **Verboden:** een gold-element wijzigen naar aanleiding van systeemoutput, zonder dat A, B en C het
  opnieuw volgens stap 2–4 beoordelen.
