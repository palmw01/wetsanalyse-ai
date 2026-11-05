# Referentieset bronselectie – Invorderbaarheid, per deelvraag

Soort: *meting* (referentie) · Status: **concept, niet geadjudiceerd** · Hoort bij: PLAN spoor J, de
rangschikking van `bepaling_opties`

De **held-out set** voor de zoek- en rangschikkingswijziging van november 2026. De bezwaarset
(`bezwaar-ontvankelijkheid-concept`) is sinds 21 okt 2026 een ontwikkelset; deze set is niet gebruikt om iets af
te stemmen.

Dezelfde analysevraag als `invorderbaarheid-concept` (*"Wanneer is een belastingaanslag invorderbaar?"*), maar met
vier deelvragen en per deelvraag de verwachte bepalingen, binnen de Invorderingswet 1990 en de Leidraad Invordering
2008. De oude set blijft ongewijzigd: die meet de methoden van de bronnenrun vanaf een kern.

**Blind.** De agent stelde de set op uit de letterlijke tekst in de graaf (acceptatie, 3 nov 2026), zonder
`bepaling_opties` erop te draaien, en hij staat in een eigen commit vóór de nieuwe code. De deelvragen zijn
geformuleerd zoals een analist ze typt ("direct invorderbaar"), niet in de woorden van de wet.

**Een jurist stelt de set vast**; tot dan heten de cijfers een trendmeting.

Meten, vanuit `tools/graph-qa`:

```bash
uv run python -m eval.bronselectie_eval --intake --set invorderbaarheid-deelvragen-concept --opnemen  # live, één keer
uv run python -m eval.bronselectie_eval --intake --set invorderbaarheid-deelvragen-concept            # offline
```
