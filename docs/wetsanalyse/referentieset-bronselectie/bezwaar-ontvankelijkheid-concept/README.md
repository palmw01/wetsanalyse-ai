# Referentieset bronselectie – Ontvankelijkheid van bezwaar tegen een belastingaanslag

Soort: *meting* (referentie) · Status: **concept, niet geadjudiceerd** · Hoort bij: PLAN spoor F3f

De meetlat voor *bepalingen per deelvraag*: welke leden horen bij elke deelvraag van de analysevraag
*"Wanneer is een bezwaarschrift tegen een belastingaanslag ontvankelijk?"*, binnen de Algemene wet
bestuursrecht en de Algemene wet inzake rijksbelastingen – en welke juist niet, omdat de analist ze buiten
de afbakening zette (beroep, het horen, de uitspraak).

| Bestand | Inhoud |
|---|---|
| `set.json` | analysevraag, praktijkvoorbeeld, afbakening (`buiten`), regelingen, deelvragen; per verwachte bepaling de deelvraag (index), rol (kern / afhankelijkheid / aanverwant), motivering en herkomst; de uitgesloten bepalingen met reden |
| `graafantwoorden.json` | de opgenomen antwoorden van de graaf (acceptatie, 21 okt 2026), zodat de meting offline en in CI draait |

**Herkomst.** De agent heeft de set opgesteld uit de letterlijke tekst in de graaf, **vóór** de zoekfunctie
erop draaide: de set staat in een eigen commit, vóór de meetcode. Een "eigen keuze" is een bepaling die
de agent erbij nam zonder dat de tekst haar dwingend aanwijst. **Een jurist stelt de set vast**; tot dan
heten de cijfers een trendmeting.

**Eén keer blind gemeten, daarna een ontwikkelset.** De Awb kwam in geen eerdere meting voor (invordering
is de ontwikkelset van bronselectie; Awir en AWR zijn door de begrippen gezien). De eerste meting (21 okt
2026, [`bronselectie-2026-10-21`](../../../architectuur/metingen/bronselectie-2026-10-21/README.md)) was
blind; daarna zijn op deze set bijstellingen van de rangschikking uitgeprobeerd. Een volgende wijziging
aan de zoekfunctie hoort ook op een nieuwe set gemeten te worden.

Meten, vanuit `tools/graph-qa`:

```bash
uv run python -m eval.bronselectie_eval --intake --set bezwaar-ontvankelijkheid-concept            # offline
uv run python -m eval.bronselectie_eval --intake --set bezwaar-ontvankelijkheid-concept --opnemen  # live
```
