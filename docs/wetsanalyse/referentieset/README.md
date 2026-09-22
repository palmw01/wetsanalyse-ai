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

[Cases.json](cases.json) bewaart de exacte analysetekst met SHA-256, vindplaats,
bron-ID, conceptmarkeringen en offsets. De offsets tellen Python-Unicode-codepunten
binnen deze analysetekst; ze zijn geen vervanging van de platformankers.
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
