# Referentieset bronselectie – Termijnen, per deelvraag

Soort: *meting* (referentie) · Status: **concept, ontwikkelset, niet geadjudiceerd** · Hoort bij:
[het onderzoek naar de bronselectie bij Termijnen](../../../architectuur/onderzoek-bronselectie-termijnen-2026-11.md), stap 0

**Een ontwikkelset, geen bewijs.** Het dossier staat letterlijk zoals in het werkgebied *Termijnen* op acceptatie: de
naam, de analysevraag, het praktijkvoorbeeld, de gebeurtenis *invordering*, het zoekbereik en de drie deelvragen. De
verwachte bepalingen komen uit het onderzoek en zijn letterlijk getoetst in de graaf en bij de officiële bron. De
oorzaken in dat onderzoek zijn op dit werkgebied gevonden, dus winst op deze set zegt niets over een ander werkgebied.

- De gebeurtenis *invordering* omvat bijna de hele Invorderingswet. Dat is precies het geval van oorzaak O1, en
  hetzelfde als bij `invorderbaarheid-deelvragen-concept`.
- Het winstaandeel staat in de Mijnbouwwet. Die staat niet in het zoekbereik, dus onder `buiten_graaf`, en telt niet
  in de noemer.
- De uitgesloten bepalingen zijn de ruis die de bronnenrun van 16 nov 2026 voorstelde (Leidraad 79.x, 10.3 en 78.1,
  Awir 30 lid 2, Awb-beslistermijnen).

Meten, vanuit `tools/graph-qa`:

```bash
uv run python -m eval.bronselectie_eval --intake --b2 --set termijnen-deelvragen-concept
uv run python -m eval.bronselectie_eval --zoekvragen --set termijnen-deelvragen-concept
```

De opname (`graafantwoorden.json`) is gemaakt op acceptatie op 16 nov 2026 (`--opnemen` en `--aanvullen`).
