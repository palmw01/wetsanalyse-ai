# Referentieset bronselectie – Teruggave inhouden voor een belastingschuld (verrekening), per deelvraag

Soort: *meting* (referentie) · Status: **concept, niet geadjudiceerd** · Hoort bij: het plan *bronselectie langs
de vier zoekvragen* (PLAN spoor F), skill `references/zoekvragen-bronselectie.md`

Dit is de **held-out set** voor de bronnenrun die vanaf de gebeurtenis zoekt langs de vier zoekvragen: a
bestaansrecht, b rechtsgeldigheid, c rechtsgevolgen, d nadere invulling. De vijf bestaande sets zijn
ontwikkelsets; op 4 nov 2026 ging de laatste (kwijtschelding) blind verloren aan de woordenkloof (pool 0,33).

**Opzet.**
- Schema versie 3: elke verwachte bepaling draagt naast haar `rol` ook haar `zoekvraag` (a–d). Zo is de
  recall per zoekvraag te meten.
- Het veld `gebeurtenis` (`verrekening`) is wat de analist in de vraagkaart *Om welke gebeurtenis gaat het?*
  kiest. De naam, de analysevraag en de deelvragen zeggen het woord van de wet bewust **nergens**: de analist
  schrijft "teruggave inhouden" en "wegstrepen". Een route kan de gebeurtenis gebruiken zoals de analist haar
  kiest, en apart kan gemeten worden of Lex haar zelf voorstelt.
- De stof: de Invorderingswet 1990 (art. 24, de grondslag), de Algemene wet bestuursrecht (art. 4:93, verrekening
  in het bestuursrecht) en de Leidraad Invordering 2008 (art. 24).
- Het volledige dossier: naam, aanleiding, doel, analysevraag, praktijkvoorbeeld en afbakening.
- Het onderwerp verschilt van de ontwikkelsets: invorderbaarheid, bezwaar, bestuurdersaansprakelijkheid en
  kwijtschelding.

**Blind.** De agent stelde de set op uit de letterlijke tekst in de graaf (acceptatie, 4 nov 2026). Het enige
dat er verder gedraaid is, is een controle of de IRI's bestaan; `bepaling_opties`, de bronnenrun en de eval zijn
er niet op gedraaid. De set staat in een eigen PR vóór de code, en de graafopname komt pas bij de meting. Op
verzoek van de gebruiker (4 nov 2026) is er vooraf geen review geweest. Tot een jurist de set vaststelt, heten de
cijfers een trendmeting.

Vier deelvragen, 21 verwachte bepalingen (18 nodig: kern of afhankelijkheid), 3 uitgesloten. Per zoekvraag:
a 3, b 5, c 4, d 9.

Meten, vanuit `tools/graph-qa`:

```bash
uv run python -m eval.bronselectie_eval --intake --set verrekening-concept --opnemen  # live, één keer
uv run python -m eval.bronselectie_eval --intake --set verrekening-concept            # offline
```
