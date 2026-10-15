# Referentieset bronselectie – Invorderbaarheid van belastingaanslagen

Soort: *meting* (referentie) · Status: **concept, niet geadjudiceerd** · Hoort bij: PLAN spoor D, fase A

De meetlat voor *bronnen vinden met Lex*: welke bepalingen horen bij de analysevraag *"Wanneer is een
belastingaanslag invorderbaar?"* met als kern Invorderingswet 1990, art. 9 – en welke juist niet.

| Bestand | Inhoud |
|---|---|
| `set.json` | analysevraag, naam, kern; per verwachte bepaling de rol (kern / afhankelijkheid / aanverwant), motivering en herkomst; wat buiten de graaf valt; de uitgesloten bepalingen met reden |
| `graafantwoorden.json` | de opgenomen antwoorden van de graaf (acceptatie, 15 okt 2026), zodat de meting offline en in CI draait |

**Herkomst.** De agent heeft de set opgesteld uit de graaf en het
[invorderingsonderzoek van 29 sep 2026](../../onderzoek-invordering-2026-09-29/dossiers.md) (de
contextpassages en de open bronvragen daar). Elke regel noemt haar herkomst; een "eigen keuze" is niet
door dat onderzoek gedekt. **Een jurist stelt de set vast**; tot dan heten de cijfers een trendmeting.

**Gebruikt om te verbeteren.** De meting van 15 okt 2026 leidde tot een reparatie (de onderwerp-terugval
van het overzicht) en tot de keuze van de standaardmethoden. Deze set is daarmee een
**ontwikkelset**: een volgende wijziging aan de methoden hoort ook op een andere, nog niet gebruikte set
gemeten te worden.

Meten, vanuit `tools/graph-qa`:

```bash
uv run python -m eval.bronselectie_eval            # offline, tegen de opname
uv run python -m eval.bronselectie_eval --opnemen  # live (GRAPHDB_MCP_URL, GRAPHDB_TOKEN) en de opname vernieuwen
```

De meting zelf: [`docs/architectuur/metingen/bronselectie-2026-10-15/`](../../../architectuur/metingen/bronselectie-2026-10-15/README.md).
