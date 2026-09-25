# Referentieset JAS — ter gezamenlijke beoordeling

De set bevat **24 conceptgevallen uit zes wetsfamilies**. Zij is bewust nog geen gold:
markeringen zijn concepten, sommige onderdelen zijn nog onvolledig en juridische
contextvragen staan expliciet open. Dit is het startmateriaal voor gezamenlijke
beoordeling, geen bewijs van 10/10-prestaties.

| Gebruik | Wetsfamilie | Conceptdossiers |
|---|---|---|
| Ontwikkeling | Invorderingswet | [IW01–04](iw.md) |
| Ontwikkeling | Algemene wet bestuursrecht | [AWB01–04](awb.md) |
| Ontwikkeling | Wet op de zorgtoeslag | [WZT01–04](wzt.md) |
| Ontwikkeling | Verkeersrecht | [RVV01–04](rvv.md) |
| Afzonderlijke toetsing | Burgerlijk Wetboek 6 | [BW01–04](bw6.md) |
| Afzonderlijke toetsing | Omgevingswet | [OW01–04](omgevingswet.md) |

De laatste twee families mogen niet in prompts of few-shotvoorbeelden worden geladen.
De familie-split beperkt voorbeeldlekkage; hij maakt een generiek, mogelijk al voorgetraind
model niet blind voor de wetgeving. Vier ontwikkelgevallen zijn gebruikt voor een beperkte directe promptvergelijking;
zie het evaluatierapport. Een volledige juridische kwaliteitsmeting ontbreekt nog.

Een uitgebreider voorbeeld in dossieropmaak staat in
[het dossier over rood voetgangerslicht](voorbeeld-dossier-rvv74.md).

## Bronpakketten en actualiteit

De set is **geversioneerd**: één map per versie, nu [`v1/`](v1/). Daarin bewaart
[`cases.json`](v1/cases.json) de exacte analysetekst met SHA-256, vindplaats, bron-ID,
conceptmarkeringen (`gold`) en offsets; [`manifest.json`](v1/manifest.json) draagt de hash over
alle casussen, de status per casus en de changelog. De offsets tellen Python-Unicode-codepunten
binnen deze analysetekst; ze zijn geen vervanging van de platformankers.

Het schema staat in [onderzoek-empirische-validatie §10.4](../../architectuur/onderzoek-empirische-validatie.md)
en wordt bewaakt door `tools/graph-qa/eval/referentieset.py`:

```bash
cd tools/graph-qa
uv run python -m eval.referentieset --check       # schema + manifest
uv run python -m eval.referentieset --bijwerken   # hash herberekenen na een bewuste wijziging
uv run python -m eval.referentieset --dekking     # welke klassen/constructies ontbreken nog (§10.3)
```

Drie regels:

- **`adjudicated`/`gold` vraagt een volledig record.** Per casus twee annotatoren, een
  adjudicator, datum, protocolversie en een gecontroleerde `source_status`; per element een
  `annotation_status`, de herkenningsvraag (letterlijk uit JAS), een `H2:NN`-verwijzing en het
  adjudicatiebesluit. En alleen in een bevroren versie (`bevroren_op` in het manifest).
- **Een bevroren versie verandert niet.** Een fout in gold wordt `v<N+1>` met `voorganger` en een
  changelog per gid; een stille correctie laat de hash afwijken en de test falen.
- **Niet beoordeeld is leeg.** `v1` is de migratie van de ongeversioneerde `cases.json` (stand
  25 sep 2026) zonder inhoudelijke wijziging. Alle casussen staan op `provisional`, en
  `source_status`, `constructies`, negatieve elementen en de adjudicatievelden zijn leeg: invullen
  hoort bij de beoordeling, niet bij de migratie.
**Correctie 25 sep 2026:** bij RVV01 (E01), RVV02 (E04) en RVV03 (E05) wees de offset van
"voetgangers" naar het begin van het woord "voetgangerslichten". Het fragment klopte, de plek niet.
De offsets wijzen nu naar het zelfstandige woord in de norm. Een test in graph-qa eist sindsdien dat
elke markering letterlijk is en op woordgrenzen ligt. Metingen van vóór die datum rekenden beide
routes op deze drie markeringen onterecht af.
De leesbare dossiers zijn gegenereerd uit dat bestand:

```bash
python3 tools/graph-qa/scripts/render_jas_referentieset.py
python3 tools/graph-qa/scripts/render_jas_referentieset.py --check
```

IW/Awb gebruiken het bestaande versiegebonden evaluatiecorpus. Wzt gebruikt een historische
online weergave van 2025. RVV, BW en Omgevingswet gebruiken oorspronkelijke Staatsbladen,
gecontroleerd op respectievelijk p.13, p.135–136 en p.2–3. PDF-regelafbrekingen zijn in de
analysetekst samengevoegd; spelling en inhoud zijn visueel gecontroleerd. Het originele
PDF-bestand blijft als controlebron bewaard. Dit materiaal zegt niet dat de betreffende
tekst vandaag toepasselijk is. Actualiteit is een afzonderlijk onderzoeks- en reviewpunt.

## Samen beoordelen

Begin met IW01, AWB04 en RVV03: ze maken fragmentgrenzen, berekeningen en negaties direct
bespreekbaar. De reviewer maakt eerst een eigen duiding vanuit het bronpakket; daarna
vergelijken we het concept. Registreer per casus:

- Ontbrekende context/bronnen en normeenheden.
- Aanpassingen van fragment, klasse, relatie of scenario-uitkomst, met reden.
- Aanvaardbare alternatieven en resterende interpretatievragen.
- Reviewer, datum, besluit en eventuele voorwaarden voor vaststelling.

Breid de conceptmarkeringen uit tot volledige beoordeelde annotaties voordat een casus
voor precision/recall wordt gebruikt. De bestaande `golden_annotatie.jsonl` blijft een
conceptankerset, niet deze nieuwe referentieset. De evidente losse werkwoordankers
zijn op 12 september 2026 vervangen door betekenisdragende fragmenten; oude versies
blijven via Git beschikbaar. Vergelijk scores niet rechtstreeks
als de referentiegrenzen veranderen; herscore beide modeluitkomsten tegen dezelfde set.

De matrix bestrijkt veel taalverschijnselen, maar nog geen volwaardig overgangsrechtgeval.
Dat blijft een expliciete dekkingslacune vóór algemene claims over temporele kwaliteit.
Voor modelvergelijking: zelfde bronpakketten/modelinstellingen, drie herhalingen per geval,
voorspellingen opslaan, kritieke fouten en menselijke reviewlast apart rapporteren.
