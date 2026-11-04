# Referentieset bronselectie – Kwijtschelding voor particulieren, per deelvraag

Soort: *meting* (referentie) · Status: **concept, niet geadjudiceerd** · Hoort bij: PLAN spoor F *Vervolg*, de
opdracht "het dossier zoekt mee" in `bepaling_opties`

Dit is de **held-out set** voor november 2026. Tot nu toe telde het dossier in `bepaling_opties` alleen mee voor
de volgorde. De ingrepen die het werkgebied laten meezoeken, worden op deze set getoetst:
- aanleiding en doel lezen;
- per dossierterm een eigen lijst;
- het artikel of de divisie die het dossier aanwijst;
- de similarity-index.

Op 3 nov 2026 bleek waar het verlies zit. Op de held-out set `bestuurdersaansprakelijkheid-concept` vond de index
de verwachte bepalingen wel (pool 0,91), maar zette de fusie ze laag. De analist gebruikt andere woorden dan de
wet. Alle vier de bestaande sets zijn nu ontwikkelsets.

**Opzet.** Dit is de eerste set met een **volledig dossier**:
- naam, aanleiding, doel, analysevraag, praktijkvoorbeeld en afbakening (`buiten`);
- drie soorten regeling: de Invorderingswet 1990 (art. 26), de Uitvoeringsregeling Invorderingswet 1990 (de
  kwijtschelding voor particulieren, art. 7–25) en de Leidraad Invordering 2008 (art. 26);
- deelvragen in de woorden van een analist: "de belastingschuld laten vervallen", "niet genoeg inkomen",
  "spaargeld", "de inning gaat door". De wet zegt "kwijtschelding", "betalingscapaciteit", "financiële middelen"
  en "dwanginvordering".

Het onderwerp verschilt van de ontwikkelsets: invorderbaarheid (Iw 9), bezwaar (Awb/AWR) en
bestuurdersaansprakelijkheid (Iw 36/49).

**Blind.** De agent stelde de set op uit de letterlijke tekst in de graaf (acceptatie, 4 nov 2026). Hij draaide er
`bepaling_opties` en de eval niet op. De set staat in een eigen commit vóór de nieuwe code, en de graafopname komt
pas bij de meting. Op verzoek van de gebruiker (4 nov 2026) is er vooraf geen review geweest. Tot een jurist de set
vaststelt, heten de cijfers een trendmeting.

Vier deelvragen, 24 verwachte bepalingen (21 nodig: kern of afhankelijkheid), 3 uitgesloten. Een bepaling mag bij
meer deelvragen horen: Uitv.reg art. 7 lid 1 is de grondslag (deelvraag 1) én regelt het schriftelijke verzoek
(deelvraag 3).

Meten, vanuit `tools/graph-qa`:

```bash
uv run python -m eval.bronselectie_eval --intake --set kwijtschelding-concept --opnemen  # live, één keer
uv run python -m eval.bronselectie_eval --intake --set kwijtschelding-concept            # offline
```
