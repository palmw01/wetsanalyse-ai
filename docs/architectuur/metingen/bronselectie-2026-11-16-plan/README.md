# Bronselectie – de stappen van het plan Termijnen (16 nov 2026)

Soort: *meting* · Hoort bij: [onderzoek-bronselectie-termijnen-2026-11.md](../../onderzoek-bronselectie-termijnen-2026-11.md),
nulmeting [`bronselectie-2026-11-16-nulmeting/`](../bronselectie-2026-11-16-nulmeting/README.md)

Per stap van het plan is er een vlag in `Zoekprofiel`, en die staat standaard uit. Elke vlag is offline gemeten met
`eval/bronselectie_eval.py --intake --plan`, op de zes ontwikkelsets, tegen de opnames van acceptatie en zonder model. Nieuwe
vragen aan de graaf zijn met `--aanvullen` live opgehaald en aan de opnames toegevoegd. De cijfers zijn een trendmeting op
ontwikkelsets. Een winst geldt pas na de blinde set van stap 8. De held-out set Verrekening is niet gedraaid.

## Stap 1a – `termen_idf` (O6)

Recall nodig per set, eerst de standaard, dan met de vlag (precisie tussen haakjes):

- Termijnen: 0,00 (0,04) → 0,00 (0,00); recall 0,06 → 0,00; pool 1,00 → 0,94
- Rekeningafspraken: 0,14 (0,03) → 0,14 (0,03)
- Bestuurdersaansprakelijkheid: 0,22 (0,09) → 0,28 (0,12); pool 0,91 → 0,86
- Bezwaar/ontvankelijkheid: 0,53 (0,25) → 0,53 (0,25)
- Invorderbaarheid (deelvragen): 0,36 (0,28) → 0,36 (0,28)
- Kwijtschelding: 0,10 (0,06) → 0,14 (0,12); pool 0,33 → 0,46

**Oordeel: gemengd, en zo verwacht.** De vlag helpt waar het onderscheidende woord buiten de eerste zes termen viel
(Kwijtschelding, Bestuurdersaansprakelijkheid), en verandert niets bij drie sets. Bij Termijnen komt de kern niet in de top
8. Het grootste verlies zit daar in de rangschikking om de beurt over zes regelingen (O7, stap 1b), niet in de termen. De
vlag blijft uit, en de beslissing valt in stap 8, in combinatie met de andere stappen.

De rapporten staan in [`stap1a/`](stap1a/).
