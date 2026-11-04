# Referentieset bronselectie – Bestuurdersaansprakelijkheid, per deelvraag

Soort: *meting* (referentie) · Status: **concept, niet geadjudiceerd** · Hoort bij: PLAN spoor F *Vervolg*,
het rangsignaal van `bepaling_opties`

De **held-out set** voor de rangschikking van november 2026: wet vóór beleidsregel, of een lengtecorrectie. Op
3 nov 2026 bleek dat de Leidraad Invordering met haar lange divisies de top 8 overstroomt; de twee bestaande sets
(`bezwaar-ontvankelijkheid-concept`, `invorderbaarheid-deelvragen-concept`) zijn daarmee ontwikkelsets. Deze set
moet dat probleem toetsen, en heeft daarom bewust een wet én een beleidsregel: de Invorderingswet 1990 (art. 36 en
49) en de Leidraad Invordering 2008 (art. 36 en 49, met lange divisies).

**Blind.** De agent stelde de set op uit de letterlijke tekst in de graaf (acceptatie, 3 nov 2026), zonder
`bepaling_opties` erop te draaien, en hij staat in een eigen commit vóór de nieuwe code. De deelvragen zijn
geformuleerd zoals een analist ze typt ("oud-bestuurder", "feitelijk het beleid bepaalde"), niet in de woorden
van de wet. Op verzoek van de gebruiker (3 nov 2026) zonder review vooraf; tot een jurist hem vaststelt heten de
cijfers een trendmeting.

Vier deelvragen, 22 verwachte bepalingen (18 nodig: kern of afhankelijkheid), 3 uitgesloten.

Meten, vanuit `tools/graph-qa`:

```bash
uv run python -m eval.bronselectie_eval --intake --set bestuurdersaansprakelijkheid-concept --opnemen  # live, één keer
uv run python -m eval.bronselectie_eval --intake --set bestuurdersaansprakelijkheid-concept            # offline
```
